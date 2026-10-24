"""halo_harness.knowledge.frontmatter -- a knowledge entry's text (Halo 3.1.8.0
R4): its front matter written and read back (YAML between two `---` lines),
the one-line fields and lists it holds, the UTC time it carries, and the
confidence rule for a finding.

    confidence(evidence)   `checked` when an evidence line names a test run or a reproduction -- the
                           outcomes lines' "tests: `<command>` ..." / "reproduction: `<command>` ...", or a
                           test runner's command (outcomes/kinds.py `is_test_command`) -- else `said`
"""

from __future__ import annotations

import re
import time
from typing import Optional

LINE_CAP, LIST_CAP = 400, 40
_CHECKED = re.compile(r"\b(?:tests|reproduction):\s*`", re.I)


def confidence(evidence) -> str:
    from halo_harness.outcomes.kinds import is_test_command
    for line in evidence or []:
        if _CHECKED.search(str(line)) or is_test_command(str(line)):
            return "checked"
    return "said"


def one_line(text, cap: int = LINE_CAP) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= cap else text[:cap - 3] + "..."


def lines(values, cap: int = LIST_CAP) -> list:
    """A list of one-line strings (a bare string is a list of one), empty ones dropped, at most `cap`."""
    if isinstance(values, str):
        values = [values]
    return [one_line(v) for v in values or [] if str(v or "").strip()][:cap]


def utc(ts: Optional[float] = None) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def render(front: dict, body: str) -> str:
    import yaml
    head = yaml.safe_dump(front, sort_keys=False, allow_unicode=True, default_flow_style=False, width=1000)
    return f"---\n{head}---\n{str(body or '').strip()}\n"


def parse(text: str) -> "tuple[dict, str]":
    """`(front matter, body)` of an entry's file ({} and the text when it has none)."""
    import yaml
    text = str(text or "").lstrip("﻿").replace("\r\n", "\n")
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 3)
    if end < 0:
        return {}, text
    try:
        front = yaml.safe_load(text[4:end + 1]) or {}
    except yaml.YAMLError:
        front = {}
    return (front if isinstance(front, dict) else {}), text[end + 5:].strip("\n")
