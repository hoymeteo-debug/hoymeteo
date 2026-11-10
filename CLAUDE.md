# Proyecto @hoymeteo

Cuentas de Instagram y TikTok `@hoymeteo` que publican cada mañana (07:00–07:30) el tiempo
de hoy en España en forma de rankings. Dueño: Víctor. Idioma de trabajo: español, tuteo,
directo y sin preámbulos. Código modular, documentado y listo para producción.

**Objetivo final: cero trabajo diario para Víctor.** Datos, imágenes, textos, publicación en
Instagram y TikTok y programación, todo automático. Víctor solo hace la configuración inicial y
recibe un aviso únicamente si algo falla. "Súbelo a mano" no es una solución válida, solo un
paso provisional mientras llega una aprobación.

## Estado actual

Ya existe un generador en Python que, con la previsión de AEMET, crea para cuatro
series (`max`, `min`, `rain`, `wind`): carrusel 1080×1350 (podio + top 30), story 1080×1920 y
`caption.txt`.

**Validado contra la API real (9-nov-2026):** el esquema de la horaria coincide (`temperatura`,
`precipitacion`, `vientoAndRachaMax` con `value` = racha). Máx/mín se toman de la previsión
**diaria** (`temperatura.maxima/minima`), porque la horaria del primer día empieza en la hora de
elaboración y además da valores más bajos que la oficial (Madrid: 16° horaria vs 18° diaria).
Lluvia y rachas, de la horaria. Los 122 municipios de `municipios.csv` se resuelven (10 pueblos fríos de montaña añadidos el 10-nov para que las mínimas de invierno tengan más contraste). Una
ejecución completa son 448 llamadas (~16 min reales; empezar a las 06:15 como tarde). Pruebas: `python -m pytest` (fixtures reales en
`tests/fixtures/`). Medido el 10-nov-2026: entre 06:16 y 07:00 (Madrid) AEMET seguía sirviendo la predicción elaborada
la víspera a las 20:59; la de madrugada no llega antes de las 07:00. Se usa esa, es la última disponible
(por eso el aviso «elaboradas otro día» es normal y no bloquea).

**Instagram en marcha (10-nov-2026, aprobado por Víctor):** `instagram.py` + `publish.py`. Token de
inicio de sesión unificado (usuario del sistema, empieza por EAA, no caduca) en el secreto
`IG_ACCESS_TOKEN`; ese token no deja averiguar la cuenta, así que su id va en
`config.INSTAGRAM_USER_ID`. Las JPEG se suben cada día a la rama `media` (se reescribe, las
antiguas desaparecen) y se sirven por raw.githubusercontent.com. `INSTAGRAM_AUTOPUBLISH = True`:
la ejecución diaria publica carrusel + story de cada serie a su hora. A mano: botón
"Run workflow" con modo nada / comprobar / preparar / publicar.

**Serie de avisos hecha (10-nov-2026):** `avisos.py` descarga `avisos_cap/ultimoelaborado/area/esp`
(tar de XML CAP), descarta verdes y cancelaciones, filtra los vigentes hoy en hora de Madrid y agrupa
por zona + fenómeno (nivel más alto y solo las cifras de ese nivel). Provincia = dígitos 3-4 del código
de zona, salvo Baleares/Canarias (isla). Render en `render.py` (`render_avisos_*`): portada con recuento
por color + 8 filas, resto equilibrado hasta 10 diapositivas; story con 12 filas; sin avisos, imagen
única «Hoy no hay avisos». Publica a las 07:25. Si falla la descarga NO se publica «no hay avisos»: se
anota en `output/<fecha>/ERRORES.txt`, se publica el resto y la ejecución acaba en error (correo).

**Serie de contraste (10-nov-2026, elegida por Víctor):** ocupa el hueco de las 07:20 mientras no haya
temporada de esquí. «Hoy habrá más contraste en» = máxima − mínima oficiales (diaria). Cada fila lleva
la hora de ambas, de la horaria («↓14° a las 7 h · ↑28° a las 15 h»; si se mantiene varias horas, la
del medio). Las horas solo se muestran si la horaria trae el día completo (24 h); si no, «↓14° · ↑28°».
Cuando llegue la serie de nieve/esquí, decidir con Víctor si el contraste se mueve a otra hora.

**TikTok preparado (10-nov-2026), pendiente de Víctor:** `tiktok.py` + `tiktok_cli.py`, web en
`docs/` (privacidad, condiciones, página de retorno `/tiktok/` que muestra el código), workflows
`web.yml` (Pages por Actions, incluye la rama `media` en `/media/`), `tiktok-conectar.yml` y
`tiktok-prueba.yml`. Autorización guardada **cifrada** en `tiktok_state.enc` con clave derivada de
`TIKTOK_CLIENT_SECRET` (el refresh token rota en cada renovación). Pasos de Víctor en
`GUIA_TIKTOK.md`. Falta: activar Pages (Source: GitHub Actions), client key en
`config.TIKTOK_CLIENT_KEY`, archivo de verificación de URL en `docs/`, conectar, prueba privada,
revisión. Luego integrar en `diario.yml` con `TIKTOK_AUTOPUBLISH`.

Archivos: `run.py` (CLI), `config.py` (series, colores, textos), `aemet_client.py` (cliente y
parser), `data_sources.py` (datos reales/demo y rankings), `render.py` (Pillow), `captions.py`,
`municipios.csv` (≈110 municipios, código INE de provincia), `README.md`.

## Decisiones ya tomadas (no cambiar sin preguntar)

- **Titulares en frase:** "Hoy hará más calor en", "Hoy hará más frío en", "Hoy lloverá más en",
  "Hoy hará más viento en", "Hoy nevará más en / se podrá esquiar más en".
- **Datos de previsión de hoy**, no medidos, para poder publicar a las 7:00. Etiqueta "PREVISIÓN".
- **Diseño:** podio real (2-1-3) con pilares + tabla; top **30**, sin más municipios.
  Un color por serie: máximas cálido/rojo, mínimas azul, lluvia verde azulado, viento violeta,
  nieve gris hielo, avisos rojo suave. Tipografía Inter. Sin medallas.
- **Formato:** carrusel en el feed (portada con podio + 10 filas por diapositiva) y story 9:16 con
  las 30 filas (zonas seguras ~250 px arriba y abajo).
- **Calendario:** 07:00 máximas · 07:05 mínimas · 07:10 lluvia · 07:15 viento · 07:20 nieve ·
  07:25 avisos · 07:30 mapa o "hoy vs ayer" (domingos: récords de la semana).
- **Texto de Instagram (copy):** 1) titular con el primer puesto y su dato; 2) los **5 primeros
  como hashtag de municipio**, sin tildes (#Malaga), con su valor; 3) invitación a deslizar;
  4) bloque fijo: "📍 Cada mañana, el tiempo de hoy en España para tomártelo con el café. Sigue
  @hoymeteo y no te pierdas ninguno."; 5) "Fuente: AEMET"; 6) 2–3 hashtags generales.
- Hashtags de municipio como la gente los escribe (#SantiagoDeCompostela, no #Santiago).

## Hoja de ruta (en este orden)

1. **Validar contra AEMET real.** Clave en `.env` (`AEMET_API_KEY`, nunca en el repositorio).
   Ejecutar `python run.py --probe Madrid`, comprobar campos reales, corregir
   `parse_horaria` y los nombres sin resolver en `municipios.csv`. Revisar el límite de
   peticiones de AEMET y la hora a la que publica la pasada de las 00 UTC.
2. **Pruebas automáticas** (pytest) del parser, la resolución de nombres y los rankings, con
   respuestas reales guardadas como fixtures (sin claves).
3. **Repositorio Git y ejecución diaria sin intervención.** Ejecutar el script a las ~06:30
   (hora de Madrid) con GitHub Actions o un servidor pequeño. Ojo: el `cron` de GitHub puede
   retrasarse; y los horarios de verano/invierno cambian el UTC. El script es determinista:
   **no usar un modelo de IA para ejecutarlo cada día**.
4. **Serie de avisos (Meteoalerta).** Fuente AEMET `avisos_cap`. Ficha: filas ordenadas de más
   a menos grave con **zona, motivo (icono + cifra) y color** (rojo/naranja/amarillo, con texto
   del nivel además del color), resumen con recuento por color. Hashtags de provincia/zona,
   no de municipio. Sin avisos: post "Hoy no hay avisos meteorológicos". Citar siempre AEMET.
5. **Serie de nieve.** Ranking por **km esquiables** con **número de pistas abiertas**. No sale
   de AEMET: sale del parte de cada estación. Investigar fuentes reutilizables. Activar solo en
   temporada (normalmente desde diciembre).
6. **Publicación automática.** Instagram Graph API (cuenta profesional vinculada a página de
   Facebook; carrusel y stories) y TikTok Content Posting API (requiere aprobar la app).
   Para las URL públicas que exige Instagram, valorar primero opciones gratuitas (GitHub Pages / raw del repo).
7. **Extras:** mapa de España coloreado, "hoy vs ayer", récords semanales, versión vídeo para
   TikTok, y web con SEO para monetizar (patrocinios, afiliación).

## Límites y cuidados

- Nada de claves, tokens ni contraseñas en el código, el repositorio ni los registros.
- AEMET: citar la fuente siempre y **comprobar sus condiciones de reutilización** antes de
  vender patrocinios. No dar a entender que la cuenta es oficial (nada de "AEMET" en el nombre).
- Los rankings son entre los municipios de `municipios.csv`; las temperaturas son enteras, así
  que hay empates (desempate por nombre).
- Si una serie no tiene datos suficientes ese día, no se publica; no inventar datos.
- Antes de publicar de verdad en las cuentas, pedir confirmación a Víctor.

## Despliegue y automatización total

- **Dónde corre (decidido por Víctor, 10-nov-2026):** primero alternativas **online y gratuitas**;
  el NAS (UGREEN DXP2800, admite Docker) queda solo como plan B. Elegido: **GitHub Actions** en
  repositorio público (minutos ilimitados). `.github/workflows/diario.yml`: cron 03:47 UTC +
  `wait_until.py 06:15` (hora de Madrid, inmune al cambio de hora y a retrasos del cron),
  pruebas, generación, artefacto con el material y commit diario de `history/` (evita que GitHub
  desactive el cron tras 60 días sin actividad). Si falla, GitHub avisa por correo.
- **Premisa de Víctor:** no quiere hacer nada manual. Minimizar la configuración inicial y
  agrupar en una sola vez lo que solo pueda hacer él.
- **Instagram:** la Graph API exige que las imágenes estén en una **URL pública**. Subirlas cada
  mañana a un almacenamiento externo (p. ej. Cloudflare R2 o S3) y borrarlas después.
  Renovar automáticamente los tokens de larga duración (caducan a los ~60 días) antes de que expiren.
- **TikTok:** Content Posting API; mientras la app no esté auditada, las publicaciones salen
  privadas. Si la aprobación se atasca, valorar un intermediario de pago (Ayrshare, Publer u otro)
  que publique en ambas redes, comprobando antes precio y condiciones.
- **Fiabilidad:** reintentos, registro de cada ejecución y aviso a Víctor (correo o Telegram)
  **solo cuando algo falle o esté a punto de caducar un token**. Nunca pedirle nada a diario.
- **Salvaguardas:** si los datos son sospechosos (menos municipios de los esperados, valores
  idénticos a ayer, predicción no elaborada hoy), no publicar y avisar.
- **Horario:** 07:00 máximas · 07:05 mínimas · 07:10 lluvia · 07:15 viento · 07:20 nieve ·
  07:25 avisos · 07:30 mapa. El script debe empezar a generar ~06:30 y publicar a su hora exacta.

## Lo que solo puede hacer Víctor (avisar cuando toque)

Poner la clave de AEMET en `.env`; pasar Instagram a cuenta profesional y vincular la página de
Facebook; autorizar la app de Meta y TikTok; aprobar la primera publicación real.
