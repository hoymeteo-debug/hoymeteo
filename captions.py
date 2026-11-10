"""Textos (copys) para Instagram: titular, 5 primeros con hashtag de municipio,
bloque fijo de la cuenta y fuente."""
import config

KEYCAPS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]


def fecha_larga(d):
    return f"{config.DIAS[d.weekday()]} {d.day} de {config.MESES[d.month - 1]}"


def fecha_corta(d):
    return f"{config.DIAS[d.weekday()][:3].upper()} {d.day} {config.MESES[d.month - 1][:3].upper()}"


def format_value(cfg, value):
    num, unit = cfg["parts"](value)
    return num + unit


def build_caption(cfg, ranking, date):
    top = ranking[0]
    lines = [cfg["headline"].format(name=top["name"], value=format_value(cfg, top["value"])), ""]
    lines.append(cfg["ranking_line"].format(fecha=fecha_larga(date)))
    for i, item in enumerate(ranking[:5]):
        extra = f" ({item['detail']})" if item.get("detail") else ""
        lines.append(f"{KEYCAPS[i]} {item['hashtag']} {format_value(cfg, item['value'])}{extra}")
    lines += [
        "",
        f"➡️ Desliza para ver el ranking completo (top {len(ranking)}).",
        "",
        f"📍 Cada mañana, el tiempo de hoy en España para tomártelo con el café. "
        f"Sigue {config.HANDLE} y no te pierdas ninguno.",
        "Fuente: AEMET",
        "",
        cfg["hashtags"],
    ]
    return "\n".join(lines)
