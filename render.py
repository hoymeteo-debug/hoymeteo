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
        self.bg = bg
        self.img = Image.new("RGB", (w * S, h * S), rgb(bg))
        self.d = ImageDraw.Draw(self.img)
        self.boxes = []  # elementos para animar el vídeo: (tipo, orden, caja)

    def mark(self, kind, x0, y0, x1, y1, order=0):
        """Anota un elemento (en px finales) para animarlo luego en el vídeo de la story."""
        self.boxes.append({"kind": kind, "order": order,
                           "box": [max(0, int(x0)), max(0, int(y0)), min(self.w, int(x1 + 1)), min(self.h, int(y1 + 1))]})

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

    def save_layout(self, path):
        """Guarda junto a la imagen la posición de cada elemento (para video.py)."""
        import json
        Path(path).write_text(json.dumps({"size": [self.w, self.h], "bg": self.bg, "elements": self.boxes}), encoding="utf-8")


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
    elif kind == "bolt":
        pts = [(4, -30), (-16, 4), (-2, 4), (-6, 30), (16, -6), (2, -6), (8, -30)]
        cv.d.polygon([((cx + x * k) * S, (cy + y * k) * S) for x, y in pts], fill=rgb(fg))
    elif kind == "snow":
        for ang in (0, 60, 120):
            a = math.radians(ang)
            dx, dy = 26 * k * math.cos(a), 26 * k * math.sin(a)
            cv.line([(cx - dx, cy - dy), (cx + dx, cy + dy)], fg, 5 * k)
    elif kind == "wave":
        for dy in (-12, 10):
            for i in range(3):
                x = cx - 24 * k + i * 16 * k
                cv.arc(x + 8 * k, cy + dy * k, 8 * k, 180, 360, fg, 5 * k)
    elif kind == "fog":
        for i, dy in enumerate((-16, 0, 16)):
            off = 6 * k if i == 1 else 0
            cv.line([(cx - 26 * k + off, cy + dy * k), (cx + 26 * k - off, cy + dy * k)], fg, 6 * k)
    elif kind == "contrast":
        for x, up in ((cx - 13 * k, False), (cx + 13 * k, True)):
            y0, y1 = (cy - 24 * k, cy + 24 * k)
            cv.line([(x, y0), (x, y1)], fg, 6 * k)
            tip = y0 if up else y1
            d = 11 * k if up else -11 * k
            cv.line([(x - 10 * k, tip + d), (x, tip), (x + 10 * k, tip + d)], fg, 6 * k)
    elif kind == "check":
        cv.line([(cx - 20 * k, cy + 2 * k), (cx - 6 * k, cy + 16 * k), (cx + 22 * k, cy - 14 * k)], fg, 8 * k)
    elif kind == "alert":
        pts = [(0, -30), (30, 24), (-30, 24)]
        cv.d.polygon([((cx + x * k) * S, (cy + y * k) * S) for x, y in pts], fill=rgb(fg))
        cv.rect(cx - 3.5 * k, cy - 12 * k, cx + 3.5 * k, cy + 8 * k, circle_color, r=3 * k)
        cv.circle(cx, cy + 15 * k, 4 * k, circle_color)


# --- Bloques de diseño -----------------------------------------------------------------
def draw_header(cv, cfg, x, y_center, date_label, scale=1.0, right_text=None, right_x=None):
    c = cfg["colors"]
    r = 46 * scale
    draw_icon(cv, cfg["icon"], x + r, y_center, r, c["accent"])
    tx = x + 2 * r + 24 * scale
    eyebrow = cfg.get("eyebrow", "PREVISIÓN")
    cv.text(tx, y_center - 28 * scale, f"{eyebrow} · {date_label}", 24 * scale, c["label"], bold=True)
    cv.text(tx, y_center + 14 * scale, cfg["title"], 50 * scale, c["text"], bold=True)
    if cfg.get("subtitle"):
        cv.text(tx, y_center + 66 * scale, cfg["subtitle"], 26 * scale, c["label"])
    cv.mark("header", 0, y_center - r - 6, cv.w, y_center + (90 if cfg.get("subtitle") else r + 6) * scale)
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
    cv.mark("fade", x0, base_y, x1, base_y + 3, order=0)
    for slot, idx in enumerate(order):
        if idx >= len(top3):
            continue
        item = top3[idx]
        cx = x0 + slot * (colw + gap) + colw / 2
        h = heights[idx]
        top = base_y - h
        cv.rect(cx - colw / 2, top, cx + colw / 2, base_y, c["pillars"][idx], r=18, corners=(True, True, False, False))
        detail = item.get("detail_short")
        rank_y = top + h * (0.30 if detail else 0.42)
        cv.text(cx, rank_y, str(idx + 1), 84 if idx == 0 else 60, c["pillar_text"][idx], bold=True, anchor="mm")
        if detail:
            dsize = 22 if h >= 200 else 19
            for j, part in enumerate(detail.split(" · ")):
                cv.text(cx, rank_y + (64 if idx == 0 else 50) + j * dsize * 1.35, part, dsize, c["pillar_text"][idx], bold=True, anchor="mm")
        vsize = sizes[0] if idx == 0 else sizes[1]
        vbase = top - 22
        draw_value(cv, cx, vbase, cfg, item["value"], vsize, c["accent"])
        nsize = sizes[2] if idx == 0 else sizes[3]
        lines = cv.wrap(item["name"], nsize, colw - 8, bold=True, max_lines=2)
        ny = vbase - vsize - 16 - (len(lines) - 1) * nsize * 1.2
        for i, ln in enumerate(lines):
            cv.text(cx, ny + i * nsize * 1.2, ln, nsize, c["text"], bold=True, anchor="mm")
        cv.mark("rise", cx - colw / 2, ny - nsize, cx + colw / 2, base_y, order=3 - idx)


def draw_rows(cv, cfg, rows, start_rank, total, x0, x1, y0, row_h, gap, name_size, val_size):
    c = cfg["colors"]
    row_bg = mix(c["bg"], "#FFFFFF", 0.55)
    for i, item in enumerate(rows):
        rank = start_rank + i
        y = y0 + i * (row_h + gap)
        t = (rank - 1) / max(total - 1, 1)
        cv.rect(x0, y, x1, y + row_h, row_bg)
        cv.mark("row", x0, y, x1, y + row_h, order=rank)
        cv.rect(x0, y, x0 + 9, y + row_h, mix(c["strip_from"], c["strip_to"], t))
        cy = y + row_h / 2
        cv.text(x0 + 26, cy, str(rank), name_size * 0.85, c["label"], bold=True)
        num, unit = cfg["parts"](item["value"])
        val = num + unit
        vw = cv.width(val, val_size, True)
        cv.text(x1 - 16, cy, val, val_size, c["accent"], bold=True, anchor="rm")
        rank_w = 26 + cv.width(str(total), name_size * 0.85, True) + 20
        maxw = (x1 - x0) - rank_w - vw - 40
        if item.get("detail"):
            nsize, dsize = name_size * 0.86, name_size * 0.62
            name = cv.fit(item["name"], nsize, maxw)
            cv.text(x0 + rank_w, cy - row_h * 0.19, name, nsize, c["text"])
            det = item["detail"] if cv.width(item["detail"], dsize) <= maxw else item["detail_short"]
            cv.text(x0 + rank_w, cy + row_h * 0.24, cv.fit(det, dsize, maxw), dsize, c["label"])
        else:
            name = cv.fit(item["name"], name_size, maxw)
            cv.text(x0 + rank_w, cy, name, name_size, c["text"])


def footer(cv, cfg, y, size=24):
    cv.text(cv.w / 2, y, f"Fuente: AEMET · {config.HANDLE}", size, cfg["colors"]["label"], bold=True, anchor="mm")
    cv.mark("footer", 0, y - size, cv.w, y + size)


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
    cv.save_layout(Path(out_path).with_suffix(".json"))
    return out_path


# --- Serie de avisos ---------------------------------------------------------------------
LEVEL_STYLE = {  # nivel -> (fondo, texto, nombre)
    3: ("#C62828", "#FFFFFF", "ROJO"),
    2: ("#EF6C00", "#FFFFFF", "NARANJA"),
    1: ("#F9C80E", "#3D2E00", "AMARILLO"),
}


def draw_level_tiles(cv, cfg, n_by_level, x0, x1, y0, h, num_size=72, label_size=24):
    """Resumen: una tarjeta por color con el número de avisos y su nombre."""
    gap = 20
    w = (x1 - x0 - 2 * gap) / 3
    labels = {3: ("rojo", "rojos"), 2: ("naranja", "naranjas"), 1: ("amarillo", "amarillos")}
    for i, lvl in enumerate((3, 2, 1)):
        bg, fg, _ = LEVEL_STYLE[lvl]
        n = n_by_level.get(lvl, 0)
        x = x0 + i * (w + gap)
        if n == 0:  # sin avisos de ese color: tarjeta apagada
            bg, fg = mix(cfg["colors"]["bg"], "#FFFFFF", 0.5), cfg["colors"]["label"]
        cv.rect(x, y0, x + w, y0 + h, bg, r=18)
        cv.mark("pop", x, y0, x + w, y0 + h, order=i)
        cv.text(x + w / 2, y0 + h * 0.42, str(n), num_size, fg, bold=True, anchor="mm")
        cv.text(x + w / 2, y0 + h * 0.80, labels[lvl][0 if n == 1 else 1].upper(), label_size, fg, bold=True, anchor="mm")


def draw_aviso_rows(cv, cfg, rows, x0, x1, y0, row_h, gap, name_size, sub_size, chip_w=150):
    c = cfg["colors"]
    row_bg = mix(c["bg"], "#FFFFFF", 0.6)
    for i, a in enumerate(rows):
        y = y0 + i * (row_h + gap)
        bg, fg, name = LEVEL_STYLE[a["level"]]
        cv.rect(x0, y, x1, y + row_h, row_bg, r=12)
        cv.mark("row", x0, y, x1, y + row_h, order=i + 1)
        cv.rect(x0, y, x0 + chip_w, y + row_h, bg, r=12, corners=(True, False, False, True))
        cy = y + row_h / 2
        cv.text(x0 + chip_w / 2, cy, name, sub_size * 0.92, fg, bold=True, anchor="mm")
        ir = row_h * 0.3
        icx = x0 + chip_w + 18 + ir
        draw_icon(cv, a["icon"], icx, cy, ir, c["text"])
        tx = icx + ir + 18
        maxw = x1 - tx - 16
        cv.text(tx, cy - row_h * 0.19, cv.fit(a["zone_name"], name_size, maxw, bold=True), name_size, c["text"], bold=True)
        sub = f"{a['region']} · {a['motivo']}"
        cv.text(tx, cy + row_h * 0.22, cv.fit(sub, sub_size, maxw), sub_size, c["label"])


def _no_avisos(cv, cfg, cy, size):
    cv.mark("pop", cv.w / 2 - size, cy - size, cv.w / 2 + size, cy + size)
    cv.mark("row", 0, cy + size + 40, cv.w, cy + size + 175, order=1)
    draw_icon(cv, "check", cv.w / 2, cy, size, "#2E7D32")
    cv.text(cv.w / 2, cy + size + 80, "Hoy no hay avisos", 64, cfg["colors"]["text"], bold=True, anchor="mm")
    cv.text(cv.w / 2, cy + size + 150, "meteorológicos en España", 40, cfg["colors"]["label"], anchor="mm")


def render_avisos_carousel(cfg, avisos, n_by_level, date_label, out_dir, max_slides=10):
    W, H, M = 1080, 1350, 64
    out_dir = Path(out_dir)
    if not avisos:
        cv = Canvas(W, H, cfg["colors"]["bg"])
        draw_header(cv, cfg, M, 120, date_label)
        _no_avisos(cv, cfg, 560, 120)
        footer(cv, cfg, H - 44)
        p = out_dir / "slide_1.png"
        cv.save(p)
        return [p]

    first, per = 8, 10
    rest = avisos[first:]
    # Reparto equilibrado (p. ej. 42 filas -> 9+9+8+8+8) para no dejar una última diapositiva casi vacía
    n_chunks = min(math.ceil(len(rest) / per), max_slides - 1) if rest else 0
    size = math.ceil(len(rest) / n_chunks) if n_chunks else per
    size = min(max(size, 1), per)
    chunks = [rest[i:i + size] for i in range(0, len(rest), size)][:n_chunks]
    shown = first + sum(len(ch) for ch in chunks)
    hidden = len(avisos) - shown
    n_slides = 1 + len(chunks)
    paths = []

    cv = Canvas(W, H, cfg["colors"]["bg"])
    draw_header(cv, cfg, M, 120, date_label, right_text=f"1/{n_slides}" if n_slides > 1 else None, right_x=W - M)
    draw_level_tiles(cv, cfg, n_by_level, M, W - M, 220, 170)
    draw_aviso_rows(cv, cfg, avisos[:first], M, W - M, 420, 92, 10, 32, 24)
    footer(cv, cfg, H - 44)
    p = out_dir / "slide_1.png"
    cv.save(p)
    paths.append(p)

    for n, chunk in enumerate(chunks, start=2):
        cv = Canvas(W, H, cfg["colors"]["bg"])
        draw_header(cv, cfg, M, 120, date_label, right_text=f"{n}/{n_slides}", right_x=W - M)
        draw_aviso_rows(cv, cfg, chunk, M, W - M, 230, 92, 10, 32, 24)
        if n == n_slides and hidden > 0:
            cv.text(W / 2, H - 100, f"y {hidden} avisos más en aemet.es", 30, cfg["colors"]["label"], bold=True, anchor="mm")
        footer(cv, cfg, H - 44)
        p = out_dir / f"slide_{n}.png"
        cv.save(p)
        paths.append(p)
    return paths


def render_avisos_story(cfg, avisos, n_by_level, date_label, out_path):
    W, H, M = 1080, 1920, 50
    cv = Canvas(W, H, cfg["colors"]["bg"])
    draw_header(cv, cfg, M, 300, date_label)
    if not avisos:
        _no_avisos(cv, cfg, 820, 140)
    else:
        draw_level_tiles(cv, cfg, n_by_level, M, W - M, 400, 150, num_size=64)
        max_rows = 12
        draw_aviso_rows(cv, cfg, avisos[:max_rows], M, W - M, 580, 74, 8, 28, 21, chip_w=136)
        if len(avisos) > max_rows:
            cv.text(W / 2, 1615, f"y {len(avisos) - max_rows} avisos más", 30, cfg["colors"]["label"], bold=True, anchor="mm")
            cv.mark("footer", 0, 1590, W, 1640)
    footer(cv, cfg, 1700, size=28)
    cv.save(out_path)
    cv.save_layout(Path(out_path).with_suffix(".json"))
    return out_path
