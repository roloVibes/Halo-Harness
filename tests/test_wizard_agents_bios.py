"""tests.test_wizard_agents_bios -- Halo 2.0.5 round 2 (wizard: agent bios
and lineups), deliverable 1: the Agents list (`tui/dialogs/agents_step.py`)
and the bio view (`tui/dialogs/agent_bio_editor.py`). 3.1.1.0 R3: Studio is
the one editor of bios -- the list's New / New from... write a starter bio and
open Studio on it, View (Enter) shows it read-only, Edit in Studio (`e`, in
the list and the view) opens Studio; the edits themselves go through Studio's
routes (`PUT /api/bio/<name>`, the same the bio form saves with; the form in a
browser: tests/test_studio_edit_route.py). Hermetic: no network, no real model,
no Studio started (`tui.studio_open.OPENER` records what would open), and every
test scopes `BRIDGE_TEST_HOME`/`BRIDGE_STATE_DIR` to a fresh scratch dir per
`plans/WORKER-RULES.md`. 3.6.0.0 R5: the list, the bio view and the bio
route left; what stays checks the tool names a bio may name.
"""
from __future__ import annotations

TIER = "full"  # a TUI pilot (Textual run_test): the full tier

import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

REPO_DIR = Path(__file__).resolve().parent.parent
test, TESTS = new_registry()


async def _wait_until(pilot, cond, *, timeout: float = 5.0, step: float = 0.05) -> bool:
    """Bounded poll for a TUI condition (the H9b lesson, applied to pilot
    tests): a fixed `pilot.pause(0.2)` races a loaded runner -- a pushed
    screen can exist before its widgets mount (CI 143c1f9: 'No nodes
    match #bio-pref on the bio form'). Poll until `cond()` holds or
    the deadline passes; `cond` may raise (not-yet-mounted widgets) --
    that counts as not-yet, never as failure."""
    deadline = time.monotonic() + timeout
    while True:
        await pilot.pause(step)
        try:
            if cond():
                return True
        except Exception:
            pass
        if time.monotonic() >= deadline:
            try:
                return bool(cond())
            except Exception:
                return False

FIXTURE_MODELS = [
    {"ref": "or:vendor/strong-model", "provider": "openrouter", "group": "OpenRouter (or:)",
     "context_tokens": 128000, "price_in_per_m": 1.0, "price_out_per_m": 2.0,
     "supported_parameters": ["tools"]},
    # Declares reasoning-only support (NOT "unknown" -- a bare missing
    # field is fail-open by house convention, same as `roles.py`'s own
    # "unknown-support" entry; this row exists so the filter test below
    # has a row that's EXPLICITLY not tool-capable to drop.
    {"ref": "or:vendor/cheap-model", "provider": "openrouter", "group": "OpenRouter (or:)",
     "context_tokens": 8000, "price_in_per_m": 0.1, "price_out_per_m": 0.2,
     "supported_parameters": ["reasoning"]},
    {"ref": "ol:local-model", "provider": "ollama", "group": "Ollama (ol:)", "context_tokens": 32000},
]


class _Env:
    """Scratch `BRIDGE_TEST_HOME`/`BRIDGE_STATE_DIR` -- the real `~/.halo`
    is never touched (same pattern `tests/test_agents_teams.py::_Env`
    already uses)."""

    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
        d = Path(tempfile.mkdtemp(prefix="wizard-agents-bios-"))
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


def _static_text(widget) -> str:
    return str(widget.renderable) if hasattr(widget, "renderable") else str(widget.render())


# ---------------------------------------------------------------------------
# Pure helpers (no Textual needed).
# ---------------------------------------------------------------------------

@test
def test_known_tool_names_includes_the_real_builtins(ctx: Ctx):
    from halo_harness.tools.registry import known_tool_names  # what Studio's bio form offers (GET /api/tools)
    names = known_tool_names()
    ctx.check(f"Bash/Read/Edit are real tool names, got {names}",
              {"Bash", "Read", "Edit"}.issubset(set(names)))


class _Opened:
    """`tui.studio_open.OPENER` for a test: records each target, answers as a focused Studio would."""

    def __enter__(self):
        from halo_harness.tui import studio_open
        self.mod, self.old, self.targets = studio_open, studio_open.OPENER, []

        def _opener(target, **_kw):
            self.targets.append(target.text)
            return {"url": f"http://127.0.0.1:1/{target.query()}#t=x", "how": "focused", "pages": 1, "target": target.text}
        studio_open.OPENER = _opener
        return self

    def __exit__(self, *exc):
        self.mod.OPENER = self.old


def _put_bio(e, name: str, raw: dict) -> "tuple[int, dict]":
    """What Studio's bio form sends on Save."""
    from halo_harness.studio.api import Request, dispatch
    return dispatch(Request(owner=True, method="PUT", path=f"bio/{name}", query={}, body={"raw": raw}, cwd=e.cwd, state_dir=e.state_dir))


def _names(app) -> list:
    from textual.widgets import OptionList
    rows = app.screen.query_one("#agents-list", OptionList)
    return [str(rows.get_option_at_index(i).id) for i in range(rows.option_count)]


def _highlight(app, name: str) -> None:
    from textual.widgets import OptionList
    app.screen.query_one("#agents-list", OptionList).highlighted = _names(app).index(name)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
