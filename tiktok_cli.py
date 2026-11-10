#!/usr/bin/env python3
"""TikTok para @hoymeteo.

  python tiktok_cli.py url                        # enlace para autorizar la cuenta (una vez)
  python tiktok_cli.py connect --code CODIGO      # guarda la autorización cifrada
  python tiktok_cli.py check                      # renueva el acceso y muestra la cuenta
  python tiktok_cli.py post --serie max           # publica el carrusel de una serie (por defecto, privado)

Variables: TIKTOK_CLIENT_SECRET (secreto). La client key va en config.TIKTOK_CLIENT_KEY
(o en TIKTOK_CLIENT_KEY): no es secreta, aparece en el enlace de autorización.
"""
import argparse
import os
import sys
from datetime import date, datetime
from zoneinfo import ZoneInfo

import config
from tiktok import TikTok, TikTokError, load_state, save_state

SITE = "https://hoymeteo-debug.github.io/hoymeteo"
REDIRECT_URI = f"{SITE}/tiktok/"


def client():
    key = config.TIKTOK_CLIENT_KEY or os.environ.get("TIKTOK_CLIENT_KEY", "")
    return TikTok(key, os.environ.get("TIKTOK_CLIENT_SECRET", ""), REDIRECT_URI)


def show_creator(tk):
    info = tk.creator_info()
    print(f"Cuenta de TikTok: {info.get('creator_nickname')} (@{info.get('creator_username')})")
    print(f"Privacidad permitida: {info.get('privacy_level_options')}")
    return info


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["url", "connect", "check", "post"])
    ap.add_argument("--code")
    ap.add_argument("--serie", default="max", choices=list(config.SERIES))
    ap.add_argument("--privacy", default="SELF_ONLY",
                    help="SELF_ONLY (solo yo, obligatorio sin auditoría) o PUBLIC_TO_EVERYONE")
    ap.add_argument("--date", help="AAAA-MM-DD (por defecto, hoy en Madrid)")
    args = ap.parse_args()

    try:
        if args.command == "url":
            key = config.TIKTOK_CLIENT_KEY or os.environ.get("TIKTOK_CLIENT_KEY", "")
            print(TikTok(key, "-", REDIRECT_URI).authorize_url())
            return
        tk = client()
        if args.command == "connect":
            if not args.code:
                sys.exit("Falta --code")
            save_state(tk.exchange_code(args.code), tk.client_secret)
            print("TikTok conectado. Autorización guardada cifrada en tiktok_state.enc")
            show_creator(tk)
            return

        state = tk.refresh(load_state(tk.client_secret))
        save_state(state, tk.client_secret)  # el token de renovación cambia: guardar siempre el último
        info = show_creator(tk)
        if args.command == "check":
            return

        if args.privacy not in (info.get("privacy_level_options") or []):
            sys.exit(f"Privacidad {args.privacy} no permitida para esta cuenta: {info.get('privacy_level_options')}")
        target = date.fromisoformat(args.date) if args.date else datetime.now(ZoneInfo(config.TIMEZONE)).date()
        cfg = config.SERIES[args.serie]
        media = config.BASE / "media" / target.isoformat() / args.serie
        slides = sorted(media.glob("slide_*.jpg"), key=lambda p: int(p.stem.split("_")[1]))
        if not slides:
            sys.exit(f"No hay imágenes en {media}")
        urls = [f"{SITE}/media/{target.isoformat()}/{args.serie}/{p.name}" for p in slides]
        caption = (media / "caption.txt").read_text(encoding="utf-8")
        title = caption.splitlines()[0]
        publish_id = tk.post_photos(urls, title, caption, args.privacy)
        print(f"Enviado a TikTok ({cfg['label']}, {args.privacy}): {publish_id}")
        tk.wait_published(publish_id)
        print("Publicado en TikTok")
    except TikTokError as exc:
        sys.exit(f"ERROR de TikTok: {exc}")


if __name__ == "__main__":
    main()
