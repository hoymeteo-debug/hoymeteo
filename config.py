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
INSTAGRAM_AUTOPUBLISH = False

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


# Orden = orden de publicación (07:00 a 07:15)
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
        "post_time": "07:05",
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
        "post_time": "07:10",
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
        "post_time": "07:15",
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
}
