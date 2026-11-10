"""halo_harness.studio.modes -- the words `halo studio --mode`, `/studio <word>` and a page's `?mode=` take (Halo
3.3.13.0 R2): a core section (studio/server.py STUDIO_MODES) or a section of a pack that runs here, `<pack id>--<section
id>` (`design--design`, the design pack's). A word a core section had before it went to a pack (`design`) answers one
line naming the pack and how to turn it on.

    known(word)                          a core word or the shape of a pack section's (no lookup: building a URL)
    check(word, cwd=, state_dir=)        (word, '') when it opens something here, else (None, the line)
    moved_line(word)                     the line for a word that went to a pack
    door_line(word)                      3.3.16.0 R1: the line for roles, orchestra or team, now Agents' views
                                         (studio/agents_door.py); they still open (Agents lands them)
"""

from __future__ import annotations

import re
from typing import Optional

from halo_harness.studio.agents_door import door_line  # noqa: F401  (re-exported: halo studio --mode, /studio)

PACK_MODE_RE = re.compile(r"^[a-z][a-z0-9-]*--[A-Za-z0-9][A-Za-z0-9_-]*$")
#: A core section that became a pack's (3.3.13.0 R2): the word -> (the pack's id, the pack's section).
MOVED = {"design": ("design", "design--design")}


def _core() -> tuple:
    from halo_harness.studio.server import STUDIO_MODES
    return STUDIO_MODES


def known(word: Optional[str]) -> bool:
    return bool(word) and (word in _core() or bool(PACK_MODE_RE.match(str(word))))


def moved_line(word: str) -> str:
    pack, section = MOVED[word]
    return (f"the {word.title()} section is the {pack} pack now: halo pack install {pack}, then halo pack enable {pack} "
            f"--grant-all, and /{word} (or halo studio --mode {section}) opens it")


def pack_sections(cwd=None, state_dir=None) -> "list[str]":
    try:
        from halo_harness.packs.studio_registry import section_heads
        return [h["id"] for h in section_heads(cwd=cwd, state_dir=state_dir)]
    except Exception:
        return []


def check(word: Optional[str], *, cwd=None, state_dir=None) -> "tuple[Optional[str], str]":
    w = str(word or "").strip()
    if w.lower() in _core():
        return w.lower(), ""
    if w.lower() in MOVED:
        here = MOVED[w.lower()][1]
        return (here, "") if here in pack_sections(cwd, state_dir) else (None, moved_line(w.lower()))
    if PACK_MODE_RE.match(w):
        if w in pack_sections(cwd, state_dir):
            return w, ""
        return None, (f"{w!r} is not a section of a pack that runs here (halo pack list; a pack's sections show "
                      "once it is enabled)")
    from halo_harness.studio.server import STUDIO_SECTIONS
    have = list(STUDIO_SECTIONS) + pack_sections(cwd, state_dir)
    return None, f"{w!r} is not a Studio section: use one of {', '.join(have)}"
