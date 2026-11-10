# Guía: conectar TikTok con @hoymeteo

Tiempo: unos 30 minutos, **una sola vez**. Mejor desde el ordenador.
Lo que va en *cursiva* son nombres de botones o pantallas; TikTok cambia a veces los textos,
así que si alguno no coincide exactamente, busca el más parecido o mándale una captura a Claude.

Al terminar, TikTok revisa la app (de unos días a dos semanas). Hasta que la apruebe, lo que se
publique por la API solo puede ser **privado**. Instagram sigue funcionando igual mientras tanto.

---

## Paso 0 · Activar la web (1 minuto)

TikTok exige una web con política de privacidad. Ya está hecha; solo hay que encenderla.

1. Abre https://github.com/hoymeteo-debug/hoymeteo/settings/pages
2. En *Build and deployment → Source* elige **GitHub Actions**.
3. Díselo a Claude: la publica y comprueba que se ve en https://hoymeteo-debug.github.io/hoymeteo/

## Paso 1 · Cuenta de TikTok

- Necesitas la cuenta **@hoymeteo** creada en la app de TikTok.
- Debe ser **cuenta personal**, no de empresa: TikTok no deja hacer cuentas de empresa privadas
  y las pruebas (antes de la aprobación) solo funcionan con la cuenta en privado.
- Ponla **privada** de momento: *Perfil → ☰ → Ajustes y privacidad → Privacidad → Cuenta privada*.
  Cuando TikTok apruebe la app, la vuelves a poner pública.

## Paso 2 · Crear la app en TikTok for Developers

1. Entra en https://developers.tiktok.com e inicia sesión (*Log in*) con la cuenta @hoymeteo.
2. Arriba a la derecha: *Manage apps* (o *My apps*) → *Connect an app* / *Create app*.
   Si pregunta si eres organización o particular, elige **individual / particular**.
3. Rellena los datos de la app:

| Campo | Qué poner |
|---|---|
| App icon | Descarga https://hoymeteo-debug.github.io/hoymeteo/icono.png (1024×1024) |
| App name | `HoyMeteo` |
| Category | La más parecida a **News / Weather** (si no hay, *Utilities*) |
| Description | `Publica cada mañana en la cuenta propia @hoymeteo rankings del tiempo previsto en España (calor, frío, lluvia y viento) con datos de AEMET.` |
| Terms of Service URL | `https://hoymeteo-debug.github.io/hoymeteo/condiciones/` |
| Privacy Policy URL | `https://hoymeteo-debug.github.io/hoymeteo/privacidad/` |
| Platforms | **Web** → Website URL: `https://hoymeteo-debug.github.io/hoymeteo/` |

## Paso 3 · Productos y permisos

En la misma app, sección *Products* → *Add products*:

1. **Login Kit**
   - *Redirect URI* (Web): `https://hoymeteo-debug.github.io/hoymeteo/tiktok/`
2. **Content Posting API**
   - Activa **Direct Post**.
3. Sección *Scopes*: asegúrate de que están **`user.info.basic`** y **`video.publish`**.

Guarda los cambios (*Save*).

## Paso 4 · Verificar la web (para que TikTok acepte las imágenes)

TikTok solo descarga imágenes de webs verificadas.

1. En la app: *Content Posting API* → *URL properties* / *Verify domains* → *Add URL*.
2. Elige **URL prefix** y escribe: `https://hoymeteo-debug.github.io/hoymeteo/`
3. TikTok te da un **archivo para descargar** (algo como `tiktokXXXX.txt`). Descárgalo y
   **adjúntaselo a Claude en el chat** (no es secreto). Claude lo sube a la web.
4. Cuando Claude te diga que está subido, pulsa *Verify* en TikTok.

## Paso 5 · Claves de la app

En la app, apartado *App details* / *Credentials*, hay dos claves:

- **Client key**: no es secreta. **Pégasela a Claude en el chat.**
- **Client secret**: esta sí es secreta. **No la pegues en el chat.** Guárdala en GitHub:
  https://github.com/hoymeteo-debug/hoymeteo/settings/secrets/actions → *New repository secret* →
  Name `TIKTOK_CLIENT_SECRET`, Secret: la clave → *Add secret*.

> Si el portal tiene un modo **Sandbox**, usa las claves de Sandbox para las pruebas y añade
> @hoymeteo como *Target user* / usuario de prueba. Claude te dirá cuándo cambiar a las de producción.

## Paso 6 · Autorizar la cuenta (Claude te da el enlace)

1. Abre el enlace de autorización que te pase Claude e inicia sesión con @hoymeteo → *Authorize*.
2. Vuelves a la web de HoyMeteo, que te muestra un **código** con un botón *Copiar código*.
3. Pulsa el enlace *Abrir «TikTok: conectar» en GitHub* → *Run workflow* → pega el código →
   *Run workflow*. Tienes unos 5 minutos antes de que caduque el código.

A partir de aquí la autorización se renueva sola; no hay que repetirlo.

## Paso 7 · Publicación de prueba y vídeo para la revisión

1. Claude lanza una publicación de prueba **privada** en @hoymeteo.
2. Graba la pantalla (en iPhone: *Centro de control → Grabar pantalla*; en Mac: `Cmd + Shift + 5`)
   mostrando, en un solo vídeo de 1–2 minutos:
   - la web https://hoymeteo-debug.github.io/hoymeteo/ y su política de privacidad,
   - el enlace de autorización y la pantalla de TikTok pidiendo permiso,
   - la publicación de prueba en tu perfil de TikTok.

## Paso 8 · Enviar a revisión

1. En la app: *Submit for review*. Adjunta el vídeo.
2. Cuando pida explicar el uso, pega este texto (en inglés, que es lo que leen los revisores):

> HoyMeteo is a small automation used only by the owner of the TikTok account @hoymeteo.
> Every morning it builds a photo carousel with today's weather forecast rankings for Spain
> (hottest, coldest, rainiest and windiest towns), using open data from the Spanish
> Meteorological Agency (AEMET), and publishes it to @hoymeteo with the Content Posting API
> (Direct Post, photo mode). The account owner authorized the app once with Login Kit. No data
> from other users is collected or stored. Images are served from our verified domain
> hoymeteo-debug.github.io/hoymeteo.

3. Si después aparece una solicitud aparte para **Content Posting API / Direct Post audit**,
   envíala también con el mismo texto y el mismo vídeo.

Cuando TikTok responda (por correo), díselo a Claude: activa la publicación diaria en TikTok o,
si la rechazan, te propone la alternativa (un servicio de pago que publique por ti).
