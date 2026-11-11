"""halo_harness.knowledge.rank -- what makes a finding or a decision a hit for some words (Halo 3.3.16.2, "from a
session's own review": a search for "halo harness update new features version" came back with gate records of
the guided first run's sample repo, because their titles carry the test command, whose python sits in the tool
venv `.../uv/tools/halo-harness/bin/python`, so "halo" and "harness" matched a path, and equal scores went to
the newest).

* `content_words(text)` -- the words a record says: paths, commands' file names and shas dropped, and the
  small words (`STOP`) too;
* `project_here(cwd)` -- the project a search is made from: the git root's folder name (else the folder's);
* `project_of(e)` -- a record's project (its `repo`; '' = written with no project, so it belongs to every one);
* `is_sample(e, state_dir)` -- a record of the guided first run's sample repo (`halo start`): tagged `sample`,
  or (before 3.3.16.2) a record whose project is a sample repo's folder under `<state>/start/<day>/`;
* `is_routine_gate(e)` -- a gate's "<unit> passes `<test>` at <sha>" finding (a failed gate is a decision);
* `names_unit(e, words)` -- the query names that gate's file or symbol;
* `dup_key(e)` -- the same gate on the same unit re-run: one key (the sha and the command dropped).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

STOP = frozenset(("a", "an", "and", "are", "as", "at", "be", "by", "do", "does", "for", "from", "has", "have", "how",
                  "in", "is", "it", "its", "me", "my", "of", "on", "or", "our", "so", "that", "the", "their", "this",
                  "to", "was", "we", "were", "what", "when", "where", "which", "who", "why", "with", "you", "your"))
SAMPLE_TAG = "sample"
_PATH = re.compile(r"[^\s`'\"()\[\]]*[/\\][^\s`'\"()\[\]]*")
_QUOTED = re.compile(r"`[^`]*`")
_SHA = re.compile(r"\b[0-9a-f]{7,40}\b")
_WORD = re.compile(r"[a-z0-9_]{2,}")


def content_words(text) -> set:
    text = _SHA.sub(" ", _PATH.sub(" ", str(text or "").lower()))
    return {w for w in _WORD.findall(text) if w not in STOP}


def entry_words(e: dict) -> set:
    return content_words(" ".join([str(e.get("title") or ""), str(e.get("body") or ""),
                                   " ".join(e.get("evidence") or []), " ".join(e.get("tags") or [])]))


def project_here(cwd=None) -> str:
    here = Path(cwd) if cwd is not None else Path.cwd()
    try:
        here = here.resolve()
    except OSError:
        pass
    for p in (here, *here.parents):
        if (p / ".git").exists():
            return p.name
    return here.name


def project_of(e: dict) -> str:
    return str(e.get("repo") or "")


def role_of(e: dict) -> str:
    return str(e.get("by") or "").split("@", 1)[0]


def sample_root(state_dir) -> Path:
    """Where the guided first run (the first-run pack, 3.4.0.0 B) writes its sample repos: `<state>/start/<day>/`."""
    return Path(state_dir) / "start"


def sample_folders(state_dir) -> set:
    from halo_harness.knowledge.store import root
    base = sample_root(root(state_dir).parent)
    try:
        return {p.name for day in base.iterdir() if day.is_dir() for p in day.iterdir() if p.is_dir()}
    except OSError:
        return set()


def is_sample(e: dict, state_dir=None, folders: Optional[set] = None) -> bool:
    if SAMPLE_TAG in (e.get("tags") or []) or (e.get("meta") or {}).get("sample") is True:
        return True
    if role_of(e) not in ("gate", "judge") or not project_of(e):
        return False
    return project_of(e) in (folders if folders is not None else sample_folders(state_dir))


def is_gate(e: dict) -> bool:
    return role_of(e) == "gate"


def is_routine_gate(e: dict) -> bool:
    return is_gate(e) and e.get("kind") == "finding" and " passes " in str(e.get("title") or "")


def unit_words(e: dict) -> set:
    """The file and symbol words a gate record is about (its title before " passes ")."""
    head = str(e.get("title") or "").split(" passes ", 1)[0]
    words = set()
    for unit in re.split(r"[,\s]+", head):
        words |= {w for w in re.split(r"[#.:]", unit.lower()) if len(w) > 2 and w not in ("py",)}
    return words


def names_unit(e: dict, query_words: set) -> bool:
    return bool(unit_words(e) & set(query_words))


def dup_key(e: dict) -> tuple:
    """The same record re-run: the kind, who wrote it, its project and its title without the sha and command."""
    title = re.sub(r"\s+at\s*$", "", _SHA.sub("", _QUOTED.sub("", str(e.get("title") or ""))).strip())
    return e.get("kind"), role_of(e), project_of(e), " ".join(title.split())


def age_s(e: dict, now: float) -> Optional[float]:
    import calendar
    import time
    try:
        when = calendar.timegm(time.strptime(str(e.get("when") or "")[:19], "%Y-%m-%dT%H:%M:%S"))
    except ValueError:
        return None
    return now - when
