"""tests.test_review2_round9c -- pins for the vibes/review.md fix pass, round 9,
CLI and doctor findings (the first half of this round is in
tests/test_review2_round9.py, the TUI pilots in tests/test_review2_round9b.py):

  * f77  `providers setup openai/...` died in argparse; doctor suggested
        `--provider` values argparse rejects
  * f78  `doctor --agents/--roles/--teams/--local --json` printed text first
  * f80  the PATH check read halo's own environment

The session-flag pins (76, 82, 83) are in tests/test_review2_round9d.py.
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

REPO_DIR = Path(__file__).resolve().parent.parent
test, TESTS = new_registry()

if "BRIDGE_TEST_HOME" not in os.environ:
    os.environ["BRIDGE_TEST_HOME"] = tempfile.mkdtemp(prefix="r9c-home-")


# ---- f77: providers setup for the providers init does not take ---------------------

def _providers_setup(args: list, tty: bool = False) -> tuple:
    import halo_harness.init_cli as init_cli
    import halo_harness.providers_cli as providers_cli
    calls: list = []
    real_init, real_tty = init_cli.cmd_init, (sys.stdin, sys.stdout)
    init_cli.cmd_init = lambda argv: calls.append(list(argv)) or 0
    err, out = io.StringIO(), io.StringIO()
    old_err = sys.stderr
    sys.stderr, sys.stdout = err, out
    sys.stdin = SimpleNamespace(isatty=lambda: tty)
    sys.stdout = SimpleNamespace(isatty=lambda: tty, write=out.write, flush=lambda: None)
    try:
        rc = providers_cli.cmd_providers(["setup"] + args)
    finally:
        init_cli.cmd_init = real_init
        sys.stderr, sys.stdout = old_err, real_tty[1]
        sys.stdin = real_tty[0]
    return rc, calls, err.getvalue()


@test
def test_f77_setup_for_a_key_only_provider_says_what_to_set(ctx: Ctx):
    expect = {"openai": "OPENAI_API_KEY", "huggingface": "HF_TOKEN", "experiential": "EXPLABS_API_KEY",
              "codex_subscription": "codex login"}
    for name, needle in expect.items():
        rc, calls, err = _providers_setup([name])
        ctx.check(f"{name}: no argparse flow ran, got {calls}", calls == [])
        ctx.check(f"{name}: names {needle!r}, got {err!r}", needle in err and rc == 2)


@test
def test_f77_on_a_terminal_those_providers_open_the_wizard_without_a_bad_flag(ctx: Ctx):
    rc, calls, _err = _providers_setup(["openai"], tty=True)
    ctx.check(f"cmd_init is called with no --provider, got {calls}", calls == [[]] and rc == 0)
    rc2, calls2, _ = _providers_setup(["openrouter"])
    ctx.check(f"a sequential provider still gets its flag, got {calls2}", calls2 == [["--provider", "openrouter"]])


@test
def test_f77_doctor_never_suggests_a_provider_flag_init_rejects(ctx: Ctx):
    from halo_harness.init_providers import PROVIDERS, init_command_for
    from halo_harness.providers.enablement import PROVIDER_NAMES
    for name in list(PROVIDER_NAMES) + ["cc", "openai", "hf", "xp", "ollama", "codex"]:
        cmd = init_command_for(name)
        if "--provider" in cmd:
            ctx.check(f"{name}: {cmd!r} uses a flag value argparse accepts", cmd.split()[-1] in PROVIDERS)
    ctx.check("openai falls back to the wizard", init_command_for("openai") == "halo init")
    ctx.check("databricks keeps its flag", init_command_for("databricks") == "halo init --provider databricks")


# ---- f78: doctor --json starts at the JSON -----------------------------------------

def _doctor_stdout(argv: list) -> str:
    env = {k: v for k, v in os.environ.items() if not k.startswith("HALO_") and k != "BRIDGE_STATE_DIR"}
    env["PYTHONPATH"] = str(REPO_DIR)
    r = subprocess.run([sys.executable, "-m", "halo_harness", "doctor"] + argv, env=env, cwd=str(REPO_DIR),
                       capture_output=True, text=True, timeout=120)
    return r.stdout


@test
def test_f78_json_output_is_one_parseable_value_for_each_mode(ctx: Ctx):
    for argv in (["--agents", "--mock", "--json"], ["--teams", "--mock", "--json"], ["--roles", "--json"]):
        out = _doctor_stdout(argv)
        try:
            json.loads(out)
            parsed = True
        except ValueError:
            parsed = False
        ctx.check(f"{' '.join(argv)}: stdout is exactly one JSON value, got {out[:80]!r}", parsed)


@test
def test_f78_local_and_probe_all_honour_json_in_process(ctx: Ctx):
    import halo_harness.doctor as doctor
    import halo_harness.doctor_local as doctor_local
    import halo_harness.work_matrix as work_matrix
    real_local, real_matrix = doctor_local.run_local_acceptance_check, work_matrix.run_work_matrix
    doctor_local.run_local_acceptance_check = lambda model, state_dir=None: ([{"step": "load", "ok": True}], True)
    row = work_matrix.ProbeRow(name="ep", family="f", path_type="chat", status="200")
    work_matrix.run_work_matrix = lambda **kw: ([row], "report.json")
    buf, old = io.StringIO(), sys.stdout
    try:
        for argv in (["--local", "--json"], ["--work", "--probe-all", "--json"]):
            buf.seek(0)
            buf.truncate()
            sys.stdout = buf
            try:
                doctor.cmd_doctor(argv)
            finally:
                sys.stdout = old
            try:
                json.loads(buf.getvalue())
                ok = True
            except ValueError:
                ok = False
            ctx.check(f"{' '.join(argv)}: stdout is one JSON value, got {buf.getvalue()[:80]!r}", ok)
    finally:
        doctor_local.run_local_acceptance_check, work_matrix.run_work_matrix = real_local, real_matrix


# ---- f80: the PATH check asks a fresh shell ---------------------------------------

@test
def test_f80_path_check_runs_the_shell_without_halos_own_path(ctx: Ctx):
    import halo_harness.linux_fixes as lf
    seen: dict = {}

    def _fake_run(argv, **kw):
        seen["argv"], seen["env"] = argv, kw.get("env")
        return SimpleNamespace(stdout="/usr/bin:/bin\n")

    real, old_path = lf.subprocess.run, os.environ.get("PATH")
    lf.subprocess.run = _fake_run
    home = Path(tempfile.mkdtemp(prefix="r9-home-path-"))
    os.environ["PATH"] = str(home / ".local" / "bin") + os.pathsep + (old_path or "")
    try:
        on_path = lf.local_bin_on_noninteractive_path(shell="/bin/bash", home=home)
    finally:
        lf.subprocess.run = real
        os.environ["PATH"] = old_path or ""
    ctx.check("halo's own widened PATH no longer makes the check pass", on_path is False)
    ctx.check(f"the child env has no PATH, got keys {sorted((seen['env'] or {}))[:6]}", "PATH" not in (seen["env"] or {"PATH": 1}))
    ctx.check(f"bash is started as a login shell, got {seen['argv']}", seen["argv"][1:3] == ["-l", "-c"])


@test
def test_f80_bash_rc_file_is_the_one_a_login_bash_reads(ctx: Ctx):
    import halo_harness.linux_fixes as lf
    home = Path(tempfile.mkdtemp(prefix="r9-home-rc-"))
    ctx.check("no startup file yet -> .profile", lf.rc_file_for_shell("/bin/bash", home=home).name == ".profile")
    (home / ".bash_profile").write_text("# x\n", encoding="utf-8")
    ctx.check("a .bash_profile hides .profile from a login bash -> write that one",
              lf.rc_file_for_shell("/bin/bash", home=home).name == ".bash_profile")
    ctx.check("zsh is unchanged", lf.rc_file_for_shell("/bin/zsh", home=home).name == ".zshenv")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
