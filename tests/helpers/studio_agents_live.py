"""tests.helpers.studio_agents_live -- Agents -> Live's own pieces (Halo 3.3.16.0 R2) in headless Chrome on the driver
base, over a scratch home (this harness alone, no session). tests/test_studio_agents.py runs it:

    python -m tests.helpers.studio_agents_live live   the Attention chip on every view, its panel closed on load, opened
                                                      by the chip and closed by A; Live's inspector at a glance with
                                                      nothing picked

The last stdout line is a JSON object of what it saw (exit 2: no Chrome)."""
from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.chrome_driver import Driver  # noqa: E402
from tests.helpers.studio_agents import key, open_page  # noqa: E402

VIEW = "document.querySelector('[data-testid=\"agents\"]')?.dataset.view"
MAP = "document.querySelector('[data-testid=\"roles-live-map\"]')"
CHIP = "document.querySelector('[data-testid=\"agents-attention\"]')"
PANEL = "document.querySelector('[data-testid=\"fleet-attention\"]')"


def chip(c, page) -> dict:
    out = {}
    for view in ("cast", "live", "workflows"):  # 3.4.0.0 D: Runs went
        open_page(c, page, f"mode=agents&view={view}")
        out[view] = c.wait(f"{VIEW} === '{view}' && !!{CHIP} && [{CHIP}.dataset.count, {CHIP}.dataset.tone || '', !!{PANEL}]", 30)
    c.click_on(CHIP)
    out["chip_opened"] = c.wait(f"!!{PANEL} && {PANEL}.dataset.panel", 10)
    out["rows_match"] = c.wait(f"(document.querySelector('[data-testid=\"fleet-attn-empty\"]') || document.querySelector("
                               f"'[data-testid=\"fleet-attention-list\"]')) && +{CHIP}.dataset.count === "
                               "document.querySelectorAll('[data-testid=\"fleet-attn-row\"]').length", 15)
    c.js("document.activeElement?.blur(); document.body.focus(); 1")
    key(c, "a")
    out["a_closes"] = c.wait(f"!{PANEL} && 'closed'", 10)
    key(c, "a")
    out["a_opens"] = c.wait(f"!!{PANEL} && 'open'", 10)
    return out


def glance(c, page) -> dict:
    from tests.helpers.studio_live_panels import open_strip
    open_page(c, page, "mode=agents&view=live")
    open_strip(c, "roles-inspector")  # a strip on load (one thing open per section); its chevron opens it
    body = "document.querySelector('[data-testid=\"live-inspector\"]')"
    out = {"none": c.wait(f"{body}?.dataset.pick === 'none' && !!document.querySelector('[data-testid=\"live-glance\"]') && "
                          "[...document.querySelectorAll('[data-testid=\"live-glance-lines\"] dt')].map((d) => d.textContent)", 30)}
    return out


class AgentsLiveDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_studio import serve
        from halo_harness.config.paths import bridge_home
        from halo_harness.studio.server import url_for
        state = bridge_home()
        state.mkdir(parents=True, exist_ok=True)
        srv, _url = serve(state)
        base = url_for(srv)

        def page(query: str) -> str:
            return base.replace("/#t=", f"/?{query}&feed=off&tour=off#t=")
        try:
            args = (c, page)
            yield ((chip, args), (glance, args))
        finally:
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    sys.exit(AgentsLiveDriver(sys.argv[1:]).main())
