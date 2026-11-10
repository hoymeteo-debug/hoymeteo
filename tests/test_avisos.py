"""Serie de avisos: lectura de los CAP reales de AEMET, agrupación, textos e imágenes."""
import io
import tarfile
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

import avisos as av
import config
import render

FIX = Path(__file__).parent / "fixtures" / "avisos_muestra.tar"
DAY = date(2026, 11, 10)
TZ = ZoneInfo("Europe/Madrid")


@pytest.fixture(scope="module")
def lista():
    return av.avisos_de_hoy(av.read_tar(FIX.read_bytes()), DAY)


def test_lee_la_muestra_real(lista):
    assert lista, "la muestra tiene avisos vigentes el 10-nov"
    assert all(a["level"] in (1, 2, 3) for a in lista)


def test_orden_de_mas_a_menos_grave(lista):
    levels = [a["level"] for a in lista]
    assert levels == sorted(levels, reverse=True)


def test_un_aviso_por_zona_y_fenomeno(lista):
    keys = [(a["zone"], a["fen"]) for a in lista]
    assert len(keys) == len(set(keys))


def test_dia_sin_avisos_vigentes():
    assert av.avisos_de_hoy(av.read_tar(FIX.read_bytes()), date(2030, 1, 1)) == []


def test_paquete_vacio_no_se_toma_como_sin_avisos():
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w"):
        pass
    with pytest.raises(av.AvisosError):
        av.avisos_de_hoy(av.read_tar(buf.getvalue()), DAY)


def test_paquete_corrupto():
    with pytest.raises(av.AvisosError):
        av.read_tar(b"esto no es un tar")


def test_vigencia_respeta_hora_de_madrid():
    it = {"onset": datetime(2026, 11, 9, 18, tzinfo=TZ), "expires": datetime(2026, 11, 10, 0, 30, tzinfo=TZ)}
    assert av.active_on(it, DAY)
    it = {"onset": datetime(2026, 11, 11, 0, tzinfo=TZ), "expires": datetime(2026, 11, 11, 23, tzinfo=TZ)}
    assert not av.active_on(it, DAY)


@pytest.mark.parametrize("zona, region", [
    ("711502", "A Coruña"), ("614102", "Sevilla"), ("659303C", "La Palma"),
    ("645401C", "Mallorca"), ("659001C", "Gran Canaria"), ("785101", "Ceuta"),
])
def test_region(zona, region):
    assert av.region(zona) == region


@pytest.mark.parametrize("fen, param, desc, esperado", [
    ("PR", "P1;Precipitación acumulada en una hora;15 mm", "", "15 mm en 1 h"),
    ("PR", "P2;Precipitación acumulada en 12 horas;80 mm", "", "80 mm en 12 h"),
    ("VI", "RM;Rachas máximas;90 km/h", "", "rachas de 90 km/h"),
    ("CO", "CO;Costeros;", "Viento del sur de 50 a 61 km/h (fuerza 7) y mar combinada del suroeste de 4 a 5 m.", "olas de 4 a 5 m"),
    ("CO", "CO;Costeros;", "Viento del oeste de 50 a 61 km/h (fuerza 7).", "viento de 50 a 61 km/h"),
    ("TO", "TO;Tormentas;", "", ""),
])
def test_cifras(fen, param, desc, esperado):
    assert av.figure(fen, param, desc) == esperado


def _item(level, param, zone="701003", fen="PR"):
    return {"zone": zone, "zone_name": "Meseta cacereña", "fen": fen, "level": level, "param": param,
            "description": "", "onset": None, "expires": None}


def test_agrupa_y_muestra_solo_cifras_del_nivel_mas_alto():
    g = av.group([
        _item(1, "P1;Precipitación acumulada en una hora;15 mm"),
        _item(2, "P2;Precipitación acumulada en 12 horas;80 mm"),
        _item(2, "P2;Precipitación acumulada en 12 horas;100 mm"),
    ])
    assert len(g) == 1
    assert g[0]["level_name"] == "Naranja"
    assert g[0]["motivo"] == "Lluvias: 100 mm en 12 h"
    assert g[0]["hashtag"] == "#Caceres"


def test_texto_sin_avisos():
    t = av.build_caption([], "martes 10 de noviembre")
    assert "no hay avisos" in t and "Fuente: AEMET" in t


def test_texto_con_avisos(lista):
    t = av.build_caption(lista, "martes 10 de noviembre")
    assert lista[0]["hashtag"] in t
    assert "Protección Civil" in t and "Fuente: AEMET" in t


def test_imagenes(tmp_path, lista):
    cfg = config.SERIES["avisos"]
    n = av.counts(lista)
    slides = render.render_avisos_carousel(cfg, lista * 8, n, "MAR 10 NOV", tmp_path)
    assert 2 <= len(slides) <= 10
    assert render.render_avisos_story(cfg, lista, n, "MAR 10 NOV", tmp_path / "story.png").exists()
    vacio = render.render_avisos_carousel(cfg, [], {3: 0, 2: 0, 1: 0}, "MAR 10 NOV", tmp_path / "v")
    assert len(vacio) == 1
