"""tests.test_fx_jb15_init_input -- the terminal setup (`halo init --terminal`) on a real Mac (fx jb15).

1. An ended input (Ctrl+D, a closed terminal, a pipe that ran out) was taken as "the default" at every prompt: the
   setup walked on through every step and wrote a configuration nobody chose. It now stops there, like Ctrl+C: one
   line, a non-zero exit, nothing written after that point. A default is taken only for an empty line the person sent
   (Enter); letters that are no answer are not the default either ('q' at the provider pick stops the setup).
2. macOS ran the step titled "Linux fixes:": it offered to download a static rg into ~/.local/bin and to add a PATH line
   to ~/.profile, a file the Mac's zsh does not read. On macOS the step offers no download and edits no file.
Run: python -m tests.test_fx_jb15_init_input
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
SCRUB = ("OPENROUTER_", "DATABRICKS_", "ANTHROPIC_", "BRIDGE_", "HALO_", "ROLO_CLAUDE_", "TYPESAFE_", "OPENAI_", "HF_",
         "EXPLABS_", "OLLAMA_")
KEY = "sk-or-v1-test-only-not-a-real-key"
ARGV = ["--terminal", "--no-live", "--no-fixes"]


def _home() -> "tuple[Path, Path]":
    home = Path(tempfile.mkdtemp(prefix="jb15-init-"))
    state = home / ".halo"
    state.mkdir()
    (state / "models.json").write_text(json.dumps({"vendor/alpha": {"context_length": 8000, "pricing": {}}}),
                                       encoding="utf-8")
    return home, state


def _env(home: Path) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith(SCRUB)}
    env.update(BRIDGE_TEST_HOME=str(home), BRIDGE_TEST_NO_BACKGROUND_NET="1", PYTHONPATH=str(REPO),
               HALO_ENV_FILE=str(home / "env"), PYTHONIOENCODING="utf-8", HALO_INIT_NO_LAUNCH="1",
               HALO_NO_UPDATER="1", OLLAMA_HOST="http://127.0.0.1:9")
    return env


def _init(home: Path, stdin: str, argv=ARGV) -> "tuple[subprocess.CompletedProcess, float]":
    t0 = time.monotonic()
    r = subprocess.run([sys.executable, "-m", "halo_harness", "init"] + list(argv), input=stdin, text=True,
                       capture_output=True, env=_env(home), cwd=str(home), timeout=120, encoding="utf-8")
    return r, time.monotonic() - t0


def _config(state: Path) -> dict:
    p = state / "config.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _stopped(r) -> bool:
    return r.returncode not in (0, None) and "the input ended" in r.stderr and "nothing more was written" in r.stderr \
        and "Traceback" not in r.stdout + r.stderr


@test
def test_an_input_that_ends_at_once_stops_the_setup_and_writes_nothing(ctx: Ctx):
    home, state = _home()
    r, took = _init(home, "")
    out = r.stdout + r.stderr
    ctx.check(f"a non-zero exit and the one line, got {r.returncode} {out[-600:]!r}", _stopped(r))
    ctx.check(f"it never walked on to the key, the doctor or the permission mode, got {r.stdout[-600:]!r}",
              "OpenRouter key not found" not in r.stdout and "Checks:" not in r.stdout
              and "Default permission mode" not in r.stdout)
    ctx.check(f"nothing was written: config {_config(state)}", "model" not in _config(state)
              and "permission_mode" not in _config(state) and not (home / "env").exists())
    ctx.check(f"it ended at once, took {took:.1f} s", took < 30)


@test
def test_an_input_that_ends_after_the_first_answer_stops_at_the_next_prompt(ctx: Ctx):
    home, state = _home()
    r, _took = _init(home, "2\n")  # openrouter, then the input ends at the key prompt
    out = r.stdout + r.stderr
    ctx.check(f"stopped at the key prompt, got {r.returncode} {out[-600:]!r}", _stopped(r))
    ctx.check(f"no key, no model, no permission mode was written, got {_config(state)}",
              not (home / "env").exists() and "model" not in _config(state) and "permission_mode" not in _config(state))
    ctx.check("no doctor ran", "Checks:" not in r.stdout and "Sessions:" not in r.stdout)


@test
def test_an_input_that_ends_at_a_yes_no_question_is_not_its_default(ctx: Ctx):
    home, state = _home()
    r, _took = _init(home, f"2\n{KEY}\n")  # the key is given; the input ends at "Run halo doctor now?" (default yes)
    out = r.stdout + r.stderr
    ctx.check(f"stopped at the doctor question, got {r.returncode} {out[-600:]!r}", _stopped(r))
    ctx.check("the doctor did not run", "Sessions:" not in r.stdout)
    ctx.check(f"no model and no permission mode were written after it, got {_config(state)}",
              "permission_mode" not in _config(state) and "Default permission mode" not in r.stdout)


@test
def test_an_input_that_ends_at_the_permission_mode_writes_no_mode(ctx: Ctx):
    home, state = _home()
    r, _took = _init(home, f"2\n{KEY}\nn\n\nn\n")  # all answered up to the permission mode; the input ends there
    out = r.stdout + r.stderr
    ctx.check(f"stopped at the permission mode, got {r.returncode} {out[-600:]!r}", _stopped(r))
    ctx.check(f"no permission mode was written, got {_config(state)}", "permission_mode" not in _config(state))


@test
def test_letters_are_not_the_default_and_q_stops_at_the_provider_pick(ctx: Ctx):
    home, state = _home()
    r, _took = _init(home, "x\n5\n\n")  # 'x': said what can be typed, asked again; 5 = Done; Enter = auto
    out = r.stdout + r.stderr
    ctx.check(f"'x' was not taken as the default: asked again, then Done, exit 0, got {r.returncode} {out[-800:]!r}",
              r.returncode == 0 and "OpenRouter key not found" not in r.stdout and "a number from 1 to" in r.stdout)
    ctx.check(f"Enter took the permission default, got {_config(state)}", _config(state).get("permission_mode") == "auto")
    home, state = _home()
    r, _took = _init(home, "q\n")
    out = r.stdout + r.stderr
    ctx.check(f"'q' stops the setup, got {r.returncode} {out[-600:]!r}", r.returncode not in (0, None)
              and "halo init: stopped" in r.stderr and "OpenRouter key not found" not in r.stdout)
    ctx.check(f"nothing written after 'q', got {_config(state)}", "permission_mode" not in _config(state))


@test
def test_a_run_that_does_not_ask_still_reads_an_ended_input_as_no_value(ctx: Ctx):
    """--yes over a pipe (a script, CI): an ended input is "no key entered", as it always was; never a stop."""
    home, state = _home()
    r, _took = _init(home, "", argv=["--provider", "openrouter", "--yes", "--no-live", "--no-fixes"])
    out = r.stdout + r.stderr
    ctx.check(f"exit 0 and the no-key line, got {r.returncode} {out[-600:]!r}", r.returncode == 0
              and "no key entered" in out and "the input ended" not in out)


@test
def test_ctrl_d_at_the_provider_pick_on_a_terminal_stops_the_setup(ctx: Ctx):
    if os.name == "nt":
        raise SkipTest("a pseudo-terminal is POSIX only (the pipe tests above run here)")
    import pty
    import select
    home, state = _home()
    master, slave = pty.openpty()
    proc = subprocess.Popen([sys.executable, "-m", "halo_harness", "init"] + ARGV, stdin=slave, stdout=slave,
                            stderr=slave, env=dict(_env(home), TERM="dumb"), cwd=str(home), start_new_session=True)
    os.close(slave)
    buf, sent, t0 = b"", False, time.monotonic()
    try:
        while time.monotonic() - t0 < 60:
            ready, _w, _x = select.select([master], [], [], 0.2)
            if ready:
                try:
                    chunk = os.read(master, 4096)
                except OSError:
                    break
                if not chunk:
                    break
                buf += chunk
            if not sent and b"choose [1-" in buf:
                os.write(master, b"\x04")
                sent, t_sent = True, time.monotonic()
            if proc.poll() is not None and not ready:
                break
        rc = proc.wait(timeout=10)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=10)
        os.close(master)
    text = buf.decode("utf-8", "replace")
    ctx.check(f"Ctrl+D was sent at the provider pick, got {text[-400:]!r}", sent)
    ctx.check(f"a non-zero exit and the one line, got {rc} {text[-600:]!r}", rc != 0 and "the input ended" in text
              and "Traceback" not in text)
    ctx.check(f"it ended within 2 s of the Ctrl+D, took {time.monotonic() - t_sent:.1f} s",
              time.monotonic() - t_sent < 12)
    ctx.check(f"nothing written, got {_config(state)}", "permission_mode" not in _config(state)
              and "Default permission mode" not in text)


# -- 2. the platform step ---------------------------------------------------------------------------------------------

def _fixes_step(platform: str, *, rg: "str | None", path: str) -> "tuple[str, dict]":
    import io
    from rich.console import Console
    from halo_harness import init_cli, linux_fixes
    rec = {"confirm": [], "install": 0, "rc": 0, "net": 0}

    def confirm(_args, _console, question, *, default):
        rec["confirm"].append(question)
        return True

    def install(dest):
        rec["install"] += 1
        return False, "stubbed"

    def rc_line(**_k):
        rec["rc"] += 1
        return True, Path("/stub/.profile")

    buf = io.StringIO()
    console = Console(file=buf, width=200, color_system=None)
    args = argparse.Namespace(no_fixes=False, yes=False, terminal=True)
    which = (lambda name: rg if name == "rg" else None)
    with mock.patch.object(init_cli.sys, "platform", platform), mock.patch.object(init_cli.shutil, "which", which), \
            mock.patch.object(init_cli, "_confirm", confirm), \
            mock.patch.object(linux_fixes, "install_static_ripgrep", install), \
            mock.patch.object(linux_fixes, "ensure_local_bin_on_rc", rc_line), \
            mock.patch.object(linux_fixes, "local_bin_on_noninteractive_path", lambda **_k: False), \
            mock.patch.dict(os.environ, {"PATH": path, "EDITOR": "nano"}):
        init_cli._step_linux_fixes(args, console)
    return buf.getvalue(), rec


@test
def test_macos_gets_no_linux_offers(ctx: Ctx):
    local_bin = str(Path.home() / ".local" / "bin")
    text, rec = _fixes_step("darwin", rg=None, path="/usr/bin:/bin")
    ctx.check(f"no 'Linux fixes' title on macOS, got {text!r}", "Linux fixes" not in text)
    ctx.check(f"no download offered, no rc file touched, got {rec}", rec["install"] == 0 and rec["rc"] == 0
              and not rec["confirm"])
    ctx.check(f"a missing rg names what a Mac user does, got {text!r}", "brew install ripgrep" in text)
    ctx.check(f"~/.local/bin off PATH names ~/.zprofile, never ~/.profile, got {text!r}", "~/.zprofile" in text
              and "~/.profile" not in text)
    text, rec = _fixes_step("darwin", rg="/opt/homebrew/bin/rg", path=os.pathsep.join(["/usr/bin", local_bin]))
    ctx.check(f"rg there and ~/.local/bin on PATH: nothing to do and nothing asked, got {text!r} {rec}",
              not rec["confirm"] and "brew install" not in text and ".zprofile" not in text)


@test
def test_linux_still_gets_its_offers_and_windows_none(ctx: Ctx):
    text, rec = _fixes_step("linux", rg=None, path="/usr/bin:/bin")
    ctx.check(f"Linux: the title and both offers, got {text!r} {rec}", "Linux fixes:" in text
              and len(rec["confirm"]) == 2 and rec["install"] == 1 and rec["rc"] == 1)
    text, rec = _fixes_step("win32", rg=None, path="C:\\Windows")
    ctx.check(f"Windows: no Linux offer, got {text!r} {rec}", "Linux fixes" not in text and not rec["confirm"]
              and rec["install"] == 0 and rec["rc"] == 0)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="fx jb15 init input tests"))
