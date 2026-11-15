"""tests.helpers.halo_turn_net -- Halo 3.6.0.0 R8: `python -m tests.helpers.halo_turn_net <halo args>` runs
`halo` with `BRIDGE_TEST_NO_BACKGROUND_NET=1` honoured everywhere EXCEPT inside `halo_harness.agent.loop`, the
session loop, so a load-counting test (tests/test_ollama_loads.py) sees every request a real turn would send to its
Ollama host -- a first-use measurement included, which that flag would otherwise hide -- while nothing else in the
run (catalog refreshes, GPU probes, update checks) touches the network. The host is the test's own fake on loopback.
"""
from __future__ import annotations

import sys


def _install() -> None:
    import halo_harness.config.paths as paths
    original = paths.background_net_disabled

    def gate() -> bool:
        caller = sys._getframe(1).f_globals.get("__name__", "")
        if caller == "halo_harness.agent.loop":
            return False
        return original()

    paths.background_net_disabled = gate


if __name__ == "__main__":
    _install()
    from halo_harness.cli import main
    sys.argv = ["halo"] + sys.argv[1:]
    sys.exit(main())
