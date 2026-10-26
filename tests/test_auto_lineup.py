"""tests.test_auto_lineup -- the `auto` lineup and the default (Halo 3.1.9.0
R2, "the Auto lineup"):

1. the lineup and its seven pool bios load through the normal loaders with
   no problems (validation, the run-start preflight, tiers);
2. with no `team:` anywhere a session runs `auto` (the default), `/status`,
   `halo doctor` and `roles: on (...)` say so, and the Agent tool's
   description says the lineup is auto; roles off runs none;
3. a set `team:` (or `--team`) is never changed and wins; under the default a
   role table you set and `agents.max_depth` win, under `team: auto` the
   lineup does;
4. the wizard's Team step: Next on the default row writes nothing, One model
   for everything clears `team:` (no more `team: standard`), another lineup
   applies; existing users with `team: standard` keep it.
No model call. Run: python -m tests.test_auto_lineup
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

ensure_default_provider_credentials()
test, TESTS = new_registry()
POOL = ("auto-planner", "auto-researcher", "auto-coder", "auto-reviewer", "auto-media", "auto-writer", "auto-ops")


class _Env:
    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
        d = Path(tempfile.mkdtemp(prefix="auto-lineup-"))
        os.environ["BRIDGE_TEST_HOME"], os.environ["BRIDGE_STATE_DIR"] = str(d), str(d / ".halo")
        self.state_dir, self.cwd = d / ".halo", d / "project"
        self.cwd.mkdir(parents=True)
        return self

    def __exit__(self, *exc):
        for k, v in self._saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


def _session(e: _Env, team_name=None):
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.agent.loop import Session
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.providers.stream import ProviderCreds
    from halo_harness.roles import resolve_role_table
    return Session(cwd=e.cwd, model_ref=parse_model_ref("or:mock/auto-main"), model_profile=ModelProfile(),
                   creds=ProviderCreds(base_url="http://127.0.0.1:9", api_key="k"), state_dir=e.state_dir,
                   model_label="mock/auto-main", session_context=SessionContext(cwd=e.cwd, model_label="mock/auto-main"),
                   max_turns=2, team_name=team_name, roles=resolve_role_table(provider="openrouter"))  # as headless does


@test
def test_the_lineup_and_its_pool_load_with_no_problems(ctx: Ctx):
    from halo_harness.agents_yaml import load_agent_bio_raw, resolve_agent_bio, validate_agent_bio
    from halo_harness.lineup_preflight import lineup_problems
    from halo_harness.teams_tiers import tier_warnings
    from halo_harness.teams_yaml import list_bundled_team_templates, resolve_role_table, resolve_team_template, \
        validate_team_template
    with _Env() as e:
        ctx.check("auto ships", "auto" in list_bundled_team_templates())
        for name in POOL:
            raw, bio = load_agent_bio_raw(name), resolve_agent_bio(name)
            models = (bio or {}).get("models") or {}
            ctx.check(f"{name}: loads, validates, prefers auto, lists its needs, carries an instruction set and limits",
                      raw is not None and validate_agent_bio(raw, name=name) == [] and models.get("preference") == "auto"
                      and isinstance(models.get("needs"), list) and (bio.get("context") or {}).get("system_prompt")
                      and (bio.get("limits") or {}).get("max_iterations"))
        template = resolve_team_template("auto", cwd=e.cwd, state_dir=e.state_dir)
        ctx.check("the lineup validates", template is not None and validate_team_template(template, name="auto") == [])
        blocks = [f for f in lineup_problems("auto", cwd=e.cwd, state_dir=e.state_dir) if f["severity"] == "blocks"]
        ctx.check(f"the run-start preflight finds nothing that blocks, got {blocks}", blocks == [])
        ctx.check("every alias sits in a tier", tier_warnings(template) == [])
        d = template.get("delegation") or {}
        ctx.check(f"delegation is open (4 parallel, depth 2), got {d}", d.get("max_parallel") == 4 and d.get("max_depth") == 2)
        ctx.check("the band is mid", (template.get("budget") or {}).get("band") == "mid")
        table, _notes = resolve_role_table(template, cwd=e.cwd, state_dir=e.state_dir)
        pool = {k: v for k, v in table.items() if k != "main"}
        ctx.check(f"every pool slot resolves to `auto` (picked at spawn), got {pool}",
                  sorted(pool) == ["coder", "media", "ops", "planner", "researcher", "reviewer", "writer"]
                  and set(pool.values()) == {"auto"})
        bad = dict(template, budget={"band": "cheap"})
        ctx.check("a band outside low/mid/high is a problem", any("budget.band" in p for p in validate_team_template(bad)))


@test
def test_with_no_team_set_a_session_runs_auto_by_default(ctx: Ctx):
    from halo_harness.commands.builtins import HeadlessFacade, _cmd_status
    from halo_harness.doctor import _check_lineup
    from halo_harness.lineup_default import lineup_in_use
    from halo_harness.roles import roles_state_line, set_roles_enabled
    from halo_harness.teams_runtime import active_team_name
    from halo_harness.tools.agent import AgentTool
    with _Env() as e:
        ctx.check(f"nothing set: the default, got {lineup_in_use()}", lineup_in_use() == ("auto", "default") and active_team_name() == "auto")
        s = _session(e)
        tc = s.team_control
        ctx.check("a session loads the auto lineup as the default", tc is not None and tc.name == "auto" and tc.default)
        ctx.check(f"its delegation caps apply, got depth {s.agent_runtime.max_depth} parallel {s.agent_runtime.max_concurrent}",
                  s.agent_runtime.max_depth == 2 and s.agent_runtime.max_concurrent == 4)
        ctx.check("the pool's roles are in the live role table", s.agent_runtime.role_table.get("planner") == "auto")
        ctx.check("only a child on one of its cards reports to main next turn",
                  tc.reports_for("coder") and not tc.reports_for("orchestrator") and not tc.reports_for(None))
        desc = s.tool_registry.get("Agent").description
        ctx.check("the Agent tool's description says the lineup is auto",
                  "The lineup is auto: a sub-agent's model is picked for its task; say `model:` to choose yourself." in desc)
        ctx.check("an Agent tool under no lineup says nothing of it", "lineup is auto" not in AgentTool().description)
        status = _cmd_status("", HeadlessFacade(cwd=e.cwd, session=s))
        ctx.check(f"/status names it, got {status.splitlines()[-1]!r}",
                  "Lineup: auto (default) -- main delegates to a pool whose models are picked for each task; change it "
                  "with `halo config set team <name>` or Studio Roles -> Apply" in status)
        ctx.check(f"halo doctor names it, got {_check_lineup()!r}", "Lineup: auto (default)" in _check_lineup())
        ctx.check(f"so does the roles line, got {roles_state_line()!r}", roles_state_line() == "roles: on (lineup auto, the default)")
        set_roles_enabled(False)
        ctx.check("roles off: no lineup at all", lineup_in_use() == (None, "none") and _session(e).team_control is None)
        ctx.check(f"and doctor says so, got {_check_lineup()!r}", "none (roles off: one model for everything)" in _check_lineup())


@test
def test_a_set_team_is_never_changed_and_your_settings_win_the_default(ctx: Ctx):
    from halo_harness.lineup_default import lineup_in_use
    from halo_harness.theme import get_config_value, set_config_value
    with _Env() as e:
        set_config_value("team", "standard")
        s = _session(e)
        ctx.check("team: standard runs standard, not the default", s.team_control.name == "standard" and not s.team_control.default)
        ctx.check("a lineup you chose reports every member, as before", s.team_control.reports_for("orchestrator"))
        ctx.check("and stays written", get_config_value("team", default=None) == "standard" and lineup_in_use()[1] == "config")
        ctx.check("--team wins for one run", _session(e, team_name="quality").team_control.name == "quality")
        ctx.check("the Agent tool says nothing of auto under standard", "lineup is auto" not in s.tool_registry.get("Agent").description)
    with _Env() as e:
        set_config_value("roles.researcher", "or:mock/my-researcher")
        set_config_value("agents.max_depth", 3)
        s = _session(e)
        ctx.check(f"under the default your role table wins role by role, got {s.agent_runtime.role_table.get('researcher')}",
                  s.agent_runtime.role_table.get("researcher") == "or:mock/my-researcher"
                  and s.agent_runtime.role_table.get("planner") == "auto")
        ctx.check(f"and so does agents.max_depth, got runtime {s.agent_runtime.max_depth}", s.agent_runtime.max_depth is None)
        set_config_value("team", "auto")
        s = _session(e)
        ctx.check("team: auto set on purpose: the lineup wins", not s.team_control.default
                  and s.agent_runtime.role_table.get("researcher") == "auto" and s.agent_runtime.max_depth == 2)


class _Step:
    """The Team step's commit without a screen: the highlighted row is `name`."""

    def __init__(self, cwd, name):
        from halo_harness.tui.dialogs.team_step_actions import TeamActionsMixin
        self.state, self.app, self._name = SimpleNamespace(cwd=cwd, written=[]), SimpleNamespace(controller=None), name
        self.commit = lambda: TeamActionsMixin.commit(self)
        self._rows = lambda: TeamActionsMixin._rows(self)

    def _highlighted_lineup_name(self):
        return self._name


@test
def test_the_wizard_writes_nothing_for_the_default_and_no_team_standard(ctx: Ctx):
    from halo_harness.roles import roles_mode_enabled
    from halo_harness.theme import get_config_value, load_config, set_config_value
    from halo_harness.tui.dialogs import team_preview as tp
    with _Env() as e:
        rows = {r["name"]: r for r in _Step(e.cwd, "auto")._rows()}
        ctx.check("a fresh install: the auto row is the checked default, One model is not",
                  rows["auto"]["active"] and rows["auto"]["default"] and not rows[tp.ONE_MODEL_ID]["active"])
        step = _Step(e.cwd, "auto")
        step.commit()
        ctx.check(f"Next on the default row writes no team:, got {load_config()}", "team" not in load_config() and roles_mode_enabled())
        ctx.check(f"and says so, got {step.state.written}", step.state.written == ["lineup 'auto' in use (the default: no team: written)"])
        _Step(e.cwd, "balanced").commit()
        ctx.check("another lineup applies", get_config_value("team", default=None) == "balanced")
        _Step(e.cwd, "auto").commit()
        ctx.check("auto over a set team applies auto", get_config_value("team", default=None) == "auto")
        step = _Step(e.cwd, tp.ONE_MODEL_ID)
        step.commit()
        ctx.check(f"One model for everything: roles off and team: cleared, never standard, got {load_config()}",
                  "team" not in load_config() and not roles_mode_enabled())
        summary = tp.applied_summary_lines(cwd=e.cwd, default_model="or:mock/m")
        ctx.check(f"the Summary names one model, got {summary}", summary == ["One model for everything: or:mock/m"])
        set_config_value("roles.enabled", True)
        summary = tp.applied_summary_lines(cwd=e.cwd)
        ctx.check(f"with roles on and no team the Summary names the default and how to change it, got {summary[:2]}",
                  summary[0] == "Lineup: auto (the default; change it with `halo config set team <name>` or Studio Roles -> Apply)"
                  and "  planner: auto (picked at spawn)" in summary)
    with _Env() as e:
        set_config_value("team", "standard")
        rows = {r["name"]: r for r in _Step(e.cwd, "standard")._rows()}
        ctx.check("an existing user's team: standard keeps its check, auto is not the default",
                  rows["standard"]["active"] and not rows["auto"]["default"] and not rows["auto"]["active"])
        _Step(e.cwd, "standard").commit()
        ctx.check("and Next keeps it", get_config_value("team", default=None) == "standard")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
