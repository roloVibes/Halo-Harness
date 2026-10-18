"""halo_harness.explain_cli -- `halo explain [thing]` (Halo 3.1.1.0 R1).

    halo explain              every word, with its first sentence
    halo explain <thing>      the word's paragraph (fuzzy: `halo explain lineups`, `handoff`, `orch`)
    halo explain --json [thing]

The paragraphs are docs/GLOSSARY.md's (halo_harness/glossary.py), the same
the TUI's /explain card and Studio's Glossary show. Exit codes: 0 found or
listed, 1 no such word (the closest ones are named), 2 usage.
"""

from __future__ import annotations

import json
import shutil
import sys
import textwrap

from halo_harness import glossary as G


def _width() -> int:
    return max(60, min(100, shutil.get_terminal_size((100, 24)).columns - 2))


def explain_text(thing: str) -> "tuple[bool, str]":
    """`(found, text)`: the word and its paragraph, or what is closest."""
    words = G.load()
    word, close = G.find(thing, words)
    if word is None:
        hint = f" Closest: {', '.join(close)}." if close else ""
        return False, f"halo explain: no word {thing!r} in the glossary.{hint} halo explain lists them all."
    # never break inside a word: "hand-off" split at a line end read as "hand- off" on the Windows runner
    body = textwrap.fill(words[word], width=_width(), break_on_hyphens=False, break_long_words=False)
    return True, f"{word}\n\n{body}"


def list_text() -> str:
    words = G.load()
    if not words:
        return f"halo explain: the glossary is missing ({G.source_path()})"
    pad = max(len(w) for w in words) + 2
    lines = [f"{len(words)} words (halo explain <word> for the paragraph; docs/GLOSSARY.md):", ""]
    for word, text in words.items():
        lines.append(f"  {word:<{pad}}{G.first_sentence(text)}")
    return "\n".join(lines)


def cmd_explain(argv) -> int:
    args = [a for a in argv if a != "--json"]
    as_json = len(args) != len(argv)
    if args[:1] in (["-h"], ["--help"]):
        print("usage: halo explain [--json] [thing]   (no thing: every word)")
        return 0
    thing = " ".join(args).strip()
    if as_json:
        words = G.load()
        if not thing:
            print(json.dumps({"words": [{"word": w, "text": t} for w, t in words.items()]}, indent=2))
            return 0
        word, close = G.find(thing, words)
        print(json.dumps({"query": thing, "word": word, "text": words.get(word or "", ""), "closest": close}, indent=2))
        return 0 if word else 1
    if not thing:
        print(list_text())
        return 0
    found, text = explain_text(thing)
    print(text, file=sys.stdout if found else sys.stderr)
    return 0 if found else 1
