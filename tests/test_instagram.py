"""Publicación en Instagram con una API simulada (no se conecta a Meta)."""
import pytest

from instagram import Instagram, InstagramError


class FakeResponse:
    def __init__(self, body, status=200):
        self.status_code, self._body, self.text = status, body, str(body)

    def json(self):
        return self._body


class FakeSession:
    """Simula la Graph API: crea contenedores, informa de su estado y publica."""

    def __init__(self, fail_status=None):
        self.calls, self.n, self.fail_status = [], 0, fail_status

    def request(self, method, url, params=None, data=None, timeout=None):
        args = params or data
        assert args["access_token"] == "EAAtoken"
        path = url.split("/v23.0/")[1]
        self.calls.append((method, path, {k: v for k, v in args.items() if k != "access_token"}))
        if path.endswith("/media"):
            self.n += 1
            return FakeResponse({"id": f"c{self.n}"})
        if path.endswith("/media_publish"):
            return FakeResponse({"id": "post1"})
        if method == "GET" and path.startswith("c"):
            return FakeResponse({"status_code": self.fail_status or "FINISHED"})
        return FakeResponse({"error": {"message": "desconocido", "code": 100}}, 400)


def ig(session):
    return Instagram("EAAtoken", "1789", session=session, poll_seconds=0, rate_wait=0)


def test_host_segun_token():
    assert "graph.facebook.com" in Instagram("EAAx", "1").base
    assert "graph.instagram.com" in Instagram("IGAAx", "1").base


def test_carrusel_y_publicacion():
    s = FakeSession()
    client = ig(s)
    parent = client.prepare_carousel(["https://x/1.jpg", "https://x/2.jpg"], "texto")
    assert parent == "c3"
    posts = [c for c in s.calls if c[0] == "POST"]
    assert posts[0][2] == {"image_url": "https://x/1.jpg", "is_carousel_item": "true"}
    assert posts[2][2] == {"media_type": "CAROUSEL", "children": "c1,c2", "caption": "texto"}
    # el carrusel se crea sin consultar antes cada imagen
    assert not [c for c in s.calls if c[0] == "GET" and c[1] in ("c1", "c2")]
    assert client.publish(parent) == "post1"


def test_story():
    s = FakeSession()
    assert ig(s).prepare_story("https://x/story.jpg") == "c1"
    assert s.calls[0][2] == {"image_url": "https://x/story.jpg", "media_type": "STORIES"}


def test_contenedor_con_error():
    with pytest.raises(InstagramError, match="ERROR"):
        ig(FakeSession(fail_status="ERROR")).prepare_story("https://x/s.jpg")


def test_carrusel_necesita_dos_imagenes():
    with pytest.raises(InstagramError):
        ig(FakeSession()).prepare_carousel(["https://x/1.jpg"], "t")


def test_error_de_api_no_muestra_el_token():
    with pytest.raises(InstagramError) as exc:
        ig(FakeSession())._call("GET", "otra/cosa")
    assert "EAAtoken" not in str(exc.value)


class LimitedSession(FakeSession):
    """Devuelve «Application request limit reached» las dos primeras veces que se publica."""

    def __init__(self):
        super().__init__()
        self.limited = 2

    def request(self, method, url, params=None, data=None, timeout=None):
        if url.endswith("/media_publish") and self.limited:
            self.limited -= 1
            return FakeResponse({"error": {"message": "Application request limit reached", "code": 4}}, 403)
        return super().request(method, url, params, data, timeout)


def test_reintenta_si_se_agota_el_cupo():
    client = ig(LimitedSession())
    assert client.publish("c9") == "post1"
    assert client.calls == 3
