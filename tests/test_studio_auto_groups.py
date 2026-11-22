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
7. (batch 7) Session's slot holds still for the longest name at any drawer width; Agents -> Live renders on a scroll only
   when the slot's words change, drops a focus its first full draw does not place, and restarts the pulse on a second press.
8. (batch 8) Session's slot is sized for a long name of ordinary letters (3.6.0.13 L4: its longest form, at most four of
   its own lines at the default width); Agents ->
   Live's slot follows the window's height with no scroll.
9. (k/batch02) On Auto main's box keeps one height whatever main does, so group 1 under it stands still.
10. (r/batch04, tests/helpers/studio_auto_room.py) On Auto Session's drawing takes the whole room of its drawer from the
   first draw at 1280 x 800 and 1440 x 900, group 1's head in view; on a map of his the released height. A helper's card
   lies inside the drawer and its Send is in view or brought into view by the card's own scroll.
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
    first = (one.get("lines") or [[]])[0]
    ctx.check(f"a member reads who: description over model · state, then NOW (3.6.0.13 L2a: the rig's rows only, no feed "
              f"line: a model reply), got {one.get('lines')}",
              first[:2] == ["researcher: read report A", "kimi-k3 · working"] and len(first) == 3
              and first[2].startswith("waiting for a model reply · "))
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
def test_mains_box_keeps_its_height_on_auto(ctx: Ctx):
    """k/batch02 entry 1: on Auto main's box has the height of its fullest state from the first draw, so group 1 under it
    stands still whatever main does (done, a tool, the Agent tool, thinking with the model wait's clock, waiting on you,
    done again); no word of main's rows is cut."""
    d = _ran(ctx, "mainstill")
    st = d.get("states") or []
    ctx.check(f"six states read, got {[s.get('state') for s in st]}", len(st) == 6)
    says = {s.get("state"): (s.get("row"), s.get("clock")) for s in st}
    ctx.check(f"the states were drawn as driven (the fullest: thinking with 'waiting for a model reply'), got {says}",
              (says.get("thinking") or ("", ""))[0] == "main · working · thinking"
              and (says.get("thinking") or ("", ""))[1].startswith("waiting for a model reply")
              and (says.get("agent") or ("", ""))[0] == "main · working · Agent read report C")
    turns = {s.get("state"): s.get("turn") for s in st}
    ctx.check(f"3.6.0.13 L3: TURN blank before the first turn, then the turn's counts, got {turns}",
              turns.get("done") == "" and turns.get("done again") == "This turn: started 12 helpers · used 14 tools itself")
    first = st[0] if st else {}
    moved = [(s.get("state"), s.get("main"), s.get("one")) for s in st if s.get("main") != first.get("main") or s.get("one") != first.get("one")]
    ctx.check(f"main's rect and group 1's rect have the same four numbers in every state (first {first.get('main')} "
              f"{first.get('one')}), moved: {moved}", bool(first.get("main")) and bool(first.get("one")) and not moved)


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
              d.get("counts") == "5 agents · 2 working · 1 waiting on you · 1 done · 1 failed · $0.03" and d.get("bad") == "1 failed")
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
              and len(g4) == 5 and g4[3].startswith("working · $0.01 · ")
              and g4[4].startswith("Now: waiting for a model reply · "))  # 3.6.0.13 L2a: the hover adds NOW's whole words
    card = d.get("card") or {}
    ctx.check(f"its card: the same why line, the member marked, got {card}",
              card.get("why") == "Why this model: code work; tools; mid budget" and card.get("title") == "researcher" and card.get("sel"))
    grp = d.get("group") or {}
    ctx.check(f"a group's card: a row per live member, each with Pause and Stop, the group marked, got {grp}",
              grp.get("title") == "compare" and grp.get("rows") == [["h1", True, True], ["h2", True, True]] and grp.get("sel"))
    ctx.check(f"main's hover on Auto before its first request: G5 from the row's map_agents, got {d.get('g5')}",
              d.get("g5") == ["main · glm-5", "Can hand work to: coder, reviewer, writer"])
    # 3.6.0.13 L3 (R8): once told, main's hover says the session's counts and the kinds main was told it can start
    ctx.check(f"main's hover once told, got {d.get('told')}", d.get("told") == [
        "main · glm-5", "This session: started 3 helpers · used 4 tools itself", "Told it can start: coder, reviewer, writer"])


@test
def test_new_group_below_the_fold_is_named_in_the_slot(ctx: Ctx):
    d = _ran(ctx, "slot")
    before, after = d.get("before") or {}, d.get("after") or {}
    name = "part 5 of the basket work"
    ctx.check(f"Session: the slot names the fifth group, got {after.get('text')!r}",
              str(after.get("text") or "").startswith(f"↓ {name} · working")
              and after.get("text") in (f"↓ {name} · working", *(f"↓ {name} · working · and {n} more {'group' if n == 1 else 'groups'} below"
                                                                for n in range(1, 5))))
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
    r = d.get("reduced") or {}
    ctx.check(f"with reduced motion the cue stays its 2 s (+-0.5 s) as a still outline, got {r} (reduced: {d.get('reduced_media')})",
              d.get("reduced_media") is True and r.get("on") is not None and r.get("off") is not None
              and 1500 <= r["off"] - r["on"] <= 2500)


@test
def test_live_scroll_renders_only_when_the_slot_changes(ctx: Ctx):
    """b/batch07 entry 3: Agents -> Live on Auto re-renders on a scroll only when the slot's words change; a stored focus
    whose group is not placed at the first full draw is dropped; two presses of Open within the pulse leave one pulse."""
    d = _ran(ctx, "scrolls")
    n = d.get("count") or {}
    ctx.check(f"the rig counts React's commits and scrolled 80 px inside group 3's span, got {n}",
              n.get("hooked") is True and n.get("moved") == 80 and (n.get("span") or 0) > 90)
    ctx.check(f"40 scroll steps add at most 2 commits over 40 idle frames, got {n}", (n.get("scroll") or 0) - (n.get("idle") or 0) <= 2)
    st = d.get("stale") or {}
    ctx.check(f"a focus on a group not placed at the first full draw is dropped: when it comes later nothing jumps or pulses, got {st}",
              st.get("done") is True and st.get("moved") is False and st.get("pulsed") is False)
    tw = d.get("twice") or {}
    presses, states = tw.get("presses") or [], tw.get("states") or []
    offs = [t for t, on in states if not on]
    ctx.check(f"two presses within the pulse, at least 0.5 s apart, got {presses}",
              len(presses) == 2 and 500 <= presses[1] - presses[0] < 2000)
    ctx.check(f"the pulse ends once, about 2 s after the LAST press (it restarted), and is gone, got {states} end {tw.get('end')}",
              len(offs) == 1 and 1800 <= offs[0] - presses[-1] <= 3000 and tw.get("end") is False)


@test
def test_the_slot_holds_still_for_the_longest_group_name(ctx: Ctx):
    """b/batch07 entry 1, b/batch08 entry 1: on Auto Session's slot reserves, from the first draw, the room of its words
    for a long name of ordinary letters (the 60-character sample) with a two-digit count: the slot and the scroll box do
    not move when the sample's words or a 25-character name's appear, at the default drawer width and at its narrowest;
    at the default width the slot is no taller than its twin needs, and the twin (3.6.0.13 L4: the slot's longest form, the
    under form with the sample and 99) needs at most four of the slot's own lines (its line-height read from the page;
    three were asked, four are what the longest form needs at the default drawer width, LV batch 2 repair)."""
    import re
    d = _ran(ctx, "longest")
    sample, short = "compare the three reports and write the summary for the team", "compare the three reports"
    ctx.check(f"the names are 60 and 25 characters, got {d.get('len')} {d.get('short')}", d.get("len") == 60 and d.get("short") == 25)
    for a, b, name in (("first", "named", sample), ("short_first", "short_named", short),
                       ("narrow_first", "narrow_named", sample), ("narrow_short_first", "narrow_short_named", short)):
        x, y = d.get(a) or {}, d.get(b) or {}
        ctx.check(f"{b}: the slot names the group with a two-digit count, got {y.get('text')!r}",
                  re.fullmatch(rf"↓ {re.escape(name)} · working · and \d\d more groups below", str(y.get("text") or "")) is not None)
        ctx.check(f"{a} -> {b}: the slot's rect and the scroll box's rect are equal, got {x} -> {y}",
                  bool(x.get("slot")) and x.get("slot") == y.get("slot") and x.get("scroll") == y.get("scroll"))
    dr = d.get("drawer") or [0, 1]
    ctx.check(f"the drawer was dragged to its narrowest, got {dr}", dr[0] <= dr[1] + 1)
    first = d.get("first") or {}
    slot_h, twin_h = (first.get("slot") or [0, 0, 0, 999])[3], (first.get("twin") or [0, 0, 0, 999])[3]
    wait_h = (first.get("wait") or [0, 0, 0, 0])[3]  # the wait link's own reserved lines (batch 6: 56 px), beside it
    need = max(32, twin_h, wait_h)
    lh = float(first.get("lh") or 0)  # the slot's computed line-height, read from the page (never a constant of a machine)
    ctx.check(f"at the default width the slot ({slot_h} px) is no taller than its twin ({twin_h} px) or the wait link's "
              f"room ({wait_h} px) needs, and the twin is at most four of the slot's lines ({lh} px each)",
              lh > 0 and slot_h <= need + 0.5 and twin_h <= 4 * lh + 0.5)


@test
def test_live_slot_follows_the_view_height(ctx: Ctx):
    """b/batch08 entry 2: on Auto Agents -> Live's slot names what is out of sight right after the window's height
    changes, with no scroll: twelve groups at 1280x800, at 1280x1400 (fewer more below, or nothing), then back. The page's
    interval timers are held by the rig meanwhile (its one-second clock re-renders the drawing, which hid the fault for up
    to a second), so only the view's size can give the slot a new answer."""
    import re
    d = _ran(ctx, "heights")
    first, tall, back = d.get("first") or {}, d.get("tall") or {}, d.get("back") or {}
    more = lambda t: int(m.group(1)) if (m := re.search(r"and (\d+) more groups? below", t or "")) else 0  # noqa: E731
    ctx.check(f"the page's clock is held by the rig (only the view's size can change the slot), got {first.get('hooked')}",
              first.get("hooked") is True)
    ctx.check(f"at 800 the slot names group 12, got {first}", str(first.get("text") or "").startswith("↓ job number 12 · working"))
    ctx.check(f"no scroll at any height, got {first.get('top')} {tall.get('top')} {back.get('top')}",
              first.get("top") == 0 and tall.get("top") == 0 and back.get("top") == 0)
    ctx.check(f"at 1400 the view is taller and the slot says so (fewer more below, or nothing), got {first} -> {tall}",
              (tall.get("h") or 0) > (first.get("h") or 0) and tall.get("text") != first.get("text")
              and (not tall.get("text") or more(tall.get("text")) < more(first.get("text"))))
    ctx.check(f"back at 800: the first reading again, got {back}",
              back.get("text") == first.get("text") and back.get("h") == first.get("h") and back.get("vw") == first.get("vw"))


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


_ROOM: dict = {}
SIZES = ("1280x800", "1440x900")


def _room(ctx: Ctx, key: str) -> dict:
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (the drawings need headless Chrome)")
    if not _ROOM:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_auto_room"], capture_output=True, encoding="utf-8",
                           errors="replace", timeout=400, env=driver_env(REPO), cwd=str(REPO))
        try:
            _ROOM.update(json.loads(r.stdout.strip().splitlines()[-1]))
        except (ValueError, IndexError):
            _ROOM.update(failed=r.stderr[-600:])
    if _ROOM.get("skip"):
        raise SkipTest(_ROOM["skip"])
    ctx.check(f"the room driver reached {key}, got {_ROOM.get('failed')!r}", _ROOM.get(key) is not None)
    return _ROOM.get(key) or {}


def _inside(a, b, slack: float = 1.0) -> bool:
    """Rect `a` ([left, top, width, height]) lies within rect `b`."""
    if not a or not b:
        return False
    return (a[0] >= b[0] - slack and a[1] >= b[1] - slack and a[0] + a[2] <= b[0] + b[2] + slack
            and a[1] + a[3] <= b[1] + b[3] + slack)


def _released(his: dict) -> float:
    """The released rule (3.6.0.2 R11, downFit.viewHeight): the bottom of the last whole row plus the 12 px pad, counted
    from the scroll's top, at most the room; the whole room when not even one row fits."""
    k, room, top, rows = his.get("k") or 1, his.get("room") or 0, his.get("top") or 0, []
    for _, y, h in sorted(his.get("boxes") or [], key=lambda b: b[1]):
        r = next((x for x in rows if abs(x[0] - y) < 0.5), None)
        if r:
            r[1] = max(r[1], y + h)
        else:
            rows.append([y, y + h])
    best = 0.0
    for _, bottom in rows:
        if bottom * k <= top + 0.5:
            continue
        end = (bottom + 12) * k - top
        if end <= room + 0.5:
            best = max(best, end)
    return max(0.0, min(room, best or room))


@test
def test_the_auto_drawing_uses_the_whole_room(ctx: Ctx):
    """r/batch04 entry 1: on Auto, at 1280 x 800 and at 1440 x 900, Session's drawing takes the whole room of its drawer from
    the first draw (main alone, then group 1, then four groups: its rect never moves) and group 1's head is in view; on a
    map of his the scroll box's height is the released rule's."""
    got = _room(ctx, "room")
    for size in SIZES:
        at = got.get(size) or {}
        first = (at.get("alone") or {}).get("box")
        for k in ("alone", "one", "four"):
            r = at.get(k) or {}
            box, fill, slot = r.get("box") or [0, 0, 0, 0], r.get("fill") or [0, 0, 0, 0], r.get("slot") or [0, 0, 0, 0]
            ctx.check(f"{size} {k}: the drawing's box is the whole room (top and bottom on the room's), got box {box} room {fill}",
                      fill[3] > 100 and abs(box[1] - fill[1]) <= 2 and abs(box[1] + box[3] - fill[1] - fill[3]) <= 2)
            ctx.check(f"{size} {k}: the slot stands right under it (the drawer's own gap only), got box {box} slot {slot}",
                      0 <= slot[1] - (box[1] + box[3]) <= 12)
            ctx.check(f"{size} {k}: the box's rect is the one of the first draw, got {box} vs {first}",
                      first is not None and all(abs(p - q) <= 0.5 for p, q in zip(box, first)))
        for k in ("one", "four"):
            r = at.get(k) or {}
            head = r.get("head") or [None, None]
            ctx.check(f"{size} {k}: group 1's name and counts line are inside the visible box, got {head} in {r.get('vis')}",
                      all(_inside(h, r.get("vis")) for h in head))
        ctx.check(f"{size}: four groups drawn, got {(at.get('four') or {}).get('groups')}", (at.get("four") or {}).get("groups") == 4)
    his = got.get("his") or {}
    rule = _released(his)
    ctx.check(f"his map: the scroll box is {his.get('offset')} px, the released rule gives {rule} (room {his.get('room')}, "
              f"boxes {his.get('boxes')})", his.get("boxes") and abs((his.get("offset") or 0) - rule) <= 1)
    ctx.check(f"his map: the released rule stops above the room's foot here (so the rule is what is measured), got {rule} < {his.get('room')}",
              0 < rule < (his.get("room") or 0) - 1)


@test
def test_a_helpers_card_stays_inside_the_drawer(ctx: Ctx):
    """r/batch04 entry 2: at 1280 x 800, 1440 x 900 and a short 1280 x 500, on Auto, a click on a helper of group 1 opens
    its card inside the drawer's content box (its height the smaller of its own 264 px and the room); its Send button is
    in view, or a scroll INSIDE the card brings it into view."""
    got = _room(ctx, "card")
    for size in (*SIZES, "1280x500"):
        at = got.get(size) or {}
        o, s = at.get("open") or {}, at.get("scrolled") or {}
        ctx.check(f"{size}: the helper's card opened, got {o.get('title')!r}", o.get("title") == "researcher")
        if size in SIZES:
            ctx.check(f"{size}: where it fits, the card keeps its own height, got {o.get('card')}", (o.get("card") or [0] * 4)[3] == 264)
        ctx.check(f"{size}: the card lies inside the drawing's content box and the drawer, got {o.get('card')} in {o.get('down')} / {o.get('drawer')}",
                  _inside(o.get("card"), o.get("down")) and _inside(o.get("card"), o.get("drawer")))
        shown = _inside(o.get("send"), o.get("vis")) and _inside(o.get("send"), o.get("down"))
        after = _inside(s.get("send"), s.get("vis")) and _inside(s.get("send"), s.get("down"))
        ctx.check(f"{size}: Send in view ({shown}) or brought into view by the card's own scroll ({after}), got send "
                  f"{o.get('send')} / {s.get('send')} in {o.get('vis')}, scroll {o.get('scroll')} -> {s.get('scroll')}",
                  shown or (after and (s.get("scroll") or [0])[0] > 0))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
