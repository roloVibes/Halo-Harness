"""tests.helpers.studio_fleet_layout -- the Fleet default layout in headless
Chrome (Halo 3.1.4.0 R1, from the owner's live check of 3.1.3.0: the Activity
log line wrapped one letter per row and the view read "really busy").

The rig is one harness `rolo@kali` with ONE live session: the remote tests'
FakeSession behind the real Controller and control socket (the way the TUI
opens it), its main agent marked running with a 40-character state text, so
the Activity log's first line is `STATE rolo@kali · main` "main running: ...".
Studio runs in-process over the scoped home. The page opens Fleet in a fresh
profile (no saved arrangement), at the driver's 1500 x 900 window.

    python -m tests.helpers.studio_fleet_layout layout   # five panels open, four strips, one click each, Reset, an old save kept
    python -m tests.helpers.studio_fleet_layout widths   # the log line's text column, narrow wrapped text, glance text at 12 px
    python -m tests.helpers.studio_fleet_layout mission  # the Mission how-it-works lines: in full, then folded, then opened

The last stdout line is a JSON object of what it saw (exit 2: no Chrome).
The checks it reads live in tests/helpers/studio_ui_fleet_layout.py."""
from __future__ import annotations

import os
import sys
import threading
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.helpers.chrome_driver import Driver  # noqa: E402
from tests.helpers.studio_fleet_probe import layout, mission, widths  # noqa: E402

STATE_TEXT = "Bash; sleep 40 while the test build runs"  # 40 characters, the shape of the owner's "Bash; sleep"
assert len(STATE_TEXT) == 40


class OneAgentRig:
    """Studio over the scoped home with one live local session whose main agent runs."""

    def __init__(self) -> None:
        from halo_harness.config.paths import bridge_home
        from halo_harness.controller import Controller
        from halo_harness.fleet import identity
        from halo_harness.remote import runtime
        from halo_harness.studio.server import start_server
        from halo_harness.theme import set_config_value
        from tests.helpers.fake_remote_session import FakeRegistry, FakeSession
        self.closers: list = []
        self._saved = {k: os.environ.get(k) for k in ("HALO_FLEET_PRIVATE", "HALO_FLEET_PARENT")}
        for k in self._saved:
            os.environ.pop(k, None)
        self.state = Path(bridge_home())
        self.state.mkdir(parents=True, exist_ok=True)
        for k, v in (("fleet.name", "rolo@kali"), ("remote.enabled", False)):
            set_config_value(k, v)
        identity.forget_cache()
        self.proj = self.state.parent / "kali-project"
        self.proj.mkdir(exist_ok=True)
        self.session = FakeSession("f1ee7a11000000000000000000000001")
        self.controller = Controller(session=self.session, cwd=self.proj, registry=FakeRegistry()).start()
        self.closers.append(self.controller.quit)
        self.act = runtime.start_for_controller(self.controller)
        if self.act is None:
            raise RuntimeError("the fake session's control socket did not open")
        self.run_main()
        self.server = start_server(port=0, cwd=self.proj, state_dir=self.state)
        threading.Thread(target=self.server.serve_forever, daemon=True, name="layout-studio").start()
        self.closers.append(self.server.server_close)
        self.closers.append(self.server.shutdown)

    def run_main(self) -> None:
        """The main agent works: state running, the 40-character state text as what it does now."""
        from halo_harness.agent import agent_registry
        tree = agent_registry.tree_for(self.session)
        with tree.lock:
            tree.rows[tree.root_id].update(state="running", current=STATE_TEXT, task="keep the test build green")

    def seed_mission(self) -> str:
        """One drafted mission in this harness's missions folder (GET fleet/missions lists it)."""
        from halo_harness.fleet import mission as M
        from halo_harness.fleet import mission_store as S
        doc = M.new_doc(mid=M.new_id(), goal="scan the lab network and chart what it finds", by="rolo")
        S.create(self.state, doc)
        return doc["id"]

    def url(self, extra: str = "") -> str:
        from halo_harness.studio.server import url_for
        return url_for(self.server, "fleet").replace("#t=", f"&tour=off{extra}#t=")  # 3.3.2.0 R2: Reset layout is the header's ... menu

    def close(self) -> None:
        from halo_harness.fleet import identity
        from halo_harness.remote import runtime
        try:
            runtime.stop()
        except Exception:
            pass
        runtime._private_flag = None
        runtime._reopeners[:] = []
        for fn in reversed(self.closers):
            try:
                fn()
            except Exception:
                pass
        identity.forget_cache()
        for k, v in self._saved.items():
            if v is not None:
                os.environ[k] = v


class FleetLayoutDriver(Driver):
    """`layout`, `widths`, `mission` over OneAgentRig (the driver base scopes the home)."""

    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        rig = OneAgentRig()
        try:
            which = (self.argv[:1] or ["layout"])[0]
            step = {"layout": layout, "widths": widths, "mission": mission}[which]
            yield ((step, (c, rig)),)
        finally:
            rig.close()


def main(argv: list) -> int:
    return FleetLayoutDriver(argv).main()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
