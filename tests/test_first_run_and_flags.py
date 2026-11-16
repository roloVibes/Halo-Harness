"""tests.test_first_run_and_flags -- fix pass 2, sessions-storage batch 2: what a person types first gets one plain
line that says what to do, never silence or a dead end.

* No provider set up: `halo -p hello` ended on `OpenRouter not configured` (twice on one screen) and the TUI's first
  screen said nothing of setup. The sentence now names the key to set and `halo init`; the TUI says it at start.
* `halo config set` took any key and any value: a misspelled key or an invalid permission mode was saved (rc 0) and
  doctor showed `[OK] Permission mode: bogus`; a bad model made every later `-p` blame a `--model` never given.
* `--settings`, `--mcp-config`, `--agents` naming a missing file or bad JSON, and `--cwd` naming no folder, were
  ignored and the run went ahead.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()

_TEMP_DIRS: list = []


def _tmp(prefix: str) -> str:
    """A scratch folder removed when the module ends."""
    d = tempfile.mkdtemp(prefix=prefix)
    if not _TEMP_DIRS:
        import atexit
        import shutil
        atexit.register(lambda: [shutil.rmtree(p, ignore_errors=True) for p in _TEMP_DIRS])
    _TEMP_DIRS.append(d)
    return d

_KEY_VARS = ("OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "EXPLABS_API_KEY", "HF_TOKEN",
             "DATABRICKS_HOST", "DATABRICKS_TOKEN", "DATABRICKS_CONFIG_PROFILE", "HALO_MODEL", "ANTHROPIC_MODEL")


def _run_halo(home: Path, *args: str, keys: "dict | None" = None) -> "tuple[int, str]":
    """The real `python -m halo_harness <args>` in a scratch home with no provider key (no network, no updater)."""
    import subprocess
    env = {k: v for k, v in os.environ.items() if k not in _KEY_VARS and not k.startswith("BRIDGE_")}
    env.update(BRIDGE_TEST_HOME=str(home), HOME=str(home), USERPROFILE=str(home), OLLAMA_HOST="http://127.0.0.1:9",
               HALO_NO_UPDATER="1", PYTHONIOENCODING="utf-8", PYTHONPATH=str(Path(__file__).resolve().parent.parent))
    env.update(keys or {})
    proj = home / "proj"
    proj.mkdir(exist_ok=True)
    p = subprocess.run([sys.executable, "-m", "halo_harness", *args], cwd=str(proj), env=env, input="",
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


@contextlib.contextmanager
def _scratch_home():
    saved = os.environ.get("BRIDGE_TEST_HOME")
    home = Path(_tmp("first-run-home-"))
    os.environ["BRIDGE_TEST_HOME"] = str(home)
    try:
        yield home
    finally:
        if saved is None:
            os.environ.pop("BRIDGE_TEST_HOME", None)
        else:
            os.environ["BRIDGE_TEST_HOME"] = saved


# ---- no provider set up ------------------------------------------------------------------------------------------

@test
def test_a_first_prompt_with_no_provider_says_what_to_set(ctx: Ctx):
    home = Path(_tmp("first-run-p-"))
    rc, out = _run_halo(home, "-p", "hello")
    ctx.check(f"the run fails (rc 1), got {rc}", rc == 1)
    ctx.check(f"the line names the key to set, got {out!r}", "OPENROUTER_API_KEY" in out)
    ctx.check(f"and `halo init`, got {out!r}", "halo init" in out)


@test
def test_every_not_configured_sentence_names_its_fix(ctx: Ctx):
    from halo_harness.agent.subagent import _child_credential_message
    from halo_harness.controller import _not_configured_message
    from halo_harness.providers.stream import not_configured_message
    for provider, word in (("openrouter", "OPENROUTER_API_KEY"), ("anthropic", "ANTHROPIC_API_KEY"),
                           ("databricks", "halo init --provider databricks"), ("ollama", "OLLAMA_HOST"),
                           ("copilot", "halo copilot signin")):
        ref = types.SimpleNamespace(provider=provider, model="x")
        for name, fn in (("controller", _not_configured_message), ("sub-agent", _child_credential_message)):
            line = fn(ref)
            ctx.check(f"{name} {provider}: names {word!r}, got {line!r}", word in line)
            if provider != "openrouter":
                ctx.check(f"{name} {provider}: never sends the person to OpenRouter, got {line!r}",
                          "OPENROUTER" not in line and "OpenRouter" not in line)
    ctx.check("the phase-1 sentence is the same one",
              not_configured_message("OpenRouter") == _not_configured_message(types.SimpleNamespace(provider="openrouter")))


@test
def test_a_print_mode_error_shows_once_on_one_screen(ctx: Ctx):
    from halo_harness import events as ev
    from halo_harness.output import PrintModeSink

    class Screen(io.StringIO):
        def isatty(self):
            return True
    screen = Screen()
    sink = PrintModeSink(output_format="text", stream=screen)
    with contextlib.redirect_stderr(screen):
        code = sink.consume(iter([ev.error("OpenRouter not configured -- set OPENROUTER_API_KEY",
                                           err_type="not_configured")]))
    ctx.check(f"rc 1, got {code}", code == 1)
    n = screen.getvalue().count("OpenRouter not configured")
    ctx.check(f"stdout and stderr are one terminal: the sentence once, got {n}: {screen.getvalue()!r}", n == 1)
    piped, err = io.StringIO(), io.StringIO()
    sink = PrintModeSink(output_format="text", stream=piped)
    with contextlib.redirect_stderr(err):
        sink.consume(iter([ev.error("OpenRouter not configured", err_type="not_configured")]))
    ctx.check("piped: still on stdout and on stderr (a script reads either)",
              "OpenRouter not configured" in piped.getvalue() and "OpenRouter not configured" in err.getvalue())


@test
def test_the_session_start_says_when_no_provider_is_set_up(ctx: Ctx):
    from halo_harness.controller import setup_hint_line
    bare = types.SimpleNamespace(creds=None, model_ref=types.SimpleNamespace(provider="openrouter", model="m"))
    line = setup_hint_line(bare) or ""
    ctx.check(f"a session with no credentials names the setup, got {line!r}",
              "halo init" in line and "OPENROUTER_API_KEY" in line)
    ready = types.SimpleNamespace(creds=object(), model_ref=types.SimpleNamespace(provider="openrouter", model="m"))
    ctx.check("a session that has its credentials gets no line", setup_hint_line(ready) is None)
    ctx.check("no session, no line", setup_hint_line(None) is None)
    cp = types.SimpleNamespace(creds=None, model_ref=types.SimpleNamespace(provider="copilot", model="work",
                                                                           raw="cp:work"))
    line = setup_hint_line(cp) or ""
    ctx.check(f"a Copilot session not signed in is told to sign in, not to set an OpenRouter key, got {line!r}",
              "halo copilot signin" in line and "OPENROUTER" not in line)


@test
def test_the_tui_shows_the_setup_line_on_its_first_screen(ctx: Ctx):
    import asyncio
    from halo_harness.testing.fake_controller import FakeController
    from halo_harness.tui.app import BridgeApp
    with _scratch_home():
        fake = FakeController()
        fake.session = types.SimpleNamespace(creds=None,
                                             model_ref=types.SimpleNamespace(provider="openrouter", model="m", raw="or:m"))
        app = BridgeApp(fake, cwd=str(Path(_tmp("first-run-tui-"))))
        got: dict = {}

        async def body():
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.pause(0.5)
                got["log"] = "\n".join(app.transcript.plain_log)
        asyncio.run(body())
    log = got.get("log", "")
    ctx.check(f"the first screen names the setup, got {log[-400:]!r}",
              "No provider is set up for or:m" in log and "halo init" in log)


# ---- halo config set ---------------------------------------------------------------------------------------------

@test
def test_config_set_refuses_an_unknown_key_and_a_value_outside_its_choices(ctx: Ctx):
    from halo_harness.config_cli import cmd_config
    with _scratch_home() as home:
        from halo_harness.config.paths import bridge_home
        cfg = bridge_home() / "config.json"
        for argv, word in ((["set", "permission_mode", "bogus"], "plan"),
                           (["set", "permision_mode", "plan"], "permission_mode"),
                           (["set", "model", "nosuch:model"], "nosuch:model")):
            err = io.StringIO()
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                rc = cmd_config(argv)
            ctx.check(f"{argv}: rc 2, got {rc}", rc == 2)
            ctx.check(f"{argv}: one line naming {word!r}, got {err.getvalue()!r}", word in err.getvalue())
            saved = json.loads(cfg.read_text(encoding="utf-8")) if cfg.exists() else {}
            ctx.check(f"{argv}: nothing saved, got {saved!r}", argv[1] not in saved)
        for argv in (["set", "permission_mode", "plan"], ["set", "studio.hover_cards", "false"],
                     ["set", "model", "ol:qwen3:8b"]):
            with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                rc = cmd_config(argv)
            ctx.check(f"{argv}: a valid key and value still saves (rc 0), got {rc}", rc == 0)
        # repair: model settings that take an Ollama model's own name (or "none"), not a routed ref, still save
        # (docs/CONFIG.md tells people to run the first one)
        from halo_harness.config_cli import _set_problem
        for key, value in (("embeddings.model", "nomic-embed-text"), ("ollama.steward.model", "none"),
                           ("ollama.steward.model", "qwen3:4b"), ("host.steward.model", "qwen3:4b")):
            with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                rc = cmd_config(["set", key, value])
            ctx.check(f"{key} {value}: saved (rc 0), got {rc}: {_set_problem(key, value)!r}", rc == 0)
            saved = json.loads(cfg.read_text(encoding="utf-8"))
            for part in key.split("."):
                saved = saved.get(part) if isinstance(saved, dict) else None
            ctx.check(f"{key}: stored as typed, got {saved!r}", saved == value)


@test
def test_a_bad_saved_model_is_not_blamed_on_a_model_flag(ctx: Ctx):
    home = Path(_tmp("first-run-model-"))
    (home / ".halo").mkdir()
    (home / ".halo" / "config.json").write_text(json.dumps({"model": "nosuch:model"}), encoding="utf-8")
    rc, out = _run_halo(home, "-p", "hello")
    ctx.check(f"rc 2, got {rc}", rc == 2)
    ctx.check(f"no --model blamed, got {out!r}", "--model" not in out)
    ctx.check(f"names where the model came from, got {out!r}", "config.json" in out)


# ---- flags that name a file ----------------------------------------------------------------------------------------

@test
def test_a_flag_naming_a_missing_file_or_bad_json_stops_the_run(ctx: Ctx):
    home = Path(_tmp("first-run-flags-"))
    missing_dir = str(home / "nosuch" / "dir")
    for flag, value in (("--settings", "nosuch.json"), ("--mcp-config", "nosuch.json"), ("--mcp-config", "{bad json"),
                        ("--agents", "{bad json"), ("--agents", "nosuch-agents.json"), ("--cwd", missing_dir)):
        rc, out = _run_halo(home, flag, value, "-p", "hi", "--model", "ol:qwen3:8b")
        ctx.check(f"{flag} {value}: rc 2, got {rc}", rc == 2)
        ctx.check(f"{flag} {value}: one line naming the flag, got {out[-300:]!r}", f"halo: {flag}" in out)
    (home / "proj" / "good.json").write_text('{"mcpServers": {}}', encoding="utf-8")
    rc, out = _run_halo(home, "--mcp-config", "good.json", "--settings", '{"env": {}}', "-p", "hi",
                        "--model", "ol:qwen3:8b")
    ctx.check(f"good flags still reach the model call, got rc {rc}: {out[-200:]!r}", "halo: --" not in out)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
