"""halo_harness.themes.cli -- the words `/theme`, `halo config set theme` and Studio's settings route say about a
theme (Halo 3.3.12.0 R1): the listing of the eleven and the one-line answer for a name the registry does not know.
R2: an enabled pack's palettes are listed under the pack's name, by their `<pack-id>/<id>` names."""

from __future__ import annotations

from typing import Optional

from halo_harness.themes import registry


def ten_words() -> str:
    """`claude-dark, claude-light, holo, ...; each also as <id>-daltonized or <id>-ansi`."""
    return ", ".join(registry.ids()) + "; each also as <id>-daltonized or <id>-ansi"


def pack_words() -> str:
    """`; from packs: pack-theme/nightshade, pack-theme/linen` ("" with no pack palette)."""
    names = registry.pack_ids()
    return f"; from packs: {', '.join(names)}" if names else ""


def refusal(name) -> str:
    """One line: the name is not a palette, the eleven named (plus the removed-game-theme note when it was one)."""
    from halo_harness.theme import removed_theme_hint
    return (f"not a valid theme name: {name!r} (the palettes: {ten_words()}{pack_words()}; auto follows the system)"
            + removed_theme_hint(name))


def listing(current: Optional[str]) -> str:
    """`/theme` with no argument: the current theme, then the eleven, one line each (id, posture, label), the current
    palette marked, then how the modifiers and a change work."""
    base, mod = registry.split(current)
    width = max(len(pid) for pid in registry.all_ids())
    lines = [f"Current theme: {current}" if current else f"Current theme: none saved (Halo's default, {registry.DEFAULT})"]
    shown = ""
    for pid in registry.all_ids():
        mark = "*" if pid == base else " "
        p = registry.palette(pid)
        if p.get("pack") and p["pack"] != shown:  # 3.3.12.0 R2: a pack's palettes under its name
            shown = p["pack"]
            lines.append(f"From the pack {shown}" + (f" ({p['pack_name']})" if p.get("pack_name", shown) != shown else "") + ":")
        lines.append(f" {mark} {pid.ljust(width)}  {p['posture']:<5}  {p['label']}")
    lines.append("Modifiers: <id>-daltonized (blue and orange, never red against green), "
                 "<id>-ansi (16 colours)" + (f"; on now: -{mod}" if mod else ""))
    lines.append("/theme <name> sets it for the terminal and Studio (theme in ~/.halo/config.json); /theme auto follows "
                 f"the system (Studio: {registry.FOLLOW_DARK} on dark, {registry.FOLLOW_LIGHT} on light); unset is {registry.DEFAULT}.")
    return "\n".join(lines)
