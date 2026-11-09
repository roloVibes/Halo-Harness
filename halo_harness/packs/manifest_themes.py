"""halo_harness.packs.manifest_themes -- a pack's `contributes.themes`: its own palettes (Halo 3.3.12.0 R2;
docs/EXTENSION_API.md "Themes", stable in API 1.1).

    contributes:
      themes:
        - id: nightshade                 # lower-case letters, digits and -; not a core palette's id
          label: Violet night, a green second accent
          posture: dark                  # dark | light
          palette: {bg: "#0d0b14", bg2: "#120f1c", ...}   # every token of halo_harness/themes/palettes.py TOKENS

A palette registers like one of the core palettes while its pack is enabled, as `<pack-id>/<id>` (halo_harness/themes/packs.py),
with the `-daltonized` and `-ansi` modifiers derived the same way. It must meet the same WCAG AA pins the core palettes meet
(themes/registry.py PAIRS), its -daltonized variant included.

    themes_of(manifest)        the entries (mappings only)
    theme_name(pack_id, id)    "<pack-id>/<id>"
    theme_lines(data)          one line per problem, each naming the entry
"""

from __future__ import annotations

import re

THEME_KEYS = ("id", "label", "posture", "palette")
POSTURES = ("dark", "light")
THEME_ID = re.compile(r"^[a-z][a-z0-9-]*$")
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
SEP = "/"


def _contributes(manifest) -> dict:
    c = manifest.get("contributes") if isinstance(manifest, dict) else None
    return c if isinstance(c, dict) else {}


def themes_of(manifest) -> "list[dict]":
    raw = _contributes(manifest).get("themes")
    return [e for e in raw if isinstance(e, dict)] if isinstance(raw, list) else []


def theme_name(pack_id: str, theme_id: str) -> str:
    return f"{pack_id}{SEP}{theme_id}"


def _id_lines(entries) -> "list[str]":
    from halo_harness.themes.palettes import MODIFIERS, PALETTES
    core = {p["id"] for p in PALETTES}
    out, seen = [], set()
    for i, e in enumerate(entries):
        tid, where = e.get("id"), f"contributes.themes[{i}].id"
        if not isinstance(tid, str) or not tid:
            out.append(f"{where}: required (lower-case letters, digits and -)")
        elif not THEME_ID.match(tid):
            out.append(f"{where} {tid!r} is not a palette id (lower-case letters, digits and -, a letter first)")
        elif tid in core:
            out.append(f"{where} {tid!r} is a core palette's id; pick another (the core palettes: {', '.join(sorted(core))})")
        elif any(tid.endswith(f"-{m}") for m in MODIFIERS):
            out.append(f"{where} {tid!r} ends in a modifier (-{', -'.join(MODIFIERS)}); pick another")
        elif tid in seen:
            out.append(f"{where} {tid!r} is used twice")
        else:
            seen.add(tid)
    return out


def _palette_lines(where: str, palette) -> "tuple[list[str], bool]":
    """(lines, every token there and a colour)."""
    from halo_harness.themes.palettes import TOKEN_NAMES
    if not isinstance(palette, dict):
        return [f"{where}: required, a mapping of every token to a #rrggbb colour ({', '.join(TOKEN_NAMES)})"], False
    out = []
    missing = [t for t in TOKEN_NAMES if t not in palette]
    extra = [str(k) for k in palette if k not in TOKEN_NAMES]
    if missing:
        out.append(f"{where}: missing {', '.join(missing)} (a palette names every token)")
    if extra:
        out.append(f"{where}: {', '.join(extra)} {'is not a token' if len(extra) == 1 else 'are not tokens'} "
                   f"(the tokens: {', '.join(TOKEN_NAMES)})")
    bad = [t for t in TOKEN_NAMES if t in palette and not (isinstance(palette[t], str) and HEX.match(palette[t]))]
    out += [f"{where}.{t}: {palette[t]!r} is not a #rrggbb colour" for t in bad]
    return out, not missing and not bad


def contrast_lines(where: str, tokens: dict, posture: str) -> "list[str]":
    """One line per pinned pair under its WCAG AA floor, the palette's own and its -daltonized variant's."""
    from halo_harness.themes import registry
    norm = {k: v.lower() for k, v in tokens.items()}
    out = []
    for label, t in (("", norm), (" (its -daltonized variant)", registry.daltonize(norm, posture))):
        for fg, bg, floor in registry.PAIRS:
            ratio = registry.contrast(t[fg], t[bg])
            if ratio < floor:
                out.append(f"{where}: {fg} on {bg}{label} reads {ratio:.2f}:1, under WCAG AA's {floor:g}:1 "
                           f"({t[fg]} on {t[bg]})")
    return out


def theme_lines(data) -> "list[str]":
    """One line per problem in `contributes.themes`; [] for a pack without it."""
    c = _contributes(data)
    if "themes" not in c:
        return []
    if not isinstance(c["themes"], list):
        return ["contributes.themes: a list of palettes ({id, label, posture: dark | light, palette})"]
    entries = themes_of(data)
    out = [f"contributes.themes[{i}]: a palette is a mapping ({{id, label, posture, palette}})"
           for i, e in enumerate(c["themes"]) if not isinstance(e, dict)]
    out += _id_lines(entries)
    for i, e in enumerate(entries):
        where = f"contributes.themes[{i}]"
        label = e.get("label")
        if not (isinstance(label, str) and label.strip()):
            out.append(f"{where}.label: required (the line a person reads beside the palette)")
        posture = e.get("posture")
        if posture not in POSTURES:
            out.append(f"{where}.posture {posture!r} is not one of {', '.join(POSTURES)}")
        lines, whole = _palette_lines(f"{where}.palette", e.get("palette"))
        out += lines
        if whole and posture in POSTURES:
            out += contrast_lines(f"{where}.palette", e["palette"], posture)
    return out


def palettes(pack_id: str, manifest) -> "list[dict]":
    """The pack's good palettes as registry entries: {id: "<pack>/<id>", local_id, pack, label, posture, tokens}.
    A pack with a problem never runs (packs/registry.py), so an entry here has every token."""
    from halo_harness.themes.palettes import TOKEN_NAMES
    out = []
    for e in themes_of(manifest):
        pal = e.get("palette")
        if not (isinstance(e.get("id"), str) and isinstance(pal, dict) and e.get("posture") in POSTURES):
            continue
        if not all(isinstance(pal.get(t), str) and HEX.match(pal[t]) for t in TOKEN_NAMES):
            continue
        out.append({"id": theme_name(pack_id, e["id"]), "local_id": e["id"], "pack": pack_id,
                    "label": str(e.get("label") or e["id"]), "posture": e["posture"],
                    "tokens": {t: pal[t].lower() for t in TOKEN_NAMES}})
    return out
