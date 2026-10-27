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
   inspector line (fleet/checklist.md, read through the pack's file route);
3. (3.2.1.0 R1) the Mission form's Lineup select: the active lineup first, the
   pack's lineup picked and planned: the new mission's head says the lineup
   and carries the pack's metadata;
4. (3.2.1.0 R3) a mission part on a member `kali@lab` whose pack net-scan
   runs only there: its inspector line shows the text the member's catalog
   carries (the capabilities route lists the member from that step on).

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
from tests.helpers.studio_full import toggle_face  # noqa: E402

TOOLS_ROW = {"ref": "or:anthropic/claude-sonnet-4.6", "provider": "openrouter", "tools": True}
CAPS = "document.querySelector('[data-testid=\"fleet-capabilities\"]')"
MPANEL = "document.querySelector('[data-testid=\"fleet-mission\"]')"


def _q(sel: str) -> str:
    return f"document.querySelector({json.dumps(sel)})"


def capabilities(c, url, ctx) -> dict:
    from tests.helpers.studio_fleet_panels import open_strip, seen
    out: dict = {}
    c.go(url)
    c.wait(f"{CAPS}?.querySelector('.panel-title')?.title", 40)
    open_strip(c, "fleet-capabilities")
    toggle_face(c, '[data-testid="fleet-capabilities"]')  # 3.3.2.0 R3: Expand is a row of the ... menu
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
    out["mission_lineup"] = c.js(f"{_q('[data-testid=fleet-mission-lineup]')}?.textContent")
    return out


FORM_GOAL = "Review the docs from the form"


def _set(c, expr: str, proto: str, value: str) -> None:
    c.js(f"(() => {{ const el = {expr}; const set = Object.getOwnPropertyDescriptor({proto}.prototype, 'value').set; "
         f"set.call(el, {json.dumps(value)}); el.dispatchEvent(new Event({json.dumps('change' if proto == 'HTMLSelectElement' else 'input')}, "
         f"{{bubbles: true}})); return 1; }})()")


def mission_form(c, url, ctx) -> dict:
    """3.2.1.0 R1: the Mission form's Lineup select lists the lineups, the active one first; the pack's lineup
    picked there rides in the mission (its head says it, with the pack's metadata)."""
    from tests.helpers.studio_fleet_panels import seen
    out: dict = {}
    back = _q("[data-testid=fleet-mission-back]")
    if c.js(f"!!{back}"):
        seen(c, back)
        c.click_on(back)
    pick = _q("[data-testid=fleet-mission-lineup-pick]")
    c.wait(f"!!{pick} && {pick}.options.length > 1", 30)
    out["form_options"] = c.js(f"[...{pick}.options].map((o) => o.value)")
    out["form_first"] = c.js(f"{pick}.options[0].textContent")
    _set(c, pick, "HTMLSelectElement", "doc-review--review")
    _set(c, _q("[data-testid=fleet-mission-goal]"), "HTMLTextAreaElement", FORM_GOAL)
    btn = _q("[data-testid=fleet-mission-plan-it]")
    c.wait(f"!!{btn} && !{btn}.disabled", 10)
    seen(c, btn)
    c.click_on(btn)
    head = _q("[data-testid=fleet-mission] .fmi-head-main .fmi-goal")
    c.wait(f"{head}?.title === {json.dumps(FORM_GOAL)}", 40)
    out["form_lineup"] = c.wait(f"{_q('[data-testid=fleet-mission-lineup]')}?.textContent", 15)
    out["form_metadata"] = c.js(f"{_q('[data-testid=fleet-mission-metadata]')}?.textContent")
    return out


MEMBER_ID = "hid-kali-r3"


def member_entry() -> dict:
    """3.2.1.0 R3: a member `kali@lab` whose catalog carries pack net-scan with one inspector line and its text."""
    import time
    from tests.helpers.mission_seed import kali_box
    cap = {"name": "net.scan", "description": "Scans the lab subnet", "available": True, "why": "nmap 7.95 (CLI)",
           "checks": [], "requires": {}, "capacity": {}}
    cat = {**kali_box({"id": MEMBER_ID, "name": "kali@lab"}), "hash": "r3member", "packs": [
        {"id": "net-scan", "name": "Net scan", "version": "1.0.0", "capabilities": [cap], "metadata": {},
         "inspector": [{"label": "Scan rules", "source": "fleet/rules.md", "text": "# Scan rules\n\n- Only the lab subnet, never the office.\n"}]}]}
    now = time.time()
    return {"harness": MEMBER_ID, "name": "kali@lab", "local": False, "online": True, "hash": cat["hash"], "summary": "",
            "chips": [], "at": now, "received": now, "catalog": cat}


def member_inspector(c, url, ctx) -> dict:
    """3.2.1.0 R3: a part on a member whose pack runs only there: the inspector line shows the text the member's
    catalog carries (not "its Studio reads this file")."""
    from halo_harness.studio import fleet_feed
    from tests.helpers.studio_fleet_panels import open_strip, seen
    out: dict = {}
    ctx["member_on"]["on"] = True  # the member's catalog arrives: the hub's frame tells Studio to read the catalogs again
    fleet_feed.publish(ctx["srv"], {"event": "fleet", "harness": MEMBER_ID, "data": {
        "action": "capabilities", "harness": MEMBER_ID, "name": "kali@lab", "hash": "r3member"}})
    open_strip(c, "fleet-mission")
    back = _q("[data-testid=fleet-mission-back]")
    if c.wait(f"!!{back} || !!{_q('[data-testid=fleet-mission-row]')}", 30) and c.js(f"!!{back}"):
        seen(c, back)
        c.click_on(back)
    btn = _q(f'[data-testid="fleet-mission-row"][data-id="{ctx["member_mission"]}"] [data-testid="fleet-mission-open"]')
    c.wait(f"!!{btn}", 30)
    seen(c, btn)
    c.click_on(btn)
    row = _q('[data-testid="fleet-mission-part-row"][data-part="1"] .fmi-ptitle')
    c.wait(f"!!{row}", 30)
    seen(c, row)
    c.click_on(row)
    line = _q('[data-testid="fleet-pack-inspector-line"][data-pack="net-scan"]')
    out["member_local"] = c.wait(f"{line}?.dataset.local", 30)
    out["member_text"] = c.wait(f"{line}?.querySelector('.fpk-md')?.textContent", 20)
    out["member_head"] = c.js(f"{line}?.querySelector('.fpk-line-head')?.textContent")
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
            from tests.helpers.packs_home import fixture  # 3.2.0.0 R6: doc-review is the shipped pack
            ok, lines = install(str(fixture(name)))
            assert ok, lines
            ok, lines = enable(find(name), grant=grants)
            assert ok, lines
        A.LEAD = FakeLead(json.dumps({"parts": [{"id": "1", "title": "Review the docs", "brief": "Review docs/ for dead links.",
                                                 "kind": "files", "needs": ["docs.review"], "outputs": ["review.md"],
                                                 "est_cost_usd": 0.1}], "merge_order": []}))
        status, body = A.create(A.Ctx(state, None, by="you"), {"goal": "Review the docs", "repo": False, "lineup": "doc-review--review"})
        assert status == 200, body
        member, on = member_entry(), {"on": False}  # 3.2.1.0 R3: a member's pack, listed by the capabilities route at its step
        mctx = A.Ctx(state, None, by="you")
        real = mctx.dispatch.entries
        mctx.dispatch.entries = lambda view=None: real(view) + [member]
        lead, A.LEAD = A.LEAD, FakeLead(json.dumps({"parts": [{"id": "1", "title": "Scan the lab subnet", "kind": "files",
                                                               "brief": "Run nmap over the lab subnet.", "needs": ["net.scan"],
                                                               "outputs": ["scan.xml"], "est_cost_usd": 0.1}], "merge_order": []}))
        status, scan = A.create(mctx, {"goal": "Scan the lab subnet", "repo": False})
        A.LEAD = lead
        assert status == 200 and scan["plan"]["parts"][0]["harness"] == MEMBER_ID, scan
        from halo_harness.studio import fleet_capabilities_api as FC
        routes = FC._entries
        FC._entries = lambda req, refresh_member="": (lambda got: (got[0], got[1] + [member]) if got[0] == 200 and on["on"] else got)(
            routes(req, refresh_member))
        srv, _url = serve(state, True)
        url = url_for(srv, "fleet").replace("#t=", "&tour=off&view=workspace&open=all#t=")  # 3.3.2.0 R3: every panel open
        ctx = {"state": state, "srv": srv, "mission": body["mission"]["id"], "member_mission": scan["mission"]["id"], "member_on": on,
               "harness": (body["plan"]["parts"][0] or {}).get("harness_name")}
        self.out["planned_on"] = ctx["harness"]
        try:
            yield tuple((fn, (c, url, ctx)) for fn in (capabilities, mission, mission_form, member_inspector))
        finally:
            FC._entries = routes
            A.LEAD = None
            bio_models.ROWS = None
            srv.shutdown()
            srv.server_close()
            shutil.rmtree(state.parent, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(PacksFleetDriver(sys.argv[1:]).main())
