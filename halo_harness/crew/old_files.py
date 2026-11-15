"""halo_harness.crew.old_files -- the old files' one line, once (Halo 3.6.0.0 R5, docs/CREW.md "Old files").

Halo no longer reads the old lineups, bios and workflow squares (`~/.halo/teams`, `~/.halo/workflows`, `~/.halo/agents`
and a project's `.halo/teams`, `.halo/workflows`, `.halo/agents`). They stay on disk exactly as they are: nothing here
deletes, moves, converts or rewrites a file of yours.

    found(cwd, state_dir) -> (folders, count)   the old folders that hold files, and how many files
    line(cwd, state_dir) -> str                 the one line ("" when there is nothing old)
    once(cwd, state_dir) -> str                 the line the first time only (the terminal at the first start, the
                                                Attention row's first showing); "" after, and when there is nothing
    said(state_dir, who) / mark(state_dir, who) whether the line was said in the terminal (`terminal`) or set aside
                                                in Studio's Attention (`studio`: live/crew_attention.py `crew_old`)

`halo doctor` repeats the line while the folders hold files (doctor_crew.py).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

KINDS = ("teams", "workflows", "agents")
MARKS = {"terminal": ".old-files-said", "studio": ".old-files-set-aside"}
FILES = ("*.yaml", "*.yml", "*.md", "*.json")


def _home(state_dir=None) -> Path:
    if state_dir is not None:
        return Path(state_dir)
    from halo_harness.providers.config import default_state_dir
    return Path(default_state_dir())


def _count(folder: Path) -> int:
    try:
        return sum(1 for pat in FILES for p in folder.rglob(pat) if p.is_file())
    except OSError:
        return 0


def found(cwd=None, state_dir=None) -> "tuple[list, int]":
    home = _home(state_dir)
    places = [(home / k, f"~/.halo/{k}") for k in KINDS]
    if cwd is not None:
        proj = Path(cwd) / ".halo"
        if proj.resolve() != home.resolve():
            places += [(proj / k, f".halo/{k}") for k in KINDS]
    folders, total = [], 0
    for path, label in places:
        n = _count(path) if path.is_dir() else 0
        if n:
            folders.append(label)
            total += n
    return folders, total


def line(cwd=None, state_dir=None) -> str:
    folders, n = found(cwd, state_dir)
    if not folders:
        return ""
    mine = [f for f in folders if f.startswith("~")]
    proj = [f for f in folders if not f.startswith("~")]
    where = ", ".join(mine) + (" and this project's " + ", ".join(proj) if proj else "")
    if not mine:
        where = "this project's " + ", ".join(proj)
    return (f"Halo no longer uses {where} ({n} file{'' if n == 1 else 's'}). They are still there; the new ones live in "
            "~/.halo/crew/ (Studio: Agents -> 1 Agents, 2 Workflows, 3 Map).")


def said(state_dir=None, who: str = "terminal") -> bool:
    return (_home(state_dir) / "crew" / MARKS[who]).is_file()


def mark(state_dir=None, who: str = "terminal") -> None:
    p = _home(state_dir) / "crew" / MARKS[who]
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("1\n", encoding="utf-8")
    except OSError:
        pass


def once(cwd=None, state_dir=None) -> str:
    if said(state_dir):
        return ""
    text = line(cwd, state_dir)
    if text:
        mark(state_dir)
    return text


def terminal_once(cwd=None, state_dir=None, out=None) -> Optional[str]:
    """The terminal's first start: the line on stderr, once. Never raises."""
    import sys
    try:
        text = once(cwd, state_dir)
    except Exception:
        return None
    if text:
        print(f"halo: {text}", file=out or sys.stderr)
    return text or None
