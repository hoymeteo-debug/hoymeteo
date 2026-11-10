"""Avisos meteorológicos de AEMET (Meteoalerta, formato CAP) para la serie de avisos.

AEMET publica un .tar con un XML por aviso y zona (incluidos los "verdes", sin aviso).
Aquí se descarga, se filtran los vigentes hoy en hora de Madrid y se agrupan por
zona + fenómeno, quedándose con el nivel más alto y las cifras de cada umbral.
"""
import io
import json
import re
import tarfile
import xml.etree.ElementTree as ET
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import config
from data_sources import make_hashtag

NS = {"c": "urn:oasis:names:tc:emergency:cap:1.2"}
TZ = ZoneInfo(config.TIMEZONE)
ENDPOINT = "/avisos_cap/ultimoelaborado/area/esp"

LEVELS = {"rojo": 3, "naranja": 2, "amarillo": 1}
LEVEL_NAMES = {3: "Rojo", 2: "Naranja", 1: "Amarillo"}

# Código de fenómeno -> (nombre corto, icono)
PHENOMENA = {
    "PR": ("Lluvias", "drop"), "TO": ("Tormentas", "bolt"), "VI": ("Viento", "wind"),
    "CO": ("Costeros", "wave"), "NE": ("Nieve", "snow"), "AT": ("Calor", "thermometer_plus"),
    "BT": ("Frío", "thermometer_minus"), "NI": ("Niebla", "fog"), "VS": ("Polvo", "fog"),
    "DH": ("Deshielo", "drop"), "GA": ("Galerna", "wind"), "AL": ("Aludes", "snow"),
    "RI": ("Rissagas", "wave"),
}
PHENOMENA_ORDER = ["PR", "TO", "VI", "CO", "NE", "AT", "BT", "NI", "VS", "AL", "DH", "GA", "RI"]

PROVINCIAS = {
    "01": "Álava", "02": "Albacete", "03": "Alicante", "04": "Almería", "05": "Ávila", "06": "Badajoz",
    "07": "Baleares", "08": "Barcelona", "09": "Burgos", "10": "Cáceres", "11": "Cádiz", "12": "Castellón",
    "13": "Ciudad Real", "14": "Córdoba", "15": "A Coruña", "16": "Cuenca", "17": "Girona", "18": "Granada",
    "19": "Guadalajara", "20": "Gipuzkoa", "21": "Huelva", "22": "Huesca", "23": "Jaén", "24": "León",
    "25": "Lleida", "26": "La Rioja", "27": "Lugo", "28": "Madrid", "29": "Málaga", "30": "Murcia",
    "31": "Navarra", "32": "Ourense", "33": "Asturias", "34": "Palencia", "35": "Las Palmas",
    "36": "Pontevedra", "37": "Salamanca", "38": "Santa Cruz de Tenerife", "39": "Cantabria",
    "40": "Segovia", "41": "Sevilla", "42": "Soria", "43": "Tarragona", "44": "Teruel", "45": "Toledo",
    "46": "Valencia", "47": "Valladolid", "48": "Bizkaia", "49": "Zamora", "50": "Zaragoza",
    "51": "Ceuta", "52": "Melilla",
}
# En Baleares y Canarias el código de zona indica la isla, no la provincia
ISLAS = {
    "53": "Ibiza y Formentera", "54": "Mallorca", "55": "Menorca",
    "90": "Gran Canaria", "91": "Lanzarote", "92": "Fuerteventura", "93": "La Palma",
    "94": "La Gomera", "95": "El Hierro", "96": "Tenerife",
}
HASHTAGS = {"Ibiza y Formentera": "#Ibiza", "Santa Cruz de Tenerife": "#Tenerife", "Álava": "#Alava"}


class AvisosError(Exception):
    pass


# --- Descarga ------------------------------------------------------------------------
def fetch_tar(client, target_date, cache_dir=config.CACHE_DIR, use_cache=True) -> bytes:
    cache = cache_dir / target_date.isoformat() / "avisos.tar"
    if use_cache and cache.exists():
        return cache.read_bytes()
    meta = json.loads(client._get("https://opendata.aemet.es/opendata/api" + ENDPOINT).decode("utf-8", "replace"))
    if meta.get("estado") != 200 or "datos" not in meta:
        raise AvisosError(f"AEMET avisos: {meta.get('estado')} {meta.get('descripcion')}")
    raw = client._get(meta["datos"])
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_bytes(raw)
    return raw


def read_tar(raw: bytes):
    """Devuelve la lista de XML (bytes) del paquete. Falla si no es un tar válido."""
    try:
        with tarfile.open(fileobj=io.BytesIO(raw)) as tar:
            return [tar.extractfile(m).read() for m in tar.getmembers() if m.isfile() and m.name.endswith(".xml")]
    except tarfile.TarError as exc:
        raise AvisosError(f"El paquete de avisos de AEMET no es válido: {exc}") from None


# --- Interpretación ---------------------------------------------------------------------
def _t(el, tag):
    return el.findtext(f"c:{tag}", namespaces=NS)


def parse_cap(xml_bytes):
    """Un XML CAP -> dict con lo necesario, o None si es verde / cancelación."""
    root = ET.fromstring(xml_bytes)
    if _t(root, "msgType") == "Cancel":
        return None
    infos = root.findall("c:info", NS)
    info = next((i for i in infos if _t(i, "language") == "es-ES"), infos[0] if infos else None)
    if info is None:
        return None
    params = {_t(p, "valueName"): _t(p, "value") for p in info.findall("c:parameter", NS)}
    level = LEVELS.get((params.get("AEMET-Meteoalerta nivel") or "").lower())
    if not level:
        return None
    area = info.find("c:area", NS)
    zone = area.find("c:geocode", NS).findtext("c:value", namespaces=NS)
    fen = info.find("c:eventCode", NS).findtext("c:value", namespaces=NS).split(";")[0]
    return {
        "zone": zone, "zone_name": _t(area, "areaDesc"), "fen": fen, "level": level,
        "param": params.get("AEMET-Meteoalerta parametro") or "",
        "description": (_t(info, "description") or "").strip(),
        "onset": datetime.fromisoformat(_t(info, "onset")),
        "expires": datetime.fromisoformat(_t(info, "expires")),
    }


def active_on(item, target_date):
    start = datetime.combine(target_date, time.min, TZ)
    end = start + timedelta(days=1)
    return item["onset"] < end and item["expires"] > start


def region(zone):
    """Provincia (o isla) de una zona de Meteoalerta: 'CCPPZZ' (+ 'C' si es costera)."""
    code = zone[2:4]
    return ISLAS.get(code) or PROVINCIAS.get(code) or "España"


def region_hashtag(name):
    return HASHTAGS.get(name) or make_hashtag(name)


def figure(fen, param, description):
    """Cifra corta del umbral: '40 mm en 12 h', 'rachas de 90 km/h', 'olas de 4 a 5 m'…"""
    parts = param.split(";")
    value = parts[2].strip() if len(parts) > 2 else ""
    if fen == "PR" and value:
        hours = "1 h" if "una hora" in parts[1] else re.sub(r".*en (\d+) horas.*", r"\1 h", parts[1])
        return f"{value} en {hours}"
    if fen == "VI" and value:
        return f"rachas de {value}"
    if fen == "CO":
        m = re.search(r"(?:olas|mar combinada)[^.]*?de (\d+(?: a \d+)?) m", description, re.I)
        if m:
            return f"olas de {m.group(1)} m"
        m = re.search(r"de (\d+ a \d+ km/h)", description)
        return f"viento de {m.group(1)}" if m else ""
    if value:
        return value
    m = re.match(r"[^.:]*:\s*([^.]+)", description)  # "Temperaturas máximas: 39 ºC."
    return m.group(1).strip() if m else ""


def group(items):
    """Agrupa por zona + fenómeno: nivel más alto y todas las cifras distintas."""
    groups = {}
    for it in items:
        name = it["zone_name"]
        if name.startswith("Costa - "):
            name = name[len("Costa - "):] + " (costa)"
        g = groups.setdefault((it["zone"], it["fen"]), {
            "zone": it["zone"], "zone_name": name,
            "fen": it["fen"], "level": 0, "figs": {}, "region": region(it["zone"]),
        })
        if it["level"] < g["level"]:
            continue  # solo se muestran las cifras del nivel más alto
        if it["level"] > g["level"]:
            g["level"], g["figs"] = it["level"], {}
        f = figure(it["fen"], it["param"], it["description"])
        if f:
            # Misma cifra en varias franjas del día: se queda la más alta ("100 mm en 12 h" y "120 mm en 12 h")
            kind = re.sub(r"\d+(?! h)", "#", f)  # conserva la franja: "en 1 h" ≠ "en 12 h"
            num = max((int(n) for n in re.findall(r"\d+", f)), default=0)
            if kind not in g["figs"] or num > g["figs"][kind][0]:
                g["figs"][kind] = (num, f)
    out = list(groups.values())
    for g in out:
        # "en 1 h" antes que "en 12 h"
        g["figures"] = [f for _, (_, f) in sorted(g.pop("figs").items(), key=lambda kv: (" 1 h" not in kv[0], kv[0]))]
        g["label"], g["icon"] = PHENOMENA.get(g["fen"], (g["fen"], "alert"))
        g["level_name"] = LEVEL_NAMES[g["level"]]
        g["hashtag"] = region_hashtag(g["region"])
        g["motivo"] = g["label"] + (": " + " · ".join(g["figures"]) if g["figures"] else "")
    fen_rank = {f: i for i, f in enumerate(PHENOMENA_ORDER)}
    out.sort(key=lambda g: (-g["level"], fen_rank.get(g["fen"], 99), g["region"], g["zone_name"]))
    return out


def avisos_de_hoy(xml_files, target_date):
    """Lista agrupada y ordenada (de más a menos grave) de los avisos vigentes hoy."""
    if not xml_files:
        raise AvisosError("El paquete de avisos de AEMET está vacío; no se publica nada")
    items = []
    for x in xml_files:
        try:
            it = parse_cap(x)
        except (ET.ParseError, AttributeError, ValueError, TypeError):
            continue
        if it and active_on(it, target_date):
            items.append(it)
    return group(items)


def counts(avisos):
    c = {3: 0, 2: 0, 1: 0}
    for a in avisos:
        c[a["level"]] += 1
    return c


# --- Texto para Instagram ------------------------------------------------------------------
EMOJI = {3: "🔴", 2: "🟠", 1: "🟡"}


def _plural(n, singular, plural):
    return f"{n} {singular if n == 1 else plural}"


def build_caption(avisos, fecha_larga):
    if not avisos:
        return "\n".join([
            f"✅ Hoy, {fecha_larga}, no hay avisos meteorológicos en España.",
            "",
            "📍 Cada mañana, el tiempo de hoy en España para tomártelo con el café. "
            f"Sigue {config.HANDLE} y no te pierdas ninguno.",
            "Fuente: AEMET",
            "",
            "#AvisosMeteorologicos #ElTiempo #AEMET",
        ])
    c = counts(avisos)
    partes = [_plural(c[3], "rojo", "rojos"), _plural(c[2], "naranja", "naranjas"), _plural(c[1], "amarillo", "amarillos")]
    partes = [p for p, n in zip(partes, (c[3], c[2], c[1])) if n]
    resumen = partes[0] if len(partes) == 1 else ", ".join(partes[:-1]) + " y " + partes[-1]
    top = avisos[0]
    if top["level"] >= 2:
        headline = f"{EMOJI[top['level']]} Aviso {top['level_name'].lower()} por {top['label'].lower()} en {top['zone_name']}"
    else:
        headline = f"⚠️ Hoy hay avisos amarillos en {len({a['region'] for a in avisos})} provincias e islas"
    lines = [headline, "", f"{_plural(len(avisos), 'aviso', 'avisos')} para hoy, {fecha_larga}: {resumen}.", ""]
    for a in avisos[:5]:
        lines.append(f"{EMOJI[a['level']]} {a['hashtag']} · {a['motivo']} ({a['zone_name']})")
    lines += [
        "",
        "➡️ Desliza para ver todos los avisos.",
        "Consulta siempre aemet.es y sigue las indicaciones de Protección Civil.",
        "",
        "📍 Cada mañana, el tiempo de hoy en España para tomártelo con el café. "
        f"Sigue {config.HANDLE} y no te pierdas ninguno.",
        "Fuente: AEMET",
        "",
        "#AvisosMeteorologicos #ElTiempo #AEMET",
    ]
    return "\n".join(lines)
