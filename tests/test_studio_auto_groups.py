"""tests.test_studio_auto_groups -- Halo 3.6.0.5 (package b, batch 5): Auto's own groups as a person sees them, in headless
Chrome (tests/helpers/studio_auto_groups_draw.py; on the Linux VM, never on the owner's PC). No model is called.

1. On Auto (the row says map_plain) Session's Live drawer and Agents -> Live draw main alone, then one named box per piece
   of work in its own colour (never a state's), a new one below the last, the first not moving; a workflow run with no
   step frames shows its member; in Agents -> Live the groups stand right of main and a line into a group has no label.
2. Main's line into a group lights while a member works, then stays as a trace weighing min(3, members); a map_hop frame
   lights nothing on Auto (B12a).
3. A group's head and members grow, never clip: no ellipsis, nothing under 12 px; the block takes the drawer's row.
4. Five groups: colour five is colour one; the names differ.
5. Hover a member: G4 ("Why this model: ..."); its card the same line; a group's card a row per live member with Pause and
   Stop; main's hover on Auto: G5 from the row's map_agents.
6. (batch 6) The slot names a working group out of sight ("↓ {name} · working ...") in Session and in Agents -> Live, holds
   still, and its press brings the head into view; on his map Agents -> Live has no slot. A group card's [Open in Agents
   -> Live] puts the head at the top within 1 s with its border pulsing 2 s. An ask's Open lands on the asker's group
   (tests/helpers/studio_auto_groups_doors.py).
Run: python -m tests.test_studio_auto_groups
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
_RUNS: dict = {}


def _ran(ctx: Ctx, key: str) -> dict:
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (the drawings need headless Chrome)")
    if not _RUNS:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_auto_groups_draw"], capture_output=True, encoding="utf-8",
                           errors="replace", timeout=400, env=driver_env(REPO), cwd=str(REPO))
        try:
            got = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            got = {}
        _RUNS.update(r=r, got=got)
    if _RUNS["got"].get("skip"):
        raise SkipTest(_RUNS["got"]["skip"])
    r, got = _RUNS["r"], _RUNS["got"]
    ctx.check(f"the driver reached {key}, got {r.returncode} {got.get('failed')!r} {r.stderr[-600:]!r}", got.get(key) is not None)
    return got.get(key) or {}


@test
def test_auto_draws_main_alone_then_named_coloured_groups(ctx: Ctx):
    d = _ran(ctx, "scene")
    alone = d.get("alone") or {}
    ctx.check(f"before anyone: data-map=auto, main the one box, no group, got {alone}",
              alone == {"map": "auto", "boxes": 1, "groups": 0})
    one, probe = (d.get("one") or [{}])[0], d.get("probe") or {}
    ctx.check(f"group 1 named by its task with its three members, got {one}",
              one.get("n") == "1" and one.get("name") == "compare the three reports" and one.get("members") == 3
              and one.get("counts") == "3 agents · 3 working" and one.get("why", "").startswith("3 researchers on kimi-k3"))
    ctx.check(f"a member reads who: description over model · state, got {one.get('lines')}",
              (one.get("lines") or [[]])[0] == ["researcher: read report A", "kimi-k3 · working"])
    ctx.check(f"its border is --group-1, no state's colour, got {one.get('border')} {probe}",
              one.get("border") == probe.get("--group-1") and one.get("border") not in [probe.get(v) for v in ("--accent", "--warn", "--ok", "--bad")])
    ctx.check(f"main's box holds no rows of its helpers (they are the groups' members), got {d.get('mainRows')}", d.get("mainRows") == 0)
    two = {g.get("n"): g for g in d.get("two") or []}
    g1, g2, g3 = two.get("1") or {}, two.get("2") or {}, two.get("3") or {}
    ctx.check(f"group 1 did not move by a pixel, got {one.get('rect')} -> {g1.get('rect')}", one.get("rect") == g1.get("rect"))
    r1, r2 = g1.get("rect") or [0, 0, 0, 0], g2.get("rect") or [0, 0, 0, 0]
    ctx.check(f"group 2 'fix the login bug' below group 1, got {g2.get('name')!r} {r2}",
              g2.get("name") == "fix the login bug" and r2[1] >= r1[1] + r1[3] and g2.get("colour") == "2")
    ctx.check(f"a workflow run with no step frames shows its member, got {g3}",
              g3.get("name") == "workflow Q" and g3.get("members") == 1)
    lv = d.get("live") or {}
    main = lv.get("main") or [0, 0, 0, 0]
    ctx.check(f"Agents -> Live: data-map=auto, the three groups right of main, got {lv}",
              lv.get("map") == "auto" and len(lv.get("groups") or []) == 3
              and all((r or [0])[0] >= main[0] + main[2] for _, r in lv.get("groups") or []))
    ctx.check(f"no label on a line into a group, got {lv.get('labels')}", not any(str(t).startswith("group:") for t in lv.get("labels") or []))


@test
def test_group_line_live_then_trace_on_auto(ctx: Ctx):
    d = _ran(ctx, "lines")
    live, hop2, trace = d.get("live") or {}, d.get("hop2") or {}, d.get("trace") or {}
    ctx.check(f"group 1's line is live while a member works, got {live}", live.get("lit") == "live")
    ctx.check(f"a map_hop frame on Auto lights nothing (group 2 all done: a trace of 1), got {hop2}",
              hop2.get("lit") == "trace" and hop2.get("hops") == "1")
    ctx.check(f"all done: a trace weighing min(3, members), got {trace}", trace.get("lit") == "trace" and trace.get("hops") == "3")


@test
def test_group_head_and_members_grow_never_clip(ctx: Ctx):
    d = _ran(ctx, "grow")
    ctx.check(f"nothing inside a group is cut, got clip {d.get('clip')} cut {d.get('cut')}", d.get("clip") == [] and d.get("cut") == [])
    ctx.check(f"no ellipsis, no text under 12 px, got {d.get('ell')} {d.get('small')}", d.get("ell") == 0 and d.get("small") == 0)
    ctx.check(f"the 60-character name whole, got {d.get('name')!r}", d.get("name") == "compare the three quarterly reports and write the summary now")
    ctx.check(f"five count parts, the failed one in --bad, got {d.get('counts')!r} {d.get('bad')!r}",
              d.get("counts") == "5 agents · 2 working · 1 waiting · 1 done · 1 failed · $0.03" and d.get("bad") == "1 failed")
    ctx.check(f"the why line, got {d.get('why')!r}", bool(d.get("why")))
    ctx.check(f"the child of a child's third line, got {d.get('third')!r}",
              d.get("third") == "started by researcher: compare the three quarterly reports and write the summary now")
    w, left, world = d.get("w") or 0, d.get("left") or 0, d.get("world") or 0
    ctx.check(f"the block on the drawer's full row, got left {left} w {w} world {world}", w > 0 and abs(world - (2 * left + w)) <= 1.5)
    inner = w - 24
    half = (inner - 8) / 2
    want = half if half >= 160 else inner
    ctx.check(f"members as groupBox says ({want} wide), at least 48 px tall, got {d.get('members')}",
              all(abs(m[1] - want) <= 1 and m[2] >= 48 - 0.5 for m in d.get("members") or [[0, 0, 0]]))
    ctx.check(f"the block holds its measured head and members, got h {d.get('h')} inner {d.get('inner')}",
              abs((d.get("h") or 0) - (d.get("inner") or 0) - 24) <= 1.5)


@test
def test_five_groups_colour_five_is_colour_one_names_differ(ctx: Ctx):
    gs = {g.get("n"): g for g in _ran(ctx, "five") or [] if isinstance(g, dict)}
    ctx.check(f"five groups, colours 1 2 3 4 1, got {[g.get('colour') for g in gs.values()]}",
              [gs.get(str(i), {}).get("colour") for i in range(1, 6)] == ["1", "2", "3", "4", "1"])
    ctx.check(f"group 5's border is group 1's, got {gs.get('5', {}).get('border')} {gs.get('1', {}).get('border')}",
              gs.get("5", {}).get("border") == gs.get("1", {}).get("border") and gs.get("1", {}).get("border") != gs.get("2", {}).get("border"))
    ctx.check(f"the names differ, got {[g.get('name') for g in gs.values()]}", len({g.get("name") for g in gs.values()}) == 5)


@test
def test_hover_and_click_say_why_this_model(ctx: Ctx):
    d = _ran(ctx, "hover")
    g4 = d.get("g4") or []
    ctx.check(f"hover a member: G4, got {g4}",
              g4[:3] == ["read report A", "researcher on kimi-k3", "Why this model: code work; tools; mid budget"]
              and len(g4) == 4 and g4[3].startswith("working · $0.01 · "))
    card = d.get("card") or {}
    ctx.check(f"its card: the same why line, the member marked, got {card}",
              card.get("why") == "Why this model: code work; tools; mid budget" and card.get("title") == "researcher" and card.get("sel"))
    grp = d.get("group") or {}
    ctx.check(f"a group's card: a row per live member, each with Pause and Stop, the group marked, got {grp}",
              grp.get("title") == "compare" and grp.get("rows") == [["h1", True, True], ["h2", True, True]] and grp.get("sel"))
    ctx.check(f"main's hover on Auto: G5 from the row's map_agents, got {d.get('g5')}",
              d.get("g5") == ["main · glm-5", "Can hand work to: coder, reviewer, writer"])


@test
def test_new_group_below_the_fold_is_named_in_the_slot(ctx: Ctx):
    d = _ran(ctx, "slot")
    before, after = d.get("before") or {}, d.get("after") or {}
    name = "part 5 of the basket work"
    ctx.check(f"Session: the slot names the fifth group, got {after.get('text')!r}",
              str(after.get("text") or "").startswith(f"↓ {name} · working")
              and after.get("text") in (f"↓ {name} · working", *(f"↓ {name} · working and {n} more below" for n in range(1, 5))))
    ctx.check(f"the slot's rect is the same before and after the words change, got {before.get('rect')} -> {after.get('rect')}",
              bool(before.get("rect")) and before.get("rect") == after.get("rect"))
    press = d.get("press") or {}
    ctx.check(f"its press puts the fifth group's head at the scroll box's top (1 px), got {press}", abs(press.get("d", 99)) <= 1)
    live, empty = d.get("live") or {}, d.get("live_empty") or {}
    ctx.check(f"Agents -> Live: the same words in its slot, got {live.get('text')!r}", str(live.get("text") or "").startswith(f"↓ {name} · working"))
    ctx.check(f"Agents -> Live: the slot and the scroll box hold still when the words go, got {live} -> {empty}",
              bool(live.get("rect")) and live.get("rect") == empty.get("rect") and live.get("scroll") == empty.get("scroll"))
    ctx.check(f"its press brings the head into view, got {d.get('live_press')}", (d.get("live_press") or {}).get("inside") is True)
    his = d.get("his") or {}
    ctx.check(f"on his map Agents -> Live has no slot, got {his}", his.get("slot") is False and "live-below" not in (his.get("frame") or []))


@test
def test_group_card_open_puts_its_head_at_the_top_within_1s(ctx: Ctx):
    d = _ran(ctx, "focus")
    for where in ("session", "live"):
        w = d.get(where) or {}
        top, on, off = w.get("top"), w.get("on"), w.get("off")
        ctx.check(f"from {where}: the head at the top within 1 s of the press, got {w}", top is not None and top <= 1000)
        ctx.check(f"from {where}: data-pulse within 1 s, gone 2 s later (+-0.5 s), got {w}",
                  on is not None and on <= 1000 and off is not None and 1500 <= off - on <= 2500)
    ctx.check(f"Agents -> Live shows it (from Session and staying there), got {d.get('session_view')} {d.get('live_view')}",
              d.get("session_view") == "live" and d.get("live_view") == "live")
    ctx.check(f"the card closed, got {d.get('card')}", d.get("card") is False)


_DOORS: dict = {}


@test
def test_ask_from_a_group_member_opens_on_its_group(ctx: Ctx):
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (the drawings need headless Chrome)")
    if not _DOORS:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_auto_groups_doors"], capture_output=True, encoding="utf-8",
                           errors="replace", timeout=300, env=driver_env(REPO), cwd=str(REPO))
        try:
            _DOORS.update(json.loads(r.stdout.strip().splitlines()[-1]))
        except (ValueError, IndexError):
            _DOORS.update(failed=r.stderr[-600:])
    if _DOORS.get("skip"):
        raise SkipTest(_DOORS["skip"])
    for k in ("ask_live", "ask_session"):
        got = _DOORS.get(k)
        ctx.check(f"{k}: group 2 selected, the reviewer's member card open with the ask's choices, got {got!r} {_DOORS.get('failed')!r}",
                  isinstance(got, list) and got[0] == "member:r3v1e2w0" and got[1] == "reviewer" and got[2] > 0)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
