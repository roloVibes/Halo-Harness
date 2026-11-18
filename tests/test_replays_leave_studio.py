"""tests.test_replays_leave_studio -- Halo 3.6.0.3 B (Z4 batch 4, "Studio, the rest"): the last doors of replays and
History leave Studio's UI. Plain Python over the UI source (the browser halves: tests/test_studio_agents_live.py,
tests/test_studio_report_card.py, tests/test_studio_ui.py; the word test: tests/test_removed_replays.py).

1. Session's Agent panel: no Replay button; each LAST SESSIONS row's "replay" link is "export", that session's Markdown
   export through TraceExport's own fetch-and-save (Z9, R-B9); Record stays, only its hover words lose "replay" (Z1);
2. the palette: no "replay this session on the Map" line; Record's hint is Z1's words; a goal-run worker's line names a
   door that exists; the goal runs' palette group is "Agents" (History left);
3. a goal run's report has no Replay; crew/live/replay.ts and timeline.ts are gone and nothing imports them; types.ts has
   no Replay types;
4. the report card's page: no "(Replay shows every one)" and no "saved replay"; the page shows the whole story from the
   route's `story_all` (Z10 as ruled; the route half is tests/test_report_card.py);
5. an old `replay=` address: agentsDoor.ts keeps its one line (the Map), and where the door is read (agents/store.ts)
   the parameter and the `at=` that came with it leave the address with history.replaceState, nothing said (Z7).
Run: python -m tests.test_replays_leave_studio
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
SRC = Path(__file__).resolve().parent.parent / "halo_harness" / "studio" / "ui" / "src"
ROUTES = SRC / "routes"
RECORD_WORDS = "this session as one HTML page you can open anywhere"  # Z1


def _read(rel: str) -> str:
    return (ROUTES / rel).read_text(encoding="utf-8")


def _code(text: str) -> str:
    """The source without its comments (a `//` after a colon or a quote -- a URL, a string -- is kept)."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(?<![:\"'`])//[^\n]*", "", text)


def _line(text: str, needle: str) -> str:
    return next((ln for ln in text.splitlines() if needle in ln), "")


@test
def test_session_panel_offers_the_export_not_replay(ctx: Ctx):
    src = _read("fleet/AgentHistory.tsx")
    code = _code(src)
    ctx.check("no Replay button (fleet-replay) and no replaySession", "fleet-replay" not in code and "replaySession" not in code)
    ctx.check("no row link fleet-history-replay", "fleet-history-replay" not in code)
    link = _line(code, 'data-testid="fleet-history-export"')
    ctx.check(f"each row has an export link that calls exportTrace(r.session_id), got {link.strip()[:200]!r}",
              "exportTrace(r.session_id)" in link and ">export<" in link)
    ctx.check("exportTrace is TraceExport's own (imported, no second fetch)",
              re.search(r'import \{[^}]*\bexportTrace\b[^}]*\} from "\.\./session/TraceExport"', code) is not None
              and "trace.md" not in code and "fetch(" not in code)
    rec = _line(code, 'data-testid="fleet-record"')
    ctx.check(f"Record's hover words are Z1's, got {rec.strip()[:200]!r}", f'title="{RECORD_WORDS}"' in rec and "record(r.key, true)" in rec)
    ctx.check("the rows' record link still records the row's session (main, no download)",'record(keyOf(here, r.session_id, "main"), false)}>record</button>' in code)
    fetchers = [p.relative_to(SRC).as_posix() for p in SRC.rglob("*.ts*") if "trace.md" in _code(p.read_text(encoding="utf-8"))]
    ctx.check(f"one fetch of a session's export under ui/src, got {fetchers}", fetchers == ["routes/session/TraceExport.tsx"])


@test
def test_a_rows_record_link_has_records_hover_words(ctx: Ctx):
    """3.6.0.3 B (file 10): on a LAST SESSIONS row `export` had hover words and `record` had none."""
    code = _code(_read("fleet/AgentHistory.tsx"))
    link = _line(code, 'record(keyOf(here, r.session_id, "main"), false)')
    ctx.check(f"the row's record link says Record's hover words, got {link.strip()[:200]!r}",
              f'title="{RECORD_WORDS}"' in link and ">record</button>" in link)


@test
def test_the_palette_has_no_replay_line(ctx: Ctx):
    code = _code(_read("fleet/commands.ts"))
    ctx.check("no fleet-replay line and no replaySession", "fleet-replay" not in code and "replaySession" not in code)
    said = re.findall(r'(?:label|hint): (?:"([^"]*)"|`([^`]*)`)', code)
    bad = [a or b for a, b in said if re.search(r"replay|scrubber|\bHistory\b", a or b, re.I)]
    ctx.check(f"no label or hint says replay, scrubber or History, got {bad}", not bad)
    rec = _line(code, 'id: "fleet-record"')
    ctx.check(f"Record's hint is Z1's words, got {rec.strip()[:200]!r}", f'hint: "{RECORD_WORDS}"' in rec and "record(sel.key, true)" in rec)
    run = _code(_read("crew/run/commands.ts"))
    ctx.check("the goal runs' palette group is Agents (History left)", 'group: "History"' not in run and 'group: "Agents"' in run)


@test
def test_the_goal_runs_report_has_no_replay(ctx: Ctx):
    rr = _code(_read("crew/run/RunReport.tsx"))
    ctx.check("RunReport has no Replay button, no openLiveReplay, no onReplayed",
              "history-report-replay" not in rr and "openLiveReplay" not in rr and "onReplayed" not in rr and ">Replay<" not in rr)
    for gone in ("crew/live/replay.ts", "crew/live/timeline.ts"):
        ctx.check(f"{gone} is gone", not (ROUTES / gone).exists())
    importers = [p.relative_to(SRC).as_posix() for p in SRC.rglob("*.ts*")
                 if re.search(r"""from\s+["'][./]*(?:crew/)?(?:live/)?(?:replay|timeline)["']""", p.read_text(encoding="utf-8"))]
    ctx.check(f"nothing imports them, got {importers}", not importers)
    types = _read("crew/models/types.ts")
    ctx.check("types.ts exports no Replay, ReplayMeta, ReplayEvent", re.search(r"export type Replay(Meta|Event)?\b", types) is None)


@test
def test_the_card_page_says_no_replay_and_shows_every_step(ctx: Ctx):
    card = _read("crew/live/ReportCard.tsx")
    code = _code(card)
    ctx.check("no '(Replay shows every one)'", "Replay shows" not in code and "more step" not in code)
    ctx.check("no 'from the saved replay'", "saved replay" not in code)
    ctx.check("the source line reads 'from the record'", '"from the record"' in code or ">from the record" in code)
    data = _code(_read("crew/live/cardData.ts"))
    ctx.check("the card's data reads the route's story_all", "story_all" in data)
    ctx.check("the page draws every step (story_all), not the card's ten", re.search(r"\ball\b|story_all", code) is not None
              and "c.story.map" not in code)


@test
def test_an_old_replay_link_leaves_the_address(ctx: Ctx):
    door = (SRC / "lib" / "agentsDoor.ts").read_text(encoding="utf-8")
    lines = [ln for ln in _code(door).splitlines() if re.search(r"replay", ln, re.I)]
    ctx.check(f"agentsDoor.ts keeps ONE line for replay= (the Map), got {lines}",
              len(lines) == 1 and 'q.get("replay")' in lines[0] and 'view: "map"' in lines[0])
    store = _code(_read("agents/store.ts"))
    ctx.check("agents/store.ts drops replay= and its at= with history.replaceState",
              'delete("replay")' in store and 'delete("at")' in store and "history.replaceState(" in store)
    ctx.check("and the address names the tab it opened (view=map), so a reload opens the Map, not 4 · Live",
              'set("view", "map")' in store)
    ctx.check("and says nothing about it (no toast, no note)", "toast(" not in store)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="replays leave studio"))
