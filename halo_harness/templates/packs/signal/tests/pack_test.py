"""The Signal pack's own test. Run it from the pack's folder:

    python -m tests.pack_test

It runs `halo_harness.ext.testing` -- the same checks `halo pack test .` makes, in a scratch home and project, never a
model call, never the network; the pack's tests/test_*.py run there too -- and then the pack's own checks below.
"""

import sys
from pathlib import Path

from halo_harness.ext import testing

PACK = Path(__file__).resolve().parent.parent


def own_checks(report) -> None:
    m = testing.manifest(PACK)
    report.add("pack.yaml", "the pack's id is signal", m.get("id") == "signal", "the id is the folder's name")
    svc = ((m.get("contributes") or {}).get("services") or [{}])[0]
    report.add("pack.yaml", "the bridge is an autostart service with a health file",
               svc.get("name") == "bridge" and svc.get("autostart") is True and (svc.get("health") or {}).get("file"),
               "contributes.services[bridge]: autostart true, health {file: health.json}")
    report.add("pack.yaml", "signal-cli is a requirement, never installed",
               any(r.get("name") == "signal-cli" for r in m.get("requires") or [] if isinstance(r, dict)),
               "requires: [{kind: command, name: signal-cli, ...}]")


def main() -> int:
    report = testing.run(PACK)
    own_checks(report)
    print(report.text())
    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
