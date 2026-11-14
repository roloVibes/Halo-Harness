"""tests.helpers.studio_packs_bundle -- the bundle panel's `api` step of tests/helpers/studio_packs.py (Halo 3.3.10.0
R3; docs/EXTENSION_API.md "Studio contributions"): on the Hello section, with studio-script granted by the step
before, the fixture's hello.js buttons each call one api function and write its result line:

- publish: hello.said shows in the pack's own events panel, and the bundle's on() hears its own publish;
- an undeclared kind is refused with the server's line;
- getData reads note.json from the pack's data folder; mode() reads the mode `halo pack mode` turned on;
- attention raises a row; route goes to the fleet (Agents -> Live), where the Attention queue shows that row, the pack named.
"""
from __future__ import annotations

import json

from tests.helpers.studio_packs_steps import CUR, panel, press, q, qa

GREET = "studio-bundle--greet"


def _click(c, name: str, want: str, timeout: float = 15) -> str:
    """Press the bundle's `bundle-<name>` button and wait for its result line to say something other than '...'."""
    out = panel(GREET, f"[data-testid=bundle-{name}-result]")
    press(c, panel(GREET, f"[data-testid=bundle-{name}]"))
    try:
        return c.wait(f"(({out})?.textContent || '').startsWith({json.dumps(want)}) && {out}.textContent", timeout)
    except TimeoutError:
        return str(c.js(f"({out})?.textContent || ''"))


def bundle_api(c, url, ctx) -> dict:
    from halo_harness.ext.files import data_dir
    from halo_harness.packs.mode_state import set_mode
    out: dict = {}
    c.wait(f"{CUR}.startsWith('Hello') && !!{panel(GREET, '[data-testid=bundle-publish]')}", 20)
    folder = data_dir("studio-bundle")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "note.json").write_text('{"note": "kept in the data folder"}', encoding="utf-8")
    ok, lines = set_mode("studio-bundle", "loud", True, by="cli")
    assert ok, lines
    out["bundle_publish"] = _click(c, "publish", "published")
    lines_sel = qa("[data-panel='studio-bundle--said'] [data-testid=pack-event-line]")
    c.wait(f"{lines_sel}.length >= 1", 15)
    out["bundle_events_panel"] = c.js(f"{lines_sel}.map((l) => [l.querySelector('.fac-kind').textContent, l.querySelector('.fac-text').textContent])")
    heard = panel(GREET, "[data-testid=bundle-on-result]")
    out["bundle_on"] = c.wait(f"({heard})?.textContent.startsWith('heard') && {heard}.textContent", 15)
    out["bundle_publish_bad"] = _click(c, "publish-bad", "error:")
    out["bundle_getdata"] = _click(c, "getdata", "{")
    out["bundle_mode"] = _click(c, "mode", "mode ")
    out["bundle_attention"] = _click(c, "attention", "row ")
    from halo_harness.packs import state as S  # 3.3.14.0 R1 (#4): the page asks to change its own grant
    out["bundle_grant_self"] = _click(c, "grant-self", "lib: ")
    out["bundle_grants_after"] = S.granted("studio-bundle", S.load(ctx["state"]))
    press(c, panel(GREET, "[data-testid=bundle-route]"))
    out["bundle_route"] = c.wait(f"{CUR}.startsWith('Agents') && {CUR}", 15)  # a core section by its id
    from tests.helpers.studio_packs_steps import fleet_queue
    fleet_queue(c)
    row = q('[data-panel="fleet-attention"] [data-testid=fleet-attn-row][data-kind="pack:studio-bundle:hello.ask"]')
    c.wait(f"!!{row}", 25)
    out["bundle_attn_what"] = c.js(f"{row}.querySelector('.fat-what').textContent")
    out["bundle_attn_chip"] = c.js(f"{row}.querySelector('.fat-kind').textContent")
    return out
