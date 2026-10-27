"""tests.helpers.studio_model_select -- the model select outside Roles for
tests/test_studio_model_select.py (Halo 3.1.4.0 R4), real clicks in headless
Chrome through the driver base:

    python -m tests.helpers.studio_model_select forms   Orchestra's goal form and Design
    python -m tests.helpers.studio_model_select team    the Team stage face

`forms`: a fresh home with the shipped lineups, a catalog of two fake models
(OpenRouter's cache shape), the role table's `main` on one of them and the
default model on the other. Orchestra's Start view shows the select without
opening the "who plays the parts" disclosure, its first option "the
lineup's (<the lead's model>)"; Design's Projects panel shows the open
project's model and changing it saves the project (`GET design/projects`);
New project's dialog creates a project on the picked model.
`team`: tests/helpers/studio_team_rig.py's team (no run): the `draft` stage
says what it runs on (its lead member's card in the `standard` lineup) and
its link opens that card in Roles with the MODEL strip's select focused.
The last stdout line is the JSON of what it saw (exit 2: no Chrome)."""
from __future__ import annotations

import json
import shutil
import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.chrome_driver import Driver  # noqa: E402
from tests.helpers.studio_roles_model import FAKE, STRIP, TOKEN, pick  # noqa: E402

ALPHA, BETA = "or:fakeco/alpha-1", "or:fakeco/beta-2"
OM = "document.querySelector('[data-testid=\"orchestra-model\"]')"
PM = "document.querySelector('[data-testid=\"design-project-model\"]')"
NM = "document.querySelector('[data-testid=\"design-new-model\"]')"


def seed_catalog(state: Path) -> None:
    from halo_harness.theme import set_config_value
    rows = {k: {"context_length": c, "pricing": {"prompt": f"{i / 1e6:.10f}", "completion": f"{o / 1e6:.10f}"}} for k, (i, o, c) in FAKE.items()}
    (state / "models.json").write_text(json.dumps(rows), encoding="utf-8")
    set_config_value("providers.openrouter.enabled", True)


def projects(c) -> str:
    return f"(async () => (await (await fetch('/api/design/projects', {TOKEN})).json()).projects)()"


def forms(c, url: str, state: Path) -> dict:
    out: dict = {}
    c.go(url.replace("mode=roles", "mode=orchestra"))
    out["orch_first"] = c.wait(f"{OM}?.querySelector('option')?.textContent.includes('beta-2') && {OM}.querySelector('option').textContent", 20)
    out["orch_outside_disclosure"] = c.js(f"!{OM}.closest('details') && !document.querySelector('details.og-more').open")
    out["orch_options"] = c.wait(f"(() => {{ const v = [...{OM}.querySelectorAll('optgroup option')].map((o) => o.value).filter((v) => v.startsWith('or:fakeco')); return v.length === 2 && v; }})()", 15)
    pick(c, f"{OM}.querySelector('select')", ALPHA)
    out["orch_value"] = c.wait(f"{OM}.querySelector('select').value === {json.dumps(ALPHA)} && {OM}.dataset.value", 10)
    out["orch_summary"] = c.js("document.querySelector('details.og-more summary').textContent")
    c.go(url.replace("mode=roles", "mode=design"))
    out["design_value"] = c.wait(f"{PM} && ({PM}.dataset.value === '' ? 'default' : {PM}.dataset.value)", 25)
    # the first option names the inherited default once the catalog answer lands: on the Linux runner it still read
    # "(none resolves)" when read at once (a3a4d2e), so wait for the resolved name like `orch_first` does
    out["design_first"] = c.wait(f"{PM}.querySelector('option')?.textContent.includes('alpha-1') && {PM}.querySelector('option').textContent", 20)
    c.wait(f"!!{PM}.querySelector('option[value=\"{BETA}\"]')", 15)
    pick(c, f"{PM}.querySelector('select')", BETA)
    out["design_saved"] = c.wait(f"(async () => {{ const p = await {projects(c)}; return p.find((x) => x.slug === 'launch-page')?.model; }})()", 15)
    c.click_on("document.querySelector('[data-testid=\"design-new\"]')")
    c.wait(f"!!{NM}", 10)
    out["new_first"] = c.js(f"{NM}.querySelector('option').textContent")
    c.wait(f"!!{NM}.querySelector('option[value=\"{ALPHA}\"]')", 15)
    pick(c, f"{NM}.querySelector('select')", ALPHA)
    c.click_on("document.querySelector('[data-testid=\"design-new-name\"]')")
    c.type_text("Second page")
    c.click_on("document.querySelector('[data-testid=\"design-new-go\"]')")
    out["new_saved"] = c.wait(f"(async () => {{ const p = await {projects(c)}; return p.find((x) => x.name === 'Second page')?.model; }})()", 15)
    return out


def team(c, rig) -> dict:
    out: dict = {}
    face = "document.querySelector('[data-testid=\"team-stage-model\"]')"
    c.go(rig.url("team"))
    c.wait("document.querySelectorAll('[data-testid=\"team-stage\"]').length >= 3", 30)
    shape = "document.querySelector('[data-testid=\"team-stage\"][data-stage=\"draft\"] .tm-stage-shape')"
    c.js(f"{shape}.scrollIntoView({{block: 'center', inline: 'center'}}); 1")
    time.sleep(0.2)
    c.click_on(shape)
    out["source"] = c.wait(f"{face}?.dataset.source", 15)
    out["ref"] = c.js(f"{face}.dataset.ref")
    out["text"] = c.js(f"{face}.textContent")
    status, want = rig.api("GET", "models/resolve?role=main&lineup=standard")
    out["want"] = want if status == 200 else {"status": status}
    c.click_on(f"{face}.querySelector('[data-testid=\"team-stage-model-link\"]')")
    out["roles_card"] = c.wait(f"document.activeElement === {STRIP}?.querySelector('[data-testid=\"model-select\"]') && {STRIP}.dataset.card", 20)
    out["roles_lineup"] = c.js("document.querySelector('[data-testid=\"roles-canvas\"]')?.dataset.lineup")
    return out


class FormsDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_studio import seeded_home, serve
        from halo_harness.design.store import Project
        from halo_harness.theme import set_config_value
        state = seeded_home()
        seed_catalog(state)
        set_config_value("roles.main", BETA)
        set_config_value("model", ALPHA)
        Project.create("Launch page", state_dir=state)
        srv, url = serve(state, True)
        from tests.helpers.studio_full import full
        url = full(url)  # 3.3.2.0 R3: every panel open, the arrangement this driver works in
        try:
            yield ((forms, (c, url.replace("mode=orchestra", "mode=roles").replace("feed=off", "feed=off&tour=off"), state)),)
        finally:
            srv.shutdown()
            srv.server_close()
            shutil.rmtree(state.parent, ignore_errors=True)


class TeamDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from tests.helpers.studio_team_rig import StudioTeamRig
        with StudioTeamRig(live=False) as rig:
            yield ((team, (c, rig)),)


if __name__ == "__main__":
    kind = sys.argv[1:2]
    if kind not in (["forms"], ["team"]):
        print("usage: python -m tests.helpers.studio_model_select forms|team", file=sys.stderr)
        sys.exit(2)
    sys.exit((FormsDriver if kind == ["forms"] else TeamDriver)(sys.argv[2:]).main())
