"""halo_harness.glossary -- the words Halo uses, one paragraph each (Halo
3.1.1.0 R1).

`docs/GLOSSARY.md` is the source: a `## <word>` heading per word, then one
paragraph. `halo explain`, the TUI's `/explain` and Studio's Glossary
(`GET /api/glossary`) all read it through `load()`. A checkout reads the
docs file itself; an installed copy (no docs/ folder) reads the packaged
twin `templates/glossary/GLOSSARY.md`, which `python tools/sync_glossary.py`
writes and tests/test_glossary.py keeps byte-identical.

`find(query)` matches loosely: case, a plural (`lineups`, `hand-offs`),
spaces, hyphens and underscores (`handoff`, `orchestra_run`), a unique
prefix (`orch`), then the closest spelling. It returns `(word or None,
suggestions)`.
"""

from __future__ import annotations

import difflib
import re
from pathlib import Path
from typing import Optional

TERMS = ("lineup", "bio", "role", "tier", "team", "member", "block", "stage", "lane", "part", "step",
         "mission", "gate", "claim", "hand-off", "plan", "coach", "orchestra run", "fleet", "hub", "harness",
         "capability", "unit", "pack", "guided first run", "setup", "provider", "env file")  # 3.2.1.0 R1: "pack"; 3.2.2.0 R2: "guided first run"; 3.3.0.0 R1: the Setup section's three

PACKAGE_DIR = Path(__file__).resolve().parent
DOCS_FILE = PACKAGE_DIR.parent / "docs" / "GLOSSARY.md"
PACKAGED_FILE = PACKAGE_DIR / "templates" / "glossary" / "GLOSSARY.md"
_HEADING = re.compile(r"^##\s+(.+?)\s*$")


def source_path() -> Path:
    return DOCS_FILE if DOCS_FILE.is_file() else PACKAGED_FILE


def parse(text: str) -> "dict[str, str]":
    """`{word: paragraph}` in file order; a word's lines are joined with single spaces."""
    out: "dict[str, str]" = {}
    word, lines = None, []

    def close() -> None:
        if word is not None:
            out[word] = " ".join(" ".join(lines).split())
    for raw in text.splitlines():
        m = _HEADING.match(raw)
        if m:
            close()
            word, lines = m.group(1).strip().lower(), []
        elif word is not None and raw.strip():
            lines.append(raw.strip())
    close()
    return out


def paragraph_counts(text: str) -> "dict[str, int]":
    """How many paragraphs each word has (the test wants exactly one)."""
    counts: "dict[str, int]" = {}
    word, blank = None, True
    for raw in text.splitlines():
        m = _HEADING.match(raw)
        if m:
            word, blank = m.group(1).strip().lower(), True
            counts[word] = 0
        elif word is not None:
            if raw.strip() and blank:
                counts[word] += 1
            blank = not raw.strip()
    return counts


def load(path: Optional[Path] = None) -> "dict[str, str]":
    try:
        return parse(Path(path or source_path()).read_text(encoding="utf-8"))
    except OSError:
        return {}


def _norm(text: str) -> str:
    return re.sub(r"[\s_\-]+", "", str(text or "").strip().lower())


def _singular(text: str) -> "list[str]":
    forms = [text]
    for suffix in ("ies", "es", "s"):
        if text.endswith(suffix) and len(text) > len(suffix) + 2:
            forms.append(text[: -len(suffix)] + ("y" if suffix == "ies" else ""))
    return forms


def find(query: str, words=None) -> "tuple[Optional[str], list[str]]":
    words = list(words if words is not None else load())
    keyed = {_norm(w): w for w in words}
    q = _norm(query)
    if not q:
        return None, []
    for form in _singular(q):
        if form in keyed:
            return keyed[form], []
    starts = [w for k, w in keyed.items() if k.startswith(q)]
    if len(starts) == 1:
        return starts[0], []
    close = difflib.get_close_matches(q, list(keyed), n=3, cutoff=0.72)
    if len(close) == 1 or (close and difflib.SequenceMatcher(None, q, close[0]).ratio() >= 0.85):
        return keyed[close[0]], []
    return None, sorted(set(starts) | {keyed[c] for c in close})


def first_sentence(text: str) -> str:
    m = re.match(r"(.+?\.)(\s|$)", text)
    return m.group(1) if m else text
