"""halo_harness.crew.old_files -- the old files' one line, once (Halo 3.6.0.0 R5, docs/CREW.md "Old files").

Halo no longer reads the old lineups, bios and workflow squares (`~/.halo/teams`, `~/.halo/workflows`, `~/.halo/agents`
and a project's `.halo/teams`, `.halo/workflows`, `.halo/agents`). They stay on disk exactly as they are: nothing here
deletes, moves, converts or rewrites a file of yours.

    found(cwd, state_dir) -> (folders, count)   the old folders that hold files of the user's, and how many (a file
                                                Halo itself copied there, unchanged, is not counted: `stock`)
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
SHIPPED = Path(__file__).resolve().parent.parent / "templates"
_STOCK: dict = {}  # path -> (size, mtime_ns, is Halo's own copy): a file is read again only when it changed


def _home(state_dir=None) -> Path:
    if state_dir is not None:
        return Path(state_dir)
    from halo_harness.providers.config import default_state_dir
    return Path(default_state_dir())


def _bytes(p: Path) -> bytes:
    return p.read_bytes().replace(b"\r\n", b"\n")


def stock(p: Path, kind: str) -> bool:
    """3.6.0.0 R5 fix: a file Halo itself copied there (a shipped lineup, bio or square, unchanged: the same bytes as
    the shipped file of its name, line ends aside) -- not the user's, so never named as theirs."""
    try:
        st = p.stat()
        key = (st.st_size, st.st_mtime_ns)
        hit = _STOCK.get(str(p))
        if hit is not None and hit[:2] == key:
            return hit[2]
        twin = SHIPPED / kind / p.name
        same = twin.is_file() and _bytes(twin) == _bytes(p)
        _STOCK[str(p)] = (*key, same)
        return same
    except OSError:
        return False


def _count(folder: Path, kind: str) -> int:
    try:
        return sum(1 for pat in FILES for p in folder.rglob(pat) if p.is_file() and not stock(p, kind))
    except OSError:
        return 0


def team_line() -> str:
    """A configured `team:` no session reads any more: named, and what to do, in one line ("" when none is set)."""
    try:
        from halo_harness.theme import get_config_value
        team = get_config_value("team", default=None)
    except Exception:
        return ""
    if not (isinstance(team, str) and team.strip()):
        return ""
    return (f"Your config sets team: {team.strip()}, which no session reads any more (lineups are gone): pick a map with "
            "halo maps use <name>, and clear the old key with halo config set team null.")


def found(cwd=None, state_dir=None) -> "tuple[list, int]":
    home = _home(state_dir)
    places = [(home / k, f"~/.halo/{k}") for k in KINDS]
    if cwd is not None:
        proj = Path(cwd) / ".halo"
        if proj.resolve() != home.resolve():
            places += [(proj / k, f".halo/{k}") for k in KINDS]
    folders, total = [], 0
    for path, label in places:
        n = _count(path, label.rsplit("/", 1)[-1]) if path.is_dir() else 0
        if n:
            folders.append(label)
            total += n
    return folders, total


def line(cwd=None, state_dir=None) -> str:
    """The files the user wrote or changed in the old folders, and a configured `team:` now ignored; "" for neither."""
    folders, n = found(cwd, state_dir)
    team = team_line()
    if not folders:
        return team
    mine = [f for f in folders if f.startswith("~")]
    proj = [f for f in folders if not f.startswith("~")]
    where = ", ".join(mine) + (" and this project's " + ", ".join(proj) if proj else "")
    if not mine:
        where = "this project's " + ", ".join(proj)
    return (f"Halo no longer uses {where} ({n} file{'' if n == 1 else 's'} of yours). They are still there; the new ones "
            "live in ~/.halo/crew/ (Studio: Agents -> 1 Agents, 2 Workflows, 3 Map)." + (f" {team}" if team else ""))


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
