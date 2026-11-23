"""tests.helpers.studio_sheet_acts_steps -- Halo 3.6.0.15 OP2 rule O2-7: the sheet's MODEL block as a person uses it, in
headless Chrome over tests/helpers/studio_live_now_steps.py's rig (this harness's real session A on Auto, its rows set
through GET live by standing in `peers.local_view.sessions` inside the in-process Studio). No model is called. Every name
and figure is invented; the words are compared with the product's own constants by the test.

The scene: main and one group of seven helpers, one of each kind (MINE `sorter`, his file in the scratch home; SHIPPED
`planner`; ROUTED, a general helper Auto sent to its `media` card; BUILT-IN `Judge`; MADE-UP; PACK; CLAUDE).

    kinds    every kind's MODEL block from its member's sheet (main's from main's), the now form (`use_now` true, reduced
             motion) then the later form (false, no preference); a group's sheet: no block, no MODEL request; the
             rig's maps that name each name a pick writes (`store.used_by`: the line's map sentence)
    picks    MINE: the picker folds open in the body, a pick, the line and the file's model; Undo, the line, the file's
             bytes. BUILT-IN Judge: a pick makes `judge`, Undo takes it back (the file gone)
    forms    Edit in Agents (MINE) and Make it an agent (MADE-UP) from Agents -> Live, then from Session's drawer: the form
             they open, its note, the agents folder before and after
    door     main's pick through the door, `studio.live_agents_api.forward` stood in for main's three commands: a terminal,
             none, a refused ref, a busy session (what was sent each time)
    late     the GET held in the page past 1 s: the sheet open without the block, then the block at the body's end
    picker   reduced motion: a click in the folded picker and Escape in its search box leave the sheet open; Escape after
             the picker closed folds it

    python -m tests.helpers.studio_sheet_acts_steps [step ...]
The last stdout line is a JSON object of what it saw.
"""
from __future__ import annotations

import json
import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.studio_auto_groups_draw import LW, RECT  # noqa: E402
from tests.helpers.studio_live_now_steps import LiveNowDriver, frames, go, mk, to_live  # noqa: E402
from tests.helpers.studio_session_map_down import Rows  # noqa: E402
from tests.helpers.studio_session_run import M, _main  # noqa: E402
from tests.helpers.studio_sheet_steps import SHEET, gone, is_open, open_on  # noqa: E402

RUN = "or:vendor/fast"  # every helper's model (invented)
TASK = "Count the lines in basket.py"
GROUP_TASK = "tidy the basket module"
# aid -> (name, spawn.source, more of spawn)
KINDS = {"a1": ("sorter", "crew:yours", {}), "a2": ("planner", "crew:starter", {}),
         "a3": ("general-purpose", "built-in", {"routed": {"word": "transcribe", "card": "media"}}),
         "a4": ("Judge", "built-in", {}), "a5": ("general-purpose", "built-in", {}),
         "a6": ("doc-review--review-docs", "crew:pack", {}), "a7": ("helper-x", "user", {})}
ROOTS = {"live": LW, "session": M}
# the page's GETs of crew/agent-model, counted; held while `window.__modelHold` (released by `window.__modelRelease()`)
WRAP = """(() => { const f = window.fetch.bind(window); window.__modelGets = []; window.__modelHold = false; window.__modelWaits = [];
  window.fetch = (u, init) => { const s = String((u && u.url) || u), m = String((init && init.method) || 'GET').toUpperCase();
    if (m === 'GET' && s.includes('crew/agent-model')) { window.__modelGets.push(s);
      if (window.__modelHold) return new Promise((r) => window.__modelWaits.push(r)).then(() => f(u, init)); }
    return f(u, init); };
  window.__modelRelease = () => { window.__modelHold = false; const w = window.__modelWaits; window.__modelWaits = []; w.forEach((r) => r()); return w.length; };
})()"""
BLOCK = ("((k) => { const b = k?.querySelector('[data-testid=map-step-in-model]'); if (!b) return null; const q = (t) => b.querySelector(`[data-testid=${t}]`);"
         " return { kind: b.dataset.kind || '', late: b.hasAttribute('data-late'), head: b.querySelector('.mp-step-in-model-head')?.textContent || '',"
         " first: q('map-step-in-model-first')?.textContent ?? null, rows: [...(q('map-step-in-model-line')?.querySelectorAll(':scope > p') || [])].map((p) => p.textContent),"
         " select: !!q('map-step-in-model-select'), value: q('map-step-in-model-select')?.dataset.value ?? null,"
         " undo: q('map-step-in-model-undo')?.textContent ?? null, edit: q('map-step-in-model-edit')?.textContent ?? null,"
         " make: q('map-step-in-model-make')?.textContent ?? null, inBody: !!b.closest('[data-testid=map-step-in-body]'),"
         " fold: !!b.querySelector('[data-testid=model-select-fold]'), dialog: !!document.querySelector('[data-testid=model-select-dialog]') }; })")
KIDS = ("((k) => { const b = k?.querySelector('[data-testid=map-step-in-body]'), R = " + RECT + "; return b ? [...b.children].map((e) =>"
        " [e.dataset.testid || e.className || e.tagName, R(e)]) : null; })")
FORM = ("(() => { const n = document.querySelector('[data-testid=\"crew-name\"]'), a = document.querySelector('[data-testid=agents]');"
        " return { name: n ? n.value : null, shown: !!n && n.getClientRects().length > 0, view: a?.dataset.view ?? null,"
        " note: document.querySelector('[data-testid=\"crew-note\"]')?.innerText ?? null }; })()")


def his_sorter(state) -> Path:
    """HIS agent `sorter` (yours), the file a MINE helper runs."""
    folder = Path(state) / "crew" / "agents"
    folder.mkdir(parents=True, exist_ok=True)
    p = folder / "sorter.yaml"
    p.write_text("format: agent/1\nname: sorter\ndoes: Does sorter work.\nmodel: auto\nuses:\n- read\ncareful: ask-changes\n",
                 encoding="utf-8", newline="\n")
    return p


def drop_his(state) -> None:
    for p in (Path(state) / "crew" / "agents").glob("sorter.*"):
        p.unlink()


def yours(state) -> list:
    """The names of his agents' files (yours)."""
    folder = Path(state) / "crew" / "agents"
    return sorted(p.name for p in folder.glob("*")) if folder.is_dir() else []


def scene(rows: Rows, a: str, t0: float) -> list:
    main = _main(rows, a, state="running", current="Agent: tidy the basket module", since=t0, started=t0)
    out = [main]
    for aid, (name, src, more) in KINDS.items():
        k = mk(aid, name, TASK, GROUP_TASK, 1, model=RUN, since=t0)
        k["spawn"] = {**k["spawn"], "source": src, **more}
        out.append(k)
    return out


def on_auto(c, rig, rows: Rows, a: str, b: str, view: str = "live", now: bool = True, w: int = 1440, h: int = 900) -> None:
    """Session's drawer (or Agents -> Live) on A, Auto, the scene drawn; `now`: the row's `use_now`."""
    go(c, rig, rows, a, b, scene(rows, a, time.time() - 40), w=w, h=h)
    rows.set(a, use_now=now)
    c.wait(f"{M}.querySelectorAll('[data-member]').length >= {len(KINDS)}", 20)
    if view == "live":
        to_live(c, 1)
    frames(c, 6)


def box(view: str, aid: str) -> str:
    return f"{ROOTS[view]}.querySelector('[data-box=main]')" if aid == "main" else f"{ROOTS[view]}.querySelector('[data-member={aid}]')"


def blk(view: str) -> str:
    return f"{SHEET[view]}?.querySelector('[data-testid=map-step-in-model]')"


def block(c, view: str) -> dict:
    return c.js(f"({BLOCK})({SHEET[view]})") or {}


def open_box(c, view: str, aid: str) -> dict:
    """The box's sheet open and its MODEL block read (its rows drawn)."""
    c.js(f"{box(view, aid)}.scrollIntoView({{block: 'nearest', inline: 'nearest'}}); 1")
    frames(c, 3)
    open_on(c, view, box(view, aid))
    c.wait(f"!!{blk(view)}?.dataset.kind && {blk(view)}.querySelectorAll('[data-testid=map-step-in-model-line] > p').length > 0", 20)
    return block(c, view)


def close(c, view: str) -> None:
    c.click_on(f"{SHEET[view]}.querySelector('[data-testid=map-step-in-close]')")
    c.wait(gone(view), 15)


def line_is(view: str, start: str) -> str:
    return f"({blk(view)}?.querySelector('[data-testid=map-step-in-model-line]')?.textContent || '').startsWith({json.dumps(start)})"


def field(view: str) -> str:
    return f"{blk(view)}.querySelector('[data-testid=map-step-in-model-select]')"


def trig(view: str) -> str:
    return f"{field(view)}.querySelector('[data-testid=model-select]')"


def fold(view: str) -> str:
    return f"{field(view)}.closest('.msel')?.querySelector('[data-testid=model-select-fold]') || {field(view)}.querySelector('[data-testid=model-select-fold]')"


def refs(c, view: str) -> list:
    return c.js(f"[...{blk(view)}.querySelectorAll('[role=option][data-ref]')].filter((r) => /-row$/.test(r.dataset.testid)).map((r) => r.dataset.ref)") or []


def unfold(c, view: str) -> None:
    """The picker folded open in place by a pointer press on its field (a person's click)."""
    c.wait(f"!!{trig(view)} && !{trig(view)}.disabled", 15)
    c.click_on(trig(view))
    c.wait(f"!!({fold(view)})", 15)


def pick_other(c, view: str) -> str:
    """Unfold the picker (when it is not) and click the first of his models that is not the field's value: its ref."""
    if not c.js(f"!!({fold(view)})"):
        unfold(c, view)
    value = c.js(f"{field(view)}.dataset.value || ''")
    ref = next((r for r in refs(c, view) if r != value), "")
    if not ref:
        raise AssertionError(f"no model to pick other than {value!r}: {refs(c, view)}")
    row = f"{blk(view)}.querySelector('[role=option][data-ref={json.dumps(ref)}]')"
    c.js(f"{row}.scrollIntoView({{block: 'nearest'}}); 1")
    c.click_on(row)
    return ref


def _step(key: str, fn) -> dict:
    """What a step saw, kept when it fails part way (its `error` says where)."""
    out: dict = {}
    try:
        fn(out)
    except Exception as e:  # the test names the step and shows what it saw so far
        out["error"] = f"{type(e).__name__}: {e}"[:500]
    return {key: out}


# ---- kinds ---------------------------------------------------------------------------------------------------------
def kinds(c, rig, rows: Rows, a: str, b: str) -> dict:
    from tests.helpers.chrome_driver import emulate_motion

    def run(out: dict) -> None:
        from halo_harness.crew import store
        his_sorter(rig.state)
        out["maps"] = {n: [u[4:] for u in store.used_by(n, cwd=rig.proj) if u.startswith("map ")]  # the rig's maps that name it
                       for n in ("sorter", "planner", "media-reader", "judge", "count-lines-basket")}
        for form, now, motion in (("now", True, "reduce"), ("later", False, "no-preference")):
            emulate_motion(c, motion)
            on_auto(c, rig, rows, a, b, now=now)
            got = out[form] = {}
            for aid in ("main", *KINDS):
                got[aid] = open_box(c, "live", aid)
                close(c, "live")
        before = c.js("window.__modelGets.length")
        open_on(c, "live", f"{LW}.querySelector('[data-box=\"group:1\"] [data-testid=map-group-name]')")
        c.wait(f"!!{SHEET['live']}?.querySelector('[data-testid=map-step-in-said]')", 15)
        frames(c, 4)
        out["group"] = {"target": c.js(f"{SHEET['live']}.dataset.target"), "block": c.js(f"!!{blk('live')}"),
                        "gets": c.js("window.__modelGets.length") - before}
        close(c, "live")
    try:
        return _step("kinds", run)
    finally:
        emulate_motion(c, "no-preference")


# ---- picks ---------------------------------------------------------------------------------------------------------
def _took(rig, name: str) -> dict:
    """Did session A take `name` to start it at main's next turn (UN's push)? The pick's line says the now form only
    then. `can`: crew.use_now.can_take(session) (this rig's session is not on Auto: it takes nothing, "off")."""
    from halo_harness.crew.use_now import can_take
    pend = getattr(rig.session, "_kinds_pending", None) or {}
    return {"took": name in pend, "can": can_take(rig.session)}


def picks(c, rig, rows: Rows, a: str, b: str) -> dict:
    def run(out: dict) -> None:
        sorter = his_sorter(rig.state)
        raw = sorter.read_bytes()
        on_auto(c, rig, rows, a, b)
        mine = out["mine"] = {"open": open_box(c, "live", "a1")}
        unfold(c, "live")
        mine["unfolded"] = block(c, "live")
        mine["ref"] = pick_other(c, "live")
        c.wait(f"!{line_is('live', 'Picking')} && !{trig('live')}.disabled", 20)
        mine["picked"] = block(c, "live")
        mine["file_model"] = next((ln[7:].strip() for ln in sorter.read_text(encoding="utf-8").splitlines() if ln.startswith("model: ")), None)
        mine.update(_took(rig, "sorter"))
        mine["sheet_open"] = c.js(is_open("live"))
        c.click_on(f"{blk('live')}.querySelector('[data-testid=map-step-in-model-undo]')")
        c.wait(f"!{line_is('live', 'Saved')} && !{line_is('live', 'Not saved')} && !{trig('live')}.disabled", 20)
        mine["undone"] = block(c, "live")
        mine["bytes_back"] = sorter.read_bytes() == raw
        close(c, "live")
        made = out["made"] = {"before": yours(rig.state), "open": open_box(c, "live", "a4")}
        made["ref"] = pick_other(c, "live")
        c.wait(f"!{line_is('live', 'Judge is built')} && !{trig('live')}.disabled", 20)
        made["picked"] = block(c, "live")
        made["after_pick"] = yours(rig.state)
        files = list((Path(rig.state) / "crew" / "agents").glob("judge.*"))
        made["file_model"] = next((ln[7:].strip() for ln in files[0].read_text(encoding="utf-8").splitlines() if ln.startswith("model: ")), None) if files else None
        made.update(_took(rig, "judge"))
        c.click_on(f"{blk('live')}.querySelector('[data-testid=map-step-in-model-undo]')")
        c.wait(f"!{line_is('live', 'Made')} && !{trig('live')}.disabled", 20)
        made["undone"] = block(c, "live")
        made["after_undo"] = yours(rig.state)
        close(c, "live")
    return _step("picks", run)


# ---- forms ---------------------------------------------------------------------------------------------------------
def forms(c, rig, rows: Rows, a: str, b: str) -> dict:
    def run(out: dict) -> None:
        his_sorter(rig.state)
        for view in ("live", "session"):
            for act, aid, tid, name in (("edit", "a1", "map-step-in-model-edit", "sorter"), ("make", "a5", "map-step-in-model-make", "count-lines-basket")):
                on_auto(c, rig, rows, a, b, view=view)
                rec = out[f"{view}_{act}"] = {"before": yours(rig.state), "open": open_box(c, view, aid)}
                c.click_on(f"{blk(view)}.querySelector('[data-testid={tid}]')")
                c.wait(f"(() => {{ const n = document.querySelector('[data-testid=\"crew-name\"]'); return !!n && n.value === {json.dumps(name)} && n.getClientRects().length > 0; }})()", 20)
                frames(c, 3)
                rec["form"] = c.js(FORM)
                rec["after"] = yours(rig.state)
    return _step("forms", run)


# ---- door: main's pick -------------------------------------------------------------------------------------------
REFUSED = "No model named {ref} on this harness\n/model lists the ones you have"


def door(c, rig, rows: Rows, a: str, b: str) -> dict:
    from halo_harness.studio import live_agents_api as la
    orig = la.forward
    st: dict = {}

    def fwd(sid, cmd, fields):
        if sid != a or cmd not in ("status", "slash", "model"):
            return orig(sid, cmd, fields)
        st["calls"].append(cmd)
        if cmd == "status":
            return 200, {"busy": st["busy"], "status": "busy" if st["busy"] else "idle", "model": st["model"]}
        if cmd == "slash":
            ref = str(fields.get("line") or "").split(" ", 1)[-1]
            if st["refuse"]:
                return 200, {"output": REFUSED.format(ref=ref), "ran": True, "terminal": True}
            if st["terminal"]:
                st["model"] = ref
                return 200, {"output": f"Model: {ref}", "ran": True, "terminal": True}
            return 200, {"output": f"/model {ref}", "ran": False, "terminal": False}
        st["model"] = str(fields.get("ref") or "")
        return 200, {"ok": True}

    def run(out: dict) -> None:
        on_auto(c, rig, rows, a, b)
        for case, terminal, refuse, busy in (("terminal", True, False, False), ("none", False, False, False),
                                             ("refused", True, True, False), ("busy", False, False, True)):
            rec = out[case] = {"open": open_box(c, "live", "main")}
            st.update(calls=[], busy=busy, terminal=terminal, refuse=refuse, model=rec["open"].get("value") or "")
            rec["ref"] = pick_other(c, "live")
            c.wait(f"!{line_is('live', 'Picking')} && !{trig('live')}.disabled", 20)
            rec["picked"] = block(c, "live")
            rec["calls"] = list(st["calls"])
            close(c, "live")
    la.forward = fwd
    try:
        return _step("door", run)
    finally:
        la.forward = orig


# ---- late: the sheet waits for the model's read at most 1 s ------------------------------------------------------
def late(c, rig, rows: Rows, a: str, b: str) -> dict:
    def run(out: dict) -> None:
        on_auto(c, rig, rows, a, b)
        c.js("window.__modelHold = true; 1")
        open_on(c, "live", box("live", "a1"))
        frames(c, 4)
        out["held"] = c.js("window.__modelWaits.length")
        out["at_open"] = {"block": c.js(f"!!{blk('live')}"), "kids": c.js(f"({KIDS})({SHEET['live']})")}
        out["released"] = c.js("window.__modelRelease()")
        c.wait(f"!!{blk('live')}?.dataset.kind && {blk('live')}.querySelectorAll('[data-testid=map-step-in-model-line] > p').length > 0", 20)
        frames(c, 4)
        out["after"] = {"block": block(c, "live"), "kids": c.js(f"({KIDS})({SHEET['live']})"),
                        "last": c.js(f"{SHEET['live']}.querySelector('[data-testid=map-step-in-body]').lastElementChild === {blk('live')}")}
        close(c, "live")
    try:
        return _step("late", run)
    finally:
        c.js("window.__modelRelease && window.__modelRelease(); 1")


# ---- picker: it never folds the sheet ---------------------------------------------------------------------------
def picker(c, rig, rows: Rows, a: str, b: str) -> dict:
    from tests.helpers.chrome_driver import emulate_motion

    def run(out: dict) -> None:
        emulate_motion(c, "reduce")
        on_auto(c, rig, rows, a, b)
        open_box(c, "live", "a1")
        unfold(c, "live")
        search = f"({fold('live')}).querySelector('[data-testid$=\"-search\"]')"
        c.click_on(search)
        frames(c, 3)
        out["click"] = {"open": c.js(is_open("live")), "fold": c.js(f"!!({fold('live')})"),
                        "focus": c.js(f"document.activeElement === {search}")}
        c.key("Escape")
        c.wait(f"!({fold('live')})", 10)
        frames(c, 3)
        out["escape_in_search"] = {"open": c.js(is_open("live")), "fold": c.js(f"!!({fold('live')})")}
        c.key("Escape")
        out["escape_after"] = {"gone": bool(c.wait(gone("live"), 10))}
    try:
        return _step("picker", run)
    finally:
        emulate_motion(c, "no-preference")


STEPS = (kinds, picks, forms, door, late, picker)


class SheetActsDriver(LiveNowDriver):
    """tests/helpers/studio_live_now_steps.py's rig (its session, the clock, the motion setting), these steps; the page's
    GETs of crew/agent-model counted (and held on request) from its first script; his `sorter` dropped at the end."""

    @contextmanager
    def session(self, c):
        want, self.argv = self.argv, []
        with super().session(c) as theirs:
            self.argv = want
            args = theirs[0][1]
            c.call("Page.addScriptToEvaluateOnNewDocument", source=WRAP)
            try:
                yield tuple((fn, args) for fn in STEPS if not want or fn.__name__ in want)
            finally:
                drop_his(args[1].state)


if __name__ == "__main__":
    sys.exit(SheetActsDriver(sys.argv[1:]).main())
