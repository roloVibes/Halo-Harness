"""tests.test_init_wizard_round7_integration -- Halo 2.0.2 round 7 (init
wizard brief): the wiring pieces that sit between the pure-logic additions
in tests/test_init_wizard_round7.py and a real session -- the slash-menu/
tips discoverability gating (`roles.enabled`), the Agent tool's schema
(3.1.4.0: no `org` parameter), the shared task board's new `kind`/`parent`
fields and `halo setup`'s no-TTY fallback.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials

ensure_default_provider_credentials()

test, TESTS = new_registry()


def _fresh_state_dir(prefix: str) -> Path:
    d = Path(tempfile.mkdtemp(prefix=prefix))
    os.environ["BRIDGE_STATE_DIR"] = str(d)
    return d


def _clear_state_dir_env() -> None:
    os.environ.pop("BRIDGE_STATE_DIR", None)


# ---- commands/registry.py: hidden command names ----------------------------

@test
def test_hidden_command_names_follows_the_mode_switches(ctx: Ctx):
    from halo_harness.commands.registry import Registry, SlashCommand
    from halo_harness.theme import set_config_value
    _fresh_state_dir("registry-hidden-")
    try:
        reg = Registry()
        reg.add(SlashCommand(name="roles", description="d"))
        reg.add(SlashCommand(name="role", description="d"))
        reg.add(SlashCommand(name="setup", description="d"))
        set_config_value("roles.enabled", False)
        set_config_value("orgs.enabled", False)  # 3.1.4.0: a leftover section hides nothing
        names = {c.name for c in reg.all()}
        ctx.check(f"roles/role hidden, setup never hidden, got {names}", names == {"setup"})
        ctx.check("help_rows() agrees", {row[0] for row in reg.help_rows()} == {"/setup"})
        ctx.check("completion for an empty prefix agrees too",
                  {c.name for c in reg.complete("")} == {"setup"})
        set_config_value("roles.enabled", True)
        names2 = {c.name for c in reg.all()}
        ctx.check(f"all three visible once roles are on, got {names2}",
                  names2 == {"roles", "role", "setup"})
        ctx.check("resolve() ALWAYS works regardless of hiding (never a functional gate)",
                  reg.resolve("roles") is not None)
    finally:
        _clear_state_dir_env()


# ---- tools/agent.py: no org= parameter (3.1.4.0) ----------------------------

@test
def test_agent_tool_schema_has_no_org(ctx: Ctx):
    from halo_harness.tools.agent import AgentTool
    from halo_harness.theme import set_config_value
    _fresh_state_dir("agent-tool-schema-")
    try:
        tool = AgentTool()
        for on in (False, True):  # a leftover orgs.enabled changes nothing
            set_config_value("orgs.enabled", on)
            ctx.check(f"no org in the schema (orgs.enabled {on})", "org" not in tool.input_schema["properties"])
            ctx.check(f"the description names no organization (orgs.enabled {on})", "organization" not in tool.description.lower())
    finally:
        _clear_state_dir_env()


# ---- tools/task_board.py: kind="goal" / parent -----------------------------

@test
def test_create_task_goal_and_parent_linking(ctx: Ctx):
    from halo_harness.tools.task_board import create_task, read_board
    session_dir = Path(tempfile.mkdtemp(prefix="task-board-goal-"))
    goal_id = create_task(session_dir, title="Goal: ship it", kind="goal")
    child_id = create_task(session_dir, title="write the brief", parent=goal_id)
    board = read_board(session_dir)
    ctx.check(f"two tasks on the board, got {len(board)}", len(board) == 2)
    goal = next(t for t in board if t["id"] == goal_id)
    child = next(t for t in board if t["id"] == child_id)
    ctx.check(f"goal task kind, got {goal.get('kind')}", goal.get("kind") == "goal")
    ctx.check("goal task has no parent of its own", goal.get("parent") is None)
    ctx.check(f"child points at the goal, got {child.get('parent')}", child.get("parent") == goal_id)
    ctx.check("a plain pre-round-7 task (no kind/parent given) still defaults to kind=task",
              create_task(session_dir, title="plain") and
              next(t for t in read_board(session_dir) if t["title"] == "plain")["kind"] == "task")


@test
def test_task_create_tool_accepts_an_optional_parent(ctx: Ctx):
    from halo_harness.tools.base import ToolContext
    from halo_harness.tools.task_board import TaskCreateTool, read_board
    session_dir = Path(tempfile.mkdtemp(prefix="task-board-tool-"))
    tool = TaskCreateTool()
    r1 = tool.run({"title": "Goal: ship it"}, ToolContext(cwd=session_dir, session_dir=session_dir))
    goal_id = r1.content.split("'")[1]
    r2 = tool.run({"title": "write the brief", "parent": goal_id},
                  ToolContext(cwd=session_dir, session_dir=session_dir))
    ctx.check(f"second create succeeds, got {r2.content}", not r2.is_error)
    board = read_board(session_dir)
    child = next(t for t in board if t["title"] == "write the brief")
    ctx.check(f"parent carried through the Tool, got {child.get('parent')}", child.get("parent") == goal_id)


# ---- halo setup: CLI-level pins ----------------------------------------------

class _IsattyProxy:
    def __init__(self, value: bool, real):
        self._value, self._real = value, real

    def isatty(self) -> bool:
        return self._value

    def __getattr__(self, name):
        return getattr(self._real, name)


def _no_tty(fn, *args):
    real_stdin, real_stdout = sys.stdin, sys.stdout
    sys.stdin, sys.stdout = _IsattyProxy(False, real_stdin), _IsattyProxy(False, real_stdout)
    try:
        return fn(*args)
    finally:
        sys.stdin, sys.stdout = real_stdin, real_stdout


@test
def test_halo_setup_no_tty_lists_templates_and_exits_0(ctx: Ctx):
    """Brief's own pin: "halo setup roles with no TTY lists templates and
    exits 0"."""
    from halo_harness.setup_cli import cmd_setup
    _fresh_state_dir("setup-cli-roles-")
    try:
        rc = _no_tty(cmd_setup, ["roles"])
        ctx.check(f"exit 0, got {rc}", rc == 0)
    finally:
        _clear_state_dir_env()
    _fresh_state_dir("setup-cli-orgs-")
    try:
        rc = _no_tty(cmd_setup, ["orgs"])
        ctx.check(f"halo setup orgs (removed in 3.1.4.0): a usage error, got {rc}", rc == 2)
    finally:
        _clear_state_dir_env()
    _fresh_state_dir("setup-cli-bare-")
    try:
        rc = _no_tty(cmd_setup, [])
        ctx.check(f"bare halo setup: exit 0 too, got {rc}", rc == 0)
        rc_bad = _no_tty(cmd_setup, ["not-a-real-subcommand"])
        ctx.check(f"an unknown subcommand is a clean usage error, got {rc_bad}", rc_bad == 2)
    finally:
        _clear_state_dir_env()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
