"""tests.helpers.standalone_studio -- the two processes of 3.4.1.1 defect 48, each run as a child by
tests/test_quit_leaves_own_studio.py in a scratch home (BRIDGE_TEST_HOME set by the parent):

    python -m tests.helpers.standalone_studio studio   # `halo studio --no-open --port 0`, the real command,
                                                       # as the owner starts it on its own (loopback, a free port)
    python -m tests.helpers.standalone_studio quit     # a halo session of this home that starts and quits (the
                                                       # Controller's quit path, as the TUI's /quit runs it);
                                                       # prints its one quit line
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def studio() -> int:
    from halo_harness.studio.server import cmd_studio
    return cmd_studio(["--no-open", "--port", "0"])


def quit_session() -> int:
    from halo_harness.controller import Controller
    from halo_harness.providers.config import default_state_dir
    from tests.helpers.fake_remote_session import FakeRegistry, FakeSession
    state = Path(default_state_dir())
    controller = Controller(session=FakeSession(), cwd=state, registry=FakeRegistry(), state_dir=state)
    controller.quit()
    print(f"QUIT-LINE {controller.stopped_line}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(studio() if sys.argv[1:] == ["studio"] else quit_session())
