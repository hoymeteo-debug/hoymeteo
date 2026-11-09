#!/usr/bin/env python3
"""Espera hasta una hora de Madrid (HH:MM). Si ya ha pasado, sale al momento.

GitHub Actions programa en UTC y su cron puede retrasarse; lanzamos pronto y
esperamos aquí, así el cambio de hora verano/invierno no afecta.
Uso: python wait_until.py 06:15
"""
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

hh, mm = map(int, sys.argv[1].split(":"))
now = datetime.now(ZoneInfo("Europe/Madrid"))
target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
seconds = (target - now).total_seconds()
if seconds > 0:
    print(f"Son las {now:%H:%M} en Madrid; espero hasta las {target:%H:%M} ({seconds / 60:.0f} min)", flush=True)
    time.sleep(seconds)
else:
    print(f"Son las {now:%H:%M} en Madrid; empiezo ya", flush=True)
