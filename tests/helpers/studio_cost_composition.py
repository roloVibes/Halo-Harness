"""tests.helpers.studio_cost_composition -- Halo 3.3.5.0 R4: the prompt
budget's two Session pieces in headless Chrome, a step of the Cost driver
(tests/helpers/studio_session_cost_map.py) over its rig's session row
(tests/helpers/studio_live_rig.py `Live.refresh`):

* the Cost panel's composition bar (`session-cost-composition`): a segment per
  part sized by its tokens, a key per part with its count, the parts in their
  token colours, and a status frame's composition moving it;
* the Live composer's preflight (`session-live-preflight`): the line and the
  three buttons (`preflight-compact`, `preflight-switch` naming the model,
  `preflight-send`); a click posts the answer through the session's command
  route; no bigger-window model -> the switch button is disabled.
No model is called.
"""
from __future__ import annotations

import time

COMP = {"system": 3587, "memory": 9900, "topic_index": 6400, "tools_schema": 2100, "history": 8700, "user": 69, "total": 30756}
LINE = "prompt 41,104 tokens · window 32,768 · usable 16,386 · this will be cut"
BAR = "document.querySelector('[data-testid=\"session-cost-composition\"]')"
PF = "document.querySelector('[data-testid=\"session-live-preflight\"]')"
SEGS_JS = (f"[...({BAR}?.querySelectorAll('[data-testid=\"session-cost-composition-seg\"]') || [])]"
           ".map((s) => [s.dataset.part, +(+s.style.flexGrow).toFixed(3), getComputedStyle(s).backgroundColor])")
HOOK_JS = ("window.__pf = []; const f0 = window.fetch; window.fetch = (u, o) => { if (String(u).includes('/command'))"
           " window.__pf.push([String(u), (o && o.body) || '']); return f0(u, o); }; 'hooked'")


def composition(c, rig) -> dict:
    lv, out = rig.cost_live, {}
    lv.refresh(composition=dict(COMP))
    out["comp_total"] = c.wait(f"{BAR}?.dataset.total === '{COMP['total']}' && {BAR}.dataset.total", 10) or c.js(f"{BAR}?.dataset.total")
    time.sleep(0.2)
    out["comp_segs"] = c.js(SEGS_JS)
    out["comp_keys"] = c.js(f"[...({BAR}?.querySelectorAll('.sco-comp-key') || [])].map((k) => [k.dataset.part, +k.dataset.n, k.textContent.trim()])")
    out["comp_title"] = c.js(f"{BAR}?.title")
    moved = {**COMP, "user": 900, "total": 31587}
    lv.fields.update(composition=moved)  # later GET answers agree with the frame
    rig.server.events.publish({"session_id": lv.sid, "harness": lv.hid, "event": "status", "agent_id": None, "turn": 4,
                               "data": {"phase": "idle", "turn": 4, "composition": moved}, "ts": time.time()})
    out["comp_after_frame"] = c.wait(f"{BAR}?.dataset.total === '31587' && {BAR}.dataset.total", 10)
    lv.refresh(preflight={"id": "preflight-r4test", "line": LINE, "switch_to": "ol:wide:14b@lan", "default": "compact"})
    out["pf_line"] = c.wait(f"{PF}?.querySelector('[data-testid=\"preflight-line\"]')?.textContent", 15)
    out["pf_buttons"] = c.js(f"['compact', 'switch', 'send'].map((k) => {{ const b = {PF}?.querySelector(`[data-testid=\"preflight-${{k}}\"]`);"
                             " return b ? [k, b.textContent.trim(), b.disabled] : null; })")
    c.js(HOOK_JS)
    c.js(f"{PF}.querySelector('[data-testid=\"preflight-send\"]').click()")
    out["pf_posted"] = c.wait("window.__pf.length > 0 && window.__pf[0]", 10)
    lv.refresh(preflight={"id": "preflight-r4none", "line": LINE, "switch_to": None})
    out["pf_no_switch"] = c.wait(f"{PF}?.dataset.id === 'preflight-r4none' && "
                                 f"{PF}.querySelector('[data-testid=\"preflight-switch\"]').disabled && 'disabled'", 15)
    lv.refresh(preflight=None)
    out["pf_gone"] = c.wait(f"!{PF} && 'gone'", 15)
    return out
