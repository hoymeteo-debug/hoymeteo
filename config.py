"""Configuración general de @hoymeteo: series, colores, textos y rutas."""
from pathlib import Path

BASE = Path(__file__).parent
FONT_DIR = BASE / "fonts"
OUTPUT_DIR = BASE / "output"
CACHE_DIR = BASE / "cache"
MUNICIPIOS_CSV = BASE / "municipios.csv"
HISTORY_DIR = BASE / "history"  # un JSON por día; se guarda en el repositorio
MIN_COVERAGE = 0.9  # si faltan más del 10 % de municipios, no se publica

# Publicación automática en Instagram cada mañana. Mientras sea False, la ejecución diaria
# solo PREPARA las publicaciones (comprueba que todo funciona) pero no publica nada.
# Se activa cuando Víctor apruebe la primera publicación real.
INSTAGRAM_AUTOPUBLISH = True  # aprobado por Víctor el 10-nov-2026

# Id de la cuenta de Instagram @hoymeteo (no es secreto). El token de inicio de sesión
# unificado no permite averiguarlo, así que se fija aquí. El secreto IG_USER_ID lo sustituye.
INSTAGRAM_USER_ID = "17841475798213052"

# TikTok: client key de la app (no es secreta; el secreto va en TIKTOK_CLIENT_SECRET).
TIKTOK_CLIENT_KEY = "sbaw6d4jvj09ewvqd5"  # Sandbox (pruebas). Cambiar por la de producción tras la aprobación
# Publicar en TikTok cada mañana. Solo tiene sentido cuando TikTok apruebe la app (auditoría);
# antes, todo lo publicado por la API sale privado.
TIKTOK_AUTOPUBLISH = False

HANDLE = "@hoymeteo"
TIMEZONE = "Europe/Madrid"
TOP_N = 30  # puestos del ranking

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def _num(v, decimals=0):
    """Formatea con coma decimal y sin ceros sobrantes."""
    if decimals == 0:
        return str(int(round(v)))
    s = f"{v:.{decimals}f}".replace(".", ",")
    return s[:-2] if s.endswith(",0") else s


def parts_temp(v):
    return _num(v) + "°", ""


def parts_rain(v):
    return _num(v, 1 if v < 10 else 0), " mm"


def parts_wind(v):
    return _num(v), " km/h"


def _contrast_detail(r, short=False):
    """'↓14° a las 7 h · ↑28° a las 14 h' (o sin horas si el día no está completo)."""
    lo, hi = _num(r["tmin"]) + "°", _num(r["tmax"]) + "°"
    if r.get("tmin_h") is None or r.get("tmax_h") is None:
        return f"↓{lo} · ↑{hi}"
    if short:
        return f"↓{lo} {r['tmin_h']} h · ↑{hi} {r['tmax_h']} h"
    return f"↓{lo} a las {r['tmin_h']} h · ↑{hi} a las {r['tmax_h']} h"


# Orden = orden de publicación: una serie por minuto, de 07:00 a 07:05 (decidido por Víctor, 10-nov-2026)
SERIES = {
    "max": {
        "label": "Máximas",
        "title": "Hoy hará más calor en",
        "icon": "thermometer_plus",
        "post_time": "07:00",
        "field": "tmax",
        "ascending": False,
        "min_items": 3,
        "parts": parts_temp,
        "headline": "🔥 Hoy hará más calor en {name}, con {value}",
        "ranking_line": "Ranking de temperaturas máximas previstas para hoy, {fecha}:",
        "hashtags": "#ElTiempo #Temperaturas #AEMET",
        "colors": {
            "bg": "#FAEEDA", "text": "#412402", "accent": "#A32D2D", "label": "#854F0B",
            "strip_from": "#791F1F", "strip_to": "#FAC775",
            "pillars": ["#A32D2D", "#D85A30", "#EF9F27"],
            "pillar_text": ["#FFFFFF", "#FFFFFF", "#412402"],
        },
    },
    "min": {
        "label": "Mínimas",
        "title": "Hoy hará más frío en",
        "icon": "thermometer_minus",
        "post_time": "07:01",
        "field": "tmin",
        "ascending": True,
        "min_items": 3,
        "parts": parts_temp,
        "headline": "❄️ Hoy hará más frío en {name}, con {value}",
        "ranking_line": "Ranking de temperaturas mínimas previstas para hoy, {fecha}:",
        "hashtags": "#ElTiempo #Frio #AEMET",
        "colors": {
            "bg": "#E6F1FB", "text": "#042C53", "accent": "#185FA5", "label": "#185FA5",
            "strip_from": "#0C447C", "strip_to": "#85B7EB",
            "pillars": ["#185FA5", "#378ADD", "#85B7EB"],
            "pillar_text": ["#FFFFFF", "#FFFFFF", "#042C53"],
        },
    },
    "rain": {
        "label": "Lluvia",
        "title": "Hoy lloverá más en",
        "icon": "drop",
        "post_time": "07:02",
        "field": "rain_mm",
        "ascending": False,
        "min_value": 0.1,   # por debajo se considera "sin lluvia"
        "min_items": 3,
        "parts": parts_rain,
        "headline": "☔ Hoy lloverá más en {name}, con {value}",
        "ranking_line": "Ranking de precipitación prevista para hoy, {fecha}:",
        "hashtags": "#ElTiempo #Lluvia #AEMET",
        "colors": {
            "bg": "#E1F5EE", "text": "#04342C", "accent": "#0F6E56", "label": "#0F6E56",
            "strip_from": "#085041", "strip_to": "#5DCAA5",
            "pillars": ["#0F6E56", "#1D9E75", "#5DCAA5"],
            "pillar_text": ["#FFFFFF", "#FFFFFF", "#04342C"],
        },
    },
    "wind": {
        "label": "Viento",
        "title": "Hoy hará más viento en",
        "icon": "wind",
        "post_time": "07:03",
        "field": "gust_kmh",
        "ascending": False,
        "min_value": 1,
        "min_items": 3,
        "parts": parts_wind,
        "headline": "💨 Hoy hará más viento en {name}, con rachas de {value}",
        "ranking_line": "Ranking de rachas máximas previstas para hoy, {fecha}:",
        "hashtags": "#ElTiempo #Viento #AEMET",
        "colors": {
            "bg": "#EEEDFE", "text": "#26215C", "accent": "#534AB7", "label": "#534AB7",
            "strip_from": "#3C3489", "strip_to": "#AFA9EC",
            "pillars": ["#534AB7", "#7F77DD", "#AFA9EC"],
            "pillar_text": ["#FFFFFF", "#FFFFFF", "#26215C"],
        },
    },
    # 07:04: contraste (la serie de nieve está descartada).
    "contrast": {
        "label": "Contraste",
        "title": "Hoy habrá más contraste en",
        "subtitle": "Diferencia entre la mínima y la máxima de hoy",
        "icon": "contrast",
        "post_time": "07:04",
        "field": "amp_c",
        "ascending": False,
        "min_items": 3,
        "parts": parts_temp,
        "detail": lambda r: _contrast_detail(r, short=False),
        "detail_short": lambda r: _contrast_detail(r, short=True),
        "headline": "🌡️ Hoy habrá más contraste en {name}: {value} de diferencia entre la mínima y la máxima",
        "ranking_line": "Diferencia entre la mínima y la máxima previstas para hoy, {fecha}:",
        "hashtags": "#ElTiempo #Temperaturas #AEMET",
        "colors": {
            # Fucsia: entre el rojo de avisos y el violeta del viento en la cuadrícula del feed
            "bg": "#F9E6F1", "text": "#45102F", "accent": "#A3306F", "label": "#94376A",
            "strip_from": "#7A1F52", "strip_to": "#E7A3C8",
            "pillars": ["#A3306F", "#C95A93", "#E7A3C8"],
            "pillar_text": ["#FFFFFF", "#FFFFFF", "#45102F"],
        },
    },
    # Serie de avisos (Meteoalerta): no es un ranking; la genera avisos.py
    "avisos": {
        "kind": "avisos",
        "label": "Avisos",
        "title": "Avisos para hoy",
        "eyebrow": "AVISOS",
        "icon": "alert",
        "post_time": "07:05",
        "colors": {
            "bg": "#FCEEEC", "text": "#4A1714", "accent": "#B3261E", "label": "#9A3B33",
        },
    },
}

# Series de ranking (todas menos los avisos)
RANKING_SERIES = [k for k, v in SERIES.items() if v.get("kind") != "avisos"]
