"""halo_harness.themes.cli -- the words `/theme`, `halo config set theme` and Studio's settings route say about a
theme (Halo 3.3.12.0 R1): the listing of the ten and the one-line answer for a name the registry does not know."""

from __future__ import annotations

from typing import Optional

from halo_harness.themes import registry


def ten_words() -> str:
    """`claude-dark, claude-light, holo, ...; each also as <id>-daltonized or <id>-ansi`."""
    return ", ".join(registry.ids()) + "; each also as <id>-daltonized or <id>-ansi"


def refusal(name) -> str:
    """One line: the name is not a palette, the ten named (plus the removed-game-theme note when it was one)."""
    from halo_harness.theme import removed_theme_hint
    return f"not a valid theme name: {name!r} (the palettes: {ten_words()})" + removed_theme_hint(name)


def listing(current: Optional[str]) -> str:
    """`/theme` with no argument: the current theme, then the ten, one line each (id, posture, label), the current
    palette marked, then how the modifiers and a change work."""
    base, mod = registry.split(current)
    width = max(len(pid) for pid in registry.ids())
    lines = [f"Current theme: {current}" if current else "Current theme: none saved (the terminal's default)"]
    for pid in registry.ids():
        mark = "*" if pid == base else " "
        p = registry.palette(pid)
        lines.append(f" {mark} {pid.ljust(width)}  {p['posture']:<5}  {p['label']}")
    lines.append("Modifiers: <id>-daltonized (blue and orange, never red against green), "
                 "<id>-ansi (16 colours)" + (f"; on now: -{mod}" if mod else ""))
    lines.append("/theme <name> sets it for the terminal and Studio (theme in ~/.halo/config.json).")
    return "\n".join(lines)
