"""The first-run pack's own test. Run it from the pack's folder:

    python -m tests.pack_test

It runs `halo_harness.ext.testing` -- the same checks `halo pack test .` makes, in a scratch home and project, never a
model call, never the network; the pack's tests/test_*.py run there too -- and then the pack's own checks below. The
guided first run's behaviour is tested from Halo's suite (tests/test_pack_first_run*.py), with the pack linked in.
"""

import sys
from pathlib import Path

from halo_harness.ext import testing

PACK = Path(__file__).resolve().parent.parent


def own_checks(report) -> None:
    m = testing.manifest(PACK)
    c = m.get("contributes") or {}
    report.add("pack.yaml", "the pack's id is first-run", m.get("id") == "first-run", "the id is the folder's name")
    report.add("pack.yaml", "`halo start` is the pack's verb (cli/start.py) and asks for cli:start",
               any(e.get("verb") == "start" and e.get("module") == "cli/start.py" for e in c.get("cli") or [])
               and "cli:start" in (m.get("permissions") or []), "contributes.cli: [{verb: start, module: cli/start.py}]")
    report.add("pack.yaml", "the Setup check row is the block `run`",
               any(b.get("id") == "run" and b.get("kind") == "check" for b in c.get("setup") or []),
               "contributes.setup: [{id: run, kind: check, ...}]")
    src = (PACK / "cli" / "start.py").read_text(encoding="utf-8")
    report.add("cli/start.py", "exposes main(argv)", "def main(argv)" in src, "def main(argv) -> int")


def main() -> int:
    report = testing.run(PACK)
    own_checks(report)
    print(report.text())
    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
