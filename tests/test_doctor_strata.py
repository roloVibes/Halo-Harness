"""tests.test_doctor_strata -- Halo 3.3.9.2 deliverable 6: `halo doctor --local`'s Strata lines
(halo_harness/doctor_strata.py through doctor_local_ids.id_steps), only when the runtime is configured:

1. not configured: no lines;
2. configured (`huggingface.strata_bin` = the fake strata): `strata --version` OK and `strata launch --status` OK
   (nothing serving, then the server Halo started), and id_steps carries them;
3. strata missing: one WARN line with the install route for this OS (install.ps1 on Windows, install.sh on Linux and
   the Mac), never a refusal.
`strata` is the fake (tests/helpers/fake_strata.py): nothing real runs, nothing is downloaded.
Run: python -m tests.test_doctor_strata
"""
from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.st_home import StHome  # noqa: E402

test, TESTS = new_registry()


@test
def test_nothing_when_not_configured(ctx: Ctx):
    from halo_harness.doctor_strata import configured, st_steps
    with StHome() as h:
        h.set_hf(strata_bin=None)
        ctx.check("not configured: no Strata lines", not configured(h.state) and st_steps(h.state) == [])


@test
def test_the_ok_lines(ctx: Ctx):
    from halo_harness.doctor_local_ids import id_steps
    from halo_harness.doctor_strata import st_steps
    with StHome() as h:
        steps = {s["step"]: s for s in st_steps(h.state)}
        ctx.check(f"two OK lines, got {[(k, s.get('tag'), s['reason']) for k, s in steps.items()]}",
                  list(steps) == ["strata", "strata launch"] and all(s["ok"] and not s.get("tag") for s in steps.values())
                  and steps["strata"]["reason"] == "strata --version: 0.2.10 (huggingface.strata_bin)"
                  and steps["strata launch"]["reason"] == "strata launch --status: nothing from strata launch is serving")
        from halo_harness.local_cli import cmd_local
        with contextlib.redirect_stdout(io.StringIO()):
            cmd_local(["serve", "--runtime", "strata", "--model", "qwen/IQ3_XXS"])
        st = next(s for s in st_steps(h.state) if s["step"] == "strata launch")
        ctx.check(f"what it serves now, got {st['reason']!r}", st["reason"].startswith(
            "strata launch --status: iq3-xxs-32k ready at http://127.0.0.1:"))
        got = [s["step"] for s in id_steps(h.state, role_table={}, main_ref="", versions={"box": "0.40.6"},
                                           staged=lambda host: None) if s["step"].startswith("strata")]
        ctx.check(f"halo doctor --local carries them, got {got}", got == ["strata", "strata launch"])


@test
def test_missing_says_the_install_route_for_this_os(ctx: Ctx):
    from halo_harness.doctor_strata import st_steps
    from halo_harness.strata import requirements as R
    with StHome() as h:
        h.set_hf(strata_bin=None, local_servers=[{"name": "strata-box", "url": "http://127.0.0.1:9/v1",
                                                  "runtime": "strata"}])
        R.SEAMS.update(which=lambda name: None, os=lambda: "windows")
        steps = st_steps(h.state)
        ctx.check(f"Windows: one WARN line, install.ps1, got {steps}", len(steps) == 1 and steps[0]["ok"]
                  and steps[0].get("tag") == "WARN" and "install.ps1 | iex" in steps[0]["reason"]
                  and r"%LOCALAPPDATA%\Strata\install" in steps[0]["reason"])
        R.SEAMS["os"] = lambda: "macos"
        steps = st_steps(h.state)
        ctx.check(f"the Mac: install.sh, got {steps[0]['reason']!r}", "sh install.sh" in steps[0]["reason"]
                  and "$XDG_DATA_HOME/strata/install" in steps[0]["reason"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
