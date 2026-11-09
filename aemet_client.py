"""Cliente mínimo de AEMET OpenData.

AEMET responde en dos pasos: la primera llamada devuelve una URL ("datos") y la
segunda descarga el contenido real. La clave se envía en la cabecera api_key.
"""
import difflib
import json
import re
import time
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

import requests

BASE_URL = "https://opendata.aemet.es/opendata/api"


class AemetError(Exception):
    pass


def _decode(content: bytes) -> str:
    """AEMET a veces responde en ISO-8859-15 aunque anuncie UTF-8."""
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return content.decode("latin-1")


class AemetClient:
    def __init__(self, api_key: str, min_interval: float = 1.5, max_retries: int = 6):
        if not api_key:
            raise AemetError("Falta AEMET_API_KEY (ponla en el archivo .env)")
        self.min_interval = min_interval
        self.max_retries = max_retries
        self._last = 0.0
        self.session = requests.Session()
        self.session.headers.update({"api_key": api_key, "Accept": "application/json"})

    def _get(self, url: str) -> bytes:
        for attempt in range(1, self.max_retries + 1):
            wait = self.min_interval - (time.time() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.time()
            try:
                r = self.session.get(url, timeout=30)
            except requests.RequestException as exc:
                if attempt == self.max_retries:
                    raise AemetError(f"Error de red: {exc}") from exc
                time.sleep(2 * attempt)
                continue
            if r.status_code == 429 or r.status_code >= 500:
                retry_after = r.headers.get("Retry-After")
                time.sleep(float(retry_after) if retry_after and retry_after.isdigit() else 5 * attempt)
                continue
            if r.status_code in (401, 403):
                raise AemetError(f"Clave rechazada por AEMET (HTTP {r.status_code}). Revisa AEMET_API_KEY")
            if r.status_code != 200:
                raise AemetError(f"HTTP {r.status_code} en {url}")
            return r.content
        raise AemetError(f"Demasiados reintentos en {url}")

    def get_json(self, endpoint: str):
        meta = json.loads(_decode(self._get(BASE_URL + endpoint)))
        if meta.get("estado") != 200 or "datos" not in meta:
            raise AemetError(f"{endpoint}: {meta.get('estado')} {meta.get('descripcion')}")
        return json.loads(_decode(self._get(meta["datos"])))

    # --- Endpoints concretos -------------------------------------------------
    def maestro_municipios(self, cache_dir: Path, max_age_days: int = 30):
        cache = cache_dir / "maestro_municipios.json"
        if cache.exists() and datetime.now() - datetime.fromtimestamp(cache.stat().st_mtime) < timedelta(days=max_age_days):
            return json.loads(cache.read_text(encoding="utf-8"))
        data = self.get_json("/maestro/municipios")
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data

    def prediccion_horaria(self, ine: str):
        return self.get_json(f"/prediccion/especifica/municipio/horaria/{ine}")

    def prediccion_diaria(self, ine: str):
        return self.get_json(f"/prediccion/especifica/municipio/diaria/{ine}")


# --- Resolución de nombres a códigos INE --------------------------------------
_ARTICLES = r"(el|la|los|las|l'|a|o|as|os|els|les)"


def normalize(name: str) -> str:
    s = unicodedata.normalize("NFD", name.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.replace("'", "' ")
    m = re.match(rf"^(.+),\s*{_ARTICLES}$", s.strip())
    if m:  # "Coruña, A" -> "a coruña"
        s = f"{m.group(2)} {m.group(1)}"
    return re.sub(r"[^a-z0-9 ]+", " ", s).strip()


def _variants(name: str):
    raw = [name] + re.split(r"[/\-]", name)
    return {normalize(v) for v in raw if v.strip()}


def resolve_municipios(rows, maestro):
    """Devuelve (resueltos, no_resueltos). Cada fila: provincia, nombre, nombre_aemet."""
    by_prov = {}
    for m in maestro:
        ine = m["id"].replace("id", "")
        by_prov.setdefault(ine[:2], []).append((ine, m["nombre"]))

    resolved, unresolved = [], []
    for row in rows:
        candidates = by_prov.get(row["provincia"], [])
        wanted = _variants(row["nombre"]) | _variants(row.get("nombre_aemet") or "")
        wanted.discard("")
        hit = None
        for ine, nombre in candidates:
            if _variants(nombre) & wanted:
                hit = ine
                break
        if hit is None:  # parecido razonable dentro de la provincia
            names = {normalize(n): ine for ine, n in candidates}
            for w in wanted:
                close = difflib.get_close_matches(w, list(names), n=1, cutoff=0.88)
                if close:
                    hit = names[close[0]]
                    break
        if hit:
            resolved.append({**row, "ine": hit})
        else:
            sugg = difflib.get_close_matches(normalize(row["nombre"]), [normalize(n) for _, n in candidates], n=3, cutoff=0.5)
            unresolved.append((row, sugg))
    return resolved, unresolved


# --- Interpretación de la predicción horaria ----------------------------------
def _to_float(v):
    if v is None:
        return None
    v = str(v).strip()
    if v == "":
        return None
    if v.lower() == "ip":  # precipitación inapreciable (<0,1 mm)
        return 0.0
    try:
        return float(v.replace(",", "."))
    except ValueError:
        return None


def _find_day(payload, target_date):
    base = payload[0]
    dia = next((d for d in base["prediccion"]["dia"] if str(d.get("fecha", ""))[:10] == target_date.isoformat()), None)
    return dia, base.get("elaborado")


def parse_diaria(payload, target_date):
    """Máxima y mínima oficiales del día (las que publica aemet.es).

    Se usan para las series de temperatura porque cubren el día completo; la
    horaria solo empieza en la hora en que se elabora y pierde la madrugada.
    Devuelve (valores, elaborado) o (None, elaborado) si no hay datos de ese día.
    """
    dia, elaborado = _find_day(payload, target_date)
    if dia is None:
        return None, elaborado
    temp = dia.get("temperatura") or {}
    return {"tmax": _to_float(temp.get("maxima")), "tmin": _to_float(temp.get("minima"))}, elaborado


def parse_horaria(payload, target_date):
    """Extrae tmax, tmin, lluvia total (mm) y racha máxima (km/h) de un día.

    Ojo: el primer día solo cubre desde la hora de elaboración ("horas" indica
    cuántas horas trae). Devuelve (valores, elaborado) o (None, elaborado).
    """
    dia, elaborado = _find_day(payload, target_date)
    if dia is None:
        return None, elaborado

    temps = [t for t in (_to_float(x.get("value")) for x in dia.get("temperatura", [])) if t is not None]
    rains = [r for r in (_to_float(x.get("value")) for x in dia.get("precipitacion", [])) if r is not None]
    gusts = []
    for x in dia.get("vientoAndRachaMax", []):
        if "value" in x:  # las entradas con "value" son las rachas
            g = _to_float(x.get("value"))
            if g is not None:
                gusts.append(g)

    return {
        "tmax": max(temps) if temps else None,
        "tmin": min(temps) if temps else None,
        "rain_mm": round(sum(rains), 1) if rains else None,
        "gust_kmh": max(gusts) if gusts else None,
        "horas": len(dia.get("temperatura", [])),
    }, elaborado
