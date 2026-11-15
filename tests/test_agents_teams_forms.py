"""tests.test_agents_teams_forms -- Halo 2.0.5 round 2 (wizard: agent
bios and lineups), deliverable 4: `/agents`/`/teams` (list, new, edit,
view, duplicate, delete, activate) in a running session, `/edit`, and
`halo agents|teams new|edit` from the CLI -- plus `halo init --step agents`
(deliverable 1). 3.1.1.0 R3: Studio is the one editor of bios and lineups:
`edit` (and `new --studio`, `/agents new`) open Studio on the thing, `view`
shows it read-only in the terminal. Hermetic: no network, no real model,
no Studio started (`studio_edit_cli.open_in_studio` and
`tui.studio_open.OPENER` record what would open).
"""
from __future__ import annotations

TIER = "full"  # a TUI pilot (Textual run_test): the full tier

import asyncio
import contextlib
import io
import os
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

REPO_DIR = Path(__file__).resolve().parent.parent
test, TESTS = new_registry()

FIXTURE_MODELS = [{"ref": "or:vendor/strong-model", "provider": "openrouter", "group": "OpenRouter (or:)"}]


class _Env:
    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
        d = Path(tempfile.mkdtemp(prefix="agents-teams-forms-"))
        os.environ["BRIDGE_TEST_HOME"] = str(d)
        os.environ["BRIDGE_STATE_DIR"] = str(d / ".halo")
        self.home, self.state_dir = d, d / ".halo"
        self.cwd = d / "project"
        self.cwd.mkdir(parents=True, exist_ok=True)
        return self

    def __exit__(self, *exc):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _capture(fn, argv) -> "tuple[int, str]":
    """`argparse`'s own `-h`/`--help` action raises `SystemExit` (never an
    `Exception` subclass -- `run_all`'s own `except Exception:` does NOT
    catch it, so an uncaught one here silently ends the WHOLE process
    with no traceback, confirmed live: every later test's own [PASS]/
    [FAIL] line, and `print_results`' summary, simply never printed).
    Same catch `tests/test_docs_commands.py::_capture` already uses."""
    buf = io.StringIO()
    rc = 0
    try:
        with redirect_stdout(buf), redirect_stderr(buf):
            rc = fn(argv)
    except SystemExit as e:
        rc = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    return rc, buf.getvalue()


# ---------------------------------------------------------------------------
# CLI: `edit` and `new --studio` open Studio (3.1.1.0 R3) -- the opener is
# monkeypatched (no Studio, no browser).
# ---------------------------------------------------------------------------

@contextlib.contextmanager
def _studio_calls():
    """`studio_edit_cli.open_in_studio` recorded instead of reaching a Studio (3.1.1.0 R3)."""
    import halo_harness.studio_edit_cli as mod
    calls, old = [], mod.open_in_studio
    mod.open_in_studio = lambda kind, name, **kw: calls.append((kind, name, kw.get("no_open"))) or 0
    try:
        yield calls
    finally:
        mod.open_in_studio = old


class _FakeTranscript:
    def __init__(self):
        self.notes = []

    async def add_note(self, text, kind=None):
        self.notes.append((text, kind))


class _FakeController:
    def list_models(self):
        return FIXTURE_MODELS

    def run_slash(self, name, args):
        """The headless builtin the real controller falls through to."""
        from halo_harness.commands.builtins import HeadlessFacade, _BUILTIN_SPECS
        return _BUILTIN_SPECS[name][3](args, HeadlessFacade(cwd=Path.cwd()))


async def _poll_until(pilot, predicate, *, iterations: int = 60, step_s: float = 0.05) -> bool:
    for _ in range(iterations):
        await pilot.pause(step_s)
        if predicate():
            return True
    return False


def _build_slash_host_app(cwd: Path):
    from textual.app import App
    from textual.screen import Screen

    class _HostApp(App):
        def __init__(self):
            super().__init__()
            self.cwd = cwd
            self.controller = _FakeController()
            self.transcript = _FakeTranscript()

        def on_mount(self):
            self.push_screen(Screen())
    return _HostApp()


class _Opened:
    """`tui.studio_open.OPENER` for a test (3.1.1.0 R3): records each target, answers as a focused Studio."""

    def __enter__(self):
        from halo_harness.tui import studio_open
        self.mod, self.old, self.targets = studio_open, studio_open.OPENER, []
        studio_open.OPENER = lambda target, **_kw: self.targets.append(target.text) or {
            "url": f"http://127.0.0.1:1/{target.query()}#t=x", "how": "focused", "pages": 1, "target": target.text}
        return self

    def __exit__(self, *exc):
        self.mod.OPENER = self.old


@test
def test_halo_init_help_documents_step(ctx: Ctx):
    import halo_harness.init_cli as init_cli_mod
    rc, out = _capture(init_cli_mod.cmd_init, ["--help"])
    ctx.check(f"--step is a real, documented flag, got {out!r}", "--step" in out)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
