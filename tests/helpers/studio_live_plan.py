"""tests.helpers.studio_live_plan -- Live with the plan under it (Halo 3.3.18.0 "The living canvas" part 2) in headless
Chrome on the driver base, over tests/helpers/studio_fleet_rig.py: its real session (main, an implementer, a researcher)
runs under halo-dev-cycle, rewritten here with two tiers that have a purpose (build: worker, verify; read: research) and
one square (media); plus three agents through tests/helpers/studio_live_rig.py: a square agent of media, its helper, and
a scribe no card matches. tests/test_studio_live_plan.py runs it:

    python -m tests.helpers.studio_live_plan plan [--shots DIR]
        Live opens with the plan under it (the toggle on by default): main's block, the build and read tiers, the media
        square, the implicit tier dim, "not in the plan" with the scribe and why; each agent inside its block; main's line
        into each tier and square with its when label, the dash only on lines into blocks at work; no two boxes overlap,
        no bar text spills; the toggle off draws the grouped tree, on again the blocks; part 3 (studio_live_plan_more.py):
        each agent's waits-on fact (an agent, a model reply, a tool, nothing, you), the sentence and the waiting path for a
        tool wait and for an ask, the sentence steady while the tool's seconds tick, a click centres the agent; a task
        labels its line then fades to the when, the line's hover card, a click opens Conversations on the pair; part 4:
        far / mid / near by the switch, the near thought, the wheel keeps the agent under the pointer; Fit with thirty
        more agents lands on far, every block readable, nothing overlapping

The last stdout line is a JSON object of what it saw (exit 2: no Chrome). No model is called."""
from __future__ import annotations

import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.helpers.chrome_driver import Driver  # noqa: E402
from tests.helpers.studio_live_plan_more import MORE_STEPS  # noqa: E402

Q = "document.querySelector"
QA = "document.querySelectorAll"
MAP = f"{Q}('[data-testid=\"roles-live-map\"]')"
WORLD = f"{Q}('[data-testid=\"roles-live-world\"]')"
DOES = "Reads and makes images, audio, video and PDFs for a model that cannot."

READ = """[...document.querySelectorAll('[data-testid="live-block"]')].map((b) => {
  const bar = document.querySelector(`[data-testid="live-block-bar"][data-block="${b.dataset.block}"]`);
  const t = (s) => bar.querySelector(s)?.textContent || '';
  const r = b.getBoundingClientRect();
  const inside = [...document.querySelectorAll('[data-testid="roles-live-node"]')].filter((n) => {
    const q = n.getBoundingClientRect(); return q.left >= r.left - 0.5 && q.right <= r.right + 0.5 && q.top >= r.top - 0.5 && q.bottom <= r.bottom + 0.5; })
    .map((n) => n.dataset.agent);
  const cut = [...bar.querySelectorAll('.pb-title, .pb-counts, .pb-purpose')].filter((e) => e.scrollWidth > e.clientWidth + 1 && getComputedStyle(e).textOverflow !== 'ellipsis');
  return {id: b.dataset.block, kind: b.dataset.kind, used: !!b.dataset.used, title: t('[data-testid="live-block-title"]'),
          counts: t('[data-testid="live-block-counts"]'), purpose: t('[data-testid="live-block-purpose"]'), inside,
          spill: bar.scrollHeight > bar.clientHeight + 1, cut: cut.length, color: getComputedStyle(bar.querySelector('.pb-title')).color};
})"""

OVERLAP = """(() => { const r = [...document.querySelectorAll('[data-testid="roles-live-node"], [data-testid="live-block-bar"], [data-testid="live-plan-when"]')]
  .map((e) => [e.dataset.testid, e.dataset.agent || e.dataset.block || e.dataset.to, e.getBoundingClientRect()]);
  const hits = [];
  for (let i = 0; i < r.length; i++) for (let j = i + 1; j < r.length; j++) { const a = r[i][2], b = r[j][2];
    if (a.left < b.right - 0.5 && b.left < a.right - 0.5 && a.top < b.bottom - 0.5 && b.top < a.bottom - 0.5) hits.push(r[i][1] + '/' + r[j][1]); }
  return hits; })()"""


def seed_lineup(state: Path) -> None:
    """halo-dev-cycle with two tiers that say what they are for, and the media square."""
    import yaml
    p = state / "teams" / "halo-dev-cycle.yaml"
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    raw["tiers"] = [{"name": "top", "members": ["boss"]}, {"name": "build", "purpose": "the builders", "members": ["worker", "verify"]},
                    {"name": "read", "purpose": "the readers", "members": ["research"]}]
    raw["workflows"] = ["media"]
    raw.setdefault("delegation", {})["max_depth"] = 3
    p.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")


def rows() -> list:
    now = time.time()

    def row(aid, name, role, parent="main", **more):
        return {"agent_id": aid, "parent": parent, "name": name, "role": role, "bio": role, "lineup": "halo-dev-cycle", "model": "or:mock/cheap-fast",
                "kind": "member", "task": f"{name}: its part", "since": now - 20, "state": "running", "turns": 1, "cost_usd": 0.002,
                "current": "thinking", "last_text": "", "transcript": None, **more}
    return [row("sqm1", "media", "media", square={"name": "media", "engine": "session", "does": DOES}),
            row("sqh1", "listener", "listener", parent="sqm1"),
            row("scr1", "scribe", "scribe")]


def open_plan(c, rig) -> dict:
    from tests.helpers.studio_live_rig import Live
    lv = rig.plan_live = Live(rig, extra=())
    for r in rows():
        lv.rows[r["agent_id"]] = r
    lv.refresh()
    rig.plan = ""  # the default: the toggle untouched
    c.go(rig.url("agents", "&view=live&scope=here"))
    out = {"plan_on": c.wait(f"{WORLD}?.dataset.plan === 'on' && {QA}('[data-testid=\"live-block\"]').length >= 5 && "
                             f"{Q}('[data-testid=\"live-plan-toggle\"]').getAttribute('aria-pressed')", 40)}
    c.click_on(f"{Q}('[data-testid=\"live-level-mid\"]')")  # part 4 draws the agents from the mid level
    out["opened_level"] = c.wait(f"{WORLD}.dataset.level === 'mid' && {QA}('[data-testid=\"roles-live-node\"]').length >= 6 && 'mid'", 15)
    return out


def blocks(c, rig) -> dict:
    out = {"blocks": c.js(READ)}
    out["lines"] = c.js(f"[...{QA}('[data-testid=\"live-plan-line\"]')].map((l) => [l.dataset.to, !!l.dataset.live])")
    out["whens"] = c.js(f"[...{QA}('[data-testid=\"live-plan-when\"]')].map((l) => [l.dataset.to, l.textContent])")
    out["flows"] = c.js(f"{QA}('.pb-line + .rlm-edge-flow, .rlm-edge-flow').length")
    out["overlap"] = c.js(OVERLAP)
    out["bar_heights"] = c.js(f"[...{QA}('[data-testid=\"live-block-bar\"], [data-testid=\"live-narration\"]')].map((b) => Math.round(b.getBoundingClientRect().height))")
    return out


def toggle(c, rig) -> dict:
    btn = f"{Q}('[data-testid=\"live-plan-toggle\"]')"
    c.click_on(f"{Q}('[data-testid=\"live-level-mid\"]')")  # the mid level: far draws blocks either way
    c.wait(f"{WORLD}.dataset.level === 'mid'", 10)
    c.click_on(btn)
    out = {"off": c.wait(f"!{WORLD}.dataset.plan && {btn}.getAttribute('aria-pressed') === 'false' && !{Q}('[data-testid=\"live-block\"]') && "
                         f"{QA}('[data-testid=\"roles-live-edge\"]').length", 15)}
    c.click_on(btn)
    out["on_again"] = c.wait(f"{WORLD}.dataset.plan === 'on' && {QA}('[data-testid=\"live-block\"]').length", 15)
    return out


def shots(c, rig, folder: str) -> dict:
    if not folder:
        return {}
    Path(folder).mkdir(parents=True, exist_ok=True)
    c.click_on(f"{Q}('[data-testid=\"roles-live-fit\"]')")
    time.sleep(0.6)
    c.shot(str(Path(folder) / "live-plan.png"), 1500, 900, 1)
    return {"shots": folder}


class LivePlanDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from tests.helpers.studio_fleet_rig import StudioFleetRig
        folder = self.argv[self.argv.index("--shots") + 1] if "--shots" in self.argv else ""
        with StudioFleetRig() as rig:
            seed_lineup(rig.state)
            rig.full = False  # the default arrangement: the canvas has the page
            a = (c, rig)
            yield ((open_plan, a), (blocks, a), (shots, (c, rig, folder)), (toggle, a), *((fn, a) for fn in MORE_STEPS))


if __name__ == "__main__":
    sys.exit(LivePlanDriver(sys.argv[1:]).main())
