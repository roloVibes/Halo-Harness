"""tests.helpers.flow_studio_rig -- Halo 3.0.4.0 R5: a Studio server over a
temp state dir with a FakeComfy server beside it, plus the flow runs the
Flow routes read: a finished social-post run (`finished_run`, --yes) and a
run parked at its confirm gate on a background thread (`waiting_run`), both
made with the R3 fakes (tests/helpers/fake_flow.py). `factory(...)` is a
`flow_api.RUNNER` over the same fakes. The JSON client and the SSE reader
are orchestra_studio_rig's. No model, no real ComfyUI, no Postiz.
"""
from __future__ import annotations

import shutil
import tempfile
import threading
import time
from pathlib import Path

from tests.helpers.fake_comfy import FakeComfy
from tests.helpers.fake_flow import FakeOneShot, FakeOrg, make_adapters, template_spec, uniq
from tests.helpers.orchestra_studio_rig import Reader, Studio as _OrchestraStudio

__all__ = ["FlowStudio", "Reader", "factory"]


def factory(comfy_url: str, *, org_gate: bool = False, calls: "list | None" = None):
    """flow_api.RUNNER: the fakes, the Studio's state dir and --yes as Studio passes them."""

    def make(**kw):
        if calls is not None:
            calls.append(dict(kw))
        ad = make_adapters(comfy_url, one_shot=FakeOneShot(), run_org=FakeOrg(gate=org_gate),
                           auto_accept=kw.get("auto_accept", False), model=kw.get("model"), cwd=kw.get("cwd"))
        ad.state_dir = kw.get("state_dir")
        return ad
    return make


class FlowStudio(_OrchestraStudio):
    """`with FlowStudio() as s:` -- s.state (the state dir), s.comfy (FakeComfy), s.call/get/post."""

    def __init__(self, cwd=None):
        super().__init__(Path(cwd) if cwd else Path(tempfile.mkdtemp(prefix="flow-studio-cwd-")))
        self._own_cwd = cwd is None
        self._threads: list = []

    def __enter__(self):
        from halo_harness.studio import flow_api, media_api
        self.comfy = FakeComfy()
        super().__enter__()
        self._saved = (flow_api.RUNNER, media_api.URL)
        flow_api.RUNNER = factory(self.comfy.url)
        media_api.URL = self.comfy.url
        return self

    def __exit__(self, *a):
        from halo_harness.flows.state import request_stop
        from halo_harness.studio import flow_api, flow_runs, media_api
        for run_dir, t in self._threads:
            request_stop(run_dir, "rig closing")
            t.join(10)
        flow_runs.wait(15)
        flow_api.RUNNER, media_api.URL = self._saved
        super().__exit__(*a)
        self.comfy.close()
        if self._own_cwd:
            shutil.rmtree(self.repo, ignore_errors=True)

    # ---- runs ----------------------------------------------------------------------------------
    def new_run(self, slug: str = "flow-studio", **intake):
        from halo_harness.flows.state import new_run
        values = {"brief": "a one-line teaser for Halo Harness 3.0.4", "platforms": "x,instagram",
                  "project": uniq(slug)}
        values.update(intake)
        return Path(new_run(template_spec(), values, source="test", state_dir=self.state))

    def adapters(self, **kw):
        kw.setdefault("auto_accept", False)
        return factory(self.comfy.url)(state_dir=self.state, cwd=str(self.repo), **kw)

    def finished_run(self, slug: str = "flow-done"):
        from halo_harness.flows.run import run
        run_dir = self.new_run(slug)
        report = run(run_dir, adapters=self.adapters(auto_accept=True))
        assert report["status"] == "finished", report.get("stop_reason")
        return run_dir

    def waiting_run(self, slug: str = "flow-wait", timeout: float = 20.0):
        """A run on a background thread, parked at its confirm gate (`approve`)."""
        from halo_harness.flows import gates
        from halo_harness.flows.run import run
        run_dir = self.new_run(slug)
        box: dict = {}
        t = threading.Thread(target=lambda: box.update(report=run(run_dir, adapters=self.adapters())), daemon=True)
        t.start()
        self._threads.append((run_dir, t))
        end = time.monotonic() + timeout
        while time.monotonic() < end and gates.open_gate(run_dir) is None:
            time.sleep(0.02)
        assert gates.open_gate(run_dir) is not None, "the run never opened its gate"
        return run_dir, t, box


def wait_for(pred, timeout: float = 15.0, step: float = 0.02) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if pred():
            return True
        time.sleep(step)
    return bool(pred())
