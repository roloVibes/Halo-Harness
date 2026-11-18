"""tests.test_removed_replays -- Halo 3.6.0.3 B (Z6): replays and History left Halo, and a test keeps it so. The word
Grep of the decided text, case-insensitive:

    replay|scrubber|halo-replay|\\bHistory\\b|\\bCompare\\b|Back to now|What happened|\\bclip\\b

over the files of SCOPE, minus SKIP. SKIP is data: (a glob of the file, a regex of the line, the reason), one line per
thing that keeps its word for a reason of its own (a browser API, a CSS keyword, a wire key, a pinned test id, another
sense of the word). A skip excuses only the span its regex matches: that span is cut out of the line and the rest is
looked at again, so a word beside a kept one (`data-testid="history-report-replay" title="Replay ..."`) is still seen.
A skip that excuses nothing fails the test, so the list cannot rot.

Z4 batch 4 (this file's first scope) is Studio's UI source, halo_harness/studio/ui/src (.ts, .tsx, .css; the built
bundle is not in it). Z4 batches 5 and 6 widen SCOPE to halo_harness/ (Python, templates with both glossaries and the
first-run pack), README.md and docs/ (not docs/harness/, plans/, CHANGELOG.md, tests/), and add their skip lines
(R-B3's list, the retired-verb line of Z12 ...).
Run: python -m tests.test_removed_replays
"""
from __future__ import annotations

import fnmatch
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
WORDS = re.compile(r"replay|scrubber|halo-replay|\bHistory\b|\bCompare\b|Back to now|What happened|\bclip\b", re.I)

# (a folder of the repo, the file patterns read in it)
SCOPE = [("halo_harness/studio/ui/src", ("*.ts", "*.tsx", "*.css"))]

UI = "halo_harness/studio/ui/src/"
# (a glob of the file, relative to the repo; a regex of the line; the reason it keeps its word)
SKIP = [
    (UI + "lib/agentsDoor.ts", r'q\.get\("replay"\)\) return \{ view: "map"',
     "Z7: an old replay link (`&replay=<id>`) picks 3 · Map; the one line that reads it"),
    (UI + "routes/agents/store.ts", r'q\.(has|delete)\("replay"\)|`&replay=<id>`',
     "Z7: where the door is read, the old link's `replay=` (and its `at=`) leaves the address, nothing said"),
    (UI + "**", r"\bhistory\.(replaceState|state)\b",
     "the browser's History API (history.replaceState drops a door's words from the address), not Halo's History"),
    (UI + "routes/session/promptDraft.ts", r"history",
     "prompt history: the Prompt box's sent prompts per session, Up / Down walk them (kept in this browser)"),
    (UI + "routes/session/PromptComposer.tsx", r"history",
     "prompt history: Up / Down walk this session's sent prompts (promptDraft.ts)"),
    (UI + "routes/session/promptStore.ts", r"History \(promptDraft\.ts\)",
     "prompt history (promptDraft.ts), per session"),
    (UI + "routes/help-session.ts", r"Up / Down walk this session's history",
     "prompt history: the Prompt panel's help on its Up / Down keys"),
    (UI + "routes/session/CostComposition.tsx", r"history",
     "the conversation so far, a part of a prompt's composition (the wire key `history` of the session row)"),
    (UI + "routes/fleet/types.ts", r"history: number",
     "the conversation so far, a part of a prompt's composition (the wire key `history`)"),
    (UI + "styles/session.css", r'data-part="history"',
     "the composition bar's part for the conversation so far"),
    (UI + "routes/crew/builderStore.ts", r"\bhistory\b",
     "the builder's conversation so far, sent with each ask (`builder/ask`'s `history` key)"),
    (UI + "routes/orchestra/types.ts", r"history: LaneStep\[\]",
     "a lane's history, a wire key of a goal run's lane (each state it went through)"),
    (UI + "routes/crew/run/RunInspector.tsx", r"lane\??\.history",
     "a lane's history, a wire key of a goal run's lane"),
    (UI + "routes/fleet/pstore.ts", r"One lane's history",
     "a lane's history: each state from the moment it began"),
    (UI + "routes/fleet/AgentHistory.tsx", r'live/history',
     "the route `live/history` that Session's LAST SESSIONS list reads (Z6 names it `fleet/history`; Studio reads live/history)"),
    (UI + "routes/fleet/AgentHistory.tsx", r"\bhistory: |s\.history\b",
     "Session's LAST SESSIONS list, its field `history` in the panels' store (fleet/pstore.ts)"),
    (UI + "routes/fleet/pstore.ts", r"^\s*history: ",
     "Session's LAST SESSIONS list, the panels' store field `history` (read from live/history)"),
    (UI + "**", r"fleet-(agent-)?history(-run|-export)?\b|fa-history",
     "the test ids fleet-history-* / fleet-agent-history and the class .fa-history of Session's LAST SESSIONS list"),
    (UI + "**", r"history-report",
     "the goal run report page's test ids history-report-* (kept by batch 1; other tests pin them)"),
    (UI + "styles/model-select.css", r"clip-path",
     "the CSS property clip-path"),
    (UI + "styles/map-down.css", r"text-overflow: clip",
     "the CSS keyword text-overflow: clip (package A's file)"),
    (UI + "routes/crew/live/ReportCard.tsx", r"WHAT FAILED AND WHAT HAPPENED NEXT",
     "the report card's own heading, the same as `halo report` prints (## What failed and what happened next)"),
]


def _files():
    for folder, pats in SCOPE:
        root = REPO / folder
        for p in sorted(root.rglob("*")):
            if p.is_file() and any(fnmatch.fnmatch(p.name, pat) for pat in pats):
                yield p.relative_to(REPO).as_posix(), p


def _left(rel: str, line: str, used: "set[int] | None" = None) -> str:
    """The line with the span of every skip of this file cut out (a skip that cut a word is marked used)."""
    for i, (glob, rx, _why) in enumerate(SKIP):
        if not fnmatch.fnmatch(rel, glob):
            continue
        cut = re.sub(rx, " ", line)
        if used is not None and len(WORDS.findall(cut)) < len(WORDS.findall(line)):
            used.add(i)
        line = cut
    return line


def scan() -> "tuple[list[str], set[int]]":
    hits: list[str] = []
    used: set[int] = set()
    for rel, p in _files():
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if WORDS.search(line) and WORDS.search(_left(rel, line, used)):
                hits.append(f"{rel}:{n}: {line.strip()[:160]}")
    return hits, used


@test
def test_the_word_test_sees_what_it_must(ctx: Ctx):
    for said in ("Replay it on the map", "the scrubber", "a .halo-replay file", "in History.", "History's list", "Compare two runs",
                 "Back to now", "What happened", "Export a clip"):
        ctx.check(f"the pattern sees {said!r}", WORDS.search(said) is not None)
    for other in ("historyStore", "AgentHistory", "clipboard", "comparer", "eclipse"):
        ctx.check(f"the pattern does not see {other!r}", WORDS.search(other) is None)


@test
def test_a_skip_excuses_only_its_own_words(ctx: Ctx):
    # (a file, a line a skip of that file touches, whether a word must still be seen)
    for rel, line, seen in (
        (UI + "routes/crew/run/RunReport.tsx", '<Button data-testid="history-report-replay" title="Replay it">', True),
        (UI + "routes/crew/run/RunReport.tsx", '<Button data-testid="history-report-x" title="Replay">', True),
        (UI + "routes/fleet/AgentHistory.tsx", 'data-testid="fleet-history-replay">replay</button>', True),
        (UI + "routes/agents/store.ts", 'toast("this replay is gone"); q.delete("replay");', True),
        (UI + "routes/fleet/AgentHistory.tsx", 'title="History" onClick={() => api("live/history")}', True),
        (UI + "routes/crew/run/RunReport.tsx", '<Button data-testid="history-report-export">', False),
        (UI + "routes/fleet/AgentHistory.tsx", 'data-testid="fleet-history-export">export</button>', False),
        (UI + "routes/agents/store.ts", '    q.delete("replay");', False),
        (UI + "lib/agentsDoor.ts", '  if (word === "agents" && q.get("replay")) return { view: "map", word };', False),
    ):
        got = WORDS.search(_left(rel, line)) is not None
        ctx.check(f"{rel.rsplit('/', 1)[-1]}: {line.strip()!r} is {'a hit' if seen else 'kept'}, got {'a hit' if got else 'kept'}",
                  got == seen)


@test
def test_studio_names_no_replay_and_no_history(ctx: Ctx):
    hits, _used = scan()
    sep = "\n    "
    ctx.check(f"{len(hits)} lines name a replay, the scrubber, History, Compare, Back to now, What happened or a clip:"
              + sep + sep.join(hits[:80]), not hits)


@test
def test_every_skip_line_still_matches_something(ctx: Ctx):
    _hits, used = scan()
    idle = [f"{SKIP[i][0]} /{SKIP[i][1]}/ ({SKIP[i][2]})" for i in range(len(SKIP)) if i not in used]
    ctx.check("every skip line matches a line it keeps (a skip that matches nothing is taken out): " + "; ".join(idle), not idle)
    ctx.check("every skip line says its reason", all(len(why) > 10 for _g, _r, why in SKIP))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="removed replays"))
