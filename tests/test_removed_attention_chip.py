"""tests.test_removed_attention_chip -- Halo 3.6.0.5 r, "Attention leaves Agents" (the owner, 2026-11-18, point 29:
"What's the point of the attention button if it just shows you the flow? Remove that from agents."): the chip
"Attention · n", its panel, its A key, its styles and its help left every Agents tab, and a test keeps it so. The word
Grep of the decided text (R6), case as written, each identifier bounded by \\b so that a longer name of Session's is
not hit (`useAttentionKeys`, the keys of Session's Attention, stays):

    \\bagents-attention\\b|\\bAttentionChip\\b|\\bag-attn\\b|Attention · |Agents: Attention|Agents, Attention|
    \\btoggleAttention\\b|\\buseAttentionKey\\b

over Studio's UI source (.ts, .tsx, .css), README.md, every file of docs/ (.md, .html, .txt) and the string constants of
every .py under halo_harness/ (the ast scan of tests/test_removed_replays.py: docstrings and comments left out), minus
SKIP. SKIP is data, the shape of tests/test_removed_replays.py's: (a glob of the file, a regex of the line, the reason);
a skip excuses only the span it matches, and a skip that matches nothing fails. The word Attention alone stays:
Session's Attention drawer keeps it. No browser driver opens the Agents panel. The docs say where decisions wait now.
Run: python -m tests.test_removed_attention_chip
"""
from __future__ import annotations

import ast
import fnmatch
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.test_removed_replays import PY_NOT, _strings  # noqa: E402

test, TESTS = new_registry()

WORDS = re.compile(r"\bagents-attention\b|\bAttentionChip\b|\bag-attn\b|Attention · |Agents: Attention|Agents, Attention"
                   r"|\btoggleAttention\b|\buseAttentionKey\b")
# (a folder of the repo -- or one file --, the file patterns read in it)
SCOPE = [("halo_harness/studio/ui/src", ("*.ts", "*.tsx", "*.css")),
         ("README.md", ("README.md",)),
         ("docs", ("*.md", "*.html", "*.txt"))]
# (a glob of the file, relative to the repo; a regex of the line; the reason it keeps its words)
SKIP = [
    ("docs/STUDIO.md", r"How this works: Attention · How this works: Costs",
     "the index of STUDIO-live-panels.md's headings: Session's Attention section, not the chip"),
]
UI = REPO / "halo_harness" / "studio" / "ui" / "src"
DRIVER = re.compile(r"""agents-attention|data-(testid|panel)=[\\"']*fleet-attention(?![-\w])""")


def _files():
    for folder, pats in SCOPE:
        root = REPO / folder
        for p in sorted(root.rglob("*")) if root.is_dir() else [root]:
            if p.is_file() and any(fnmatch.fnmatch(p.name, pat) for pat in pats):
                yield p.relative_to(REPO).as_posix(), p


def _py_files():
    for p in sorted((REPO / "halo_harness").rglob("*.py")):
        rel = p.relative_to(REPO).as_posix()
        if "__pycache__" not in rel and not any(fnmatch.fnmatch(rel, g) for g in PY_NOT):
            yield rel, p


def _left(rel: str, line: str, used: "set[int] | None" = None) -> str:
    """The line with the span of every skip of this file cut out (a skip that cut a word is marked used)."""
    for i, (glob, rx, _why) in enumerate(SKIP):
        if not any(fnmatch.fnmatch(rel, g) for g in ((glob,) if isinstance(glob, str) else glob)):
            continue
        cut = re.sub(rx, " ", line)
        if used is not None and len(WORDS.findall(cut)) < len(WORDS.findall(line)):
            used.add(i)
        line = cut
    return line


def scan() -> "tuple[list[str], set[int], dict]":
    hits: list = []
    used: set = set()
    seen = {"ui": 0, "docs": 0, "py": 0}
    for rel, p in _files():
        seen["ui" if rel.startswith("halo_harness/") else "docs"] += 1
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if WORDS.search(line) and WORDS.search(_left(rel, line, used)):
                hits.append(f"{rel}:{n}: {line.strip()[:160]}")
    for rel, p in _py_files():
        seen["py"] += 1
        for n, text in _strings(p.read_text(encoding="utf-8")):
            for piece in text.splitlines() or [text]:
                if WORDS.search(piece) and WORDS.search(_left(rel, piece, used)):
                    hits.append(f"{rel}:{n}: {piece.strip()[:160]}")
    return hits, used, seen


@test
def test_the_chip_left_studio_and_its_words_with_it(ctx: Ctx):
    hits, _used, _seen = scan()
    sep = "\n    "
    ctx.check(f"{len(hits)} lines still name the Agents chip, its panel, its key or its help:" + sep + sep.join(hits[:120]), not hits)


@test
def test_no_browser_driver_opens_the_agents_panel(ctx: Ctx):
    me = Path(__file__).name
    files = sorted((REPO / "tests" / "helpers").glob("*.py")) + sorted(p for p in (REPO / "tests").glob("test_*.py") if p.name != me)
    hits = [f"{p.relative_to(REPO).as_posix()}:{n}: {line.strip()[:140]}"
            for p in files for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1) if DRIVER.search(line)]
    ctx.check(f"{len(hits)} test lines still open or read the Agents panel:\n    " + "\n    ".join(hits), not hits)


@test
def test_the_word_test_sees_what_it_must(ctx: Ctx):
    for said in ('data-testid="agents-attention"', "<AttentionChip />", ".ag-attn-chip", "Attention · 2", "Agents: Attention",
                 "(answer it in Studio: Agents, Attention)", "toggleAttention()", "useAttentionKey();", "agents-attention-close"):
        ctx.check(f"the pattern sees {said!r}", WORDS.search(said) is not None)
    for other in ("Attention 2", "Session: Attention", "session-attention", "fleet-attention-list", "useAttentionWord",
                  "useAttentionKeys", "AttentionDetail"):
        ctx.check(f"the pattern does not see {other!r}", WORDS.search(other) is None)
    src = ('"""(answer it in Studio: Agents, Attention) in a docstring."""\n'
           'def f():\n    """Agents, Attention again."""\n    return "(answer it in Studio: Agents, Attention)"\n')
    got = [t for _n, t in _strings(src) if WORDS.search(t)]
    ctx.check(f"the Python scan reads the string constant and no docstring, got {got}", got == ["(answer it in Studio: Agents, Attention)"])
    for line, hit in (('[data-testid=agents-attention]', True), ('"[data-panel=\\"fleet-attention\\"]"', True),
                      ("data-testid=fleet-attention-list", False), ("'fleet-attention', 'session-attention'", False)):
        ctx.check(f"the driver pattern {'sees' if hit else 'does not see'} {line!r}", bool(DRIVER.search(line)) is hit)


@test
def test_the_scope_holds(ctx: Ctx):
    _hits, _used, seen = scan()
    ctx.check(f"the scan read at least 100 UI files, 40 docs files and 100 Python files, got {seen}",
              seen["ui"] >= 100 and seen["docs"] >= 40 and seen["py"] >= 100)


@test
def test_what_stays_stays(ctx: Ctx):
    for rel in ("routes/agents/AttentionChip.tsx", "routes/agents/attention.ts", "routes/help-live.ts", "styles/agents-live.css"):
        ctx.check(f"{rel} is gone", not (UI / rel).exists())
    session = (UI / "routes" / "session" / "Session.tsx").read_text(encoding="utf-8")
    line = next((ln for ln in session.splitlines() if 'panel("session-attention"' in ln), "")
    ctx.check(f"Session's Attention button counts what waits: {line.strip()[:200]!r}", "useCount: useAttentionWord" in line)
    att = (UI / "routes" / "fleet" / "Attention.tsx").read_text(encoding="utf-8")
    ctx.check("Session's Attention keeps its drawer (AttentionDetail)", "export function AttentionDetail" in att)
    ctx.check("and its keys (useAttentionKeys defined and called)",
              re.search(r"function useAttentionKeys\b", att) is not None and len(re.findall(r"\buseAttentionKeys\(", att)) >= 2)
    sel = next((ln for ln in att.splitlines() if "closest(" in ln and "data-panel" in ln), "")
    ctx.check(f"the keys listen in Session's drawer only: {sel.strip()[:160]!r}",
              '[data-panel="session-attention"]' in sel and "fleet-attention" not in sel)


@test
def test_every_skip_line_still_matches_something(ctx: Ctx):
    _hits, used, _seen = scan()
    idle = [f"{SKIP[i][0]} /{SKIP[i][1]}/ ({SKIP[i][2]})" for i in range(len(SKIP)) if i not in used]
    ctx.check("every skip line matches a line it keeps: " + "; ".join(idle), not idle)
    ctx.check("every skip line says its reason", all(len(why) > 10 for _g, _r, why in SKIP))


def _doc(rel: str) -> str:
    return " ".join((REPO / rel).read_text(encoding="utf-8").split())


def _docstring(rel: str) -> str:
    return " ".join((ast.get_docstring(ast.parse((REPO / rel).read_text(encoding="utf-8"))) or "").split())


@test
def test_the_docs_say_where_the_count_and_the_queue_are(ctx: Ctx):
    """3.6.0.5 r (R7): the docs say the truth after the cut."""
    panels = _doc("docs/STUDIO-live-panels.md")
    ctx.check("STUDIO-live-panels.md: the button in Session's view bar counts what waits",
              "its button in Session's view bar shows how many wait" in panels)
    for gone in ("chip in Agents' bar", "| `A` | Agents |", "on the Agents icon in the rail", "inside the Attention queue",
                 "The palette's Agents group**: Attention", "(the agent on the Map, the run"):
        ctx.check(f"STUDIO-live-panels.md no longer says {gone!r}", gone not in panels)
    ctx.check("STUDIO-live-panels.md: an agent's ask opens on the run's drawing in Session's Live drawer",
              "its box on the run's drawing in Session's Live drawer" in panels)
    live = _doc("docs/STUDIO-live.md")
    ctx.check("STUDIO-live.md names no attention chip and no Agents' Attention",
              "attention chip" not in live and "Agents' Attention" not in live)
    ctx.check("SUBAGENTS.md names no Map's chip", "Map's chip" not in _doc("docs/SUBAGENTS.md"))
    ctx.check("STUDIO-security.md names no help-live.ts", "help-live.ts" not in _doc("docs/STUDIO-security.md"))
    for rel in ("halo_harness/agent/bg_pickup.py", "halo_harness/studio/live_api.py"):
        ctx.check(f"{rel}'s docstring names no attention chip", "attention chip" not in _docstring(rel))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="removed attention chip"))
