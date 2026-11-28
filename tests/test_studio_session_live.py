"""tests.test_studio_session_live -- Session's Live column in a real browser
(Halo 3.1.5.0 R3, the owner: "the entire right side on the dashboard
landing page is like scrolling visually seeing everything working in real
time"; headless Chrome through the driver base,
tests/helpers/studio_session_live.py `live`; skipped without one).

Over this harness's real session (a lead, an implementer and a researcher
mid-work) plus three extra agents and scripted feed frames
(tests/helpers/studio_live_rig.py):

1. the arrangement (3.6.0.0 R0a, the stage): Live the main thing, the widest; Map in the left drawer, Cost in the
   right one; Agent / Activity / Attention closed, buttons in the view bar;
2. two agents' lines interleave in arrival order, each tagged with its
   agent's name; an agent's text joins its own recent line;
3. a tool row shows its target, its clock ticks while it runs (the map node
   shows "Bash Ns" too) and it takes its result's first line;
4. Follow is on; a scroll up pauses it, new lines count on the "↓ N new"
   pill, the pill resumes it at the bottom;
5. a tag click pins its agent (only its lines, the Steer box), Esc unpins;
   hovering a line lights that agent's node on the map;
6. an ask lands as an amber card with its A / R / S / O keys; a new agent's
   spawn and a finished agent's hand-back land as their own lines;
7. 1000 more lines keep the DOM at the newest 500, the rest named as older;
8. (3.6.0.0 R5: the capture tool's DOM count of both scenes went with the Roles scene.)
9. (3.1.7.0 R1) Fleet's time and KIND lead a tool, a text and a state row,
   stacked under 440 px; a click opens a tool row's whole result.
10. (3.6.0.17 N2) a running `!` command's row carries its own Stop; a model's tool row none.
11. (3.6.0.23 PV) the objective and the plan chip in the Feed's title bar, the Feed's head unmoved; the plan's list
    opens on a click (the one move), the fold kept across a reload.
Run: python -m tests.test_studio_session_live
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.studio_session_plan import LONG_NOW, LONG_OBJ  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
_RUNS: dict = {}


def _driver(*argv: str) -> "tuple[subprocess.CompletedProcess, dict]":
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (the Live column needs headless Chrome)")
    if argv not in _RUNS:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_session_live", *argv], capture_output=True, encoding="utf-8",
                           errors="replace", timeout=500, env=driver_env(REPO), cwd=str(REPO))
        try:
            info = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            info = {}
        _RUNS[argv] = (r, info)
    r, info = _RUNS[argv]
    if info.get("skip"):
        raise SkipTest(info["skip"])
    return r, info


def _ran(ctx: Ctx, r, got) -> None:
    ctx.check(f"the driver ran, got {r.returncode} {got.get('failed')!r} {r.stderr[-600:]!r}", r.returncode == 0 and "failed" not in got)


@test
def test_the_default_arrangement_gives_live_the_right_side(ctx: Ctx):
    r, got = _driver("live")
    _ran(ctx, r, got)
    a = got.get("arrangement") or {}
    live = a.get("session-live") or ["", 0]
    ctx.check(f"Feed is the main thing and the widest panel, got {a}", live[0] == "main" and all(live[1] > v[1] for k, v in a.items() if k != "session-live"))
    ctx.check(f"Live (the drawing) in the left drawer, Cost in the right one, got {a.get('session-map')} {a.get('session-cost')}",
              (a.get("session-map") or [""])[0] == "left" and (a.get("session-cost") or [""])[0] == "right")
    t = got.get("titles") or {}
    ctx.check(f"3.6.0.2 R35: the main panel reads Feed, the left drawer Live (ids unchanged), got {t}",
              t.get("session-live") == "Feed" and t.get("session-map") == "Live")
    closed = [a.get(k) for k in ("session-agent", "session-activity", "session-attention")]
    ctx.check(f"Agent, Activity, Attention: closed, buttons in the view bar, got {closed}", all(s and s[0] == "closed" for s in closed))
    ctx.check("Follow is on by default", got.get("follow_default") is True)


@test
def test_two_agents_interleave_in_arrival_order_with_their_tags(ctx: Ctx):
    r, got = _driver("live")
    _ran(ctx, r, got)
    order = got.get("order") or []
    ctx.check(f"ALPHA (implementer), BRAVO (researcher), the implementer's tool, in that order, got {order}",
              [o[:2] for o in order] == [["impl", "text"], ["res", "text"], ["impl", "tool"]])
    ctx.check(f"each tagged with its agent's name, got {order}", [o[2] for o in order] == ["implementer", "researcher", "implementer"])
    ctx.check("the researcher's next words joined its own line", got.get("joined") is True)


@test
def test_a_tool_row_ticks_and_takes_its_result(ctx: Ctx):
    r, got = _driver("live")
    _ran(ctx, r, got)
    ctx.check(f"the row names its target, got {got.get('tool_target')!r}", got.get("tool_target") == "git status --short")
    e = got.get("elapsed") or ["", ""]
    secs = [int(m.group(1)) if (m := re.match(r"(\d+)s$", str(x or ""))) else -1 for x in e]
    ctx.check(f"its clock ticks while it runs, got {e}", secs[0] >= 0 and secs[1] >= secs[0] + 2)
    ctx.check(f"it takes its result's first line, got {got.get('result')!r}", str(got.get("result") or "").endswith("M basket.py"))


@test
def test_every_line_leads_with_fleets_time_and_kind_columns(ctx: Ctx):
    r, got = _driver("live")
    _ran(ctx, r, got)
    kinds = [(got.get(k) or ["", ""])[1] for k in ("cols_tool", "cols_text", "cols_state")]
    ctx.check(f"HH:MM:SS and TOOL / TEXT / STATE on a tool, a text and a state row, got {kinds} {got.get('clock_ok')}", kinds == ["TOOL", "TEXT", "STATE"] and got.get("clock_ok") is True)
    ctx.check(f"the tool row reads like Fleet's log, got {got.get('tool_reads')!r}", got.get("tool_reads") == "runs Bash")
    w, n = got.get("wide") or {}, got.get("narrow") or {}
    row = lambda d, *k: max(d[x] for x in k) - min(d[x] for x in k) <= 8  # noqa: E731  (one row: baselines aligned)
    ctx.check(f"wide: time, kind, tag and body on one row, got {w}", bool(w) and row(w, "time", "kind", "tag", "body"))
    ctx.check(f"under 440 px: time, kind, tag on one row, the body under them, full width, got {n}",
              bool(n) and row(n, "time", "kind", "tag") and n["body"] >= n["tag_bottom"] - 1 and n["body_w"] >= 300 and n["body_h"] < 120)


@test
def test_a_tool_row_click_opens_its_whole_result(ctx: Ctx):
    r, got = _driver("live")
    _ran(ctx, r, got)
    ctx.check(f"a landed row with more than one line opens: both lines, got {got.get('tool_more')} {got.get('full')!r}",
              got.get("tool_more") is True and "M basket.py" in str(got.get("full")) and "?? notes.md" in str(got.get("full")))
    ctx.check(f"a second click closes it, got {got.get('full_closed')!r}", got.get("full_closed") == "closed")


@test
def test_a_running_bang_row_carries_stop(ctx: Ctx):
    """3.6.0.17 N2 (a thing that runs needs a way to stop it in every view that shows it): a running `!` command's row in
    the Feed carries its own Stop, as its row in the Prompt panel does (tests/helpers/studio_session_insight.py bang_stop)."""
    r, got = _driver("live")
    _ran(ctx, r, got)
    ctx.check(f"a model's Bash row (toolu_1) carries no Stop, got {got.get('model_row_stops')}", got.get("model_row_stops") == 0)
    ctx.check(f"the running `!` row reads Stop with its title, got {got.get('bang_stop')} {got.get('bang_error', '')}",
              got.get("bang_stop") == ["Stop", "Stop: ends this command now, and a running turn with it (Esc in the terminal does the same)"])
    ctx.check(f"a click asks this session's interrupt, once, got {got.get('bang_calls')}", got.get("bang_calls") == [[got.get("sid"), "interrupt"]])
    ctx.check(f"... and opens nothing, got {got.get('bang_opened')}", got.get("bang_opened") is False)
    run, end = got.get("bang_running") or {}, got.get("bang_ended") or {}
    s, ru = run.get("stop") or {}, run.get("runs") or {}
    ctx.check(f"the Stop is of text height (no taller than the row's words), got {s} {ru}",
              bool(s) and bool(ru) and s.get("height", 99) <= ru.get("height", 0) + 0.5)
    ctx.check(f"when the result lands the Stop is gone, got {end.get('stop')}", bool(end) and end.get("stop") is None)
    same = lambda a, b, *k: bool(a) and bool(b) and all(abs(a[x] - b[x]) <= 0.5 for x in k)  # noqa: E731
    ctx.check(f"the row's first line keeps its height and the elapsed time its place, got {run} {end}",
              same(run.get("runs"), end.get("runs"), "top", "bottom")
              and same(run.get("elapsed"), end.get("elapsed"), "top", "bottom", "right"))
    # the join's repair after the review: the Stop is drawn only on a session of THIS harness (a peer harness's `!` row
    # would post to this Studio's own door, which has no such session and answers 404): the rule's source, both parts
    src = (REPO / "halo_harness" / "studio" / "ui" / "src" / "routes" / "session" / "LiveTool.tsx").read_text(encoding="utf-8")
    ctx.check("the Stop is drawn only when the row's harness is the local one",
              re.search(r"const mine = useFleet\(\(s\) => parseKey\(l\.key\)\.h === localId\(s\)\)", src) is not None
              and re.search(r"isBang\(l\.id\) && !l\.ended && mine && \(", src) is not None)


@test
def test_follow_pauses_on_scroll_up_and_the_pill_resumes(ctx: Ctx):
    r, got = _driver("live")
    _ran(ctx, r, got)
    ctx.check("with Follow on, the newest line is in view", got.get("at_bottom") is True)
    ctx.check(f"a scroll up pauses it, got {got.get('paused')!r}", got.get("paused") == "paused")
    ctx.check(f"new lines count on the pill while it stays put, got {got.get('pill')!r} {got.get('stayed_up')}",
              re.match(r"\d+ new rows? · follow$", str(got.get("pill") or "").strip()) is not None and got.get("stayed_up") is True)
    ctx.check(f"the pill resumes it at the bottom, got {got.get('resumed')!r} {got.get('back_bottom')}",
              got.get("resumed") == "resumed" and got.get("back_bottom") is True)


@test
def test_a_tag_pins_esc_unpins_and_hover_lights_the_node(ctx: Ctx):
    r, got = _driver("live")
    _ran(ctx, r, got)
    ctx.check(f"a tag click pins its agent: only its lines, and opens no Steer box (3.6.0.11: Steer opens it), got {got.get('pinned')} {got.get('pinned_only')} {got.get('pinned_steer')}",
              got.get("pinned") == got.get("res_key") and got.get("pinned_only") is True and got.get("pinned_steer") is False)
    ctx.check(f"Esc shows everyone again, got {got.get('unpinned')!r} ({got.get('everyone_back')} agents)",
              got.get("unpinned") == "everyone" and (got.get("everyone_back") or 0) >= 4)


@test
def test_an_ask_lands_as_a_card_with_its_keys(ctx: Ctx):
    r, got = _driver("live")
    _ran(ctx, r, got)
    ask = got.get("ask") or ["", 0, ""]
    ctx.check(f"the reviewer's ask is an amber card with A / R / S / O, got {ask}",
              ask[0] == "reviewer" and ask[1] == 4 and "git push" in str(ask[2]))


@test
def test_a_spawn_and_a_finished_agent_land_in_the_column(ctx: Ctx):
    r, got = _driver("live")
    _ran(ctx, r, got)
    sp = got.get("spawn_line") or ["", ""]
    ctx.check(f"a new agent's spawn line, tagged with it, naming who spawned it, got {sp}", sp[0] == "linter" and "main spawned it" in str(sp[1]))
    op = got.get("output_line") or ["", ""]
    ctx.check(f"an agent that finishes hands its last words back as a block, got {op}", op[0] == "docs" and op[1].startswith("CHANGES.md"))


@test
def test_a_thousand_lines_keep_the_dom_capped(ctx: Ctx):
    r, got = _driver("live")
    _ran(ctx, r, got)
    ctx.check(f"the newest 500 in the DOM of {got.get('total_lines')}, got {got.get('dom_lines')} in {got.get('flood_s')} s",
              got.get("dom_lines") == 500 and (got.get("total_lines") or 0) >= 1000)
    ctx.check(f"the rest are named as older, in Activity, got {got.get('older')!r}",
              re.match(r"\d+ older lines: the full log is in Activity", str(got.get("older") or "")) is not None)


def _gif_facts(path: Path) -> dict:
    """A GIF's signature, size, loop extension and frame count, read with the stdlib (GIF89a block walk)."""
    b = path.read_bytes()
    out = {"sig": b[:6], "w": int.from_bytes(b[6:8], "little"), "h": int.from_bytes(b[8:10], "little"), "loop": b"NETSCAPE2.0" in b[:4096], "frames": 0}
    i = 13 + (3 * 2 ** ((b[10] & 7) + 1) if b[10] & 0x80 else 0)
    while i < len(b) and b[i] != 0x3B:
        if b[i] == 0x21:  # an extension: its label, then sub-blocks
            i += 2
        elif b[i] == 0x2C:  # an image: its descriptor, its local table, the LZW byte, then sub-blocks
            out["frames"] += 1
            flags = b[i + 9]
            i += 10 + (3 * 2 ** ((flags & 7) + 1) if flags & 0x80 else 0) + 1
        else:
            break
        while i < len(b) and b[i]:
            i += b[i] + 1
        i += 1
    return out


@test
def test_the_objective_and_the_plan_chip_in_the_feed_title_bar(ctx: Ctx):
    """3.6.0.23 PV after the first CI run, the coordinator's ruling (tests/helpers/studio_session_plan.py): the objective
    and the plan chip sit in the Feed panel's title bar from the first draw (the rig's prompt "Ship the basket discount
    fix", "no plan yet"), none of it in the head; the head and the Timeline do not move with no objective, a long one
    (an ellipsis in the bar, its hover whole) or a plan arriving (the list closed); a click opens the list (the one
    move, the objective whole at its top); a change of states keeps its height; the fold survives a reload; a click
    closes it and every place is back."""
    r, got = _driver("live")
    _ran(ctx, r, got)
    f = got.get("plan_first") or {}
    ctx.check(f"the title bar at the first draw: the objective, 'no plan yet' (28 px), no list, nothing in the head, got {f}",
              f.get("bar") is True and f.get("words") == "Ship the basket discount fix" and f.get("chip") == "no plan yet"
              and f.get("list") is False and f.get("in_head") is False and f.get("chip_h") == 28)
    p = got.get("plan_places") or []
    ctx.check(f"the Timeline's top, the head's and the bar's heights hold with no objective, a long one and a plan "
              f"arriving, got {p}", len(p) == 4 and all(x == p[0] for x in p) and (p[0][2] or 0) > 0)
    lo = got.get("plan_long_objective") or {}
    ctx.check(f"a long objective ends with an ellipsis in the bar, its hover whole, got {lo}",
              lo.get("ellipsis") is True and lo.get("ends") == "ellipsis" and lo.get("hover") == LONG_OBJ)
    pa = got.get("plan_arrived") or {}
    ctx.check(f"a plan arriving leaves the list closed, the chip 8 px or more from its neighbours, got {pa}",
              pa.get("list") is False and pa.get("expanded") == "false" and (pa.get("gap") or 0) >= 8)
    o, h = got.get("plan_opened") or [], got.get("plan_heights") or []
    ctx.check(f"a click opens the list (the one move), a change of states keeps the Timeline, got {o} after {p[-1:]}",
              len(o) == 2 and bool(p) and o[0] > p[0][0] and o[1] == o[0])
    oo = got.get("plan_open_objective") or {}
    ctx.check(f"the open list starts with the objective whole, wrapping, got {oo}", oo.get("words") == LONG_OBJ and oo.get("wraps") is True)
    ctx.check(f"the step that turns to 'doing' wraps in its activeForm words (so the height check means the twin), "
              f"got {got.get('plan_now_wraps')!r}", got.get("plan_now_wraps") is True)
    ctx.check(f"a change of states keeps the checklist's height, got {h}", len(h) == 2 and h[0] > 0 and h[0] == h[1])
    ctx.check(f"the chip's hover says the step in progress, got {got.get('plan_hover')!r}", got.get("plan_hover") == "Now: Fixing the discount order")
    ctx.check(f"each step a mark and a word, the one in progress in its activeForm words, got {got.get('plan_rows')}",
              got.get("plan_rows") == [["completed", "✓ done", "Read basket.py"], ["completed", "✓ done", "Fix the discount order"],
                                       ["in_progress", "▸ doing", LONG_NOW]])
    ro = got.get("plan_reload_open") or {}
    ctx.check(f"after a reload the list is still open (the fold kept), got {ro}",
              ro.get("chip") == "Plan 2 of 3" and ro.get("expanded") == "true" and ro.get("list") is True)
    cl = got.get("plan_closed") or {}
    ctx.check(f"a click closes it and every place is back, got {cl} vs {p[:1]}", cl.get("list") is False and bool(p) and cl.get("place") == p[0])
    rc = got.get("plan_reload_closed") or {}
    ctx.check(f"after a reload it is still closed, got {rc}", rc.get("chip") == "Plan 2 of 3" and rc.get("expanded") == "false" and rc.get("list") is False)


@test
def test_the_committed_gifs_loop_at_1500x900_under_3mb(ctx: Ctx):
    for name in ("studio-session.gif",):  # 3.6.0.0 R5: the Roles GIF went with Cast
        path = REPO / "docs" / "media" / name
        ctx.check(f"docs/media/{name} exists", path.is_file())
        if not path.is_file():
            continue
        f = _gif_facts(path)
        ctx.check(f"{name}: a looping GIF89a at 1500 x 900, 24 frames or more, at most 3 MB, got {f} {path.stat().st_size} bytes",
                  f["sig"] == b"GIF89a" and (f["w"], f["h"]) == (1500, 900) and f["loop"] and f["frames"] >= 24 and path.stat().st_size <= 3 * 1024 * 1024)
    for name in ("studio-session.png", "studio-session-live.png"):
        path = REPO / "docs" / "media" / name
        ctx.check(f"docs/media/{name}: a PNG under 1 MB", path.is_file() and path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n" and path.stat().st_size < 1024 * 1024)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
