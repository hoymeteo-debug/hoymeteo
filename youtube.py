"""Subida del Short diario a YouTube (YouTube Data API v3).

Autorización (una vez): la cuenta del canal acepta en Google y se obtiene un «refresh token»
que no caduca mientras la app de Google esté en modo Producción. Se guarda **cifrado** en
`youtube_state.enc` con una clave derivada de YT_CLIENT_SECRET (igual que TikTok).

Ojo: mientras el proyecto de Google no pase la auditoría de YouTube, todo lo que se sube por la
API queda en privado, se pida lo que se pida.
"""
import json
import time
from pathlib import Path

import requests

from tiktok import TikTokError, load_state, save_state  # mismo cifrado

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
SCOPE = "https://www.googleapis.com/auth/youtube.upload"
STATE_FILE = Path(__file__).parent / "youtube_state.enc"


class YouTubeError(Exception):
    pass


class YouTube:
    def __init__(self, client_id, client_secret, redirect_uri, session=None):
        if not client_id or not client_secret:
            raise YouTubeError("Faltan YT_CLIENT_ID / YT_CLIENT_SECRET")
        self.client_id, self.client_secret = client_id.strip(), client_secret.strip()
        self.redirect_uri = redirect_uri
        self.session = session or requests.Session()
        self.access_token = None

    def authorize_url(self):
        q = {"client_id": self.client_id, "redirect_uri": self.redirect_uri, "response_type": "code",
             "scope": SCOPE, "access_type": "offline", "prompt": "consent", "state": "hoymeteo"}
        return AUTH_URL + "?" + "&".join(f"{k}={requests.utils.quote(v, safe='')}" for k, v in q.items())

    def _token(self, **form):
        form.update(client_id=self.client_id, client_secret=self.client_secret)
        r = self.session.post(TOKEN_URL, data=form, timeout=30)
        body = r.json() if r.content else {}
        if r.status_code != 200 or "access_token" not in body:
            raise YouTubeError(f"Google rechazó la autorización: {body.get('error')} {body.get('error_description', '')}")
        self.access_token = body["access_token"]
        return body

    def exchange_code(self, code):
        body = self._token(code=code.strip(), grant_type="authorization_code", redirect_uri=self.redirect_uri)
        if "refresh_token" not in body:
            raise YouTubeError("Google no ha devuelto refresh_token: quita el acceso de la app y vuelve a autorizar")
        return {"refresh_token": body["refresh_token"], "connected_at": int(time.time())}

    def refresh(self, state):
        body = self._token(grant_type="refresh_token", refresh_token=state["refresh_token"])
        if body.get("refresh_token"):  # Google rara vez lo cambia, pero si lo hace se guarda
            state = {**state, "refresh_token": body["refresh_token"]}
        return state

    def channel(self):
        r = self.session.get("https://www.googleapis.com/youtube/v3/channels",
                             params={"part": "snippet", "mine": "true"},
                             headers={"Authorization": f"Bearer {self.access_token}"}, timeout=30)
        items = (r.json() or {}).get("items") or []
        return items[0]["snippet"] if items else {}

    def upload(self, video_path, title, description, tags=None, privacy="public"):
        """Subida reanudable. Devuelve el id del vídeo."""
        meta = {
            "snippet": {"title": title[:100], "description": description[:5000],
                        "tags": tags or [], "categoryId": "22", "defaultLanguage": "es",
                        "defaultAudioLanguage": "es"},
            "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
        }
        size = Path(video_path).stat().st_size
        r = self.session.post(UPLOAD_URL, params={"uploadType": "resumable", "part": "snippet,status"},
                              headers={"Authorization": f"Bearer {self.access_token}",
                                       "Content-Type": "application/json; charset=UTF-8",
                                       "X-Upload-Content-Type": "video/mp4",
                                       "X-Upload-Content-Length": str(size)},
                              data=json.dumps(meta), timeout=60)
        if r.status_code != 200 or "Location" not in r.headers:
            raise YouTubeError(f"No se pudo iniciar la subida: HTTP {r.status_code} {r.text[:300]}")
        with open(video_path, "rb") as f:
            up = self.session.put(r.headers["Location"], data=f,
                                  headers={"Authorization": f"Bearer {self.access_token}",
                                           "Content-Type": "video/mp4"}, timeout=600)
        if up.status_code not in (200, 201):
            raise YouTubeError(f"La subida falló: HTTP {up.status_code} {up.text[:300]}")
        return up.json()["id"]


def load(client_secret):
    try:
        return load_state(client_secret, STATE_FILE)
    except TikTokError as exc:
        raise YouTubeError(str(exc).replace("TikTok", "YouTube").replace("tiktok_state", "youtube_state")
                           .replace("«TikTok: conectar»", "«YouTube: conectar»")) from None


def save(state, client_secret):
    save_state(state, client_secret, STATE_FILE)
