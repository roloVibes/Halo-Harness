"""tests.helpers.studio_session_cost_map -- Session's Cost graphics and its
map drawn as a tree (Halo 3.1.5.0 R3) in headless Chrome on the driver base,
over tests/helpers/studio_session_rig.py with three extra agents and scripted
session figures (tests/helpers/studio_live_rig.py).
tests/test_studio_session_cost_map.py runs it as a subprocess:

    python -m tests.helpers.studio_session_cost_map costmap   the context bar at 50 / 85 / 97 %, the sparkline
                                                              gaining points as the spend rises, cost per turn and the
                                                              share bar, a node's tool clock, the tree's fan (main's
                                                              children side by side under it, no two labels touching),
                                                              the state colours on node and edge, done fading, failed
                                                              staying (motion pinned to no-preference; then under
                                                              reduce a done node is green with no fade); then (3.1.8.0
                                                              R6) the figures moving on the session's own message_end /
                                                              status frames, a GET from before them never pulling them
                                                              back, a sub-agent's frames ignored, a finished child
                                                              counted once and TURNS one unit (`figures`); then (3.3.3.1)
                                                              a "+" on the spend when main's model reports no price
                                                              and main's line saying "no price" (`partial`); then
                                                              (3.3.5.0 R4) the last prompt's composition bar and the
                                                              Live composer's preflight buttons
                                                              (studio_cost_composition.py)

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

CTX = "document.querySelector('[data-testid=\"session-cost-context\"]')"
SPARK = "document.querySelector('[data-testid=\"session-cost-spark\"]')"


def costmap(c, rig) -> dict:
    from tests.helpers.studio_live_rig import Live
    lv = rig.cost_live = Live(rig)
    out: dict = {}
    # 3.3.3.1: the rig's real session runs an unpriced mock model (its status says cost_complete false); these
    # steps read whole figures, so the seeded row says every part is priced (`partial` below reads the "+")
    lv.refresh(context_tokens=50_000, context_limit=100_000, cost_usd=0.010, turns=2, cost_complete=True, cost_unknown=[])
    from tests.helpers.chrome_driver import emulate_motion
    emulate_motion(c, "no-preference")  # the done fade is an animation: the same media on every runner
    c.go(rig.url("session"))
    c.wait(f"!!{CTX} && document.querySelectorAll('[data-testid=\"session-cost-agent\"]').length >= 1", 40)  # 3.6.0.0 R5: no tree
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
    lv.state("docs", state="waiting")  # the states the figures below count from (the tree that drew them went, 3.6.0.0 R5)
    lv.state("tester", state="done", last_text="the basket suite passes")
    lv.state("reviewer", state="failed", last_text="the diff did not apply")
    time.sleep(1.0)
    return out


def _seen(c, expr: str, timeout: float):
    """`c.wait`, or None when it does not come (the step goes on; the test names what was missing)."""
    try:
        return c.wait(expr, timeout)
    except TimeoutError:
        return None


FIG = "document.querySelector('[data-testid=\"session-cost-{}\"]')?.textContent"
FIGS_JS = "[" + ", ".join(FIG.format(k) for k in ("usd", "in", "out", "turns", "per-turn")) + f", {CTX}?.dataset.pct]"
SEGS_JS = ("[...document.querySelectorAll('[data-testid=\"session-cost-share-seg\"]')].map((s) => [s.dataset.key.split('|')[2], +s.style.flexGrow])")


def figures(c, rig) -> dict:
    """3.1.8.0 R6: main mid-turn on its gated sub-agents; the figures move on the session's own frames (no cache
    clear, no sessions frame), a GET from before them never pulls them back, a status frame with no totals and a
    sub-agent's frames leave them, a finished child is counted once, TURNS is the session's user turns."""
    lv, out = rig.cost_live, {}
    pub = lambda event, data, turn=3, aid=None: rig.server.events.publish({"session_id": lv.sid, "harness": lv.hid, "event": event,  # noqa: E731
                                                                            "agent_id": aid, "turn": turn, "data": data, "ts": time.time()})
    out["fig_before"] = c.js(FIGS_JS)
    t0 = time.monotonic()
    pub("message_end", {"stop_reason": "tool_use", "usage": {}, "cost_usd": 0.2468, "context_pct": 60.0, "context_tokens": 60_000, "context_limit": 100_000,
                        "total_input_tokens": 54_321, "total_output_tokens": 4_321, "saved_usd": None})
    moved = _seen(c, f"{FIG.format('usd')} === '$0.2468' && {FIG.format('in')} === '54.3k' && {FIG.format('turns')} === '3' && 'moved'", 5)
    out["fig_moved"] = [moved, round(time.monotonic() - t0, 2)]
    lv.refresh(cost_usd=0.2000, tokens_in=50_000, tokens_out=4_000, turns=2, context_tokens=10_000, title="R6 a GET from before the frame")
    out["fig_get_landed"] = _seen(c, "document.querySelector('.sco-head')?.textContent.includes('R6 a GET') && 'landed'", 10)
    lv.fields.update(cost_usd=0.2468, tokens_in=54_321, tokens_out=4_321, turns=3, context_tokens=60_000)  # later answers agree with the frame
    out["fig_after_get"] = c.js(FIGS_JS)
    pub("status", {"phase": "thinking", "model": "or:mock/r6-status", "turn": 3, "cost_usd": None, "context_tokens": None,
                   "context_limit": None, "total_input_tokens": None, "total_output_tokens": None})
    out["fig_status_landed"] = _seen(c, "document.querySelector('[data-testid=\"session-cost-model\"]')?.textContent === 'r6-status' && 'landed'", 5)
    out["fig_after_status"] = c.js(FIGS_JS)
    pub("message_end", {"cost_usd": 0.0009, "total_input_tokens": 12, "total_output_tokens": 3, "context_tokens": 1, "context_limit": 10}, 1, lv.aid("tester"))
    pub("status", {"phase": "idle", "model": "or:mock/child", "turn": 1, "cost_usd": 0.0009, "session_id": "agent-t7e5s1t0"}, 1)
    time.sleep(0.8)
    out["fig_after_child"] = c.js(FIGS_JS + ".concat([document.querySelector('[data-testid=\"session-cost-model\"]')?.textContent])")
    lv.state("main", cost_usd=0.2468)  # main's own row figure is the session's total: it holds the finished tester's 0.012
    out["fig_share"] = c.js(SEGS_JS)
    main = f"document.querySelector('[data-testid=\"session-cost-agent\"][data-key=\"{lv.key('main')}\"]')"
    out["fig_main_line"] = c.js(f"[{main}?.querySelector('[data-testid=\"session-cost-agent-usd\"]')?.textContent, "
                                f"{main}?.querySelector('[data-testid=\"session-cost-agent-calls\"]')?.textContent]")
    return out


def partial(c, rig) -> dict:
    """3.3.3.1: the session's spend is the priced part; main's own model reports no price (`cost_complete` false,
    `cost_unknown` its ref) -> the ticker carries a "+" titled with the model, PER TURN too, and main's line says
    "no price" (the finished tester holds the whole priced spend, so main's own is nothing priced)."""
    lv, out = rig.cost_live, {}
    rows = [s for h in rig.api("GET", "live")[1].get("harnesses", []) for s in h.get("sessions") or [] if s.get("session_id") == lv.sid]
    main_row = next((a for a in (rows[0].get("agents") or []) if a.get("agent_id") == "main"), {}) if rows else {}
    model = main_row.get("model") or c.js("document.querySelector('[data-testid=\"session-cost-model\"]')?.title") or ""
    lv.state("tester", cost_usd=3.63)
    lv.state("main", cost_usd=3.63)
    lv.refresh(cost_usd=3.63, cost_complete=False, cost_unknown=[model], title="3.3.3.1 cost counts what it knows")
    plus = "document.querySelector('[data-testid=\"session-cost-partial\"]')"
    usd = "document.querySelector('[data-testid=\"session-cost-usd\"]')?.textContent"
    out["partial"] = _seen(c, f"!!{plus} && {usd} === '$3.63+' && {usd}", 10) or c.js(usd)  # the ticker counts up to it
    out["partial_title"] = c.js(f"{plus}?.title")
    out["partial_per_turn"] = c.js(FIG.format("per-turn"))
    main = f"document.querySelector('[data-testid=\"session-cost-agent\"][data-key=\"{lv.key('main')}\"]')"
    out["noprice"] = _seen(c, f"{main}?.querySelector('[data-testid=\"session-cost-noprice\"]')?.textContent", 10)
    out["partial_model"] = model.split(":", 1)[-1]
    lv.refresh(cost_complete=False, cost_unknown=[model, "cp:work"])  # 3.3.17.0 R2: a Copilot part says its own reason
    out["copilot_line"] = _seen(c, "document.querySelector('[data-testid=\"session-cost-copilot\"]')?.textContent", 10)
    lv.refresh(cost_complete=True, cost_unknown=[])
    out["complete_again"] = _seen(c, f"!{plus} && !{main}?.querySelector('[data-testid=\"session-cost-noprice\"]') && 'gone'", 10)
    return out


class CostMapDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from tests.helpers.studio_session_rig import StudioSessionRig
        with StudioSessionRig() as rig:
            from tests.helpers.studio_cost_composition import composition  # 3.3.5.0 R4: the prompt budget
            yield ((costmap, (c, rig)), (figures, (c, rig)), (partial, (c, rig)), (composition, (c, rig)))


if __name__ == "__main__":
    sys.exit(CostMapDriver(sys.argv[1:]).main())
