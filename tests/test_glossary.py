"""tests.test_glossary -- Halo 3.1.1.0 R1: docs/GLOSSARY.md, `halo explain`,
the TUI's /explain, Studio's `GET /api/glossary` and the words each section's
help links (halo_harness/glossary.py, explain_cli.py, studio/glossary_api.py,
ui/src/routes/sectionHelp.ts).

1. every word of the brief's list has exactly one paragraph, and nothing else
   is in the file; the packaged twin is byte-identical (tools/sync_glossary.py)
2. every word Studio's section help names exists in the glossary
3. `halo explain` for three words, the list, an unknown word
4. the fuzzy match: plurals, hyphens and spaces, a prefix, a misspelling
5. the API route and the /explain headless text and card
Run: python -m tests.test_glossary
"""
from __future__ import annotations

import io
import json
import re
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

ensure_scoped_state_dir_once()
test, TESTS = new_registry()

REPO = Path(__file__).resolve().parent.parent
BRIEF = ("lineup", "bio", "role", "tier", "team", "member", "block", "stage", "lane", "part", "flow", "step", "mission",
         "gate", "claim", "hand-off", "plan", "coach", "orchestra run", "fleet", "hub", "harness", "capability")


def _explain(*argv):
    from halo_harness.explain_cli import cmd_explain
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = cmd_explain(list(argv))
    return rc, out.getvalue(), err.getvalue()


@test
def test_every_word_has_one_paragraph(ctx: Ctx):
    from halo_harness import glossary as G
    text = (REPO / "docs" / "GLOSSARY.md").read_text(encoding="utf-8")
    words = G.parse(text)
    ctx.check(f"the module's list is the brief's, got {G.TERMS}", tuple(G.TERMS) == BRIEF)
    ctx.check(f"the file has exactly the brief's words, got {list(words)}", sorted(words) == sorted(BRIEF))
    counts = G.paragraph_counts(text)
    ctx.check(f"one paragraph each, got {[w for w, n in counts.items() if n != 1]}", all(n == 1 for n in counts.values()))
    short = [w for w, t in words.items() if len(t) < 120]
    ctx.check(f"each paragraph says something (120+ characters), short: {short}", not short)
    ctx.check("the file opens with when to read it", text.startswith("# Glossary\n\nRead this when"))
    twin = REPO / "halo_harness" / "templates" / "glossary" / "GLOSSARY.md"
    ctx.check("the packaged twin is byte-identical (python tools/sync_glossary.py)",
              twin.read_bytes().replace(b"\r\n", b"\n") == (REPO / "docs" / "GLOSSARY.md").read_bytes().replace(b"\r\n", b"\n"))
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    ctx.check("the twin ships as package data", '"templates/glossary/*.md"' in pyproject)
    ctx.check("a checkout reads docs/GLOSSARY.md itself", G.source_path() == REPO / "docs" / "GLOSSARY.md")
    ctx.check("the twin parses the same", G.load(twin) == words)


@test
def test_every_word_studio_help_names_exists(ctx: Ctx):
    from halo_harness import glossary as G
    words = set(G.load())
    src = (REPO / "halo_harness" / "studio" / "ui" / "src" / "routes" / "sectionHelp.ts").read_text(encoding="utf-8")
    blocks = re.findall(r"terms: \[([^\]]*)\]", src)
    ctx.check(f"seven sections name their words, got {len(blocks)}", len(blocks) == 7)
    named = [w for b in blocks for w in re.findall(r'"([^"]+)"', b)]
    missing = sorted({w for w in named if w not in words})
    ctx.check(f"every named word has a paragraph, missing: {missing}", named and not missing)
    shell = (REPO / "halo_harness" / "studio" / "ui" / "src" / "shell" / "SectionHelp.tsx").read_text(encoding="utf-8")
    ctx.check("the help page links each word into the Glossary", "copy.terms.map" in shell and "openGlossary(w)" in shell)


@test
def test_halo_explain_prints_the_paragraph(ctx: Ctx):
    from halo_harness import glossary as G
    words = G.load()
    for word in ("lineup", "hand-off", "orchestra run"):
        rc, out, _ = _explain(*word.split())
        flat = " ".join(out.split())
        ctx.check(f"`halo explain {word}`: the word, then its paragraph, got {rc} {out[:120]!r}",
                  rc == 0 and out.startswith(word + "\n\n") and flat.endswith(words[word]))
    rc, out, _ = _explain()
    ctx.check(f"no word lists all 23, got {rc} {out[:80]!r}", rc == 0 and out.startswith("23 words")
              and all(f"  {w} " in out for w in BRIEF))
    rc, _, err = _explain("xyzzy")
    ctx.check(f"an unknown word: exit 1, said so, got {rc} {err!r}", rc == 1 and "no word 'xyzzy'" in err)
    rc, out, _ = _explain("--json", "lineups")
    data = json.loads(out)
    ctx.check(f"--json, got {data.get('word')}", rc == 0 and data["word"] == "lineup" and data["text"] == words["lineup"])
    from halo_harness.cli import main
    so = io.StringIO()
    with redirect_stdout(so):
        rc = main(["explain", "tier"])
    ctx.check(f"`halo explain` is a verb of the CLI, got {rc}", rc == 0 and so.getvalue().startswith("tier\n"))


@test
def test_fuzzy_match(ctx: Ctx):
    from halo_harness import glossary as G
    for query, want in (("lineups", "lineup"), ("Lineup", "lineup"), ("handoff", "hand-off"), ("hand-offs", "hand-off"),
                        ("hand off", "hand-off"), ("orchestra_run", "orchestra run"), ("orch", "orchestra run"),
                        ("capabilities", "capability"), ("teem", "team"), ("missions", "mission"), ("tiers", "tier")):
        word, _ = G.find(query)
        ctx.check(f"{query!r} -> {want!r}, got {word!r}", word == want)
    word, close = G.find("st")
    ctx.check(f"an ambiguous prefix names the candidates, got {word} {close}", word is None and {"stage", "step"} <= set(close))
    ctx.check("nothing for an empty query", G.find("") == (None, []))


@test
def test_api_route_and_the_tui(ctx: Ctx):
    from halo_harness import glossary as G
    from halo_harness.studio.api import Request, dispatch
    from halo_harness.config.paths import bridge_home
    req = Request(method="GET", path="glossary", query={}, body={}, cwd=REPO, state_dir=Path(bridge_home()))
    status, body = dispatch(req)
    ctx.check(f"GET /api/glossary: 200 and 23 words in file order, got {status}", status == 200
              and [w["word"] for w in body["words"]] == list(BRIEF) and body["words"][0]["text"] == G.load()["lineup"])
    status, _ = dispatch(Request(method="POST", path="glossary", query={}, body={}, cwd=REPO, state_dir=Path(bridge_home())))
    ctx.check(f"POST is a 405, got {status}", status == 405)
    from halo_harness.commands.builtins import _BUILTIN_SPECS
    ctx.check("/explain and /start are built-ins", "explain" in _BUILTIN_SPECS and "start" in _BUILTIN_SPECS)
    text = _BUILTIN_SPECS["explain"][3]("gate", None)
    ctx.check(f"headless /explain gate: the paragraph, got {text[:60]!r}", text.startswith("gate\n\n") and "return cap" in text)
    from halo_harness.tui.dialogs.explain_card import card_parts
    title, body_text = card_parts("claims")
    ctx.check(f"the TUI card: claims -> claim, got {title}", title == "claim" and body_text == G.load()["claim"])
    title, body_text = card_parts("nope-nope")
    ctx.check(f"an unknown word's card lists the words, got {title}", title.startswith("No word") and "lineup" in body_text)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
