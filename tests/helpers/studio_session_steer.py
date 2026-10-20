"""tests.helpers.studio_session_steer -- Session's Live column, Halo 3.1.7.0
R1 "the steer is always at hand", through real clicks, keys and the pointer
in headless Chrome on the driver base (tests/helpers/chrome_driver.Driver),
over tests/helpers/studio_fleet_rig.py (this harness's real session: a lead,
an implementer and a researcher mid-work behind the real Controller) with
three extra agents and scripted feed frames (tests/helpers/studio_live_rig.py).
Studio's command route to a session is recorded (fleet_api.forward wrapped),
so a steer is seen reaching the main agent's control socket and its answer.
tests/test_studio_session_steer.py runs it as a subprocess:

    python -m tests.helpers.studio_session_steer steer   the Steer box at the foot with nothing pinned, addressed to
                                                          main; a steer sent there echoing as a YOU line at once and
                                                          reaching main's command route; the "steer" on a tag's hover
                                                          and on a map node's (pin + the box focused); the agent pick
                                                          following the pin; the strip's lanes and a lane click; the
                                                          kind pick hiding text; a finished agent's box disabled with
                                                          one line; Stop asking first; Pause reaching the route;
                                                          in Fleet the chip opening the Agent panel's box
                                                          (tests/helpers/studio_session_steer2.py)

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

COL = "document.querySelector('[data-testid=\"session-live-detail\"]')"
LINES = "[...document.querySelectorAll('[data-testid=\"session-live-line\"]')]"
BOX = f"{COL}.querySelector('[data-testid=\"session-live-steer\"]')"
AREA = f"{BOX}.querySelector('[data-testid=\"fleet-steer\"]')"
AGENT_PICK = f"{COL}.querySelector('[data-testid=\"session-live-agent\"]')"
KIND_PICK = f"{COL}.querySelector('[data-testid=\"session-live-kind-pick\"]')"
SENT = "check the tax rule before the discount"


def box(c) -> dict:
    """The Steer box at the foot: who it talks to, its header, whether it takes text, Pause / Stop, where the keyboard is."""
    return c.js(f"(() => {{ const b = {BOX}; if (!b) return null; const a = b.querySelector('[data-testid=\"fleet-steer\"]'); "
                "const btn = (id) => b.querySelector(`[data-testid=\"${id}\"]`); "
                "return {key: b.dataset.key, main: b.dataset.main === 'true', head: b.querySelector('.slv-steer-to .rail-label').textContent + ' ' + "
                "b.querySelector('[data-testid=\"session-live-steer-to\"]').textContent, enabled: !a.disabled, placeholder: a.placeholder, "
                "pause: btn('session-live-pause') ? [btn('session-live-pause').textContent, !btn('session-live-pause').disabled] : null, "
                "stop: btn('session-live-stop') ? [btn('session-live-stop').textContent, !btn('session-live-stop').disabled] : null, "
                "focused: document.activeElement === a, pinned: " + COL + ".dataset.pinned || ''}; })()") or {}


def pick(c, expr: str, value: str) -> None:
    """Choose `value` in the <select> `expr` the way a user's change does."""
    import json
    c.js(f"(() => {{ const el = {expr}; const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set; "
         f"set.call(el, {json.dumps(value)}); el.dispatchEvent(new Event('change', {{bubbles: true}})); return 1; }})()")


def record_forward(rig) -> list:
    """Every command Studio forwards to a session's socket, with its answer (restored on close)."""
    from halo_harness.studio import fleet_api
    orig, seen = fleet_api.forward, []

    def forward(sid, cmd, fields):
        status, result = orig(sid, cmd, fields)
        seen.append({"sid": sid, "cmd": cmd, "fields": dict(fields), "status": status, "result": result})
        return status, result
    fleet_api.forward = forward
    rig.closers.append(lambda: setattr(fleet_api, "forward", orig))
    return seen


def shown(c, expr: str, timeout: float = 5) -> str:
    """'1' once the element `expr` evaluates to is fully shown (its opacity), else ''."""
    try:
        return c.wait(f"(() => {{ const e = {expr}; return e && getComputedStyle(e).opacity === '1' && '1'; }})()", timeout) or ""
    except TimeoutError:
        return ""


def hover(c, target: str, el: str, fx: float = 0.3, fy: float = 0.5, tries: int = 4) -> "tuple[str, str]":
    """Point at `target` (scrolled into view, the column settled) until `el` shows: ('1', '') or ('', what was under the pointer)."""
    under = ""
    for _ in range(tries):
        c.js(f"{target}.scrollIntoView({{block: 'center'}}); 1")
        time.sleep(0.4)
        x, y, w, h = c.rect(target)
        c.mouse("mouseMoved", 4, 4)
        c.mouse("mouseMoved", x + w * fx, y + h * fy)
        if shown(c, el, 2):
            return "1", ""
        under = c.js(f"(() => {{ const e = document.elementFromPoint({x + w * fx}, {y + h * fy}); return e ? (e.getAttribute('class') || e.tagName) : ''; }})()") or ""
    return "", under


def steer_main(c, rig, lv, sent: list) -> dict:
    """Nothing pinned: the box talks to main; a steer typed there echoes at once and reaches main's route."""
    from tests.helpers.fleet_rig import wait_for
    out: dict = {"main_key": lv.key("main"), "sid": rig.act.session_id}
    out["box_main"] = c.wait(f"!{COL}.dataset.pinned && {BOX} && {BOX}.dataset.key === '{lv.key('main')}' && 'ok'", 15) and box(c)
    c.click_on(AREA)
    c.type_text(SENT)
    t0 = time.time()
    c.key("Enter")
    you = f"{LINES}.find((l) => l.dataset.kind === 'you' && l.textContent.includes('{SENT}'))"
    out["you_line"] = c.wait(f"(() => {{ const l = {you}; return l && [l.dataset.key, l.querySelector('[data-testid=\"session-live-kind\"]').textContent]; }})()", 5)
    out["you_s"] = round(time.time() - t0, 2)
    got = wait_for(lambda: [d for d in sent if d["cmd"] == "agent_steer" and SENT in str(d["fields"].get("text"))], 20) or [{}]
    d = got[-1]
    out["steer_route"] = {"sid": d.get("sid"), "agent_id": (d.get("fields") or {}).get("agent_id"), "mode": (d.get("fields") or {}).get("mode"),
                          "status": d.get("status"), "delivered": (d.get("result") or {}).get("delivered")}
    out["steer_ack"] = c.wait("document.querySelector('.toasts')?.textContent.includes('Steered') && 'steered'", 15) or False
    out["steer_cleared"] = c.js(f"{AREA}.value === ''")
    return out


def tag_steer(c, lv) -> dict:
    """The researcher's line: its tag shows "steer" on hover; the click pins it and puts the keyboard in the box."""
    out: dict = {}
    res = lv.key("researcher")
    lv.say("researcher", "BRAVO reads the pricing notes. ")
    line = f"{LINES}.filter((l) => l.dataset.key === '{res}').pop()"
    c.wait(f"!!{line}", 10)
    btn = f"{line}.querySelector('[data-testid=\"session-live-steer-tag\"]')"
    c.mouse("mouseMoved", 4, 4)
    out["tag_hidden"] = c.js(f"getComputedStyle({btn}).opacity")
    out["tag_shown"], out["tag_under"] = hover(c, f"{line}.querySelector('[data-testid=\"session-live-tag\"]')", btn)
    c.click_on(btn)
    c.wait(f"{COL}.dataset.pinned === '{res}' && {BOX}.dataset.key === '{res}'", 5)
    time.sleep(0.2)
    out["tag_steer"] = box(c)
    out["res_key"] = res
    out["pick_after_tag"] = c.js(f"{AGENT_PICK}.value")
    pick(c, AGENT_PICK, "")
    out["pick_cleared"] = c.wait(f"!{COL}.dataset.pinned && {BOX}.dataset.key === '{lv.key('main')}' && 'main'", 5) or False
    return out


def node_steer(c, lv) -> dict:
    """The implementer's map node: "steer" on hover; the click pins it in Live, the box focused."""
    out: dict = {}
    impl = lv.key("implementer")
    node = f"document.querySelector('[data-testid=\"session-map\"] [data-testid=\"fleet-node\"][data-key=\"{impl}\"]')"
    chip = f"{node}.querySelector('[data-testid=\"fleet-node-steer\"]')"
    c.mouse("mouseMoved", 4, 4)
    out["node_hidden"] = c.js(f"getComputedStyle({chip}).opacity")
    out["node_shown"], out["node_under"] = hover(c, node, chip, 0.4, 0.7)
    c.click_on(chip)
    c.wait(f"{COL}.dataset.pinned === '{impl}' && {BOX}.dataset.key === '{impl}'", 5)
    time.sleep(0.2)
    out["node_steer"] = box(c)
    out["impl_key"] = impl
    out["pick_after_node"] = c.js(f"{AGENT_PICK}.value")
    c.mouse("mouseMoved", 4, 4)
    return out


class SteerDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from tests.helpers.studio_fleet_rig import StudioFleetRig
        from tests.helpers.studio_live_rig import Live
        from tests.helpers.studio_session_steer2 import done_box, fleet_chip, kinds, opened, pause, stop, strip
        with StudioFleetRig() as rig:
            lv = Live(rig)
            sent = record_forward(rig)
            yield ((opened, (c, rig)), (steer_main, (c, rig, lv, sent)), (tag_steer, (c, lv)), (node_steer, (c, lv)), (strip, (c, lv)),
                   (kinds, (c, lv)), (done_box, (c, lv)), (stop, (c, sent)), (pause, (c, lv, sent)), (fleet_chip, (c, rig, lv)))


if __name__ == "__main__":
    sys.exit(SteerDriver(sys.argv[1:]).main())
