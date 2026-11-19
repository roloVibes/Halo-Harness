"""tests.helpers.studio_auto -- scene 4 of 3.6.0.5 "Auto and groups" (design section 6, the VM browser test) in a
browser on the Linux VM, without a model and without a terminal: over this harness's REAL session
(tests/helpers/studio_session_rig.py, on Auto: its row says `map_plain`) his workflow `tidy` (a copy of the shipped
`plan`) and the card's files (the agent checker, the workflow review: code (coder), check (checker)) are written as
an applied card on Auto writes them (no map, crew.map untouched), and the Builder's outcome frame `builder_done` (the
receipt's wire shape, with t's `ready` and `later`) is published through Studio's own bridge. Then, at 1280 x 800,
pointer moved out first, Studio's page is read:

    ready    Session's Live drawer: the head H1 with [Open in Workflows], P1 then P2 under it, no pair, still Auto, the
             same boxes, no control of the view bar moved
    use      the rows and the two `map_step` frames a run of the crew workflow review gives: the group
             "workflow review · step 1 of 2" wholly inside the drawer's visible box, still Auto
    waits    (its own process: `python -m tests.helpers.studio_auto waits`) a home with no workflow of his: H2 with
             [Open in Workflows], P2 for the agent then P2 for the workflow, no P1, no pair

Every step catches its own waits and returns what it saw (no step raises); `verdicts(got)` says, per assert, what a
person would have seen wrong. The words are scripts/realcheck/steps_auto.py's (one place).

    python -m tests.helpers.studio_auto            (ready, then use; the last stdout line is the JSON)
    python -m tests.helpers.studio_auto waits      (waits alone)
"""
from __future__ import annotations

import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from tests.helpers.chrome_driver import Driver  # noqa: E402
from realcheck.steps_auto import H1, OPEN_WF, P1, P2, SCROLL_BOX, USE_HEAD  # noqa: E402

H2 = ("Just built: the workflow review. It waits for your next session: this session started with no workflow, so it "
      "has no Workflow tool.")
P2_AGENT = "Saved for your next session: the agent checker (this session's list of agents was fixed when it started)."
P2_FLOW = ("Saved for your next session: the workflow review (this session started with no workflow, so it has no "
           "Workflow tool).")
CHECKER = {"format": "agent/1", "name": "checker", "does": "checks the code against the request"}
REVIEW = {"format": "workflow/1", "name": "review", "for": "review",
          "steps": [{"name": "code", "agents": ["coder"]}, {"name": "check", "agents": ["checker"]}]}
WROTE = [{"kind": "agent", "name": "checker", "added": True}, {"kind": "workflow", "name": "review", "added": True}]
M = "document.querySelector('[data-testid=session-lit-map]')"
OFF = (1279, 799)
VIEWBAR = """(() => { const rects = {}; for (const e of document.querySelectorAll('[data-testid=viewbar-btn]')) {
  const r = e.getBoundingClientRect(); rects[e.dataset.panel] = [r.left, r.top, r.width, r.height]; } return rects; })()"""
BOXES = f"[...({M}?.querySelectorAll('[data-box]') || [])].map((e) => e.dataset.box)"
HEAD = f"""(() => {{ const hd = document.querySelector('[data-testid=session-built-head]'), D = {M};
  return {{head: hd ? hd.querySelector('[data-testid=session-built-text]')?.textContent || '' : null,
    buttons: hd ? [...hd.querySelectorAll('button')].map((b) => b.textContent.trim()) : [],
    lines: [...document.querySelectorAll('[data-testid=session-ready-line] [data-testid=session-ready-text]')].map((e) => e.textContent),
    pair: !!document.querySelector('[data-testid=session-map-pair]'), map: D ? D.dataset.map || '' : null}}; }})()"""
# the workflow's group: the one of the workflow review (the rig's own helpers are groups too on Auto)
USE = f"""(() => {{ const D = {M}, box = {SCROLL_BOX};
  const g = D && (D.querySelector('[data-testid=session-map-group][data-workflow=review]') || D.querySelector('[data-testid=session-map-group]'));
  if (!g) return {{found: false, map: D ? D.dataset.map || '' : null}};
  const r = g.getBoundingClientRect(), b = box(g), s = b ? b.getBoundingClientRect() : {{left: 0, top: 0, right: 1280, bottom: 800}};
  return {{found: true, map: D.dataset.map || '', name: g.querySelector('[data-testid=map-group-name]')?.textContent || '',
    rect: [r.left, r.top, r.right, r.bottom],
    visible: [Math.max(0, s.left), Math.max(0, s.top), Math.min(innerWidth, s.right), Math.min(innerHeight, s.bottom)]}}; }})()"""


def _fold(text) -> str:
    return " ".join(str(text or "").split())


def _wait(c, expr: str, timeout: float):
    try:
        return c.wait(expr, timeout)
    except TimeoutError:
        return None


def _load(c, rig) -> bool:
    c.go(rig.url("session", "&open=session-map"))
    ok = bool(_wait(c, f"!!{M} && !!{M}.querySelector('[data-box=main]')", 30))
    c.mouse("mouseMoved", *OFF)
    time.sleep(0.5)
    return ok


def _builder_done(lv, ready: list, later: list) -> None:
    """The `builder_done` frame an applied card on Auto sends (the receipt's wire shape, t/batch01 entry 3), from main."""
    lv.frame("main", "builder_done", {"id": "card-auto-1", "outcome": "applied", "wrote": WROTE, "undo": "u-auto-1",
                                      "next": "auto", "this_session": "auto", "maps": {}, "ready": ready, "later": later,
                                      "t": time.time()})


def ready(c, rig, lv, st) -> dict:
    out: dict = {"reached": _load(c, rig)}
    out["boxes_before"] = c.js(BOXES) or []
    bar = c.js(VIEWBAR) or {}
    _builder_done(lv, ["review"], [{"kind": "agent", "name": "checker", "why": "AG1", "step": "review"}])
    _wait(c, "document.querySelectorAll('[data-testid=session-ready-line]').length >= 2", 10)
    time.sleep(0.5)
    out.update(c.js(HEAD) or {})
    out["boxes"] = c.js(BOXES) or []
    after = c.js(VIEWBAR) or {}
    out["moved"] = [k for k, r in bar.items() if any(abs(x - y) > 0.5 for x, y in zip(r, after.get(k) or [1e9] * 4))]
    return {"ready": out}


def use(c, rig, lv, st) -> dict:
    now = time.time()
    # main's child as the rig's own helpers are (they are group 1 on Auto: this run is the session's next group)
    parent = rig.agent("Implement").get("parent") or "main"
    lv.rows["c0d3r0a1"] = {"agent_id": "c0d3r0a1", "parent": parent, "name": "coder", "role": "coder", "bio": "coder",
                           "model": "or:mock/glm-5-coder", "kind": "subagent", "task": "fix the login bug", "since": now,
                           "state": "running", "turns": 1, "cost_usd": 0.0, "current": "thinking", "last_text": "",
                           "transcript": None, "crew": {"workflow": "review", "step": 1, "agent": "coder"},
                           "spawn": {"step": "1", "description": "code", "task": "fix the login bug",
                                     "group": {"key": "workflow:review#run-1", "n": 2, "by": "workflow"}}}
    lv.state("coder")
    lv.frame("main", "map_step", {"map": "auto", "box": "workflow:review", "workflow": "review", "kind": "start",
                                  "steps": ["code", "check"], "t": time.time()})
    lv.frame("main", "map_step", {"map": "auto", "box": "workflow:review", "workflow": "review", "kind": "step", "n": 1,
                                  "name": "code", "state": "running", "t": time.time()})
    lv.refresh()
    _wait(c, f"(({USE}).name || '').replace(/\\s+/g, ' ').trim() === {USE_HEAD!r}", 10)
    time.sleep(0.3)
    got = c.js(USE) or {}
    got["groups"] = c.js(f"""[...({M}?.querySelectorAll('[data-testid=session-map-group]') || [])].map((g) =>
      [g.dataset.group, g.dataset.workflow || '', g.querySelector('[data-testid=map-group-name]')?.textContent || ''])""")
    return {"use": got}


def waits(c, rig, lv, st) -> dict:
    out: dict = {"reached": _load(c, rig)}
    _builder_done(lv, [], [{"kind": "agent", "name": "checker", "why": "AG1"},
                           {"kind": "workflow", "name": "review", "why": "WF"}])
    _wait(c, "document.querySelectorAll('[data-testid=session-ready-line]').length >= 2", 10)
    time.sleep(0.5)
    out.update(c.js(HEAD) or {})
    return {"waits": out}


def _ready_says(r: dict) -> list:
    if not r:
        return ["not run"]
    says = []
    if _fold(r.get("head")) != H1:
        says.append(f"the head says {_fold(r.get('head'))!r}, not H1")
    if OPEN_WF not in (r.get("buttons") or []):
        says.append(f"the head has no button {OPEN_WF!r} (got {r.get('buttons')})")
    if [_fold(x) for x in r.get("lines") or []] != [P1, P2]:
        says.append(f"the lines under the head are {[_fold(x) for x in r.get('lines') or []]}, not P1 then P2")
    if r.get("pair"):
        says.append("a pair Running | Just built is shown")
    if r.get("map") != "auto":
        says.append(f"the drawer draws {r.get('map')!r}, not auto")
    if r.get("boxes") != r.get("boxes_before"):
        says.append(f"the drawer's boxes changed from {r.get('boxes_before')} to {r.get('boxes')}")
    if r.get("moved"):
        says.append(f"the view bar's controls moved: {r['moved']}")
    return says


def _use_says(u: dict) -> list:
    if not u or not u.get("found"):
        return ["no group of the workflow review in the drawer in 10 s"]
    says = []
    if _fold(u.get("name")) != USE_HEAD:
        says.append(f"the workflow's group is named {_fold(u.get('name'))!r}, not {USE_HEAD!r}")
    (lf, tp, rt, bt), (vl, vt, vr, vb) = u["rect"], u["visible"]
    if lf < vl - 0.5 or tp < vt - 0.5 or rt > vr + 0.5 or bt > vb + 0.5:
        says.append(f"the group is not wholly in the drawer's visible box ({[round(x) for x in u['rect']]} outside "
                    f"{[round(x) for x in u['visible']]})")
    if u.get("map") != "auto":
        says.append(f"the drawer draws {u.get('map')!r}, not auto")
    return says


def _waits_says(w: dict) -> list:
    if not w:
        return ["not run"]
    says = []
    if _fold(w.get("head")) != H2:
        says.append(f"the head says {_fold(w.get('head'))!r}, not H2")
    if OPEN_WF not in (w.get("buttons") or []):
        says.append(f"the head has no button {OPEN_WF!r} (got {w.get('buttons')})")
    lines = [_fold(x) for x in w.get("lines") or []]
    if lines != [P2_AGENT, P2_FLOW]:
        says.append(f"the lines are {lines}, not P2 for the agent then P2 for the workflow")
    if any(x.startswith("Ready in this session now:") for x in lines):
        says.append("a P1 line is shown")
    if w.get("pair"):
        says.append("a pair Running | Just built is shown")
    return says


def verdicts(got: dict) -> list:
    """One line per assert a person would have seen wrong: '(ready) ...', '(use) ...', '(waits) ...'."""
    out = []
    parts = (("waits", _waits_says),) if "waits" in got else (("ready", _ready_says), ("use", _use_says))
    for name, judge in parts:
        says = judge(got.get(name) or {})
        if says:
            out.append(f"({name}) " + "; ".join(says))
    return out


class AutoDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}
    width, height = 1280, 800

    @contextmanager
    def session(self, c):
        from halo_harness.crew import store
        from tests.helpers.studio_live_rig import Live
        from tests.helpers.studio_session_rig import StudioSessionRig
        alone = "waits" in self.argv
        t0 = time.monotonic()
        with StudioSessionRig() as rig:
            rig.full = False
            lv = Live(rig, extra=())
            lv.refresh(map="auto", map_plain=True)  # this session started on the default, as the engine's row says
            if not alone:  # his workflow tidy: the session has the Workflow tool
                store.own_copy("workflow", "plan", as_name="tidy", state_dir=rig.state)
            for kind, body in (("agent", CHECKER), ("workflow", REVIEW)):  # the card's files, in its write order
                store.write_text(store.path_for(kind, body["name"], state_dir=rig.state), store.dump(body))
            st = {"t0": t0}
            yield tuple((fn, (c, rig, lv, st)) for fn in ((waits,) if alone else (ready, use)))
        self.out["seconds"] = round(time.monotonic() - t0, 1)


if __name__ == "__main__":
    sys.exit(AutoDriver(sys.argv[1:]).main())
