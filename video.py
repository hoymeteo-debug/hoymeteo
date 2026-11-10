"""Stories en vídeo: anima la imagen de la story y le pone una pista lo-fi propia.

Parte de `story.png` y de su `story.json` (posición de cada elemento, lo genera render.py).
Cada fotograma se compone pegando recortes de la imagen final con un desplazamiento y una
opacidad que siguen una curva de aceleración suave (ease-out): nada de rebotes ni saltos.

Orden de entrada: cabecera → podio (3.º, 2.º, 1.º) o tarjetas de avisos → filas → pie.
Después la imagen queda quieta para que dé tiempo a leerla.
"""
import json
import subprocess
from pathlib import Path

from PIL import Image

import config

FPS = 30
DURATION = 12.0          # segundos
MUSIC_DIR = config.BASE / "music"


def ease_out(t):
    """Desaceleración marcada (similar a cubic-bezier(0.23, 1, 0.32, 1))."""
    t = min(max(t, 0.0), 1.0)
    return 1 - (1 - t) ** 4


def ffmpeg_exe():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"


def pick_track(target_date, series_key, long=False):
    """Pista distinta por serie y día (se van alternando). long=True: versiones de 52 s (Short)."""
    tracks = sorted(MUSIC_DIR.glob("lofi_largo_*.m4a" if long else "lofi_[0-9]*.m4a"))
    if not tracks:
        return None
    pos = list(config.SERIES).index(series_key) if series_key in config.SERIES else 0
    return tracks[(target_date.toordinal() * 7 + pos) % len(tracks)]


def schedule(elements):
    """Asigna a cada elemento (inicio, duración) en segundos."""
    timed = []
    has_intro = any(e["kind"] in ("rise", "pop") for e in elements)
    rows = sorted((e for e in elements if e["kind"] == "row"), key=lambda e: e["order"])
    rows_start = 1.55 if has_intro else 0.7
    for e in elements:
        k, o = e["kind"], e["order"]
        if k == "header":
            start, dur = 0.15, 0.6
        elif k == "rise":
            start, dur = 0.6 + 0.2 * (o - 1), 0.8   # orden 1 = 3.er puesto: el 1.º entra el último
        elif k == "pop":
            start, dur = 0.6 + 0.12 * o, 0.5
        elif k == "fade":
            start, dur = 0.55, 0.4
        elif k == "row":
            start, dur = rows_start + 0.055 * rows.index(e), 0.45
        else:  # pie y notas
            last_row = rows_start + 0.055 * max(len(rows) - 1, 0)
            start, dur = last_row + 0.3, 0.5
        timed.append((e, start, dur))
    return timed


def compose(final, bg, timed, t, crops):
    frame = bg.copy()
    for e, start, dur in timed:
        p = ease_out((t - start) / dur)
        if p <= 0:
            continue
        x0, y0, x1, y1 = e["box"]
        crop = crops[id(e)]
        if p >= 1:
            frame.paste(crop, (x0, y0))
            continue
        alpha = Image.new("L", crop.size, int(255 * min(1.0, p * 1.4)))
        kind = e["kind"]
        if kind == "rise":  # sube desde la línea base, recortado por abajo
            h = y1 - y0
            visible = max(1, int(h * p))
            frame.paste(crop.crop((0, 0, crop.width, visible)), (x0, y1 - visible),
                        alpha.crop((0, 0, crop.width, visible)))
        elif kind == "pop":  # crece ligeramente desde el centro
            scale = 0.92 + 0.08 * p
            w, h = max(1, int(crop.width * scale)), max(1, int(crop.height * scale))
            small = crop.resize((w, h), Image.BILINEAR)
            frame.paste(small, (x0 + (crop.width - w) // 2, y0 + (crop.height - h) // 2), alpha.resize((w, h)))
        else:  # entra deslizándose hacia arriba
            dy = int((1 - p) * (28 if kind == "row" else 20))
            frame.paste(crop, (x0, y0 + dy), alpha)
    return frame


def render_story_video(story_png, out_mp4, music=None, duration=DURATION):
    story_png, out_mp4 = Path(story_png), Path(out_mp4)
    layout = json.loads(story_png.with_suffix(".json").read_text(encoding="utf-8"))
    final = Image.open(story_png).convert("RGB")
    w, h = final.size
    bg = Image.new("RGB", (w, h), layout["bg"])
    timed = schedule(layout["elements"])
    crops = {id(e): final.crop(tuple(e["box"])) for e, _, _ in timed}
    end_anim = max(s + d for _, s, d in timed) if timed else 0

    cmd = [ffmpeg_exe(), "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(FPS), "-i", "-"]
    if music:
        fade_at = duration - 1.5
        cmd += ["-i", str(music), "-af", f"afade=t=in:d=0.4,afade=t=out:st={fade_at}:d=1.5",
                "-c:a", "aac", "-b:a", "128k", "-ar", "48000"]
    cmd += ["-t", str(duration), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-profile:v", "high", "-movflags", "+faststart", str(out_mp4)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    still = final.tobytes()
    try:
        for i in range(int(duration * FPS)):
            t = i / FPS
            proc.stdin.write(still if t > end_anim else compose(final, bg, timed, t, crops).tobytes())
    finally:
        proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError(f"ffmpeg falló al crear {out_mp4}")
    return out_mp4


# --- Short diario de YouTube: todas las series en un vídeo ------------------------------
SEGMENT = 7.0      # segundos por serie
INTRO, OUTRO = 1.8, 2.4
FADE = 0.25        # fundido entre series


def _card(lines, bg="#0E4A85", fg="#FFFFFF", sub="#BFD3EA", size=(1080, 1920)):
    """Tarjeta de entrada o de cierre: logo de hoymeteo y texto, con los colores del perfil."""
    import render
    cv = render.Canvas(size[0], size[1], bg)
    y = 1010
    for text, px, color, bold in lines:
        color = {"fg": fg, "sub": sub}[color]
        for ln in cv.wrap(text, px, size[0] - 160, bold=bold, max_lines=2):
            cv.text(size[0] / 2, y, ln, px, color, bold=bold, anchor="mm")
            y += px * 1.25
        y += 18
    img = cv.img.resize(size, Image.LANCZOS)
    logo_file = config.BASE / "docs" / "perfiles" / "hoymeteo.png"
    if logo_file.exists():
        logo = Image.open(logo_file).convert("RGB").resize((420, 420), Image.LANCZOS)
        mask = Image.new("L", (420 * 4, 420 * 4), 0)
        from PIL import ImageDraw
        ImageDraw.Draw(mask).ellipse([0, 0, 420 * 4 - 1, 420 * 4 - 1], fill=255)
        img.paste(logo, ((size[0] - 420) // 2, 520), mask.resize((420, 420), Image.LANCZOS))
    return img


def render_daily_short(story_pngs, out_mp4, date_text, music=None):
    """Une las stories del día en un Short: entrada, una serie tras otra y cierre."""
    story_pngs = [Path(p) for p in story_pngs if Path(p).exists()]
    if not story_pngs:
        raise RuntimeError("No hay stories para montar el Short")
    intro = _card([("El tiempo de hoy en España", 64, "fg", True), (date_text, 40, "sub", False)])
    outro = _card([("Cada mañana a las 7:00", 56, "fg", True), (f"Sigue a {config.HANDLE}", 40, "sub", False)])
    segments = []
    for png in story_pngs:
        layout = json.loads(png.with_suffix(".json").read_text(encoding="utf-8"))
        final = Image.open(png).convert("RGB")
        timed = schedule(layout["elements"])
        segments.append((final, Image.new("RGB", final.size, layout["bg"]), timed,
                         {id(e): final.crop(tuple(e["box"])) for e, _, _ in timed}))
    w, h = intro.size
    starts = [INTRO + i * SEGMENT for i in range(len(segments))] + [INTRO + SEGMENT * len(segments)]
    duration = starts[-1] + OUTRO

    def frame_at(t):
        if t < INTRO:
            return intro
        idx = int((t - INTRO) // SEGMENT)
        if idx >= len(segments):
            return outro
        final, bg, timed, crops = segments[idx]
        return compose(final, bg, timed, t - starts[idx], crops)

    # Imagen con la que acaba cada tramo, para fundirla con el comienzo del siguiente
    ends = [intro] + [seg[0] for seg in segments]

    cmd = [ffmpeg_exe(), "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(FPS), "-i", "-"]
    if music:
        cmd += ["-i", str(music), "-af", f"afade=t=in:d=0.5,afade=t=out:st={duration - 2:.2f}:d=2",
                "-c:a", "aac", "-b:a", "128k", "-ar", "48000"]
    cmd += ["-t", f"{duration:.2f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
            "-pix_fmt", "yuv420p", "-profile:v", "high", "-movflags", "+faststart", str(out_mp4)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        for i in range(int(duration * FPS)):
            t = i / FPS
            img = frame_at(t)
            for k, b in enumerate(starts):
                if b <= t < b + FADE:
                    img = Image.blend(ends[k], img, ease_out((t - b) / FADE))
            proc.stdin.write(img.tobytes())
    finally:
        proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError(f"ffmpeg falló al crear {out_mp4}")
    return out_mp4
