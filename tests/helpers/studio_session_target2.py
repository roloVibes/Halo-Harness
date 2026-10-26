"""tests.helpers.studio_session_target2 -- the second half of
tests/helpers/studio_session_target.py's `target` run (Halo 3.3.0.0 R6):
Tab / Shift+Tab in the Steer field cycling the target among the session's
live agents (the field keeping the keyboard and its text), Escape out of the
field following again, `s` on a focused row making its agent the target with
the field focused, and Export: the download's name and its text read back
through the page (URL.createObjectURL wrapped), the bytes the route serves.
No model is called."""
from __future__ import annotations

import json
import time

from tests.helpers.studio_session_steer import AGENT_PICK, AREA, COL, LINES
from tests.helpers.studio_session_target import PILL, press

LIVE = ("queued", "running", "waiting", "paused")
TARGET_KEY = f"({COL}.dataset.target || '')"


def _clear_field(c) -> None:
    c.js(f"(() => {{ const a = {AREA}; Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set.call(a, ''); "
         "a.dispatchEvent(new Event('input', {bubbles: true})); return 1; })()")


def keys(c, lv) -> dict:
    """Tab / Shift+Tab cycle the target, the text stays; Escape follows again; `s` on a row steers it."""
    out: dict = {}
    c.click_on(AREA)
    c.wait(f"document.activeElement === {AREA} && 1", 5)
    _clear_field(c)
    c.type_text("KEEP")
    before = c.js(TARGET_KEY)
    live = c.js(f"[...{AGENT_PICK}.options].map((o) => o.value).filter((v) => v && {list(LIVE)!r}.includes("
                "document.querySelector(`[data-testid=\"session-map\"] [data-testid=\"fleet-node\"][data-key=\"${v}\"]`)?.dataset.state))") or []
    out["tab_live"], out["tab_before"] = live, before
    out["tab_expected"] = live[(live.index(before) + 1) % len(live)] if before in live else (live[0] if live else "")
    press(c, "Tab", "Tab", 9)
    out["tab_after"] = c.wait(f"{TARGET_KEY} !== {json.dumps(before)} && {TARGET_KEY}", 5)
    out["tab_kept"] = c.js(f"[document.activeElement === {AREA}, {AREA}.value]")
    out["tab_line"] = c.js(f"{COL}.querySelector('[data-testid=\"live-target\"]').dataset.key")
    press(c, "Tab", "Tab", 9, shift=True)
    out["shift_tab"] = c.wait(f"{TARGET_KEY} === {json.dumps(before)} && {TARGET_KEY}", 5)
    out["esc_paused"] = c.js(f"!{COL}.dataset.follow")
    press(c, "Escape", "Escape", 27)
    out["esc_follows"] = c.wait(f"{COL}.dataset.follow === 'true' && !{PILL} && document.activeElement !== {AREA} && 'follows'", 5) or False
    impl = lv.key("implementer")
    lv.say("implementer", "GOLF writes the change. ")
    row = f"{LINES}.filter((l) => l.dataset.key === '{impl}').pop()"
    c.wait(f"!!{row}", 10)
    c.js(f"{row}.scrollIntoView({{block: 'center'}}); {row}.focus(); 1")
    out["row_focused"] = c.js(f"document.activeElement === {row}")
    press(c, "s", "KeyS", 83)
    out["s_key"] = c.wait(f"{TARGET_KEY} === '{impl}' && document.activeElement === {AREA} && {TARGET_KEY}", 5)
    out["impl_key"] = impl
    press(c, "Escape", "Escape", 27)
    return out


HOOK = ("(() => { if (window.__traceHook) return 1; window.__traceHook = 1; const make = URL.createObjectURL; "
        "URL.createObjectURL = (b) => { window.__traceBlob = b; return make.call(URL, b); }; "
        "const click = HTMLAnchorElement.prototype.click; HTMLAnchorElement.prototype.click = function () { "
        "if (this.dataset.testid === 'trace-link') { window.__traceName = this.download; return; } return click.call(this); }; return 1; })()")


def export(c, rig) -> dict:
    """Export on the header: the browser gets halo-trace-<sid>-<stamp>.md, its text the route's trace."""
    from halo_harness.session_trace_cli import find_session_log, trace_for_path
    out: dict = {"sid": rig.act.session_id}
    out["buttons"] = c.js(f"[...{COL}.querySelectorAll('[data-testid=\"trace-export\"]')].map((b) => [b.dataset.where, b.textContent.trim(), !b.disabled])")
    c.js(HOOK)
    path, why = find_session_log(rig.act.session_id)
    out["log_found"] = why or "found"
    before = trace_for_path(path) if path else ""
    c.click_on(f"{COL}.querySelector('[data-testid=\"trace-export\"][data-where=\"head\"]')")
    out["name"] = c.wait("window.__traceName", 15)
    text = c.js("window.__traceBlob.text()") or ""
    after = trace_for_path(path) if path else ""
    out["head"] = text.split("\n", 1)[0]
    out["has_totals"] = "\n- Totals: turns " in text
    out["same_as_route"] = text in (before, after)
    out["toast"] = c.wait("document.querySelector('.toasts')?.textContent.includes('Saved halo-trace-') && 'saved'", 10) or False
    time.sleep(0.2)
    return out
