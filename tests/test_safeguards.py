"""Salvaguardas: no publicar con datos incompletos o repetidos."""
import json
from datetime import date

import pytest

import config
import run

MUNIS = [{"nombre": f"M{i}"} for i in range(10)]
RECS = [{"name": f"M{i}", "tmax": 20.0 + i, "tmin": 5.0, "rain_mm": 0.0, "gust_kmh": 30.0} for i in range(10)]
DAY = date(2026, 11, 10)


@pytest.fixture(autouse=True)
def tmp_history(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "HISTORY_DIR", tmp_path)
    return tmp_path


def test_guarda_historico(tmp_history):
    run.check_and_save(RECS, MUNIS, DAY)
    saved = json.loads((tmp_history / "2026-11-10.json").read_text(encoding="utf-8"))
    assert saved["M3"]["tmax"] == 23.0


def test_faltan_municipios():
    with pytest.raises(run.SuspiciousData) as exc:
        run.check_and_save(RECS[:5], MUNIS, DAY)
    assert exc.value.code.startswith("ERROR")


def test_identico_a_ayer():
    run.check_and_save(RECS, MUNIS, date(2026, 11, 9))
    with pytest.raises(run.SuspiciousData):
        run.check_and_save(RECS, MUNIS, DAY)


def test_distinto_de_ayer_pasa():
    run.check_and_save(RECS, MUNIS, date(2026, 11, 9))
    changed = [{**r, "tmax": r["tmax"] + 1} for r in RECS]
    run.check_and_save(changed, MUNIS, DAY)
