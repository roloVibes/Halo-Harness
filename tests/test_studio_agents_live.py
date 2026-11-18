"""tests.test_studio_agents_live -- Halo 3.6.0.2 R52: Agents -> 4 · Live, in headless Chrome as a first-time user (driver
tests/helpers/studio_agents_live.py over the session rig and the live rig; skipped without Chrome; the Linux VM and CI
only). The pure half of the doors (urlDoor, viewOf, a replay on the Map, the live panels' doors) is
tests/test_agents_door.py, run in node everywhere.

1. the old door `?mode=agents&view=live` opens 4 · Live, its tab pressed; the switch reads
   `1 · Agents | 2 · Workflows | 3 · Map | 4 · Live`; the Live part holds its shell (the session's T-state line from
   truth.ts, its status line, the frame reserved for the drawing) in its own workspace `agents-live`; the dot sits on
   4 · Live while a session runs, never on 3 · Map; C -> Map, L -> Live, 3 -> Map, 4 -> Live; Live is remembered as the
   tab used last; the palette lists `Agents: 4 · Live` with its key 4 and Enter lands on Live;
2. R56 (decision 4): while a session he has talked to is open (here: between turns), Alt+2 opens Agents on 4 · Live
   whatever the tab used last, and Agents' help says so; a Studio-started session with no message yet (T10) does not
   count: Agents opens on the tab used last (2 · Workflows); this is decision 4's rewrite of
   tests/test_studio_session.py's `test_alt_keys_and_agents_opens_on_the_map` (there now `..._opens_on_live`);
2b. the coordinator's ruling on R56: a page loaded on Agents with no `view=` says "Reading the sessions." and draws no
   view until the session list is read, then opens on Live (a session he talked to open) or the tab used last (only a
   T10 one open), and no other view is drawn first;
3. R56: once Agents has drawn its opening tab it never moves by itself: busy, idle, busy frames leave it on Live;
4. R34: Live draws the map the chosen session follows (shop), left to right, lit, read-only, never amber, whatever map
   3 · Map has open;
5. R12: nothing in Live moves under the pointer while rows and a hand-off arrive; the change is drawn when it leaves;
6. R3: the picker lists other machines' sessions; one picked says T9 and nothing is fetched;
7. R57: what the agents say and do, line by line, is Live's right drawer titled Feed (WORDS.feed), for Live's session,
   opened by his hand; a click on a box in Live sets it to that box; 3 · Map has no feed and no "What they think and
   say"; Run a goal opens in the Map's own right drawer, titled by the page, its button holding still (3.6.0.3 B: History
   left; the drawer's own button opens Run a goal's form); an
   agent's "open" door (the palette's "Agents: follow agent ...") lands on Live's Feed for that agent.
8. R55 R24 R33: 3 · Map is the plan -- one quiet line (L1-L3) in a row reserved from the first draw, box W marked
   "running now in {session}", nothing lit or amber; the picker's "· running in" / "· new sessions" and the switch
   "New sessions run on this"; the hand switch's receipt S13 naming the session; a build heard while away opens next
   visit, one heard on the Map says L4 and waits, the same map is re-read in place (tests/helpers/studio_map_quiet.py);
   at 1280 x 800 the quiet line coming and going never moves the drawing; his pick of a map stands over the tab's own
   first open answered late.
Run: python -m tests.test_studio_agents_live
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.driver_got import got as driver_got  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
_RUN: dict = {}
FOUR = ["1 · Agents", "2 · Workflows", "3 · Map", "4 · Live"]
OPENS = "Agents opens on Live while a session is open, else on the tab used last."  # R56's words in its help


def _got(ctx: Ctx) -> dict:
    slow = {"HALO_STUDIO_SLOW_MS": os.environ["HALO_STUDIO_SLOW_MS"]} if os.environ.get("HALO_STUDIO_SLOW_MS") else None
    return driver_got(ctx, "tests.helpers.studio_agents_live", why="Agents -> Live is driven in headless Chrome", cache=_RUN, timeout=600,
                      env=slow)


@test
def test_old_live_door_and_l_key_open_live(ctx: Ctx):
    d = _got(ctx)
    ctx.check(f"?mode=agents&view=live opens Live, got {d.get('door')!r}", d.get("door") == "live")
    ctx.check(f"its tab pressed, got {d.get('pressed')!r}", d.get("pressed") == "true")
    ctx.check(f"four tabs, got {d.get('switch')}", d.get("switch") == FOUR)
    ctx.check(f"the Live part shown with its shell, in its own workspace, got {d.get('shown')} {d.get('workspace')!r}",
              d.get("shown") is True and d.get("workspace") == "agents-live")
    truth = d.get("truth") or ["", ""]
    ctx.check(f"the session's T-state line (T1), got {truth}", truth[0] == "T1" and str(truth[1]).startswith("This session runs on shop, as it started at "))
    ctx.check(f"the status line and the reserved frame, got {d.get('status')} {d.get('frame')}", d.get("status") is True and d.get("frame") is True)
    ctx.check(f"the dot on 4 · Live while a session runs, not on 3 · Map, got {d.get('dot')} {d.get('map_dot')!r}",
              d.get("dot") == ["1", "4 · Live"] and d.get("map_dot") == "")
    ctx.check(f"the keys: C -> Map, L -> Live, 3 -> Map, 4 -> Live, got {d}",
              d.get("key_c") == "map" and d.get("key_l") == "live" and d.get("key_3") == "map" and d.get("key_4") == "live")
    ctx.check(f"Live remembered as the tab used last, got {d.get('remembered')!r}", d.get("remembered") == "live")
    ctx.check(f"the palette's line with its key, got {d.get('palette')} (first {d.get('palette_first')!r})",
              d.get("palette") == [["Agents: 4 · Live", "4"]])
    ctx.check(f"Enter lands on Live, got {d.get('palette_to')!r}", d.get("palette_to") == "live")
    ctx.check(f"the driver ran every step, got {d.get('failed')!r}", not d.get("failed"))



@test
def test_alt_keys_and_agents_opens_on_live(ctx: Ctx):
    d = _got(ctx)
    ctx.check(f"R56: a session between turns open, the tab used last 1 · Agents: Alt+2 opens Agents on Live, got {d.get('alt2')!r} {d.get('opens')!r}",
              str(d.get("alt2")).startswith("Agents") and d.get("opens") == "live")
    ctx.check(f"Agents' help says the opening rule, got {d.get('help')!r}", OPENS in str(d.get("help")) and "Agents opens on the Map" not in str(d.get("help")))
    ctx.check(f"Alt+1 comes back to Session, got {d.get('alt1')!r}", str(d.get("alt1")).startswith("Session"))
    ctx.check(f"T10 (Studio-started, no message yet) does not count: the tab used last (2 · Workflows), got {d.get('t10')!r}",
              d.get("t10") == "workflows")
    ctx.check(f"the driver ran every step, got {d.get('failed')!r}", not d.get("failed"))


@test
def test_a_page_load_on_agents_opens_on_live_after_reading_the_sessions(ctx: Ctx):
    d = _got(ctx)
    ctx.check(f"a reload on Agents with a session he talked to open lands on Live, got {d.get('talked')!r}", d.get("talked") == "live")
    ctx.check(f"no other view drawn first, got {d.get('talked_drawn')!r}", d.get("talked_drawn") == ["live"])
    ctx.check(f"'Reading the sessions.' showed while the list was read, got {d.get('talked_reading')!r}", d.get("talked_reading") is True)
    ctx.check(f"only a T10 session open: the tab used last (2 · Workflows), nothing drawn first, got {d.get('t10')!r} "
              f"{d.get('t10_drawn')!r}", d.get("t10") == "workflows" and d.get("t10_drawn") == ["workflows"])
    ctx.check(f"the driver ran every step, got {d.get('failed')!r}", not d.get("failed"))


@test
def test_opening_tab_never_flips_once_drawn(ctx: Ctx):
    d = _got(ctx)
    ctx.check(f"the three frames each read by the page, got {d.get('flip_reads')!r}", (d.get("flip_reads") or 0) >= 3)
    ctx.check(f"R56: busy, idle, busy never move the opening tab: one value, Live, got {d.get('flips')!r}", d.get("flips") == ["live"])
    ctx.check(f"the driver ran every step, got {d.get('failed')!r}", not d.get("failed"))


@test
def test_live_view_follows_the_session_never_amber(ctx: Ctx):
    d = _got(ctx)
    ctx.check(f"3 · Map shows starter, got {d.get('map_shows')!r}", d.get("map_shows") == "starter")
    ctx.check(f"Live draws the session's map shop, >= 6 boxes, got {d.get('drawn')}", (d.get("drawn") or ["", 0])[0] == "shop" and d["drawn"][1] >= 6)
    lefts = d.get("lefts") or [None, []]
    ctx.check(f"left to right: main's box leftmost, two or more columns, got {lefts}",
              lefts[0] is not None and len(lefts[1]) >= 2 and round(lefts[0]) == lefts[1][0])
    ctx.check(f"no connect dot, no label that is a button, got {d.get('dots')} {d.get('label_buttons')}", d.get("dots") == 0 and d.get("label_buttons") == 0)
    ctx.check(f"a label is words (its When), got {d.get('label')!r}", str(d.get("label")).startswith("SPAN:"))
    ctx.check(f"a label's click opens the step-in card for its line, never a When card, got {d.get('card')!r} {d.get('when_cards')}",
              d.get("card") == "line:main>code" and d.get("when_cards") == 0)
    ctx.check(f"nothing amber in Live, got {d.get('amber')}", d.get("amber") == 0)
    tc = d.get("truth_color") or ["", ""]
    ctx.check(f"the truth line is not in --warn, got {tc}", tc[0] and tc[0] != tc[1])
    ctx.check(f"code's box lit and working, got {d.get('code')}", d.get("code") == ["live", "working"])
    ctx.check(f"3 · Map's picker changed afterwards: Live stays on shop, got {d.get('after_map_pick')!r}", d.get("after_map_pick") == "shop")
    ctx.check(f"the driver ran every step, got {d.get('failed')!r}", not d.get("failed"))


@test
def test_live_holds_still_under_the_pointer(ctx: Ctx):
    d = _got(ctx)
    ctx.check(f"the new rows reached the drawing, got {d.get('rows_in')!r}", d.get("rows_in") is True)
    ctx.check(f"the hand-off lights its line in place, got {d.get('lit')!r}", d.get("lit") in ("live", "trace"))
    ctx.check(f"R12: no box moved under the pointer, got {d.get('moved')}", d.get("moved") == [])
    sc = d.get("scroll") or [0, 1]
    ctx.check(f"the scroll stayed, got {sc}", sc[0] == sc[1])
    ctx.check(f"R12: a second session opening shows the picker, got {d.get('pick_before')!r} -> {d.get('pick_after')!r}",
              d.get("pick_before") is False and d.get("pick_after") is True)
    ctx.check(f"R12: ... in the room kept for it: no box and no zoom button moved under the held pointer, got {d.get('moved_on_pick')} "
              f"(held {d.get('held_on_pick')!r})", d.get("moved_on_pick") == [] and d.get("held_on_pick") == "1")
    ctx.check(f"the pointer left: code's box grew to hold its new row, got {d.get('released')!r}", bool(d.get("released")))
    ctx.check(f"the driver ran every step, got {d.get('failed')!r}", not d.get("failed"))


@test
def test_live_picker_other_machine_t9_no_fetch(ctx: Ctx):
    d = _got(ctx)
    opts = d.get("options") or []
    texts = [o[1] for o in opts]
    ctx.check(f"the picker: this machine's session on shop, then nightly · tiers, none disabled, got {opts}",
              any(o[0] != "away-1" and str(o[1]).endswith(" · shop") for o in opts) and ["away-1", "nightly · tiers", False] in opts
              and not any(o[2] for o in opts) and texts.index("nightly · tiers") == len(texts) - 1)
    ctx.check(f"its name, got {d.get('pick_label')!r}", d.get("pick_label") == "Which session")
    ctx.check(f"T9 in section 4's words, got {d.get('t9')}", d.get("t9") == ["T9", "nightly runs on tiers on gpu-box. Its drawing is in that machine's Studio."])
    ctx.check(f"no drawing, got {d.get('boxes')}", d.get("boxes") == 0)
    ctx.check(f"the server's tap sees the page's reads: the local session's map read when it was drawn, got {d.get('gets_drawn')}",
              "crew/map/shop" in (d.get("gets_drawn") or []))
    ctx.check(f"nothing fetched for it (no map read, nothing of away-1, at the server), got {d.get('gets')}", d.get("gets") == [])
    ctx.check(f"R1: a pick in Session (its Open in Agents -> Live) replaces it: Live draws that session, got {d.get('session_pick')!r}",
              d.get("session_pick") in ("T1", "T2", "T3", "T11", "T12"))
    ctx.check(f"the driver ran every step, got {d.get('failed')!r}", not d.get("failed"))


@test
def test_live_has_the_feed_map_does_not(ctx: Ctx):
    d = _got(ctx)
    ctx.check(f"Live's view bar has the Feed's button, closed until pressed, got {d.get('button')}", d.get("button") == ["Feed", "false", False])
    ctx.check(f"its drawer is titled Feed, got {d.get('title')!r}", d.get("title") == "Feed")
    ctx.check(f"THINK, SAY and TALK rows of Live's session, got {d.get('kinds')} {d.get('sids')}",
              {"think", "text", "talk"} <= set(d.get("kinds") or []) and (d.get("sids") or ["", "-"])[0] == d["sids"][1])
    ctx.check(f"a click on code's box in Live sets the Feed to it, and its step-in card opens, got {d.get('filter')!r} {d.get('feed_card')!r}",
              d.get("filter") == "code" and d.get("feed_card") == "box:code")
    ctx.check(f"3 · Map has no feed drawer, got {d.get('map_feed')}", d.get("map_feed") == 0)
    ctx.check(f"nothing says 'What they think and say', got {d.get('map_words')!r}", d.get("map_words") is False)
    ctx.check(f"the Map's own drawer: closed, its button on Run a goal, got {d.get('md_closed')}", d.get("md_closed") == ["Run a goal", False])
    ctx.check(f"Run a goal opens the goal form in the Map's right drawer, titled Run a goal, got {d.get('goal')}", d.get("goal") == ["Run a goal", "Run a goal"])
    ctx.check(f"the goal form's x closes the drawer with it, got {d.get('closed')!r}", d.get("closed") == "closed")
    ctx.check(f"3.6.0.3 B: the drawer's own button opens it on Run a goal's form, never History, got {d.get('by_button')}",
              d.get("by_button") == ["Run a goal", "goal"])
    ctx.check(f"the drawer's button holds still whatever its page, got {d.get('btn_before')} {d.get('goal_btn')} {d.get('button_btn')}",
              d.get("btn_before") == d.get("goal_btn") == d.get("button_btn") and d.get("btn_before"))
    door = d.get("agent_door") or []
    ctx.check(f"an agent's open door from 3 · Map lands on Live's Feed for that agent, got {door} (implementer {d.get('aid')!r})",
              door[:2] == ["live", f"agent:{d.get('aid')}"])
    # batch 4 repair: another machine's agent (its id `main` is this session's main's too) lands on its own session (T9),
    # never on this machine's session with a Feed filtered to an id it does not have
    ctx.check(f"another machine's agent's open door lands on Live of that session, T9, no Feed, got {d.get('away_door')}",
              d.get("away_door") == ["live", "away-1", "T9", None])
    ctx.check(f"the driver ran every step, got {d.get('failed')!r}", not d.get("failed"))


def _q(d: dict, step: str) -> dict:
    return {k.split(".", 1)[1]: v for k, v in d.items() if k.startswith(step + ".")}


@test
def test_map_tab_quiet_line_and_running_workflow_box(ctx: Ctx):
    d = _got(ctx)
    q = _q(d, "quiet")
    title, sid = str(q.get("title")), q.get("sid")
    ctx.check(f"L3 in the reserved row, got {q.get('l3')!r}", re.fullmatch(
        rf"{re.escape(title)} is running the workflow review from this map\. It runs on starter \(the default\), as it started\. Watch it in Live",
        str(q.get("l3"))) is not None)
    ctx.check(f"box check marked running now in {title}, got {q.get('mark')}", q.get("mark") == [sid, f"running now in {title}"])
    ctx.check(f"nothing lit on the Map, got {q.get('lit')}", q.get("lit") == 0)
    ctx.check(f"no session picker, no Show the running map, no Show it, nothing amber, got {q.get('gone')}", q.get("gone") == 0)
    col = q.get("color") or ["", ""]
    ctx.check(f"the quiet line is not in --warn, got {col}", col[0] and col[0] != col[1])
    hp = str(q.get("help"))
    ctx.check(f"Agents' help names 4 · Live and the switch's words, not the old ones, got {hp[:200]!r}",
              "4 · Live" in hp and "New sessions run on this" in hp and "My sessions use this" not in hp and "The map lights up" not in hp)
    ph = str(q.get("panel_help"))
    ctx.check(f"the Map panel's help says the switch in its new words, got {ph!r}",
              "New sessions run on this: new sessions run on this map." in ph and "My sessions use this" not in ph)
    ctx.check(f"[Watch it in Live] lands on 4 · Live on that session, got {q.get('watch')}", q.get("watch") == ["live", sid])
    ctx.check(f"on starter (its own map): L1, got {q.get('l1')!r}", q.get("l1") == f"{title} runs on this map now. Watch it in Live")
    ctx.check(f"the driver ran every step, got {d.get('failed')!r}", not d.get("failed"))


@test
def test_picker_says_running_in_session(ctx: Ctx):
    d = _got(ctx)
    p = _q(d, "picker")
    title = str(p.get("title"))
    fresh, opts = p.get("fresh") or [], p.get("options") or []
    ctx.check(f"a fresh home (crew.map unset): starter running in {title}, no map tagged new sessions, got {fresh}",
              any(o.startswith("starter") and o.endswith(f" · running in {title}") for o in fresh) and not any(o.endswith(" · new sessions") for o in fresh))
    ctx.check(f"crew.map = shop: starter running in {title}, shop new sessions, no 'my sessions use this', got {opts}",
              any(o.startswith("starter") and o.endswith(f" · running in {title}") for o in opts)
              and any(o.startswith("shop") and o.endswith(" · new sessions") for o in opts)
              and not any("my sessions use this" in o for o in opts + fresh))
    ctx.check(f"the switch on for shop, its words, got {p.get('switch')}", p.get("switch") == ["true", "New sessions run on this"])
    ctx.check(f"two sessions on starter, got {p.get('two')!r}", str(p.get("two")).endswith(" · running in 2 sessions"))
    ctx.check(f"the driver ran every step, got {d.get('failed')!r}", not d.get("failed"))


@test
def test_hand_switch_receipt_is_s13(ctx: Ctx):
    d = _got(ctx)
    r = _q(d, "receipt")
    title = str(r.get("title"))
    ctx.check(f"the receipt is S13 naming the open session, Undo beside it, got {r.get('s13')}",
              r.get("s13") == [f"{title} keeps running on starter (the default), as it started. Start a new session to run on shop.", True])
    ctx.check(f"with no open session: R36's words, got {r.get('none')!r}", r.get("none") == "New sessions run on ship-it.")
    ctx.check(f"the driver ran every step, got {d.get('failed')!r}", not d.get("failed"))


@test
def test_away_it_opens_on_the_built_map(ctx: Ctx):
    d = _got(ctx)
    a = _q(d, "away")
    ctx.check(f"the frame on Session writes the map to open next, got {a.get('last')!r}", a.get("last") == "review-flow")
    ctx.check(f"no map fetched for it, got {a.get('fetched')}", a.get("fetched") == [])
    ctx.check(f"the section is still Session, got {a.get('section')!r}", str(a.get("section")).startswith("Session"))
    ctx.check(f"Alt+2, 3 opens 3 · Map on review-flow, got {a.get('opened')!r}", a.get("opened") == "review-flow")
    ctx.check(f"the driver ran every step, got {d.get('failed')!r}", not d.get("failed"))


@test
def test_on_another_map_it_says_and_waits(ctx: Ctx):
    d = _got(ctx)
    w = _q(d, "waits")
    title = str(w.get("title"))
    ctx.check(f"L2, one session, got {w.get('l2_one')!r}",
              w.get("l2_one") == f"{title} runs on starter (the default), as it started; new sessions run on this map. Watch it in Live")
    ctx.check(f"L2, two sessions, got {w.get('l2_two')!r}",
              w.get("l2_two") == "2 sessions run on other maps, as they started; new sessions run on this map. Watch them in Live")
    ctx.check(f"L4 in the reserved row, got {w.get('notice')!r}",
              re.fullmatch(rf"review-flow was just built in {re.escape(title)} at \d{{1,2}}[:.]\d{{2}}.*\. Open it", str(w.get("notice"))) is not None)
    ctx.check(f"no box moved, got {w.get('moved')}", w.get("moved") == [])
    st = w.get("still") or ["", False, ""]
    ctx.check(f"the switcher still shop, the When card open, the section unchanged, got {st}",
              st[0] == "shop" and st[1] is True and str(st[2]).startswith("Agents"))
    ctx.check(f"[Open it] opens review-flow, the notice gone, got {w.get('opened')!r}", w.get("opened") == "review-flow")
    ctx.check(f"the driver ran every step, got {d.get('failed')!r}", not d.get("failed"))


@test
def test_notice_row_reserved_canvas_still(ctx: Ctx):
    d = _got(ctx)
    w = _q(d, "waits")
    tops = [w.get("top_empty"), w.get("top_l2"), w.get("top_l2_two"), *(w.get("top_l4") or [None, None])]
    ctx.check(f"the canvas top: the row empty, L2 (one, two), before and with L4, got {tops}",
              all(isinstance(x, (int, float)) for x in tops) and max(tops) - min(tops) <= 0.5)
    ctx.check(f"the driver ran every step, got {d.get('failed')!r}", not d.get("failed"))


@test
def test_quiet_line_never_moves_the_drawing_at_1280(ctx: Ctx):
    d = _got(ctx)
    s = _q(d, "still")
    for name in ("shop", "starter"):
        tops = s.get(name) or []
        ctx.check(f"{name}: the canvas top with the quiet line, without the session, with it again (1280 x 800), got {tops}",
                  len(tops) == 3 and all(isinstance(x, (int, float)) for x in tops) and max(tops) - min(tops) <= 0.5)
        gaps = s.get(f"{name}_gaps") or []
        ctx.check(f"P4 batch 12: {name}: nothing in the top line is an unseen copy, no visible gap (with and without the "
                  f"session; [hidden, gap, a Replay part, the plan's offset] each), got {gaps}",
                  len(gaps) == 3 and all(isinstance(g, list) and g[0] == 0 and g[1] is False for g in gaps))
        ctx.check(f"3.6.0.3 B (R-B8): {name}: the top line has no Replay slot, offer, line or data-lit, and its first control "
                  f"sits at the row's left edge, got {gaps}",
                  len(gaps) == 3 and all(isinstance(g, list) and g[2] is False and g[3] == 0 for g in gaps))
    ctx.check(f"the driver ran every step, got {d.get('failed')!r}", not d.get("failed"))


@test
def test_latest_map_pick_wins(ctx: Ctx):
    d = _got(ctx)
    r = _q(d, "race")
    ctx.check(f"the tab's first open was answered after his pick, got {r.get('served')!r}", r.get("served") is True)
    ctx.check(f"in that ORDER: his pick drawn, then the first open answered, got {r.get('order')!r}",
              r.get("order") == ["his pick drawn", "first open answered"])
    ctx.check(f"his pick (shop) still open after the late answer for starter, got {r.get('after')}", r.get("after") == ["shop", True])
    ctx.check(f"the driver ran every step, got {d.get('failed')!r}", not d.get("failed"))


@test
def test_same_map_rereads_keeping_the_when_card(ctx: Ctx):
    d = _got(ctx)
    r = _q(d, "reread")
    ctx.check(f"the new box drawn, got {r.get('drawn')!r}", r.get("drawn") == "extra")
    ctx.check(f"the When card still open on main -> code, got {r.get('card')!r}", r.get("card") == "When does main hand work to code?")
    ctx.check(f"the zoom kept, got {r.get('zoom_before')} {r.get('zoom_after')}", r.get("zoom_before") == r.get("zoom_after") and r.get("zoom_before"))
    ctx.check(f"no notice for the open map, got {r.get('notice')!r}", r.get("notice") is False)
    ctx.check(f"the driver ran every step, got {d.get('failed')!r}", not d.get("failed"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
