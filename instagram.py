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
    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code  # código de error de Meta, si lo hay


class Instagram:
    # Límites de Meta: «Application request limit reached» y similares
    RATE_LIMIT_CODES = (4, 17, 32, 613)

    def __init__(self, token: str, ig_user_id: str = "", session=None, poll_seconds: float = 15.0,
                 rate_wait: float = 90.0):
        if not token:
            raise InstagramError("Falta IG_ACCESS_TOKEN (secreto del repositorio)")
        self.token = token.strip()
        host = "graph.instagram.com" if self.token.startswith("IG") else "graph.facebook.com"
        self.base = f"https://{host}/{GRAPH_VERSION}"
        self.session = session or requests.Session()
        self.poll_seconds = poll_seconds
        self.rate_wait = rate_wait
        self.calls = 0  # llamadas hechas (Meta limita las llamadas por hora)
        self.user_id = ig_user_id.strip()

    # --- HTTP -----------------------------------------------------------------
    def _call(self, method, path, once=False, **params):
        """Llamada a la API con reintentos. `once=True`: sin reintentos (para media_publish,
        que no se puede repetir a ciegas porque podría duplicar la publicación)."""
        params["access_token"] = self.token
        url = path if path.startswith("http") else f"{self.base}/{path.lstrip('/')}"
        for attempt in range(1, 6):
            self.calls += 1
            try:
                r = self.session.request(method, url, params=params if method != "POST" else None,
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
            if r.status_code >= 500 and attempt < 3 and not once:
                time.sleep(5 * attempt)
                continue
            err_code = body.get("error", {}).get("code") if isinstance(body, dict) else None
            if err_code in self.RATE_LIMIT_CODES and attempt < 5 and not once:
                # Se ha agotado el cupo de llamadas: esperar y reintentar (90 s, 180 s, 270 s, 360 s)
                time.sleep(self.rate_wait * attempt)
                continue
            if r.status_code != 200 or (isinstance(body, dict) and "error" in body):
                err = body.get("error", {})
                detail = " · ".join(x for x in (err.get("error_user_title"), err.get("error_user_msg")) if x)
                raise InstagramError(
                    f"HTTP {r.status_code} en {path.split('?')[0]}: {err.get('message', r.text[:200])}"
                    f" (code {err.get('code')}, subcode {err.get('error_subcode')})"
                    + (f" — {detail}" if detail else ""), code=err.get("code"))
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
        """Espera a que Instagram termine de procesar. Pregunta cada vez más espaciado
        (15 s, 22 s, 34 s… hasta 60 s) para no agotar el cupo de llamadas de Meta."""
        deadline = time.time() + timeout
        interval = self.poll_seconds
        while True:
            status = self._call("GET", container_id, fields="status_code,status").get("status_code")
            if status == "FINISHED":
                return
            if status in ("ERROR", "EXPIRED"):
                raise InstagramError(f"El contenedor {container_id} ha fallado ({status}). "
                                     "¿Instagram no pudo descargar la imagen?")
            if time.time() > deadline:
                raise InstagramError(f"El contenedor {container_id} no está listo tras {timeout} s")
            time.sleep(interval)
            interval = min(interval * 1.5, 60)

    def prepare_carousel(self, image_urls, caption):
        if not 2 <= len(image_urls) <= 10:
            raise InstagramError(f"Un carrusel necesita de 2 a 10 imágenes (hay {len(image_urls)})")
        children = [self._container(image_url=u, is_carousel_item="true") for u in image_urls]
        # Cada imagen debe estar terminada antes de crear el carrusel (si no, Meta deja publicar
        # el contenedor pero falla al final con «Fatal», subcódigo 2207085). Las imágenes suelen
        # estar listas a la primera consulta, así que cuesta una llamada por imagen.
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

    def prepare_story_video(self, video_url):
        """Story en vídeo (MP4 H.264 + AAC, 9:16). Instagram tarda más en procesarla."""
        cid = self._container(video_url=video_url, media_type="STORIES")
        self.wait_ready(cid, timeout=600)
        return cid

    def publish(self, container_id):
        """Publica un contenedor sin duplicar nunca.

        Meta a veces responde con error aunque la publicación SÍ ha salido (11-nov-2026: «Fatal»,
        subcódigo 2207085, y cada «reintento» creó un duplicado). Así que tras cualquier error se
        mira el contenedor: PUBLISHED = hecho. Solo se vuelve a intentar si sigue sin publicar
        (FINISHED) y el error fue de cupo de llamadas."""
        last = None
        for attempt in range(1, 5):
            try:
                return self._call("POST", f"{self.resolve_user_id()}/media_publish", once=True,
                                  creation_id=container_id)["id"]
            except InstagramError as exc:
                last = exc
            status = self._status_after_error(container_id)
            if status == "PUBLISHED":
                return container_id  # publicado (Meta no devuelve el id de la publicación)
            if status != "FINISHED" or last.code not in self.RATE_LIMIT_CODES:
                raise last
            time.sleep(self.rate_wait * attempt)
        raise last

    def _status_after_error(self, container_id):
        """Estado del contenedor tras un error al publicar (Meta tarda unos segundos en marcarlo)."""
        status = None
        for wait in (10, 30, 60):
            time.sleep(wait * (self.poll_seconds > 0))
            try:
                status = self._call("GET", container_id, fields="status_code").get("status_code")
            except InstagramError:
                continue
            if status == "PUBLISHED":
                break
        return status
