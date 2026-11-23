"""tests.test_studio_sheet -- Halo 3.6.0.14 OP1 rule O1-5: the box opens in place, as a person sees it, in headless Chrome
(tests/helpers/studio_sheet_steps.py; on the Linux VM, never on the owner's PC). No model is called. The tests assert the
rules (sheetPlace.ts agentsPlace / drawerPlace, useSheet.ts, StepIn.tsx), never a scene's pixel figures: every expected
figure is read from the page (the box, the view, the frame, `data-side`, `data-words`).

1. Agents -> Live: a member of group 2 clicked (S3's twelve helpers in seven groups): the sheet 440 wide (the view less 16 at most) at the member's top-left
   ("corner"), or its top-right when 440 would pass the view's right ("right"), lifted till its foot is 8 inside the view.
2. Session's drawer at its narrowest: 8 from the frame's left, the frame less 16 wide, 6 under its box when 240 fit below,
   else its side's rule.
3. No other `[data-box]` / `[data-member]` rect moves over 0.5 px from before the click through the open, a tool change
   and an ask (Agents -> Live; in Session's drawer at its narrowest, none beyond what the drawing alone moves on them).
4. The sheet, Pause, Stop, the steer box, the body and NOW hold still across that tool change and that ask; NOW's words
   change, its rows do not.
5. An outside click, Escape, its x and a wheel over the drawing each fold it; a pointer-down on another member opens THAT
   member's sheet.
6. Reduced motion: usable on its first frame, no unfold, no fold, no animation, gone the next frame after Escape; no
   preference: it carries `data-unfold` at its start and is usable after (the hosted runners reduce motion: the module
   emulates both settings itself).
7. A wheel over the body scrolls the body alone (head and action row still); Last said reads one of its forms letter for
   letter.
Run: python -m tests.test_studio_sheet
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
from tests.helpers.studio_session_step_in import sheet_rule  # noqa: E402

test, TESTS = new_registry()
_RUNS: dict = {}
S = r"\d+(?:\s(?:s|min)(?:\s\d+\ss)?)?"  # "{s}"
CLOCK = r"\d{1,2}[:.]\d\d[:.]\d\d(?:\s?[AaPp]\.?\s?[Mm]\.?)?"  # the locale's time with its seconds (R41)
BY = r"(?: by \S(?:.*?\S)?)?"  # 3.6.0.15 F8: " by {name}" when the name read at the click is known
SAID = [rf"Last said{BY} at {CLOCK}: .+", rf"Last said{BY}: .+", rf"Last thought{BY} at {CLOCK}: .+", rf"Last thought{BY}: .+",
        r"Nothing said yet\.", r"Reading what it said\.\.\.", r"Could not read what it said: .+"]
REST = r"The rest is in the session export: Export on Session's Feed, or halo session export \S+\."


def _ran(ctx: Ctx, key: str) -> dict:
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (the drawings need headless Chrome)")
    if not _RUNS:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_sheet_steps"], capture_output=True, encoding="utf-8",
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


def _near(a, b, d: float = 0.5) -> bool:
    return bool(a) and bool(b) and len(a) == len(b) and all(abs(x - y) <= d for x, y in zip(a, b))


def agents_rule(rect, geo) -> tuple:
    """O1-1's Agents place, every figure read from the page: 440 wide (the view less 16 at most); at the box's top-left, or
    its top-right ("right") when 440 would pass the view's right less 8, kept 8 inside the view's left; its height the
    smaller of its words at open and the view less 16; its top the box's, lifted till its foot is 8 inside the view."""
    g = geo or {}
    a, v, side, words = g.get("anchor"), g.get("view"), g.get("side"), g.get("words") or 0
    if not (rect and a and v and words):
        return False, f"nothing to read: {rect} {g}"
    near = lambda x, y: abs(x - y) <= 1.0  # noqa: E731
    left, top, width, h = rect
    vl, vt, vr, vb = v[0], v[1], v[0] + v[2], v[1] + v[3]
    w, hh = min(440, v[2] - 16), min(words, v[3] - 16)
    turn = a[0] + w > vr - 8
    want_left = max(min(a[0] + a[2], vr - 8) - w if turn else a[0], vl + 8)
    want_top = a[1] if a[1] + hh <= vb - 8 else vb - 8 - hh
    want_top = max(want_top, vt + 8)
    ok = side == ("right" if turn else "corner") and near(width, w) and near(h, hh) and near(left, want_left) and near(top, want_top)
    return ok and top + h <= vb - 8 + 1, (f"side {side}, rect {rect}, box {a}, view {v}, words {words}: want left {want_left} top {want_top} "
                                          f"width {w} height {hh} ({'lifted' if want_top != a[1] else 'at the box'})")


@test
def test_the_sheet_opens_at_its_members_corner_in_agents(ctx: Ctx):
    o = (_ran(ctx, "place").get("live") or {}).get("open") or {}
    ctx.check(f"the coder's sheet (group 2) usable, got {o.get('target')!r} {o.get('open')}", o.get("target") == "member:k1" and o.get("open") is True)
    ok, why = agents_rule(o.get("rect"), o.get("geo"))
    ctx.check(f"at its member's corner (or its top-right / lifted by the rule): {why}", ok)


@test
def test_the_sheet_opens_at_its_boxs_side_in_the_drawer(ctx: Ctx):
    """The drawer's rule against the page: 6 under its box when 240 fit below, else its side's place. In this scene
    240 do not fit below the member, so the sheet sits over it: "6 under" itself is proven on numbers by
    tests/test_sheet_place.py test_drawer_sheet_6_under_its_box_when_240_fit_below, not in a browser."""
    d = _ran(ctx, "place").get("session") or {}
    dr, o = d.get("drawer") or [0, 0], d.get("open") or {}
    ctx.check(f"the drawer at its narrowest, got {dr}", len(dr) == 2 and 0 < dr[0] <= dr[1])
    ctx.check(f"its member's sheet usable in the drawer, got {o.get('target')!r} {o.get('open')}",
              o.get("target") == f"member:{d.get('aid')}" and bool(d.get("aid")) and o.get("open") is True)
    ok, why = sheet_rule(o.get("rect"), o.get("geo"))
    ctx.check(f"8 from the frame's left, the frame less 16 wide, at its side's place: {why}", ok)
    g = o.get("geo") or {}
    a, v = g.get("anchor"), g.get("view")
    fits = bool(a and v) and (v[1] + v[3] - 8) - max(a[1] + a[3] + 6, v[1] + 8) >= 240
    ctx.check(f"6 under its box whenever 240 fit below it, got side {g.get('side')!r} (240 fit: {fits})", not fits or g.get("side") == "below")


def _moves(first: dict, got: dict) -> dict:
    """Every box whose rect moved over 0.5 px: its key -> how far (left, top, width, height)."""
    return {k: [round(y - x, 1) for x, y in zip(first.get(k) or [0] * 4, got.get(k) or [0] * 4)]
            for k in set(first) | set(got) if not _near(first.get(k), got.get(k))}


@test
def test_no_other_box_moves_while_the_sheet_is_open(ctx: Ctx):
    """Agents -> Live: no box moves at all. Session's drawer at its narrowest: none moves at the open, and after the tool
    change and the ask none moves beyond what the same two move in the drawing with no sheet open (`alone`, the same
    pointer): there a group's head counts can take a second row ("1 waiting on you", 3.6.0.13), which the sheet does not do."""
    d = _ran(ctx, "place")
    for view in ("live", "session"):
        v = d.get(view) or {}
        first, alone = v.get("before") or {}, v.get("alone") or {}
        ctx.check(f"{view}: the drawing's boxes read before the click, got {len(first)}", len(first) >= 13)
        if view == "session":
            ctx.check(f"session: the drawing alone read too, got {len(alone.get('before') or {})}", len(alone.get("before") or {}) == len(first))
        for at in ("at_open", "at_tool", "at_ask"):
            moved = _moves(first, v.get(at) or {})
            base = {} if view == "live" or at == "at_open" else _moves(alone.get("before") or {}, alone.get(at) or {})
            extra = {k: m for k, m in moved.items() if not _near(m, base.get(k), 0.5)}
            ctx.check(f"{view} {at}: no box moved over 0.5 px by the sheet, got {dict(list(extra.items())[:4])} (the drawing alone: {base})",
                      not extra)


@test
def test_pause_holds_still_across_a_tool_change_and_an_ask(ctx: Ctx):
    d = _ran(ctx, "place")
    for view in ("live", "session"):
        v = d.get(view) or {}
        o, t, a = (v.get(k) or {} for k in ("open", "tool", "ask"))
        ctx.check(f"{view}: NOW's words changed: a tool, then the ask, got {o.get('nowText')!r} {t.get('nowText')!r} {a.get('nowText')!r}",
                  re.fullmatch(rf"Grep · {S}", t.get("nowText") or "") is not None
                  and re.fullmatch(rf"waiting for you · {S}", a.get("nowText") or "") is not None and not (o.get("nowText") or "").startswith("Grep"))
        ctx.check(f"{view}: the ask came into the sheet, got {o.get('asks')} then {a.get('asks')}", (a.get("asks") or 0) > (o.get("asks") or 0))
        ctx.check(f"{view}: Pause and Stop there, got {o.get('pauseText')!r} {o.get('pause')} {o.get('stop')}",
                  o.get("pauseText") == "Pause" and bool(o.get("pause")) and bool(o.get("stop")))
        for part in ("rect", "pause", "stop", "steer", "body", "now"):
            ctx.check(f"{view}: the {part} held still across the tool change and the ask, got {o.get(part)} {t.get(part)} {a.get(part)}",
                      _near(o.get(part), t.get(part)) and _near(o.get(part), a.get(part)))


@test
def test_outside_click_escape_x_and_a_wheel_fold_it(ctx: Ctx):
    d = _ran(ctx, "closers")
    for how in ("outside", "escape", "x", "wheel"):
        g = d.get(how) or {}
        ctx.check(f"{how}: opened again first, then folded by it, got {g}", g.get("opened") is True and g.get("gone") is True
                  and (how not in ("outside", "wheel") or bool(g.get("at"))))
    p = d.get("pick") or {}
    ctx.check(f"a pointer-down on another member opens THAT member's sheet (one sheet), got {p}",
              p.get("first") == "member:k1" and bool(p.get("other")) and p.get("then") == f"member:{p.get('other')}"
              and p.get("open") is True and p.get("sheets") == 1)


@test
def test_reduced_motion_opens_and_folds_at_once(ctx: Ctx):
    d = _ran(ctx, "motion")
    r, n = d.get("reduce") or {}, d.get("no-preference") or {}
    rf = r.get("first") or {}
    ctx.check(f"reduce emulated: usable on its first frame, no animation on it, got {r.get('media')} {rf} {r.get('anims')}",
              r.get("media") is True and rf.get("open") is True and rf.get("anims") == [] and r.get("anims") == 0)
    ctx.check(f"reduce: no unfold and no fold ran, gone the next frame after Escape, got {r.get('adds')} {r.get('next_frame_gone')}",
              "data-unfold" not in (r.get("adds") or []) and "data-fold" not in (r.get("adds") or []) and r.get("next_frame_gone") is True)
    ctx.check(f"no preference: it carried data-unfold at its start, was usable after and folded, got {n}",
              n.get("media") is False and "data-unfold" in (n.get("opened") or []) and "data-open" in (n.get("opened") or [])
              and n.get("gone") is True and "data-fold" in (n.get("adds") or []))


@test
def test_the_body_alone_scrolls_and_last_said_reads_one_form(ctx: Ctx):
    d = _ran(ctx, "body")
    f, a = d.get("first") or {}, d.get("after") or {}
    room = f.get("bodyRoom") or [0, 0]
    ctx.check(f"group 1's sheet, its body longer than its room, got {f.get('target')!r} {room}", f.get("target") == "group:1" and room[0] > room[1] > 0)
    ctx.check(f"a wheel over the body scrolled it, the sheet not, got {f.get('bodyTop')} -> {a.get('bodyTop')}, sheet {a.get('top')}",
              (f.get("bodyTop") or 0) == 0 and (a.get("bodyTop") or 0) > 0 and a.get("top") == 0)
    for part in ("rect", "head", "actions", "body"):
        ctx.check(f"the {part} did not move, got {f.get(part)} {a.get(part)}", _near(f.get(part), a.get(part)))
    said = a.get("said") or []  # its place, and the late answer at the body's end when it came after the open
    ctx.check(f"Last said reads one of its forms letter for letter, got {said}",
              1 <= len(said) <= 2 and all(1 <= len(s) <= 2 and any(re.fullmatch(p, s[0], re.S) for p in SAID)
                                          and (len(s) == 1 or re.fullmatch(REST, s[1]) is not None) for s in said))


@test
def test_pause_on_a_helper_that_waits_on_you_reads_resume_and_a_second_press_resumes(ctx: Ctx):
    """3.6.0.15 F3: Pause says what a press does. On a helper that waits on an ask (it holds only after his answer) the
    press sets a pause: the button reads "Resume" at once, and a second press takes the pause back ("Pause" again);
    the session received pause, then resume. The sheet and its buttons do not move."""
    d = _ran(ctx, "pausing")
    f, m, a = (d.get(k) or {} for k in ("first", "mid", "after"))
    ctx.check(f"the sheet opened on k1 with Pause, got {f.get('target')!r} {f.get('pauseText')!r}",
              f.get("target") == "member:k1" and f.get("pauseText") == "Pause")
    ctx.check(f"after the press it reads Resume while it still waits, got {d.get('resume')} {m.get('pauseText')!r} {d.get('state')!r}",
              d.get("resume") is True and m.get("pauseText") == "Resume")
    ctx.check(f"a second press resumes: Pause again, got {d.get('pause')} {a.get('pauseText')!r}", d.get("pause") is True and a.get("pauseText") == "Pause")
    ctx.check(f"the session received pause, then resume, got {d.get('log')}", d.get("log") == ["pause", "resume"])
    for part in ("rect", "pause", "stop", "steer"):
        ctx.check(f"the {part} did not move, got {f.get(part)} {m.get(part)} {a.get(part)}",
                  _near(f.get(part), m.get(part)) and _near(f.get(part), a.get(part)))


@test
def test_last_said_keeps_naming_the_agent_read_at_the_click(ctx: Ctx):
    """3.6.0.15 F8: Last said names whose words it shows, the name of the row chosen at the click as that row shows it;
    when a row of another name is chosen it keeps naming the agent read, and the click made ONE read of the tail."""
    d = _ran(ctx, "said")
    name, first, then = d.get("name") or "", d.get("first") or [], d.get("then") or []
    ctx.check(f"two names among group 1's rows, got {name!r} and {d.get('other')!r}: {[r.get('text') for r in d.get('rows') or []]}",
              bool(name) and bool(d.get("other")) and d.get("chose") is True)
    pat = rf"Last said by {re.escape(name)} at {CLOCK}: .+"
    ctx.check(f"at the open: 'Last said by {name} at ...', got {first}", bool(first) and re.fullmatch(pat, first[0]) is not None)
    ctx.check(f"another row chosen: the same line, still naming {name}, got {then}", then[:1] == first[:1])
    ctx.check(f"ONE read of the tail at the click, got {d.get('tails')}", d.get("tails") == 1)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
