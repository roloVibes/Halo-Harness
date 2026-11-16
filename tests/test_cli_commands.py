"""tests.test_cli_commands -- Halo 3.6.0.0 R16: `halo --help` names every command, from the one registry.

1. Every command the dispatcher accepts (cli_commands.COMMANDS, plus any literal verb cli.py's own source still
   tests `argv[0]` against) is listed in `halo --help` or is marked internal / retired in the registry -- and every
   command `halo --help` lists is one the registry runs. Before R16 the help was a hand-kept line naming 26 of 53.
2. Every listed command's own `halo <command> --help` exits 0 (a scratch home, no network).
3. `halo --help` imports no command's module (it stays fast; the time is printed).
4. `halo --version` prints one line, `halo <version> (<commit>, <branch>)`, nothing else, exit 0 -- no banner.

Run: python -m tests.test_cli_commands
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _env() -> dict:
    home = tempfile.mkdtemp(prefix="halo-cli-commands-")
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HALO_", "BRIDGE_"))}
    env.update({"PYTHONPATH": str(REPO), "BRIDGE_TEST_HOME": home, "BRIDGE_TEST_NO_BACKGROUND_NET": "1",
                "OLLAMA_HOST": "http://127.0.0.1:9", "HALO_NO_UPDATER": "1", "PYTHONIOENCODING": "utf-8"})
    return env


def _halo(args: list, env: dict, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "halo_harness", *args], env=env, cwd=str(REPO), capture_output=True,
                          encoding="utf-8", errors="replace", timeout=timeout, stdin=subprocess.DEVNULL)


def _listed_in_help(text: str) -> list:
    """The command names of the help's commands block: `    <name>  <purpose>` under a group heading."""
    block = text[text.index("Commands: `halo <command> --help`"):]
    return re.findall(r"^    ([a-z][a-z0-9-]*)\s{2,}\S", block, re.MULTILINE)


@test
def test_every_dispatched_command_is_in_the_help_or_marked(ctx: Ctx):
    from halo_harness import cli
    from halo_harness.cli_commands import BY_NAME, COMMANDS, GROUPS, listed
    names = [c.name for c in COMMANDS]
    ctx.check(f"each command is registered once, got {sorted(n for n in names if names.count(n) > 1)}",
              len(names) == len(set(names)))
    ctx.check("every row has a group, a purpose and a known kind",
              all(c.group in GROUPS and c.purpose and c.kind in ("", "internal", "retired") for c in COMMANDS))
    src = (REPO / "halo_harness" / "cli.py").read_text(encoding="utf-8")
    literal = set(re.findall(r'argv\[0\] == "([^"]+)"', src))
    for group in re.findall(r"argv\[0\] in \(([^)]*)\)", src):
        literal |= set(re.findall(r'"([^"]+)"', group))
    literal |= set(re.findall(r'argv\[:2\] == \["([^"]+)"', src))
    accepted = set(BY_NAME) | literal | set(cli.GONE_VERBS)
    ctx.check(f"every verb cli.py tests by hand is registered, missing {sorted(accepted - set(BY_NAME))}",
              accepted <= set(BY_NAME))
    retired = {c.name for c in COMMANDS if c.kind == "retired"}
    ctx.check(f"the retired rows are cli.py's GONE_VERBS (but roles, internal) and design, got {sorted(retired)}",
              retired == (set(cli.GONE_VERBS) - {"roles"}) | {"design"})
    text = cli._build_parser().format_help()
    shown = _listed_in_help(text)
    want = [c.name for c in listed()]
    ctx.check(f"halo --help lists every listed command, missing {sorted(set(want) - set(shown))}, "
              f"extra {sorted(set(shown) - set(want))}", sorted(shown) == sorted(want))
    hidden = {c.name for c in COMMANDS if c.kind}
    ctx.check(f"no internal or retired command is listed, got {sorted(hidden & set(shown))}", not hidden & set(shown))
    ctx.check("the everyday group comes first", text.index("  " + GROUPS[0] + "\n") < text.index("  " + GROUPS[1] + "\n"))
    import importlib
    bad = []
    for c in COMMANDS:
        if not c.target:
            continue
        module, func = c.target.split(":")
        if not callable(getattr(importlib.import_module(module), func, None)):
            bad.append(c.name)
    ctx.check(f"every row's target is a function, not: {bad}", not bad)


@test
def test_every_listed_command_answers_its_own_help(ctx: Ctx):
    from halo_harness.cli_commands import listed
    env = _env()
    failed = []
    for c in listed():
        r = _halo([c.name, "--help"], env)
        if r.returncode != 0 or "Traceback" in r.stderr:
            failed.append((c.name, r.returncode, (r.stderr or r.stdout)[-200:]))
    ctx.check(f"`halo <command> --help` exits 0 for each listed command, not: {failed}", not failed)


@test
def test_help_imports_no_command_module(ctx: Ctx):
    from halo_harness.cli_commands import COMMANDS
    probe = ("import contextlib, io, sys\n"
             "import halo_harness.cli as cli\n"
             "before = set(sys.modules)\n"
             "with contextlib.redirect_stdout(io.StringIO()):\n"
             "    try:\n"
             "        cli.main(['--help'])\n"
             "    except SystemExit:\n"
             "        pass\n"
             "print('\\n'.join(sorted(set(sys.modules) - before)))\n")
    r = subprocess.run([sys.executable, "-c", probe], env=_env(), cwd=str(REPO), capture_output=True,
                       encoding="utf-8", errors="replace", timeout=60)
    loaded = set(r.stdout.split())
    targets = {c.target.split(":")[0] for c in COMMANDS if c.target}
    ctx.check(f"the probe ran, got {r.returncode} {r.stderr[-300:]!r}", r.returncode == 0)
    ctx.check(f"building halo --help imports no command's module, got {sorted(loaded & targets)}",
              not loaded & targets)
    ctx.check(f"nor any halo_harness module past the registry, got {sorted(loaded)}",
              {m for m in loaded if m.startswith("halo_harness")} <= {"halo_harness.cli_commands"})
    env = _env()
    best = min(_timed(["--help"], env) for _ in range(3))
    print(f"  halo --help: {best:.3f} s (best of 3, interpreter start included)")


def _timed(args: list, env: dict) -> float:
    t0 = time.perf_counter()
    _halo(args, env)
    return time.perf_counter() - t0


@test
def test_version_is_one_line(ctx: Ctx):
    from halo_harness import __version__
    env = _env()
    for flag in ("--version", "-v"):
        r = _halo([flag], env)
        lines = r.stdout.splitlines()
        ctx.check(f"{flag}: exit 0, got {r.returncode} {r.stderr[-300:]!r}", r.returncode == 0)
        ctx.check(f"{flag}: exactly one line, `halo {__version__} (<commit>, <branch>)`, got {r.stdout!r}",
                  len(lines) == 1 and re.fullmatch(rf"halo {re.escape(__version__)}( \([0-9a-f]{{7,40}}(, \S+)?\))?",
                                                   lines[0]) is not None)
        ctx.check(f"{flag}: nothing on stderr, got {r.stderr!r}", r.stderr == "")
    from halo_harness.cli import version_line
    from halo_harness.update import format_version_line, installed_build
    ctx.check(f"the line is update.format_version_line's, the branch kept (halo update's before and after lines match), "
              f"got {version_line()!r}", version_line() == format_version_line(installed_build()))
    ctx.check("a live checkout names its commit", re.fullmatch(r"halo \S+ \([0-9a-f]{7,40}(, \S+)?\)", version_line())
              is not None or not (REPO / ".git").exists())


@test
def test_a_mistyped_command_says_did_you_mean_and_starts_no_session(ctx: Ctx):
    """3.6.0.0 fix pass: `halo docter` used to go to the model as a prompt (a full session titled 'docter' on a
    terminal, a billed call); `halo map show x` / `halo theme x` dumped argparse's usage."""
    env = _env()
    for args, want in ((["docter"], "halo doctor"), (["initt"], "halo init"), (["map", "show", "nosuch-map"], "halo maps"),
                       (["theme", "nosuch"], "halo config set theme")):
        got = _halo(args, env)
        err = got.stderr
        ctx.check(f"`halo {' '.join(args)}` exits 2, got {got.returncode} {err[-300:]!r}", got.returncode == 2)
        ctx.check(f"`halo {' '.join(args)}` says no such command and suggests {want!r}, got {err[-300:]!r}",
                  "no command" in err and want in err)
        ctx.check(f"`halo {' '.join(args)}` dumps no usage and starts no session, got {err[-300:]!r}",
                  "usage:" not in err and "interactive terminal" not in err)
    from halo_harness import cli
    ctx.check("a word close to no command is left alone (a prompt)", cli._near_miss_command(["hello"]) is None)
    ctx.check("a sentence prompt is left alone", cli._near_miss_command(["fix the docter page"]) is None)
    # Batch-1 check: an ordinary word two edits off a command, or one that starts with another letter, is a prompt
    # (`lint` is not `init`, `port` is not `report`, `post` is not `host`, `start`/`stash` are not `stats`).
    for word in ("lint", "port", "post", "start", "stash", "hello"):
        ctx.check(f"`halo {word}` is left alone (a prompt)", cli._near_miss_command([word]) is None)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
