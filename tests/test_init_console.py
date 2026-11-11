"""tests.test_init_console -- Halo 3.4.0.0 B2: the terminal wizard shrank to a console fallback.

1. `halo init --terminal` with scripted stdin in a scratch home: a provider from a numbered list, its key stored by
   its variable's NAME in Halo's env file (the writer Setup uses; no key value in config.json), a default model picked
   from a short numbered list or typed as a ref, the permission mode, doctor when asked, then where the rest is
   (Studio's Setup) and the start line.
2. The no-browser fallback: on a terminal where no browser opens, `halo init` prints the URL with the port-forward
   line, then runs the same console setup (no Textual screen) and ends on "at the address above".
3. The legacy role table still becomes the "migrated" lineup: at session start (tui/launch.py) and in the console
   setup, once (legacy_roles.migrate_on_start).
Run: python -m tests.test_init_console
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
SCRUB = ("OPENROUTER_", "DATABRICKS_", "ANTHROPIC_", "BRIDGE_", "HALO_", "ROLO_CLAUDE_", "TYPESAFE_", "OPENAI_", "HF_",
         "EXPLABS_", "OLLAMA_")
KEY = "sk-or-v1-test-only-not-a-real-key"


def _home() -> "tuple[Path, Path]":
    home = Path(tempfile.mkdtemp(prefix="b2-init-"))
    state = home / ".halo"
    state.mkdir()
    (state / "models.json").write_text(json.dumps({"vendor/alpha": {"context_length": 8000, "pricing": {}},
                                                   "vendor/beta": {"context_length": 8000, "pricing": {}}}),
                                       encoding="utf-8")
    return home, state


def _env(home: Path, **extra) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith(SCRUB)}
    env.update(BRIDGE_TEST_HOME=str(home), BRIDGE_TEST_NO_BACKGROUND_NET="1", PYTHONPATH=str(REPO),
               HALO_ENV_FILE=str(home / "env"), PYTHONIOENCODING="utf-8", HALO_INIT_NO_LAUNCH="1", **extra)
    return env


def _init(home: Path, argv: list, stdin: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "halo_harness", "init"] + argv, input=stdin, text=True,
                          capture_output=True, env=_env(home), cwd=str(home), timeout=180, encoding="utf-8")


@test
def test_terminal_asks_the_essentials_line_by_line(ctx: Ctx):
    home, state = _home()
    # provider 2 (openrouter), its key, doctor yes, the model typed as a ref, no second provider, permission 1 (auto)
    script = "\n".join(["2", KEY, "y", "or:vendor/beta", "n", "1"]) + "\n"
    r = _init(home, ["--terminal", "--no-live", "--no-fixes"], script)
    out = r.stdout + r.stderr
    ctx.check(f"exit 0, got {r.returncode}: {out[-800:]!r}", r.returncode == 0)
    ctx.check("a numbered provider list", "1. databricks" in out and "2. openrouter" in out)
    env_text = (home / "env").read_text(encoding="utf-8") if (home / "env").exists() else ""
    ctx.check("the key landed in the env file under its NAME", f"OPENROUTER_API_KEY={KEY}" in env_text)
    cfg_text = (state / "config.json").read_text(encoding="utf-8")
    cfg = json.loads(cfg_text)
    ctx.check("no key value in config.json", KEY not in cfg_text)
    ctx.check(f"the typed model is the default, got {cfg.get('model')!r}", cfg.get("model") == "or:vendor/beta")
    ctx.check(f"the permission mode, got {cfg.get('permission_mode')!r}", cfg.get("permission_mode") == "auto")
    ctx.check("doctor ran when asked", "Sessions:" in out)
    ctx.check("a short numbered model list", "1. or:vendor/alpha" in out.replace("  ", " ") or "or:vendor/alpha" in out)
    ctx.check("it ends on where the rest is (Studio's Setup)", "is in Studio's Setup" in out and "halo studio --mode setup" in out)
    ctx.check("no Textual screen", "\x1b[?1049h" not in r.stdout)


@test
def test_terminal_can_skip_doctor_and_pick_a_model_by_number(ctx: Ctx):
    home, state = _home()
    r = _init(home, ["--terminal", "--no-live", "--no-fixes"], "\n".join(["2", KEY, "n", "1", "n", "3"]) + "\n")
    out = r.stdout + r.stderr
    cfg = json.loads((state / "config.json").read_text(encoding="utf-8"))
    ctx.check(f"exit 0, doctor skipped, got {r.returncode} {out[-400:]!r}", r.returncode == 0 and "doctor: skipped" in out
              and "Sessions:" not in out)
    ctx.check(f"model 1 of the list, mode 3, got {cfg.get('model')} {cfg.get('permission_mode')}",
              cfg.get("model") == "or:vendor/alpha" and cfg.get("permission_mode") not in (None, "", "auto"))


@test
def test_no_browser_prints_the_url_then_runs_the_console_setup(ctx: Ctx):
    import contextlib
    import io
    from halo_harness.init_cli import cmd_init
    from tests.helpers.setup_door_stubs import door_stubs, fake_tty
    home, state = _home()
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "HALO_ENV_FILE", "HALO_INIT_NO_LAUNCH", "OPENROUTER_API_KEY")}
    os.environ.update(BRIDGE_TEST_HOME=str(home), HALO_ENV_FILE=str(home / "env"), HALO_INIT_NO_LAUNCH="1")
    os.environ.pop("OPENROUTER_API_KEY", None)
    old_stdin = sys.stdin
    try:  # no provider this time (4: Done), so nothing reaches the network; then the permission mode (1)
        with door_stubs(env={"HALO_NO_BROWSER": "1"}) as rec, fake_tty() as out, contextlib.redirect_stderr(io.StringIO()):
            sys.stdin = io.StringIO("4\n1\n")
            sys.stdin.isatty = lambda: True  # type: ignore[method-assign]
            rc = cmd_init(["--no-fixes"])
    finally:
        sys.stdin = old_stdin
        for k, v in saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
    import re
    text = re.sub(r"\x1b\[[0-9;]*m", "", out.getvalue())
    ctx.check(f"the URL with the port-forward line first, got {text[:600]!r}", "Setup is at http://127.0.0.1:" in text
              and "Over SSH: ssh -L" in text and not rec["opened"])
    ctx.check("then the console setup, no wizard", "The terminal setup runs here instead." in text and "2. openrouter" in text)
    ctx.check(f"it asks the permission mode and ends on the address above, rc 0, got {rc} {text[-500:]!r}", rc == 0
              and "Default permission mode: auto" in text and "at the address above" in text)


@test
def test_the_legacy_role_table_still_migrates_once(ctx: Ctx):
    home, state = _home()
    (state / "config.json").write_text(json.dumps({"model": "or:vendor/alpha", "roles": {"coder": "or:vendor/alpha", "reviewer": "or:vendor/beta"}}),
                                       encoding="utf-8")
    script = "\n".join(["2", KEY, "n", "", "n", "1"]) + "\n"
    r = _init(home, ["--terminal", "--no-live", "--no-fixes"], script)
    out = r.stdout + r.stderr
    ctx.check(f"the console setup says it once, got {out[:500]!r}", "is now the lineup 'migrated'" in out)
    lineups = list(state.rglob("migrated*.y*ml"))
    ctx.check(f"the lineup file is written, got {lineups}", bool(lineups))
    r2 = _init(home, ["--terminal", "--no-live", "--no-fixes"], script)
    ctx.check("a second run is a no-op", "is now the lineup" not in (r2.stdout + r2.stderr))
    src = (REPO / "halo_harness" / "tui" / "launch.py").read_text(encoding="utf-8")
    ctx.check("an interactive session start runs it too (tui/launch.py)", "migrate_on_start(cwd)" in src)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="init console tests"))
