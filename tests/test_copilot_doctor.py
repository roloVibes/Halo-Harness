"""tests.test_copilot_doctor -- `halo doctor`'s one Copilot row (Halo 3.3.17.0 R2, providers/copilot_doctor.py): not
set up (an info line naming the two settings), set up but not signed in, signed in as whom until when, the token
expired, consent missing (the scopes named), billing not enabled and no licence -- each with its one next step; the
row is in `halo doctor`'s table under the id `copilot`. No network: the row reads the settings, the env file and the
account record only.

Run: python -m tests.test_copilot_doctor
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.copilot_rig import CopilotRig  # noqa: E402
from tests.helpers.mock_copilot import USER  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _row() -> str:
    from halo_harness.providers.copilot_doctor import row
    return row()


@test
def test_each_state_and_its_next_step(ctx: Ctx):
    from halo_harness.providers import copilot_account as A
    with CopilotRig(configured=False):
        line = _row()
        ctx.check(f"not set up: an info line naming the settings, got {line!r}", line.startswith("[OK] Copilot at work: not set up")
                  and "copilot.tenant" in line and "copilot.client_id" in line)
    with CopilotRig() as r:
        line = _row()
        ctx.check(f"not signed in, got {line!r}", line.startswith("[WARN]") and "not signed in" in line
                  and line.endswith("-> fix: halo copilot signin"))
        r.signin()
        line = _row()
        ctx.check(f"signed in as whom until when, got {line!r}", line.startswith(f"[OK] Copilot at work: signed in as {USER}")
                  and "pretend-tenant" in line and " until 20" in line)
        cases = (("expired", "token expired", "-> fix: halo copilot signin"),
                 ("consent", "consent missing -- an admin consents to https://workiq.svc.cloud.microsoft/.default", "-> see:"),
                 ("billing", "billing not enabled", "-> see:"), ("licence", "no Microsoft 365 Copilot licence", "-> see:"))
        for kind, words, step in cases:
            A.note_error(kind, f"Copilot: a {kind} line")
            line = _row()
            ctx.check(f"{kind}: {words!r}, got {line!r}", line.startswith("[WARN]") and words in line and step in line)


@test
def test_the_row_is_in_the_doctor_table(ctx: Ctx):
    from halo_harness.doctor import _check_entries
    with CopilotRig(configured=False):
        ids = [cid for cid, _line in _check_entries()]
        ctx.check("one copilot row", ids.count("copilot") == 1)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
