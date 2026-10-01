"""Paletas e preferência de tema do clinews."""

from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_THEME = "Midnight"

# Vampire usa Dracula; Midnight usa Night Owl. Os demais são paletas do clinews.
THEMES: dict[str, dict[str, str]] = {
    "Vampire": dict(bg="#282A36", fg="#F8F8F2", surface="#44475A", muted="#A3ACC7",
                    accent="#BD93F9", accent2="#FF79C6", selection="#44475A",
                    selected_fg="#F8F8F2", unread="#50FA7B", link="#8BE9FD",
                    logo_border="#BD93F9", logo_paper="#F8F8F2", logo_cyan="#8BE9FD", logo_rss="#FF79C6"),
    "NeoTokio": dict(bg="#0B061A", fg="#F5F3FF", surface="#24113B", muted="#B0A4CA",
                      accent="#FF2A6D", accent2="#4DEEEA", selection="#612268",
                      selected_fg="#FFFFFF", unread="#F8E16C", link="#4DEEEA",
                      logo_border="#FF2A6D", logo_paper="#FFFFFF", logo_cyan="#4DEEEA", logo_rss="#F8E16C"),
    "OldCity": dict(bg="#211B16", fg="#E8D7B0", surface="#3C3025", muted="#B5A181",
                     accent="#C88B3A", accent2="#A5693F", selection="#5A4230",
                     selected_fg="#FFF3D4", unread="#D7B56D", link="#E4B973",
                     logo_border="#9D6339", logo_paper="#E8D7B0", logo_cyan="#B98850", logo_rss="#D7B56D"),
    "FullDark": dict(bg="#000000", fg="#A9EFB5", surface="#07150B", muted="#82A88A",
                      accent="#00FF66", accent2="#AAFF55", selection="#0C3B1D",
                      selected_fg="#E7FFEA", unread="#00FF66", link="#70FF9B",
                      logo_border="#00BB4C", logo_paper="#D8FFE0", logo_cyan="#70FF9B", logo_rss="#AAFF55"),
    "SunMode": dict(bg="#FAFAF7", fg="#202A31", surface="#E9EDEB", muted="#5C686D",
                     accent="#176A72", accent2="#C48239", selection="#CFE9E9",
                     selected_fg="#10262A", unread="#137048", link="#0B6675",
                     logo_border="#176A72", logo_paper="#FFFFFF", logo_cyan="#36A6B2", logo_rss="#C48239"),
    "Midnight": dict(bg="#011627", fg="#D6DEEB", surface="#0B2942", muted="#89A4BB",
                     accent="#82AAFF", accent2="#C792EA", selection="#234D70",
                     selected_fg="#FFFFFF", unread="#22DA6E", link="#7FDBCA",
                     logo_border="#82AAFF", logo_paper="#D6DEEB", logo_cyan="#7FDBCA", logo_rss="#C792EA"),
    "Zenmode": dict(bg="#EFF9F1", fg="#1B4035", surface="#DDEEE1", muted="#537866",
                    accent="#388B69", accent2="#7CBAA2", selection="#BFDFC9",
                    selected_fg="#173C32", unread="#26805C", link="#287E69",
                    logo_border="#388B69", logo_paper="#FFFFFF", logo_cyan="#7CBAA2", logo_rss="#71AE80"),
}


def config_path() -> Path:
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
