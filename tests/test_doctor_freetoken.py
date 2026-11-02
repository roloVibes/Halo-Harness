"""tests.test_doctor_freetoken -- Halo 3.3.9.1 deliverable 6: `halo doctor --local`'s FreeToken lines
(halo_harness/doctor_freetoken.py through doctor_local_ids.id_steps), only when the runtime is configured:

1. not configured: no lines;
2. configured (`huggingface.freetoken_bin` = the fake ft), Linux, driver 580, nvcc 13: four OK lines (the platform,
   `ft --version`, the driver, nvcc), and id_steps carries them;
3. on Windows with no driver and no nvcc: WARN lines, each with its install line, never a refusal; under WSL2 the
   pinned-memory caveat is its own WARN line.
The driver and nvcc are answered by the requirements seam: no real nvidia-smi or nvcc runs; `ft --version` is the fake.
Run: python -m tests.test_doctor_freetoken
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.ft_home import LINUX, FtHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _runner(driver: str = "580.65.06", nvcc: str = "13.0"):
    def run(argv: list) -> "tuple[int, str]":
        if argv[0] == "nvidia-smi":
            return (0, f"{driver}\n") if driver else (127, "nvidia-smi: not found")
        if argv[0] == "nvcc":
            return (0, f"Cuda compilation tools, release {nvcc}, V{nvcc}.48") if nvcc else (127, "nvcc: not found")
        p = subprocess.run(argv, capture_output=True, text=True, timeout=30)  # the fake ft (tests/helpers/fake_ft_server.py)
        return p.returncode, p.stdout + p.stderr
    return run


@test
def test_nothing_when_not_configured(ctx: Ctx):
    from halo_harness.doctor_freetoken import configured, ft_steps
    with FtHome() as h:
        h.set_hf(freetoken_bin=None)
        ctx.check("not configured: no FreeToken lines", not configured(h.state) and ft_steps(h.state) == [])


@test
def test_the_four_ok_lines(ctx: Ctx):
    from halo_harness.doctor_freetoken import ft_steps
    from halo_harness.doctor_local_ids import id_steps
    from halo_harness.freetoken import requirements as R
    with FtHome() as h:
        R.SEAMS["run"] = _runner()
        steps = {s["step"]: s for s in ft_steps(h.state)}
        ctx.check(f"four lines, got {list(steps)}", list(steps) == ["freetoken platform", "freetoken ft", "freetoken driver",
                                                                    "freetoken nvcc"])
        ctx.check(f"all OK, got {[(s.get('tag'), s['reason']) for s in steps.values()]}",
                  all(s["ok"] and not s.get("tag") for s in steps.values())
                  and steps["freetoken platform"]["reason"] == "FreeToken platform: linux x86_64"
                  and steps["freetoken ft"]["reason"] == "ft --version: 0.0.0+gfake (huggingface.freetoken_bin)"
                  and steps["freetoken driver"]["reason"] == "NVIDIA driver 580.65 (r580+, CUDA 13)"
                  and steps["freetoken nvcc"]["reason"] == "nvcc: CUDA 13.0 (kernels compile on first use)")
        got = [s["step"] for s in id_steps(h.state, role_table={}, main_ref="", versions={"box": "0.40.6"},
                                           staged=lambda host: None) if s["step"].startswith("freetoken")]
        ctx.check(f"halo doctor --local carries them, got {got}", got == list(steps))


@test
def test_warn_lines_say_what_to_install(ctx: Ctx):
    from halo_harness.doctor_freetoken import ft_steps
    from halo_harness.freetoken import requirements as R
    with FtHome() as h:
        R.SEAMS.update(run=_runner(driver="", nvcc=""), which=lambda name: None,
                       platform=lambda: {"os": "windows", "arch": "amd64", "linux": False, "x86": True, "wsl": False})
        steps = {s["step"]: s for s in ft_steps(h.state)}
        ctx.check(f"WARN, never a failure, got {[(s.get('tag'), s['ok']) for s in steps.values()]}",
                  all(s["ok"] and s.get("tag") == "WARN" for k, s in steps.items() if k != "freetoken ft"))
        ctx.check(f"the platform line, got {steps['freetoken platform']['reason']!r}",
                  steps["freetoken platform"]["reason"] == "FreeToken runs on Linux x86_64; this machine is windows "
                                                           "amd64 (on Windows: WSL2 with Ubuntu)")
        ctx.check(f"the driver's install line, got {steps['freetoken driver']['reason']!r}",
                  "nvidia-driver-580" in steps["freetoken driver"]["reason"])
        ctx.check(f"nvcc's install line, got {steps['freetoken nvcc']['reason']!r}",
                  steps["freetoken nvcc"]["reason"].startswith("nvcc not on PATH: FreeToken compiles its kernels with it")
                  and "cuda-toolkit-13-0" in steps["freetoken nvcc"]["reason"])
        R.SEAMS.update(run=_runner(), platform=lambda: {**LINUX, "wsl": True})
        wsl = next((s for s in ft_steps(h.state) if s["step"] == "freetoken wsl"), {})
        ctx.check(f"WSL2: the pinned-memory caveat, got {wsl}", wsl.get("tag") == "WARN"
                  and "pinned memory is capped near half of RAM" in wsl.get("reason", ""))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
