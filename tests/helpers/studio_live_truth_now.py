"""tests.helpers.studio_live_truth_now -- the "now" scene of tests/helpers/studio_live_truth.py (Halo 3.3.18.0 "The living
canvas") over tests/helpers/studio_fleet_rig.py: this harness's real session (main, implementer, researcher at work) and
a member whose main waits on a question; extra agents through tests/helpers/studio_live_rig.py `Live`."""
from __future__ import annotations

import time

Q = "document.querySelector"
QA = "document.querySelectorAll"
VIEW = f"{Q}('[data-testid=\"agents\"]')?.dataset.view"
MAP = f"{Q}('[data-testid=\"roles-live-map\"]')"
LIVE = ("queued", "running", "waiting", "paused")


def node(aid: str) -> str:
    return f"{Q}('[data-testid=\"roles-live-node\"][data-agent=\"{aid}\"]')"


def group(part: str) -> str:
    return f"[...{QA}('[data-testid=\"live-group\"]')].find((g) => g.dataset.group.endsWith({part!r}))"


def live_now(rig) -> int:
    """The agents at work across the harnesses that count (this one, members online), from GET fleet."""
    _st, view = rig.api("GET", "fleet")
    n = 0
    for h in view.get("harnesses") or []:
        if not (h.get("local") or h.get("online") is not False):
            continue
        for s in h.get("sessions") or []:
            n += sum(1 for a in s.get("agents") or [] if a.get("state") in LIVE)
    return n


def opens_on_live(c, rig) -> dict:
    from tests.helpers.studio_session import alt
    c.go(rig.url("session"))
    c.wait(f"{QA}('[data-testid=\"section-tab\"]').length > 0", 40)
    c.js("document.activeElement?.blur()")
    alt(c, 2)
    out = {"alt2": c.wait(f"{VIEW} === 'live' && {MAP} && +{MAP}.dataset.nodes >= 3 && {VIEW}", 40)}
    for name, url in (("door_cast", rig.url("agents", "&view=cast")), ("door_roles", rig.url("roles"))):
        c.go("about:blank")
        c.go(url)
        out[name] = c.wait(f"{VIEW} === 'cast' && !!{Q}('[data-testid=\"roles-card\"]') && {VIEW}", 40)
    return out


def cast_line(c, rig) -> dict:
    chip = f"{Q}('[data-testid=\"cast-live-chip\"]')"
    want = live_now(rig)
    out = {"want_live": want, "plan_line": c.wait(f"{Q}('[data-testid=\"cast-plan-line\"]')?.textContent", 30)}
    out["chip"] = c.wait(f"+{chip}?.dataset.count === {want} && {chip}.textContent", 20)
    out["rail"] = c.wait(f"+{Q}('[data-testid=\"rail-fleet-count\"]')?.dataset.count === {want} && {want}", 20)
    c.click_on(chip)
    out["chip_goes"] = c.wait(f"{VIEW} === 'live' && {VIEW}", 15)
    return out


def _row(aid, name, step, state="running"):
    return {"agent_id": aid, "parent": "main", "name": name, "role": name, "bio": name, "lineup": "auto", "model": "or:mock/cheap-fast",
            "kind": "member", "task": f"{name}: check the basket", "since": time.time() - 5, "state": state, "turns": 1, "cost_usd": 0.001,
            "current": "thinking", "last_text": "", "transcript": None, "spawn": {"step": step, "description": "Check the basket", "lead": ""}}


def linger(c, rig) -> dict:
    """Two agents of one step (a group) finish: they stay their ten seconds, then leave, and the group with them."""
    from tests.helpers.studio_live_rig import Live
    lv = rig.truth_live = Live(rig, extra=())
    for aid, name in (("ln0", "lint-a"), ("ln1", "lint-b"), ("fx0", "fixer")):
        lv.rows[aid] = _row(aid, name, "main#9" if aid.startswith("ln") else "main#10")
    lv.refresh()
    c.go("about:blank")
    c.go(rig.url("agents", "&view=live&scope=here"))
    out = {"group": c.wait(f"{group('main#9')} && {node('ln0')} && {node('ln1')} && {node('fx0')} && +{group('main#9')}.dataset.count", 40)}
    lv.state("lint-a", state="done")
    lv.state("lint-b", state="done")
    t0 = time.time()
    out["done_drawn"] = c.wait(f"{node('ln0')}?.dataset.state === 'done' && {node('ln1')}?.dataset.state === 'done' && 'done'", 10)
    time.sleep(4)
    out["still_at_4s"] = c.js(f"!!{node('ln0')} && !!{group('main#9')}")
    c.wait(f"!{node('ln0')} && !{node('ln1')} && !{group('main#9')}", 25)
    out["left_after_s"] = round(time.time() - t0, 1)
    out["others_stay"] = c.js(f"!!{node('fx0')}")
    return out


def failed_stays(c, rig) -> dict:
    lv = rig.truth_live
    lv.state("fixer", state="failed")
    out = {"failed_state": c.wait(f"{node('fx0')}?.dataset.state === 'failed' && 'failed'", 15)}
    time.sleep(13)
    out["after_13s"] = c.js(f"{node('fx0')}?.dataset.state || ''")
    btn = f"{node('fx0')}.querySelector('[data-testid=\"roles-live-dismiss\"]')"
    out["dismiss_title"] = c.js(f"{btn}?.title || ''")
    c.click_on(btn)
    out["dismissed"] = c.wait(f"!{node('fx0')} && 'gone'", 10)
    c.go("about:blank")  # a failure from before the page loaded is past: not drawn
    c.go(rig.url("agents", "&view=live&scope=here"))
    c.wait(f"{MAP} && +{MAP}.dataset.nodes >= 3", 40)
    time.sleep(1.5)
    out["after_reload"] = c.js(f"!!{node('fx0')}")
    return out


NOW_STEPS = (opens_on_live, cast_line, linger, failed_stays)
