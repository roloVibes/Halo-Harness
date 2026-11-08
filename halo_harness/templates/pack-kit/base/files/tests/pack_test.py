"""__NAME__'s own test. Run it from the pack's folder:

    python -m tests.pack_test

It runs `halo_harness.ext.testing` -- the same checks `halo pack test .` makes, in a scratch home and project, never a
model call, never the network -- and then the pack's own checks in `own_checks` below. Add yours there: each is one
`report.add(file, what, ok, fix)`, and a failed one prints `<file>: <what> -- <fix>` like every other.
"""

import sys
from pathlib import Path

from halo_harness.ext import testing

PACK = Path(__file__).resolve().parent.parent


def own_checks(report) -> None:
    """The pack's own checks, after the standard ones."""
    report.add("pack.yaml", "the pack's id is __ID__", testing.manifest(PACK).get("id") == "__ID__",
               "the id in pack.yaml is the pack's name everywhere: keep it as the folder's name")
# __OWN_CHECKS__


def main() -> int:
    report = testing.run(PACK)
    own_checks(report)
    print(report.text())
    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
