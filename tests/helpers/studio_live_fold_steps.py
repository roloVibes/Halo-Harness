"""tests.helpers.studio_live_fold_steps -- "fold and lanes" as a person sees it (Halo 3.6.0.15 LW, rules L9a and L9b), in
headless Chrome over tests/helpers/studio_session_rig.py, with the rig and steps of tests/helpers/studio_live_now_steps.py
(imported, never copied). Agents -> Live on Auto at 1440 x 900; Session's drawer at its default width. No model is called.
Every name is invented; every figure a test asserts is read from the page (the zoom from live-world's data-zoom, the view
from the scroll box's clientWidth).

    lanes    L9a: three groups at 1440 x 900: main's and each group's rect, the zoom, the view; then the pointer resting on
             main while the window narrows to 1100 x 800 (nothing may move), then the pointer leaves (every group takes
             the new width)
    three    L9b: a group of four members at 1440 x 900 (three a row), then at 1000 x 800 (two a row), then the same
             groups in Session's drawer at its default width
    groupfold  L8, in Session's drawer and then in Agents -> Live: a group all done before the page loaded is folded at
             the first draw; a done + failed and a done + stopped group stay open; a running group's last member ends
             with the pointer resting on the drawing (nothing moves for 11 s of the page's time), then the pointer leaves
             (it folds, the group under it moves up); a group's member ends while a sheet is open (it stays open), the
             sheet closed (it folds); a member joins the folded group (it opens with its earlier heights and one HAND
             ring) and one joins the group folded from the start; the slot's group read at every step

    python -m tests.helpers.studio_live_fold_steps [step ...]
The last stdout line is a JSON object of what it saw.
"""
from __future__ import annotations

import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.studio_auto_groups_draw import LSCROLL, LW, P, RECT  # noqa: E402
from tests.helpers.studio_live_now_steps import CLOCK, VIEWS, frames, go, mk, put, rest_on, to_live, wait_or  # noqa: E402
from tests.helpers.studio_session_map_down import MapDownDriver, Rows  # noqa: E402
from tests.helpers.studio_session_run import M, _main, _seed  # noqa: E402

FRAME = f"document.querySelector('{P} [data-testid=live-frame]')"
# Agents -> Live's geometry: the zoom, the view, the scroll box's scroll width, the world's, main's and each group's rect,
# each group's data-per and its members' rects (in the order drawn)
GEO = f"""(() => {{ const w = {LW}, s = {LSCROLL}; if (!w || !s) return null; const R = {RECT};
  return {{ zoom: +w.dataset.zoom, view: s.clientWidth, sw: s.scrollWidth, world: R(w), main: R(w.querySelector('[data-box=main]')),
    held: {FRAME}?.dataset.held || '',
    groups: Object.fromEntries([...w.querySelectorAll('[data-testid=live-group]')].map((g) => [g.dataset.group, {{ rect: R(g),
      per: g.querySelector('.mp-group-members')?.dataset.per || '', members: [...g.querySelectorAll('[data-member]')].map(R) }}])) }}; }})()"""
# L9a's rule, worked out on the page from what it reads: every group as wide as max(352, min(760, floor(view / zoom - 392)))
SETTLED = f"""(() => {{ const w = {LW}, s = {LSCROLL}; if (!w || !s) return false; const z = +w.dataset.zoom || 1;
  const want = Math.max(352, Math.min(760, Math.floor(s.clientWidth / z - 392)));
  const gs = [...w.querySelectorAll('[data-testid=live-group]')];
  return gs.length > 0 && gs.every((g) => Math.abs(g.getBoundingClientRect().width / z - want) <= 1); }})()"""
MAIN = f"{LW}.querySelector('[data-box=main]')"


def _size(c, w: int, h: int) -> None:
    c.call("Emulation.setDeviceMetricsOverride", width=w, height=h, deviceScaleFactor=1, mobile=False)


def _narrowed(c, was: float) -> None:
    """Waits until the scroll box is narrower than `was` (the window's new size reached it), then a few frames."""
    wait_or(c, f"({LSCROLL}?.clientWidth || 1e9) < {was} - 50", 15)
    frames(c, 6)


def lanes(c, rig, rows: Rows, a: str, b: str) -> dict:
    out: dict = {}
    t0 = time.time() - 5
    main = _main(rows, a, state="running", current="Agent: survey the TODOs", since=t0, started=t0)
    kids = [mk("u1", "researcher", "read part 1", "survey the TODOs", 1, since=t0),
            mk("u2", "coder", "fix the form", "fix the login bug", 2, model="glm-5", since=t0),
            mk("u3", "writer", "note the release", "write the changelog", 3, since=t0)]
    go(c, rig, rows, a, b, [main, *kids])
    c.wait(f"{M}.querySelectorAll('[data-member]').length === 3", 20)
    to_live(c, 3)
    out["settled"] = bool(wait_or(c, SETTLED, 15))
    frames(c, 4)
    out["wide"] = c.js(GEO)
    rest_on(c, MAIN)  # the pointer resting on the drawing: nothing may move while the window narrows
    frames(c, 2)
    before = c.js(GEO) or {}
    _size(c, 1100, 800)
    _narrowed(c, before.get("view") or 0)
    out["resting"] = [before, c.js(GEO)]
    c.mouse("mouseMoved", 2, 400)  # off the frame, on the rail: the new width is drawn
    out["settled_narrow"] = bool(wait_or(c, SETTLED, 15))
    frames(c, 2)
    out["narrow"] = c.js(GEO)
    return {"lanes": out}


def three(c, rig, rows: Rows, a: str, b: str) -> dict:
    out: dict = {}
    t0 = time.time() - 5
    main = _main(rows, a, state="running", current="Agent: survey the TODOs", since=t0, started=t0)
    kids = [mk(f"t{i}", "researcher", f"read part {i}", "survey the TODOs", 1, since=t0) for i in (1, 2, 3, 4)]
    kids += [mk("t5", "coder", "fix the form", "fix the login bug", 2, model="glm-5", since=t0)]
    go(c, rig, rows, a, b, [main, *kids])
    c.wait(f"{M}.querySelectorAll('[data-member]').length === 5", 20)
    to_live(c, 2)
    out["settled"] = bool(wait_or(c, SETTLED, 15))
    frames(c, 4)
    out["wide"] = c.js(GEO) or {}
    _size(c, 1000, 800)
    _narrowed(c, out["wide"].get("view") or 0)
    out["settled_narrow"] = bool(wait_or(c, SETTLED, 15))
    frames(c, 2)
    out["narrow"] = c.js(GEO)
    go(c, rig, rows, a, b, [main, *kids])  # Session's drawer at its default width (1440 x 900 again)
    c.wait(f"{M}.querySelectorAll('[data-member]').length === 5", 20)
    frames(c, 4)
    out["session"] = c.js(f"[...{M}.querySelectorAll('.mp-group-members')].map((e) => e.dataset.per || '')")
    return {"three": out}


# ---- L8: the fold ---------------------------------------------------------------------------------------------------
FOLD_TASKS = {1: "sort the old mail", 2: "read the release notes", 3: "fix the login bug", 4: "check the money module",
              5: "note the release", 6: "run the slow tests"}
# A (1) all done before the page loads; D (2) one done, one running; F (3) running under D; B (4) done + failed;
# C (5) done + stopped; E (6) running
FOLD_SPEC = [("a1", "sorter", "sort the inbox", 1, "done"), ("a2", "sorter", "sort the outbox", 1, "done"),
             ("d1", "researcher", "read the notes", 2, "done"), ("d2", "researcher", "read the issues", 2, "running"),
             ("f1", "coder", "fix the form", 3, "running"),
             ("b1", "reviewer", "check pay.py", 4, "done"), ("b2", "reviewer", "check tax.py", 4, "failed"),
             ("c1", "writer", "note the fixes", 5, "done"), ("c2", "writer", "note the moves", 5, "stopped"),
             ("e1", "Tester", "run the unit tests", 6, "running")]
GROUP_SEL = ":is([data-testid=session-map-group], [data-testid=live-group])"
SHEET = "document.querySelector('[data-testid=map-step-in]')"
OPEN_SHEET = "document.querySelector('[data-testid=map-step-in][data-open]')"
# one drawing as the fold check reads it: each group's fold, place in the world (offsets: unscaled), height, its head's
# height, counts, data-rang, and each member's size, raw state and data-rang; main's place; the slot's group; the sheet
FREAD = f"""((root, slot) => {{ if (!root) return null; const gs = {{}};
  for (const g of root.querySelectorAll('{GROUP_SEL}')) {{ const head = g.querySelector('[data-testid=map-group-head]');
    gs[g.dataset.group] = {{ folded: g.hasAttribute('data-folded'), top: g.offsetTop, left: g.offsetLeft, h: g.offsetHeight,
      head: head ? head.offsetHeight : 0, counts: g.querySelector('[data-testid=map-group-counts]')?.textContent || '', rang: g.dataset.rang || '',
      members: Object.fromEntries([...g.querySelectorAll('[data-member]')].map((m) => {{ const r = m.getBoundingClientRect();
        return [m.dataset.member, {{ h: m.offsetHeight, w: r.width, rh: r.height, raw: m.dataset.raw || '', rang: m.dataset.rang || '' }}]; }})) }}; }}
  const main = root.querySelector('[data-box=main]');
  return {{ groups: gs, main: main ? [main.offsetTop, main.offsetLeft] : null, slot: slot ? (slot.dataset.group ?? null) : null,
    sheet: !!{OPEN_SHEET} }}; }})"""


def _fold_rows(rows: Rows, a: str, t0: float, **st) -> list:
    """The fold scene; `st` sets a member's state by its id; `extra` adds (aid, who, desc, n) members."""
    spec = FOLD_SPEC + [(aid, who, desc, n, "running") for aid, who, desc, n in st.pop("extra", ())]
    main = _main(rows, a, state="running", current="Agent: run the slow tests", since=t0, started=t0)
    return [main, *[mk(aid, who, desc, FOLD_TASKS[n], n, st.get(aid, s), since=t0) for aid, who, desc, n, s in spec]]


def _fread(c, view: str) -> dict:
    root, _, slot = VIEWS[view]
    return c.js(f"({FREAD})({root}, {slot})") or {}


def _page_wait(c, secs: float) -> None:
    """Waits until the page's own clock (Date.now()) is `secs` past now (a state read from the page, never a sleep)."""
    t = c.js("Date.now()")
    wait_or(c, f"Date.now() >= {t} + {int(secs * 1000)}", secs + 15)


def _group(view: str, n: int) -> str:
    return f"{VIEWS[view][0]}.querySelector('[data-box=\"group:{n}\"]')"


def _fold_view(c, rig, rows: Rows, a: str, b: str, view: str) -> dict:
    out: dict = {}
    root, sc, _ = VIEWS[view]
    t0 = time.time() - 60
    put_rows = lambda **st: put(rows, a, _fold_rows(rows, a, t0, **st))  # noqa: E731
    go(c, rig, rows, a, b, _fold_rows(rows, a, t0))
    c.wait(f"{M}.querySelectorAll('{GROUP_SEL}').length === 6", 20)
    if view == "live":
        to_live(c, 6)
    c.mouse("mouseMoved", 2, 400)  # the pointer off the drawing (on the rail)
    wait_or(c, f"!!{_group(view, 1)}?.hasAttribute('data-folded')", 10)
    frames(c, 6)
    out["first"] = _fread(c, view)
    # (b) D open: its members' heights and data-rang; the pointer rests on main; d2 ends; 11 s of the page's time
    rest_on(c, f"{root}.querySelector('[data-box=main]')")
    frames(c, 2)
    out["d_open"] = _fread(c, view)
    put_rows(d2="done")
    wait_or(c, f"{root}.querySelector('[data-member=d2]')?.dataset.raw === 'done'", 15)
    _page_wait(c, 11)
    frames(c, 2)
    out["resting"] = _fread(c, view)
    c.mouse("mouseMoved", 2, 400)
    out["d_folded"] = bool(wait_or(c, f"!!{_group(view, 2)}?.hasAttribute('data-folded')", 10))
    frames(c, 4)
    out["left"] = _fread(c, view)
    # (c) a sheet open on B's member b1; E's member ends; 11 s with the pointer off; the sheet closed by Escape
    c.click_on(f"{root}.querySelector('[data-member=b1]')")
    out["sheet_opened"] = bool(wait_or(c, f"!!{OPEN_SHEET}", 10))
    c.mouse("mouseMoved", 2, 400)
    put_rows(d2="done", e1="done")
    wait_or(c, f"{root}.querySelector('[data-member=e1]')?.dataset.raw === 'done'", 15)
    _page_wait(c, 11)
    frames(c, 2)
    out["sheet"] = _fread(c, view)
    c.key("Escape")
    if not wait_or(c, f"!{SHEET}", 5) and c.js(f"!!{SHEET}"):
        c.click_on("document.querySelector('[data-testid=map-step-in-close]')")
        c.mouse("mouseMoved", 2, 400)
    out["closed"] = bool(wait_or(c, f"!{SHEET}", 10))
    out["e_folded"] = bool(wait_or(c, f"!!{_group(view, 6)}?.hasAttribute('data-folded')", 10))
    frames(c, 4)
    out["after_sheet"] = _fread(c, view)
    # (d) D (drawn open, then folded) at the scroll box's top; a member joins it with the pointer off
    c.js(f"(() => {{ const s = {sc}, g = {_group(view, 2)}; s.scrollTop += g.getBoundingClientRect().top - s.getBoundingClientRect().top - 8; return 1; }})()")
    frames(c, 4)
    out["d_before"] = _fread(c, view)
    put_rows(d2="done", e1="done", extra=[("d3", "researcher", "read the wiki", 2)])
    out["d_opened"] = bool(wait_or(c, f"!!{root}.querySelector('[data-member=d3]') && !{_group(view, 2)}.hasAttribute('data-folded')", 15))
    wait_or(c, f"!!{_group(view, 2)}?.dataset.rang", 10)
    frames(c, 4)
    out["d_after"] = _fread(c, view)
    # A, folded from the first draw: a member joins
    c.js(f"(() => {{ const s = {sc}; s.scrollTop = 0; return 1; }})()")
    put_rows(d2="done", e1="done", extra=[("d3", "researcher", "read the wiki", 2), ("a3", "sorter", "sort the drafts", 1)])
    out["a_opened"] = bool(wait_or(c, f"!!{root}.querySelector('[data-member=a3]') && !{_group(view, 1)}.hasAttribute('data-folded')", 15))
    frames(c, 4)
    out["a_after"] = _fread(c, view)
    return out


def groupfold(c, rig, rows: Rows, a: str, b: str) -> dict:
    return {"groupfold": {view: _fold_view(c, rig, rows, a, b, view) for view in ("session", "live")}}


STEPS = (lanes, three, groupfold)


class LiveFoldDriver(MapDownDriver):
    width, height = 1440, 900

    @contextmanager
    def session(self, c):
        from tests.helpers.chrome_driver import emulate_motion
        from tests.helpers.studio_session import FAKE_SID, collect_page_errors, second_session
        from tests.helpers.studio_session_rig import StudioSessionRig
        with StudioSessionRig() as rig:
            _seed(rig)
            second_session(rig)
            rows = Rows(rig)
            collect_page_errors(c)
            c.call("Page.addScriptToEvaluateOnNewDocument", source=CLOCK)
            emulate_motion(c, "no-preference")
            args = (c, rig, rows, rig.act.session_id, FAKE_SID)
            yield tuple((fn, args) for fn in STEPS if not self.argv or fn.__name__ in self.argv)


if __name__ == "__main__":
    sys.exit(LiveFoldDriver(sys.argv[1:]).main())
