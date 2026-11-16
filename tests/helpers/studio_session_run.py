"""tests.helpers.studio_session_run -- the run drawn as it is in Session's Live drawer (Halo 3.6.0.2 R14 R15 R16 R17), in
headless Chrome at 1280 x 800 over tests/helpers/studio_session_rig.py (this harness's real session A, its rows set
through GET live, tests/helpers/studio_session_map_down.py `Rows`) and the map frames the runtime sends (`map_hop`,
`map_step`, published on Studio's own bridge as crew/map_events.py publishes them). No model is called.

    block   A on starter: main runs the workflow W (on no box) whose steps 1-4 are tagged rows, plus one general-purpose
            child of main: the block on a full-width row, its head, its six step rows; main's made-up row and its Save
    hops    A on `hops` (main -> code, code -> review, main -> docs): a hand-off lights its line (8 s, no end, a live row
            carries it), its end leaves a trace, three hand-offs weigh more, the newest marked, its hover; a line no hop
            took stays calm; a workflow's steps light in order
    off     A on `offmap` (a map of his) with a made-up child of main no line brought: the row dashed in --off-map, its
            hover, the status line's count; the same on starter: plain dashed, not counted
    sender  A on `offmap`: coder (on its line) starts a reviewer no line brought: the row is in code's box, its hover
            names code, review stays calm

    python -m tests.helpers.studio_session_run [step ...]
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

from tests.helpers.studio_session_map_down import MapDownDriver, Rows  # noqa: E402

M = "document.querySelector('[data-testid=\"session-lit-map\"]')"
HOPS = {"format": "map/1", "name": "hops", "main": {"agent": "main"},
        "boxes": [{"id": "code", "agent": "coder"}, {"id": "review", "agent": "reviewer"}, {"id": "docs", "agent": "writer"}],
        "lines": [{"from": "main", "to": "code", "when": "always"}, {"from": "code", "to": "review", "when": "always"},
                  {"from": "main", "to": "docs", "when": "main-decides"}]}
OFFMAP = {"format": "map/1", "name": "offmap", "main": {"agent": "main"}, "boxes": [{"id": "code", "agent": "coder"}, {"id": "review", "agent": "reviewer"}],
          "lines": [{"from": "main", "to": "code", "when": "always"}, {"from": "main", "to": "review", "when": "named"}]}
SIX = ["plan", "code", "test", "review", "fix", "ship"]
AGENTS = ("planner", "coder", "tester", "reviewer")
TASK = "fix the retry in client.py so it backs off"
# a path's computed look, by its ends
LINE = f"""((f, t) => {{ const p = {M}?.querySelector(`path[data-from="${{f}}"][data-to="${{t}}"]`); if (!p) return null;
  const s = getComputedStyle(p); return {{lit: p.dataset.lit || '', hops: p.dataset.hops || '', last: !!p.dataset.last, w: parseFloat(s.strokeWidth),
  stroke: s.stroke, dash: s.strokeDasharray, hover: p.querySelector('title')?.textContent || '' }}; }})"""


def _size(c, w: int, h: int) -> None:
    c.call("Emulation.setDeviceMetricsOverride", width=w, height=h, deviceScaleFactor=1, mobile=False)


def _seed(rig) -> None:
    from halo_harness.crew import store
    for m in (HOPS, OFFMAP):
        store.write_text(store.path_for("map", m["name"], state_dir=rig.state), json.dumps(m))


def _main(rows: Rows, sid: str, **over) -> dict:
    base = next((r for r in rows.orig() if r.get("session_id") == sid), {})
    head = next((a for a in base.get("agents") or [] if a.get("agent_id") == "main"), {"agent_id": "main", "name": "main", "kind": "main"})
    return {**head, "parent": None, "crew": None, "square": None, "cost_usd": 0, "state": "running", **over}


def _kid(aid: str, name: str, state: str, crew=None, task: str = "", model: str = "") -> dict:
    return {"agent_id": aid, "name": name, "role": name, "parent": "main", "kind": "member", "state": state, "current": "thinking",
            "cost_usd": 0.0, "crew": crew, "square": None, "task": task or f"{name}'s task", "model": model, "since": time.time()}


def _frame(rig, sid: str, event: str, data: dict) -> None:
    from halo_harness.peers.identity import harness
    now = time.time()
    rig.server.events.publish({"session_id": sid, "harness": harness()["id"], "event": event, "agent_id": "main", "turn": 1,
                               "data": {"t": now, **data}, "ts": now})


def _hop(rig, sid: str, frm: str, to: str, state: str, **kw) -> None:
    _frame(rig, sid, "map_hop", {"from": frm, "to": to, "state": state, "task": TASK, **kw})


def _open(c, rig, rows: Rows, a: str, b: str, mp: str, plain: bool, agents: list) -> None:
    from tests.helpers.studio_session import boot_go, url
    rows.reset()
    rows.idle(b)
    rows.set(a, map=mp, map_plain=plain, busy=True, status="busy", agents=agents)
    _size(c, 1280, 800)
    boot_go(c, url(rig, f"mode=session&session={a}&open=session-map"))
    c.wait(f"!!{M} && {M}.dataset.map === '{mp}' && !!{M}.querySelector('[data-box=main]')", 40)
    c.mouse("mouseMoved", 1279, 799)  # the pointer out of the drawer (it is on the left)


def block(c, rig, rows: Rows, a: str, b: str) -> dict:
    flow = lambda i: {"map": "starter", "workflow": "W", "step": i, "agent": AGENTS[i - 1], "saved": True}  # noqa: E731
    kids = [_kid(f"w{i}", AGENTS[i - 1], st, crew=flow(i), model=f"or:v/{AGENTS[i - 1]}")
            for i, st in enumerate(("done", "done", "running", "queued"), start=1)]
    gp = _kid("g1", "general-purpose", "running", crew={"map": "starter", "box": "main", "made_up": True, "agent": "general-purpose"},
              task="list the repo")
    _open(c, rig, rows, a, b, "starter", True, [_main(rows, a, current="Workflow: W"), *kids, gp])
    _hop(rig, a, "main", "workflow:W", "start", workflow="W", off=False, why="named by main")
    _frame(rig, a, "map_step", {"map": "starter", "box": "workflow:W", "workflow": "W", "kind": "start", "steps": SIX})
    blk = f"{M}.querySelector('[data-testid=session-map-block][data-workflow=W]')"
    c.wait(f"!!{blk} && {blk}.querySelectorAll('[data-testid=session-map-step]').length === 6", 20)
    time.sleep(0.8)
    return {"block": c.js(f"""(() => {{ const m = {M}, k = {blk}, R = (e) => {{ const r = e.getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; }};
      const boxes = [...m.querySelectorAll('[data-testid=session-lit-box]')];
      const main = m.querySelector('[data-box=main]');
      return {{ block: R(k), boxes: boxes.map((b) => [b.dataset.box, ...R(b), b.dataset.state, b.textContent]),
        head: k.querySelector('[data-testid=session-map-block-head]')?.textContent || '',
        steps: [...k.querySelectorAll('[data-testid=session-map-step]')].map((s) => [s.textContent, s.dataset.state]),
        mainRows: [...main.querySelectorAll('[data-testid=session-map-row]')].map((r) => [r.querySelector('[data-testid=session-map-row-text]')?.textContent || '',
                   !!r.querySelector('[data-testid=map-save-agent]'), r.dataset.helper || '']),
        saves: m.querySelectorAll('[data-testid=map-save-agent]').length, text: m.innerText,
        line: ({LINE})('main', 'workflow:W') }}; }})()""")}


def hops(c, rig, rows: Rows, a: str, b: str) -> dict:
    out: dict = {}
    line = {"map": "hops", "box": "code", "line": "main -> code", "agent": "coder", "saved": True}
    _open(c, rig, rows, a, b, "hops", False, [_main(rows, a, current="Agent: coder"), _kid("c1", "coder", "running", crew=line)])
    c.wait(f"!!({LINE})('main', 'code')", 20)
    out["calm"] = c.js(f"[({LINE})('main', 'code'), ({LINE})('main', 'docs')]")
    _hop(rig, a, "main", "code", "start", line="main -> code", off=False)
    c.wait(f"({LINE})('main', 'code')?.lit === 'live'", 15)
    out["live"] = c.js(f"({LINE})('main', 'code')")
    time.sleep(8)
    out["live8"] = c.js(f"({LINE})('main', 'code')")
    _hop(rig, a, "main", "code", "end", line="main -> code", off=False)
    c.wait(f"({LINE})('main', 'code')?.lit === 'trace'", 15)
    out["t1"] = c.js(f"({LINE})('main', 'code')")
    for n in (2, 3):
        _hop(rig, a, "main", "code", "start", line="main -> code", off=False)
        _hop(rig, a, "main", "code", "end", line="main -> code", off=False)
        c.wait(f"({LINE})('main', 'code')?.hops === '{n}' && ({LINE})('main', 'code')?.lit === 'trace'", 15)
        out[f"t{n}"] = c.js(f"({LINE})('main', 'code')")
    out["lasts"] = c.js(f"[...{M}.querySelectorAll('path[data-last]')].map((p) => p.dataset.from + '>' + p.dataset.to)")
    out["docs"] = c.js(f"({LINE})('main', 'docs')")
    # a workflow's steps light in order (W on no box of this map: its block under main)
    _hop(rig, a, "main", "workflow:W", "start", workflow="W", off=True)
    _frame(rig, a, "map_step", {"map": "hops", "box": "workflow:W", "workflow": "W", "kind": "start", "steps": ["one", "two"]})
    _frame(rig, a, "map_step", {"map": "hops", "box": "workflow:W", "workflow": "W", "kind": "step", "n": 1, "name": "one", "state": "running"})
    st = f"[...{M}.querySelectorAll('[data-workflow=W] [data-testid=session-map-step]')].map((s) => s.dataset.state)"
    c.wait(f"({st}).join() === 'working,next'", 15)
    out["steps1"] = c.js(st)
    _frame(rig, a, "map_step", {"map": "hops", "box": "workflow:W", "workflow": "W", "kind": "step", "n": 1, "name": "one", "state": "done"})
    _frame(rig, a, "map_step", {"map": "hops", "box": "workflow:W", "workflow": "W", "kind": "step", "n": 2, "name": "two", "state": "running"})
    c.wait(f"({st}).join() === 'done,working'", 15)
    out["steps2"] = c.js(st)
    return {"hops": out}


OFF_READ = f"""(() => {{ const m = {M}; if (!m) return null;
  const probe = (v) => {{ const s = document.createElement('span'); s.style.color = `var(${{v}})`; m.appendChild(s); const c = getComputedStyle(s).color; s.remove(); return c; }};
  const r = m.querySelector('[data-row=a1]'), cs = r && getComputedStyle(r);
  return {{ row: r ? {{off: r.dataset.off || '', unlined: r.dataset.unlined || '', color: cs.borderLeftColor, style: cs.borderLeftStyle, title: r.title,
                     text: r.querySelector('[data-testid=session-map-row-text]')?.textContent || ''}} : null,
    offs: m.querySelectorAll('[data-off="1"]').length, offMap: probe('--off-map'), warn: probe('--warn'), accent: probe('--accent'),
    status: document.querySelector('[data-testid=session-status]')?.textContent || '' }}; }})()"""


def off(c, rig, rows: Rows, a: str, b: str) -> dict:
    out: dict = {}
    for name, plain in (("offmap", False), ("starter", True)):
        gp = _kid("a1", "general-purpose", "running", crew={"map": name, "box": "main", "made_up": True, "agent": "general-purpose"},
                  task="list the repo")
        _open(c, rig, rows, a, b, name, plain, [_main(rows, a, current="Agent: general-purpose"), gp])
        _hop(rig, a, "main", "made-up:a1", "start", off=not plain, aid="a1")
        try:
            c.wait(f"!!{M}.querySelector('[data-row=a1]') && !!document.querySelector('[data-testid=session-status]')?.textContent", 20)
            time.sleep(0.8)
        except TimeoutError:
            pass
        out[name] = c.js(OFF_READ)
    return {"off": out}


def sender(c, rig, rows: Rows, a: str, b: str) -> dict:
    """R17: coder (on its line) starts a reviewer no line brought: the row is drawn in code's box, its hover names code,
    and review (the box the row names, which started nothing) stays calm."""
    c1 = _kid("c1", "coder", "running", crew={"map": "offmap", "box": "code", "line": "main -> code", "agent": "coder", "saved": True})
    r1 = {**_kid("r1", "reviewer", "running", crew={"map": "offmap", "box": "review", "agent": "reviewer", "saved": True}), "parent": "c1"}
    _open(c, rig, rows, a, b, "offmap", False, [_main(rows, a), c1, r1])
    c.wait(f"!!{M}.querySelector('[data-row=r1]')", 20)
    return {"sender": c.js(f"""(() => {{ const m = {M}, r = m.querySelector('[data-row=r1]');
  const box = (id) => m.querySelector(`[data-testid=session-lit-box][data-box="${{id}}"]`);
  return {{ in: r.closest('[data-box]')?.dataset.box || '', title: r.title, off: r.dataset.off || '',
           review: box('review')?.dataset.state || '', reviewRows: box('review')?.querySelectorAll('[data-testid=session-map-row]').length ?? -1 }}; }})()""")}


class RunDriver(MapDownDriver):
    width, height = 1280, 800

    @contextmanager
    def session(self, c):
        from tests.helpers.studio_session import ERRS_JS, FAKE_SID, second_session
        from tests.helpers.studio_session_rig import StudioSessionRig
        with StudioSessionRig() as rig:
            _seed(rig)
            second_session(rig)
            rows = Rows(rig)
            c.call("Page.addScriptToEvaluateOnNewDocument", source=ERRS_JS)
            args = (c, rig, rows, rig.act.session_id, FAKE_SID)
            steps = [s for s in (block, hops, off, sender) if not self.argv or s.__name__ in self.argv]
            yield tuple((fn, args) for fn in steps)


if __name__ == "__main__":
    sys.exit(RunDriver(sys.argv[1:]).main())
