"""The fleet pack's own test. Run it from the pack's folder:

    python -m tests.pack_test

It runs `halo_harness.ext.testing` -- the same checks `halo pack test .` makes, in a scratch home and project, never a
model call, never the network -- and then the pack's own checks below. The fleet's behaviour is tested from Halo's
suite (tests/test_fleet_*.py, test_pack_fleet.py), with the pack's modules under their old names
(tests/helpers/fleet_pack.py).
"""

import sys
from pathlib import Path

from halo_harness.ext import testing

PACK = Path(__file__).resolve().parent.parent


def own_checks(report) -> None:
    m = testing.manifest(PACK)
    c = m.get("contributes") or {}
    verbs = {e.get("verb"): e.get("module") for e in c.get("cli") or []}
    report.add("pack.yaml", "the pack's id is fleet", m.get("id") == "fleet", "the id is the folder's name")
    report.add("pack.yaml", "`halo fleet` and `halo mission` are the pack's verbs and ask for their grants",
               verbs == {"fleet": "cli/fleet.py", "mission": "cli/mission.py"}
               and {"cli:fleet", "cli:mission"} <= set(m.get("permissions") or []), "contributes.cli")
    for rel in ("cli/fleet.py", "cli/mission.py"):
        src = (PACK / rel).read_text(encoding="utf-8")
        report.add(rel, "exposes main(argv)", "def main(argv)" in src, "def main(argv) -> int")
    for rel in ("cli/slash_fleet.py", "cli/slash_mission.py"):
        src = (PACK / rel).read_text(encoding="utf-8")
        report.add(rel, "exposes run(args_text, facade)", "def run(args_text" in src, "def run(args_text, facade)")
    report.add("server/fleet_hub_api.py", "answers Studio's fleet routes (dispatch_fleet, view_for)",
               all(w in (PACK / "server" / "fleet_hub_api.py").read_text(encoding="utf-8")
                   for w in ("def dispatch_fleet", "def view_for", "def start_for_flag")), "the core's door calls them")


def main() -> int:
    report = testing.run(PACK)
    own_checks(report)
    print(report.text())
    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
