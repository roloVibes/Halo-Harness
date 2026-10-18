"""tools/split_doc.py -- split one long doc under docs/ into parts by task,
keeping the original file as the short entry page that links them.

    python tools/split_doc.py PLAN.json [--dry-run] [--skip docs/OTHER.md ...]

PLAN.json:

    {"doc": "MODELS.md", "read_when": "Read this when ...",
     "parts": [{"file": "MODELS-ollama.md", "title": "Models: Ollama", "read_when": "Read this when ...",
                "from": "## Ollama", "heading": null}, ...]}

Each part starts at the first line (outside a code fence, after the previous
part's start) that begins with its `from` text and runs to the next part's
start; `heading`, when given, is put at the top of the part's body (for a
part that starts inside a section). The text before the first part stays in
the entry page under its title, followed by a table of the parts.

Links are kept working: every `DOC.md#anchor` link in README.md and
docs/**/*.md (and every same-file `#anchor` inside the moved text and the
entry page) is pointed at the part that now holds that heading. A link to
DOC.md without an anchor still reaches the entry page. Never touches
CHANGELOG.md; `--skip` leaves a file's links as they are (another round owns it).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DOCS = REPO / "docs"
_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")


def slug(text: str) -> str:
    """GitHub's heading anchor: lower case, punctuation dropped, spaces to hyphens."""
    s = text.strip().lower()
    s = re.sub(r"[^\w\- ]", "", s)
    return s.replace(" ", "-")


def headings(lines: list) -> list:
    """`[(index, level, text)]` outside code fences."""
    out, fence = [], False
    for i, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            fence = not fence
            continue
        m = None if fence else _HEADING.match(line)
        if m:
            out.append((i, len(m.group(1)), m.group(2)))
    return out


def anchors(lines: list) -> list:
    """`[(index, anchor)]` with GitHub's -1, -2 suffixes for repeats."""
    seen: dict = {}
    out = []
    for i, _level, text in headings(lines):
        base = slug(text)
        n = seen.get(base, 0)
        seen[base] = n + 1
        out.append((i, base if n == 0 else f"{base}-{n}"))
    return out


def _starts(lines: list, parts: list) -> list:
    fence, at, idx = False, 0, []
    for part in parts:
        want = part["from"]
        for i in range(at, len(lines)):
            if lines[i].lstrip().startswith("```"):
                fence = not fence
                continue
            if not fence and lines[i].startswith(want) and (not idx or i > idx[-1]):
                idx.append(i)
                at = i + 1
                break
        else:
            raise SystemExit(f"split_doc: {part['file']}: no line starts with {want!r} after line {at}")
    return idx


def _short(text: str) -> str:
    m = re.match(r"`([^`]+)`", text)
    return f"`{m.group(1).split()[0]}`" if m else text


def _sections(body: list) -> str:
    hs = [(lvl, t) for _i, lvl, t in headings(body)]
    top = [t for lvl, t in hs if lvl == 2]
    if len(top) <= 1:
        top = top + [_short(t) for lvl, t in hs if lvl == 3]
    return " · ".join(top)


def build(plan: dict) -> "tuple[dict, dict]":
    doc = plan["doc"]
    lines = (DOCS / doc).read_text(encoding="utf-8").split("\n")
    title = lines[0]
    starts = _starts(lines, plan["parts"])
    bodies = []
    for n, part in enumerate(plan["parts"]):
        end = starts[n + 1] if n + 1 < len(plan["parts"]) else len(lines)
        body = lines[starts[n]:end]
        while body and not body[-1].strip():
            body.pop()
        if part.get("heading"):
            body = [part["heading"], ""] + body
        bodies.append(body)
    old = {i: a for i, a in anchors(lines)}
    where: dict = {}
    for n, part in enumerate(plan["parts"]):
        end = starts[n + 1] if n + 1 < len(plan["parts"]) else len(lines)
        offset = 2 if part.get("heading") else 0
        new = {i: a for i, a in anchors(bodies[n])}
        for i in range(starts[n], end):
            if i in old and (i - starts[n] + offset) in new:
                where[old[i]] = (part["file"], new[i - starts[n] + offset])
    out: "dict[str, str]" = {}
    intro = lines[1:starts[0]]
    while intro and not intro[0].strip():
        intro.pop(0)
    while intro and not intro[-1].strip():
        intro.pop()
    table = ["## The parts", "", "| Part | Read it when | What is in it |", "|---|---|---|"]
    for part, body in zip(plan["parts"], bodies):
        when = part["read_when"].removeprefix("Read this when ").rstrip(".")
        table.append(f"| [{part['title']}]({part['file']}) | {when} | {_sections(body)} |")
    entry = [title, "", plan["read_when"], ""] + intro + ["", "This page is the entry point; the content lives in "
             "the parts below, one per task.", ""] + table + [""]
    out[doc] = _fix_local("\n".join(entry), doc, where, doc)
    name = title.lstrip("# ").strip()
    for part, body in zip(plan["parts"], bodies):
        head = [f"# {part['title']}", "", part["read_when"], "",
                f"Part of [{name}]({doc}), which lists every part.", ""]
        out[part["file"]] = _fix_local("\n".join(head + body) + "\n", part["file"], where, doc)
    return out, where


def _fix_local(text: str, me: str, where: dict, doc: str) -> str:
    def same(m):
        target = where.get(m.group(1))
        if target is None:
            return m.group(0)
        file, anchor = target
        return f"](#{anchor})" if file == me else f"]({file}#{anchor})"
    return re.sub(r"\]\(#([^)\s]+)\)", same, text)


def relink(text: str, doc: str, where: dict) -> str:
    """Point `[text](<prefix>DOC.md#anchor)` at the part holding the anchor; a
    link text that names the doc (`DOC.md`, `docs/DOC.md`) names the part."""
    pattern = re.compile(r"\[([^\]]*)\]\(([^)\s#]*?)" + re.escape(doc) + r"#([^)\s]+)\)")

    def repl(m):
        target = where.get(m.group(3))
        if target is None:
            return m.group(0)
        label = m.group(1)
        if label.endswith(doc):
            label = label[:-len(doc)] + target[0]
        return f"[{label}]({m.group(2)}{target[0]}#{target[1]})"
    return pattern.sub(repl, text)


def main(argv: list) -> int:
    plan = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    dry = "--dry-run" in argv
    skip = {argv[i + 1] for i, a in enumerate(argv) if a == "--skip" and i + 1 < len(argv)}
    files, where = build(plan)
    for name, text in files.items():
        n = text.count("\n") + 1
        print(f"{name}: {n} lines")
        if not dry:
            (DOCS / name).write_text(text, encoding="utf-8", newline="\n")
    targets = [REPO / "README.md"] + sorted(DOCS.rglob("*.md"))
    for path in targets:
        rel = path.relative_to(REPO).as_posix()
        if path.name == "CHANGELOG.md" or "tui-snapshots" in rel or rel in skip:
            continue
        text = path.read_text(encoding="utf-8")
        new = relink(text, plan["doc"], where)
        if new != text:
            print(f"relinked {rel}")
            if not dry:
                path.write_text(new, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
