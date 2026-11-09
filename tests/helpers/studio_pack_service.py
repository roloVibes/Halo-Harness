"""tests.helpers.studio_pack_service -- the Pack Manager's service row (Halo 3.3.13.0 R3), one step of
tests/helpers/studio_pack_manager.py's driver run (after the policy row): the `service-pack` fixture installed into
the served home and enabled with `services`, a supervisor's pulse and its services file written as a running
supervisor writes them, the page re-opened: the row's `pm-service` chip says "service running since <hh:mm>", and
Stop asks the supervisor (services-want.json says stop).
"""
from __future__ import annotations

import json
import shutil
import time

from tests.helpers.studio_packs_steps import CUR, TABS, alt, q

ROW = "[data-testid=pm-installed-row][data-id=service-pack]"


def _text(sel: str) -> str:
    return f"({q(sel)}?.textContent || '')"


def service_row(c, url, ctx) -> dict:
    from halo_harness.packs import registry
    from halo_harness.packs.discover import find
    from halo_harness.packs.grants import enable as enable_pack
    from halo_harness.packs.install import install
    from halo_harness.supervise import pulse
    from halo_harness.supervise.services_rows import state_path, want_path, write_json
    from tests.helpers.packs_home import fixture
    state, proj = ctx["state"], ctx["state"].parent / "project"
    src = state.parent / "service-src" / "service-pack"
    shutil.copytree(fixture("service-pack"), src, ignore=shutil.ignore_patterns("__pycache__"))
    ok, lines = install(str(src), cwd=proj)
    assert ok, lines
    ok, lines = enable_pack(find("service-pack", cwd=proj), grant=["services"])
    assert ok, lines
    pulse.Pulse(state).write("running")
    write_json(state_path(state), {"version": 1, "services": {"service-pack/ticker": {
        "pack": "service-pack", "name": "ticker", "state": "running", "since": time.time(), "line": "ticking",
        "autostart": True, "restart": "on-failure", "health": "ok"}}})
    registry.invalidate()
    c.go("about:blank")
    c.go(url)
    c.wait(f"{TABS}.length >= 8", 40)
    alt(c, 6)  # 3.3.13.0 R2: Packs is the sixth section (Design is a pack now)
    c.wait(f"{CUR}.startsWith('Packs')", 15)
    chip = f"{ROW} [data-testid=pm-service]"
    text = c.wait(f"{_text(chip)}.includes('running since') && {_text(chip)}", 30)
    label = c.js(_text(f"{chip} [data-testid=pm-service-act]"))
    c.js(f"{q(chip + ' [data-testid=pm-service-act]')}?.click()")
    asked = c.wait(f"{_text('[data-testid=pm-last]')}.includes('asked the supervisor to stop') || "
                   f"document.body.textContent.includes('asked the supervisor to stop')", 20)
    want = json.loads(want_path(state).read_text(encoding="utf-8")) if want_path(state).exists() else {}
    return {"service_chip": text, "service_act": label, "service_asked": bool(asked), "service_want": want}
