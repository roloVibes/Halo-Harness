"""tests.helpers.studio_packs_fleet -- the Fleet-capabilities-from-packs checks
of tests/test_packs_fleet_ui.py (Halo 3.2.0.0 R4), real clicks in headless
Chrome through the driver base, over a scratch home with the doc-review
fixture pack (enabled, bash granted; a catalog model that calls tools) and
fleet-needs-gpu (enabled; this host has no GPU under the test's no-spawn
rule); Studio is served in a thread of this process (no hub, no model call:
the mission's lead is a fake):

1. Fleet's Capabilities panel, expanded: this harness's card has a "packs"
   line with docs.review (available, the model and the grant) and gpu.render
   (not available: no GPU here);
2. a mission planned with the pack's lineup: the Mission panel's plan shows
   the part's need as "docs.review · pack doc-review on <this harness>", the
   head the mission's metadata, and with the part selected the pack
   inspector line (fleet/checklist.md, read through the pack's file route).

The last stdout line is the JSON of what it saw (exit 2: no Chrome)."""
from __future__ import annotations

import json
import shutil
import sys
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.chrome_driver import Driver  # noqa: E402

TOOLS_ROW = {"ref": "or:anthropic/claude-sonnet-4.6", "provider": "openrouter", "tools": True}
CAPS = "document.querySelector('[data-testid=\"fleet-capabilities\"]')"
MPANEL = "document.querySelector('[data-testid=\"fleet-mission\"]')"


def _q(sel: str) -> str:
    return f"document.querySelector({json.dumps(sel)})"


def capabilities(c, url, ctx) -> dict:
    from tests.helpers.studio_fleet_panels import open_strip, seen
    out: dict = {}
    c.go(url)
    c.wait(f"{CAPS}?.querySelector('.panel-about')?.textContent", 40)
    open_strip(c, "fleet-capabilities")
    expand = f"{CAPS}.querySelector('[data-testid=\"panel-compact\"]')"
    seen(c, expand)
    c.click_on(expand)
    c.wait("document.querySelectorAll('[data-testid=\"fleet-caps-card\"]').length >= 1", 40)
    out["caps_packs"] = c.wait("document.querySelectorAll('[data-testid=\"fleet-caps-pack\"]').length === 2 && "
                               "[...document.querySelectorAll('[data-testid=\"fleet-caps-pack\"]')].map((li) => "
                               "[li.dataset.name, li.dataset.available, li.querySelector('[data-testid=\"fleet-caps-pack-why\"]').textContent])", 40)
    out["caps_label"] = c.js("[...document.querySelectorAll('[data-testid=\"fleet-caps-card\"] .fcap-facts dt')].map((d) => d.textContent)"
                             ".filter((t) => t === 'packs')")
    out["caps_chips"] = c.js("[...document.querySelectorAll('[data-testid=\"fleet-caps-chip\"]')].map((x) => x.textContent)")
    return out


def mission(c, url, ctx) -> dict:
    from tests.helpers.studio_fleet_panels import open_strip, seen
    out: dict = {}
    mid = ctx["mission"]
    open_strip(c, "fleet-mission")
    btn = _q(f'[data-testid="fleet-mission-row"][data-id="{mid}"] [data-testid="fleet-mission-open"]')
    c.wait(f"!!{btn}", 30)
    seen(c, btn)
    c.click_on(btn)
    out["need_chip"] = c.wait(f"{_q('[data-testid=fleet-mission-pack-need]')}?.textContent", 30)
    out["need_pack"] = c.js(f"{_q('[data-testid=fleet-mission-pack-need]')}?.dataset.pack")
    out["metadata"] = c.wait(f"{_q('[data-testid=fleet-mission-metadata]')}?.textContent", 15)
    out["inspector_before"] = c.js(f"!!{_q('[data-testid=fleet-pack-inspector]')}")
    row = _q('[data-testid="fleet-mission-part-row"][data-part="1"] .fmi-ptitle')
    seen(c, row)
    c.click_on(row)
    line = _q('[data-testid="fleet-pack-inspector-line"][data-pack="doc-review"]')
    out["inspector_label"] = c.wait(f"{line}?.dataset.label", 20)
    out["inspector_text"] = c.wait(f"{line}?.querySelector('.fpk-md')?.textContent", 20)
    return out


class PacksFleetDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_studio import seeded_home, serve
        from halo_harness.fleet import mission_api as A
        from halo_harness.packs import bio_models
        from halo_harness.packs.discover import find
        from halo_harness.packs.grants import enable
        from halo_harness.packs.install import install
        from halo_harness.studio.server import url_for
        from tests.helpers.mission_seed import FakeLead
        state = seeded_home()
        bio_models.ROWS = lambda _s, _c: [dict(TOOLS_ROW)]
        for name, grants in (("doc-review", ["bash"]), ("fleet-needs-gpu", [])):
            ok, lines = install(str(REPO / "tests" / "fixtures" / "packs" / name))
            assert ok, lines
            ok, lines = enable(find(name), grant=grants)
            assert ok, lines
        A.LEAD = FakeLead(json.dumps({"parts": [{"id": "1", "title": "Review the docs", "brief": "Review docs/ for dead links.",
                                                 "kind": "files", "needs": ["docs.review"], "outputs": ["review.md"],
                                                 "est_cost_usd": 0.1}], "merge_order": []}))
        status, body = A.create(A.Ctx(state, None, by="you"), {"goal": "Review the docs", "repo": False, "lineup": "doc-review--review"})
        assert status == 200, body
        srv, _url = serve(state, True)
        url = url_for(srv, "fleet").replace("#t=", "&tour=off&view=workspace#t=")
        ctx = {"state": state, "srv": srv, "mission": body["mission"]["id"],
               "harness": (body["plan"]["parts"][0] or {}).get("harness_name")}
        self.out["planned_on"] = ctx["harness"]
        try:
            yield tuple((fn, (c, url, ctx)) for fn in (capabilities, mission))
        finally:
            A.LEAD = None
            bio_models.ROWS = None
            srv.shutdown()
            srv.server_close()
            shutil.rmtree(state.parent, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(PacksFleetDriver(sys.argv[1:]).main())
