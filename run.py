#!/usr/bin/env python3
"""Genera las publicaciones diarias de @hoymeteo.

Ejemplos:
  python run.py --demo                 # prueba con datos de ejemplo (sin clave)
  python run.py                        # datos reales de AEMET para hoy
  python run.py --series max,rain      # solo algunas series
  python run.py --probe Madrid         # comprueba la conexión con AEMET y muestra lo que lee
"""
import argparse
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

import captions
import config
import data_sources as ds
import render

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None


def load_env():
    env_file = config.BASE / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def today_madrid():
    if ZoneInfo:
        return datetime.now(ZoneInfo(config.TIMEZONE)).date()
    return date.today()


def probe(name):
    from aemet_client import AemetClient, parse_diaria, parse_horaria, resolve_municipios
    key = os.environ.get("AEMET_API_KEY", "")
    client = AemetClient(key)
    rows = [r for r in ds.load_municipios() if r["nombre"].lower() == name.lower()]
    if not rows:
        sys.exit(f"'{name}' no está en municipios.csv")
    resolved, unresolved = resolve_municipios(rows, client.maestro_municipios(config.CACHE_DIR))
    if not resolved:
        sys.exit(f"No se pudo resolver {name}: {unresolved}")
    ine = resolved[0]["ine"]
    payload = client.prediccion_horaria(ine)
    day = payload[0]["prediccion"]["dia"][0]
    print(f"Municipio {name} (INE {ine}), elaborado: {payload[0].get('elaborado')}")
    print("Campos del primer día:", sorted(day.keys()))
    print("Ejemplo vientoAndRachaMax:", day.get("vientoAndRachaMax", [])[:2])
    values, _ = parse_horaria(payload, today_madrid())
    print("Horaria (lluvia, rachas) para hoy:", values)
    diaria, elab_d = parse_diaria(client.prediccion_diaria(ine), today_madrid())
    print(f"Diaria (máx/mín oficiales) para hoy: {diaria} · elaborado {elab_d}")


class SuspiciousData(SystemExit):
    """Datos que no deben publicarse: la ejecución termina con error y GitHub avisa por correo."""


def check_and_save(records, municipios, target):
    """Salvaguardas antes de generar nada y registro diario en history/.

    - Faltan demasiados municipios (AEMET caído o respuesta incompleta).
    - Valores idénticos a los de ayer (predicción no actualizada).
    El histórico también sirve para "hoy vs ayer" y para los récords semanales.
    """
    min_ok = int(len(municipios) * config.MIN_COVERAGE)
    if len(records) < min_ok:
        raise SuspiciousData(f"ERROR: solo {len(records)} municipios con datos (mínimo {min_ok}). No se publica.")

    fields = ("tmax", "tmin", "rain_mm", "gust_kmh")
    today = {r["name"]: {f: r.get(f) for f in fields} for r in records}
    prev_file = config.HISTORY_DIR / f"{date.fromordinal(target.toordinal() - 1).isoformat()}.json"
    if prev_file.exists():
        prev = json.loads(prev_file.read_text(encoding="utf-8"))
        if prev == today:
            raise SuspiciousData("ERROR: los datos son idénticos a los de ayer. No se publica.")

    config.HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    (config.HISTORY_DIR / f"{target.isoformat()}.json").write_text(
        json.dumps(today, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


def main():
    load_env()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--demo", action="store_true", help="usa datos de ejemplo")
    ap.add_argument("--date", help="fecha AAAA-MM-DD (por defecto, hoy en Madrid)")
    ap.add_argument("--series", default=",".join(config.SERIES), help="series separadas por coma: " + ",".join(config.SERIES))
    ap.add_argument("--refresh", action="store_true", help="ignora la caché y vuelve a pedir a AEMET")
    ap.add_argument("--probe", metavar="MUNICIPIO", help="prueba la conexión con un municipio")
    args = ap.parse_args()

    if args.probe:
        return probe(args.probe)

    target = date.fromisoformat(args.date) if args.date else today_madrid()
    keys = [k.strip() for k in args.series.split(",") if k.strip()]
    unknown = [k for k in keys if k not in config.SERIES]
    if unknown:
        sys.exit(f"Series desconocidas: {unknown}")

    municipios = ds.load_municipios()
    print(f"Fecha: {target} · {len(municipios)} municipios en la lista · {'DEMO' if args.demo else 'AEMET'}")
    if args.demo:
        records = ds.demo_records(municipios, target)
    else:
        key = os.environ.get("AEMET_API_KEY", "")
        if not key:
            sys.exit("Falta AEMET_API_KEY. Copia .env.example a .env y pon tu clave (o usa --demo).")
        records = ds.fetch_records(key, municipios, target, use_cache=not args.refresh)
    print(f"Datos válidos: {len(records)} municipios")
    if not args.demo:
        check_and_save(records, municipios, target)

    out_root = config.OUTPUT_DIR / target.isoformat()
    date_label = captions.fecha_corta(target)
    made = 0
    for key in keys:
        cfg = config.SERIES[key]
        ranking = ds.build_ranking(records, cfg)
        if len(ranking) < cfg["min_items"]:
            print(f"- {cfg['label']}: solo {len(ranking)} municipios con datos, no se publica hoy")
            continue
        out = out_root / key
        slides = render.render_carousel(cfg, ranking, date_label, out)
        story = render.render_story(cfg, ranking, date_label, out / "story.png")
        (out / "caption.txt").write_text(captions.build_caption(cfg, ranking, target), encoding="utf-8")
        print(f"- {cfg['label']} ({cfg['post_time']}): {len(slides)} diapositivas + story + texto -> {out}")
        made += 1
    print(f"Listo: {made} series generadas en {out_root}")


if __name__ == "__main__":
    main()
