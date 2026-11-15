"""tests.test_wizard_lineup -- Halo 2.0.5 round 2 (wizard: agent bios and
lineups): deliverable 2 (the roles editor's Models/Agents picker source)
and deliverable 3 (the lineup editor) plus the `about:` context-builder
fold-in. 3.1.1.0 R3: Studio is the one editor of lineups -- the lineups are
made and saved through Studio's routes (the ones its Lineups panel and
inspector call; the inspector in a browser: tests/test_studio_edit_route.py)
and the terminal shows them in the read-only view (`tui/dialogs/
lineup_editor.py`: `e` opens Studio, `t` probes a model). Hermetic: no
network, no real model, no Studio started. 3.6.0.0 R5: the roles editor and the lineup
view left the TUI with their four tests; the lineup layer's own checks stay until R5b.
"""
from __future__ import annotations

TIER = "full"  # a TUI pilot (Textual run_test): the full tier

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

REPO_DIR = Path(__file__).resolve().parent.parent
test, TESTS = new_registry()

FIXTURE_MODELS = [
    {"ref": "or:vendor/strong-model", "provider": "openrouter", "group": "OpenRouter (or:)",
     "context_tokens": 128000, "price_in_per_m": 1.0, "price_out_per_m": 2.0},
    {"ref": "or:vendor/cheap-model", "provider": "openrouter", "group": "OpenRouter (or:)",
     "context_tokens": 8000, "price_in_per_m": 0.1, "price_out_per_m": 0.2},
]


class _Env:
    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
        d = Path(tempfile.mkdtemp(prefix="wizard-lineup-"))
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
# Pure helpers.
# ---------------------------------------------------------------------------

@test
def test_draft_about_text_is_never_blank(ctx: Ctx):
    from halo_harness.tui.dialogs.lineup_view_text import draft_about_text
    empty = draft_about_text({"agents": []})
    ctx.check(f"an empty lineup still gets a sentence, got {empty!r}", bool(empty.strip()))
    full = draft_about_text({"agents": [{"agent": "coder", "role": "main", "as": "boss"}],
                              "delegation": {"mode": "by-skill"},
                              "pipeline": {"stages": [{"name": "implement"}, {"name": "review"}]}})
    ctx.check(f"mentions the assignment, got {full!r}", "boss" in full and "coder" in full)
    ctx.check("mentions delegation mode", "by-skill" in full)
    ctx.check("mentions the pipeline order", "implement -> review" in full)


@test
def test_lineup_warnings_catch_missing_bio_duplicate_alias_and_main_count(ctx: Ctx):
    from halo_harness.tui.dialogs.lineup_view_text import lineup_warnings
    with _Env():
        warnings = lineup_warnings([
            {"agent": "no-such-bio", "role": "main", "as": "a"},
            {"agent": "no-such-bio", "role": "subagent", "as": "a"},  # duplicate alias "a"
        ])
        ctx.check(f"missing bio flagged, got {warnings}", any("not found" in w for w in warnings))
        ctx.check(f"duplicate alias flagged, got {warnings}", any("duplicate alias" in w for w in warnings))
        none_main = lineup_warnings([{"agent": "x", "role": "subagent", "as": "a"}])
        ctx.check(f"no role: main flagged, got {none_main}", any("role: main" in w for w in none_main))


@test
def test_lineup_warnings_flag_a_same_gateway_fallback(ctx: Ctx):
    from halo_harness.agents_yaml import save_agent_bio
    from halo_harness.tui.dialogs.lineup_view_text import lineup_warnings
    with _Env() as e:
        save_agent_bio("same-gateway-bio", {"description": "x",
                                             "models": {"preference": "or:vendor/a", "fallback": "or:vendor/b"}},
                        state_dir=e.state_dir)
        warnings = lineup_warnings([{"agent": "same-gateway-bio", "role": "main", "as": "boss"}],
                                    state_dir=e.state_dir)
        ctx.check(f"same-gateway fallback flagged, got {warnings}",
                  any("same gateway" in w for w in warnings))


@test
def test_about_round_trips_through_teams_yaml_and_extends_inherits_it(ctx: Ctx):
    from halo_harness.agents_yaml import save_agent_bio
    from halo_harness.teams_yaml import resolve_team_template, save_team_template
    with _Env() as e:
        save_agent_bio("lineup-member", {"description": "x", "models": {"preference": "or:vendor/a"}},
                        state_dir=e.state_dir)
        save_team_template("about-base", {"description": "d", "about": "How this team works: carefully.",
                                           "agents": [{"agent": "lineup-member", "role": "main"}]},
                            state_dir=e.state_dir)
        resolved = resolve_team_template("about-base", state_dir=e.state_dir)
        ctx.check(f"about round-trips, got {resolved.get('about')!r}",
                  resolved["about"] == "How this team works: carefully.")
        save_team_template("about-child", {"description": "child", "extends": "about-base"}, state_dir=e.state_dir)
        child = resolve_team_template("about-child", state_dir=e.state_dir)
        ctx.check(f"a child that never sets its own about inherits the parent's, got {child.get('about')!r}",
                  child["about"] == "How this team works: carefully.")


@test
def test_member_system_context_addition_appends_how_this_team_works(ctx: Ctx):
    """Tests section: "The active team's about text reaches a member's
    system context (unit test on the context builder)"."""
    from halo_harness.agents_yaml import save_agent_bio
    from halo_harness.teams_yaml import member_system_context_addition, save_team_template
    from halo_harness.theme import set_config_value
    with _Env() as e:
        save_agent_bio("ctx-member", {"description": "x", "models": {"preference": "or:vendor/a"},
                                       "context": {"system_prompt": "Be terse."}}, state_dir=e.state_dir)
        save_agent_bio("ctx-outsider", {"description": "y", "models": {"preference": "or:vendor/a"}},
                        state_dir=e.state_dir)
        save_team_template("ctx-team", {"description": "d", "about": "Ship small, verify every round.",
                                         "agents": [{"agent": "ctx-member", "role": "main"}]}, state_dir=e.state_dir)
        set_config_value("team", "ctx-team")
        addition = member_system_context_addition("ctx-member", state_dir=e.state_dir)
        ctx.check(f"the bio's own system_prompt is included, got {addition!r}", "Be terse." in addition)
        ctx.check(f"the team's about text lands under the house heading, got {addition!r}",
                  "How this team works" in addition and "Ship small" in addition)
        outsider_addition = member_system_context_addition("ctx-outsider", state_dir=e.state_dir)
        ctx.check(f"a bio NOT in the active team never gets the about text, got {outsider_addition!r}",
                  "How this team works" not in outsider_addition)


@test
def test_apply_team_template_writes_roles_and_active_team(ctx: Ctx):
    from halo_harness.agents_yaml import save_agent_bio
    from halo_harness.teams_yaml import apply_team_template, save_team_template
    from halo_harness.theme import get_config_value
    with _Env() as e:
        save_agent_bio("apply-member", {"description": "x", "models": {"preference": "or:vendor/pinned"}},
                        state_dir=e.state_dir)
        save_team_template("apply-lineup", {"description": "d",
                                             "agents": [{"agent": "apply-member", "role": "main", "as": "boss"}]},
                            state_dir=e.state_dir)
        ok, problems, notes = apply_team_template("apply-lineup", state_dir=e.state_dir)
        ctx.check(f"apply succeeded, got {problems}", ok)
        ctx.check(f"roles.boss landed in config, got {get_config_value('roles.boss', default=None)}",
                  get_config_value("roles.boss", default=None) == "or:vendor/pinned")
        ctx.check(f"team: is now active, got {get_config_value('team', default=None)}",
                  get_config_value("team", default=None) == "apply-lineup")


# ---------------------------------------------------------------------------
# Textual pilots: deliverable 2 (roles editor Agents source) and
# deliverable 3 (the lineup editor + the RolesStep "Roles and lineup"
# panes).
# ---------------------------------------------------------------------------

def _host_screen(screen):
    from textual.app import App

    class _Host(App):
        result = None

        def on_mount(self):
            def _after(r):
                self.result = r
            self.push_screen(screen, _after)
    return _Host()


def _studio(e, method: str, path: str, body: "dict | None" = None) -> "tuple[int, dict]":
    """One of Studio's routes, the ones its Lineups panel and inspector use."""
    from halo_harness.studio.api import Request, dispatch
    return dispatch(Request(owner=True, method=method, path=path, query={}, body=body or {}, cwd=e.cwd, state_dir=e.state_dir))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
