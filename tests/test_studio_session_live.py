"""tests.test_studio_session_live -- Session's Live column in a real browser
(Halo 3.1.5.0 R3, the owner: "the entire right side on the dashboard
landing page is like scrolling visually seeing everything working in real
time"; headless Chrome through the driver base,
tests/helpers/studio_session_live.py `live`; skipped without one).

Over this harness's real session (a lead, an implementer and a researcher
mid-work) plus three extra agents and scripted feed frames
(tests/helpers/studio_live_rig.py):

1. the default arrangement: Map over Cost on the left, Live the whole right
   side (14 of 24 columns, full height), Agent / Activity / Attention strips;
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
8. tools/capture_session_anim.py --dom: both filmed scenes draw what the
   captures show (the Live lines and their tags, an ask card, the tree and
   its edges, the Cost graphics; the Roles cards glowing, their glyphs, the
   legend's four rows);
9. (3.1.7.0 R1) Fleet's time and KIND lead a tool, a text and a state row,
   stacked under 440 px; a click opens a tool row's whole result.
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
    ctx.check(f"Live: x 10, y 0, 14 of 24 columns, open, got {a.get('session-live')}", (a.get("session-live") or [None])[0] == 10
              and a["session-live"][1] == 0 and a["session-live"][2] == 14 and a["session-live"][4] is False)
    ctx.check(f"Live runs the full height (the tallest panel), got {a}", all((a["session-live"][3] >= v[1] + v[3] - 1) for k, v in a.items() if v and not v[4]))
    ctx.check(f"Map over Cost in the left 10 columns, got {a.get('session-map')} {a.get('session-cost')}",
              (a.get("session-map") or [None])[:3] == [0, 0, 10] and (a.get("session-cost") or [None])[0] == 0
              and a["session-cost"][1] == a["session-map"][3] and a["session-cost"][2] == 10)
    strips = [a.get(k) for k in ("session-agent", "session-activity", "session-attention")]
    ctx.check(f"Agent, Activity, Attention: strips under Cost, got {strips}", all(s and s[4] is True and s[0] == 0 for s in strips)
              and strips[0][1] == a["session-cost"][1] + a["session-cost"][3])
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
    ctx.check(f"the map node shows the tool and its time, got {got.get('node_clock')!r}", re.match(r"Bash \d+s", str(got.get("node_clock") or "")) is not None)
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
def test_follow_pauses_on_scroll_up_and_the_pill_resumes(ctx: Ctx):
    r, got = _driver("live")
    _ran(ctx, r, got)
    ctx.check("with Follow on, the newest line is in view", got.get("at_bottom") is True)
    ctx.check(f"a scroll up pauses it, got {got.get('paused')!r}", got.get("paused") == "paused")
    ctx.check(f"new lines count on the pill while it stays put, got {got.get('pill')!r} {got.get('stayed_up')}",
              re.match(r"↓ \d+ new", str(got.get("pill") or "")) is not None and got.get("stayed_up") is True)
    ctx.check(f"the pill resumes it at the bottom, got {got.get('resumed')!r} {got.get('back_bottom')}",
              got.get("resumed") == "resumed" and got.get("back_bottom") is True)


@test
def test_a_tag_pins_esc_unpins_and_hover_lights_the_node(ctx: Ctx):
    r, got = _driver("live")
    _ran(ctx, r, got)
    ctx.check(f"a tag click pins its agent: only its lines, the Steer box, got {got.get('pinned')} {got.get('pinned_only')} {got.get('pinned_steer')}",
              got.get("pinned") == got.get("res_key") and got.get("pinned_only") is True and got.get("pinned_steer") is True)
    ctx.check(f"Esc shows everyone again, got {got.get('unpinned')!r} ({got.get('everyone_back')} agents)",
              got.get("unpinned") == "everyone" and (got.get("everyone_back") or 0) >= 4)
    ctx.check(f"hovering a line lights that agent's node, got {got.get('hover_node')} for {got.get('pinned')}",
              got.get("hover_node") == got.get("res_key") and got.get("hover_off") == "off")


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
def test_the_committed_gifs_loop_at_1500x900_under_3mb(ctx: Ctx):
    for name in ("studio-session.gif", "studio-roles-live.gif"):
        path = REPO / "docs" / "media" / name
        ctx.check(f"docs/media/{name} exists", path.is_file())
        if not path.is_file():
            continue
        f = _gif_facts(path)
        ctx.check(f"{name}: a looping GIF89a at 1500 x 900, 24 frames or more, at most 3 MB, got {f} {path.stat().st_size} bytes",
                  f["sig"] == b"GIF89a" and (f["w"], f["h"]) == (1500, 900) and f["loop"] and f["frames"] >= 24 and path.stat().st_size <= 3 * 1024 * 1024)
    for name in ("studio-session.png", "studio-session-live.png", "studio-roles-live.png"):
        path = REPO / "docs" / "media" / name
        ctx.check(f"docs/media/{name}: a PNG under 1 MB", path.is_file() and path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n" and path.stat().st_size < 1024 * 1024)


@test
def test_the_capture_tool_dom_mode_counts_both_scenes(ctx: Ctx):
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found")
    r = subprocess.run([sys.executable, str(REPO / "tools" / "capture_session_anim.py"), "--dom"], capture_output=True, encoding="utf-8",
                       errors="replace", timeout=500, env=driver_env(REPO), cwd=str(REPO))
    try:
        got = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        got = {}
    ctx.check(f"it ran, got {r.returncode} {r.stderr[-400:]!r}", r.returncode == 0 and "session" in got)
    s, ro = got.get("session") or {}, got.get("roles") or {}
    ctx.check(f"Session: one Live column, its lines each tagged, an ask card, got {s}",
              s.get("session-live") == 1 and (s.get("session-live-line") or 0) >= 8 and s.get("session-live-tag") == s.get("session-live-line")
              and (s.get("session-live-ask") or 0) >= 1)
    ctx.check(f"the tree: seven agents, an edge into each; the Cost graphics, got {s}",
              s.get("fleet-node") == 7 and s.get("fleet-edge") == 7 and s.get("session-cost-context") == 1 and s.get("session-cost-spark") == 1)
    ctx.check(f"Roles: the lineup's seven cards, the working ones glowing with their glyphs, one tier, the legend's four rows, got {ro}",
              ro.get("roles-card") == 7 and (ro.get("live-card") or 0) >= 3 and (ro.get("roles-card-glyph") or 0) >= 3
              and ro.get("roles-tier") == 1 and ro.get("roles-glow-legend-row") == 4)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
