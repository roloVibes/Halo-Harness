"""tests.test_review3_f3 -- 3.0.2.0 review fix pass, round F: review items 150
(/update relaunch drops the prompt), 151 (doctor honours --cwd and the model
chain), 152 (CI workflow), 153 (installer PATH edit) and 154 (the release
script's credential lookup never prompts). No network, no real installer.
"""
from __future__ import annotations

import contextlib
import io
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials

ensure_default_provider_credentials()

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
_ENV_KEYS = ("BRIDGE_STATE_DIR", "BRIDGE_TEST_HOME", "HALO_MODEL", "BRIDGE_MODEL", "ROLO_CLAUDE_MODEL",
             "CLAUDE_CONFIG_DIR")


@contextlib.contextmanager
def _home():
    saved = {k: os.environ.get(k) for k in _ENV_KEYS}
    home = Path(tempfile.mkdtemp(prefix="r3f3-home-"))
    for k in _ENV_KEYS:
        os.environ.pop(k, None)
    os.environ["BRIDGE_STATE_DIR"] = str(home)
    os.environ["CLAUDE_CONFIG_DIR"] = str(home / "claude")  # never read the real ~/.claude
    try:
        yield home
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# ---- item 150 -----------------------------------------------------------------

def _parse(argv):
    from halo_harness import cli
    return cli._build_parser().parse_intermixed_args(argv)


@test
def test_item150_relaunch_drops_the_prompt_and_fork_session(ctx: Ctx):
    from halo_harness import cli
    flags = cli._relaunch_flags(["refactor the parser", "--model", "or:x/y"])
    ns = _parse(["--continue", *flags])
    ctx.check(f"flags kept, prompt gone, got {flags}", flags == ["--model", "or:x/y"] and ns.prompt is None)
    ctx.check("--continue is set", ns.continue_ is True)
    flags = cli._relaunch_flags(["--model", "or:x/y", "-c", "--fork-session", "do X"])
    ns = _parse(["--continue", *flags])
    ctx.check(f"-c, --fork-session and the prompt are dropped, got {flags}",
              ns.prompt is None and not ns.fork_session and ns.model == "or:x/y")
    flags = cli._relaunch_flags(["--model", "same", "same"])
    ns = _parse(["--continue", *flags])
    ctx.check(f"a flag VALUE equal to the prompt stays, got {flags}", ns.model == "same" and ns.prompt is None)
    ctx.check("no prompt: argv minus --continue", cli._relaunch_flags(["--continue", "--model", "m"]) == ["--model", "m"])


@test
def test_item150_apply_update_and_relaunch_sends_no_prompt(ctx: Ctx):
    from halo_harness import cli
    from halo_harness import update as upd
    from halo_harness import update_cli
    sent = []
    orig_apply, orig_relaunch = update_cli.apply_update, upd.relaunch_halo
    update_cli.apply_update = lambda **kw: 0
    upd.relaunch_halo = lambda args, **kw: sent.append(list(args)) or 0
    try:
        cli._apply_update_and_relaunch(["do X", "--model", "or:a/b"])
    finally:
        update_cli.apply_update, upd.relaunch_halo = orig_apply, orig_relaunch
    ns = _parse(sent[0])
    ctx.check(f"relaunch argv parses with prompt None and continue_ True, got {sent}",
              ns.prompt is None and ns.continue_ is True and ns.model == "or:a/b")


# ---- item 151 -----------------------------------------------------------------

@test
def test_item151_doctor_permission_mode_reads_the_cwd_it_was_given(ctx: Ctx):
    from halo_harness import doctor
    with _home():
        project = Path(tempfile.mkdtemp(prefix="r3f3-proj-"))
        (project / ".claude").mkdir()
        (project / ".claude" / "settings.json").write_text('{"permissions": {"defaultMode": "plan"}}', encoding="utf-8")
        other = Path(tempfile.mkdtemp(prefix="r3f3-other-"))
        old = os.getcwd()
        os.chdir(other)
        try:
            line = doctor._check_permission_mode(project)
            ctx.check(f"--cwd project's defaultMode is reported, got {line!r}", "Permission mode: plan" in line)
            ctx.check("without --cwd the process directory is used (no plan there)",
                      "Permission mode: plan" not in doctor._check_permission_mode())
            flag = '{"permissions": {"defaultMode": "acceptEdits"}}'
            ctx.check("--settings is honoured too", "acceptEdits" in doctor._check_permission_mode(other, flag))
            entries = dict(doctor._check_entries(project, None))
            ctx.check(f"run_checks threads the cwd into the entry, got {entries['permission_mode']!r}",
                      "Permission mode: plan" in entries["permission_mode"])
        finally:
            os.chdir(old)


@test
def test_item151_default_model_line_names_the_effective_chain(ctx: Ctx):
    from halo_harness import doctor, launch_state
    with _home() as home:
        ctx.check("nothing set: the built-in default applies",
                  "not set in config.json" in doctor._check_default_model())
        os.environ["HALO_MODEL"] = "or:openai/gpt-5"
        line = doctor._check_default_model()
        ctx.check(f"HALO_MODEL is reported with its origin, got {line!r}",
                  "or:openai/gpt-5" in line and "HALO_MODEL" in line and "not set in config.json" not in line)
        os.environ.pop("HALO_MODEL")
        (home / "routes.json").write_text('{"default": "or:routes/model"}', encoding="utf-8")
        ctx.check("routes.json default is reported", "or:routes/model" in doctor._check_default_model())
        proj = Path(tempfile.mkdtemp(prefix="r3f3-last-"))
        launch_state.record_last_model("or:last/one", cwd=proj)
        ctx.check("the last-used model for that cwd wins", "or:last/one" in doctor._check_default_model(proj))


# ---- item 152 -----------------------------------------------------------------

@test
def test_item152_workflow_is_least_privilege_pinned_and_hash_locked(ctx: Ctx):
    import yaml
    path = REPO / ".github" / "workflows" / "suites.yml"
    wf = yaml.safe_load(path.read_text(encoding="utf-8"))
    ctx.check(f"top-level permissions are contents: read, got {wf.get('permissions')}",
              wf.get("permissions") == {"contents": "read"})
    steps = [s for job in wf["jobs"].values() for s in job["steps"]]
    uses = [s["uses"] for s in steps if "uses" in s]
    ctx.check(f"every action is pinned to a full commit SHA, got {uses}",
              uses and all(re.search(r"@[0-9a-f]{40}$", u) for u in uses))
    text = path.read_text(encoding="utf-8")
    ctx.check("each pin carries a version comment", all(re.search(r"@[0-9a-f]{40} # v\d", ln)
                                                       for ln in text.splitlines() if "uses: actions/" in ln))
    for job in wf["jobs"].values():
        pip_lines = [ln.strip() for s in job["steps"] for ln in str(s.get("run") or "").splitlines()
                     if "pip install" in ln]
        loose = [ln for ln in pip_lines if "--require-hashes" not in ln and "-e ." not in ln]
        ctx.check(f"no loose pip install in the job, got {loose}", not loose)
        editable = [ln for ln in pip_lines if "-e ." in ln]
        # a job without an editable install (the studio-ui build job runs the
        # tests from the checkout on PYTHONPATH) is fine; one that has it must
        # resolve nothing
        ctx.check(f"the editable install resolves nothing, got {editable}",
                  all("--no-deps" in ln and "--no-build-isolation" in ln for ln in editable))
    suites_jobs = [j for j in wf["jobs"].values() if "suites" in str(j.get("name", ""))]
    ctx.check("the suites jobs install the package editable and hash-locked",
              suites_jobs and all(any("-e ." in ln for s in j["steps"] for ln in str(s.get("run") or "").splitlines())
                                  for j in suites_jobs))
    lock = (REPO / "requirements-ci.lock").read_text(encoding="utf-8")
    blocks = re.split(r"\n(?=[A-Za-z0-9_.-]+==)", lock)[1:]
    names = {b.split("==")[0].lower() for b in blocks}
    ctx.check("the CI lock pins pyflakes, pip-audit and setuptools", {"pyflakes", "pip-audit", "setuptools"} <= names)
    ctx.check("every CI pin has a sha256", all(re.search(r"--hash=sha256:[0-9a-f]{64}", b) for b in blocks))


# ---- item 153 -----------------------------------------------------------------

@test
def test_item153_installers_ask_before_editing_shell_startup(ctx: Ctx):
    sh = (REPO / "scripts" / "install-halo.sh").read_text(encoding="utf-8")
    ps = (REPO / "scripts" / "install-halo.ps1").read_text(encoding="utf-8")
    ctx.check("sh: opt-out flag and env", "--no-modify-path" in sh and "HALO_NO_MODIFY_PATH" in sh)
    ctx.check("ps1: opt-out switch and env", "NoModifyPath" in ps and "HALO_NO_MODIFY_PATH" in ps)
    sh_lines = [ln for ln in sh.splitlines() if "update-shell" in ln and not ln.lstrip().startswith("#")]
    ctx.check(f"sh: the call is never silenced, got {sh_lines}", sh_lines and not any("/dev/null" in ln for ln in sh_lines))
    ps_lines = [ln for ln in ps.splitlines() if "update-shell" in ln and not ln.lstrip().startswith("#")]
    ctx.check(f"ps1: the call is not swallowed and goes through Run, got {ps_lines}",
              not any("$null" in ln for ln in ps_lines) and any(ln.strip().startswith("Run uv tool update-shell") for ln in ps_lines))
    ctx.check("sh: it is asked first (confirm) before the run", re.search(
        r'confirm "Add ~/\.local/bin to PATH[^\n]*\n\s*run uv tool update-shell', sh) is not None)
    ctx.check("ps1: it is asked first (Confirm) before the run", re.search(
        r'Confirm "Add [^\n]*\n\s*Run uv tool update-shell', ps) is not None)
    for rel in ("docs/INSTALL.md", "README.md"):
        t = (REPO / rel).read_text(encoding="utf-8")
        ctx.check(f"{rel} documents the edit and the opt-out", "update-shell" in t and "--no-modify-path" in t)
    if os.name == "nt":
        return  # `bash` on a Windows runner can be the WSL stub, which exits non-zero with no distro; the text checks above stand
    try:
        syntax = subprocess.run(["bash", "-n", "scripts/install-halo.sh"], capture_output=True, text=True, cwd=str(REPO))
    except OSError:
        return  # no bash on this runner; the text checks above stand
    ctx.check(f"install-halo.sh still parses, got {syntax.stderr!r}", syntax.returncode == 0)


# ---- item 154 -----------------------------------------------------------------

@test
def test_item154_credential_lookup_never_prompts_or_hangs(ctx: Ctx):
    sys.path.insert(0, str(REPO / "scripts"))
    import release
    seen = {}

    def _ok(cmd, **kw):
        seen.update(kw)
        return subprocess.CompletedProcess(cmd, 0, stdout="username=u\npassword=tok123\n", stderr="")
    ctx.check("a stored token is returned", release.git_credential_token(run_fn=_ok) == "tok123")
    ctx.check(f"terminal prompts are off, got {seen.get('env', {}).get('GIT_TERMINAL_PROMPT')!r}",
              seen["env"].get("GIT_TERMINAL_PROMPT") == "0")
    ctx.check("askpass is a no-op program", seen["env"].get("GIT_ASKPASS") == "true")
    ctx.check(f"a timeout is set, got {seen.get('timeout')}", isinstance(seen.get("timeout"), (int, float)) and seen["timeout"] > 0)
    ctx.check("a failing git (no helper, prompts disabled) is None", release.git_credential_token(
        run_fn=lambda cmd, **kw: subprocess.CompletedProcess(cmd, 128, stdout="", stderr="fatal: terminal prompts disabled")) is None)

    def _slow(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, kw.get("timeout", 1))
    ctx.check("a timeout is None, never an exception", release.git_credential_token(run_fn=_slow) is None)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
