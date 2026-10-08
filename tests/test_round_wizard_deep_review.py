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
def test_team_step_one_pane_at_a_time_at_every_width(ctx: Ctx):
    from halo_harness.tui.dialogs.init_wizard import InitWizardApp, WizardState

    async def body(w, h):
        with _Env():
            state = WizardState(cwd=REPO_DIR, step_keys=("team",), no_live=True)
            app = InitWizardApp(state)
            async with app.run_test(size=(w, h)) as pilot:
                await pilot.pause(0.2)
                what = app.screen.query_one("#wiz-team-what-sentence")
                ctx.check(f"the what-a-role-is sentence shows at {w}x{h}",
                          "A role names the model for one job" in _static_text(what))
                lineups = app.screen.query_one("#wiz-team-lineups-pane")
                agents = app.screen.query_one("#wiz-team-agents-pane")
                switch_bar = app.screen.query_one("#wiz-team-pane-switch")
                ctx.check(f"the pane switch is ALWAYS visible at {w}x{h}",
                          switch_bar.styles.display != "none")
                lp = lineups.styles.display
                ap = agents.styles.display
                ctx.check(f"exactly ONE pane visible at {w}x{h} (lineups={lp}, agents={ap})",
                          (lp == "none") != (ap == "none"))
                ctx.check("lineups pane is the one shown first",
                          lp != "none" and ap == "none")

    for size in ((80, 24), (120, 40), (160, 50)):
        _run(body(*size))


# ---- the lineup editor ----------------------------------------------------------------


@test
def test_lineup_editor_opens_with_help_and_a_cost_footer(ctx: Ctx):
    from halo_harness.tui.dialogs.lineup_editor import LineupEditor

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
            editor = LineupEditor("smoke", template, models)

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


# ---- the bio editor ---------------------------------------------------------------------


@test
def test_bio_editor_opens_with_a_sentence_and_per_field_help(ctx: Ctx):
    from halo_harness.tui.dialogs.agent_bio_editor import AgentBioEditor, FIELD_HELP, FIELDS

    covered = {(s, k) for (s, k, *_rest) in FIELDS}
    missing = [key for key in FIELD_HELP if key not in covered]
    ctx.check(f"every FIELD_HELP entry matches a real field, bogus: {missing}", not missing)
    key_fields = [("models", "preference"), ("tools", "allow"), ("limits", "max_budget_usd"),
                  ("output", "handoff")]
    for key in key_fields:
        ctx.check(f"the {key[1]} field has its one plain line", key in FIELD_HELP)

    async def body():
        with _Env():
            from textual.app import App
            from halo_harness.tui.dialogs.agent_bio_editor import _IDENTITY_HINT_ID

            editor = AgentBioEditor("smoke-agent", {}, [], is_new=True)

            class _Host(App):
                def on_mount(self):
                    self.push_screen(editor)

            async with _Host().run_test(size=(120, 40)) as pilot:
                await pilot.pause(0.6)  # the focus poll runs every 0.25s
                hint = _static_text(editor.query_one(f"#{_IDENTITY_HINT_ID}"))
                # On open the NAME field is focused (is_new) -- its plain
                # line is already showing; the what-a-bio-is sentence is
                # the idle/unmapped fallback of the SAME line.
                ctx.check(f"the focused name field's plain line shows, got {hint!r}",
                          "how /agent and lineups call this bio" in hint)
                # Focus the preferred-model field -> its plain line shows.
                try:
                    editor.query_one("#bio-pref").focus()
                except Exception:
                    pass
                await pilot.pause(0.6)
                hint2 = _static_text(editor.query_one(f"#{_IDENTITY_HINT_ID}"))
                ctx.check(f"the focused model field's plain line shows, got {hint2!r}",
                          "the model this agent runs on, when it runs" in hint2)
                # Focus the tools-allow field -> THAT plain line shows.
                try:
                    editor.query_one("#bio-tools-allow").focus()
                except Exception:
                    pass
                await pilot.pause(0.6)
                hint3 = _static_text(editor.query_one(f"#{_IDENTITY_HINT_ID}"))
                ctx.check(f"the focused allow-list field's plain line shows, got {hint3!r}",
                          "the ONLY tools this agent may call" in hint3)

    _run(body())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
