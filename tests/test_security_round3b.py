"""tests.test_security_round3b -- 2.0.10 round 3, security fix pass 1,
trust-boundary findings 9-10 of docs/harness/SECURITY-REVIEW-2.0.10.md.

9   server names carrying `__` are rejected; rule suggestions keep the
    whole tool name and escape a literal `*`
10  a Databricks host chosen by a project `team.json` is https-only, named,
    and retyped before a token is stored for it
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()

os.environ.setdefault("BRIDGE_TEST_HOME", tempfile.mkdtemp(prefix="halo-sec3-home-"))


@contextlib.contextmanager
def _env(**values):
    """Set/clear env vars for one block (None clears), restoring every one."""
    saved = {k: os.environ.get(k) for k in values}
    try:
        for k, v in values.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _repo(project_settings: dict | None = None, mcp: dict | None = None) -> Path:
    cwd = Path(tempfile.mkdtemp(prefix="halo-sec3-repo-"))
    if project_settings is not None:
        (cwd / ".claude").mkdir()
        (cwd / ".claude" / "settings.json").write_text(json.dumps(project_settings), encoding="utf-8")
    if mcp is not None:
        (cwd / ".mcp.json").write_text(json.dumps({"mcpServers": mcp}), encoding="utf-8")
    return cwd




# ---- 9: `__` in server names; rule suggestions ----------------------------------


@test
def test_f9_server_name_with_double_underscore_is_rejected(ctx: Ctx):
    from halo_harness.mcp import manager as M
    cfg = M.parse_server("github__evil", {"command": "x"}, scope="project")
    ctx.check("disabled placeholder", cfg is not None and cfg.type == "invalid")
    ctx.check(f"reason names the separator: {cfg.disabled_reason}", "__" in (cfg.disabled_reason or ""))
    ok = M.parse_server("github-evil", {"command": "x"}, scope="project")
    ctx.check("a normal name still parses", ok is not None and ok.type == "stdio")
    resolved, _ = M.resolve_server_configs(cwd=_repo(None, {"a__b": {"command": "x"}}), claude_json={}, print_mode=True)
    ctx.check("resolve_server_configs does not register a usable a__b", resolved["a__b"].type == "invalid")


@test
def test_f9_suggest_rule_keeps_the_whole_mcp_tool_name(ctx: Ctx):
    import halo_harness.permissions as P
    tmp = Path(tempfile.mkdtemp())
    engine = P.PermissionEngine(mode="default", cwd=tmp)
    suggestion = engine.suggest_rule("mcp__srv__do__thing", {})
    ctx.check(f"suggestion is the full name, got {suggestion!r}", suggestion == "mcp__srv__do__thing")
    allow = P.parse_rule(suggestion, source="user", base_dir=tmp, action="allow")
    live = P.PermissionEngine(mode="default", cwd=tmp, allow_rules=[allow])
    ctx.check("the suggested rule matches the call it came from",
              live.decide("mcp__srv__do__thing", {}).action == "allow")
    ctx.check("server-only names still suggest the server rule", engine.suggest_rule("mcp__srv", {}) == "mcp__srv")


@test
def test_f9_suggest_rule_escapes_star_in_a_command_token(ctx: Ctx):
    import halo_harness.permissions as P
    tmp = Path(tempfile.mkdtemp())
    engine = P.PermissionEngine(mode="default", cwd=tmp)
    suggestion = engine.suggest_rule("Bash", {"command": "docker * --privileged"})
    ctx.check(f"star is escaped, got {suggestion!r}", suggestion == "Bash(docker \\*:*)")
    rule = P.parse_rule(suggestion, source="user", base_dir=tmp, action="allow")
    live = P.PermissionEngine(mode="default", cwd=tmp, allow_rules=[rule])
    ctx.check("the literal-star rule does not allow `docker ps`", live.decide("Bash", {"command": "docker ps"}).action != "allow")


# ---- 10: a project team.json chooses the Databricks host ---------------------------


def _team_cfg_from_project(host: str) -> dict:
    from halo_harness.team_config import load_team_config
    cwd = Path(tempfile.mkdtemp(prefix="halo-sec3-team-"))
    (cwd / ".halo").mkdir()
    (cwd / ".halo" / "team.json").write_text(json.dumps({"host": host}), encoding="utf-8")
    cfg, _w = load_team_config(cwd)
    return cfg


@test
def test_f10_team_host_problem_requires_https(ctx: Ctx):
    from halo_harness.team_config import team_host_problem
    ctx.check("https host ok", team_host_problem("https://your-workspace.cloud.databricks.com") is None)
    for bad in ("http://your-workspace.cloud.databricks.com", "ftp://x", "your-workspace.cloud.databricks.com",
                "https://", "", None, "https://a b.example.com"):
        ctx.check(f"rejected {bad!r}", team_host_problem(bad) is not None)


@test
def test_f10_project_team_json_host_is_not_prefilled_in_the_wizard(ctx: Ctx):
    from halo_harness.init_cli import _known_databricks_host
    from halo_harness.init_providers import tab_credential_state
    from halo_harness.providers import config as pc
    host = "https://your-workspace.cloud.databricks.com"
    cfg = _team_cfg_from_project(host)
    ctx.check("the preset records that it is a project file", cfg.get("_project_file") is True)
    real_resolve = pc.resolve_databricks
    try:
        pc.resolve_databricks = lambda *a, **k: None
        import halo_harness.init_cli as ic
        real_known, ic._known_databricks_host = _known_databricks_host, (lambda: None)
        try:
            state = tab_credential_state("databricks", team_cfg=cfg)
        finally:
            ic._known_databricks_host = real_known
    finally:
        pc.resolve_databricks = real_resolve
    ctx.check("known_host is not set from a project file", not state.get("known_host"))
    ctx.check("the host is offered as a hint naming the file", state.get("host_hint") == host
              and "team.json" in str(state.get("source")))
    ctx.check("a host field is asked for", any(f["name"] == "host" for f in state["fields"]))
    from halo_harness.init_providers import _safe_team_host
    ctx.check("save_tab_credentials will not fall back to it", _safe_team_host(cfg) == "")
    user_cfg = dict(cfg, _project_file=False)
    ctx.check("a user-level preset host is still used", _safe_team_host(user_cfg) == host)
    ctx.check("an http host is never used", _safe_team_host({"host": "http://x.example.com"}) == "")


def _run_ensure_creds(team_cfg: dict, typed: list, yes: bool = False):
    import halo_harness.init_cli as ic
    from halo_harness.providers import config as pc
    from rich.console import Console
    writes: dict = {}
    out = io.StringIO()
    patches = {
        (pc, "resolve_databricks"): lambda *a, **k: None,
        (ic, "_known_databricks_host"): lambda: None,
        (ic, "_load_team_config"): lambda args, console: team_cfg,
        (ic, "_prompt_plain"): lambda label: typed.pop(0) if typed else "",
        (ic, "_prompt_secret"): lambda label: "fake-token-value",
        (ic, "_env_file_path"): lambda: Path(tempfile.mkdtemp(prefix="halo-sec3-env-")) / "env",
        (ic, "_write_env_var"): lambda path, name, value: writes.__setitem__(name, value),
    }
    saved = {k: getattr(k[0], k[1]) for k in patches}
    try:
        for (mod, name), fn in patches.items():
            setattr(mod, name, fn)
        with _env(DATABRICKS_HOST=None, DATABRICKS_TOKEN=None):
            ic._ensure_databricks_creds(SimpleNamespace(yes=yes, team=None), Console(file=out, width=200))
            os.environ.pop("DATABRICKS_HOST", None)
            os.environ.pop("DATABRICKS_TOKEN", None)
    finally:
        for (mod, name), fn in saved.items():
            setattr(mod, name, fn)
    return writes, out.getvalue()


@test
def test_f10_init_requires_retyping_a_project_file_host(ctx: Ctx):
    host = "https://your-workspace.cloud.databricks.com"
    cfg = _team_cfg_from_project(host)
    writes, out = _run_ensure_creds(cfg, [host])
    ctx.check("the file is named in the output", "team.json" in out and "project folder" in out)
    ctx.check(f"retyped host is written, got {writes}", writes.get("DATABRICKS_HOST") == host)
    writes, out = _run_ensure_creds(_team_cfg_from_project(host), ["https://other.example.com", ""])
    ctx.check(f"a different typed host is not the project's, got {writes}",
              writes.get("DATABRICKS_HOST") != host)
    writes, out = _run_ensure_creds(_team_cfg_from_project(host), [], yes=True)
    ctx.check(f"--yes cannot confirm a project-file host, got {writes}", "DATABRICKS_HOST" not in writes)


@test
def test_f10_init_ignores_a_non_https_team_host(ctx: Ctx):
    cfg = _team_cfg_from_project("http://attacker.example.com")
    writes, out = _run_ensure_creds(cfg, [])
    ctx.check("warning names the problem", "https" in out)
    ctx.check(f"no token stored for it, got {writes}", "DATABRICKS_HOST" not in writes)


@test
def test_f10_user_level_team_json_host_keeps_working(ctx: Ctx):
    host = "https://your-workspace.cloud.databricks.com"
    cfg = dict(_team_cfg_from_project(host), _project_file=False)
    writes, out = _run_ensure_creds(cfg, [])
    ctx.check(f"user-level host used with only the token asked for, got {writes}", writes.get("DATABRICKS_HOST") == host)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
