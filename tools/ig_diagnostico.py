#!/usr/bin/env python3
"""Diagnóstico de Instagram: publica solo la story (imagen) de una serie del día.

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

key = sys.argv[1] if len(sys.argv) > 1 else "avisos"
d = datetime.now(ZoneInfo(config.TIMEZONE)).date().isoformat()
url = f"{os.environ['MEDIA_BASE_URL'].rstrip('/')}/{d}/{key}/story.jpg"
ig = Instagram(os.environ["IG_ACCESS_TOKEN"], os.environ.get("IG_USER_ID") or config.INSTAGRAM_USER_ID)
try:
    cid = ig.prepare_story(url)
    print("Story preparada:", cid)
    print("Publicada:", ig.publish(cid))
except InstagramError as exc:
    sys.exit(f"ERROR: {exc}")
