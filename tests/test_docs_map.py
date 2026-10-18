"""tests.test_docs_map -- the docs map and the split docs (Halo 3.1.1.0 R2).

  - docs/README.md links every doc under docs/ (and docs/harness/README.md),
    each under one task heading, each line ending in the doc's own
    "Read this when ..." sentence;
  - every doc opens with a one-line "Read this when ..." under its title;
  - a split doc (an entry page with a "## The parts" table) is short, every
    part it lists exists, opens with "Part of [...](<entry>)" and is at most
    400 lines, and no `<ENTRY>-*.md` file is left out of its table;
  - every `file.md#anchor` link in README.md and docs/ names a heading that
    file has (the split moved sections; their links moved with them).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.doc_parts import doc_parts  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tools.split_doc import anchors  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
DOCS = REPO / "docs"
MAP = DOCS / "README.md"
TASKS = ("## I want to set up", "## I want to run agents", "## I want to use Studio", "## I want to run a fleet",
         "## I want to develop Halo")
SPLIT = ("MODELS.md", "STUDIO.md", "SLASH-COMMANDS.md", "ARCHITECTURE.md", "COMMANDS.md")  # 3.1.1.0 R3: COMMANDS.md too
_MAP_LINE = re.compile(r"^\s*- \[([^\]]+)\]\(([^)]+)\) \([^\n]*?\): (read this when .+)$")
_LINK = re.compile(r"\]\(([^)\s]*?\.md)?#([^)\s]+)\)")


def _docs() -> "list[str]":
    return sorted(p.name for p in DOCS.glob("*.md") if p.name != "README.md") + ["harness/README.md"]


def _opening(rel: str) -> str:
    lines = (DOCS / rel).read_text(encoding="utf-8").split("\n")
    rest = [ln for ln in lines[1:6] if ln.strip()]
    return rest[0] if rest else ""


@test
def test_the_map_lists_every_doc_under_a_task(ctx: Ctx):
    text = MAP.read_text(encoding="utf-8")
    ctx.check("the map opens with its own Read this when line", _opening("README.md").startswith("Read this when"))
    for heading in TASKS:
        ctx.check(f"the map has the task heading {heading!r}", f"\n{heading}\n" in text)
    listed = {}
    for line in text.split("\n"):
        m = _MAP_LINE.match(line)
        if m:
            listed[m.group(2)] = m.group(3)
    missing = [d for d in _docs() if d not in listed]
    ctx.check(f"every doc is in docs/README.md; missing: {missing}", not missing)
    for rel, sentence in listed.items():
        own = _opening(rel)
        ctx.check(f"the map's line for {rel} is the doc's own: {sentence!r} vs {own!r}",
                  own.startswith("Read this when") and sentence == "r" + own[1:])
    tasks_of = {}
    section = ""
    for line in text.split("\n"):
        if line.startswith("## "):
            section = line
        m = _MAP_LINE.match(line)
        if m and not line.startswith("  "):
            tasks_of.setdefault(m.group(2), []).append(section)
    ctx.check("each top-level doc is under exactly one task",
              all(len(v) == 1 and v[0] in TASKS for v in tasks_of.values()))


@test
def test_every_doc_opens_with_read_this_when(ctx: Ctx):
    bad = [d for d in _docs() + ["README.md"] if not _opening(d).startswith("Read this when")]
    ctx.check(f"every doc opens with 'Read this when ...' under its title; not: {bad}", not bad)
    one_line = [d for d in _docs()
                if (DOCS / d).read_text(encoding="utf-8").split("\n")[3].strip()]
    ctx.check(f"the line is one line (a blank line follows it); not: {one_line}", not one_line)


@test
def test_the_split_docs_are_short_entry_pages_with_parts(ctx: Ctx):
    for entry in SPLIT:
        parts = doc_parts(entry)
        ctx.check(f"{entry} lists its parts", len(parts) >= 3)
        n = (DOCS / entry).read_text(encoding="utf-8").count("\n")
        ctx.check(f"{entry} is a short entry page ({n} lines)", n <= 80)
        stem = entry[:-3]
        stray = sorted(p.name for p in DOCS.glob(f"{stem}-*.md") if p.name not in parts)
        ctx.check(f"every {stem}-*.md is in {entry}'s table; not: {stray}", not stray)
        for part in parts:
            text = (DOCS / part).read_text(encoding="utf-8")
            lines = text.count("\n")
            ctx.check(f"{part} is at most 400 lines ({lines})", lines <= 400)
            ctx.check(f"{part} says which doc it is part of", "Part of [" in text and f"]({entry})" in text.split("\n## ")[0])


@test
def test_every_anchor_link_names_a_heading_of_its_file(ctx: Ctx):
    cache: dict = {}
    broken = []
    for f in [REPO / "README.md"] + sorted(DOCS.rglob("*.md")):
        rel = f.relative_to(REPO).as_posix()
        text = f.read_text(encoding="utf-8")
        for m in _LINK.finditer(text):
            target = (f.parent / m.group(1)).resolve() if m.group(1) else f
            if not target.is_file():
                continue
            if target not in cache:
                cache[target] = {a for _i, a in anchors(target.read_text(encoding="utf-8").split("\n"))}
            if m.group(2) not in cache[target]:
                broken.append(f"{rel}:{text.count(chr(10), 0, m.start()) + 1}: {m.group(1) or ''}#{m.group(2)}")
    ctx.check("every anchor link names a heading of its file:\n  " + "\n  ".join(broken), not broken)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
