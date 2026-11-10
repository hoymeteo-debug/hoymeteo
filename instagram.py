"""Publicación en Instagram (Graph API) para @hoymeteo.

Funciona con los dos tipos de token que da Meta:
- `EAA…` (inicio de sesión unificado / usuario del sistema): graph.facebook.com
- `IGAA…` (inicio de sesión con Instagram): graph.instagram.com

Instagram no recibe archivos: descarga cada imagen desde una URL pública (solo JPEG).
El flujo es: crear "contenedores" -> esperar a que estén listos -> publicar.
El token nunca se imprime ni se guarda.
"""
import time

import requests

GRAPH_VERSION = "v23.0"


class InstagramError(Exception):
    pass


class Instagram:
    def __init__(self, token: str, ig_user_id: str = "", session=None, poll_seconds: float = 3.0):
        if not token:
            raise InstagramError("Falta IG_ACCESS_TOKEN (secreto del repositorio)")
        self.token = token.strip()
        host = "graph.instagram.com" if self.token.startswith("IG") else "graph.facebook.com"
        self.base = f"https://{host}/{GRAPH_VERSION}"
        self.session = session or requests.Session()
        self.poll_seconds = poll_seconds
        self.user_id = ig_user_id.strip()

    # --- HTTP -----------------------------------------------------------------
    def _call(self, method, path, **params):
        params["access_token"] = self.token
        url = path if path.startswith("http") else f"{self.base}/{path.lstrip('/')}"
        for attempt in range(1, 4):
            try:
                r = self.session.request(method, url, params=params if method == "GET" else None,
                                         data=params if method == "POST" else None, timeout=60)
            except requests.RequestException as exc:
                if attempt == 3:
                    raise InstagramError(f"Error de red: {type(exc).__name__}") from None
                time.sleep(5 * attempt)
                continue
            try:
                body = r.json()
            except ValueError:
                body = {}
            if r.status_code >= 500 and attempt < 3:
                time.sleep(5 * attempt)
                continue
            if r.status_code != 200 or "error" in body:
                err = body.get("error", {})
                raise InstagramError(
                    f"HTTP {r.status_code} en {path.split('?')[0]}: {err.get('message', r.text[:200])}"
                    f" (code {err.get('code')}, subcode {err.get('error_subcode')})")
            return body
        raise InstagramError(f"Demasiados reintentos en {path}")

    # --- Cuenta -----------------------------------------------------------------
    def resolve_user_id(self):
        """Busca el id de la cuenta de Instagram del token si no se ha indicado."""
        if self.user_id:
            return self.user_id
        if "graph.instagram.com" in self.base:
            self.user_id = str(self._call("GET", "me", fields="user_id,username")["user_id"])
            return self.user_id
        # Token de Facebook: según cómo se generó, la cuenta aparece en un sitio u otro.
        notes = []

        def first_ig(items, *keys):
            for it in items or []:
                for k in keys:
                    v = it.get(k)
                    if isinstance(v, dict) and v.get("id"):
                        return v["id"]
                    if isinstance(v, dict) and v.get("data"):
                        return v["data"][0]["id"]
            return None

        attempts = [
            ("me/accounts", {"fields": "name,instagram_business_account{id,username}"},
             lambda b: first_ig(b.get("data"), "instagram_business_account")),
            ("me/businesses", {"fields": "name,owned_instagram_accounts{id,username},instagram_accounts{id,username}"},
             lambda b: first_ig(b.get("data"), "owned_instagram_accounts", "instagram_accounts")),
            ("me/instagram_accounts", {"fields": "id,username"},
             lambda b: (b.get("data") or [{}])[0].get("id")),
            ("debug_token", {"input_token": self.token},
             lambda b: next((s["target_ids"][0] for s in b.get("data", {}).get("granular_scopes", [])
                             if s.get("scope") == "instagram_content_publish" and s.get("target_ids")), None)),
        ]
        for path, params, pick in attempts:
            try:
                found = pick(self._call("GET", path, **params))
            except InstagramError as exc:
                notes.append(f"{path}: {exc}")
                continue
            except (KeyError, IndexError, TypeError):
                found = None
            if found:
                self.user_id = str(found)
                return self.user_id
            notes.append(f"{path}: sin cuenta de Instagram")
        raise InstagramError("No encuentro la cuenta de Instagram del token. Intentos:\n    "
                             + "\n    ".join(notes))

    def account_info(self):
        uid = self.resolve_user_id()
        info = self._call("GET", uid, fields="username,media_count")
        try:
            limit = self._call("GET", f"{uid}/content_publishing_limit", fields="config,quota_usage")
            info["publishing_limit"] = (limit.get("data") or [{}])[0]
        except InstagramError as exc:
            info["publishing_limit"] = f"no disponible ({exc})"
        return info

    # --- Contenedores --------------------------------------------------------------
    def _container(self, **params):
        return self._call("POST", f"{self.resolve_user_id()}/media", **params)["id"]

    def wait_ready(self, container_id, timeout=300):
        deadline = time.time() + timeout
        while True:
            status = self._call("GET", container_id, fields="status_code,status").get("status_code")
            if status == "FINISHED":
                return
            if status in ("ERROR", "EXPIRED"):
                raise InstagramError(f"El contenedor {container_id} ha fallado ({status}). "
                                     "¿Instagram no pudo descargar la imagen?")
            if time.time() > deadline:
                raise InstagramError(f"El contenedor {container_id} no está listo tras {timeout} s")
            time.sleep(self.poll_seconds)

    def prepare_carousel(self, image_urls, caption):
        if not 2 <= len(image_urls) <= 10:
            raise InstagramError(f"Un carrusel necesita de 2 a 10 imágenes (hay {len(image_urls)})")
        children = [self._container(image_url=u, is_carousel_item="true") for u in image_urls]
        for c in children:
            self.wait_ready(c)
        parent = self._container(media_type="CAROUSEL", children=",".join(children), caption=caption)
        self.wait_ready(parent)
        return parent

    def prepare_image(self, image_url, caption):
        """Publicación de una sola imagen (p. ej. «Hoy no hay avisos»)."""
        cid = self._container(image_url=image_url, caption=caption)
        self.wait_ready(cid)
        return cid

    def prepare_story(self, image_url):
        cid = self._container(image_url=image_url, media_type="STORIES")
        self.wait_ready(cid)
        return cid

    def publish(self, container_id):
        return self._call("POST", f"{self.resolve_user_id()}/media_publish", creation_id=container_id)["id"]
