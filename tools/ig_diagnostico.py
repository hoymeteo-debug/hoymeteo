#!/usr/bin/env python3
"""Diagnóstico de Instagram: publica una pieza suelta de una serie del día.

Modos: story, imagen (una foto en el feed), carrusel, carrusel-sin-texto.

  python tools/ig_diagnostico.py avisos
"""
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
from instagram import Instagram, InstagramError  # noqa: E402

import urllib.request  # noqa: E402

key = sys.argv[1] if len(sys.argv) > 1 else "avisos"
mode = sys.argv[2] if len(sys.argv) > 2 else "story"
d = datetime.now(ZoneInfo(config.TIMEZONE)).date().isoformat()
base = f"{os.environ['MEDIA_BASE_URL'].rstrip('/')}/{d}/{key}"
ig = Instagram(os.environ["IG_ACCESS_TOKEN"], os.environ.get("IG_USER_ID") or config.INSTAGRAM_USER_ID)
if mode == "listar":  # últimas publicaciones del feed y stories activas (no publica nada)
    uid = ig.resolve_user_id()
    for m in ig._call("GET", f"{uid}/media", fields="id,timestamp,media_type,caption,permalink", limit=30)["data"]:
        print("feed ", m.get("id"), m.get("timestamp"), m.get("media_type"),
              (m.get("caption") or "").split("\n")[0][:60], m.get("permalink"))
    for m in ig._call("GET", f"{uid}/stories", fields="timestamp,media_type")["data"]:
        print("story", m.get("timestamp"), m.get("media_type"))
    print("Límite:", ig._call("GET", f"{uid}/content_publishing_limit", fields="config,quota_usage"))
    sys.exit(0)
try:
    if mode == "story":
        cid = ig.prepare_story(f"{base}/story.jpg")
    elif mode == "imagen":  # una sola imagen en el feed (sin carrusel)
        cid = ig.prepare_image(f"{base}/slide_1.jpg", "Prueba")
    else:
        caption = urllib.request.urlopen(f"{base}/caption.txt").read().decode("utf-8")
        slides, n = [], 1
        while True:
            u = f"{base}/slide_{n}.jpg"
            try:
                urllib.request.urlopen(urllib.request.Request(u, method="HEAD"))
            except Exception:
                break
            slides.append(u)
            n += 1
        print(f"Carrusel de {len(slides)} con texto de {len(caption)} caracteres y {caption.count('#')} hashtags")
        cid = ig.prepare_carousel(slides, caption if mode == "carrusel" else "")
        print("Estado:", ig._call("GET", cid, fields="status_code,status"))
    print("Preparado:", cid)
    print("Publicado:", ig.publish(cid))
except InstagramError as exc:
    sys.exit(f"ERROR: {exc}")
