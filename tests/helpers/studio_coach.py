"""tests.helpers.studio_coach -- the post-run coach in Studio (Halo 3.0.9.0
round R3) in headless Chrome over the DevTools protocol (tests/helpers/cdp.py),
over tests/helpers/studio_coach_rig.py (the finished R2 run with three
findings seeded, the bios, the catalog, an ended mission; no model call).
tests/test_studio_ui.py runs it as a subprocess with a scrubbed environment
(tests/helpers/studio_ui_coach.py):

    python -m tests.helpers.studio_coach

* the Report panel's Coach tab shows three cards (model, tools, structure),
  each with its why lines, Ask the model, Apply and Edit, and the help line;
* Edit on the model card opens Roles on bio coach-cheap's form with
  or:vendor/strong picked, the coach's note on top and the field marked;
  nothing is saved (the bio on disk keeps its model);
* Dismiss hides the tools card; after a reload it stays hidden;
* Edit on the structure card opens the plan editor with job-5 after job-4
  staged (no Approve on a run that already ran); Back returns to the console;
* 3.1.3.0 R1: Apply on the model card shows the confirm card (the bio's file,
  the diff), Apply there writes the bio (APPLIED), Undo puts it back
  (UNDONE); Ask the model shows the lead's paragraph (HALO_COACH_FAKE=1);
* the Mission panel's Coach face lists the ended mission's cards;
* 3.1.6.0 R2: Probe in the Coach tab's header shows the cost line, Run the
  probe runs it (the fakes, in this process), and the probe's card leads the
  tab with its contrast table;
* 3.1.6.0 R3: an entry an earlier run made is cited (the library line, the
  `lib` chip, the "Library (1)" fold); Forget asks, then deletes it.

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
    out["edits"] = c.js(f"{N.format('coach-edit')}")
    out["asks"] = c.js(f"{N.format('coach-ask')}")
    out["help"] = c.js(f"{TID.format('coach-help')}?.textContent || ''")
    out["model_why"] = c.js(f"{CARD.format('model')}.querySelector('[data-testid=\"coach-why\"]').innerText")


def apply_model(c, rig, out: dict) -> None:
    click(c, f"{CARD.format('model')}.querySelector('[data-testid=\"coach-edit\"]')")
    out["bio_form"] = c.wait("document.querySelector('[data-testid=\"bio-form\"]')?.dataset.bio === 'coach-cheap' && 'coach-cheap'", 20)
    out["note_value"] = c.wait(f"{TID.format('bio-coach-value')}?.textContent", 10)
    out["note_field"] = c.js(f"{TID.format('bio-coach-note')}.dataset.field")
    # 3.1.4.0 R4: the bio form's model select holds the filled-in model (the picker table is folded under "more...")
    out["picked"] = c.wait("document.querySelector('[data-testid=\"bio-form\"] [data-testid=\"bio-model\"]')?.dataset.value === 'or:vendor/strong' && 'or:vendor/strong'", 10)
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
    click(c, f"{CARD.format('structure')}.querySelector('[data-testid=\"coach-edit\"]')")
    out["staged"] = c.wait(f"!!{TID.format('plan-staged')} && {TID.format('plan-staged')}.textContent", 20)
    out["staged_edge"] = c.wait("!!document.querySelector('[data-testid=\"plan-edge\"][data-from=\"job-4\"][data-to=\"job-5\"]') && 'job-4>job-5'", 10)
    out["staged_buttons"] = {k: c.js(N.format(k)) for k in ("plan-approve", "plan-reject", "plan-copy", "plan-back")}
    click(c, TID.format("plan-back"))
    out["console_back"] = c.wait(f"{N.format('orchestra-root')} === 1 && {N.format('orchestra-plan')} === 0 && 'back'", 10)
    out["draft_written"] = (rig.run_dir / "plan.draft.json").exists() or (rig.run_dir / "plan.json").exists()


def _bio_model(rig) -> str:
    from halo_harness.agents_yaml import load_agent_bio_raw
    return str((load_agent_bio_raw("coach-cheap", state_dir=rig.studio.state) or {}).get("models", {}).get("preference"))


def apply_and_undo(c, rig, url: str, out: dict) -> None:
    """3.1.3.0 R1: Apply -> the confirm card -> Apply writes the bio -> APPLIED -> Undo -> UNDONE, the bio as before."""
    open_coach(c, url)
    model = CARD.format("model")
    click(c, f"{model}.querySelector('[data-testid=\"coach-apply\"]')")
    out["confirm_file"] = c.wait(f"{model}.querySelector('[data-testid=\"coach-confirm\"]')?.dataset.file || ''", 20)
    out["confirm_diff"] = c.js(f"{model}.querySelector('[data-testid=\"coach-diff\"]').innerText")
    out["before_confirm"] = _bio_model(rig)
    click(c, f"{model}.querySelector('[data-testid=\"coach-confirm-apply\"]')")
    out["applied_chip"] = c.wait(f"{model}?.dataset.applied === 'applied' && "
                                 f"{model}.querySelector('[data-testid=\"coach-applied\"]').textContent", 20)
    out["after_apply"] = _bio_model(rig)
    out["summary"] = c.js(f"{TID.format('coach-summary')}.textContent")
    click(c, f"{model}.querySelector('[data-testid=\"coach-undo\"]')")
    out["undone_chip"] = c.wait(f"{model}?.dataset.applied === 'undone' && "
                                f"{model}.querySelector('[data-testid=\"coach-applied\"]').textContent", 20)
    out["after_undo"] = _bio_model(rig)


def ask_model(c, rig, url: str, out: dict) -> None:
    """3.1.3.0 R1: Ask the model on the model card: the lead's paragraph (the fake lead, no model)."""
    model = CARD.format("model")
    click(c, f"{model}.querySelector('[data-testid=\"coach-ask\"]')")
    out["paragraph"] = c.wait(f"{model}.querySelector('[data-testid=\"coach-paragraph\"] p')?.textContent || ''", 20)
    out["ask_kept"] = (rig.run_dir / "coach.ask.json").is_file()


def probe_card(c, rig, url: str, out: dict) -> None:
    """3.1.6.0 R2: Probe in the header row -> the cost line and the confirm (nothing run) -> Run the probe (the fake
    lead, workers and judge in this process) -> the probe's card first, with its contrast table."""
    from halo_harness.orchestra import probe_runs
    from tests.helpers.coach_probe_rig import fake_adapters
    probe_runs.ADAPTERS = fake_adapters([])
    open_coach(c, url)
    out["probe_button"] = c.js("!!document.querySelector('.cc-head [data-testid=\"coach-probe\"]')")
    click(c, TID.format("coach-probe"))
    out["probe_cost"] = c.wait(f"{TID.format('coach-probe-cost')}?.textContent || ''", 20)
    out["probe_ran_before"] = (rig.run_dir / "probe.json").exists()
    click(c, TID.format("coach-probe-run"))
    card = CARD.format("probe")
    out["probe_rows"] = c.wait(f"!!{card} && {card}.querySelectorAll('[data-testid=\"coach-contrast-row\"]').length", 90)
    out["probe_first"] = c.js("document.querySelector('[data-testid=\"coach-card\"]')?.dataset.kind")
    out["probe_reference"] = c.js(f"{card}.querySelector('[data-testid=\"coach-contrast-row\"]').dataset.id")
    out["probe_judge"] = c.js(f"{card}.querySelector('[data-testid=\"coach-paragraph\"] .glance-kicker')?.textContent")
    out["probe_listed"] = len(rig.studio.get("orchestra/runs")[1])


def library_fold(c, rig, url: str, out: dict) -> None:
    """3.1.6.0 R3: an entry an earlier run of this repo made is cited: the library line, the `lib` chip on the model
    card, the "Library (1)" fold; Forget asks first, then deletes the entry's folder and the fold goes."""
    from halo_harness.orchestra import coach_library as L
    eid = rig.seed_entry()
    open_coach(c, url)
    out["lib_line"] = c.wait(f"{TID.format('coach-library-line')}?.textContent || ''", 20)
    out["lib_chip"] = c.js(f"{CARD.format('model')}?.querySelector('[data-testid=\"coach-lib\"]')?.dataset.entries || ''")
    out["lib_summary"] = c.js(f"{TID.format('coach-library-summary')}?.textContent.trim()")
    click(c, TID.format("coach-library-summary"))
    out["lib_rows"] = c.wait(f"{N.format('coach-library-row')} > 0 && {N.format('coach-library-row')}", 10)
    out["lib_row_entry"] = c.js(f"{TID.format('coach-library-row')}.dataset.entry")
    click(c, TID.format("coach-library-forget"))
    out["lib_confirm"] = bool(c.wait(f"!!{TID.format('coach-library-confirm')}", 10))
    out["lib_kept_before"] = L.read(eid, rig.studio.state) is not None
    click(c, TID.format("coach-library-forget-yes"))
    out["lib_gone"] = c.wait(f"{N.format('coach-library-block')} === 0 && 'gone'", 20)
    out["lib_deleted"] = not L.entry_dir(eid, rig.studio.state).exists()
    out["lib_api"] = rig.coach().get("library")


def mission_coach(c, rig, out: dict) -> None:
    from tests.helpers.studio_fleet_panels import open_strip
    c.go(rig.url("fleet").replace("#t=", "&view=workspace#t="))
    open_strip(c, "fleet-mission")  # 3.1.4.0 R1: Mission starts as a strip on the right edge
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
                   (apply_plan, (c, rig, url, self.out)), (apply_and_undo, (c, rig, url, self.out)),
                   (ask_model, (c, rig, url, self.out)), (mission_coach, (c, rig, self.out)),
                   (probe_card, (c, rig, url, self.out)), (library_fold, (c, rig, url, self.out)))


def main() -> int:
    return CoachDriver().main()


if __name__ == "__main__":
    sys.exit(main())
