"""tests.helpers.studio_workflow -- the typed-artifact viewer checks of
tests/test_workflow_ui.py (Halo 3.2.0.0 R5), real keys and clicks in headless
Chrome through the driver base, over a scratch home with the doc-review
reference pack (enabled, bash granted; a catalog model that calls tools) and a
project repo where the review workflow already ran to its report (the fake
lead and stage workers of tests/helpers/workflow_rig.py; no model call):

1. the pack's Docs review section (Alt+9): its "Last review report" panel
   draws the newest run's review-report by its schema's view (table): the
   summary above, one row per finding, the run named in its meta line;
2. Session's Reviews panel: a review.done shows its data under the line (the
   kind's schema says keyvalue), an off-schema one shows its problems;
3. Orchestra's run view: the Report panel has an "Artifacts (1)" tab; it
   lists the report artifact (schema, view, saved) and draws the same table.

The last stdout line is the JSON of what it saw (exit 2: no Chrome)."""
from __future__ import annotations

import json
import shutil
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.chrome_driver import Driver  # noqa: E402
from tests.helpers.studio_packs_steps import CUR, alt, pa, panel, press, q, qa  # noqa: E402


def pack_section(c, url, ctx) -> dict:
    out: dict = {}
    c.go(url)
    c.wait("[...document.querySelectorAll('[data-testid=section-tab]')].some((t) => t.textContent.startsWith('Docs review'))", 40)
    alt(c, 9)  # 3.2.0.0 R6: Alt+7 is Packs; 3.3.0.0 R1: Alt+8 is Setup
    out["section"] = c.wait(f"{CUR}.startsWith('Docs review') && {CUR}", 10)
    art = panel("doc-review--report", "[data-testid=pack-artifact]")
    out["view"] = c.wait(f"{art}?.dataset.view", 20)
    out["run"] = c.js(f"{art}.dataset.run")
    out["meta"] = c.js(f"{panel('doc-review--report', '[data-testid=artifact-meta]')}.textContent")
    out["rows"] = c.wait(pa("doc-review--report", "[data-testid=artifact-row]") + ".length", 15)
    out["head"] = c.js(pa("doc-review--report", "[data-testid=artifact-table] th") + ".map((t) => t.textContent)")
    out["cells"] = c.js(pa("doc-review--report", "[data-testid=artifact-row] td") + ".map((t) => t.textContent)")
    out["summary"] = c.js(f"{panel('doc-review--report', '[data-testid=artifact-kv] [data-key=summary] dd')}?.textContent")
    return out


def event_data(c, url, ctx) -> dict:
    """Session's Reviews panel: a review.done's data under its line (the kind's schema says keyvalue) and an off-schema
    one's problems under it."""
    from halo_harness.ext import publish_event
    from halo_harness.studio.events import bridge_for
    out: dict = {}
    alt(c, 1)
    c.wait(f"{CUR}.startsWith('Session') && !!{panel('doc-review--reviews')}", 20)
    publish_event("doc-review", "review.done", {"file": "docs/guide.md", "findings": 1}, bridge=bridge_for(ctx["srv"]))
    publish_event("doc-review", "review.done", {"file": "docs/intro.md"}, bridge=bridge_for(ctx["srv"]))
    press(c, panel("doc-review--reviews", "button[aria-label=Open]"))
    ev = qa("[data-panel='doc-review--reviews'] [data-testid=pack-event]")
    c.wait(f"{ev}.length >= 2", 15)
    out["event_kv"] = c.js(f"[...{ev}[0].querySelectorAll('[data-testid=pack-event-data] .pk-art-kv-row')].map((r) => r.dataset.key + '=' + r.querySelector('dd').textContent)")
    out["event_problems"] = c.js(f"[...{ev}[1].querySelectorAll('[data-testid=artifact-problems] li')].map((li) => li.textContent)")
    out["event_line"] = c.js(f"{ev}[1].querySelector('.fac-text').textContent")
    return out


def run_view(c, url, ctx) -> dict:
    out: dict = {}
    c.go("about:blank")
    c.go(url)
    tab = q("[data-testid=report-tab-artifacts]")
    out["tab"] = c.wait(f"{tab}?.textContent", 40)
    press(c, "document.querySelector('[data-testid=report-tab-artifacts]')")
    one = q("[data-testid=run-artifact]")
    out["artifact"] = c.wait(f"{one} && [{one}.dataset.name, {one}.dataset.state, {one}.dataset.ok]", 20)
    out["artifact_head"] = c.js(f"{one}.querySelector('.og-artifact-head').textContent")
    out["artifact_rows"] = c.wait(qa("[data-testid=run-artifact] [data-testid=artifact-row]") + ".length", 15)
    out["artifact_cells"] = c.js(qa("[data-testid=run-artifact] [data-testid=artifact-row] td") + ".map((t) => t.textContent)")
    return out


def _ran(state: Path) -> "tuple[Path, str]":
    """A project repo where the doc-review workflow ran to its report; its run id."""
    from halo_harness.orchestra import plan as P
    from halo_harness.orchestra.goal import new_run
    from halo_harness.orchestra.run import run
    from halo_harness.workflows.compile import compile_workflow
    from halo_harness.workflows.spec import find
    from tests.helpers.workflow_rig import FakeLead, StageWorker, fake_judge, git
    proj = state.parent / "project"
    for rel, text in (("docs/guide.md", "# Guide\n\nRead [this](missing.md).\n"), ("docs/intro.md", "# Intro\n\nHello.\n")):
        p = proj / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
    git(proj, "init", "-q")
    for key, value in (("user.name", "t"), ("user.email", "t@t"), ("core.autocrlf", "false"), ("commit.gpgsign", "false")):
        git(proj, "config", key, value)
    git(proj, "add", "-A")
    git(proj, "commit", "-q", "-m", "docs to review")
    wf, why = find("doc-review/review", cwd=proj)
    assert wf is not None, why
    compiled = compile_workflow(wf, {"docs": "docs"}, repo=proj, cwd=proj)
    assert not compiled.problems, compiled.problems
    run_dir = new_run(proj, compiled.goal)
    stop = threading.Event()

    def approver():
        while not stop.is_set():
            if P.is_planned(run_dir):
                P.approve(run_dir, P.current_jobs(run_dir), by="test")
                return
            time.sleep(0.05)
    threading.Thread(target=approver, daemon=True).start()
    try:
        report = run(run_dir, model_calls=FakeLead(), spawn=StageWorker(), judge=fake_judge, plan_poll_s=0.05)
    finally:
        stop.set()
    assert report["status"] == "finished", report.get("stop_reason")
    return proj, run_dir.name


class WorkflowUiDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_studio import seeded_home, serve
        from halo_harness.packs import bio_models
        from halo_harness.packs.discover import find
        from halo_harness.packs.grants import enable
        from halo_harness.packs.install import install
        from halo_harness.studio.server import url_for
        from tests.helpers.workflow_rig import TOOLS_ROW
        state = seeded_home()
        bio_models.ROWS = lambda _s, _c: [dict(TOOLS_ROW)]
        from tests.helpers.packs_home import DOC_REVIEW  # 3.2.0.0 R6: the shipped reference pack
        ok, lines = install(str(DOC_REVIEW))
        assert ok, lines
        ok, lines = enable(find("doc-review"), grant=["bash"])
        assert ok, lines
        proj, run_id = _ran(state)
        self.out["run_id"] = run_id
        srv, _url = serve(state, True, proj=proj)
        roles = url_for(srv, "roles").replace("#t=", "&tour=off&view=workspace&open=all#t=")  # 3.3.2.0 R3: every panel open
        orch = url_for(srv, "orchestra").replace("#t=", "&tour=off&view=workspace&open=all#t=")
        try:
            yield ((pack_section, (c, roles, {})), (event_data, (c, roles, {"srv": srv})), (run_view, (c, orch, {})))
        finally:
            bio_models.ROWS = None
            srv.shutdown()
            srv.server_close()
            shutil.rmtree(state.parent, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(WorkflowUiDriver(sys.argv[1:]).main())
