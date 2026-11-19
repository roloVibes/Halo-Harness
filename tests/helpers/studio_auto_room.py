"""tests.helpers.studio_auto_room -- Session's Live drawer on Auto uses its whole room, and a helper's card stays inside
it (Halo 3.6.0.5 r/batch04 entries 1 and 2, the pictures taken for the owner), in headless Chrome over
tests/helpers/studio_session_rig.py (this harness's real session A, its rows set through GET live as
tests/helpers/studio_auto_groups_draw.py sets them). A fresh page is loaded at each size. No model is called.

    room    at 1280 x 800 and 1440 x 900: main alone, then group 1 ("compare the three reports", three researchers), then
            the pictures' four groups: the drawing's scroll box, its visible part, the room it stands in, the slot, group
            1's name and counts; then a map of his (the scratch map of seven boxes, scratch_seven.NAME): the boxes and the
            scroll box's height, for the released rule
    card    at 1280 x 800 and 1440 x 900, the four groups: a click on researcher A of group 1 opens its card; the card,
            the drawer and the drawing's content box, the Send button before and after the card is scrolled to its end

    python -m tests.helpers.studio_auto_room [step ...]
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

from tests.helpers.scratch_seven import NAME as SEVEN  # noqa: E402
from tests.helpers.studio_auto_groups_draw import GROUP, MORE, RECT, SLOT, _set, member, scene2  # noqa: E402
from tests.helpers.studio_session_map_down import MapDownDriver, Rows  # noqa: E402
from tests.helpers.studio_session_run import M, _main, _seed, _size  # noqa: E402

SIZES = ((1280, 800), (1440, 900))
SCROLL = f"{M}?.querySelector('.mp-mini-scroll')"
FILL = f"{M}?.querySelector('.mp-down-fill')"
READ = f"""(() => {{ const s = {SCROLL}, f = {FILL}, g = ({GROUP})(1), r = {RECT};
  const v = s && s.getBoundingClientRect();
  return {{box: r(s), vis: s ? [v.left + s.clientLeft, v.top + s.clientTop, s.clientWidth, s.clientHeight] : null,
    room: f ? f.clientHeight : 0, fill: r(f), slot: r({SLOT}), main: r({M}?.querySelector('[data-box=main]')), top: s ? s.scrollTop : 0,
    head: g ? [r(g.querySelector('[data-testid=map-group-name]')), r(g.querySelector('[data-testid=map-group-counts]'))] : null,
    groups: {M}?.querySelectorAll('[data-testid=session-map-group]').length || 0, more: ({MORE})?.textContent || ''}}; }})()"""
# a map of his: every box's rect in the world's own coordinates (the zoom taken out), the zoom, the scroll box and the room
HIS = f"""(() => {{ const s = {SCROLL}, f = {FILL}, w = {M}?.querySelector('.mp-mini-world'); if (!s || !w) return null;
  const k = Number(w.dataset.zoom) || 1, wt = w.getBoundingClientRect().top;
  return {{k, h: s.clientHeight + 0, offset: s.offsetHeight, room: f ? f.clientHeight : 0, top: s.scrollTop,
    boxes: [...w.querySelectorAll('[data-box]')].filter((b) => b.parentElement === w).map((b) => {{ const r = b.getBoundingClientRect();
      return [b.dataset.box, (r.top - wt) / k, r.height / k]; }})}}; }})()"""
CARD = "document.querySelector('[data-testid=map-step-in]')"
SEND = f"{CARD}?.querySelector('[data-testid=fleet-steer-send]')"
CARD_READ = f"""(() => {{ const c = {CARD}, r = {RECT}; if (!c) return null; const v = c.getBoundingClientRect();
  return {{card: r(c), vis: [v.left + c.clientLeft, v.top + c.clientTop, c.clientWidth, c.clientHeight], scroll: [c.scrollTop, c.scrollHeight, c.clientHeight],
    send: r({SEND}), down: r({M}), drawer: r({M}?.closest('[data-testid=stage-drawer]')), title: c.querySelector('[data-testid=map-step-in-title]')?.textContent || '',
    steer: r(c.querySelector('[data-testid=fleet-steer]'))}}; }})()"""


def four() -> list:
    """The pictures' mid-run on Auto: (1) three researchers working, (2) a coder done, (3) a writer waiting on him, (4) a
    workflow run's reviewer working."""
    return [*scene2(),
            member("k1", "coder", "fix the login form", "fix the login bug", 2, state="done", model="glm-5", cost=0.02),
            member("w1", "writer", "write the notes", "write the release notes", 3, state="waiting", reason="short writing; no tools"),
            member("q1", "reviewer", "review the change", "", 4, key="workflow:review#tu4", by="workflow")]


def _open_at(c, rig, rows: Rows, a: str, b: str, mp: str, plain: bool, agents: list, w: int, h: int) -> None:
    """studio_session_run._open at the size `w` x `h`: a fresh page loaded at that size."""
    from tests.helpers.studio_session import boot_go, url
    rows.reset()
    rows.idle(b)
    rows.set(a, map=mp, map_plain=plain, busy=True, status="busy", agents=agents)
    _size(c, w, h)
    boot_go(c, url(rig, f"mode=session&session={a}&open=session-map"))
    c.wait(f"!!{M} && {M}.dataset.map === '{mp}' && !!{M}.querySelector('[data-box=main]')", 40)
    c.mouse("mouseMoved", w - 1, h - 1)  # the pointer out of the drawer (it is on the left)


def room(c, rig, rows: Rows, a: str, b: str) -> dict:
    out: dict = {}
    main = _main(rows, a)
    for w, h in SIZES:
        at: dict = {}
        _open_at(c, rig, rows, a, b, "auto", True, [main], w, h)
        time.sleep(0.8)
        at["alone"] = c.js(READ)
        _set(rows, a, [main, *scene2()])
        c.wait(f"({GROUP})(1)?.querySelectorAll('[data-member]').length === 3", 20)
        time.sleep(0.8)
        at["one"] = c.js(READ)
        _set(rows, a, [main, *four()])
        c.wait(f"!!({GROUP})(4)", 20)
        time.sleep(0.8)
        at["four"] = c.js(READ)
        out[f"{w}x{h}"] = at
    _open_at(c, rig, rows, a, b, SEVEN, False, [main, *scene2()], 1280, 800)  # a map of his: the released rule
    time.sleep(1.0)
    out["his"] = c.js(HIS)
    return {"room": out}


def card(c, rig, rows: Rows, a: str, b: str) -> dict:
    out: dict = {}
    main = _main(rows, a)
    for w, h in SIZES:
        _open_at(c, rig, rows, a, b, "auto", True, [main, *four()], w, h)
        mem = f"{M}.querySelector('[data-member=r1]')"
        c.wait(f"!!({GROUP})(4) && !!{mem}", 20)
        time.sleep(0.8)
        c.js(f"{mem}.scrollIntoView({{block: 'nearest'}}); 1")  # inside the drawing's own scroll, when it is below the edge
        time.sleep(0.3)
        c.click_on(mem)
        at: dict = {}
        try:
            c.wait(f"!!{SEND}", 10)
        except TimeoutError:
            pass  # the reading says what it showed
        time.sleep(0.5)
        at["open"] = c.js(CARD_READ)
        c.js(f"(() => {{ const c = {CARD}; if (c) c.scrollTop = c.scrollHeight; return 1; }})()")
        time.sleep(0.3)
        at["scrolled"] = c.js(CARD_READ)
        out[f"{w}x{h}"] = at
        c.js("document.querySelector('[data-testid=map-step-in-close]')?.click(); 1")
    return {"card": out}


class AutoRoomDriver(MapDownDriver):
    width, height = 1280, 800

    @contextmanager
    def session(self, c):
        from tests.helpers.studio_session import FAKE_SID, collect_page_errors, second_session
        from tests.helpers.studio_session_rig import StudioSessionRig
        with StudioSessionRig() as rig:
            _seed(rig)
            second_session(rig)
            rows = Rows(rig)
            collect_page_errors(c)
            args = (c, rig, rows, rig.act.session_id, FAKE_SID)
            yield tuple((fn, args) for fn in (room, card) if not self.argv or fn.__name__ in self.argv)


if __name__ == "__main__":
    sys.exit(AutoRoomDriver(sys.argv[1:]).main())
