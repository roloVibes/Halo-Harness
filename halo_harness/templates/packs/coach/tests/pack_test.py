"""The coach pack's own test. Run it from the pack's folder:

    python -m tests.pack_test

It runs `halo_harness.ext.testing` -- the same checks `halo pack test .` makes, in a scratch home and project, never a
model call, never the network; the pack's tests/test_*.py run there too -- and then the pack's own checks below. The
coach's behaviour is tested from Halo's suite (tests/test_coach_*.py, test_improve_*.py, test_orchestra_coach*.py and
test_pack_coach.py), with the pack's modules under their old names (tests/helpers/coach_pack.py).
"""

import sys
from pathlib import Path

from halo_harness.ext import testing

PACK = Path(__file__).resolve().parent.parent


def own_checks(report) -> None:
    m = testing.manifest(PACK)
    c = m.get("contributes") or {}
    perms = m.get("permissions") or []
    report.add("pack.yaml", "the pack's id is coach", m.get("id") == "coach", "the id is the folder's name")
    for verb, module in (("coach", "cli/coach.py"), ("improve", "cli/improve.py")):
        report.add("pack.yaml", f"`halo {verb}` is the pack's verb ({module}) and asks for cli:{verb}",
                   any(e.get("verb") == verb and e.get("module") == module for e in c.get("cli") or [])
                   and f"cli:{verb}" in perms, f"contributes.cli: [{{verb: {verb}, module: {module}}}]")
        src = (PACK / module).read_text(encoding="utf-8")
        report.add(module, "exposes main(argv)", "def main(argv" in src, "def main(argv) -> int")
    report.add("pack.yaml", "the doctor row asks for doctor", bool(c.get("doctor")) and "doctor" in perms,
               "contributes.doctor + permissions: [doctor]")
    keys = {e.get("key") for e in c.get("settings") or []}
    report.add("pack.yaml", "its settings rows are the seven keys the core had",
               keys == {"probe.k", "probe.budget_factor", "library.cite", "improve.enabled", "improve.model",
                        "improve.since_days", "improve.max_candidates"}, f"got {sorted(k for k in keys if k)}")


def main() -> int:
    report = testing.run(PACK)
    own_checks(report)
    print(report.text())
    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
