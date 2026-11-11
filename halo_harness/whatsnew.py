"""halo_harness.whatsnew -- what a version changed, on a box with no repo (Halo 3.3.16.2, "from a session's own
review": a `uv tool install` carries no CHANGELOG.md, so neither the owner nor the model he asks could see what
3.3.16 changed).

The package ships `halo_harness/data/changelog.md`: the newest `KEEP` dated version entries of CHANGELOG.md,
written by `write_data(repo_dir)` -- scripts/release.py calls it when it dates a release, so every release
refreshes it (tests/test_whatsnew.py checks its newest entry is CHANGELOG.md's newest dated one).

    entries(text)              -> [Entry(version, date, body)] in file order (newest first)
    packaged(text, keep=KEEP)  -> the data file's text
    write_data(repo_dir)       -> the path written
    load()                     -> the packaged entries ([] when the file is missing)
    summary(body)              -> the entry's two-sentence summary (its first paragraph)
    headings(body)             -> [(### heading, its first line)]
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

KEEP = 12
DATA = Path(__file__).resolve().parent / "data" / "changelog.md"
HEAD = ("# What changed (the newest version entries of CHANGELOG.md, shipped with the package; "
        "`halo whatsnew` reads it)\n\n")
_HEADING = re.compile(r"^## \[([^\]]+)\] - (\S+)\s*$", re.MULTILINE)
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z`*(\"])")


class Entry(NamedTuple):
    version: str
    date: str
    body: str

    @property
    def dated(self) -> bool:
        return bool(re.match(r"^\d{4}-\d{2}-\d{2}$", self.date))


def entries(text: str) -> "list[Entry]":
    marks = list(_HEADING.finditer(text or ""))
    out = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        out.append(Entry(m.group(1).strip(), m.group(2).strip(), text[m.end():end].strip("\n")))
    return out


def packaged(text: str, keep: int = KEEP) -> str:
    dated = [e for e in entries(text) if e.dated][:keep]
    return HEAD + "\n\n".join(f"## [{e.version}] - {e.date}\n\n{e.body.strip()}" for e in dated) + "\n"


def write_data(repo_dir) -> Path:
    """`<repo>/halo_harness/data/changelog.md` from `<repo>/CHANGELOG.md` (LF line endings)."""
    repo = Path(repo_dir)
    path = repo / "halo_harness" / "data" / "changelog.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(packaged((repo / "CHANGELOG.md").read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    return path


def load(path=None) -> "list[Entry]":
    try:
        return entries(Path(path or DATA).read_text(encoding="utf-8"))
    except OSError:
        return []


def _plain(text: str) -> str:
    return " ".join(re.sub(r"\*\*([^*]+)\*\*", r"\1", text).split())


def summary(body: str, sentences: int = 2) -> str:
    """The first paragraph's first `sentences` sentences (the bold lead-in kept as plain words)."""
    para = next((p for p in re.split(r"\n\s*\n", body or "") if p.strip() and not p.lstrip().startswith("#")), "")
    parts = _SENTENCE.split(_plain(para))
    return " ".join(parts[:sentences]).strip()


def headings(body: str) -> "list[tuple[str, str]]":
    """Each `###` heading with the first line under it (a list item's marker and bold dropped)."""
    out = []
    lines = (body or "").splitlines()
    for i, line in enumerate(lines):
        if not line.startswith("### "):
            continue
        first = ""
        for ln in lines[i + 1:]:
            if ln.startswith("### ") or ln.startswith("## "):
                break
            if ln.strip() and not ln.lstrip().startswith("#"):  # a deeper heading is passed over
                first = _plain(re.sub(r"^\s*[-*]\s+", "", ln))
                break
        out.append((line[4:].strip(), first))
    return out
