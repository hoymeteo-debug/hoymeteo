"""Publicación en TikTok (Content Posting API, publicación directa de fotos).

Autorización:
- La app se identifica con TIKTOK_CLIENT_KEY y TIKTOK_CLIENT_SECRET (secretos del repositorio).
- La cuenta @hoymeteo autoriza una vez; TikTok devuelve un token de acceso (24 h) y uno de
  renovación (~1 año) que **cambia** en cada renovación y hay que guardar el último.
- Para no depender de nadie, ese estado se guarda **cifrado** en `tiktok_state.enc` (en el
  repositorio) con una clave derivada de TIKTOK_CLIENT_SECRET. Sin el secreto no se puede leer.

Las fotos se publican con PULL_FROM_URL: TikTok las descarga de una URL de un dominio verificado
en el portal de desarrolladores (nuestra web de GitHub Pages).
"""
import base64
import hashlib
import json
import time
from pathlib import Path

import requests
from cryptography.fernet import Fernet, InvalidToken

API = "https://open.tiktokapis.com/v2"
AUTHORIZE_URL = "https://www.tiktok.com/v2/auth/authorize/"
SCOPES = "user.info.basic,video.publish"
STATE_FILE = Path(__file__).parent / "tiktok_state.enc"


class TikTokError(Exception):
    pass


# --- Estado cifrado ---------------------------------------------------------------
def _fernet(client_secret: str) -> Fernet:
    key = hashlib.sha256(("hoymeteo-tiktok:" + client_secret).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def save_state(state: dict, client_secret: str, path: Path = STATE_FILE):
    path.write_bytes(_fernet(client_secret).encrypt(json.dumps(state).encode()))


def load_state(client_secret: str, path: Path = STATE_FILE) -> dict:
    if not path.exists():
        raise TikTokError("TikTok no está conectado todavía (falta tiktok_state.enc). "
                          "Ejecuta el workflow «TikTok: conectar».")
    try:
        return json.loads(_fernet(client_secret).decrypt(path.read_bytes()))
    except InvalidToken:
        raise TikTokError("No se puede descifrar tiktok_state.enc: ¿ha cambiado TIKTOK_CLIENT_SECRET?") from None


# --- Cliente ------------------------------------------------------------------------
class TikTok:
    def __init__(self, client_key: str, client_secret: str, redirect_uri: str, session=None, poll_seconds=5.0):
        if not client_key or not client_secret:
            raise TikTokError("Faltan TIKTOK_CLIENT_KEY / TIKTOK_CLIENT_SECRET")
        # Al pegar claves es fácil arrastrar espacios o saltos de línea
        self.client_key, self.client_secret = client_key.strip(), client_secret.strip()
        self.redirect_uri = redirect_uri
        self.session = session or requests.Session()
        self.poll_seconds = poll_seconds
        self.access_token = None

    def authorize_url(self, state="hoymeteo"):
        q = {"client_key": self.client_key, "scope": SCOPES, "response_type": "code",
             "redirect_uri": self.redirect_uri, "state": state}
        return AUTHORIZE_URL + "?" + "&".join(f"{k}={requests.utils.quote(v, safe='')}" for k, v in q.items())

    def _token(self, **form):
        form.update(client_key=self.client_key, client_secret=self.client_secret)
        r = self.session.post(f"{API}/oauth/token/", data=form, timeout=30,
                              headers={"Content-Type": "application/x-www-form-urlencoded"})
        body = r.json() if r.content else {}
        if r.status_code != 200 or "access_token" not in body:
            raise TikTokError(f"TikTok rechazó la autorización: {body.get('error')} {body.get('error_description', '')}")
        self.access_token = body["access_token"]
        return {"refresh_token": body["refresh_token"], "open_id": body.get("open_id"),
                "scope": body.get("scope"), "refreshed_at": int(time.time())}

    def check_credentials(self):
        """Comprueba que client key y secret casan (token de app, sin usuario)."""
        r = self.session.post(f"{API}/oauth/token/", timeout=30,
                              data={"client_key": self.client_key, "client_secret": self.client_secret,
                                    "grant_type": "client_credentials"},
                              headers={"Content-Type": "application/x-www-form-urlencoded"})
        body = r.json() if r.content else {}
        if "access_token" not in body:
            raise TikTokError(f"Las claves no casan: {body.get('error')} {body.get('error_description', '')}")
        return True

    def exchange_code(self, code: str):
        """Primera conexión: cambia el código de autorización por los tokens."""
        return self._token(code=code.strip(), grant_type="authorization_code", redirect_uri=self.redirect_uri)

    def refresh(self, state: dict):
        """Renueva el acceso. Devuelve el estado nuevo (con el token de renovación nuevo)."""
        return self._token(grant_type="refresh_token", refresh_token=state["refresh_token"])

    def _api(self, path, payload=None):
        if not self.access_token:
            raise TikTokError("Sin token de acceso: llama antes a refresh()")
        r = self.session.post(f"{API}/{path}", json=payload or {}, timeout=60,
                              headers={"Authorization": f"Bearer {self.access_token}",
                                       "Content-Type": "application/json; charset=UTF-8"})
        body = r.json() if r.content else {}
        err = body.get("error", {})
        if r.status_code != 200 or err.get("code") not in (None, "ok"):
            raise TikTokError(f"{path}: HTTP {r.status_code} {err.get('code')} {err.get('message', '')}")
        return body.get("data", {})

    def creator_info(self):
        return self._api("post/publish/creator_info/query/")

    def post_photos(self, image_urls, title, description, privacy_level):
        """Publica un carrusel de fotos. Devuelve el publish_id."""
        if not 1 <= len(image_urls) <= 35:
            raise TikTokError(f"TikTok admite de 1 a 35 fotos (hay {len(image_urls)})")
        payload = {
            "post_info": {"title": title[:90], "description": description[:4000],
                          "privacy_level": privacy_level, "disable_comment": False, "auto_add_music": True},
            "source_info": {"source": "PULL_FROM_URL", "photo_cover_index": 0, "photo_images": list(image_urls)},
            "post_mode": "DIRECT_POST",
            "media_type": "PHOTO",
        }
        return self._api("post/publish/content/init/", payload)["publish_id"]

    def post_video(self, video_url, caption, privacy_level, cover_ms=4500):
        """Publica un vídeo (la story animada con nuestra música lo-fi). Devuelve el publish_id."""
        payload = {
            "post_info": {"title": caption[:2200], "privacy_level": privacy_level,
                          "disable_duet": False, "disable_comment": False, "disable_stitch": False,
                          "video_cover_timestamp_ms": cover_ms},
            "source_info": {"source": "PULL_FROM_URL", "video_url": video_url},
        }
        return self._api("post/publish/video/init/", payload)["publish_id"]

    def wait_published(self, publish_id, timeout=300):
        deadline = time.time() + timeout
        while True:
            data = self._api("post/publish/status/fetch/", {"publish_id": publish_id})
            status = data.get("status")
            if status == "PUBLISH_COMPLETE":
                return data
            if status == "FAILED":
                raise TikTokError(f"TikTok no pudo publicar: {data.get('fail_reason')}")
            if time.time() > deadline:
                raise TikTokError(f"La publicación {publish_id} sigue en estado {status} tras {timeout} s")
            time.sleep(self.poll_seconds)
