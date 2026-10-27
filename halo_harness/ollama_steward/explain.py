"""halo_harness.ollama_steward.explain -- Halo 3.3.4.0 R4: `halo ollama
explain [<alert kind> | <topic>] [--sources]`, answered from the steward's
knowledge (knowledge/*.md) with no model at all.

- an alert kind (`prompt-trimmed`, `cpu-spill`, ... `thrash`) prints its row
  of knowledge/symptoms.md: the symptom, the cause, the Halo-side change and
  the server-side recommendation; an event kind or a rule name that has no
  row of its own (`reloaded`, `cancel-task`, `window-small`, `slow-box` ...)
  answers with the row it belongs to (ALIASES: names only, never text)
- a topic answers with the knowledge it names: a file (`scheduler`,
  `memory`, `log`, `local-servers`, `symptoms`, `sources`), else the
  sections whose heading holds every word of it (`kv-cache`, `margin`,
  `eviction`), else every paragraph, list item and table row that mentions
  it (`parallel`, `keep-alive`), each under its file and section
- no argument lists the kinds and the topics; `--sources` adds the rows of
  knowledge/SOURCES.md the answer cites (its `[S<n>]` tags)

The knowledge files are the one source: everything here is parsed from their
headings, tables and paragraphs; nothing repeats their text.
"""

from __future__ import annotations

import argparse
import re
import sys
from typing import Optional

from halo_harness.ollama_steward import KNOWLEDGE_DIR

TAG_RE = re.compile(r"\[S(\d+)\]")
_ROW = re.compile(r"^\|\s*`([a-z0-9-]+)`\s*\|(.*)\|\s*$")
_CELLS = ("symptom", "cause", "Halo-side change", "server-side recommendation")
FILE_TOPICS = {"log": "log-vocabulary", "logs": "log-vocabulary", "servers": "local-servers",
               "sources": "SOURCES", "kinds": "symptoms"}
ALIASES = {"cancel-task": "http-500", "reloaded": "thrash", "two-windows": "thrash", "window-asked-small": "prompt-trimmed",
           "window-small": "prompt-trimmed", "window-large": "cpu-spill", "no-compaction": "compaction-not-firing",
           "compaction-failed": "compaction-not-firing", "cut-resent": "truncated-reply-resent", "slow-box": "stall",
           "no-reserve": "no-reply-reserve"}
_STOP = {"the", "a", "an", "and", "of", "on", "to", "what", "how", "for", "is", "it"}


def _read(stem: str) -> str:
    try:
        return (KNOWLEDGE_DIR / f"{stem}.md").read_text(encoding="utf-8")
    except OSError:
        return ""


def stems() -> "list[str]":
    return [p.stem for p in sorted(KNOWLEDGE_DIR.glob("*.md"))]


def symptom_rows() -> "dict[str, dict]":
    """{kind: {symptom, cause, Halo-side change, server-side recommendation}} from symptoms.md's table."""
    rows = {}
    for line in _read("symptoms").splitlines():
        m = _ROW.match(line)
        if m:
            cells = [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", m.group(2))]
            if len(cells) == len(_CELLS):
                rows[m.group(1)] = dict(zip(_CELLS, cells))
    return rows


def _slug(title: str) -> str:
    plain = re.sub(r"\(.*?\)", "", title.lower()).replace("'s", "")
    words = [w for w in re.split(r"[^a-z0-9]+", plain) if w and w not in _STOP]
    return "-".join(words)


def sections(stem: Optional[str] = None) -> "list[dict]":
    """Every `## ` section of the knowledge files: {file, title, slug, lines}."""
    out = []
    for s in ([stem] if stem else stems()):
        cur = None
        fence = False
        for line in _read(s).splitlines():
            if line.startswith("```"):
                fence = not fence
            if line.startswith("## ") and not fence:
                cur = {"file": s, "title": line[3:].strip(), "slug": _slug(line[3:]), "lines": []}
                out.append(cur)
            elif cur is not None:
                cur["lines"].append(line)
    return out


def topics() -> "list[str]":
    """The topic names `explain` lists: the files, then each file's sections."""
    files = [("log" if s == "log-vocabulary" else s) for s in stems() if s != "SOURCES"] + ["sources"]
    return files + [s["slug"] for s in sections() if s["file"] != "SOURCES" and s["slug"]]


def _claims(lines: list) -> "list[str]":
    """A section's lines as claims: paragraphs, list items and table data rows."""
    out, para = [], []
    for line in lines + [""]:
        t = line.strip()
        if not t or t.startswith(("|---", "|-", "```")):
            if para:
                out.append(" ".join(para))
                para = []
            continue
        if t.startswith(("- ", "|")):
            if para:
                out.append(" ".join(para))
                para = []
            out.append(t)
        else:
            para.append(t)
    return out


def answer_kind(name: str) -> "Optional[list[str]]":
    rows = symptom_rows()
    kind = name if name in rows else ALIASES.get(name)
    if kind not in rows:
        return None
    head = f"{name} (the `{kind}` row of symptoms.md)" if kind != name else name
    return [head] + [f"  {cell}: {rows[kind][cell]}" for cell in _CELLS]


def answer_topic(name: str) -> "Optional[list[str]]":
    stem = FILE_TOPICS.get(name, name)
    if stem in stems():
        return [f"{stem}.md", ""] + _read(stem).rstrip().splitlines()
    words = [w for w in re.split(r"[^a-z0-9]+", name.lower()) if w and w not in _STOP]
    if not words:
        return None
    hits = [s for s in sections() if s["file"] != "SOURCES" and all(w in s["slug"].split("-") for w in words)]
    if hits:
        out = []
        for s in hits:
            out += ([""] if out else []) + [f"{s['file']}.md: {s['title']}"] + [x for x in s["lines"] if x.strip()]
        return out
    pat = re.compile(r"[\s_-]*".join(re.escape(w) for w in words), re.IGNORECASE)
    out, last = [], None
    for s in sections():
        if s["file"] == "SOURCES":
            continue
        for claim in _claims(s["lines"]):
            if pat.search(claim):
                if last != (s["file"], s["title"]):
                    out += ([""] if out else []) + [f"{s['file']}.md: {s['title']}"]
                    last = (s["file"], s["title"])
                out.append(f"  {claim}")
    return out or None


def source_rows() -> "dict[int, str]":
    rows = {}
    for line in _read("SOURCES").splitlines():
        m = re.match(r"^\|\s*S(\d+)\s*\|(.*)\|\s*$", line)
        if m:
            cells = [c.strip() for c in m.group(2).split("|")]
            rows[int(m.group(1))] = " | ".join(c for c in cells if c)
    return rows


def cited(lines: list) -> "list[str]":
    """The SOURCES.md rows the `[S<n>]` tags in `lines` name, in order."""
    tags = sorted({int(n) for line in lines for n in TAG_RE.findall(line)})
    rows = source_rows()
    return [f"S{n}: {rows[n]}" for n in tags if n in rows]


def listing() -> "list[str]":
    kinds = sorted(symptom_rows())
    return (["Alert kinds (halo ollama explain <kind>):", "  " + ", ".join(kinds),
             "  also: " + ", ".join(f"{a} ({k})" for a, k in sorted(ALIASES.items())), "",
             "Topics (halo ollama explain <topic>; a word that names no heading finds every line that mentions it):"]
            + [f"  {t}" for t in topics()])


def explain(what: Optional[str]) -> "tuple[list[str], bool]":
    """(the answer's lines, whether it answered)."""
    if not what:
        return listing(), True
    name = what.strip().lower()
    got = answer_kind(name) or answer_topic(name)
    if got:
        return got, True
    return [f"nothing in the steward's knowledge names {what!r}", ""] + listing(), False


def cmd_ollama_explain(argv: list) -> int:
    parser = argparse.ArgumentParser(
        prog="halo ollama explain", add_help=True,
        description="What an alert kind means (its symptom, cause, the Halo-side change and the server-side "
                    "recommendation) or what the steward's knowledge says on a topic (scheduler, memory, log, "
                    "local-servers, kv-cache, parallel, margin, ...). Answered from the knowledge files; no model "
                    "is called.")
    parser.add_argument("what", nargs="?", default=None, help="an alert kind or a topic; none lists both")
    parser.add_argument("--sources", action="store_true", help="also print the sources the answer cites")
    args = parser.parse_args(argv)
    lines, ok = explain(args.what)
    for line in lines:
        print(line)
    if args.sources and args.what and ok:
        print()
        print("Sources:")
        for row in cited(lines) or ["(the answer cites no source)"]:
            print(f"  {row}")
    return 0 if ok else 1
