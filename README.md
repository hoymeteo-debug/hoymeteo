# @hoymeteo · generador de publicaciones diarias

Genera cada mañana, con la previsión de AEMET, las publicaciones de cuatro series:
**calor, frío, lluvia y viento**. Para cada serie crea:

- Un **carrusel** 1080×1350 (portada con podio + puestos 4–10, y 2 diapositivas más hasta el top 30).
- Una **story** 1080×1920 con el top 30 completo (respeta las zonas seguras de Instagram).
- El **texto** (`caption.txt`) con titular, los 5 primeros con hashtag de municipio, bloque de la cuenta y fuente.

Todo queda en `output/AAAA-MM-DD/<serie>/`.

## 1. Instalación

Necesitas Python 3.10 o superior.

```bash
cd hoymeteo
python -m venv .venv
# Windows: .venv\Scripts\activate    ·    Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Clave de AEMET

1. Copia `.env.example` como `.env`.
2. Abre `.env` y escribe tu clave: `AEMET_API_KEY=tu_clave`.

La clave solo vive en ese archivo (no se sube a ningún sitio y `.gitignore` lo excluye).

## 3. Probar

```bash
python run.py --demo            # imágenes con datos inventados, sin clave
python run.py --probe Madrid    # comprueba la conexión con AEMET y enseña lo que lee
python run.py                   # datos reales de hoy
python run.py --series max,rain # solo algunas series
```

**Haz primero `--probe Madrid`.** Confirma que la clave funciona y que los campos que lee el
programa coinciden con los de la respuesta real de AEMET. Después ejecuta `python run.py`:
la primera vez avisará de los municipios cuyo nombre no encuentre en el catálogo de AEMET
(con sugerencias); corrígelos en la columna `nombre_aemet` de `municipios.csv`.

## 4. Uso diario

Ejecuta `python run.py` hacia las 6:30. Tarda unos 16 minutos: por cada municipio pide la
previsión horaria y la diaria (4 llamadas) y respeta el límite de AEMET (1,5 s entre llamadas). Las respuestas se guardan en `cache/`,
así que repetir la ejecución el mismo día es instantáneo (`--refresh` fuerza nuevas llamadas).

Para programarlo: cron en Mac/Linux, o el Programador de tareas en Windows.

Horario de publicación sugerido: máximas 07:00 · mínimas 07:05 · lluvia 07:10 · viento 07:15.

## 5. Pruebas

```bash
pip install pytest
python -m pytest
```

Usan respuestas reales de AEMET guardadas en `tests/fixtures/` (sin claves).

## 6. Personalizar

- `municipios.csv`: los municipios que entran en los rankings (añade o quita filas).
  `provincia` es el código INE de dos cifras. `hashtag` es opcional (se genera solo).
- `config.py`: nombre de cuenta, titulares, colores, textos y hashtags generales.

## Cosas a tener en cuenta

- Los rankings son **entre los municipios de la lista** (unos 110), no entre los 8.100 de España.
  Más municipios = más variedad, pero más tiempo de ejecución.
- **De dónde sale cada dato:** máximas y mínimas de la previsión **diaria** (las mismas que
  publica aemet.es para el día completo); lluvia (mm) y rachas de la previsión **horaria**,
  que es la única con milímetros. La horaria del primer día solo cubre desde la hora en que se
  elabora, así que no sirve para la mínima de la madrugada.
- Las temperaturas de AEMET son enteras, así que hay **muchos empates**; se desempata por nombre.
- Si hay menos de 3 municipios con lluvia o viento, esa serie no se genera ese día.
- AEMET actualiza sus modelos a las 00, 06, 12 y 18 UTC. A las 6:30 estás usando la pasada de las
  00 UTC. El programa avisa si las predicciones no son de hoy.
- Cita siempre a AEMET como fuente (ya va en las imágenes y en el texto).

## Pendiente (siguientes fases)

- Serie de **avisos** (Meteoalerta) y de **nieve en estaciones de esquí**.
- Publicación automática en Instagram (requiere cuenta profesional vinculada a una página de Facebook)
  y en TikTok (requiere aprobación de la aplicación).

La tipografía Inter se distribuye bajo licencia SIL Open Font License.
