#!/usr/bin/env python3
"""YouTube para @hoymeteo: el Short diario con todas las series.

  python youtube_cli.py url                      # enlace para autorizar el canal (una vez)
  python youtube_cli.py connect --code CODIGO    # guarda la autorización cifrada
  python youtube_cli.py check                    # renueva el acceso y muestra el canal
  python youtube_cli.py short [--privacy private] [--date AAAA-MM-DD]

Variables: YT_CLIENT_SECRET (secreto). El client id va en config.YOUTUBE_CLIENT_ID (no es secreto).
El Short y los textos se leen de media/<fecha>/ (los deja publish.py jpeg).
"""
import argparse
import os
import sys
from datetime import date, datetime
from zoneinfo import ZoneInfo

import captions
import config
import youtube as yt

REDIRECT_URI = "https://hoymeteo-debug.github.io/hoymeteo/youtube/"


def client():
    return yt.YouTube(config.YOUTUBE_CLIENT_ID or os.environ.get("YT_CLIENT_ID", ""),
                      os.environ.get("YT_CLIENT_SECRET", ""), REDIRECT_URI)


def short_texts(target):
    """Título y descripción a partir de la primera línea de cada serie."""
    media = config.BASE / "media" / target.isoformat()
    fecha = captions.fecha_larga(target)
    lines = []
    for key, cfg in config.SERIES.items():
        cap = media / key / "caption.txt"
        if cap.exists():
            lines.append(cap.read_text(encoding="utf-8").splitlines()[0])
    title = f"El tiempo de hoy en España · {fecha} #Shorts"
    description = "\n".join(
        [f"El tiempo de hoy, {fecha}, en rankings:", ""] + lines + [
            "",
            f"📍 Cada mañana, el tiempo de hoy en España para tomártelo con el café. Sigue a {config.HANDLE}.",
            "Fuente: AEMET (previsión). No es una cuenta oficial de AEMET.",
            "",
            "#ElTiempo #AEMET #Shorts",
        ])
    return title, description


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["url", "connect", "check", "short"])
    ap.add_argument("--code")
    ap.add_argument("--privacy", default="public", choices=["public", "unlisted", "private"])
    ap.add_argument("--date")
    args = ap.parse_args()
    try:
        if args.command == "url":
            print(yt.YouTube(config.YOUTUBE_CLIENT_ID or os.environ.get("YT_CLIENT_ID", "-"), "-", REDIRECT_URI).authorize_url())
            return
        c = client()
        if args.command == "connect":
            if not args.code:
                sys.exit("Falta --code")
            yt.save(c.exchange_code(args.code), c.client_secret)
            print("YouTube conectado. Autorización guardada cifrada en youtube_state.enc")
            print("Autorización válida (con el permiso de subida Google no deja leer el nombre del canal)")
            return
        old_state = yt.load(c.client_secret)
        state = c.refresh(old_state)
        if state != old_state:  # solo se reescribe si Google cambió el token
            yt.save(state, c.client_secret)
        print("Acceso a YouTube renovado")
        if args.command == "check":
            return
        target = date.fromisoformat(args.date) if args.date else datetime.now(ZoneInfo(config.TIMEZONE)).date()
        video = config.BASE / "media" / target.isoformat() / "short.mp4"
        if not video.exists():
            sys.exit(f"No hay Short en {video}")
        title, description = short_texts(target)
        vid = c.upload(video, title, description, tags=["el tiempo", "AEMET", "previsión", "España"],
                       privacy=args.privacy)
        print(f"Short subido ({args.privacy}): https://youtube.com/shorts/{vid}")
    except yt.YouTubeError as exc:
        sys.exit(f"ERROR de YouTube: {exc}")


if __name__ == "__main__":
    main()
