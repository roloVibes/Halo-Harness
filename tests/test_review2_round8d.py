"""tests.test_review2_round8d -- pins for the vibes/review.md fix pass,
round 8, the last three (findings 61, 62, 64):

  * f61  an agent file's `tools: Agent(X)` restriction never reached the
        sub-agent it describes
  * f62  agent export wrote snake_case keys the loader does not read
  * f64  a worktree leaked when the model failed to resolve (3.1.4.0: the
        org halves of f64 went with Org)
"""
from __future__ import annotations

import os
import subprocess
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


# ---- f61: tools: Agent(X) reaches the child -----------------------------------

@test
def test_f61_agent_file_tools_restriction_reaches_the_child(ctx: Ctx):
    from halo_harness.agent.subagent import _build_child_session
    from halo_harness.config.agents_md import AgentSpec
    fh = build_fake_home()
    mock = MockUpstream().start()
    try:
        session = _session(fh, mock)
        rt = session.agent_runtime

        def _child_restriction(spec):
            child, _ = _build_child_session(runtime=rt, spec=spec, agent_id="r8f61" + spec.name[:3],
                                            model_override=None, parent_tool_use_id="t")
            return child.agent_type_restriction

        restricted = AgentSpec(name="rst", description="d", tools=["Read", "Agent(Explore)", "Task(Plan)"])
        ctx.check("Agent(X)/Task(Y) entries become the child's allowed types",
                  _child_restriction(restricted) == {"Explore", "Plan"})
        ctx.check("a bare Agent grant means no restriction",
                  _child_restriction(AgentSpec(name="bare", description="d", tools=["Read", "Agent"])) is None)
    finally:
        mock.stop()
        _restore_home()


# ---- f62: export writes the keys the loader reads -----------------------------

@test
def test_f62_export_round_trips_permission_mode_mcp_servers_and_max_turns(ctx: Ctx):
    from halo_harness.agents_md_bridge import bio_from_agent_spec, frontmatter_text_from_bio
    from halo_harness.config.agents_md import load_spec_from_file
    tmp = Path(tempfile.mkdtemp(prefix="r8-f62-"))
    src = tmp / "src.md"
    src.write_text("---\nname: rt\ndescription: round trip\npermissionMode: acceptEdits\nmaxTurns: 7\n"
                   "mcpServers:\n  - docs\n---\n\nBody text.\n", encoding="utf-8")
    spec = load_spec_from_file(src, source="user")
    bio = bio_from_agent_spec(spec)
    text = frontmatter_text_from_bio(bio)
    for key in ("permissionMode:", "maxTurns:", "mcpServers:"):
        ctx.check(f"the export carries {key}", key in text)
    for bad in ("permission_mode", "max_turns", "mcp_servers"):
        ctx.check(f"the export carries no {bad}", bad not in text)
    out = tmp / "out.md"
    out.write_text(text, encoding="utf-8")
    back = load_spec_from_file(out, source="user")
    ctx.check(f"the loader reads them back, got {(back.permission_mode, back.max_turns, back.mcp_servers)}",
              (back.permission_mode, back.max_turns, back.mcp_servers) == ("acceptEdits", 7, ["docs"]))


# ---- f64: leaks ----------------------------------------------------------------

def _git_repo(path: Path) -> None:
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    for args in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "init"]):
        subprocess.run(["git", *args], cwd=str(path), env=env, capture_output=True, check=True)


@test
def test_f64_a_failed_model_resolve_does_not_leak_the_isolation_worktree(ctx: Ctx):
    from halo_harness.agent.subagent import _build_child_session
    from halo_harness.config.agents_md import AgentSpec
    fh = build_fake_home()
    (fh["proj"] / "README.txt").write_text("x\n", encoding="utf-8")
    _git_repo(fh["proj"])
    mock = MockUpstream().start()
    try:
        session = _session(fh, mock)
        spec = AgentSpec(name="iso", description="d", isolation="worktree")
        raised = None
        try:
            _build_child_session(runtime=session.agent_runtime, spec=spec, agent_id="r8f64",
                                 model_override="definitely not a model ref", parent_tool_use_id="t")
        except Exception as e:
            raised = e
        ctx.check(f"the bad model still raises to the caller, got {raised!r}", raised is not None)
        trees = Path(session.state_dir) / "worktrees"
        left = [p for p in trees.rglob("agent-r8f64*")] if trees.exists() else []
        ctx.check(f"no worktree directory is left behind, got {left}", left == [])
        branches = subprocess.run(["git", "branch", "--list", "halo-worktree-*"], cwd=str(fh["proj"]),
                                  capture_output=True, text=True).stdout.strip()
        ctx.check(f"no halo-worktree branch is left either, got {branches!r}", branches == "")
    finally:
        mock.stop()
        _restore_home()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
