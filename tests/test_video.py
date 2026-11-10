"""Stories en vídeo: orden de la animación y vídeo válido."""
import json
import subprocess
from datetime import date

import config
import render
import video
import data_sources as ds


def test_curva_suave():
    assert video.ease_out(0) == 0 and video.ease_out(1) == 1
    assert video.ease_out(0.5) > 0.5  # desacelera: avanza rápido al principio
    assert video.ease_out(-1) == 0 and video.ease_out(2) == 1


def test_orden_de_entrada():
    els = [{"kind": "row", "order": 5, "box": [0, 0, 1, 1]}, {"kind": "rise", "order": 3, "box": [0, 0, 1, 1]},
           {"kind": "header", "order": 0, "box": [0, 0, 1, 1]}, {"kind": "rise", "order": 1, "box": [0, 0, 1, 1]},
           {"kind": "row", "order": 4, "box": [0, 0, 1, 1]}, {"kind": "footer", "order": 0, "box": [0, 0, 1, 1]}]
    start = {(e["kind"], e["order"]): s for e, s, _ in video.schedule(els)}
    assert start[("header", 0)] < start[("rise", 1)] < start[("rise", 3)]   # el 1.º puesto entra el último del podio
    assert start[("rise", 3)] < start[("row", 4)] < start[("row", 5)] < start[("footer", 0)]


def test_pista_distinta_por_serie():
    d = date(2026, 11, 10)
    assert video.pick_track(d, "max") != video.pick_track(d, "min")


def test_video_de_story(tmp_path):
    recs = ds.demo_records(ds.load_municipios(), date(2026, 11, 10))
    cfg = config.SERIES["max"]
    png = render.render_story(cfg, ds.build_ranking(recs, cfg), "MAR 10 NOV", tmp_path / "story.png")
    layout = json.loads((tmp_path / "story.json").read_text())
    assert any(e["kind"] == "rise" for e in layout["elements"])
    out = video.render_story_video(png, tmp_path / "story.mp4", video.pick_track(date(2026, 11, 10), "max"), duration=2)
    probe = subprocess.run([video.ffmpeg_exe(), "-i", str(out)], capture_output=True, text=True).stderr
    assert "h264" in probe and "aac" in probe and "1080x1920" in probe


def test_short_diario(tmp_path):
    recs = ds.demo_records(ds.load_municipios(), date(2026, 11, 10))
    pngs = []
    for k in ("max", "min"):
        cfg = config.SERIES[k]
        pngs.append(render.render_story(cfg, ds.build_ranking(recs, cfg), "MAR 10 NOV", tmp_path / k / "story.png"))
    out = video.render_daily_short(pngs, tmp_path / "short.mp4", "Martes 10 de noviembre",
                                   video.pick_track(date(2026, 11, 10), "max", long=True))
    probe = subprocess.run([video.ffmpeg_exe(), "-i", str(out)], capture_output=True, text=True).stderr
    assert "1080x1920" in probe and "aac" in probe
    assert video.pick_track(date(2026, 11, 10), "max", long=True).name.startswith("lofi_largo_")
    assert not video.pick_track(date(2026, 11, 10), "max").name.startswith("lofi_largo_")
