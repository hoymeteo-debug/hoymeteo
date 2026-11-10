#!/usr/bin/env python3
"""Publica en Instagram el material generado por run.py.

  python publish.py jpeg                 # convierte output/<hoy>/ a JPEG en media/<hoy>/
  python publish.py check                # comprueba token, cuenta y límite (no publica)
  python publish.py run --mode prepare   # prepara carruseles y stories en Instagram, SIN publicar
  python publish.py run --mode publish   # publica cada serie a su hora (config.SERIES[*]["post_time"])

Variables de entorno: IG_ACCESS_TOKEN (obligatoria), IG_USER_ID (opcional) y
MEDIA_BASE_URL (URL pública donde están las JPEG de media/, p. ej. la rama "media" del repo).
"""
import argparse
import os
import sys
import time
from datetime import date, datetime
from zoneinfo import ZoneInfo

from PIL import Image

import config
from instagram import Instagram, InstagramError

MEDIA_DIR = config.BASE / "media"
TZ = ZoneInfo(config.TIMEZONE)


def today():
    return datetime.now(TZ).date()


# --- JPEG ------------------------------------------------------------------------
def export_jpeg(target: date):
    """Instagram solo acepta JPEG: convierte cada PNG de output/ a media/."""
    src_root = config.OUTPUT_DIR / target.isoformat()
    if not src_root.exists():
        sys.exit(f"No hay material en {src_root}. Ejecuta antes run.py")
    count = 0
    for png in sorted(src_root.glob("*/*.png")):
        dst = MEDIA_DIR / target.isoformat() / png.parent.name / (png.stem + ".jpg")
        dst.parent.mkdir(parents=True, exist_ok=True)
        Image.open(png).convert("RGB").save(dst, "JPEG", quality=92, optimize=True, progressive=False)
        count += 1
    for caption in src_root.glob("*/caption.txt"):  # TikTok lo lee desde aquí
        (MEDIA_DIR / target.isoformat() / caption.parent.name / "caption.txt").write_text(
            caption.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"{count} imágenes JPEG en {MEDIA_DIR / target.isoformat()}")


def series_material(target: date):
    """Devuelve [(clave, cfg, [slides], story, caption)] de las series generadas hoy."""
    items = []
    for key, cfg in config.SERIES.items():
        folder = MEDIA_DIR / target.isoformat() / key
        caption_file = config.OUTPUT_DIR / target.isoformat() / key / "caption.txt"
        slides = sorted(folder.glob("slide_*.jpg"), key=lambda p: int(p.stem.split("_")[1]))
        if not slides or not caption_file.exists():
            continue
        story = folder / "story.jpg"
        items.append((key, cfg, slides, story if story.exists() else None,
                      caption_file.read_text(encoding="utf-8")))
    return items


def public_url(base, target, key, path):
    return f"{base.rstrip('/')}/{target.isoformat()}/{key}/{path.name}"


def wait_until(hhmm: str):
    hh, mm = map(int, hhmm.split(":"))
    now = datetime.now(TZ)
    goal = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if goal > now:
        print(f"  esperando a las {hhmm}…", flush=True)
        time.sleep((goal - now).total_seconds())


# --- Comandos ------------------------------------------------------------------------
def client():
    return Instagram(os.environ.get("IG_ACCESS_TOKEN", ""), os.environ.get("IG_USER_ID") or config.INSTAGRAM_USER_ID)


def cmd_check():
    import json
    ig = client()
    print(f"Token: empieza por {ig.token[:3]}…, {len(ig.token)} caracteres · API {ig.base}")
    for path, fields in (("me", "id,name"), ("me/accounts", "id,name,instagram_business_account")):
        try:
            body = ig._call("GET", path, fields=fields)
            print(f"{path}: {json.dumps(body, ensure_ascii=False)[:400]}")
        except InstagramError as exc:
            print(f"{path}: {exc}")
    info = ig.account_info()
    print(f"Cuenta: @{info.get('username')} · publicaciones: {info.get('media_count')}")
    print(f"Límite de publicación: {info.get('publishing_limit')}")


def cmd_run(mode: str, target: date, only=None):
    base = os.environ.get("MEDIA_BASE_URL", "")
    if not base:
        sys.exit("Falta MEDIA_BASE_URL")
    material = [m for m in series_material(target) if not only or m[0] in only]
    if not material:
        sys.exit("No hay series para publicar hoy")
    ig = client()
    print(f"Cuenta de Instagram: {ig.resolve_user_id()} · modo: {mode}")

    # Preparar todo primero: si una imagen falla, se sabe antes de las 07:00
    prepared, failures = [], []
    for key, cfg, slides, story, caption in material:
        try:
            urls = [public_url(base, target, key, s) for s in slides]
            carousel = ig.prepare_carousel(urls, caption) if len(urls) > 1 else ig.prepare_image(urls[0], caption)
            story_id = ig.prepare_story(public_url(base, target, key, story)) if story else None
            prepared.append((key, cfg, carousel, story_id))
            print(f"- {cfg['label']}: " + (f"carrusel de {len(slides)}" if len(slides) > 1 else "imagen") + " lista" + (" + story lista" if story_id else ""))
        except InstagramError as exc:
            failures.append(f"{cfg['label']}: {exc}")
            print(f"- ERROR {cfg['label']}: {exc}")

    if mode == "publish":
        for key, cfg, carousel, story_id in prepared:
            wait_until(cfg["post_time"])
            try:
                media_id = ig.publish(carousel)
                print(f"- {cfg['label']} publicado a las {datetime.now(TZ):%H:%M} (id {media_id})")
                if story_id:
                    ig.publish(story_id)
                    print(f"  story de {cfg['label']} publicada")
            except InstagramError as exc:
                failures.append(f"{cfg['label']}: {exc}")
                print(f"- ERROR al publicar {cfg['label']}: {exc}")
    else:
        print("Modo prueba: no se ha publicado nada (los contenedores caducan solos en 24 h).")

    # Errores de generación (p. ej. avisos que no se pudieron descargar): se publica el resto
    # y la ejecución termina con error para que GitHub avise por correo.
    gen_errors = config.OUTPUT_DIR / target.isoformat() / "ERRORES.txt"
    if gen_errors.exists():
        failures += [f"generación: {l}" for l in gen_errors.read_text(encoding="utf-8").splitlines() if l]
    if failures:
        sys.exit("Fallos:\n  " + "\n  ".join(failures))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["jpeg", "check", "run"])
    ap.add_argument("--mode", choices=["prepare", "publish"], default="prepare")
    ap.add_argument("--date", help="AAAA-MM-DD (por defecto, hoy en Madrid)")
    ap.add_argument("--series", help="solo estas series, separadas por coma (p. ej. avisos)")
    args = ap.parse_args()
    target = date.fromisoformat(args.date) if args.date else today()
    try:
        if args.command == "jpeg":
            export_jpeg(target)
        elif args.command == "check":
            cmd_check()
        else:
            cmd_run(args.mode, target, [k.strip() for k in args.series.split(',')] if args.series else None)
    except InstagramError as exc:
        sys.exit(f"ERROR de Instagram: {exc}")


if __name__ == "__main__":
    main()
