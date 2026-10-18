"""tests.helpers.doc_parts -- read a doc under docs/ together with its parts
(Halo 3.1.1.0 R2: the longest docs were split by task; the original file is
the entry page whose "## The parts" table links each part).

    doc_text("SLASH-COMMANDS.md")  # the entry page, then every part, joined
    doc_parts("MODELS.md")         # ["MODELS-references.md", ...]

A doc without a parts table reads as itself, so a test written this way keeps
working when a doc is split later.
"""

from __future__ import annotations

import re
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent.parent / "docs"
_PART_LINK = re.compile(r"\]\(([A-Za-z0-9._-]+\.md)\)")


def doc_parts(name: str) -> "list[str]":
    text = (DOCS / name).read_text(encoding="utf-8")
    start = text.find("\n## The parts")
    if start < 0:
        return []
    section = text[start:]
    nxt = section.find("\n## ", 1)
    section = section if nxt < 0 else section[:nxt]
    seen: "list[str]" = []
    for target in _PART_LINK.findall(section):
        if target != name and target not in seen and (DOCS / target).is_file():
            seen.append(target)
    return seen


def doc_text(name: str) -> str:
    texts = [(DOCS / name).read_text(encoding="utf-8")]
    texts += [(DOCS / part).read_text(encoding="utf-8") for part in doc_parts(name)]
    return "\n".join(texts)
