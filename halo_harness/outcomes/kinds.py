"""halo_harness.outcomes.kinds -- the kind of an agent's task, and what a test
run looks like (Halo 3.1.8.0 R3, docs/OUTCOMES.md "The kinds").

One mapping, read in this order:

1. the bio's `kind` (agents_yaml.KNOWN_KINDS): coder -> code, researcher ->
   research, reviewer / judge -> review, planner -> plan, writer -> writing,
   media -> media, ops -> check;
2. else the first word among the names around the agent (its role, its
   lineup alias, its bio or agent name: `Explore`, `auto-coder`, `tester`)
   that `WORDS` knows;
3. else the caller's default: `code` for an Orchestra lane (a lane edits
   code units), `other` for a session's sub-agent.

`is_test_command(command)` -- a shell command that runs tests: pytest,
unittest, `python -m tests.<x>`, a `test_*.py` / `*_test.py` file,
`run_all.py`, npm / pnpm / yarn / bun test, jest, vitest, mocha, go /
cargo / dotnet / deno / mix test, mvn / gradle test, `make test|check`, tox,
nox, ctest, rspec, phpunit.
"""

from __future__ import annotations

import re

KINDS = ("code", "research", "check", "writing", "plan", "review", "media", "other")
BIO_KINDS = {"coder": "code", "researcher": "research", "reviewer": "review", "judge": "review",
             "planner": "plan", "writer": "writing", "media": "media", "ops": "check"}
WORDS = (("code", ("coder", "code", "implement", "implementer", "fix", "fixer", "refactor", "developer", "engineer")),
         ("research", ("researcher", "research", "explore", "explorer", "investigate", "investigator", "scout")),
         ("review", ("reviewer", "review", "judge", "audit", "auditor", "critic")),
         ("plan", ("planner", "plan", "outline", "architect")),
         ("writing", ("writer", "write", "docs", "summarize", "summarizer", "changelog", "editor")),
         ("media", ("media", "screenshot", "video", "audio", "image", "transcribe")),
         ("check", ("ops", "check", "checker", "tester", "test", "verify", "verifier", "qa", "ci", "deploy", "release")))
_WORD_KIND = {w: kind for kind, words in WORDS for w in words}
_SPLIT = re.compile(r"[^a-z0-9]+")
_TEST = re.compile(
    r"(?:^|[\s;&|(`'\"])(?:pytest|py\.test|tox|nox|jest|vitest|mocha|phpunit|rspec|ctest)(?:\s|$|['\"`])"
    r"|-m\s+(?:pytest|unittest|tests?\.\w+)"
    r"|\b(?:npm|pnpm|yarn|bun)\s+(?:run\s+)?test\b|\bnpx\s+(?:jest|vitest|mocha|playwright\s+test)\b"
    r"|\b(?:go|cargo|dotnet|deno|mix)\s+test\b|\b(?:mvn|gradle|gradlew)\b[^\n|;&]*\btest\b"
    r"|\bmake\s+(?:[\w.-]+\s+)*(?:test|check)\b|\brun_all\.py\b|(?:^|[\s/\\])test_\w+\.py\b|\b\w+_test\.py\b",
    re.I)


def kind_of(bio_kind=None, words: str = "", *, default: str = "other") -> str:
    """The task's kind (see the module docstring)."""
    if isinstance(bio_kind, str) and bio_kind.strip().lower() in BIO_KINDS:
        return BIO_KINDS[bio_kind.strip().lower()]
    for word in _SPLIT.split(str(words or "").lower()):
        if word in _WORD_KIND:
            return _WORD_KIND[word]
    return default if default in KINDS else "other"


def is_test_command(command: str) -> bool:
    return bool(_TEST.search(str(command or "")))
