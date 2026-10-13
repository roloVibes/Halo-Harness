"""tests.test_review3_b -- pins for the 3.0.1.0 review fix pass, round
B-trust (part 1): review items 4, 5 and 18.

  * item 4   a sub-agent's mode: plan is sticky, dontAsk ranks below
             default, and the team template's mode is clamped like any
             other request; a project team template in an untrusted folder
             keeps its deny/ask rules but loses its mode and allow rules
  * item 5   connector__<slug>: `tool` must be one tool name of that
             connector, and the session's whole-tool denies reach the
             inner claude's --disallowedTools
  * item 18  an untrusted project/local settings layer cannot set
             permissions.defaultMode, disableAllHooks or plansDirectory
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.fake_home import build_fake_home
from tests.helpers.mock_openai import MockUpstream
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials
from tests.test_review2_round8 import _restore_home, _session

ensure_default_provider_credentials()

test, TESTS = new_registry()

_ENV_KEYS = ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "CLAUDE_CONFIG_DIR")


class _Env:
    """Snapshot/restore of the home-scoping variables a test changes."""

    def __enter__(self):
        self._snap = {k: os.environ.get(k) for k in _ENV_KEYS}
        self.home = Path(tempfile.mkdtemp(prefix="r3b-home-"))
        os.environ["BRIDGE_TEST_HOME"] = str(self.home)
        os.environ["BRIDGE_STATE_DIR"] = str(self.home / ".halo")
        os.environ.pop("CLAUDE_CONFIG_DIR", None)
        return self

    def __exit__(self, *exc):
        for k, v in self._snap.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# ---- item 4: sub-agent mode clamp ---------------------------------------------

def _child(parent_mode: str, *, spec_mode=None, source="user", team_perms=None):
    from halo_harness.agent.subagent import _build_child_session
    from halo_harness.config.agents_md import AgentSpec
    from halo_harness.permissions import PermissionEngine
    from halo_harness.teams_runtime import TeamControl
    fh = build_fake_home()
    mock = MockUpstream().start()
    try:
        session = _session(fh, mock)
        session.permission_engine = PermissionEngine(mode=parent_mode, cwd=fh["proj"])
        rt = session.agent_runtime
        rt.team_control = TeamControl(name="t", template={"permissions": team_perms}) if team_perms else None
        spec = AgentSpec(name="x", description="d", permission_mode=spec_mode, source=source)
        child, _ = _build_child_session(runtime=rt, spec=spec, agent_id="r3b4" + parent_mode[:3],
                                        model_override=None, parent_tool_use_id="t")
        return child, fh["proj"]
    finally:
        mock.stop()
        _restore_home()


@test
def test_item4_plan_parent_keeps_an_accept_edits_agent_in_plan(ctx: Ctx):
    child, proj = _child("plan", spec_mode="acceptEdits")
    ctx.check(f"child mode is plan, got {child.permission_engine.mode!r}", child.permission_engine.mode == "plan")
    decision = child.permission_engine.decide("Write", {"file_path": str(proj / "f.txt"), "content": "x"})
    ctx.check(f"a Write in the folder is denied in the child, got {decision.action!r}", decision.action == "deny")


@test
def test_item4_team_mode_is_clamped_to_the_parent(ctx: Ctx):
    child, _ = _child("default", team_perms={"mode": "bypassPermissions", "rules": {"allow": ["Bash(*)"]}})
    ctx.check(f"default parent + team bypass -> default, got {child.permission_engine.mode!r}",
              child.permission_engine.mode == "default")
    child, _ = _child("plan", team_perms={"mode": "acceptEdits"})
    ctx.check(f"plan parent + team acceptEdits -> plan, got {child.permission_engine.mode!r}",
              child.permission_engine.mode == "plan")
    child, _ = _child("auto", team_perms={"mode": "default"})
    ctx.check(f"lowering still works: auto parent + team default -> default, got {child.permission_engine.mode!r}",
              child.permission_engine.mode == "default")


@test
def test_item4_dont_ask_parent_is_not_escaped(ctx: Ctx):
    child, _ = _child("dontAsk", spec_mode="acceptEdits")
    ctx.check(f"dontAsk parent + acceptEdits agent -> dontAsk, got {child.permission_engine.mode!r}",
              child.permission_engine.mode == "dontAsk")
    child, _ = _child("bypassPermissions", spec_mode="acceptEdits")
    ctx.check(f"an owner agent may still lower itself, got {child.permission_engine.mode!r}",
              child.permission_engine.mode == "acceptEdits")


def _write_team(cwd: Path, name: str, data: dict) -> None:
    d = cwd / ".halo" / "teams"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.yaml").write_text(json.dumps(data), encoding="utf-8")


@test
def test_item4_untrusted_project_template_loses_mode_and_allow(ctx: Ctx):
    from halo_harness.teams_runtime import load_team_control
    from halo_harness.teams_yaml import resolve_team_template
    with _Env() as e:
        cwd = e.home / "repo"
        perms = {"mode": "bypassPermissions", "rules": {"allow": ["Bash(*)"], "deny": ["Bash(rm:*)"],
                                                         "ask": ["Write"]}}
        _write_team(cwd, "base", {"agents": [], "permissions": perms})
        _write_team(cwd, "dev", {"extends": "base", "agents": []})
        untrusted = resolve_team_template("dev", cwd=cwd, state_dir=e.home / ".halo", trusted=False)
        got = untrusted["permissions"]
        ctx.check(f"mode dropped through extends, got {got!r}", "mode" not in got)
        ctx.check("allow dropped", "allow" not in got.get("rules", {}))
        ctx.check("deny and ask kept", got["rules"].get("deny") == ["Bash(rm:*)"] and got["rules"].get("ask") == ["Write"])
        trusted = resolve_team_template("dev", cwd=cwd, state_dir=e.home / ".halo", trusted=True)
        ctx.check("a trusted folder keeps them", trusted["permissions"].get("mode") == "bypassPermissions")
        control = load_team_control("dev", cwd=cwd, state_dir=e.home / ".halo", trusted=False)
        member = control.member_permissions()
        ctx.check(f"the team control sees no mode/allow, got {member!r}",
                  member["mode"] is None and member["allow"] == [] and member["deny"] == ["Bash(rm:*)"])


@test
def test_item4_user_template_is_not_filtered(ctx: Ctx):
    from halo_harness.teams_yaml import resolve_team_template, save_team_template
    with _Env() as e:
        ok, problems = save_team_template("mine", {"agents": [], "permissions": {"mode": "auto"}},
                                          state_dir=e.home / ".halo")
        ctx.check(f"saved, got {problems}", ok)
        got = resolve_team_template("mine", cwd=e.home / "elsewhere", state_dir=e.home / ".halo", trusted=False)
        ctx.check("the owner's own template keeps its mode", got["permissions"].get("mode") == "auto")


# ---- item 5: connector tool name ----------------------------------------------

def _connector_argv(tool_input: dict, deny=()):
    from halo_harness.mcp.connectors import ConnectorInfo
    from halo_harness.permissions import PermissionEngine, parse_rule
    from halo_harness.providers import cc_models
    from halo_harness.tools import _proc
    from halo_harness.tools.base import ToolContext
    from halo_harness.tools.connector_tool import ConnectorTool
    info = ConnectorInfo(name="Gmail", slug="gmail", account_token="Gmail", tools=["search_emails", "send"])
    seen = []
    real_argv, real_run = cc_models.resolve_claude_launch_argv, _proc.run_streamed
    cc_models.resolve_claude_launch_argv = lambda *a, **k: ["claude"]
    _proc.run_streamed = lambda argv, **k: (seen.append(argv) or ('{"result": "ok"}', 0, False, False))
    try:
        engine = PermissionEngine(deny_rules=[parse_rule(r, action="deny") for r in deny], cwd=Path("."))
        result = ConnectorTool(info).run(tool_input, ToolContext(cwd=Path("."), permission_engine=engine))
    finally:
        cc_models.resolve_claude_launch_argv, _proc.run_streamed = real_argv, real_run
    return result, (seen[0] if seen else None)


def _flag(argv, name):
    return argv[argv.index(name) + 1] if argv and name in argv else None


@test
def test_item5_a_tool_list_never_reaches_allowed_tools(ctx: Ctx):
    for bad in ("search_emails,Bash", "search_emails Bash", "search_*", "nope"):
        result, argv = _connector_argv({"request": "r", "tool": bad})
        ctx.check(f"{bad!r} is an error with no spawn, got argv={argv}", result.is_error and argv is None)
    result, argv = _connector_argv({"request": "r", "tool": "search_emails"})
    ctx.check(f"one known tool passes as one exact name, got {_flag(argv, '--allowedTools')!r}",
              _flag(argv, "--allowedTools") == "mcp__claude_ai_Gmail__search_emails")
    result, argv = _connector_argv({"request": "r", "tool": "mcp__claude_ai_Gmail__send"})
    ctx.check("the full mcp__ name is accepted too", _flag(argv, "--allowedTools") == "mcp__claude_ai_Gmail__send")


@test
def test_item5_session_whole_tool_denies_reach_the_inner_claude(ctx: Ctx):
    _result, argv = _connector_argv({"request": "r"},
                                    deny=("Bash", "Write", "mcp__github", "Bash(rm -rf *)", "connector__gmail(send)"))
    disallowed = (_flag(argv, "--disallowedTools") or "").split(",")
    ctx.check(f"Bash/Write/mcp server/per-tool deny forwarded, got {disallowed}",
              {"Bash", "Write", "mcp__github", "mcp__claude_ai_Gmail__send"} <= set(disallowed))
    ctx.check("a content rule with spaces is not spliced in", not any(" " in d for d in disallowed))


# ---- item 18: untrusted settings layer ----------------------------------------

@test
def test_item18_untrusted_layer_cannot_set_mode_hooks_switch_or_plans_dir(ctx: Ctx):
    from halo_harness.config.settings import resolve_settings
    with _Env() as e:
        repo = e.home / "repo"
        (repo / ".claude").mkdir(parents=True)
        body = {"permissions": {"defaultMode": "acceptEdits", "deny": ["Read(./.env)"]},
                "disableAllHooks": True, "plansDirectory": str(e.home / ".claude" / "agents")}
        (repo / ".claude" / "settings.json").write_text(json.dumps(body), encoding="utf-8")
        s = resolve_settings(repo, trusted=False)
        ctx.check(f"defaultMode dropped, got {s.permissions_default_mode!r}", s.permissions_default_mode is None)
        ctx.check("disableAllHooks dropped", s.disable_all_hooks is False)
        ctx.check(f"plansDirectory dropped, got {s.plans_directory!r}", s.plans_directory is None)
        ctx.check("deny rules kept", "Read(./.env)" in s.raw.get("permissions", {}).get("deny", []))
        t = resolve_settings(repo, trusted=True)
        ctx.check("a trusted folder keeps all three", t.permissions_default_mode == "acceptEdits"
                  and t.disable_all_hooks is True and t.plans_directory)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
