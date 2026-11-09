"""Pruebas del parser, la resolución de nombres, los rankings y los textos.

Las fixtures son respuestas reales de AEMET (Madrid, elaborada el 2026-11-09)
y el catálogo real de municipios. No contienen claves.
"""
import json
from datetime import date
from pathlib import Path

import pytest

import captions
import config
import data_sources as ds
from aemet_client import normalize, parse_diaria, parse_horaria, resolve_municipios

FIX = Path(__file__).parent / "fixtures"
DAY = date(2026, 11, 10)


def load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


# --- Parser horario ------------------------------------------------------------
def test_horaria_dia_completo():
    values, elaborado = parse_horaria(load("horaria_28079.json"), DAY)
    assert elaborado == "2026-11-09T20:59:08"
    assert values == {"tmax": 16.0, "tmin": 13.0, "rain_mm": 10.2, "gust_kmh": 38.0, "horas": 24}


def test_horaria_primer_dia_parcial():
    # El día de elaboración solo trae las horas restantes (20-23 h)
    values, _ = parse_horaria(load("horaria_28079.json"), date(2026, 11, 9))
    assert values["horas"] == 4
    assert values["gust_kmh"] == 26.0


def test_horaria_rachas_ignoran_entradas_de_viento_medio():
    # Las entradas con "velocidad" (viento medio) no deben contar como racha
    payload = load("horaria_28079.json")
    dia = payload[0]["prediccion"]["dia"][1]
    dia["vientoAndRachaMax"] = [
        {"direccion": ["S"], "velocidad": ["90"], "periodo": "00"},
        {"value": "20", "periodo": "00"},
    ]
    values, _ = parse_horaria(payload, DAY)
    assert values["gust_kmh"] == 20.0


def test_horaria_ip_cuenta_como_cero():
    payload = load("horaria_28079.json")
    dia = payload[0]["prediccion"]["dia"][1]
    dia["precipitacion"] = [{"value": "Ip", "periodo": "00"}, {"value": "1.5", "periodo": "01"}]
    values, _ = parse_horaria(payload, DAY)
    assert values["rain_mm"] == 1.5


def test_horaria_dia_inexistente():
    values, _ = parse_horaria(load("horaria_28079.json"), date(2026, 12, 25))
    assert values is None


# --- Parser diario ---------------------------------------------------------------
def test_diaria_maxima_minima_oficiales():
    values, _ = parse_diaria(load("diaria_28079.json"), DAY)
    # La oficial (18°) supera a la mayor temperatura horaria (16°)
    assert values == {"tmax": 18.0, "tmin": 13.0}


def test_diaria_dia_inexistente():
    values, _ = parse_diaria(load("diaria_28079.json"), date(2026, 12, 25))
    assert values is None


# --- Resolución de nombres ---------------------------------------------------------
def test_normalize_articulo_pospuesto():
    assert normalize("Coruña, A") == "a coruna"
    assert normalize("Palmas de Gran Canaria, Las") == "las palmas de gran canaria"


def test_todos_los_municipios_del_csv_se_resuelven():
    resolved, unresolved = resolve_municipios(ds.load_municipios(), load("maestro_municipios.json"))
    assert unresolved == []
    ines = [r["ine"] for r in resolved]
    assert len(ines) == len(set(ines)), "dos filas apuntan al mismo municipio"


@pytest.mark.parametrize("nombre, ine", [
    ("Madrid", "28079"), ("A Coruña", "15030"), ("San Sebastián", "20069"),
    ("Palma", "07040"), ("La Laguna", "38023"), ("Las Palmas", "35016"),
])
def test_resolucion_casos_dificiles(nombre, ine):
    rows = [r for r in ds.load_municipios() if r["nombre"] == nombre]
    resolved, _ = resolve_municipios(rows, load("maestro_municipios.json"))
    assert resolved[0]["ine"] == ine


# --- Rankings ----------------------------------------------------------------------
RECORDS = [
    {"name": "Bilbao", "hashtag": "#Bilbao", "tmax": 15.0, "tmin": 9.0, "rain_mm": 12.0, "gust_kmh": 60.0},
    {"name": "Almería", "hashtag": "#Almeria", "tmax": 22.0, "tmin": 14.0, "rain_mm": 0.0, "gust_kmh": 30.0},
    {"name": "Ávila", "hashtag": "#Avila", "tmax": 10.0, "tmin": -2.0, "rain_mm": 0.05, "gust_kmh": None},
    {"name": "Cádiz", "hashtag": "#Cadiz", "tmax": 22.0, "tmin": 15.0, "rain_mm": 1.0, "gust_kmh": 45.0},
]


def test_ranking_maximas_con_empate_por_nombre():
    ranking = ds.build_ranking(RECORDS, config.SERIES["max"])
    assert [r["name"] for r in ranking] == ["Almería", "Cádiz", "Bilbao", "Ávila"]


def test_ranking_minimas_ascendente():
    ranking = ds.build_ranking(RECORDS, config.SERIES["min"])
    assert ranking[0]["name"] == "Ávila"


def test_ranking_lluvia_descarta_sin_lluvia():
    ranking = ds.build_ranking(RECORDS, config.SERIES["rain"])
    assert [r["name"] for r in ranking] == ["Bilbao", "Cádiz"]


def test_ranking_ignora_valores_nulos():
    ranking = ds.build_ranking(RECORDS, config.SERIES["wind"])
    assert "Ávila" not in [r["name"] for r in ranking]


def test_ranking_limite_top_n():
    many = [{"name": f"M{i:03d}", "hashtag": "#M", "tmax": float(i)} for i in range(50)]
    assert len(ds.build_ranking(many, config.SERIES["max"])) == config.TOP_N


# --- Hashtags y textos -------------------------------------------------------------
@pytest.mark.parametrize("nombre, hashtag", [
    ("Málaga", "#Malaga"), ("Santiago de Compostela", "#SantiagoDeCompostela"), ("A Coruña", "#ACoruna"),
])
def test_make_hashtag(nombre, hashtag):
    assert ds.make_hashtag(nombre) == hashtag


def test_caption_estructura():
    ranking = ds.build_ranking(RECORDS, config.SERIES["max"])
    text = captions.build_caption(config.SERIES["max"], ranking, DAY)
    assert text.startswith("🔥 Hoy hará más calor en Almería, con 22°")
    assert "#Almeria 22°" in text
    assert "Fuente: AEMET" in text
    assert "Sigue @hoymeteo" in text
