"""tests.test_round_wizard_deep_review -- Halo 2.0.7: the wizard deep
review (rolo 2026-10-07: "everything to do with ROLES, ROLE TEMPLATES,
and AGENT BIOS needs to be incredibly smooth and clear on what is going
on and how to use this").

The first-time-user contract, pinned as a pilot path:
  * `halo roles` / `halo setup roles` (no TTY) / the roles CLI face open
    with the two plain lines: what a role IS, and WHEN it fires -- plus a
    when-it-fires note on every known role row;
  * the wizard's Team step shows the same plain sentence, and only ONE
    pane at a time at EVERY width (the old 120x40 side-by-side stack is
    gone -- that was "the thing to fix");
  * the lineup editor opens with a what-this-is sentence, a live COST
    footer (per role, the model's own picker price; free/unknown for
    local lanes, never a fabricated number), and per-field one-liners;
  * the bio editor opens with a what-a-bio-is sentence and a plain
    one-line explanation under every known field.
"""
from __future__ import annotations

TIER = "full"  # a TUI pilot (Textual run_test): the full tier

import asyncio
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

REPO_DIR = Path(__file__).resolve().parent.parent

test, TESTS = new_registry()


class _Env:
    """Scratch BRIDGE_TEST_HOME/BRIDGE_STATE_DIR, matching the round-2c
    wizard tests' own hermetic pattern."""

    def __init__(self):
        self._saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
        d = tempfile.mkdtemp(prefix="wiz-deep-")
        os.environ["BRIDGE_TEST_HOME"] = d
        os.environ["BRIDGE_STATE_DIR"] = d

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        return False


def _run(coro):
    return asyncio.run(coro)


def _static_text(widget) -> str:
    from rich.text import Text
    content = getattr(widget, "content", "")
    if isinstance(content, Text):
        return content.plain
    return str(content)


# ---- the roles CLI face -----------------------------------------------------------


@test
def test_roles_table_opens_with_the_two_plain_lines(ctx: Ctx):
    import io
    from contextlib import redirect_stdout
    from halo_harness.roles_cli import _cmd_table
    with _Env():
        buf = io.StringIO()
        with redirect_stdout(buf):
            _cmd_table()
        out = buf.getvalue()
    ctx.check("line 2 says what a role IS",
              "A role names the model for one job" in out)
    ctx.check("line 3 says what happens when roles are off",
              "Roles are off -> every job" in out)
    ctx.check("a known role carries its when-it-fires note",
              "the session's own conversation model" in out
              or "any sub-agent whose bio" in out)


# ---- the Team step ------------------------------------------------------------------


@test
def test_team_step_header_list_and_preview_at_every_width(ctx: Ctx):
    from halo_harness.tui.dialogs.init_wizard import InitWizardApp, WizardState

    async def body(w, h):
        with _Env():
            state = WizardState(cwd=REPO_DIR, step_keys=("team",), no_live=True)
            app = InitWizardApp(state)
            async with app.run_test(size=(w, h)) as pilot:
                await pilot.pause(0.2)
                head = app.screen.query_one("#wiz-team-header-sentence")
                ctx.check(f"the plain-words header shows at {w}x{h}",
                          "unless you pick a lineup" in _static_text(head))
                ctx.check(f"the lineup list and the preview both exist at {w}x{h}",
                          app.screen.query("#wiz-team-lineups-list") and app.screen.query("#wiz-team-preview"))
                ctx.check(f"no Custom roles switch any more at {w}x{h}", not app.screen.query("#wiz-team-switch"))

    for size in ((80, 24), (120, 40), (160, 50)):
        _run(body(*size))


# ---- the lineup editor ----------------------------------------------------------------


@test
def test_lineup_view_opens_with_help_and_a_cost_footer(ctx: Ctx):
    from halo_harness.tui.dialogs.lineup_editor import LineupView

    models = [
        {"ref": "or:paid/model-a", "price_in_per_m": 0.60, "price_out_per_m": 2.40},
        {"ref": "ol:local/free", "price_in_per_m": None, "price_out_per_m": None},
    ]

    async def body():
        with _Env():
            from textual.app import App

            template = {"agents": [
                {"role": "worker", "model": "or:paid/model-a"},
                {"role": "researcher", "model": "ol:local/free"},
            ]}
            editor = LineupView("smoke", template, models)

            class _Host(App):
                def on_mount(self):
                    self.push_screen(editor)

            async with _Host().run_test(size=(120, 40)) as pilot:
                await pilot.pause(0.2)
                what = editor.query_one("#lineup-what-sentence")
                ctx.check("the what-a-lineup-is sentence shows",
                          "A lineup is the role table" in _static_text(what))
                footer = _static_text(editor.query_one("#lineup-cost-footer"))
                ctx.check(f"the cost footer prices the paid row, got {footer!r}",
                          "worker:" in footer and "$0.60" in footer and "$2.40" in footer)
                ctx.check("the local lane reads free/unknown, never a fabricated price",
                          "researcher: ol:local/free -- free/unknown price" in footer)
    _run(body())


# ---- the bio view (3.1.1.0 R3: read-only; Studio edits) -------------------------------


@test
def test_bio_view_opens_with_a_sentence_and_per_field_help(ctx: Ctx):
    from halo_harness import field_help
    from halo_harness.tui.dialogs.agent_bio_editor import WHAT_SENTENCE, AgentBioView
    from halo_harness.tui.dialogs.bio_view_text import FIELDS

    missing = [f"{s}.{k}" for (s, k, _label) in FIELDS if not field_help.bio_line(s, k)]
    ctx.check(f"every field the view shows has its one plain line, missing: {missing}", not missing)
    for key in ("models.preference", "tools.allow", "limits.max_budget_usd", "output.handoff"):
        ctx.check(f"the {key} field has its one plain line", field_help.BIO.get(key))

    async def body():
        with _Env():
            from textual.app import App
            from textual.widgets import Input

            raw = {"description": "smoke", "models": {"preference": "or:paid/model-a"}, "tools": {"allow": ["Read"]}}
            editor = AgentBioView("smoke-agent", raw, [])

            class _Host(App):
                def on_mount(self):
                    self.push_screen(editor)

            async with _Host().run_test(size=(120, 40)) as pilot:
                await pilot.pause(0.3)
                ctx.check("the what-a-bio-is sentence shows", _static_text(editor.query_one("#bio-identity-hint")) == WHAT_SENTENCE)
                texts = [_static_text(s) for s in editor.query("Static")]
                for key in ("models.preference", "tools.allow"):
                    ctx.check(f"the {key} line shows under its field", any(field_help.BIO[key] in x for x in texts))
                ctx.check("the preferred model shows as text", "Preferred model: or:paid/model-a" in texts)
                ctx.check("a read-only view: no inputs at all", not editor.query(Input))

    _run(body())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
