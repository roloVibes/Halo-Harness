"""tests.test_studio_sheet_acts -- Halo 3.6.0.15 OP2 rule O2-7: the box acts, as a person sees it, in headless Chrome
(tests/helpers/studio_sheet_acts_steps.py; on the Linux VM, never on the owner's PC). No model is called. The sheet that
opens at a helper's box has a MODEL block (O2-5) that reads GET crew/agent-model (O2-2) and writes through POST
crew/agent-model and its Undo (O2-3); every word is compared with the product's own constants (studio/crew_model_api.py,
studio/crew_live_api.py), every figure read from the page.

1. test_each_kind_reads_its_line (O2-2, O2-5): MAIN, MINE, SHIPPED, ROUTED, BUILT-IN, MADE-UP, PACK, CLAUDE, each from its
   member's sheet (main from main's): the line letter for letter in the now form (`use_now` true, reduced motion) and the
   later form (false, no preference); ROUTED's first line; PACK and CLAUDE with no picker; Edit for MINE, Make for the
   made kinds.
2. test_a_groups_sheet_draws_no_model_block (the coordinator's ruling F): no block, no MODEL request.
3. test_a_pick_saves_and_undo_puts_back (O2-3, MINE): the picker folds open IN the body, a pick reads "Saved: ...", the
   file holds the pick; Undo reads "Put back: ...", the file byte-equal to before.
4. test_a_pick_makes_and_undo_takes_back (O2-3, BUILT-IN Judge): "Made judge, ..."; Undo: "Taken back: judge is gone.",
   the file gone.
5. test_edit_and_make_open_the_form (O2-5, O2-6): Edit in Agents opens his agent in the Agents form; Make it an agent fills
   it ("Built from {helper} on {model}, ..."), nothing written; from Agents -> Live and from Session's drawer.
6. test_mains_door (O2-3, ruling R7): a terminal, none, a refused ref ("Not switched: {first line}."), a busy session
   (refused before the door: nothing sent through it).
7. test_the_sheet_waits_for_the_model_read (O2-5): the GET held past 1 s: the sheet opens without it, the block lands at
   the body's end with `data-late`, nothing above it moved.
8. test_the_picker_never_folds_the_sheet (O2-5): a click in the folded picker and Escape in its search box leave the sheet
   open; Escape after the picker closed folds it.
Run: python -m tests.test_studio_sheet_acts
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from halo_harness.studio import crew_model_api as K  # noqa: E402
from halo_harness.studio.crew_live_api import BUILT  # noqa: E402
from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
_RUNS: dict = {}
RUN = "or:vendor/fast"  # the scene's model (tests/helpers/studio_sheet_acts_steps.py RUN)
MADE_UP = "count-lines-basket"  # crew_live_api.name_for("Count the lines in basket.py")


def _ran(ctx: Ctx, key: str) -> dict:
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (the sheet needs headless Chrome)")
    if not _RUNS:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_sheet_acts_steps"], capture_output=True, encoding="utf-8",
                           errors="replace", timeout=900, env=driver_env(REPO), cwd=str(REPO))
        try:
            got = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            got = {}
        _RUNS.update(r=r, got=got)
    if _RUNS["got"].get("skip"):
        raise SkipTest(_RUNS["got"]["skip"])
    r, got = _RUNS["r"], _RUNS["got"]
    step = got.get(key) or {}
    ctx.check(f"the driver ran {key}, got {r.returncode} {got.get('failed')!r} {step.get('error')!r} {r.stderr[-600:]!r}",
              bool(step) and not step.get("error"))
    return step


def want(aid: str, now: bool, maps: "dict | None" = None) -> dict:
    """What the block of helper `aid` reads, from the product's constants; `maps`: the rig's maps that name each name (the
    line then adds "Your map {M} names {name}: ..." for the first)."""
    keeps = K.KEEPS.format(model=RUN)
    made = {"edit": None, "make": "Make it an agent", "select": True, "first": None}
    lines = {
        "main": ("MAIN", [K.MAIN_LINE], {"edit": None, "make": None, "select": True, "first": None}),
        "a1": ("MINE", [K.LINES[(K.MINE, now)].format(name="sorter"), keeps], {**made, "edit": "Edit in Agents", "make": None}),
        "a2": ("SHIPPED", [K.LINES[(K.SHIPPED, now)].format(name="planner"), keeps], made),
        "a3": ("ROUTED", [K.LINES[(K.ROUTED, now)].format(name="media-reader", card="media"), keeps],
               {**made, "first": K.FIRST_ROUTED.format(card="media", word="transcribe")}),
        "a4": ("BUILT-IN", [K.LINES[(K.BUILTIN, now)].format(name="judge", X="Judge"), keeps], made),
        "a5": ("MADE-UP", [K.LINES[(K.MADE_UP, now)].format(name=MADE_UP), keeps], made),
        "a6": ("PACK", [K.PACK_LINE.format(name="doc-review--review-docs", P="doc-review")],
               {"edit": None, "make": None, "select": False, "first": None}),
        "a7": ("CLAUDE", [K.CLAUDE_LINE.format(name="helper-x")], {"edit": None, "make": None, "select": False, "first": None}),
    }
    kind, rows, more = lines[aid]
    names = {"a1": "sorter", "a2": "planner", "a3": "media-reader", "a4": "judge", "a5": MADE_UP}
    on = (maps or {}).get(names.get(aid, "")) or []
    if on:
        rows = [rows[0] + (K.MAP_MINE if kind == "MINE" else K.MAP_MADE).format(M=on[0], name=names[aid]), *rows[1:]]
    return {"kind": kind, "rows": rows, "head": "MODEL", **more}


@test
def test_each_kind_reads_its_line(ctx: Ctx):
    d = _ran(ctx, "kinds")
    for form, now in (("now", True), ("later", False)):
        got = d.get(form) or {}
        for aid in ("main", "a1", "a2", "a3", "a4", "a5", "a6", "a7"):
            w, g = want(aid, now, d.get("maps")), got.get(aid) or {}
            seen = {k: g.get(k) for k in w}
            ctx.check(f"{form} {w['kind']}: the block reads letter for letter, got {seen} want {w}", seen == w)


@test
def test_a_groups_sheet_draws_no_model_block(ctx: Ctx):
    g = _ran(ctx, "kinds").get("group") or {}
    ctx.check(f"a group's sheet open, with no MODEL block and no MODEL request, got {g}",
              g.get("target") == "group:1" and g.get("block") is False and g.get("gets") == 0)


@test
def test_a_pick_saves_and_undo_puts_back(ctx: Ctx):
    m = _ran(ctx, "picks").get("mine") or {}
    u, ref = m.get("unfolded") or {}, m.get("ref") or ""
    ctx.check(f"the picker folded open IN the sheet's body, no dialog, got {u}", u.get("fold") is True and u.get("inBody") is True and u.get("dialog") is False)
    ctx.check(f"the session took sorter exactly when it can take (UN's push), got took {m.get('took')} can {m.get('can')}",
              isinstance(m.get("took"), bool) and m.get("took") == m.get("can"))
    saved = (K.SAVED_NOW if m.get("took") else K.SAVED_LATER).format(name="sorter", model=ref)
    p = m.get("picked") or {}
    ctx.check(f"a pick of {ref!r}: {saved!r}, Undo offered, the sheet still open, got {p.get('rows')} {p.get('undo')!r} {m.get('sheet_open')}",
              bool(ref) and p.get("rows") == [saved] and p.get("undo") == "Undo" and m.get("sheet_open") is True)
    ctx.check(f"his file holds the pick, got {m.get('file_model')!r}", bool(ref) and m.get("file_model") == ref)
    un = m.get("undone") or {}
    ctx.check(f"Undo: {K.PUT_BACK.format(name='sorter', old='auto')!r}, Undo gone, got {un.get('rows')} {un.get('undo')!r}",
              un.get("rows") == [K.PUT_BACK.format(name="sorter", old="auto")] and un.get("undo") is None)
    ctx.check(f"his file byte-equal to before, got {m.get('bytes_back')}", m.get("bytes_back") is True)


@test
def test_a_pick_makes_and_undo_takes_back(ctx: Ctx):
    m = _ran(ctx, "picks").get("made") or {}
    ref = m.get("ref") or ""
    made = (K.MADE_NOW if m.get("took") else K.MADE_LATER).format(name="judge", model=ref)
    p = m.get("picked") or {}
    ctx.check(f"the session took judge exactly when it can take, got took {m.get('took')} can {m.get('can')}",
              isinstance(m.get("took"), bool) and m.get("took") == m.get("can"))
    ctx.check(f"a pick of {ref!r} on Judge: {made!r}, Undo offered, got {p.get('rows')} {p.get('undo')!r}",
              bool(ref) and p.get("rows") == [made] and p.get("undo") == "Undo")
    ctx.check(f"judge's file made on the pick, got {m.get('before')} -> {m.get('after_pick')} model {m.get('file_model')!r}",
              "judge.yaml" not in (m.get("before") or []) and "judge.yaml" in (m.get("after_pick") or []) and m.get("file_model") == ref)
    un = m.get("undone") or {}
    ctx.check(f"Undo: {K.TAKEN_BACK.format(name='judge')!r}, the file gone, got {un.get('rows')} {m.get('after_undo')}",
              un.get("rows") == [K.TAKEN_BACK.format(name="judge")] and m.get("after_undo") == m.get("before"))


@test
def test_edit_and_make_open_the_form(ctx: Ctx):
    d = _ran(ctx, "forms")
    note = BUILT.format(helper="general-purpose", model=RUN)
    for view in ("live", "session"):
        e, m = d.get(f"{view}_edit") or {}, d.get(f"{view}_make") or {}
        ef, mf = e.get("form") or {}, m.get("form") or {}
        ctx.check(f"{view}: Edit in Agents carried him to the Agents form on sorter, got {ef}",
                  ef.get("name") == "sorter" and ef.get("shown") is True and ef.get("view") == "crew")
        ctx.check(f"{view}: Make it an agent filled the form, got {mf}",
                  mf.get("name") == MADE_UP and mf.get("shown") is True and mf.get("view") == "crew" and mf.get("note") == note)
        ctx.check(f"{view}: nothing written by Edit or Make, got {e.get('before')} {e.get('after')} {m.get('before')} {m.get('after')}",
                  e.get("before") == e.get("after") and m.get("before") == m.get("after") and bool(m.get("before")))


@test
def test_mains_door(ctx: Ctx):
    d = _ran(ctx, "door")
    t, n, r, b = (d.get(k) or {} for k in ("terminal", "none", "refused", "busy"))
    for rec in (t, n, r, b):
        o = rec.get("open") or {}
        ctx.check(f"main's block: {K.MAIN_LINE!r}, its picker, got {o.get('kind')} {o.get('rows')} {o.get('select')}",
                  o.get("kind") == "MAIN" and o.get("rows") == [K.MAIN_LINE] and o.get("select") is True)
    rows = lambda rec: (rec.get("picked") or {}).get("rows")  # noqa: E731
    ctx.check(f"a terminal: {K.SWITCHED_TERMINAL!r}, got {rows(t)} {t.get('calls')}",
              rows(t) == [K.SWITCHED_TERMINAL.format(model=t.get("ref"))] and (t.get("calls") or [])[:2] == ["status", "slash"]
              and "model" not in (t.get("calls") or []))
    ctx.check(f"no terminal: {K.SWITCHED_SESSION!r}, got {rows(n)} {n.get('calls')}",
              rows(n) == [K.SWITCHED_SESSION.format(model=n.get("ref"))] and (n.get("calls") or [])[:3] == ["status", "slash", "model"])
    first = f"No model named {r.get('ref')} on this harness"
    ctx.check(f"a refused ref (R7): Not switched with the door's first line, got {rows(r)}",
              rows(r) == [K.NOT_SWITCHED.format(why=first)] and (r.get("picked") or {}).get("undo") is None)
    ctx.check(f"a busy session: {K.IN_A_TURN!r}, nothing sent through the door, got {rows(b)} {b.get('calls')}",
              rows(b) == [K.IN_A_TURN] and b.get("calls") == ["status"])


def _near(a, b) -> bool:
    return bool(a) and bool(b) and len(a) == len(b) and all(abs(x - y) <= 0.5 for x, y in zip(a, b))


@test
def test_the_sheet_waits_for_the_model_read(ctx: Ctx):
    d = _ran(ctx, "late")
    o, a = d.get("at_open") or {}, d.get("after") or {}
    ctx.check(f"the sheet opened while the GET was held, without the block, got held {d.get('held')} block {o.get('block')}",
              d.get("held") == 1 and o.get("block") is False and d.get("released") == 1)
    blk = a.get("block") or {}
    ctx.check(f"the block landed at the body's end, data-late, MINE's line, got {blk.get('late')} last {a.get('last')} {blk.get('kind')}",
              blk.get("late") is True and a.get("last") is True and blk.get("kind") == "MINE")
    before, after = o.get("kids") or [], (a.get("kids") or [])[:-1]
    ctx.check(f"nothing above it moved, got {before} -> {after}",
              len(before) >= 1 and len(before) == len(after) and all(x[0] == y[0] and _near(x[1], y[1]) for x, y in zip(before, after)))


@test
def test_the_picker_never_folds_the_sheet(ctx: Ctx):
    d = _ran(ctx, "picker")
    c, e = d.get("click") or {}, d.get("escape_in_search") or {}
    ctx.check(f"a click in the folded picker: the sheet open, the picker open, its search focused, got {c}",
              c.get("open") is True and c.get("fold") is True and c.get("focus") is True)
    ctx.check(f"Escape in its search box closed the picker, not the sheet, got {e}", e.get("open") is True and e.get("fold") is False)
    ctx.check(f"Escape after the picker closed folded the sheet, got {d.get('escape_after')}", (d.get("escape_after") or {}).get("gone") is True)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
