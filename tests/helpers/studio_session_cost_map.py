"""tests.helpers.studio_session_cost_map -- Session's Cost graphics and its
map drawn as a tree (Halo 3.1.5.0 R3) in headless Chrome on the driver base,
over tests/helpers/studio_fleet_rig.py with three extra agents and scripted
session figures (tests/helpers/studio_live_rig.py).
tests/test_studio_session_cost_map.py runs it as a subprocess:

    python -m tests.helpers.studio_session_cost_map costmap   the context bar at 50 / 85 / 97 %, the sparkline
                                                              gaining points as the spend rises, cost per turn and the
                                                              share bar, a node's tool clock, the tree's fan (main's
                                                              children side by side under it, no two labels touching),
                                                              the state colours on node and edge, done fading, failed
                                                              staying

The last stdout line is a JSON object of what it saw (exit 2: no Chrome).
No model is called."""
from __future__ import annotations

import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.helpers.chrome_driver import Driver  # noqa: E402

MAP = "document.querySelector('[data-testid=\"session-map\"]')"
CTX = "document.querySelector('[data-testid=\"session-cost-context\"]')"
SPARK = "document.querySelector('[data-testid=\"session-cost-spark\"]')"


def node(key: str) -> str:
    return f"{MAP}.querySelector('[data-testid=\"fleet-node\"][data-key=\"{key}\"]')"


def edge(key: str) -> str:
    return f"{MAP}.querySelector('[data-testid=\"fleet-edge\"][data-to=\"{key}\"]')"


def xy(c, key: str) -> list:
    return c.js(f"(({node(key)}?.getAttribute('transform') || '').match(/[-0-9.]+/g) || []).map(Number)") or []


def labels_overlap(c) -> list:
    """Every pair of node names (or session titles) on the map whose boxes intersect."""
    js = (f"(() => {{ const r = [...{MAP}.querySelectorAll('.fm-name, .fm-title')].map((t) => [t.textContent, t.getBoundingClientRect()]);"
          " const out = []; for (let i = 0; i < r.length; i++) for (let j = i + 1; j < r.length; j++) { const a = r[i][1], b = r[j][1];"
          " if (a.left < b.right - 0.5 && b.left < a.right - 0.5 && a.top < b.bottom - 0.5 && b.top < a.bottom - 0.5) out.push([r[i][0], r[j][0]]); }"
          " return out; })()")
    return c.js(js) or []


def costmap(c, rig) -> dict:
    from tests.helpers.studio_live_rig import Live
    lv = Live(rig)
    out: dict = {}
    lv.refresh(context_tokens=50_000, context_limit=100_000, cost_usd=0.010, turns=2)
    c.go(rig.url("session"))
    c.wait(f"!!{CTX} && {MAP}.querySelectorAll('[data-testid=\"fleet-node\"]').length >= 6", 40)
    out["ctx"] = [[c.wait(f"{CTX}.dataset.pct === '50.0' && {CTX}.dataset.level", 10)]]
    for used, want in ((85_000, "85.0"), (97_000, "97.0")):
        lv.refresh(context_tokens=used)
        out["ctx"].append([c.wait(f"{CTX}.dataset.pct === '{want}' && {CTX}.dataset.level", 10), c.js(f"getComputedStyle({CTX}.querySelector('.sco-ctx-fill')).backgroundColor")])
    p0 = c.js(f"+{SPARK}.dataset.points") or 0
    for usd in (0.020, 0.035, 0.060):
        lv.refresh(cost_usd=usd)
        c.wait(f"document.querySelector('[data-testid=\"session-cost-usd\"]').textContent.includes('{usd:.4f}'.slice(0, 5))", 10)
        time.sleep(0.4)
    out["spark"] = [p0, c.js(f"+{SPARK}.dataset.points"), c.js(f"{SPARK}.querySelector('.sco-spark-line')?.getAttribute('d')?.split('L').length || 0")]
    out["per_turn"] = c.wait("document.querySelector('[data-testid=\"session-cost-per-turn\"]')?.textContent", 5)
    for name, usd in (("tester", 0.012), ("docs", 0.004)):
        lv.state(name, cost_usd=usd)
    out["share"] = c.wait("[...document.querySelectorAll('[data-testid=\"session-cost-share-seg\"]')].length >= 2 && "
                          "[...document.querySelectorAll('[data-testid=\"session-cost-share-seg\"]')].map((s) => [s.dataset.key.split('|')[2], +s.style.flexGrow])", 10)
    out["agent_tokens"] = c.js("[...document.querySelectorAll('[data-testid=\"session-cost-agent-tokens\"]')].map((t) => t.textContent)")
    lv.tool("tester", "Bash", "cm-1", "pytest -q")
    tool = f"{node(lv.key('tester'))}?.querySelector('[data-testid=\"fleet-node-tool\"]')"
    s0 = c.wait(f"{tool}?.dataset.secs", 10)
    time.sleep(2.2)
    out["node_secs"] = [s0, c.js(f"{tool}?.dataset.secs"), c.js(f"{tool}?.querySelector('.fm-tool-text')?.textContent")]
    main, kids = lv.key("main"), [lv.key(n) for n in ("implementer", "researcher", "tester", "docs", "reviewer")]
    out["tree"] = {"main": xy(c, main), "kids": [xy(c, k) for k in kids], "parents": c.js(f"[...{MAP}.querySelectorAll('[data-testid=\"fleet-node\"]')].map((n) => n.dataset.parent || '')")}
    out["overlaps"] = labels_overlap(c)
    out.update(states(c, lv))
    return out


def states(c, lv) -> dict:
    """waiting: amber on node and edge; done: green, fading back to the plain line after ten seconds; failed: red that stays."""
    out: dict = {}
    # 3.1.5.0 R3 follow-up: a frame says stopped while GET fleet still says running; the GET right after keeps the frame's state
    lv.spawn("f7e5h0s1", "fresher", "fresher", "or:mock/qwen3-coder", "Fresh: a frame newer than the GET")
    c.wait(f"{node(lv.key('fresher'))}?.dataset.state === 'running'", 10)
    lv.frame("fresher", "agent_state", {**lv.rows["f7e5h0s1"], "state": "stopped"})
    out["fresh_frame"] = c.wait(f"{node(lv.key('fresher'))}?.dataset.state === 'stopped' && 'stopped'", 10)
    lv.refresh(cost_usd=0.1234)  # the page asks GET fleet again (the sessions frame); the new spend shows its answer landed
    out["fresh_get_landed"] = c.wait("document.querySelector('[data-testid=\"session-cost-usd\"]')?.textContent === '$0.1234' && 'landed'", 15)
    out["fresh_api_says"] = next((a.get("state") for h in lv.rig.api("GET", "fleet")[1].get("harnesses", []) for s in h.get("sessions") or []
                                  for a in s.get("agents") or [] if a.get("agent_id") == "f7e5h0s1"), None)
    out["fresh_after_get"] = c.js(f"{node(lv.key('fresher'))}?.dataset.state")
    w, d, f = lv.key("docs"), lv.key("tester"), lv.key("reviewer")
    lv.state("docs", state="waiting")
    out["waiting"] = [c.wait(f"{node(w)}?.dataset.motion === 'waiting' && {edge(w)}?.dataset.motion", 10),
                      c.js(f"getComputedStyle({edge(w)}).stroke"), c.js(f"getComputedStyle(document.documentElement).getPropertyValue('--warn').trim()")]
    lv.state("tester", state="done", last_text="the basket suite passes")
    lv.state("reviewer", state="failed", last_text="the diff did not apply")
    out["done"] = [c.wait(f"{node(d)}?.dataset.motion === 'done' && {edge(d)}?.dataset.motion", 10), c.js(f"getComputedStyle({node(d)}.querySelector('.fm-shape')).animationName")]
    out["red"] = [c.wait(f"{node(f)}?.dataset.motion === 'error' && {edge(f)}?.dataset.motion", 10), c.js(f"getComputedStyle({edge(f)}).stroke"),
                     c.js("getComputedStyle(document.documentElement).getPropertyValue('--bad').trim()")]
    time.sleep(10.4)
    out["done_later"] = c.wait(f"{node(d)}?.dataset.motion !== 'done' && {node(d)}.dataset.motion", 6) or c.js(f"{node(d)}?.dataset.motion")
    out["red_later"] = c.js(f"{node(f)}?.dataset.motion")
    return out


class CostMapDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from tests.helpers.studio_fleet_rig import StudioFleetRig
        with StudioFleetRig() as rig:
            yield ((costmap, (c, rig)),)


if __name__ == "__main__":
    sys.exit(CostMapDriver(sys.argv[1:]).main())
