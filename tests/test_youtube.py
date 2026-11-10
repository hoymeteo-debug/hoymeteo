"""YouTube con una API simulada (no se conecta a Google)."""
from datetime import date

import pytest

import youtube as yt
import youtube_cli


class Resp:
    def __init__(self, body=None, status=200, headers=None):
        self.status_code, self._body, self.headers = status, body or {}, headers or {}
        self.content, self.text = b"x", str(body)

    def json(self):
        return self._body


class FakeSession:
    def __init__(self):
        self.calls = []

    def post(self, url, params=None, data=None, headers=None, timeout=None):
        self.calls.append(("POST", url, params, data))
        if "oauth2" in url:
            return Resp({"access_token": "at", "refresh_token": "rt"})
        return Resp({}, 200, {"Location": "https://upload/session1"})

    def put(self, url, data=None, headers=None, timeout=None):
        self.calls.append(("PUT", url))
        return Resp({"id": "VID123"})


def test_autorizacion_pide_acceso_offline():
    url = yt.YouTube("cid", "sec", "https://x/youtube/").authorize_url()
    assert "access_type=offline" in url and "prompt=consent" in url and "youtube.upload" in url


def test_subida_reanudable(tmp_path):
    f = tmp_path / "s.mp4"
    f.write_bytes(b"0" * 100)
    s = FakeSession()
    c = yt.YouTube("cid", "sec", "https://x/", session=s)
    c.exchange_code("code")
    assert c.upload(f, "T" * 150, "desc", privacy="private") == "VID123"
    meta = [x for x in s.calls if x[0] == "POST" and "upload" in x[1]][0][3]
    assert '"privacyStatus": "private"' in meta and '"selfDeclaredMadeForKids": false' in meta
    assert len(__import__("json").loads(meta)["snippet"]["title"]) == 100


def test_sin_credenciales():
    with pytest.raises(yt.YouTubeError):
        yt.YouTube("", "", "https://x/")


def test_textos_del_short(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "BASE", tmp_path)
    d = date(2026, 11, 10)
    (tmp_path / "media" / d.isoformat() / "max").mkdir(parents=True)
    (tmp_path / "media" / d.isoformat() / "max" / "caption.txt").write_text("🔥 Hoy hará más calor en Murcia, con 28°\n\n…", encoding="utf-8")
    title, desc = youtube_cli.short_texts(d)
    assert title.endswith("#Shorts") and "martes 10 de noviembre" in title and len(title) <= 100
    assert "🔥 Hoy hará más calor en Murcia, con 28°" in desc and "Fuente: AEMET" in desc
