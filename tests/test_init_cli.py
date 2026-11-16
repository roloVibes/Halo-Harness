"""tests.test_init_cli -- `halo init` (H12 brief Part A): the whole
first run in one command. Every test runs against an isolated BRIDGE_TEST_
HOME (never the real machine's ~/.config/halo/env, ~/.config/vibes-hacker/env, or ~/.halo)
and a default `BRIDGE_TEST_CC_AUTH_STATUS` of "not logged in" so a doctor
check inside `init` never spawns a real `claude auth status` subprocess
(fast, deterministic, independent of whatever's actually installed on the
box running this suite) -- a test that specifically wants a faked claude.ai
login overrides it explicitly, the same test seam `tests/test_cc_models.py`
documents. A live pong is exercised against `tests.helpers.mock_openai.
MockUpstream` (a loopback-only HTTP server), never a real network call.
"""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.mock_openai import MockUpstream
from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials

# H15 part 2 addendum 3.1: a believable default credential (never a real
# one) keeps every or:/dbx:/ant: ref below resolving exactly as it did
# before parse_model_ref started refusing an auto-detected-disabled
# provider; no test in this file relies on credential ABSENCE itself.
ensure_default_provider_credentials()

REPO_DIR = Path(__file__).resolve().parent.parent
test, TESTS = new_registry()

_NOT_LOGGED_IN = json.dumps({"loggedIn": False})
_LOGGED_IN_CLAUDE_AI = json.dumps({"loggedIn": True, "authMethod": "claude.ai"})


def _fresh_home() -> Path:
    return Path(tempfile.mkdtemp(prefix="halo-init-"))


def _run(argv, home: Path, *, stdin: str = "", extra_env: "dict | None" = None, timeout: int = 40):
    # Hermetic child env: drop every harness/provider variable the parent
    # process (or an earlier test module) may carry, so an `init` under
    # test only ever sees what THIS test passes in.
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("BRIDGE_", "OPENROUTER_", "DATABRICKS_", "ANTHROPIC_",
                                "ROLO_CLAUDE_", "HALO_", "TYPESAFE_", "OLLAMA_", "HF_"))}
    env.update({"BRIDGE_TEST_HOME": str(home), "PYTHONPATH": str(REPO_DIR),
                "BRIDGE_TEST_CC_AUTH_STATUS": _NOT_LOGGED_IN})
    env.update(extra_env or {})
    return subprocess.run([sys.executable, "-m", "halo_harness"] + argv, env=env, cwd=str(REPO_DIR),
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           input=stdin, timeout=timeout)


def _env_file(home: Path) -> Path:
    """2.0.0 rename: `halo init` now writes the NEW default path -- the
    legacy `~/.config/vibes-hacker/env` is still READ (see
    test_env_file_still_read_from_legacy_vibes_hacker_path_when_new_
    absent below) but never written to again."""
    return home / ".config" / "halo" / "env"


# ---------------------------------------------------------------------------
# Part A step 2/7: credentials, env-file mode bits, idempotency
# ---------------------------------------------------------------------------

@test
def test_home_preset_stdin_key_writes_env_file_and_config(ctx: Ctx):
    home = _fresh_home()
    result = _run(["init", "--preset", "home", "--yes", "--no-live"], home, stdin="sk-or-fake-key-123\n")
    ctx.check(f"exit 0, got {result.returncode}, stderr={result.stderr!r}", result.returncode == 0)
    ctx.check("the key is never printed to stdout", "sk-or-fake-key-123" not in result.stdout)
    ctx.check("the key is never printed to stderr", "sk-or-fake-key-123" not in result.stderr)

    env_path = _env_file(home)
    ctx.check(f"the env file was written at {env_path}", env_path.exists())
    content = env_path.read_text(encoding="utf-8")
    ctx.check(f"it carries the key, got {content!r}", "OPENROUTER_API_KEY=sk-or-fake-key-123" in content)

    cfg_path = home / ".halo" / "config.json"
    ctx.check(f"config.json was written at {cfg_path}", cfg_path.exists())
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    ctx.check(f"model set to the home default, got {cfg}", cfg.get("model") == "or:deepseek/deepseek-v4.1-flash")

    ctx.check("never writes ~/.claude.json", not (home / ".claude.json").exists())
    ctx.check("never writes ~/.claude/settings.json", not (home / ".claude" / "settings.json").exists())

    if os.name != "nt":
        ctx.check(f"env file mode 0600, got {oct(stat.S_IMODE(env_path.stat().st_mode))}",
                   stat.S_IMODE(env_path.stat().st_mode) == 0o600)
        dir_mode = stat.S_IMODE(env_path.parent.stat().st_mode)
        ctx.check(f"env dir mode 0700, got {oct(dir_mode)}", dir_mode == 0o700)


@test
def test_home_preset_key_already_in_env_var_not_rewritten(ctx: Ctx):
    """Already-discoverable (ambient env, not yet a stdin/getpass entry) --
    reported as configured, the env file is never created at all (nothing
    to write -- the credential already resolves without it)."""
    home = _fresh_home()
    result = _run(["init", "--preset", "home", "--yes", "--no-live"], home,
                   extra_env={"OPENROUTER_API_KEY": "sk-or-ambient-key"})
    ctx.check(f"exit 0, got {result.returncode}", result.returncode == 0)
    ctx.check("reports already configured", "already configured" in result.stdout)
    ctx.check("the key is never printed", "sk-or-ambient-key" not in result.stdout)
    ctx.check("no env file needed to be created", not _env_file(home).exists())


@test
def test_home_preset_rerun_is_idempotent(ctx: Ctx):
    home = _fresh_home()
    first = _run(["init", "--preset", "home", "--yes", "--no-live"], home, stdin="sk-or-fake-key-abc\n")
    ctx.check(f"first run exit 0, got {first.returncode}", first.returncode == 0)
    env_path = _env_file(home)
    before = env_path.read_text(encoding="utf-8")

    second = _run(["init", "--preset", "home", "--yes", "--no-live"], home, stdin="")
    ctx.check(f"second run exit 0, got {second.returncode}, stderr={second.stderr!r}", second.returncode == 0)
    ctx.check("second run reports the CURRENT state (already configured)", "already configured" in second.stdout)
    after = env_path.read_text(encoding="utf-8")
    ctx.check("the env file is byte-identical after a no-op re-run", before == after)
    ctx.check("only one OPENROUTER_API_KEY= line exists (never duplicated)",
              after.count("OPENROUTER_API_KEY=") == 1)


@test
def test_no_key_entered_warns_but_does_not_crash(ctx: Ctx):
    home = _fresh_home()
    result = _run(["init", "--preset", "home", "--yes", "--no-live"], home, stdin="")
    ctx.check(f"exit 0 (no live pong attempted, so nothing to fail on), got {result.returncode}",
              result.returncode == 0)
    ctx.check("warns that no key was entered", "no key entered" in result.stdout.lower()
              or "not found" in result.stdout.lower())
    ctx.check("no traceback", "Traceback" not in result.stderr)


# ---------------------------------------------------------------------------
# Part A step 1: preset detection / gating
# ---------------------------------------------------------------------------

@test
def test_preset_and_provider_claude_are_gone(ctx: Ctx):
    """3.1.5.0 R1: the Claude subscription provider is gone from `halo
    init` -- `--preset claude` and `--provider claude` are argparse usage
    errors (exit 2), even with a claude.ai login faked."""
    home = _fresh_home()
    for flag in ("--preset", "--provider"):
        result = _run(["init", flag, "claude", "--yes", "--no-live"], home,
                      extra_env={"BRIDGE_TEST_CC_AUTH_STATUS": _LOGGED_IN_CLAUDE_AI})
        ctx.check(f"{flag} claude: exit 2, got {result.returncode}", result.returncode == 2)
        ctx.check(f"{flag} claude: argparse names the bad choice, got {result.stderr[-300:]!r}",
                  "invalid choice: 'claude'" in result.stderr)
    ctx.check("nothing written", not (home / ".halo" / "config.json").exists())


@test
def test_preset_home_and_work_never_probe_claude_login(ctx: Ctx):
    """An explicit --preset home/work never needs to know whether a claude.ai
    login exists at all -- BRIDGE_TEST_CC_AUTH_STATUS is deliberately left
    UNPARSEABLE here; the preset step never needs it -- proven by it never
    crashing even with a broken override in place, same as always."""
    home = _fresh_home()
    result = _run(["init", "--preset", "home", "--yes", "--no-live"], home, stdin="sk-or-x\n",
                   extra_env={"BRIDGE_TEST_CC_AUTH_STATUS": "not json at all"})
    ctx.check(f"exit 0, got {result.returncode}", result.returncode == 0)
    ctx.check("no traceback", "Traceback" not in result.stderr)


# ---------------------------------------------------------------------------
# Part A step 2 (Databricks) / step 3 (model) / never touching claude files
# ---------------------------------------------------------------------------

@test
def test_work_preset_host_and_token_via_stdin(ctx: Ctx):
    home = _fresh_home()
    result = _run(["init", "--preset", "work", "--yes", "--no-live"], home,
                   stdin="https://fake-ws.cloud.databricks.com\nfake-token-999\n")
    ctx.check(f"exit 0, got {result.returncode}, stderr={result.stderr!r}", result.returncode == 0)
    ctx.check("token never printed", "fake-token-999" not in result.stdout)
    content = _env_file(home).read_text(encoding="utf-8")
    ctx.check(f"host written, got {content!r}", "DATABRICKS_HOST=https://fake-ws.cloud.databricks.com" in content)
    ctx.check(f"token written, got {content!r}", "DATABRICKS_TOKEN=fake-token-999" in content)
    cfg = json.loads((home / ".halo" / "config.json").read_text(encoding="utf-8"))
    ctx.check(f"model set to the work default, got {cfg}",
              cfg.get("model") == "dbx:databricks-deepseek-v4-1-flash")


@test
def test_work_preset_already_configured_not_rewritten(ctx: Ctx):
    home = _fresh_home()
    result = _run(["init", "--preset", "work", "--yes", "--no-live"], home,
                   extra_env={"DATABRICKS_HOST": "https://ambient.cloud.databricks.com",
                              "DATABRICKS_TOKEN": "ambient-token"})
    ctx.check(f"exit 0, got {result.returncode}", result.returncode == 0)
    ctx.check("reports already configured", "already configured" in result.stdout)
    ctx.check("token never printed", "ambient-token" not in result.stdout)
    ctx.check("no env file needed to be created", not _env_file(home).exists())


@test
def test_model_flag_overrides_preset_default(ctx: Ctx):
    home = _fresh_home()
    result = _run(["init", "--preset", "home", "--yes", "--no-live", "--model", "or:deepseek/deepseek-v3.2"],
                   home, stdin="sk-or-x\n")
    ctx.check(f"exit 0, got {result.returncode}", result.returncode == 0)
    cfg = json.loads((home / ".halo" / "config.json").read_text(encoding="utf-8"))
    ctx.check(f"--model wins over the preset default, got {cfg}", cfg.get("model") == "or:deepseek/deepseek-v3.2")


# ---------------------------------------------------------------------------
# Part A step 3: model precedence in the real resolver both -p and the TUI use
# ---------------------------------------------------------------------------

@test
def test_model_precedence_flag_then_config_then_builtin_default(ctx: Ctx):
    from halo_harness.model import DEFAULT_MODEL_REF, resolve_default_model_raw
    from halo_harness.theme import set_config_value
    home = _fresh_home()
    old_home = os.environ.get("BRIDGE_TEST_HOME")
    os.environ["BRIDGE_TEST_HOME"] = str(home)
    old_bridge_model = os.environ.pop("BRIDGE_MODEL", None)
    try:
        ctx.check(f"nothing configured -> the built-in default, got {resolve_default_model_raw({})!r}",
                  resolve_default_model_raw({}) == DEFAULT_MODEL_REF)

        set_config_value("model", "or:deepseek/deepseek-v3.2")
        ctx.check("config.json's model wins over the built-in default",
                  resolve_default_model_raw({}) == "or:deepseek/deepseek-v3.2")

        ctx.check("routes.json's own 'default' still wins over config.json (pre-existing precedence)",
                  resolve_default_model_raw({"default": "or:from-routes/model"}) == "or:from-routes/model")

        os.environ["BRIDGE_MODEL"] = "or:from-env/model"
        ctx.check("BRIDGE_MODEL still wins over everything below it (pre-existing precedence)",
                  resolve_default_model_raw({"default": "or:from-routes/model"}) == "or:from-env/model")
    finally:
        os.environ.pop("BRIDGE_MODEL", None)
        if old_bridge_model is not None:
            os.environ["BRIDGE_MODEL"] = old_bridge_model
        if old_home is not None:
            os.environ["BRIDGE_TEST_HOME"] = old_home
        else:
            os.environ.pop("BRIDGE_TEST_HOME", None)


@test
def test_headless_build_session_honours_config_json_model(ctx: Ctx):
    """The one shared session builder both `-p` and the TUI call -- proof
    that a `--model` flag beats config.json's own model, which in turn beats
    the hardcoded default, at the ACTUAL session-construction call site."""
    from halo_harness import headless
    from halo_harness.theme import set_config_value
    home = _fresh_home()
    old_home = os.environ.get("BRIDGE_TEST_HOME")
    os.environ["BRIDGE_TEST_HOME"] = str(home)
    try:
        set_config_value("model", "or:deepseek/deepseek-v3.2")
        build = headless.build_session(cwd=home, bare=True, print_mode=True)
        ctx.check(f"no --model given -> config.json's model wins, got {build.model_ref.raw!r}",
                  build.model_ref.raw == "or:deepseek/deepseek-v3.2")

        build2 = headless.build_session(cwd=home, model_ref_raw="or:deepseek/deepseek-chat-v3.1",
                                         bare=True, print_mode=True)
        ctx.check(f"--model still wins over config.json, got {build2.model_ref.raw!r}",
                  build2.model_ref.raw == "or:deepseek/deepseek-chat-v3.1")
    finally:
        if old_home is not None:
            os.environ["BRIDGE_TEST_HOME"] = old_home
        else:
            os.environ.pop("BRIDGE_TEST_HOME", None)


# ---------------------------------------------------------------------------
# Part A step 6: Linux fixes (rc-file marker, rg fake download, --no-fixes)
# ---------------------------------------------------------------------------

@test
def test_no_fixes_flag_skips_the_whole_step(ctx: Ctx):
    home = _fresh_home()
    result = _run(["init", "--preset", "home", "--yes", "--no-live", "--no-fixes"], home, stdin="sk-or-x\n")
    ctx.check(f"exit 0, got {result.returncode}", result.returncode == 0)
    ctx.check("step 6 reports skipped", "skipped (--no-fixes)" in result.stdout)


@test
def test_rc_file_line_written_once_with_marker(ctx: Ctx):
    """`ensure_local_bin_on_rc`/`rc_file_for_shell` (shared by doctor.py's
    own check and this init step): zsh -> ~/.zshenv, else ~/.profile;
    idempotent -- a second call is a pure no-op, never a duplicate line."""
    from halo_harness.linux_fixes import PATH_LINE, PATH_MARKER, ensure_local_bin_on_rc, rc_file_for_shell
    home = _fresh_home()
    ctx.check("zsh -> ~/.zshenv", rc_file_for_shell("/usr/bin/zsh", home=home) == home / ".zshenv")
    ctx.check("bash -> ~/.profile", rc_file_for_shell("/bin/bash", home=home) == home / ".profile")
    ctx.check("unknown/empty $SHELL -> ~/.profile", rc_file_for_shell("", home=home) == home / ".profile")

    written1, path1 = ensure_local_bin_on_rc(shell="/bin/bash", home=home)
    ctx.check("first call writes it", written1 and path1 == home / ".profile")
    written2, path2 = ensure_local_bin_on_rc(shell="/bin/bash", home=home)
    ctx.check("second call is a no-op", not written2 and path2 == path1)

    content = path1.read_text(encoding="utf-8")
    ctx.check("marker present exactly once", content.count(PATH_MARKER) == 1)
    ctx.check("PATH line present exactly once", content.count(PATH_LINE) == 1)


@test
def test_ripgrep_install_exercised_with_a_fake_download(ctx: Ctx):
    """No real network: `fetch_json`/`fetch_bytes` are swapped for fakes
    returning a genuine in-memory tar.gz built with the stdlib `tarfile`
    module, so real extraction/chmod/verify logic still runs end to end."""
    import io
    import tarfile

    from halo_harness.linux_fixes import install_static_ripgrep, pick_ripgrep_asset, ripgrep_asset_suffix

    ctx.check("linux x86_64 -> the musl asset suffix",
              ripgrep_asset_suffix(system="Linux", machine="x86_64") == "x86_64-unknown-linux-musl.tar.gz")
    ctx.check("windows -> no asset (this fix is Linux-only)",
              ripgrep_asset_suffix(system="Windows", machine="AMD64") is None)

    release = {"assets": [
        {"name": "ripgrep-14.1.0-x86_64-unknown-linux-musl.tar.gz",
         "browser_download_url": "https://example.invalid/rg.tar.gz"},
        {"name": "ripgrep-14.1.0-x86_64-pc-windows-msvc.zip",
         "browser_download_url": "https://example.invalid/rg.zip"},
    ]}
    asset = pick_ripgrep_asset(release, system="Linux", machine="x86_64")
    ctx.check(f"picks the musl tarball, got {asset}", asset is not None and asset["name"].endswith("musl.tar.gz"))

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        payload = b"#!/bin/sh\necho fake-rg\n"
        info = tarfile.TarInfo(name="ripgrep-14.1.0-x86_64-unknown-linux-musl/rg")
        info.size = len(payload)
        info.mode = 0o755
        tf.addfile(info, io.BytesIO(payload))
    archive_bytes = buf.getvalue()

    dest = _fresh_home() / "rg-dest"
    ok, msg = install_static_ripgrep(
        dest, system="Linux", machine="x86_64",
        fetch_json=lambda url: release, fetch_bytes=lambda url: archive_bytes,
        verify=lambda p: p.exists(),
    )
    ctx.check(f"reports success, got ({ok}, {msg!r})", ok and msg == str(dest / "rg"))
    ctx.check("the fake rg binary actually landed on disk", (dest / "rg").exists())

    ok2, msg2 = install_static_ripgrep(dest, system="Darwin", machine="x86_64",
                                        fetch_json=lambda url: release, fetch_bytes=lambda url: b"")
    ctx.check(f"an unsupported OS falls back to a package-manager hint, got ({ok2}, {msg2!r})",
              ok2 is False and isinstance(msg2, str) and msg2)


# ---------------------------------------------------------------------------
# Part A step 5: live pong (against a local mock, never a real network call)
# ---------------------------------------------------------------------------

@test
def test_live_pong_success_against_mock_upstream(ctx: Ctx):
    home = _fresh_home()
    mock = MockUpstream().start()
    try:
        result = _run(["init", "--preset", "home", "--yes", "--model", "or:mock/model"], home,
                       stdin="sk-or-x\n",
                       extra_env={"BRIDGE_OPENROUTER_BASE_URL": mock.base_url})
        ctx.check(f"exit 0, got {result.returncode}, stdout={result.stdout!r} stderr={result.stderr!r}",
                  result.returncode == 0)
        ctx.check("live pong header printed", "Live pong (" in result.stdout)
        ctx.check("reports the reply/model/provider/cost line",
                  "reply='pong'" in result.stdout and "provider=openrouter" in result.stdout)
        ctx.check("no key ever printed", "sk-or-x" not in result.stdout)
        ctx.check("summary points at starting the real thing", "Run `halo`" in result.stdout)
    finally:
        mock.stop()


@test
def test_live_pong_failure_is_a_nonzero_exit_with_a_hint(ctx: Ctx):
    home = _fresh_home()
    mock = MockUpstream().start()
    try:
        result = _run(["init", "--preset", "home", "--yes", "--model", "or:mock/error-401"], home,
                       stdin="sk-or-x\n",
                       extra_env={"BRIDGE_OPENROUTER_BASE_URL": mock.base_url})
        ctx.check(f"nonzero exit when the pong fails, got {result.returncode}", result.returncode != 0)
        ctx.check("step 5 reports a WARN", "[WARN]" in result.stdout)
        ctx.check("summary names a next step", "Next:" in result.stdout)
    finally:
        mock.stop()


@test
def test_no_live_skips_pong_and_catalog_refresh(ctx: Ctx):
    home = _fresh_home()
    result = _run(["init", "--preset", "home", "--yes", "--no-live"], home, stdin="sk-or-x\n")
    ctx.check(f"exit 0, got {result.returncode}", result.returncode == 0)
    ctx.check("live pong explicitly skipped", "Live pong: skipped (--no-live)" in result.stdout)
    ctx.check("catalog refresh explicitly skipped", "catalog refresh skipped" in result.stdout)


@test
def test_a_key_pasted_with_its_name_and_quotes_is_stored_bare(ctx: Ctx):
    """fx studio pass 2: `OPENROUTER_API_KEY="sk-or-..."` (a line copied from an env file) was stored verbatim, as
    `OPENROUTER_API_KEY=OPENROUTER_API_KEY="sk-or-...`, and every call failed with 401. Studio's provider save too."""
    home = _fresh_home()
    result = _run(["init", "--provider", "openrouter", "--yes", "--no-live"], home, stdin='OPENROUTER_API_KEY="sk-or-v1-pasted"\n')
    content = _env_file(home).read_text(encoding="utf-8") if _env_file(home).exists() else ""
    ctx.check(f"init: the bare key, got rc {result.returncode} {content!r}", result.returncode == 0
              and content.splitlines() == ["OPENROUTER_API_KEY=sk-or-v1-pasted"])
    home = _fresh_home()
    result = _run(["init", "--provider", "anthropic", "--yes", "--no-live"], home, stdin="export ANTHROPIC_API_KEY='sk-ant-pasted' \n")
    content = _env_file(home).read_text(encoding="utf-8") if _env_file(home).exists() else ""
    ctx.check(f"init: `export NAME='...'` too, got {content!r}", content.splitlines() == ["ANTHROPIC_API_KEY=sk-ant-pasted"])
    home = _fresh_home()
    code = ("from halo_harness.init_providers import save_tab_credentials as s; "
            "print(s('openrouter', {'key': 'OPENROUTER_API_KEY=\"sk-or-v1-studio\"'})[0])")
    env = {k: v for k, v in os.environ.items() if not k.startswith(("BRIDGE_", "OPENROUTER_", "HALO_"))}
    env.update({"BRIDGE_TEST_HOME": str(home), "PYTHONPATH": str(REPO_DIR)})
    got = subprocess.run([sys.executable, "-c", code], env=env, cwd=str(REPO_DIR), capture_output=True, text=True, timeout=40)
    content = _env_file(home).read_text(encoding="utf-8") if _env_file(home).exists() else ""
    ctx.check(f"Studio's save: the bare key, got {got.stdout!r} {got.stderr[-300:]!r} {content!r}",
              content.splitlines() == ["OPENROUTER_API_KEY=sk-or-v1-studio"])
    from halo_harness.init_cli import pasted_value
    ctx.check("a key is never cut to nothing, and a plain key is untouched",
              pasted_value("ABC_DEF=") == "ABC_DEF=" and pasted_value("  sk-or-v1-x\n") == "sk-or-v1-x"
              and pasted_value("dapi0123=") == "dapi0123=")


@test
def test_a_bad_key_can_be_replaced_from_the_terminal(ctx: Ctx):
    """fx studio pass 2: a key that answers 401 stayed: re-running `halo init` said 'already configured -- not changed',
    and the hint named `/providers` (a TUI command). `--replace-key` asks again and the 401 names it."""
    home = _fresh_home()
    mock = MockUpstream().start()
    try:
        bad = _run(["init", "--provider", "openrouter", "--yes", "--model", "or:mock/error-401"], home, stdin="sk-or-bad\n",
                   extra_env={"BRIDGE_OPENROUTER_BASE_URL": mock.base_url})
    finally:
        mock.stop()
    one = " ".join(bad.stdout.split())
    ctx.check(f"the 401 names the way out, got {bad.returncode} {one[-500:]!r}", bad.returncode != 0
              and "halo init --provider openrouter --replace-key" in one)
    again = _run(["init", "--provider", "openrouter", "--yes", "--no-live"], home, stdin="sk-or-good\n")
    ctx.check(f"without it: not changed, and it says how, got {again.stdout[-400:]!r}", "--replace-key" in again.stdout
              and "OPENROUTER_API_KEY=sk-or-bad" in _env_file(home).read_text(encoding="utf-8"))
    new = _run(["init", "--provider", "openrouter", "--yes", "--no-live", "--replace-key"], home, stdin="sk-or-good\n")
    content = _env_file(home).read_text(encoding="utf-8")
    ctx.check(f"--replace-key: the new key, once, got {new.returncode} {content!r} {new.stdout[-300:]!r}", new.returncode == 0
              and content.splitlines() == ["OPENROUTER_API_KEY=sk-or-good"] and "sk-or-good" not in new.stdout)


@test
def test_a_home_with_no_default_model_says_so_instead_of_naming_openrouter(ctx: Ctx):
    """fx studio pass 2: Setup with only an Ollama host (no model picked) ends in a home with no `model`; `halo -p`
    then failed with 'OpenRouter not configured', a provider this person never chose. It now says what is missing."""
    home = _fresh_home()
    (home / ".halo").mkdir(parents=True)
    (home / ".halo" / "config.json").write_text(json.dumps({"ollama": {"hosts": [{"name": "default", "url": "http://127.0.0.1:9",
                                                                                  "default": True}]}}), encoding="utf-8")
    got = _run(["-p", "hello"], home, extra_env={"OLLAMA_HOST": "http://127.0.0.1:9", "HALO_NO_UPDATER": "1"}, timeout=60)
    err = " ".join(got.stderr.split())
    ctx.check(f"it names the missing default model and the command that sets one, got {got.returncode} {err[-500:]!r}",
              got.returncode != 0 and "no default model is set" in err and "halo config set model" in err and "ol:<name>" in err)


def _ollama_config(home: Path, hosts: list) -> None:
    (home / ".halo").mkdir(parents=True, exist_ok=True)
    (home / ".halo" / "config.json").write_text(json.dumps({"ollama": {"hosts": hosts}}), encoding="utf-8")


def _config(home: Path) -> dict:
    p = home / ".halo" / "config.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


_TERMINAL = ["init", "--terminal", "--no-fixes"]


@test
def test_the_terminal_setup_offers_ollama_and_saves_a_picked_model_with_no_key(ctx: Ctx):
    """Local models only: the terminal setup listed only Databricks, OpenRouter and Anthropic. It now has an ollama
    row: pick the server (a host already in ollama.hosts here, from a numbered list), pick one of the models it lists,
    and it is the default model, written as Setup's Model page writes it; no key is asked."""
    from tests.helpers.mock_ollama import MockUpstream as MockOllama
    with MockOllama() as fake:
        home = _fresh_home()
        _ollama_config(home, [{"name": "gpu-box", "url": fake.base_url, "default": True}])
        # 4 = ollama; host 2 = gpu-box (1 is this computer); model 2 = gpt-oss:20b; no other provider; default mode
        got = _run(_TERMINAL, home, stdin="4\n2\n2\nn\n\n", extra_env={"OLLAMA_HOST": "http://127.0.0.1:9"})
    out = " ".join((got.stdout + got.stderr).split())  # the console wraps at 80 columns
    ctx.check(f"the provider list has an ollama row, got {got.stdout[:600]!r}", "ollama" in got.stdout.split("Done")[0])
    ctx.check(f"it lists the server's models to pick, got {out[-1500:]!r}", "1. qwen3:30b" in out and "2. gpt-oss:20b" in out)
    ctx.check(f"the pick is the default model, got {_config(home).get('model')!r} rc={got.returncode}",
              _config(home).get("model") == "ol:gpt-oss:20b@gpu-box" and got.returncode == 0)
    asked = out.split("Which Ollama?", 1)[-1].split("Set up another provider?", 1)[0]
    ctx.check(f"no key is asked and nothing goes to the env file, got {asked!r}",
              "Which Ollama?" in out and "key" not in asked.lower() and not _env_file(home).exists())
    ctx.check(f"no traceback, got {out[-800:]!r}", "Traceback" not in out)


@test
def test_the_terminal_setup_adds_this_computers_ollama_when_it_is_picked(ctx: Ctx):
    """'this computer' (OLLAMA_HOST, else 127.0.0.1:11434) joins ollama.hosts the way Setup's Ollama tab adds it."""
    from tests.helpers.mock_ollama import MockUpstream as MockOllama
    with MockOllama() as fake:
        home = _fresh_home()
        url = fake.base_url
        got = _run(_TERMINAL, home, stdin="4\n1\n1\nn\n\n", extra_env={"OLLAMA_HOST": url})
    cfg = _config(home)
    hosts = (cfg.get("ollama") or {}).get("hosts") or []
    ctx.check(f"the model and the host are written, got {cfg!r} {got.stdout[-800:]!r}",
              cfg.get("model") == "ol:qwen3:30b@default"
              and [(h.get("name"), h.get("url")) for h in hosts] == [("default", url)])


@test
def test_an_ollama_that_does_not_answer_is_one_line_and_the_provider_list_again(ctx: Ctx):
    home = _fresh_home()
    # 4 = ollama, 1 = this computer (a dead port), then 5 = Done at the provider list again
    got = _run(_TERMINAL, home, stdin="4\n1\n5\n\n", extra_env={"OLLAMA_HOST": "http://127.0.0.1:9"}, timeout=60)
    out = " ".join((got.stdout + got.stderr).split())
    ctx.check(f"one line says nothing answers and what to do, got {out[-1500:]!r}",
              "did not answer: nothing is listening there (connection refused)" in out and "ollama serve" in out
              and "https://ollama.com" in out)
    ctx.check(f"back to the provider list, no traceback, no model written, got rc={got.returncode} {out[-600:]!r}",
              out.count("Select a provider to set up:") == 2 and "Traceback" not in out and "model" not in _config(home))


@test
def test_an_ollama_with_no_models_names_the_pull_command(ctx: Ctx):
    from tests.helpers.mock_ollama import MockUpstream as MockOllama
    with MockOllama(tags_response={"models": []}) as fake:
        home = _fresh_home()
        got = _run(_TERMINAL, home, stdin="4\n1\n5\n\n", extra_env={"OLLAMA_HOST": fake.base_url})
    out = " ".join((got.stdout + got.stderr).split())
    ctx.check(f"it says there is no model and names `halo local pull`, got {out[-1200:]!r}",
              "has no models yet" in out and "halo local pull" in out and "model" not in _config(home))


@test
def test_the_provider_flag_takes_ollama_with_a_model(ctx: Ctx):
    """jb10 (a): `halo init --provider ollama` answered 'invalid choice'. It runs the picker's Ollama steps; --model
    takes the pick (this computer's Ollama, OLLAMA_HOST, joins ollama.hosts as the picker adds it)."""
    from tests.helpers.mock_ollama import MockUpstream as MockOllama
    with MockOllama() as fake:
        home = _fresh_home()
        got = _run(["init", "--provider", "ollama", "--model", "gpt-oss:20b", "--yes", "--no-fixes"], home,
                   extra_env={"OLLAMA_HOST": fake.base_url})
        url = fake.base_url
    cfg = _config(home)
    hosts = (cfg.get("ollama") or {}).get("hosts") or []
    out = " ".join((got.stdout + got.stderr).split())
    ctx.check(f"rc 0 and the model written, got rc={got.returncode} {cfg!r} {out[-800:]!r}",
              got.returncode == 0 and cfg.get("model") == "ol:gpt-oss:20b@default")
    ctx.check(f"the server joins ollama.hosts, got {hosts}", [(h.get("name"), h.get("url")) for h in hosts]
              == [("default", url)])
    ctx.check("no key asked, nothing in the env file, no traceback",
              not _env_file(home).exists() and "Traceback" not in out and "invalid choice" not in out)


@test
def test_the_provider_flag_without_a_model_names_the_servers_models_and_writes_nothing(ctx: Ctx):
    """jb10 (a): no terminal and no --model: one plain line with the server's models and how to pass one, rc 2."""
    from tests.helpers.mock_ollama import MockUpstream as MockOllama
    with MockOllama() as fake:
        home = _fresh_home()
        got = _run(["init", "--provider", "ollama", "--no-fixes"], home, extra_env={"OLLAMA_HOST": fake.base_url})
        missing = _run(["init", "--provider", "ollama", "--model", "nope:1b", "--no-fixes"], home,
                       extra_env={"OLLAMA_HOST": fake.base_url})
    out = " ".join((got.stdout + got.stderr).split())
    ctx.check(f"rc 2, the models named and --model said, got rc={got.returncode} {out[-800:]!r}",
              got.returncode == 2 and "qwen3:30b" in out and "gpt-oss:20b" in out and "--model" in out)
    ctx.check(f"nothing half-written, got {_config(home)!r}", "model" not in _config(home)
              and not (_config(home).get("ollama") or {}).get("hosts"))
    out2 = " ".join((missing.stdout + missing.stderr).split())
    ctx.check(f"a model the server does not have: rc 2 and its list, got rc={missing.returncode} {out2[-600:]!r}",
              missing.returncode == 2 and "nope:1b is not on Ollama" in out2 and "model" not in _config(home))


@test
def test_the_final_pick_lists_the_ollama_models_beside_the_key_providers(ctx: Ctx):
    """jb10 (b): one run set up two key providers and Ollama; the last cross-provider pick listed only the key
    providers' models. The Ollama models the run saw are listed too (first), through the same list builder."""
    import io
    from types import SimpleNamespace
    from rich.console import Console
    from halo_harness import init_cli, init_ollama
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY")}
    home = _fresh_home()
    seen: list = []
    real_pick, real_listed = init_cli._run_entry_picker, list(getattr(init_ollama, "_LISTED", []))
    try:
        os.environ["BRIDGE_TEST_HOME"] = str(home)
        os.environ["OPENROUTER_API_KEY"] = "sk-or-v1-final-pick-key-0123456789abcdef"
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-final-pick-key-0123456789"
        init_ollama._LISTED = [("ol:qwen3:30b@gpu-box", "30B"), ("ol:gpt-oss:20b@gpu-box", "")]  # what the pick saw
        init_cli._run_entry_picker = lambda args, console, entries: seen.extend(entries) or "ol:qwen3:30b@gpu-box"
        got = init_cli._step_finalize_default_model(
            SimpleNamespace(yes=False, model=None, team=None), Console(file=io.StringIO()),
            ["openrouter", "anthropic", "ollama"], {"openrouter": "or:x", "anthropic": "ant:opus",
                                                     "ollama": "ol:gpt-oss:20b@gpu-box"})
    finally:
        init_cli._run_entry_picker = real_pick
        init_ollama._LISTED = real_listed
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    refs = [e.get("ref") for e in seen]
    ctx.check(f"the Ollama models are offered, first, beside the others, got {refs[:6]} ({len(refs)})",
              refs[:2] == ["ol:qwen3:30b@gpu-box", "ol:gpt-oss:20b@gpu-box"]
              and any(str(r).startswith("ant:") for r in refs))
    ctx.check(f"an Ollama pick there is the default, got {got!r}", got == "ol:qwen3:30b@gpu-box")


_CTRL_C = """

import sys, getpass, rich.prompt
class Tty:
    def isatty(self): return True
    def readline(self): return sys.__stdin__.readline()
    def __getattr__(self, name): return getattr(sys.__stdin__, name)
sys.stdin = Tty()
def stop(*_a, **_k): raise KeyboardInterrupt
where = sys.argv[1]
getpass.getpass = stop if where == "key" else (lambda *_a, **_k: "sk-or-v1-typed")
if where == "confirm":
    rich.prompt.Confirm.ask = classmethod(lambda cls, *_a, **_k: stop())
from halo_harness.init_cli import cmd_init
sys.exit(cmd_init(["--terminal", "--no-live", "--no-fixes", "--provider", "openrouter"]))
"""


@test
def test_ctrl_c_at_a_terminal_prompt_stops_init(ctx: Ctx):
    """fx studio pass 2: Ctrl+C at the key prompt was read as 'no key' and init went on to write config.json; at a
    yes/no prompt it was read as the default answer (doctor ran). Ctrl+C now stops init: one line, exit 130."""
    for where in ("key", "confirm"):
        home = _fresh_home()
        env = {k: v for k, v in os.environ.items() if not k.startswith(("BRIDGE_", "OPENROUTER_", "DATABRICKS_", "ANTHROPIC_", "HALO_"))}
        env.update({"BRIDGE_TEST_HOME": str(home), "PYTHONPATH": str(REPO_DIR), "BRIDGE_TEST_CC_AUTH_STATUS": _NOT_LOGGED_IN})
        got = subprocess.run([sys.executable, "-c", _CTRL_C, where], env=env, cwd=str(REPO_DIR), capture_output=True, text=True,
                             encoding="utf-8", errors="replace", input="", timeout=60)
        out = got.stdout + got.stderr
        ctx.check(f"{where}: exit 130 and the one line, no traceback, got {got.returncode} {out[-600:]!r}", got.returncode == 130
                  and "halo init: stopped" in out and "Traceback" not in out)
        if where == "key":
            ctx.check(f"key: nothing written after it, got {list((home / '.halo').glob('*')) if (home / '.halo').exists() else []}",
                      not (home / ".halo" / "config.json").exists() and not _env_file(home).exists())
        else:
            ctx.check(f"confirm: stopped at doctor's question, nothing after it ran, got {got.stdout[-400:]!r}",
                      "Checks:" in got.stdout and "Summary:" not in got.stdout and "permission mode" not in got.stdout)


# ---------------------------------------------------------------------------
# Part A: wired into cli.py's help
# ---------------------------------------------------------------------------

@test
def test_top_level_help_epilog_mentions_init(ctx: Ctx):
    from halo_harness.cli import _build_parser
    help_text = _build_parser().format_help()
    ctx.check("epilog lists the init command", "init" in help_text.split("Commands:")[-1])


@test
def test_init_help_runs_standalone(ctx: Ctx):
    home = _fresh_home()
    result = _run(["init", "--help"], home)
    ctx.check(f"exit 0, got {result.returncode}", result.returncode == 0)
    ctx.check("mentions every flag", all(f in result.stdout for f in
              ("--preset", "--model", "--yes", "--no-live", "--no-fixes")))


# ---------------------------------------------------------------------------
# 1.0.1 hotfix 5: the interactive model picker -- --yes/--model skip it;
# a non-tty run (every subprocess test here -- stdin/stdout both piped)
# falls back to the numbered list, one stdin line for the choice.
# ---------------------------------------------------------------------------

_ONE_ENDPOINT_PER_FAMILY_PARSED = [
    {"name": "databricks-glm-5-3", "task": "llm/v1/chat", "ready": True, "permission_level": None,
     "endpoint_type": None, "ai_gateway_v2_supported": None,
     "api_types": ["mlflow/v1/chat/completions"], "foundation_model_name": "glm-5-3", "model_class": None},
    {"name": "databricks-kimi-k3", "task": "llm/v1/chat", "ready": True, "permission_level": None,
     "endpoint_type": None, "ai_gateway_v2_supported": None,
     "api_types": ["mlflow/v1/chat/completions"], "foundation_model_name": "kimi-k3", "model_class": None},
    {"name": "databricks-deepseek-v4-1-flash", "task": "llm/v1/chat", "ready": True, "permission_level": None,
     "endpoint_type": None, "ai_gateway_v2_supported": None,
     "api_types": ["mlflow/v1/chat/completions"], "foundation_model_name": "deepseek-v4-1-flash",
     "model_class": None},
]


def _seed_dbx_cache(home: Path) -> None:
    from halo_harness.providers.databricks import write_dbx_endpoints_json
    write_dbx_endpoints_json(home / ".halo", _ONE_ENDPOINT_PER_FAMILY_PARSED)


@test
def test_picker_skipped_with_yes_even_with_a_cached_catalog(ctx: Ctx):
    home = _fresh_home()
    _seed_dbx_cache(home)
    result = _run(["init", "--preset", "work", "--yes", "--no-live"], home,
                   extra_env={"DATABRICKS_HOST": "https://fake-ws.cloud.databricks.com",
                              "DATABRICKS_TOKEN": "fake-token"})
    ctx.check(f"exit 0, got {result.returncode}, stderr={result.stderr!r}", result.returncode == 0)
    ctx.check("no picker prompt printed", "Pick a default model" not in result.stdout)
    cfg = json.loads((home / ".halo" / "config.json").read_text(encoding="utf-8"))
    ctx.check(f"still the plain preset default, got {cfg}",
              cfg.get("model") == "dbx:databricks-deepseek-v4-1-flash")


@test
def test_picker_skipped_when_model_flag_given(ctx: Ctx):
    home = _fresh_home()
    _seed_dbx_cache(home)
    result = _run(["init", "--preset", "work", "--model", "dbx:databricks-kimi-k3", "--no-live"], home,
                   extra_env={"DATABRICKS_HOST": "https://fake-ws.cloud.databricks.com",
                              "DATABRICKS_TOKEN": "fake-token"})
    ctx.check(f"exit 0, got {result.returncode}, stderr={result.stderr!r}", result.returncode == 0)
    ctx.check("no picker prompt printed", "Pick a default model" not in result.stdout)
    cfg = json.loads((home / ".halo" / "config.json").read_text(encoding="utf-8"))
    ctx.check(f"the explicit --model wins, got {cfg}", cfg.get("model") == "dbx:databricks-kimi-k3")


@test
def test_numbered_fallback_picks_the_chosen_entry_non_tty(ctx: Ctx):
    """Every `_run` invocation here has stdin/stdout both piped (never a
    real tty), so this exercises the numbered-list fallback exactly as a
    piped/non-interactive box would see it."""
    home = _fresh_home()
    _seed_dbx_cache(home)
    # No --yes: the picker step runs; the numbered list is alphabetical by
    # endpoint name (deepseek, glm, kimi) -- "2" is databricks-glm-5-3.
    result = _run(["init", "--preset", "work", "--no-live"], home,
                   stdin="2\n",
                   extra_env={"DATABRICKS_HOST": "https://fake-ws.cloud.databricks.com",
                              "DATABRICKS_TOKEN": "fake-token"})
    ctx.check(f"exit 0, got {result.returncode}, stderr={result.stderr!r}", result.returncode == 0)
    ctx.check("the numbered picker was actually offered", "Pick a default model" in result.stdout)
    cfg = json.loads((home / ".halo" / "config.json").read_text(encoding="utf-8"))
    ctx.check(f"the chosen (2nd) endpoint was written, got {cfg}",
              cfg.get("model") == "dbx:databricks-glm-5-3")


@test
def test_numbered_fallback_empty_input_keeps_the_preset_default(ctx: Ctx):
    home = _fresh_home()
    _seed_dbx_cache(home)
    result = _run(["init", "--preset", "work", "--no-live"], home, stdin="\n",
                   extra_env={"DATABRICKS_HOST": "https://fake-ws.cloud.databricks.com",
                              "DATABRICKS_TOKEN": "fake-token"})
    ctx.check(f"exit 0, got {result.returncode}, stderr={result.stderr!r}", result.returncode == 0)
    cfg = json.loads((home / ".halo" / "config.json").read_text(encoding="utf-8"))
    ctx.check(f"unchanged preset default, got {cfg}",
              cfg.get("model") == "dbx:databricks-deepseek-v4-1-flash")


@test
def test_picker_offers_nothing_without_a_cached_catalog(ctx: Ctx):
    home = _fresh_home()
    result = _run(["init", "--preset", "work", "--no-live"], home, stdin="\n",
                   extra_env={"DATABRICKS_HOST": "https://fake-ws.cloud.databricks.com",
                              "DATABRICKS_TOKEN": "fake-token"})
    ctx.check(f"exit 0, got {result.returncode}, stderr={result.stderr!r}", result.returncode == 0)
    ctx.check("no picker prompt with nothing cached", "Pick a default model" not in result.stdout)


# ---------------------------------------------------------------------------
# 1.0.1 hotfix 13: provider-first init -- "select a provider to set up"
# instead of a home/work/claude preset. `--preset` stays as a deprecated
# `--provider` alias; `--provider` (repeatable) drives the non-interactive
# path directly; the fully interactive picker loop + cross-provider default
# pick are exercised in-process with the picker/confirm steps monkeypatched
# (a real subprocess has no tty to drive a Textual app through anyway).
# ---------------------------------------------------------------------------

@test
def test_provider_databricks_yes_non_interactive(ctx: Ctx):
    home = _fresh_home()
    result = _run(["init", "--provider", "databricks", "--yes", "--no-live"], home,
                   extra_env={"DATABRICKS_HOST": "https://fake-ws.cloud.databricks.com",
                              "DATABRICKS_TOKEN": "fake-token"})
    ctx.check(f"exit 0, got {result.returncode}, stderr={result.stderr!r}", result.returncode == 0)
    ctx.check("the databricks provider path ran", "Databricks" in result.stdout)
    ctx.check("no preset/home/work wording anywhere", not any(
        w in result.stdout for w in ("Preset:", "home preset", "work preset")))
    cfg = json.loads((home / ".halo" / "config.json").read_text(encoding="utf-8"))
    ctx.check(f"model set to the databricks default, got {cfg}",
              cfg.get("model") == "dbx:databricks-deepseek-v4-1-flash")


@test
def test_provider_openrouter_yes_non_interactive(ctx: Ctx):
    home = _fresh_home()
    result = _run(["init", "--provider", "openrouter", "--yes", "--no-live"], home, stdin="sk-or-x\n")
    ctx.check(f"exit 0, got {result.returncode}, stderr={result.stderr!r}", result.returncode == 0)
    cfg = json.loads((home / ".halo" / "config.json").read_text(encoding="utf-8"))
    ctx.check(f"model set to the openrouter default, got {cfg}",
              cfg.get("model") == "or:deepseek/deepseek-v4.1-flash")


@test
def test_provider_anthropic_yes_non_interactive_writes_api_key(ctx: Ctx):
    home = _fresh_home()
    result = _run(["init", "--provider", "anthropic", "--yes", "--no-live"], home, stdin="sk-ant-fake-1\n")
    ctx.check(f"exit 0, got {result.returncode}, stderr={result.stderr!r}", result.returncode == 0)
    ctx.check("the key is never printed", "sk-ant-fake-1" not in result.stdout)
    content = _env_file(home).read_text(encoding="utf-8")
    ctx.check(f"ANTHROPIC_API_KEY written, got {content!r}", "ANTHROPIC_API_KEY=sk-ant-fake-1" in content)
    cfg = json.loads((home / ".halo" / "config.json").read_text(encoding="utf-8"))
    ctx.check(f"model set to the anthropic default, got {cfg}", cfg.get("model") == "ant:sonnet")


@test
def test_provider_anthropic_already_configured_not_rewritten(ctx: Ctx):
    home = _fresh_home()
    result = _run(["init", "--provider", "anthropic", "--yes", "--no-live"], home,
                   extra_env={"ANTHROPIC_API_KEY": "sk-ant-ambient"})
    ctx.check(f"exit 0, got {result.returncode}", result.returncode == 0)
    ctx.check("reports already configured", "already configured" in result.stdout)
    ctx.check("the key is never printed", "sk-ant-ambient" not in result.stdout)
    ctx.check("no env file needed to be created", not _env_file(home).exists())


@test
def test_provider_requires_at_least_one_value(ctx: Ctx):
    """`--provider` with no value at all is an argparse error (exit 2);
    covered here mainly so a FUTURE argparse config change that silently
    allows an empty list is caught (the guard in cmd_init is otherwise
    unreachable via argparse's own `action="append"`)."""
    home = _fresh_home()
    result = _run(["init", "--provider"], home)
    ctx.check(f"argparse usage error, got {result.returncode}", result.returncode == 2)


@test
def test_preset_alias_prints_a_deprecation_notice_and_behaves_like_provider(ctx: Ctx):
    home = _fresh_home()
    result = _run(["init", "--preset", "work", "--yes", "--no-live"], home,
                   extra_env={"DATABRICKS_HOST": "https://fake-ws.cloud.databricks.com",
                              "DATABRICKS_TOKEN": "fake-token"})
    ctx.check(f"exit 0, got {result.returncode}", result.returncode == 0)
    ctx.check("prints a one-line deprecation notice naming the real provider",
              "deprecated alias for --provider databricks" in result.stdout)


@test
def test_unconfigured_provider_status_tag(ctx: Ctx):
    from halo_harness.init_providers import provider_status
    home = _fresh_home()
    old_home = os.environ.get("BRIDGE_TEST_HOME")
    old_auth = os.environ.get("BRIDGE_TEST_CC_AUTH_STATUS")
    # 1.0.1 part 2 fixpass finding 10: snapshot every provider var cleared
    # below so the `finally` can RESTORE them (not just pop them) --
    # popping without restoring leaked into test_scripted_provider_loop_...
    # (this module's own `ensure_default_provider_credentials()` module-
    # level default), making ITS cross-provider pick see 2 or 3 configured
    # providers depending on which order the test runner happened to pick.
    old_provider_env = {k: os.environ.get(k) for k in
                         ("OPENROUTER_API_KEY", "DATABRICKS_HOST", "DATABRICKS_TOKEN", "ANTHROPIC_API_KEY",
                          "ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN")}
    os.environ["BRIDGE_TEST_HOME"] = str(home)
    os.environ["BRIDGE_TEST_CC_AUTH_STATUS"] = _NOT_LOGGED_IN
    for k in ("OPENROUTER_API_KEY", "DATABRICKS_HOST", "DATABRICKS_TOKEN", "ANTHROPIC_API_KEY",
              "ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN"):
        os.environ.pop(k, None)
    try:
        for p in ("databricks", "openrouter", "anthropic"):
            ctx.check(f"{p} starts out 'not set up', got {provider_status(p)!r}",
                      provider_status(p) == "not set up")
        os.environ["OPENROUTER_API_KEY"] = "sk-or-x"
        ctx.check(f"openrouter flips to configured, got {provider_status('openrouter')!r}",
                  provider_status("openrouter") == "configured")
        os.environ["BRIDGE_TEST_CC_AUTH_STATUS"] = _LOGGED_IN_CLAUDE_AI
        ctx.check(f"a claude.ai login is no provider, got {provider_status('claude')!r}",
                  provider_status("claude") == "not set up")
    finally:
        for k, v in old_provider_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        if old_home is None:
            os.environ.pop("BRIDGE_TEST_HOME", None)
        else:
            os.environ["BRIDGE_TEST_HOME"] = old_home
        if old_auth is None:
            os.environ.pop("BRIDGE_TEST_CC_AUTH_STATUS", None)
        else:
            os.environ["BRIDGE_TEST_CC_AUTH_STATUS"] = old_auth


@test
def test_scripted_provider_loop_sets_up_two_then_done_then_cross_provider_pick(ctx: Ctx):
    """In-process (never a subprocess -- a real tty-driven Textual picker
    has no piped-stdin equivalent to script): monkeypatches `_step_select_
    provider`/`_confirm`/`_run_entry_picker` to walk databricks then
    openrouter, say "yes" to "set up another?" once and "no" the second
    time, then answers the final cross-provider pick explicitly."""
    import halo_harness.init_cli as init_cli

    home = _fresh_home()
    old_home = os.environ.get("BRIDGE_TEST_HOME")
    old_env_file = os.environ.get("BRIDGE_ENV_FILE")
    old_auth = os.environ.get("BRIDGE_TEST_CC_AUTH_STATUS")
    os.environ["BRIDGE_TEST_HOME"] = str(home)
    os.environ["BRIDGE_ENV_FILE"] = str(home / ".config" / "vibes-hacker" / "env")
    os.environ["BRIDGE_TEST_CC_AUTH_STATUS"] = _NOT_LOGGED_IN
    os.environ["DATABRICKS_HOST"] = "https://fake-ws.cloud.databricks.com"
    os.environ["DATABRICKS_TOKEN"] = "fake-token"
    os.environ["OPENROUTER_API_KEY"] = "sk-or-fake"
    # Both providers' catalogs are pre-seeded (rather than a live --refresh,
    # which --no-live skips) so the final cross-provider pick has real
    # entries from EACH provider to choose between.
    from halo_harness.providers.databricks import write_dbx_endpoints_json, write_models_json
    write_models_json(home / ".halo", [{"id": "vendor/model-x", "context_length": 128000,
                                                "max_output_tokens": 8192}])
    write_dbx_endpoints_json(home / ".halo", _ONE_ENDPOINT_PER_FAMILY_PARSED)

    real_select = init_cli._step_select_provider
    real_confirm = init_cli._confirm
    real_run_entry_picker = init_cli._run_entry_picker
    select_calls = iter(["databricks", "openrouter"])
    confirm_calls = iter([True, False])

    def _fake_select(args, console, *, header):
        try:
            return next(select_calls)
        except StopIteration:
            return "done"

    def _fake_confirm(args, console, question, *, default):
        if question.startswith("Run the guided first run now?"):  # 3.4.0.0 B: init offers it no more (kept: harmless)
            return False
        try:
            return next(confirm_calls)
        except StopIteration:
            return False

    def _fake_run_entry_picker(args, console, entries):
        # The final cross-provider pick: explicitly choose the OpenRouter
        # entry if present, proving the picker really did see BOTH
        # providers' catalogs merged together.
        for e in entries:
            if e["ref"].startswith("or:"):
                return e["ref"]
        return None

    init_cli._step_select_provider = _fake_select
    init_cli._confirm = _fake_confirm
    init_cli._run_entry_picker = _fake_run_entry_picker
    try:
        rc = init_cli.cmd_init(["--no-live"])
        ctx.check(f"exit 0, got {rc}", rc == 0)
        cfg = json.loads((home / ".halo" / "config.json").read_text(encoding="utf-8"))
        ctx.check(f"both providers' credentials resolve now, got databricks="
                  f"{init_cli.provider_status('databricks')!r} openrouter={init_cli.provider_status('openrouter')!r}",
                  init_cli.provider_status("databricks") == "configured"
                  and init_cli.provider_status("openrouter") == "configured")
        ctx.check(f"the cross-provider pick (an OpenRouter entry) won, got {cfg}",
                  isinstance(cfg.get("model"), str) and cfg["model"].startswith("or:"))
    finally:
        init_cli._step_select_provider = real_select
        init_cli._confirm = real_confirm
        init_cli._run_entry_picker = real_run_entry_picker
        for k in ("DATABRICKS_HOST", "DATABRICKS_TOKEN", "OPENROUTER_API_KEY"):
            os.environ.pop(k, None)
        for k, old in (("BRIDGE_TEST_HOME", old_home), ("BRIDGE_ENV_FILE", old_env_file),
                       ("BRIDGE_TEST_CC_AUTH_STATUS", old_auth)):
            if old is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = old


# ---------------------------------------------------------------------------
# 1.0.1 part 2 fixpass finding 15: a successful provider setup must not
# write a PERMANENT `enabled: true` override unless it's flipping an
# existing EXPLICIT `enabled: false` -- auto-detection already covers the
# ordinary case live, every time.
# ---------------------------------------------------------------------------

@test
def test_provider_setup_does_not_write_a_permanent_enabled_override_on_a_fresh_box(ctx: Ctx):
    home = _fresh_home()
    result = _run(["init", "--provider", "openrouter", "--yes", "--no-live"], home,
                   extra_env={"OPENROUTER_API_KEY": "sk-or-fake"})
    ctx.check(f"exit 0, got {result.returncode}", result.returncode == 0)
    config_path = home / ".halo" / "config.json"
    providers_block = None
    if config_path.exists():
        providers_block = json.loads(config_path.read_text(encoding="utf-8")).get("providers")
    ctx.check(f"no 'providers' block written just from a fresh successful setup, got {providers_block!r}",
              not providers_block)


@test
def test_provider_setup_flips_an_existing_explicit_disable_back_on(ctx: Ctx):
    home = _fresh_home()
    config_dir = home / ".halo"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.json").write_text(
        json.dumps({"providers": {"openrouter": {"enabled": False}}}), encoding="utf-8")
    result = _run(["init", "--provider", "openrouter", "--yes", "--no-live"], home,
                   extra_env={"OPENROUTER_API_KEY": "sk-or-fake"})
    ctx.check(f"exit 0, got {result.returncode}", result.returncode == 0)
    config = json.loads((config_dir / "config.json").read_text(encoding="utf-8"))
    ctx.check(f"the explicit disable was flipped back to enabled, got {config.get('providers')}",
              config["providers"]["openrouter"]["enabled"] is True)


@test
def test_chat_capable_dbx_entries_excludes_decision_only_endpoints(ctx: Ctx):
    """2.0.2 review finding 8 (major) pin: a decision-only/judge endpoint
    is chat-shaped (`is_chat_task` alone used to let it through) but
    takes no tools at all -- shown in init/the wizard's own default-
    model list as an ordinary family row, with nothing marking it
    different, it could become `config.model` after which every real
    turn failed with ToolsNotSupported. `databricks-openjev-qwen35-4b`
    is tabled `capabilities.decision_only` in the repo's own real
    model_table.json (test_qwen_decision_only.py's own fixture-free
    classification test relies on the exact same thing)."""
    from halo_harness.init_cli import _chat_capable_dbx_entries
    from halo_harness.providers.databricks import write_dbx_endpoints_json
    state_dir = Path(tempfile.mkdtemp(prefix="init-dbx-decision-only-"))
    write_dbx_endpoints_json(state_dir, [
        {"name": "databricks-qwen35-122b-a10b", "task": "llm/v1/chat", "ready": True},
        {"name": "databricks-openjev-qwen35-4b", "task": "llm/v1/chat", "ready": True},
    ])
    refs = [e["ref"] for e in _chat_capable_dbx_entries(state_dir)]
    ctx.check(f"the ordinary chat endpoint is offered, got {refs}", "dbx:databricks-qwen35-122b-a10b" in refs)
    ctx.check(f"the decision-only endpoint is excluded, got {refs}", "dbx:databricks-openjev-qwen35-4b" not in refs)


# ---------------------------------------------------------------------------
# 3.3.0.0 R4: `halo init` opens Studio on Setup (studio/setup_door.py); the
# console setup is `--terminal` (3.4.0.0 B2), and runs when no browser can open. In process, on a fake terminal,
# every Studio and browser seam stubbed (tests/helpers/setup_door_stubs.py); the console's questions stubbed too.
# ---------------------------------------------------------------------------

def _door_init(argv, extra_env=None, **stubs):
    """`cmd_init(argv)` on a fake terminal in a fresh home: `(rc, stdout, the door record, the wizard's args)`."""
    from halo_harness import init_cli
    from tests.helpers.setup_door_stubs import door_stubs, fake_tty
    home = _fresh_home()
    keys = ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "HALO_ENV_FILE", "HALO_INIT_NO_LAUNCH", "HALO_INIT_POLL_S")
    before = {k: os.environ.get(k) for k in keys}
    for k in ("BRIDGE_STATE_DIR", "HALO_INIT_NO_LAUNCH", "HALO_INIT_POLL_S"):
        os.environ.pop(k, None)
    os.environ.update({"BRIDGE_TEST_HOME": str(home), "HALO_ENV_FILE": str(home / "env"), **(extra_env or {})})
    ran: list = []  # 3.4.0.0 B2: the console setup's first question stands in for the wizard: it says the setup ran
    saved = (init_cli._step_select_provider, init_cli._step_pick_permission_mode, init_cli._step_linux_fixes)
    init_cli._step_select_provider, init_cli._step_pick_permission_mode, init_cli._step_linux_fixes = (
        lambda args, console, header: ran.append(args) or "done", lambda args, console: "", lambda args, console: [])
    try:
        with door_stubs(**stubs) as rec, fake_tty() as out:
            rc = init_cli.cmd_init(list(argv))
    finally:
        init_cli._step_select_provider, init_cli._step_pick_permission_mode, init_cli._step_linux_fixes = saved
        for k, v in before.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    return rc, out.getvalue(), rec, ran


@test
def test_init_opens_setup_in_studio(ctx: Ctx):
    rc, text, rec, ran = _door_init(["--no-launch"])  # 3.3.3.0 R1: --no-launch is the old return-at-once, byte for byte
    url = rec["opened"][0] if rec["opened"] else ""
    ctx.check(f"exit 0, the wizard not run, got {rc} {ran}", rc == 0 and not ran)
    ctx.check(f"Studio started on ?mode=setup&first=1 with no browser of its own, got {rec['launched']}",
              len(rec["launched"]) == 1 and rec["launched"][0]["edit"] == "setup:first" and rec["launched"][0]["open_browser"] is False
              and "?mode=setup&first=1#t=" in url)
    ctx.check(f"the line with the URL, got {text!r}", f"Setup is open in your browser: {url}. `halo init --terminal` runs "
              "the terminal setup instead." in text)
    from halo_harness.init_wait import FINAL_LINE
    ctx.check(f"3.3.15.0 R6: then the line that says how both come up, got {text!r}", FINAL_LINE in " ".join(text.split()))
    rc, text, rec, ran = _door_init(["--no-launch"], running=True, pages=0)
    ctx.check(f"a running Studio is reused, got {rec}", rc == 0 and not rec["launched"] and len(rec["opened"]) == 1 and not ran)


@test
def test_init_terminal_and_the_console_flags_run_the_console_setup(ctx: Ctx):
    rc, text, rec, ran = _door_init(["--terminal"])
    ctx.check(f"--terminal: the console setup, no Studio, got {rc} {rec}", rc == 0 and len(ran) == 1 and not rec["opened"])
    rc, text, rec, ran = _door_init(["--step", "team"])
    ctx.check(f"--step team: Setup's Team page, got {rc} {ran}", rc == 0 and not ran and rec["launched"][0]["edit"] == "setup:team")
    for flags in (["--no-live"], ["--team", str(REPO_DIR / "missing-team.json")]):
        rc, text, rec, ran = _door_init(flags)
        ctx.check(f"{flags[0]}: a flag of the console setup runs it, got {ran}", len(ran) == 1 and not rec["launched"])


@test
def test_init_with_no_browser_prints_the_url_and_runs_the_console_setup(ctx: Ctx):
    from tests.helpers.setup_door_stubs import PORT
    rc, text, rec, ran = _door_init([], env={"HALO_NO_BROWSER": "1"})
    ctx.check(f"HALO_NO_BROWSER: Studio started, no browser asked, the console setup ran, got {rc} {rec} {ran}", rc == 0
              and rec["launched"] and not rec["opened"] and len(ran) == 1)
    ctx.check(f"the URL with the port-forward hint, got {text!r}", f"Setup is at http://127.0.0.1:{PORT}/?mode=setup&first=1#t=" in text
              and f"ssh -L {PORT}:127.0.0.1:{PORT} <host>" in text and "The terminal setup runs here instead." in text
              and "at the address above" in text)
    rc, text, rec, ran = _door_init([], env={"SSH_CONNECTION": "192.0.2.10 50000 192.0.2.20 22"})
    ctx.check(f"SSH_CONNECTION: the same, got {ran}", len(ran) == 1 and not rec["opened"] and "this is an SSH session" in text)
    rc, text, rec, ran = _door_init([], browser=False)
    ctx.check(f"webbrowser.open False: the URL and the console setup, got {text!r}", len(ran) == 1 and "no browser took the URL" in text)


@test
def test_init_without_a_terminal_never_opens_studio(ctx: Ctx):
    home = _fresh_home()
    result = _run(["init", "--provider", "openrouter", "--yes", "--no-live", "--no-fixes"], home, stdin="sk-or-fake\n",
                  extra_env={"HALO_NO_BROWSER": "1"})
    ctx.check(f"--provider/--yes: the console flow as before, got {result.returncode} {result.stdout[-300:]!r}",
              result.returncode == 0 and "Setup is open" not in result.stdout and "Setup is at" not in result.stdout)


# ---------------------------------------------------------------------------
# 3.3.3.0 R1: `halo init` waits for Setup's Done, then starts halo here
# (halo_harness/init_wait.py). The getter, the sleeper and the launcher are
# swapped: no test waits a real second, opens a TUI or reaches a Studio.
# ---------------------------------------------------------------------------

_DONE_STATE = {"providers": {"openrouter": {"set": True}, "ollama": {"set": False}}, "model": "or:mock/alpha",
               "team": {"active": "auto", "source": "default"}, "last_check": None}


STUDIO = {"port": 4567, "token": "tok", "pid": 1}  # the running Studio's studio.json (3.3.15.0 R6: the pairing)


def _wait_init(argv, getter, *, env=None, stale=False, answers=False, seen=None, **stubs):
    """`_door_init` with init_wait's getter, sleeper and launcher swapped:
    `(rc, text, rec, launched cwds, GET paths, sleeps)`. `stale`: the door first writes an earlier init's marker.
    3.3.15.0 R6: `answers` is whether Studio's port still answers (a busy Studio is not gone); `seen` (a dict) gets
    the Studio each launch was paired with and the waiting record as each GET saw it."""
    from halo_harness import init_wait
    from halo_harness.studio import init_waiting, setup_door, setup_done
    launched, gets, slept = [], [], []
    seen = {} if seen is None else seen
    saved = (init_wait.http_get, init_wait.sleep, init_wait.launch_halo, setup_door.open_setup, init_wait.studio_answers,
             init_wait.studio_info)
    real_open = setup_door.open_setup

    def get(state_dir, path, timeout=5.0):
        gets.append(path)
        seen.setdefault("records", []).append(init_waiting.waiting(state_dir))
        seen["state_dir"] = state_dir
        return getter(len(gets))

    def open_then_mark(target, **kw):
        real_now = setup_done.now_iso
        setup_done.now_iso = lambda: "2026-01-01T00:00:00.000000+00:00"
        try:
            setup_done.write_done()
        finally:
            setup_done.now_iso = real_now
        return real_open(target, **kw)

    init_wait.http_get, init_wait.sleep = get, slept.append
    init_wait.launch_halo = lambda cwd, studio=None: launched.append(Path(cwd)) or seen.setdefault("paired", []).append(studio) or 7
    init_wait.studio_answers = lambda state_dir: answers
    init_wait.studio_info = lambda state_dir: dict(STUDIO, state_dir=str(state_dir))
    if stale:
        setup_door.open_setup = open_then_mark
    try:
        rc, text, rec, _ran = _door_init(argv, extra_env=env, **stubs)
        if seen.get("state_dir") is not None:
            seen["after"] = init_waiting.waiting(seen["state_dir"])
    finally:
        (init_wait.http_get, init_wait.sleep, init_wait.launch_halo, setup_door.open_setup, init_wait.studio_answers,
         init_wait.studio_info) = saved
    return rc, text, rec, launched, gets, slept


def _done_after(n: int):
    """A getter: Studio answers, and its state says Done from the n-th GET on."""
    from halo_harness.studio.setup_done import now_iso
    return lambda i: dict(_DONE_STATE, done_at=now_iso() if i >= n else None)


@test
def test_init_waits_for_done_then_starts_halo_here(ctx: Ctx):
    seen: dict = {}
    rc, text, rec, launched, gets, slept = _wait_init([], _done_after(3), seen=seen)
    url = rec["opened"][0] if rec["opened"] else ""
    one = " ".join(text.split())  # the console wraps long lines
    ctx.check(f"ONE door line: this terminal starts halo on Done (3.3.15.0 R6), got {text!r}", text.count(url) == 1
              and f"Setup is open in your browser: {url}. This terminal starts halo when you press Done there (Ctrl+C: stop "
              "here; `halo` later starts it)." in one and "runs the terminal setup instead" not in text)
    ctx.check(f"polled GET setup/done-at (3.6.0.0 R14: not the whole setup/state) until Done, a poll_s apart, then read "
              f"setup/state once for the Summary, got {gets} {slept}",
              gets == ["setup/done-at"] * 3 + ["setup/state"] and slept == [1.0, 1.0])
    records = seen.get("records") or []
    ctx.check(f"while it waits, setup-wait.json names this process (Studio's Done reads it), got {records[:1]}",
              len(records) >= 3 and all(r and r.get("pid") == os.getpid() for r in records[:3]))
    ctx.check(f"the record goes once the wait ends, got {seen.get('after')}", seen.get("after") is None)
    ctx.check(f"the Summary's four lines, got {text!r}", "Provider: openrouter\n" in text and "Default model: or:mock/alpha\n" in text
              and "Lineup: auto (default)\n" in text and "Last check: not run\n" in text)
    ctx.check(f"the starting line names the Studio it pairs with, got {text!r}",
              "Setup is done: halo starts here, paired with Studio at http://127.0.0.1:4567/" in one)
    ctx.check(f"halo launched once, in the directory init ran from, with the running Studio, its exit code returned, got "
              f"{launched} {seen.get('paired')} {rc}", launched == [Path.cwd()] and rc == 7 and len(seen.get("paired") or []) == 1
              and seen["paired"][0]["port"] == 4567 and seen["paired"][0]["state_dir"] == str(seen.get("state_dir")))


@test
def test_init_waits_out_a_busy_studio(ctx: Ctx):
    """3.3.15.0 R6: GETs failing while Studio's port still answers (a long check, the guided first run) are not "gone":
    init keeps waiting and starts halo on Done (on Kali the wait gave up after 10 s of a busy Studio)."""
    from halo_harness.studio.setup_done import now_iso
    rc, text, rec, launched, gets, slept = _wait_init([], lambda i: dict(_DONE_STATE, done_at=now_iso()) if i > 15 else None,
                                                      answers=True)
    ctx.check(f"15 failed GETs with the port answering, then Done: launched, got {rc} {len(gets)} {launched} {text[-200:]!r}",
              rc == 7 and len(gets) == 17 and launched == [Path.cwd()] and "Studio closed" not in text)  # 16 polls + the Summary's read


@test
def test_init_wait_ctrl_c_and_studio_gone_launch_nothing(ctx: Ctx):
    def interrupted(_i):
        raise KeyboardInterrupt
    seen: dict = {}
    rc, text, rec, launched, gets, slept = _wait_init([], interrupted, seen=seen)
    ctx.check(f"Ctrl+C: the line and 0, no launch, got {rc} {launched} {text!r}", rc == 0 and not launched
              and "Stopped here: Studio closes with this command; `halo init` opens Setup again." in text)
    ctx.check(f"Ctrl+C: the waiting record goes too, got {seen.get('after')}", seen.get("after") is None and seen.get("records"))
    rc, text, rec, launched, gets, slept = _wait_init([], lambda _i: None)
    ctx.check(f"Studio gone for 10 s: the line and 0, no launch, got {rc} {launched} {len(gets)} {text!r}", rc == 0 and not launched
              and len(gets) == 10 and "Studio closed; run `halo` when you are ready." in text)
    rc, text, rec, launched, gets, slept = _wait_init([], lambda _i: None, env={"HALO_INIT_POLL_S": "0.5"})
    ctx.check(f"HALO_INIT_POLL_S: 0.5 s polls, gone after 20, got {len(gets)} {slept[:2]}", len(gets) == 20 and slept[:2] == [0.5, 0.5])


@test
def test_init_summary_reads_this_home_when_setup_state_does_not_answer(ctx: Ctx):
    """fx studio pass 2: the done-at poll's answer ({done_at} alone, 3.6.0.0 R14) is not the setup state. When the one
    setup/state read after Done fails (a slow Studio, a Studio closing), the Summary reads this home's own state; it
    said 'Provider: not set / Default model: not set' with a provider and a model set."""
    from halo_harness import init_wait as W
    from halo_harness.studio.setup_done import now_iso
    saved = (W.http_get, W.sleep, W.launch_halo, W.studio_info, W._local_state)
    said: list = []
    W.http_get = lambda _sd, path, timeout=5.0: {"done_at": now_iso()} if path == "setup/done-at" else None
    W.sleep = lambda _s: None
    W.launch_halo = lambda _cwd, _studio=None: 0
    W.studio_info = lambda _sd: None
    W._local_state = lambda _cwd, _sd: dict(_DONE_STATE)
    try:
        with tempfile.TemporaryDirectory() as d:
            rc = W.run(said.append, cwd=Path(d), state_dir=Path(d), poll_s=0.0, deadline=5)
    finally:
        W.http_get, W.sleep, W.launch_halo, W.studio_info, W._local_state = saved
    ctx.check(f"the Summary is this home's state, got {rc} {said}", rc == 0 and "Provider: openrouter" in said
              and "Default model: or:mock/alpha" in said and "Lineup: auto (default)" in said)


@test
def test_init_no_launch_returns_at_once(ctx: Ctx):
    for argv, env in ((["--no-launch"], None), ([], {"HALO_INIT_NO_LAUNCH": "1"})):
        rc, text, rec, launched, gets, slept = _wait_init(argv, _done_after(1), env=env)
        ctx.check(f"{argv or env}: the old one line, no wait, no launch, got {rc} {gets} {launched} {text!r}", rc == 0 and not gets
                  and not launched and "`halo init --terminal` runs the terminal setup instead." in text and "Press Done" not in text)
    from halo_harness.init_cli import _build_parser
    help_text = " ".join(_build_parser().format_help().split())
    ctx.check(f"--no-launch is in halo init --help, got {help_text[-400:]!r}", "--no-launch open Setup and serve it from here, but start no halo after its Done" in help_text)


@test
def test_init_wait_ignores_a_stale_marker_and_reads_a_fresh_one(ctx: Ctx):
    from halo_harness.studio import setup_done
    states = []

    def stale_then_gone(i):
        states.append(i)
        return dict(_DONE_STATE, done_at="2026-01-01T00:00:00.000000+00:00") if i < 3 else None
    rc, text, rec, launched, gets, slept = _wait_init([], stale_then_gone, stale=True)
    ctx.check(f"an earlier init's marker and done_at do not count: gone, no launch, got {rc} {launched} {text!r}",
              rc == 0 and not launched and "Studio closed" in text)

    def marker_on_third(i):
        if i == 3:
            setup_done.write_done()
        return None  # the GET fails: the marker file is the fallback
    rc, text, rec, launched, gets, slept = _wait_init([], marker_on_third)
    ctx.check(f"the GET failing, a fresh marker still counts: launched, got {rc} {launched} {len(gets)}", launched == [Path.cwd()]
              and rc == 7 and "Lineup:" in text)


@test
def test_init_wait_sees_done_after_the_clock_steps_back(ctx: Ctx):
    """fx studio pass 2: a Done counts because it is new since the wait began, not because its time is later. The
    wall clock stepped back during Setup (NTP after a VM restore or a wake) gave the Done an earlier `at` than the
    wait's start; init waited for ever while the person thought Setup had finished."""
    from datetime import datetime, timedelta, timezone
    from halo_harness.studio import setup_done
    back = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat(timespec="microseconds")
    rc, text, rec, launched, gets, slept = _wait_init([], lambda i: dict(_DONE_STATE, done_at=back) if i < 15 else None)
    ctx.check(f"a done_at 30 s before the wait began, new since it began: launched, got {rc} {launched} {gets}",
              launched == [Path.cwd()] and rc == 7 and gets.count("setup/done-at") == 1)

    def marker_back(i):
        if i == 3:
            real_now = setup_done.now_iso
            setup_done.now_iso = lambda: back
            try:
                setup_done.write_done()
            finally:
                setup_done.now_iso = real_now
        return None  # the GET fails: the marker file is the fallback
    rc, text, rec, launched, gets, slept = _wait_init([], marker_back)
    ctx.check(f"a marker written with the stepped-back clock counts too: launched, got {rc} {launched} {len(gets)}",
              launched == [Path.cwd()] and rc == 7)


@test
def test_launch_bare_is_what_bare_halo_runs(ctx: Ctx):
    from halo_harness import cli
    from halo_harness.tui import launch as tui_launch
    from halo_harness.update import RESTART_EXIT_CODE
    got, saved = [], (tui_launch.run_tui, cli._apply_update_and_relaunch)
    try:
        tui_launch.run_tui = lambda args: got.append(args) or 0
        cli._apply_update_and_relaunch = lambda argv: 99
        rc = cli.launch_bare(Path.cwd())
        default = cli._build_parser().parse_intermixed_args([])
        ctx.check(f"main([])'s default args, no --cwd for this directory, got {rc} {got}", rc == 0 and len(got) == 1
                  and vars(got[0]) == vars(default) and got[0].cwd is None)
        other = _fresh_home()
        cli.launch_bare(other)
        ctx.check(f"another directory rides in --cwd, got {got[-1].cwd!r}", Path(got[-1].cwd).resolve() == other.resolve())
        tui_launch.run_tui = lambda args: RESTART_EXIT_CODE
        ctx.check("/update's restart code goes to the detached updater, as bare halo's does", cli.launch_bare(None) == 99)
    finally:
        tui_launch.run_tui, cli._apply_update_and_relaunch = saved


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
