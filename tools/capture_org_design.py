"""tools/capture_org_design.py -- the Org and Design captures for
tools/capture_studio.py --mode org|design (Halo 3.0.7.0 round R3: both are
React sections of the shell now, no framed classic page).

    docs/media/studio-org.png     the halo-dev-cycle lineup synced into "Halo Harness" on a fake
                                  Paperclip (tests/helpers/fake_paperclip.py): Company, the work
                                  lists, the org chart in its group boxes, the Inspector on the lead
    docs/media/studio-design.png  the seeded "Launch page" project (tools/design_demo.py): Projects,
                                  Assets, the Artboards canvas with its pins, the Thread of its turns

With --dom each section is read twice, its Start view first (Org: Paperclip
unreachable, so no company; Design: no project yet), then over the seeded
data, and the data-testid values are counted (the last stdout line is the
JSON: {"start": {...}, "<mode>": {...}}). Never two Chromes at once.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

IDS = ("section-tab", "legacy-frame", "panel-about", "org-start", "org-canvas", "org-card", "org-group", "org-edge", "org-issue", "org-goal",
       "org-project", "org-company", "org-install", "org-link", "design-start", "design-thread", "design-turn", "design-artboard", "design-pin",
       "design-project", "design-assets", "design-asset", "design-send-box")


def counts(dom: str) -> dict:
    out = {k: dom.count(f'data-testid="{k}"') for k in IDS}
    out["iframes"] = dom.count("<iframe")
    out["title"] = dom.split("<title>")[1].split("</title>")[0] if "<title>" in dom else ""
    return out


def seed_paperclip(state: Path):
    """A fake Paperclip with the halo-dev-cycle lineup synced in, a few states, issues, goals and projects."""
    from halo_harness.paperclip.client import Paperclip, save_config
    from halo_harness.paperclip.sync import sync_lineup
    from halo_harness.theme import set_config_value
    from tests.helpers.fake_paperclip import FakePaperclip
    fake = FakePaperclip(company_name="Halo Harness")
    fake.company.update(budgetMonthlyCents=20000, spentMonthlyCents=4210)
    set_config_value("paperclip.enabled", True)  # Org mode is off by default; the picture shows it on
    save_config({"base_url": fake.base_url, "company_id": fake.company["id"]}, state)
    sync_lineup(Paperclip(fake.base_url), fake.company["id"], "halo-dev-cycle", cwd=state.parent / "project", state_dir=state, out=open(os.devnull, "w"))
    agents = list(fake.agents.values())
    for i, a in enumerate(agents):
        a.update(spentMonthlyCents=[1840, 960, 410, 380, 220, 300, 100][i % 7], budgetMonthlyCents=5000 if i == 0 else 2500)
    states = {1: "running", 2: "running", 4: "paused"}
    for i, st in states.items():
        if i < len(agents):
            agents[i]["status"] = st
    lead = agents[0]["id"] if agents else ""
    for title, who, st in (("Ship the basket discount", 1, "in_progress"), ("Review the checkout diff", 3, "todo"),
                           ("Research shipping APIs", 2, "in_progress"), ("Fix the flaky cart test", 1, "blocked"), ("Write the release notes", 0, "done")):
        fake.add_issue(title, agents[who]["id"] if who < len(agents) else "", st)
    fake.add_goal("Launch the shop by November")
    fake.add_goal("Keep the test suite green", status="achieved")
    fake.add_project("Shop", "in_progress")
    fake.add_project("Docs site", "planned")
    return fake, lead


def capture(mode: str, out: str, dom: bool, chrome, serve, state: Path) -> int:
    from halo_harness.paperclip.client import save_config
    srv, url = serve(state, True)
    url = url.replace("mode=orchestra", f"mode={mode}").replace("feed=off", "feed=off&tour=off")
    fake = None
    try:
        result: dict = {}
        if dom:  # the Start view first: no company (Paperclip unreachable) / no project yet
            if mode == "org":
                save_config({"base_url": "http://127.0.0.1:1"}, state)
            r = chrome(["--dump-dom", "--window-size=1500,900", url])
            if r is None:
                print("no Chrome found")
                return 2
            result["start"] = counts(r.stdout)
        if mode == "org":
            fake, lead = seed_paperclip(state)
        else:
            from design_demo import seed
            seed(state)
            lead = ""
        if dom:
            r = chrome(["--dump-dom", "--window-size=1500,900", url])
            result[mode] = counts(r.stdout) if r else {}
            print(json.dumps(result))
            return 0
        return shoot(mode, out, url, lead)
    finally:
        srv.shutdown()
        srv.server_close()
        if fake is not None:
            fake.close()


def shoot(mode: str, out: str, url: str, lead: str) -> int:
    """The picture through the DevTools protocol: Org selects the lead (the Inspector shows it)."""
    import time
    from tests.helpers.chrome_driver import open_chrome
    c = open_chrome()  # the driver base: HALO_CHROME first, one headless Chrome at a time
    if c is None:
        print("no Chrome found: nothing rendered")
        return 2
    try:
        c.go(url)
        if mode == "org":
            c.wait("document.querySelectorAll('[data-testid=\"org-card\"]').length >= 7", 30)
            c.js("document.querySelector('[data-testid=\"org-canvas\"] .oc-scroll').focus()")
            if lead:
                c.click_on(f"document.querySelector('[data-testid=\"org-card\"][data-id=\"{lead}\"]')")
            c.wait("!!document.querySelector('[data-testid=\"org-inspector-agent\"]')", 10)
        else:
            c.wait("document.querySelectorAll('[data-testid=\"design-artboard\"]').length >= 2 && document.querySelectorAll('[data-testid=\"design-turn\"]').length >= 2", 30)
        time.sleep(2.5)  # the frames and the images paint
        path = Path(out).resolve()
        size = c.shot(path)
        ok = path.is_file() and size > 10_000
        print(f"{'wrote' if ok else 'FAILED'} {path} ({size} bytes)")
        return 0 if ok else 1
    finally:
        c.close()
