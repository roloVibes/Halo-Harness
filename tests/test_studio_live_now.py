"""tests.test_studio_live_now -- Halo 3.6.0.13 LV rule L7 (with R10 and R4): "Live you can read" as a person sees it, in
headless Chrome (tests/helpers/studio_live_now_steps.py; on the Linux VM, never on the owner's PC). No model is called.
The tests assert the rules (R10), never the scenes' pixel figures: a figure of this machine is read from the page.

L7a (S2, S6)
1. Each NOW kind on a member, letter for letter ("{tool} · {s}", "waiting for a model reply · {s}", "queued · {s}",
   "writing · {s}", "thinking · {s}", "waiting for you · {s}", "done in {span}", "stopped after {span}"), the state words
   ("{model} · queued", "stopped"), the heads ("1 agent · 1 waiting on you" with the --warn edge, "1 agent · 1 stopped"),
   main's NOW ("Agent · {s}") and TURN ("This turn: started 5 helpers · used 4 tools itself"): Session's drawer and
   Agents -> Live.
2. One member queued -> running -> a tool -> waiting -> done keeps one height in Agents -> Live and in Session's drawer at
   its narrowest (L2b: NOW's rows and the state line's held).
3. The pointer resting on the drawing while the clock steps 30 times and a helper joins moves no rect (the helper is
   drawn when the pointer leaves).
4. Reduced motion: a member done and one asking ring nothing and run no animation; with no preference they ring.
L7b (S3, S5)
5. The slot names the group that waits on him out of sight (arrow, tail), "↑" once scrolled past it; its press brings
   the asking member into view.
6. At most four rings, none out of view or under the pointer; a group rings HAND only after the pointer leaves; none
   under the open card.
7. R4: a slot press with the card open folds it before any scroll; the "under the open box" form only folds.
8. S5: at the drawer's narrowest a 39-character tool reads "a tool · {s}" while held at the first height, grows once
   when the pointer leaves, keeps that height through done.
3.6.0.14 O1-2 ruling (4)
9. The card open in Agents -> Live, the section left by its key: the sheet closes and none of its listeners is left.
Run: python -m tests.test_studio_live_now
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
_RUNS: dict = {}
S = r"\d+(?:\s(?:s|min)(?:\s\d+\ss)?)?"  # "{s}": "12 s", "3 min 05 s" (a no-break space allowed)
SPAN = r"\d+[\w\s]*"


def _ran(ctx: Ctx, key: str) -> dict:
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (the drawings need headless Chrome)")
    if not _RUNS:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_live_now_steps"], capture_output=True, encoding="utf-8",
                           errors="replace", timeout=600, env=driver_env(REPO), cwd=str(REPO))
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


def _is(text: str, pattern: str) -> bool:
    return re.fullmatch(pattern, text or "") is not None


S2_NOW = {"r1": rf"Grep · {S}", "r2": rf"waiting for a model reply · {S}", "r3": rf"queued · {S}", "k1": rf"writing · {S}",
          "p1": rf"thinking · {S}", "v1": rf"waiting for you · {S}", "w1": rf"done in {SPAN}", "x1": rf"stopped after {SPAN}"}


@test
def test_s2_each_now_kind(ctx: Ctx):
    d = _ran(ctx, "s2now")
    for view in ("session", "live"):
        v = d.get(view) or {}
        ms, gs, main = v.get("members") or {}, v.get("groups") or {}, v.get("main") or {}
        nows = {k: (ms.get(k) or {}).get("now", "") for k in S2_NOW}
        ctx.check(f"{view}: each member's NOW in its words, got {nows}", all(_is(nows[k], p) for k, p in S2_NOW.items()))
        ctx.check(f"{view}: the queued one's state line '{{model}} · queued', the stopped one's 'stopped', got "
                  f"{(ms.get('r3') or {}).get('state')!r} {(ms.get('x1') or {}).get('state')!r}",
                  (ms.get("r3") or {}).get("state") == "kimi-k3 · queued" and (ms.get("x1") or {}).get("state") == "kimi-k3 · stopped")
        g4, g6 = gs.get("group:4") or {}, gs.get("group:6") or {}
        ctx.check(f"{view}: the asking one's head '1 agent · 1 waiting on you' (its part in --warn), its edge --warn, got "
                  f"{g4.get('counts')!r} {g4.get('warn')!r} {(ms.get('v1') or {}).get('edge')} vs {d.get('warn')}",
                  g4.get("counts") == "1 agent · 1 waiting on you" and g4.get("warn") == "1 waiting on you"
                  and (ms.get("v1") or {}).get("edge") == d.get("warn"))
        ctx.check(f"{view}: the stopped one's head '1 agent · 1 stopped', got {g6.get('counts')!r}", g6.get("counts") == "1 agent · 1 stopped")
        ctx.check(f"{view}: main's NOW 'Agent · {{s}}' and TURN, got {main.get('now')!r} {main.get('turn')!r}",
                  _is(main.get("now", ""), rf"Agent · {S}") and main.get("turn") == "This turn: started 5 helpers · used 4 tools itself")


@test
def test_member_height_holds_from_queued_to_done(ctx: Ctx):
    d = _ran(ctx, "height")
    want = [("queued", rf"queued · {S}"), ("running", rf"waiting for a model reply · {S}"), ("tool", rf"Read · {S}"),
            ("waiting", rf"waiting for you · {S}"), ("done", rf"done in {SPAN}")]
    ctx.check(f"Session's drawer at its narrowest (its least width), got {d.get('drawer')}",
              len(d.get("drawer") or []) == 2 and d["drawer"][0] <= d["drawer"][1])
    for view in ("live", "session"):
        seen = [s or [None, 0, "", ""] for s in d.get(view) or []]
        ctx.check(f"{view}: five states drawn as driven, got {seen}",
                  len(seen) == 5 and all(s[0] == n and _is(s[2], p) for s, (n, p) in zip(seen, want)))
        ctx.check(f"{view}: the state line said '{{model}} · waiting on you', got {[s[3] for s in seen]}",
                  any(s[3] == "mock-model-nine · waiting on you" for s in seen))
        hs = [s[1] for s in seen]
        ctx.check(f"{view}: one height from queued to done, got {hs}", bool(hs) and hs[0] > 0 and len(set(hs)) == 1)


@test
def test_a_resting_pointer_moves_no_rect(ctx: Ctx):
    d = _ran(ctx, "rest")
    for view in ("session", "live"):
        v = d.get(view) or {}
        ctx.check(f"{view}: the drawing held, the new row fetched, the clock stepped 30 times, got {v}",
                  v.get("held") == "1" and v.get("fetched") is True and (v.get("ticks") or 0) >= 30)
        ctx.check(f"{view}: no rect changed while the pointer rested, got {v.get('changed')}", v.get("changed") == [])
        ctx.check(f"{view}: the helper drawn only once the pointer left, got held {v.get('drawn_held')} after {v.get('drawn_after')}",
                  v.get("drawn_held") is False and v.get("drawn_after") is True)


@test
def test_s6_reduced_motion_no_animation(ctx: Ctx):
    d = _ran(ctx, "reduced")
    r, n = d.get("reduce") or {}, d.get("no-preference") or {}
    ctx.check(f"reduce emulated, a member done and one waiting, got {r.get('media')} {r.get('raw')}",
              r.get("media") is True and (r.get("raw") or [])[:2] == ["done", "waiting"])
    ctx.check(f"reduce: no data-ring, no data-rang, no animation on a member, got {r}",
              r.get("ring") == [] and r.get("rang") == [] and r.get("anims") == [])
    ctx.check(f"no preference: the same two ring (the check above is not empty), got {n}",
              n.get("media") is False and sorted(n.get("rang") or []) == ["m1", "m2"])


@test
def test_s3_slot_names_the_waiting_group_arrow_and_tail(ctx: Ctx):
    d = _ran(ctx, "s3slot")
    for view in ("session", "live"):
        v = d.get(view) or {}
        sl, n = v.get("slot") or {}, v.get("below")
        tail = "" if not n else f" · and {n} more group below" if n == 1 else f" · and {n} more groups below"
        ctx.check(f"{view}: the slot names the waiting group below with its tail (the groups wholly below read from the page), "
                  f"got {sl} below {n}", sl.get("text") == f"↓ run the tests · waits on you{tail}" and sl.get("wait") is not None
                  and sl.get("arrow") == "down" and sl.get("group") == "5")
        ctx.check(f"{view}: group 5 out of view, got {v.get('g5')}", (v.get("g5") or {}).get("seen") is False)
    up = d.get("up") or {}
    ctx.check(f"scrolled past it: '↑ run the tests · waits on you', got {up} (window height {d.get('up_height')})",
              (up.get("text") or "").startswith("↑ run the tests · waits on you") and up.get("arrow") == "up" and up.get("wait") is not None)
    ctx.check(f"each press brings the asking member into view, got before {d.get('seen_before')} down {d.get('press')} up {d.get('up_press')}",
              d.get("seen_before") is False and d.get("press") is True and d.get("up_press") is True)


@test
def test_s3_at_most_four_rings_none_hidden(ctx: Ctx):
    d = _ran(ctx, "s3rings")
    first, held, left, ptr = (d.get(k) or {} for k in ("first", "held", "left", "pointer"))
    ctx.check(f"nothing rings on the first draw, got {first.get('rang')}", first.get("rang") == [])
    hm, lm = held.get("members") or {}, left.get("members") or {}
    ctx.check(f"held (pointer on main): researcher-2 FAILED rings, group 1 not yet, the new researcher not drawn, got {held.get('rang')}",
              "r2" in (held.get("rang") or []) and "group:1" not in (held.get("rang") or []) and "r4" not in hm)
    ctx.check(f"the pointer left: group 1 rings HAND, the new researcher drawn, got {left.get('rang')}",
              "group:1" in (left.get("rang") or []) and "r4" in lm)
    for tag, v in (("held", held), ("left", left)):
        ms, gs = v.get("members") or {}, v.get("groups") or {}
        boxes = {**ms, **gs}
        ctx.check(f"{tag}: every ring wholly in view and at most four, got {v.get('rang')}",
                  len(v.get("rang") or []) <= 4 and all((boxes.get(k) or {}).get("seen") for k in v.get("rang") or []))
        ctx.check(f"{tag}: Tester-1 asked out of view: no ring, got {ms.get('t1')}",
                  (ms.get("t1") or {}).get("raw") == "waiting" and not (ms.get("t1") or {}).get("seen") and not (ms.get("t1") or {}).get("rang"))
        ctx.check(f"{tag}: the coder ended: it rings only when in view, got {ms.get('k1')}",
                  (ms.get("k1") or {}).get("raw") == "done" and bool((ms.get("k1") or {}).get("rang")) == bool((ms.get("k1") or {}).get("seen")))
    r1 = (ptr.get("members") or {}).get("r1") or {}
    ctx.check(f"a member under the pointer ends: no ring, then or once the pointer left, got {r1}", r1.get("raw") == "done" and not r1.get("rang"))
    six0, six = d.get("six_before") or {}, d.get("six") or {}
    seen = sorted(((m.get("rect") or [0, 0])[1], k) for k, m in (six0.get("members") or {}).items() if m.get("seen"))
    ctx.check(f"at least five members in view before they end (the window's height chosen so), got {seen}", len(seen) >= 5)
    ms = six.get("members") or {}
    ctx.check(f"six end at once: exactly four ring, the top-most in view, got {six.get('rang')} of {seen}",
              all(m.get("raw") == "done" for m in ms.values()) and sorted(six.get("rang") or []) == sorted(k for _, k in seen[:4]))
    alone, handed = d.get("alone") or {}, d.get("handed") or {}
    ctx.check(f"main drawn alone: nothing rings; its first group drawn: the group rings HAND, got {alone.get('rang')} then "
              f"{handed.get('rang')} of {sorted(handed.get('groups') or {})}",
              alone.get("rang") == [] and not alone.get("groups") and "group:1" in (handed.get("rang") or []))
    f = _ran(ctx, "fold")
    ctx.check(f"a member asking under the open card does not ring, got {f.get('under')} {f.get('under_rang')!r}",
              bool(f.get("under")) and f.get("under_rang") == "")


@test
def test_slot_press_with_the_card_open_folds_before_any_scroll(ctx: Ctx):
    d = _ran(ctx, "fold")
    ctx.check(f"the card open, a group waiting below: the slot says so, got {d.get('slot')}",
              ((d.get("slot") or {}).get("text") or "").startswith("↓ run the tests · waits on you"))
    p = d.get("press") or {}
    ctx.check(f"the press: the drawing scrolled, the card gone at every scroll event and after, got {p}",
              p.get("moved") is True and len(p.get("scrolls") or []) > 0 and not any(p.get("scrolls") or []) and p.get("card") is False)
    us, name = d.get("under_slot") or {}, d.get("under_name") or ""
    ctx.check(f"a member under the open card asks: '{{name}} · waits on you · under the open box', got {us} ({name!r}, {d.get('under_members')})",
              bool(name) and (us.get("text") or "").startswith(f"{name} · waits on you · under the open box") and us.get("arrow") == "under")
    up = d.get("under_press") or {}
    ctx.check(f"its press folds the card and makes no scroll, got {up}", up.get("card") is False and up.get("scrolls") == [] and up.get("moved") is False)


@test
def test_leaving_the_section_by_its_key_closes_the_card(ctx: Ctx):
    """3.6.0.14 O1-2 ruling (4): the card open in Agents -> Live, Alt+<n> to Session (the section stays mounted: no unmount
    and no pointer-down come): the sheet closes, and no listener it added to the document, the window or the drawing is left."""
    lv = _ran(ctx, "fold").get("leave") or {}
    opened = lv.get("opened") or []
    ctx.check(f"the card open: its pointer-down, key and wheel listeners are on, got {lv}",
              bool(lv.get("kbd")) and {"pointerdown", "keydown", "wheel"} <= set(opened))
    ctx.check(f"Session shown by its key: the sheet is gone and none of its listeners is left, got {lv}",
              lv.get("shown") is True and lv.get("sheet") is False and lv.get("left") == [])


@test
def test_s5_held_form_then_one_growth_at_360(ctx: Ctx):
    d = _ran(ctx, "s5held")
    dr = d.get("drawer") or [0, 0]
    ctx.check(f"the drawer at its narrowest, got {dr}", len(dr) == 2 and dr[0] <= dr[1])
    first, held, left, done = d.get("first") or 0, d.get("held") or [0, ""], d.get("left") or [0, ""], d.get("done") or [0, ""]
    ctx.check(f"held (the pointer on the drawing): 'a tool · {{s}}' at the first height, got {first} {held}",
              first > 0 and held[0] == first and _is(held[1], rf"a tool · {S}"))
    ctx.check(f"the pointer left: the whole name, the member grown once, got {left}",
              left[0] > first and _is(left[1], rf"mcp__deckcraft__insert_chart_from_range · {S}"))
    ctx.check(f"it keeps that height through done, got {done}", done[0] == left[0] and _is(done[1], rf"done in {SPAN}"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
