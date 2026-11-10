"""TikTok con una API simulada (no se conecta a TikTok)."""
import pytest

from tiktok import TikTok, TikTokError, load_state, save_state


class Resp:
    def __init__(self, body, status=200):
        self.status_code, self._body, self.content = status, body, b"x"

    def json(self):
        return self._body


class FakeSession:
    def __init__(self):
        self.calls = []
        self.n = 0

    def post(self, url, data=None, json=None, headers=None, timeout=None):
        self.calls.append((url.split("/v2/")[1], data or json))
        if url.endswith("oauth/token/"):
            self.n += 1
            if data.get("grant_type") == "refresh_token" and data["refresh_token"] == "caducado":
                return Resp({"error": "invalid_grant", "error_description": "caducado"}, 400)
            return Resp({"access_token": "act", "refresh_token": f"rft{self.n}", "open_id": "o1", "scope": "video.publish"})
        assert headers["Authorization"] == "Bearer act"
        if url.endswith("content/init/") or url.endswith("video/init/"):
            return Resp({"data": {"publish_id": "p1"}, "error": {"code": "ok"}})
        if url.endswith("status/fetch/"):
            return Resp({"data": {"status": "PUBLISH_COMPLETE"}, "error": {"code": "ok"}})
        return Resp({"error": {"code": "invalid_params", "message": "x"}}, 400)


def tk(s=None):
    return TikTok("ck", "secreto", "https://x/tiktok/", session=s or FakeSession(), poll_seconds=0)


def test_estado_cifrado_y_legible_solo_con_el_secreto(tmp_path):
    f = tmp_path / "s.enc"
    save_state({"refresh_token": "abc"}, "secreto", f)
    assert b"abc" not in f.read_bytes()
    assert load_state("secreto", f)["refresh_token"] == "abc"
    with pytest.raises(TikTokError):
        load_state("otro", f)


def test_sin_estado_avisa(tmp_path):
    with pytest.raises(TikTokError, match="conectar"):
        load_state("secreto", tmp_path / "no.enc")


def test_renovacion_devuelve_token_nuevo():
    client = tk()
    first = client.exchange_code("CODE")
    second = client.refresh(first)
    assert first["refresh_token"] != second["refresh_token"]


def test_renovacion_rechazada():
    with pytest.raises(TikTokError, match="invalid_grant"):
        tk().refresh({"refresh_token": "caducado"})


def test_publicar_fotos():
    s = FakeSession()
    client = tk(s)
    client.exchange_code("CODE")
    pid = client.post_photos(["https://x/1.jpg", "https://x/2.jpg"], "T" * 200, "texto", "SELF_ONLY")
    assert pid == "p1"
    payload = s.calls[-1][1]
    assert payload["media_type"] == "PHOTO" and payload["post_mode"] == "DIRECT_POST"
    assert payload["source_info"]["photo_images"] == ["https://x/1.jpg", "https://x/2.jpg"]
    assert len(payload["post_info"]["title"]) == 90
    assert client.wait_published(pid)["status"] == "PUBLISH_COMPLETE"


def test_enlace_de_autorizacion():
    url = tk().authorize_url()
    assert "client_key=ck" in url and "video.publish" in url.replace("%2C", ",")
    assert "redirect_uri=https%3A%2F%2Fx%2Ftiktok%2F" in url


def test_publicar_video():
    s = FakeSession()
    client = tk(s)
    client.exchange_code("CODE")
    assert client.post_video("https://x/story.mp4", "texto", "SELF_ONLY") == "p1"
    payload = s.calls[-1][1]
    assert payload["source_info"] == {"source": "PULL_FROM_URL", "video_url": "https://x/story.mp4"}
    assert payload["post_info"]["privacy_level"] == "SELF_ONLY"
