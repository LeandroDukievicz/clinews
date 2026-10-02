"""Paletas e preferência de tema do clinews."""

from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_THEME = "Midnight"

# As paletas do WatchAI descrevem 16 cores por tema; o clinews usa dez papéis.
# A correspondência entre os dois é fixa, e é ela que mantém os temas iguais
# nos dois aplicativos:
#
#     bg -> bg          text -> fg        bg2 -> surface     muted -> muted
#     cyan -> accent    cyan -> selection (com bg em selected_fg, como realce)
#     magenta -> accent2    green -> unread    cyan2 -> link
#
# `cyan` é o acento do WatchAI (seleção, títulos, teclas) e `green` marca o
# estado "pronto", que aqui vira a notícia não lida. Toda cor foi conferida em
# contraste de 4,5:1 contra o fundo em que aparece (test_readable_theme_contrast).
THEMES: dict[str, dict[str, str]] = {
    "NeoTokio": dict(bg="#020624", fg="#8BEFFD", surface="#0A123B", muted="#8AB9C4",
                      accent="#FF5BD6", accent2="#45E7F5", selection="#D83CB5",
                      selected_fg="#020624", unread="#FF5BD6", link="#45E7F5"),
    "OldCity": dict(bg="#211B16", fg="#E8D7B0", surface="#3C3025", muted="#B5A181",
                     accent="#C88B3A", accent2="#A5693F", selection="#5A4230",
                     selected_fg="#FFF3D4", unread="#D7B56D", link="#E4B973"),
    "FullDark": dict(bg="#000000", fg="#A9EFB5", surface="#07150B", muted="#82A88A",
                      accent="#00FF66", accent2="#AAFF55", selection="#0C3B1D",
                      selected_fg="#E7FFEA", unread="#00FF66", link="#70FF9B"),
    "SunMode": dict(bg="#FAFAF7", fg="#202A31", surface="#E9EDEB", muted="#5C686D",
                     accent="#176A72", accent2="#C48239", selection="#CFE9E9",
                     selected_fg="#10262A", unread="#137048", link="#0B6675"),
    "Midnight": dict(bg="#150e2e", fg="#91ebe8", surface="#251445", muted="#89A4BB",
                     accent="#82AAFF", accent2="#C792EA", selection="#3A275D",
                     selected_fg="#FFFFFF", unread="#22DA6E", link="#7FDBCA"),
    "Zenmode": dict(bg="#003d31", fg="#00b3ff", surface="#004639", muted="#9EDCD6",
                    accent="#6EE7FF", accent2="#7AF0C5", selection="#00B3FF",
                    selected_fg="#002B23", unread="#62E6A7", link="#67D5FF"),

    # -- as oito paletas do WatchAI ------------------------------------------
    "WatchAI": dict(bg="#05070D", fg="#D8E2F0", surface="#080D16", muted="#7C8799",
                    accent="#00E5FF", accent2="#FF2BD6", selection="#00E5FF",
                    selected_fg="#05070D", unread="#00FF85", link="#00AFC8"),
    "Light": dict(bg="#FBFCFD", fg="#1F2328", surface="#EFF2F6", muted="#656D76",
                  accent="#0A7C8A", accent2="#A626A4", selection="#0A7C8A",
                  selected_fg="#FBFCFD", unread="#1A7F37", link="#0E5D67"),
    "Dark": dict(bg="#0D1117", fg="#E6EDF3", surface="#161B22", muted="#8B949E",
                 accent="#56B6C2", accent2="#C678DD", selection="#56B6C2",
                 selected_fg="#0D1117", unread="#56D364", link="#3E8A94"),
    "Night Owl": dict(bg="#011627", fg="#D6DEEB", surface="#0B2942", muted="#8BA1B3",
                      accent="#7FDBCA", accent2="#C792EA", selection="#7FDBCA",
                      selected_fg="#011627", unread="#ADDB67", link="#21C7A8"),
    "Vampire": dict(bg="#282A36", fg="#F8F8F2", surface="#21222C", muted="#9AA0BF",
                    accent="#8BE9FD", accent2="#FF79C6", selection="#8BE9FD",
                    selected_fg="#282A36", unread="#50FA7B", link="#BD93F9"),
    "Cyberpunk": dict(bg="#05010A", fg="#F2E9FF", surface="#0D0418", muted="#9A86BC",
                      accent="#00F0FF", accent2="#FF00A0", selection="#00F0FF",
                      selected_fg="#05010A", unread="#00FF9F", link="#00B8C4"),
    "Steampunk": dict(bg="#140F0A", fg="#EFE2CC", surface="#1F1811", muted="#9A876C",
                      accent="#7FB2A1", accent2="#C9762F", selection="#7FB2A1",
                      selected_fg="#140F0A", unread="#9FB055", link="#5A8A7C"),
    # Sem matiz: os estados se separam por brilho. O `cyan2` do WatchAI (#7A7A7A)
    # ficaria em 4,5:1 raspando o limite, então o link usa o texto secundário.
    "Grey": dict(bg="#0E0E0E", fg="#E8E8E8", surface="#171717", muted="#8C8C8C",
                 accent="#9C9C9C", accent2="#C2C2C2", selection="#9C9C9C",
                 selected_fg="#0E0E0E", unread="#DADADA", link="#BDBDBD"),
}


def config_path() -> Path:
    if snap_data := os.environ.get("SNAP_USER_COMMON"):
        return Path(snap_data) / "config" / "config.json"
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "clinews" / "config.json"


def load_theme(path: Path | None = None) -> str:
    try:
        name = json.loads((path or config_path()).read_text(encoding="utf-8")).get("theme")
        return name if name in THEMES else DEFAULT_THEME
    except (OSError, ValueError, AttributeError):
        return DEFAULT_THEME


def save_theme(name: str, path: Path | None = None) -> None:
    if name not in THEMES:
        raise ValueError(f"Tema desconhecido: {name}")
    target = path or config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps({"theme": name}, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(target)


def nearest_xterm(hex_color: str) -> int:
    """Aproxima RGB à paleta xterm de 256 cores, sem alterar o terminal."""
    rgb = tuple(int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    levels = (0, 95, 135, 175, 215, 255)
    candidates = [(16 + 36 * r + 6 * g + b, (levels[r], levels[g], levels[b]))
                  for r in range(6) for g in range(6) for b in range(6)]
    candidates.extend((232 + n, (8 + 10 * n,) * 3) for n in range(24))
    return min(candidates, key=lambda item: sum((a - b) ** 2 for a, b in zip(rgb, item[1])))[0]


# Onde a aproximação de 256 cores perde o desenho do tema: fundos coloridos que
# viram cinza, ou dois papéis que caem na mesma cor e apagam a diferença entre
# eles. O Grey é o caso do segundo tipo — fundo e superfície aproximam no mesmo
# 233, e o cabeçalho sumiria no fundo.
XTERM_OVERRIDES: dict[str, dict[str, int]] = {
    "Midnight": {"bg": 53, "surface": 54, "selection": 60},
    "NeoTokio": {"bg": 17, "surface": 18},
    "Zenmode": {"bg": 23, "fg": 81},
    "Grey": {"surface": 234},
}


def xterm_theme_color(name: str, role: str) -> int:
    """Preserva fundos escuros e contraste dos temas na paleta xterm."""
    if (override := XTERM_OVERRIDES.get(name, {}).get(role)) is not None:
        return override
    return nearest_xterm(THEMES[name][role])


def basic_color(hex_color: str) -> int:
    """Fallback RGB para ANSI de 8 cores."""
    import curses
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    if max(r, g, b) < 55:
        return curses.COLOR_BLACK
    if min(r, g, b) > 190:
        return curses.COLOR_WHITE
    if max(r, g, b) - min(r, g, b) < 35:
        return curses.COLOR_WHITE if max(r, g, b) > 120 else curses.COLOR_BLACK
    return ((curses.COLOR_RED if r > 90 else 0) |
            (curses.COLOR_GREEN if g > 90 else 0) |
            (curses.COLOR_BLUE if b > 90 else 0))
