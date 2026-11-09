"""Renderizado de imágenes con Pillow (carrusel 4:5 y story 9:16)."""
import math
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import config

S = 2  # supersampling: se dibuja al doble y se reduce para suavizar bordes


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mix(a, b, t):
    a, b = rgb(a), rgb(b)
    return "#%02X%02X%02X" % tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


@lru_cache(maxsize=None)
def font(px, bold=False):
    path = config.FONT_DIR / ("Inter-Bold.otf" if bold else "Inter-Medium.otf")
    try:
        return ImageFont.truetype(str(path), int(round(px * S)))
    except OSError:
        return ImageFont.load_default(int(round(px * S)))


class Canvas:
    def __init__(self, w, h, bg):
        self.w, self.h = w, h
        self.img = Image.new("RGB", (w * S, h * S), rgb(bg))
        self.d = ImageDraw.Draw(self.img)

    def rect(self, x0, y0, x1, y1, fill, r=0, corners=None):
        box = [x0 * S, y0 * S, x1 * S, y1 * S]
        if r:
            self.d.rounded_rectangle(box, radius=r * S, fill=rgb(fill), corners=corners)
        else:
            self.d.rectangle(box, fill=rgb(fill))

    def circle(self, cx, cy, r, fill):
        self.d.ellipse([(cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S], fill=rgb(fill))

    def text(self, x, y, s, size, fill, bold=False, anchor="lm"):
        self.d.text((x * S, y * S), s, font=font(size, bold), fill=rgb(fill), anchor=anchor)

    def width(self, s, size, bold=False):
        return self.d.textlength(s, font=font(size, bold)) / S

    def fit(self, s, size, max_w, bold=False):
        """Recorta con puntos suspensivos si no cabe."""
        if self.width(s, size, bold) <= max_w:
            return s
        while len(s) > 1 and self.width(s + "…", size, bold) > max_w:
            s = s[:-1]
        return s.rstrip() + "…"

    def wrap(self, s, size, max_w, bold=False, max_lines=2):
        words, lines, cur = s.split(), [], ""
        for w in words:
            test = (cur + " " + w).strip()
            if self.width(test, size, bold) <= max_w or not cur:
                cur = test
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            lines[-1] = self.fit(lines[-1] + "…", size, max_w, bold)
        return [self.fit(l, size, max_w, bold) for l in lines]

    def line(self, pts, fill, width):
        self.d.line([(x * S, y * S) for x, y in pts], fill=rgb(fill), width=int(width * S))
        for x, y in (pts[0], pts[-1]):
            self.circle(x, y, width / 2, fill)

    def arc(self, cx, cy, r, start, end, fill, width):
        self.d.arc([(cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S], start, end, fill=rgb(fill), width=int(width * S))

    def save(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.img.resize((self.w, self.h), Image.LANCZOS).save(path, optimize=True)


# --- Iconos dibujados con formas simples -------------------------------------------
def draw_icon(cv, kind, cx, cy, r, circle_color, fg="#FFFFFF"):
    k = r / 48.0
    cv.circle(cx, cy, r, circle_color)
    if kind in ("thermometer_plus", "thermometer_minus"):
        tx = cx - 8 * k
        cv.rect(tx - 7 * k, cy - 28 * k, tx + 7 * k, cy + 10 * k, fg, r=7 * k)
        cv.circle(tx, cy + 17 * k, 15 * k, fg)
        cv.circle(tx, cy + 17 * k, 7 * k, circle_color)
        cv.rect(tx - 3 * k, cy - 12 * k, tx + 3 * k, cy + 17 * k, circle_color)
        mx, my = cx + 21 * k, cy - 14 * k
        cv.line([(mx - 10 * k, my), (mx + 10 * k, my)], fg, 5 * k)
        if kind == "thermometer_plus":
            cv.line([(mx, my - 10 * k), (mx, my + 10 * k)], fg, 5 * k)
    elif kind == "drop":
        cv.d.polygon([(cx * S, (cy - 32 * k) * S), ((cx - 19 * k) * S, (cy + 2 * k) * S), ((cx + 19 * k) * S, (cy + 2 * k) * S)], fill=rgb(fg))
        cv.circle(cx, cy + 9 * k, 20 * k, fg)
    elif kind == "wind":
        x0 = cx - 28 * k
        cv.line([(x0, cy - 16 * k), (cx + 12 * k, cy - 16 * k)], fg, 6 * k)
        cv.arc(cx + 12 * k, cy - 25 * k, 9 * k, 90, 360, fg, 6 * k)
        cv.line([(x0, cy + 3 * k), (cx + 26 * k, cy + 3 * k)], fg, 6 * k)
        cv.line([(x0, cy + 21 * k), (cx + 6 * k, cy + 21 * k)], fg, 6 * k)
        cv.arc(cx + 6 * k, cy + 30 * k, 9 * k, 270, 180, fg, 6 * k)


# --- Bloques de diseño -----------------------------------------------------------------
def draw_header(cv, cfg, x, y_center, date_label, scale=1.0, right_text=None, right_x=None):
    c = cfg["colors"]
    r = 46 * scale
    draw_icon(cv, cfg["icon"], x + r, y_center, r, c["accent"])
    tx = x + 2 * r + 24 * scale
    cv.text(tx, y_center - 28 * scale, f"PREVISIÓN · {date_label}", 24 * scale, c["label"], bold=True)
    cv.text(tx, y_center + 14 * scale, cfg["title"], 50 * scale, c["text"], bold=True)
    if right_text:
        cv.text(right_x, y_center - 28 * scale, right_text, 24 * scale, c["label"], bold=True, anchor="rm")


def draw_value(cv, cx, baseline, cfg, value, size, color):
    num, unit = cfg["parts"](value)
    usize = max(size * 0.42, 22)
    wn, wu = cv.width(num, size, True), cv.width(unit, usize, False) if unit else 0
    x = cx - (wn + wu) / 2
    cv.text(x, baseline, num, size, color, bold=True, anchor="ls")
    if unit:
        cv.text(x + wn, baseline, unit, usize, color, anchor="ls")


def draw_podium(cv, cfg, top3, x0, x1, base_y, heights, sizes):
    """Podio 2-1-3. sizes = (valor_1º, valor_otros, nombre_1º, nombre_otros)."""
    c = cfg["colors"]
    gap = 20
    colw = (x1 - x0 - 2 * gap) / 3
    order = [1, 0, 2]  # posiciones izquierda, centro, derecha
    cv.rect(x0, base_y, x1, base_y + 3, c["label"])
    for slot, idx in enumerate(order):
        if idx >= len(top3):
            continue
        item = top3[idx]
        cx = x0 + slot * (colw + gap) + colw / 2
        h = heights[idx]
        top = base_y - h
        cv.rect(cx - colw / 2, top, cx + colw / 2, base_y, c["pillars"][idx], r=18, corners=(True, True, False, False))
        cv.text(cx, top + h * 0.42, str(idx + 1), 84 if idx == 0 else 60, c["pillar_text"][idx], bold=True, anchor="mm")
        vsize = sizes[0] if idx == 0 else sizes[1]
        vbase = top - 22
        draw_value(cv, cx, vbase, cfg, item["value"], vsize, c["accent"])
        nsize = sizes[2] if idx == 0 else sizes[3]
        lines = cv.wrap(item["name"], nsize, colw - 8, bold=True, max_lines=2)
        ny = vbase - vsize - 16 - (len(lines) - 1) * nsize * 1.2
        for i, ln in enumerate(lines):
            cv.text(cx, ny + i * nsize * 1.2, ln, nsize, c["text"], bold=True, anchor="mm")


def draw_rows(cv, cfg, rows, start_rank, total, x0, x1, y0, row_h, gap, name_size, val_size):
    c = cfg["colors"]
    row_bg = mix(c["bg"], "#FFFFFF", 0.55)
    for i, item in enumerate(rows):
        rank = start_rank + i
        y = y0 + i * (row_h + gap)
        t = (rank - 1) / max(total - 1, 1)
        cv.rect(x0, y, x1, y + row_h, row_bg)
        cv.rect(x0, y, x0 + 9, y + row_h, mix(c["strip_from"], c["strip_to"], t))
        cy = y + row_h / 2
        cv.text(x0 + 26, cy, str(rank), name_size * 0.85, c["label"], bold=True)
        num, unit = cfg["parts"](item["value"])
        val = num + unit
        vw = cv.width(val, val_size, True)
        cv.text(x1 - 16, cy, val, val_size, c["accent"], bold=True, anchor="rm")
        rank_w = 26 + cv.width(str(total), name_size * 0.85, True) + 20
        name = cv.fit(item["name"], name_size, (x1 - x0) - rank_w - vw - 40)
        cv.text(x0 + rank_w, cy, name, name_size, c["text"])


def footer(cv, cfg, y, size=24):
    cv.text(cv.w / 2, y, f"Fuente: AEMET · {config.HANDLE}", size, cfg["colors"]["label"], bold=True, anchor="mm")


# --- Composiciones ----------------------------------------------------------------------
def render_carousel(cfg, ranking, date_label, out_dir):
    W, H, M = 1080, 1350, 64
    out_dir = Path(out_dir)
    total = len(ranking)
    first_rows = ranking[3:10]
    rest = ranking[10:]
    chunks = [rest[i:i + 10] for i in range(0, len(rest), 10)]
    n_slides = 1 + len(chunks)
    paths = []

    # Portada: podio + puestos 4 a 10
    cv = Canvas(W, H, cfg["colors"]["bg"])
    draw_header(cv, cfg, M, 120, date_label, right_text=f"1/{n_slides}", right_x=W - M)
    draw_podium(cv, cfg, ranking[:3], M, W - M, 760, (330, 240, 175), (96, 66, 46, 38))
    draw_rows(cv, cfg, first_rows, 4, total, M, W - M, 800, 60, 8, 32, 34)
    footer(cv, cfg, H - 44)
    p = out_dir / "slide_1.png"
    cv.save(p)
    paths.append(p)

    # Resto de diapositivas: 10 filas cada una
    for n, chunk in enumerate(chunks, start=2):
        cv = Canvas(W, H, cfg["colors"]["bg"])
        draw_header(cv, cfg, M, 120, date_label, right_text=f"{n}/{n_slides}", right_x=W - M)
        start = 11 + (n - 2) * 10
        draw_rows(cv, cfg, chunk, start, total, M, W - M, 245, 88, 10, 40, 42)
        footer(cv, cfg, H - 44)
        p = out_dir / f"slide_{n}.png"
        cv.save(p)
        paths.append(p)
    return paths


def render_story(cfg, ranking, date_label, out_path):
    W, H, M = 1080, 1920, 50
    total = len(ranking)
    cv = Canvas(W, H, cfg["colors"]["bg"])
    draw_header(cv, cfg, M, 285, date_label)
    draw_podium(cv, cfg, ranking[:3], M, W - M, 760, (200, 140, 100), (78, 56, 38, 30))
    rows = ranking[3:]
    left = math.ceil(len(rows) / 2)
    colw, gap = (W - 2 * M - 24) / 2, 24
    row_h, rgap, y0 = 56, 6, 790
    draw_rows(cv, cfg, rows[:left], 4, total, M, M + colw, y0, row_h, rgap, 27, 28)
    draw_rows(cv, cfg, rows[left:], 4 + left, total, M + colw + gap, W - M, y0, row_h, rgap, 27, 28)
    footer(cv, cfg, 1700, size=28)
    cv.save(out_path)
    return out_path
