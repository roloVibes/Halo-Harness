"""tests.test_doctor_tensorfold -- Halo 3.3.9.3 deliverable 6: `halo doctor --local`'s TensorFold lines
(halo_harness/doctor_tensorfold.py, tensorfold/requirements.py) with the fake binary (tests/helpers/tf_home.TfHome):

1. not configured (no `huggingface.tensorfold_bin`, no tensorfold server): no lines;
2. configured: two OK lines -- `tensorfold --version` and `tensorfold capabilities --json` (the backends, the engine,
   the families); `halo doctor --local` (doctor_local_ids.id_steps) carries them; a CUDA build on the Mac is a WARN;
3. missing: one WARN line with this OS's route -- Homebrew on the Mac, the native build guide on Windows, the fetched
   archive on Linux x86_64, no archive for another Linux CPU.
Two short commands of the fake; never a model, never the network.
Run: python -m tests.test_doctor_tensorfold
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.tf_home import TfHome  # noqa: E402

test, TESTS = new_registry()


@test
def test_nothing_when_not_configured(ctx: Ctx):
    from halo_harness.doctor_tensorfold import configured, tf_steps
    with TfHome() as h:
        h.set_hf(tensorfold_bin=None)
        ctx.check("not configured: no TensorFold lines", not configured(h.state) and tf_steps(h.state) == [])


@test
def test_the_ok_lines(ctx: Ctx):
    from halo_harness.doctor_local_ids import id_steps
    from halo_harness.doctor_tensorfold import tf_steps
    from halo_harness.tensorfold import requirements as Q
    with TfHome() as h:
        steps = {s["step"]: s for s in tf_steps(h.state)}
        ctx.check(f"two OK lines, got {[(k, s.get('tag'), s['reason']) for k, s in steps.items()]}",
                  list(steps) == ["tensorfold", "tensorfold capabilities"] and all(s["ok"] and not s.get("tag") for s in
                                                                                 steps.values())
                  and steps["tensorfold"]["reason"] == "tensorfold --version: 0.0.0-fake (huggingface.tensorfold_bin)"
                  and steps["tensorfold capabilities"]["reason"] == "tensorfold capabilities --json: backends cuda, "
                  "engine zig 0.0.0-fake, 2 model families")
        got = [s["step"] for s in id_steps(h.state, role_table={}, main_ref="", versions={"box": "0.40.6"},
                                           staged=lambda host: None) if s["step"].startswith("tensorfold")]
        ctx.check(f"halo doctor --local carries them, got {got}", got == ["tensorfold", "tensorfold capabilities"])
        Q.SEAMS["os"] = lambda: "macos"
        cap = next(s for s in tf_steps(h.state) if s["step"] == "tensorfold capabilities")
        ctx.check(f"a CUDA build on the Mac: WARN, got {cap}", cap.get("tag") == "WARN" and "wants the metal build"
                  in cap["reason"])
        os.environ["FAKE_TF_BACKEND"] = "metal"
        cap = next(s for s in tf_steps(h.state) if s["step"] == "tensorfold capabilities")
        ctx.check(f"the Metal build on the Mac: OK with its chip, got {cap['reason']!r}", not cap.get("tag")
                  and "backends metal" in cap["reason"] and "chip Apple M3 Max" in cap["reason"])


@test
def test_missing_says_the_route_for_this_os(ctx: Ctx):
    from halo_harness.doctor_tensorfold import tf_steps
    from halo_harness.tensorfold import requirements as Q
    with TfHome() as h:
        h.set_hf(tensorfold_bin=None, local_servers=[{"name": "tf-box", "url": "http://127.0.0.1:9/v1",
                                                      "runtime": "tensorfold"}])
        Q.SEAMS.update(which=lambda name: None)
        for os_name, arch, want in (("macos", "arm64", "brew install ashhart/tensorfold/tensorfold"),
                                    ("windows", "amd64", "zig build native install -Dsm=89"),
                                    ("linux", "x86_64", "fetches the linux-x86_64 release archive"),
                                    ("linux", "riscv64", "ships release archives for Linux x86_64 and aarch64 only")):
            Q.SEAMS.update(os=lambda o=os_name: o, machine=lambda a=arch: a)
            steps = tf_steps(h.state)
            ctx.check(f"{os_name} {arch}: one WARN line, got {steps}", len(steps) == 1 and steps[0]["ok"]
                      and steps[0].get("tag") == "WARN" and want in steps[0]["reason"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
