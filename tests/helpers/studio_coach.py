"""tests.helpers.studio_coach -- the post-run coach in Studio (Halo 3.0.9.0
round R3) in headless Chrome over the DevTools protocol (tests/helpers/cdp.py),
over tests/helpers/studio_coach_rig.py (the finished R2 run with three
findings seeded, the bios, the catalog, an ended mission; no model call).
tests/test_studio_ui.py runs it as a subprocess with a scrubbed environment
(tests/helpers/studio_ui_coach.py):

    python -m tests.helpers.studio_coach

* the Report panel's Coach tab shows three cards (model, tools, structure),
  each with its why lines;
* Apply on the model card opens Roles on bio coach-cheap's form with
  or:vendor/strong picked, the coach's note on top and the field marked;
  nothing is saved (the bio on disk keeps its model);
* Dismiss hides the tools card; after a reload it stays hidden;
* Apply on the structure card opens the plan editor with job-5 after job-4
  staged (no Approve on a run that already ran); Back returns to the console;
* the Mission panel's Coach face lists the ended mission's cards.

The last stdout line is a JSON object of what it saw (exit 2: no Chrome)."""
from __future__ import annotations

import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.chrome_driver import Driver  # noqa: E402

TID = "document.querySelector('[data-testid=\"{}\"]')"
N = "document.querySelectorAll('[data-testid=\"{}\"]').length"
CARD = "document.querySelector('[data-testid=\"coach-card\"][data-kind=\"{}\"]')"
KINDS = "[...document.querySelectorAll('[data-testid=\"coach-card\"]')].map((e) => e.dataset.kind).sort()"


def click(c, expr: str) -> None:
    c.js(f"({expr}).scrollIntoView({{block: 'center', inline: 'center'}}); 1")
    time.sleep(0.15)
    c.click_on(expr)


def open_coach(c, url: str) -> None:
    c.go("about:blank")  # the same URL again is a fragment hop, not a reload
    c.go(url)
    c.wait(f"!!{TID.format('report-tab-coach')}", 30)
    click(c, TID.format("report-tab-coach"))
    c.wait(f"!!{TID.format('coach')} && {N.format('coach-card')} > 0", 20)


def three_cards(c, url: str, out: dict) -> None:
    open_coach(c, url)
    out["cards"] = c.wait(f"{N.format('coach-card')} === 3 && {N.format('coach-card')}", 10)
    out["kinds"] = c.js(KINDS)
    out["why"] = c.js(f"{N.format('coach-why')}")
    out["applies"] = c.js(f"{N.format('coach-apply')}")
    out["model_why"] = c.js(f"{CARD.format('model')}.querySelector('[data-testid=\"coach-why\"]').innerText")


def apply_model(c, rig, out: dict) -> None:
    click(c, f"{CARD.format('model')}.querySelector('[data-testid=\"coach-apply\"]')")
    out["bio_form"] = c.wait("document.querySelector('[data-testid=\"bio-form\"]')?.dataset.bio === 'coach-cheap' && 'coach-cheap'", 20)
    out["note_value"] = c.wait(f"{TID.format('bio-coach-value')}?.textContent", 10)
    out["note_field"] = c.js(f"{TID.format('bio-coach-note')}.dataset.field")
    out["picked"] = c.wait("document.querySelector('[data-testid=\"bio-form\"] .rm-current b')?.textContent === 'or:vendor/strong' && 'or:vendor/strong'", 10)
    out["marked"] = c.js("[...document.querySelectorAll('[data-coach-changed]')].length")
    out["section"] = c.js("document.querySelector('[role=\"tab\"][aria-selected=\"true\"][data-tab-id]')?.dataset.tabId")
    from halo_harness.agents_yaml import load_agent_bio_raw
    out["saved_model"] = (load_agent_bio_raw("coach-cheap", state_dir=rig.studio.state) or {}).get("models", {}).get("preference")


def dismiss_survives(c, url: str, out: dict) -> None:
    open_coach(c, url)
    c.wait(f"{N.format('coach-card')} === 3", 10)
    click(c, f"{CARD.format('tools')}.querySelector('[data-testid=\"coach-dismiss\"]')")
    out["after_dismiss"] = c.wait(f"{N.format('coach-card')} === 2 && {KINDS}", 10)
    open_coach(c, url)
    time.sleep(0.5)
    out["after_reload"] = c.js(KINDS)
    out["stored"] = c.js("Object.keys(localStorage).filter((k) => k.startsWith('halo.coach.dismissed.orchestra.')).map((k) => localStorage.getItem(k))")
    out["show_dismissed"] = c.js(f"{TID.format('coach-show-dismissed')}?.textContent")


def apply_plan(c, rig, url: str, out: dict) -> None:
    open_coach(c, url)
    click(c, f"{CARD.format('structure')}.querySelector('[data-testid=\"coach-apply\"]')")
    out["staged"] = c.wait(f"!!{TID.format('plan-staged')} && {TID.format('plan-staged')}.textContent", 20)
    out["staged_edge"] = c.wait("!!document.querySelector('[data-testid=\"plan-edge\"][data-from=\"job-4\"][data-to=\"job-5\"]') && 'job-4>job-5'", 10)
    out["staged_buttons"] = {k: c.js(N.format(k)) for k in ("plan-approve", "plan-reject", "plan-copy", "plan-back")}
    click(c, TID.format("plan-back"))
    out["console_back"] = c.wait(f"{N.format('orchestra-root')} === 1 && {N.format('orchestra-plan')} === 0 && 'back'", 10)
    out["draft_written"] = (rig.run_dir / "plan.draft.json").exists() or (rig.run_dir / "plan.json").exists()


def mission_coach(c, rig, out: dict) -> None:
    c.go(rig.url("fleet").replace("#t=", "&view=workspace#t="))
    row = f"document.querySelector('[data-testid=\"fleet-mission-row\"][data-id=\"{rig.mission}\"] [data-testid=\"fleet-mission-open\"]')"
    c.wait(f"!!{row}", 30)
    click(c, row)
    c.wait(f"!!{TID.format('fleet-mission-tab-coach')}", 20)
    click(c, TID.format("fleet-mission-tab-coach"))
    out["mission_face"] = c.wait("document.querySelector('[data-testid=\"fleet-mission-detail\"]')?.dataset.face === 'coach' && 'coach'", 10)
    out["mission_cards"] = c.wait(f"{N.format('coach-card')} > 0 && {N.format('coach-card')}", 20)
    out["mission_kinds"] = c.js(KINDS)


class CoachDriver(Driver):
    """The coach over tests/helpers/studio_coach_rig.py; the base scoped the home first (the coach reads the role
    table of this process's home)."""

    @contextmanager
    def session(self, c):
        from tests.helpers.studio_coach_rig import CoachRig
        with CoachRig() as rig:
            url = rig.url()
            yield ((three_cards, (c, url, self.out)), (apply_model, (c, rig, self.out)), (dismiss_survives, (c, url, self.out)),
                   (apply_plan, (c, rig, url, self.out)), (mission_coach, (c, rig, self.out)))


def main() -> int:
    return CoachDriver().main()


if __name__ == "__main__":
    sys.exit(main())
