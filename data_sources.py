"""Obtención de datos (AEMET real o de ejemplo) y construcción de rankings."""
import csv
import json
import random
import re
import unicodedata

import config
from aemet_client import AemetClient, AemetError, parse_diaria, parse_horaria, resolve_municipios


def load_municipios():
    with open(config.MUNICIPIOS_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["hashtag"] = (r.get("hashtag") or "").strip() or make_hashtag(r["nombre"])
    return rows


def make_hashtag(name: str) -> str:
    s = unicodedata.normalize("NFD", name)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    words = re.findall(r"[A-Za-z0-9]+", s)
    return "#" + "".join(w[:1].upper() + w[1:] for w in words)


# --- Datos reales -------------------------------------------------------------
def fetch_records(api_key, municipios, target_date, use_cache=True, log=print):
    client = AemetClient(api_key)
    maestro = client.maestro_municipios(config.CACHE_DIR)
    resolved, unresolved = resolve_municipios(municipios, maestro)
    for row, sugg in unresolved:
        hint = f" (¿{', '.join(sugg)}?)" if sugg else ""
        log(f"  ! Sin resolver: {row['nombre']} [{row['provincia']}]{hint} -> corrige 'nombre_aemet' en municipios.csv")

    day_cache = config.CACHE_DIR / target_date.isoformat()
    day_cache.mkdir(parents=True, exist_ok=True)

    def cached(ine, kind, fetch):
        cache_file = day_cache / f"{ine}_{kind}.json"
        if use_cache and cache_file.exists():
            return json.loads(cache_file.read_text(encoding="utf-8"))
        payload = fetch(ine)
        cache_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return payload

    records, stale = [], 0
    for i, row in enumerate(resolved, 1):
        try:
            # Horaria: lluvia (mm) y rachas. Diaria: máxima y mínima oficiales del día.
            horaria, elaborado = parse_horaria(cached(row["ine"], "horaria", client.prediccion_horaria), target_date)
            diaria, _ = parse_diaria(cached(row["ine"], "diaria", client.prediccion_diaria), target_date)
        except (AemetError, KeyError, IndexError, TypeError, ValueError) as exc:
            log(f"  ! {row['nombre']}: {exc}")
            continue
        if horaria is None and diaria is None:
            log(f"  ! {row['nombre']}: la predicción no incluye el día {target_date}")
            continue
        values = {"tmax": None, "tmin": None, "rain_mm": None, "gust_kmh": None, "horas": 0}
        values.update(horaria or {})
        if diaria:
            values.update({k: v for k, v in diaria.items() if v is not None})
        if elaborado and str(elaborado)[:10] != target_date.isoformat():
            stale += 1
        records.append({"name": row["nombre"], "hashtag": row["hashtag"], **values})
        if i % 10 == 0:
            log(f"  {i}/{len(resolved)} municipios")
    if stale:
        log(f"  ! Aviso: {stale} predicciones están elaboradas otro día distinto de hoy (¿demasiado pronto?)")
    return records


# --- Datos de ejemplo (para probar el diseño sin clave) -------------------------
_REGIONS = {
    "canarias": ({"35", "38"}, (23, 28), (16, 20), (0, 3), (25, 60)),
    "sur": ({"04", "11", "14", "18", "21", "23", "29", "41", "51", "52"}, (19, 25), (8, 14), (0, 10), (20, 60)),
    "levante": ({"03", "12", "30", "43", "46", "08", "17", "07"}, (17, 22), (7, 13), (0, 12), (20, 55)),
    "norte": ({"15", "27", "32", "36", "33", "39", "20", "48", "01"}, (12, 17), (4, 10), (2, 40), (25, 65)),
}
_DEFAULT = ((10, 16), (-6, 4), (0, 6), (15, 50))


def demo_records(municipios, target_date):
    rng = random.Random(target_date.toordinal())
    records = []
    for m in municipios:
        tmax_r, tmin_r, rain_r, wind_r = _DEFAULT
        for provs, a, b, c, d in _REGIONS.values():
            if m["provincia"] in provs:
                tmax_r, tmin_r, rain_r, wind_r = a, b, c, d
                break
        rain = rng.uniform(*rain_r) if rng.random() < 0.7 else 0.0
        gust = rng.uniform(*wind_r)
        if m["nombre"] in ("Tarifa", "Teguise", "Mogán"):
            gust += 30
        records.append({
            "name": m["nombre"], "hashtag": m["hashtag"],
            "tmax": float(round(rng.uniform(*tmax_r))), "tmin": float(round(rng.uniform(*tmin_r))),
            "rain_mm": round(rain, 1), "gust_kmh": float(round(gust)),
        })
    return records


# --- Rankings -------------------------------------------------------------------
def build_ranking(records, series_cfg, top_n=config.TOP_N):
    field = series_cfg["field"]
    min_value = series_cfg.get("min_value")
    items = [r for r in records if r.get(field) is not None]
    if min_value is not None:
        items = [r for r in items if r[field] >= min_value]
    items.sort(key=lambda r: (r[field] if series_cfg["ascending"] else -r[field], r["name"]))
    return [{"name": r["name"], "hashtag": r["hashtag"], "value": r[field]} for r in items[:top_n]]
