"""halo_harness.agent.subagent -- the Agent/Task tool's real implementation
(H6 scope B): `AgentRuntime` (what a session's Agent-tool calls need beyond
a bare ToolContext), spawning a child `agent.loop.Session` per call with a
fresh log under `<parent_session_dir>/subagents/agent-<id>.jsonl` (+ a
`.meta.json` beside it), depth-1 + <=4-concurrent enforcement, background
completion delivered as a user-role notice on the PARENT's next turn (dsh:
"background jobs ... report completion as a user-role notice in the next
step"), resumable `task_id` (`<task_result task_id="...">` wrapping, OpenCode
adopt item), and SubagentStart/SubagentStop hook firing (tagged with the
child's own `agent_id`/`agent_type` via its own HookRunner).

`agent/loop.py`'s `_dispatch_tools` calls `run_agent_call` DIRECTLY (a
dedicated code path, like AskUserQuestion/ExitPlanMode -- never through the
generic `tool_registry.dispatch()`) so it can run several calls
CONCURRENTLY (a real `ThreadPoolExecutor`, up to `MAX_CONCURRENT_AGENTS`)
and still forward every child event, tagged, into the parent's own event
stream once the batch completes. `tools/agent.py`'s `AgentTool.run()` calls
the SAME function as a correctness fallback for any caller that dispatches
it generically instead (a unit test, or a future caller) -- it still does
the real work, just without the intermediate child events being visible.

H5c finding 8: a FOREGROUND child session's own permission "ask" is now
surfaced LIVE (an agent-tagged, answerable `permission_request` card),
never auto-denied, whenever the PARENT is interactive -- `child.
_subagent_live_asks` (set below, deliberately never `child.interactive`
itself, which also gates AskUserQuestion/ExitPlanMode -- out of this
finding's scope and would otherwise hang a child forever on those, since
only `_permission_waiters` is shared, not `_question_waiters`/
`_plan_waiters`) and a shared `_permission_waiters` dict (same pattern as
the shared `abort` Event) are what make this possible: the child's own
`_resolve_tool_call` parks its waiter in the SAME dict the PARENT's
`resolve_permission` (the UI's `Controller.answer_permission`) already
reads from, so the existing card-answer plumbing needs no changes at all.
This REQUIRES `_run_child_to_completion` to stream every child event live
(the `on_event` callback below) rather than buffer the whole turn into a
list first -- a child blocked waiting for its own permission answer would
never finish "buffering" in the first place, so its `permission_request`
would never reach anything. A BACKGROUND child (`run_in_background`/
`spec.background`) is deliberately EXCLUDED (`_subagent_live_asks` stays
False for it): its events are never forwarded to any live stream at all
(see `_bg_run`'s own `del child_events` below), so a live card for it
would have nowhere to be shown and would just hang the background thread
-- it keeps the old immediate-denial fallback instead. Print mode (`-p`,
`parent.interactive` False) also keeps the old fallback for every child,
foreground or not: deny + `permission_denials`, exactly like Claude
Code's own "print mode -> deny" rule for every session, not just `-p`
itself.
"""

from __future__ import annotations

import json
import logging
import subprocess
import threading
import time
import uuid
import contextlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from halo_harness import events
from halo_harness.agent import agent_hooks as _agent_tree
from halo_harness.agent.agent_inbox import handback as _fleet_handback, was_stopped as _fleet_stopped

log = logging.getLogger("bridge")
from halo_harness.config.agents_md import AgentSpec, resolve_agent_model

MAX_CONCURRENT_AGENTS = 4
MAX_DEPTH = 1
RESULT_CAP = 30_000


def effective_max_concurrent(runtime: "AgentRuntime") -> int:
    """Halo 2.0.2 round 2 (brief B): concurrency from `agents.max_
    concurrent` (config, default 4) unless the runtime carries its own
    `max_concurrent` (a team's `delegation.max_parallel`, set on the
    session's runtime by agent/loop.py and copied to every descendant by
    `_build_child_session`), which wins outright; the default is the
    original hardcoded `MAX_CONCURRENT_AGENTS`. Never raises: a bad value
    (not an int, <= 0) falls back to that same default."""
    candidate = runtime.max_concurrent
    if candidate is None:
        from halo_harness.theme import get_config_value
        candidate = get_config_value("agents.max_concurrent", default=MAX_CONCURRENT_AGENTS)
    try:
        value = int(candidate)
        return value if value > 0 else MAX_CONCURRENT_AGENTS
    except (TypeError, ValueError):
        return MAX_CONCURRENT_AGENTS


def effective_max_depth(runtime: "AgentRuntime") -> int:
    """Halo 2.0.2 round 3 (brief C): "agents.max_depth (default 1, up to
    3)" -- mirrors `effective_max_concurrent`'s own shape exactly. The
    runtime's own `max_depth` (a lineup's `delegation.max_depth`, set by
    agent/loop.py) wins outright, not clamped to 3. Only the
    CONFIG-sourced value is clamped to [1, 3]; a bad/missing/out-of-range one falls back to the original
    hardcoded `MAX_DEPTH=1` so every pre-2.0.2-round-3 session behaves
    exactly as before this knob existed. Never raises."""
    if runtime.max_depth is not None:
        try:
            value = int(runtime.max_depth)
            return value if value > 0 else MAX_DEPTH
        except (TypeError, ValueError):
            return MAX_DEPTH
    from halo_harness.theme import get_config_value
    candidate = get_config_value("agents.max_depth", default=MAX_DEPTH)
    try:
        value = int(candidate)
    except (TypeError, ValueError):
        return MAX_DEPTH
    return value if 1 <= value <= 3 else MAX_DEPTH


class SessionConcurrencyGate:
    """2.0.2 review finding 10 (major): a bounded gate shared by
    reference down the WHOLE tree (`AgentRuntime.concurrency_semaphore`,
    propagated by `_build_child_session`), acquired around each child's own run in
    EVERY spawn path -- single, fan-out, resume -- so the session-
    wide concurrency cap is real: two separate `count` calls in one turn
    (or nested levels) can no longer multiply past it just because each
    one's own `ThreadPoolExecutor` pool is independently sized.

    Deliberately NOT a bare `threading.Semaphore`: a child delegating to
    a grandchild is logically one more hop of the SAME call already
    holding a slot, but PHYSICALLY it runs on a brand new pool-worker
    thread -- even a lone Agent tool_use goes through `agent/loop.py`'s
    `_run_agent_batch`, which always builds its own `ThreadPoolExecutor`
    (`max_workers=min(cap, 1)` for exactly one call). A bare semaphore
    sized below the nesting depth deadlocks: the OUTER thread blocks
    waiting (`queue.Queue.get()`) for the inner pool's worker to finish,
    while that worker blocks waiting for the very slot the outer thread
    is holding. Verified directly (a traced plain-semaphore substitute
    produced exactly this hang on a 2-level chain at cap=1).

    Fixed with EXPLICIT nesting-depth handoff across the thread
    boundary: `wrap_for_pool`, called on the SUBMITTING thread right
    before `pool.submit`, captures that thread's current depth and
    returns a wrapper which seeds the SAME depth onto whichever worker
    thread the pool actually runs it on (restored afterward, since pool
    threads are reused across unrelated later jobs). A plain `threading.
    local` alone cannot do this -- a new thread never inherits another
    thread's local storage, pool-reused or not."""

    def __init__(self, value: int) -> None:
        # A counter under a Condition rather than a Semaphore, so the cap
        # can change while slots are held: `agents.max_concurrent` is read
        # again at every spawn (`set_limit`), which is how a config change
        # during a session applies to the next spawn instead of the next
        # session (the test that found this wrote the config after the
        # Session was built, exactly what `/setup` does).
        self._limit = max(1, int(value))
        self._active = 0
        self._cv = threading.Condition()
        self._local = threading.local()

    def set_limit(self, value) -> None:
        try:
            limit = max(1, int(value))
        except (TypeError, ValueError):
            return
        with self._cv:
            self._limit = limit
            self._cv.notify_all()

    @property
    def limit(self) -> int:
        return self._limit

    def _acquire(self) -> None:
        with self._cv:
            while self._active >= self._limit:
                self._cv.wait()
            self._active += 1

    def _release(self) -> None:
        with self._cv:
            self._active = max(0, self._active - 1)
            self._cv.notify_all()

    def __enter__(self) -> "SessionConcurrencyGate":
        depth = getattr(self._local, "depth", 0)
        if depth == 0:
            self._acquire()
        self._local.depth = depth + 1
        return self

    def __exit__(self, *exc_info) -> bool:
        self._local.depth -= 1
        if self._local.depth == 0:
            self._release()
        return False

    def wrap_for_pool(self, fn: Callable) -> Callable:
        """Call on the thread about to `pool.submit(...)` a job that may
        itself (directly or several Agent-dispatch hops later) try to
        enter THIS gate again -- never on the pool worker thread itself.
        The returned callable, run on whatever thread the pool actually
        picks, inherits this submitting thread's CURRENT depth for its
        own duration, then restores whatever depth that worker thread
        had before (0 for a fresh one; otherwise whatever an EARLIER,
        unrelated job left it at -- pool threads are reused)."""
        # Fix pass A, found by the session-wide test on all three platforms:
        # seeding the worker with the SUBMITTING thread's depth let every
        # fan-out child skip the semaphore whenever the submitter already
        # held a slot (two `batch` calls, cap 2, peaked at 4). A pool worker
        # now starts OUTSIDE the gate and takes a real slot; the submitting
        # thread gives its own slot back for as long as it waits on the
        # pool (`released()` / `pool()` below), which is what keeps a
        # nested chain at cap 1 from deadlocking: a parent blocked on its
        # children is not running.
        inherited = 0

        def _wrapped(*args, **kwargs):
            prev = getattr(self._local, "depth", 0)
            self._local.depth = inherited
            try:
                return fn(*args, **kwargs)
            finally:
                self._local.depth = prev
        return _wrapped

    @contextlib.contextmanager
    def released(self):
        """Give this thread's slot back while it blocks on children, and
        take it again afterwards (a no-op for a thread outside the gate).
        The per-thread depth is kept as it is, so the thread is still
        "inside" the gate logically and its own `__exit__` still balances."""
        depth = getattr(self._local, "depth", 0)
        if depth > 0:
            self._release()
        try:
            yield
        finally:
            if depth > 0:
                self._acquire()

    def pool(self, max_workers: int, limit: "Optional[int]" = None) -> "_GatedPool":
        """A `ThreadPoolExecutor` stand-in for the two spawn sites: the
        submitting thread's slot is released for the whole `with` block
        and re-taken on exit, every submitted job runs outside the gate so
        its own `with gate:` acquires a real slot, and `limit` (the cap
        read from config or the runtime right now) resizes the gate first."""
        if limit is not None:
            self.set_limit(limit)
        return _GatedPool(self, max_workers)


class _GatedPool:
    def __init__(self, gate: "SessionConcurrencyGate", max_workers: int) -> None:
        self._gate = gate
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._released = None

    def __enter__(self) -> "_GatedPool":
        self._released = self._gate.released()
        self._released.__enter__()
        return self

    def submit(self, fn: Callable, *args, **kwargs):
        return self._executor.submit(self._gate.wrap_for_pool(fn), *args, **kwargs)

    def __exit__(self, *exc_info) -> bool:
        try:
            self._executor.shutdown(wait=True)
        finally:
            self._released.__exit__(*exc_info)
        return False


@dataclass
class AgentRuntime:
    """Held as `Session.agent_runtime` and threaded through every
    `ToolContext` as `agent_runtime=` (tools/base.py) -- untyped there to
    avoid a hard import-order requirement (this module imports
    `agent.loop.Session`, so `tools/base.py` cannot import this module)."""
    parent: object                                  # agent.loop.Session
    agents: "dict[str, AgentSpec]" = field(default_factory=dict)
    routes: dict = field(default_factory=dict)
    # V2c (H15) roles: the persisted role table (config.json/team.json, or
    # the cost-aware default -- `roles.py::resolve_role_table`, resolved
    # ONCE by whoever builds the top-level Session) and this run's own CLI
    # `--role name=model` overrides -- both threaded down to every child's
    # own `resolve_agent_model` call unchanged (a grandchild can never
    # spawn per MAX_DEPTH, but `_build_child_session` still copies these
    # onto the child's own nested AgentRuntime for consistency).
    role_table: dict = field(default_factory=dict)
    cli_role_overrides: dict = field(default_factory=dict)
    depth: int = 0
    # A depth cap and a concurrency cap of the runtime's own (a lineup's
    # `delegation.max_depth` / `max_parallel`, set by agent/loop.py), or
    # `None` to fall through to `MAX_DEPTH` / the `agents.max_concurrent`
    # config knob (`effective_max_depth` / `effective_max_concurrent`).
    # `_build_child_session` copies both onto every descendant's own
    # nested `AgentRuntime` so the whole tree shares the same two caps.
    max_depth: Optional[int] = None
    max_concurrent: Optional[int] = None
    # Halo 2.0.5 round 5 "team control": the enforced lineup
    # (`teams_runtime.TeamControl`) a session runs under -- `None` for every
    # session with no active team (or a bare session), so nothing below
    # changes for them. Copied onto every descendant's own nested
    # AgentRuntime by `_build_child_session`, same as role_table above.
    team_control: Optional[object] = None
    tasks: dict = field(default_factory=dict)        # task_id -> {"child_session_id", "spec_name", "cwd"}
    lock: "threading.Lock" = field(default_factory=threading.Lock)
    # H9 whole-tree review finding 27 (task-map persistence half): flips
    # True the first time `_hydrate_tasks_from_disk` runs for THIS runtime
    # so a resumed session's on-disk `subagents/*.meta.json` files are
    # only ever scanned once, not on every single Agent/TaskStop call.
    tasks_hydrated: bool = False
    # H11b finding 14: agent_id -> the live child `Session` object, for as
    # long as its own call might still be running -- `run_agent_call`/
    # `_resume_task`/`_bg_run` each register their child here and pop it
    # in a `finally` that also calls `child.close_runtimes()`, so nothing a
    # child keeps running beside its turns outlives its ONE call.
    live_children: dict = field(default_factory=dict)
    # H9 whole-tree review finding 10: ONE semaphore shared by reference
    # down the WHOLE tree from wherever it's first sized for real (`agent.
    # loop.Session.__init__`), acquired around each child's own run in
    # EVERY spawn path (single, fan-out, resume) so the session-
    # wide concurrency cap is real: two separate `count` calls, or nested
    # levels, can no longer multiply past it just because each one's own
    # ThreadPoolExecutor pool is independently sized. Defaults to an
    # effectively-unbounded semaphore so a bare `AgentRuntime(parent=...)`
    # built directly (every pre-existing test fixture, never routed
    # through the real construction site) behaves exactly as before
    # this field existed -- unlimited, never a surprise new cap in a test
    # that never asked for one.
    concurrency_semaphore: "object" = field(default_factory=lambda: SessionConcurrencyGate(1_000_000))


def _new_agent_id() -> str:
    return uuid.uuid4().hex[:8]


def _child_log_paths(parent, agent_id: str):
    """`<parent_session_dir>/subagents/agent-<id>.jsonl` (brief B) -- built
    by constructing an ordinary `SessionLog` and then redirecting its
    `dir`/`path` (SAFE: done immediately after construction, before
    `Session.__init__` ever calls `.nodes()`/appends anything). Existing
    content is loaded up front so a task_id RESUME naturally lands in
    `Session.__init__`'s own "resume an existing log" branch with zero
    extra plumbing -- a fresh spawn's file doesn't exist yet, so `_nodes`
    stays `[]` and the "brand new session" branch runs instead."""
    from halo_harness.agent.log import SessionLog

    parent_dir = parent.log.dir / parent.log.session_id
    subdir = parent_dir / "subagents"
    subdir.mkdir(parents=True, exist_ok=True)
    session_id = f"agent-{agent_id}"
    log = SessionLog(parent.cwd, session_id=session_id)
    log.dir = subdir
    log.path = subdir / f"{session_id}.jsonl"
    if log.path.exists():
        log._nodes = log.read_all()
    return log, subdir / f"{session_id}.meta.json"


def _write_meta(meta_path: Path, data: dict) -> None:
    try:
        existing = {}
        if meta_path.exists():
            existing = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        existing = {}
    existing.update(data)
    try:
        meta_path.write_text(json.dumps(existing, indent=2, default=str), encoding="utf-8")
    except OSError:
        pass


def _child_credential_message(ref) -> str:
    """Pass-B finding 1 (critical): the provider's own "not configured"
    sentence for a sub-agent CHILD's model ref, matching providers/
    stream.py's phase-1 `ProviderNotConfigured` wording exactly so a
    child on an unconfigured route is turned away with the same sentence
    the request path would have raised at turn time (naming the actual
    missing credential), not a generic "something went wrong"."""
    if ref.provider == "huggingface":
        return ("Hugging Face not configured -- set HF_TOKEN for the router, add this name to "
                 "huggingface.endpoints, or add/run a local server (huggingface.local_servers, "
                 "or auto-detection on a default port)")
    if ref.provider == "openai":
        return "OpenAI API not configured -- set OPENAI_API_KEY"
    if ref.provider == "experiential":
        return "Experiential Labs not configured -- set EXPLABS_API_KEY"
    if ref.provider == "ollama":
        return "Ollama host not configured"
    if ref.provider == "anthropic":
        return "Anthropic not configured"
    if ref.provider == "databricks":
        return "Databricks not configured"
    return "OpenRouter not configured"


def _build_child_session(*, runtime: AgentRuntime, spec: AgentSpec, agent_id: str,
                          model_override: Optional[str], parent_tool_use_id: str, background: bool = False,
                          role_override: Optional[str] = None, effort_override: Optional[str] = None,
                          task_text: str = ""):
    """vibes/review.md finding 64: an `isolation: worktree` agent's tree is
    created first thing in the real builder, BEFORE the model resolves --
    so an unresolvable model (or an unconfigured provider) raised out with
    the fresh worktree and its branch stranded under the state dir, one
    per failed attempt. The tree this call created is removed again when
    the build raises, then the error propagates unchanged."""
    created: list = []
    try:
        return _build_child_session_inner(
            runtime=runtime, spec=spec, agent_id=agent_id, model_override=model_override,
            parent_tool_use_id=parent_tool_use_id, background=background, role_override=role_override,
            effort_override=effort_override, _created_worktrees=created, task_text=task_text,
        )
    except BaseException:
        for wt_path in created:
            try:
                from halo_harness.worktree import remove_worktree
                remove_worktree(wt_path, repo_root_hint=runtime.parent.cwd)
            except Exception:
                log.warning("could not remove the unused isolation worktree %s", wt_path)
        raise


def _build_child_session_inner(*, runtime: AgentRuntime, spec: AgentSpec, agent_id: str,
                                model_override: Optional[str], parent_tool_use_id: str, background: bool = False,
                                role_override: Optional[str] = None, effort_override: Optional[str] = None,
                                _created_worktrees: Optional[list] = None, task_text: str = ""):
    """A real `agent.loop.Session` for `spec`: its OWN fresh (or resumed)
    log, a tool subset frozen from the PARENT's own catalog (never grows
    it -- brief B), its `body` as the full system prompt (CLAUDE.md/memory
    per `AgentSpec.skips_claude_md`/`includes_memory`), a resolved model,
    and a permission mode/engine of its own (sharing the parent's rules,
    scoped by `spec.permission_mode` when set)."""
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.agent.loop import Session
    from halo_harness.hooks import HookRunner
    from halo_harness.permissions import PermissionEngine

    parent = runtime.parent
    child_log, meta_path = _child_log_paths(parent, agent_id)

    # W4a misc: `isolation: worktree` frontmatter -- "shared with
    # --worktree" (the same helper `headless.run_print_mode` uses for the
    # CLI flag). Falls back to the parent's own cwd (one log line, never a
    # hard failure) when this isn't a git repo or the worktree creation
    # itself fails -- a sub-agent must still run even when isolation isn't
    # available.
    child_cwd = parent.cwd
    # finding 14 (W6a): the worktree path THIS call created (None when
    # isolation isn't requested, or creation fell back to the parent's
    # own cwd) -- stashed on `child` below so `run_agent_call`'s own
    # completion handling (both the foreground and background paths) can
    # remove a CLEAN tree (firing WorktreeRemoved) or surface a DIRTY
    # one's path/branch in the Agent result instead of silently
    # stranding it under `~/.halo/worktrees`.
    isolation_worktree_path = None
    isolation_worktree_branch = None
    if spec.isolation == "worktree":
        from halo_harness.worktree import create_worktree
        wt_path, wt_error = create_worktree(parent.cwd, f"agent-{agent_id}", state_dir=parent.state_dir)
        if wt_path is not None:
            child_cwd = wt_path
            isolation_worktree_path = wt_path
            if _created_worktrees is not None:
                _created_worktrees.append(wt_path)
            try:
                branch_result = subprocess.run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(wt_path),
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
                )
                if branch_result.returncode == 0:
                    isolation_worktree_branch = branch_result.stdout.strip()
            except (OSError, subprocess.SubprocessError):
                pass
        else:
            log.warning("sub-agent %s isolation:worktree could not create a worktree (%s) -- "
                        "running in the parent's own cwd instead", spec.name, wt_error)

    catalog_names = (parent.session_catalog.names if parent.session_catalog is not None
                      else parent.tool_registry.names())
    tool_names = spec.resolved_tools(catalog_names)
    child_registry = parent.tool_registry.filtered(tool_names)

    ctx = SessionContext(
        cwd=child_cwd, model_label=parent.model_label, model_family="generic",
        bare=spec.skips_claude_md(), tool_registry=child_registry, mcp_servers=None,
    )
    ctx.system_prompt = spec.body or spec.description
    # Parity gap: agent frontmatter `memory:` used to be a bare truthy
    # gate -- ANY non-empty value always resolved to the SAME global
    # `~/.halo/agents/<name>/` directory, never created it, and (for that
    # global directory specifically) left it OUTSIDE the child's own
    # permission working dirs (asked for in default mode, flatly denied
    # in -p/background, for every Read/Write/Edit the agent made against
    # the exact path its own system prompt told it to use). Now honours
    # the actual scope value -- "user" (global, unchanged path; also the
    # fallback for a bare truthy non-string value like YAML `memory:
    # true`, or any unrecognized string, so nothing that used to work
    # silently stops), "project" (inside THIS project's own cwd, so it is
    # already a working dir with no extra_dirs change needed at all) or
    # "local" (this project only, but kept out of the project tree
    # itself, under state_dir keyed by a project slug) -- a PLAUSIBLE
    # mirror of Claude Code's own user|project|local agent-memory scopes,
    # never verified against a real Claude Code agent definition.
    memory_scope = spec.memory if isinstance(spec.memory, str) and spec.memory.strip() else (
        "user" if spec.memory else None)
    memory_extra_dir: Optional[Path] = None
    if memory_scope:
        if memory_scope == "project":
            memory_dir = Path(parent.cwd) / ".halo" / "agents" / spec.name
        elif memory_scope == "local":
            from halo_harness.config.paths import project_slug
            memory_dir = Path(parent.state_dir) / "agents-local" / project_slug(parent.cwd) / spec.name
            memory_extra_dir = memory_dir
        else:  # "user", or any other/unrecognized value -- the original, global default
            memory_dir = Path(parent.state_dir) / "agents" / spec.name
            memory_extra_dir = memory_dir
        memory_file = memory_dir / "MEMORY.md"
        try:
            memory_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        ctx.system_prompt = (
            f"{ctx.system_prompt}\n\nYour persistent memory directory is {memory_dir} -- write notes there "
            f"(e.g. {memory_file.name}) that you want available to your NEXT invocation; its current "
            f"contents, if any, are included below as a snapshot."
        )

        def _read_agent_memory(path=memory_file) -> str:
            try:
                return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
            except OSError:
                return ""

        ctx.memory_snapshot_text = _read_agent_memory
    elif not spec.includes_memory():
        ctx.memory_snapshot_text = lambda: ""  # D-CFG: "no memory index unless general-purpose"

    # V2c (H15): the Agent-tool-call's own `role=` argument, when given,
    # overrides this agent's own file/built-in `role:` for just this one
    # call -- see `resolve_agent_model`'s own docstring for the full chain.
    _effective_role_name = role_override or spec.role
    # Halo 2.0.5 round 5 "team control": under a team, the member's own
    # context arrives here -- the template's `context` (files/skills) plus
    # the assigned bio's own (`member_system_context_addition`, the piece
    # round 2 built and left for this round to wire), and the team's
    # namespaced shared memory (`context.memory.namespace`, writable only
    # by `writers`) as an extra permission working dir + prompt line.
    team_control = getattr(runtime, "team_control", None)
    team_memory_dir = pack_memory_dir = None
    if team_control is not None:
        addition = team_control.member_context_addition(_effective_role_name, cwd=parent.cwd,
                                                        state_dir=parent.state_dir)
        if addition:
            ctx.system_prompt = f"{ctx.system_prompt}\n\n{addition}"
        memory_dir, may_write = team_control.member_memory(_effective_role_name, parent.state_dir)
        if memory_dir is not None:
            team_memory_dir = memory_dir if may_write else None
            try:
                memory_dir.mkdir(parents=True, exist_ok=True)
            except OSError:
                pass
            role_word = "read and write" if may_write else "read"
            ctx.system_prompt = (f"{ctx.system_prompt}\n\nTeam memory namespace "
                                 f"({team_control.context.get('memory', {}).get('namespace')}): {memory_dir} "
                                 f"-- you may {role_word} it; use it for notes the whole team shares.")
        from halo_harness.packs.memory import member_note  # 3.2.0.0 R2: a pack bio's own memory namespace
        try:
            pack_memory_dir, note = member_note(team_control.bio_for(_effective_role_name), parent.state_dir)
        except Exception:
            pack_memory_dir, note = None, ""
        if pack_memory_dir is not None:
            ctx.system_prompt = f"{ctx.system_prompt}\n\n{note}"
    # Halo 3.1.9.0 R2: when the one model order reaches `auto` (an auto bio,
    # below a tier's model and the call's own `model`), `models_auto.pick`
    # chooses for this task; the Pick (and its reason) lands in `_auto`.
    from halo_harness.models_auto_spawn import resolver as _auto_resolver
    _auto: dict = {}
    model_ref, model_profile = resolve_agent_model(
        invocation_model=model_override, frontmatter_model=spec.model,
        role_name=_effective_role_name, role_table=runtime.role_table,
        cli_role_overrides=runtime.cli_role_overrides,
        env=parent.tool_env, settings=getattr(parent.session_context, "settings", None),
        parent_ref=parent.model_ref, parent_profile=parent.model_profile,
        parent_small_ref=parent.small_model_ref, state_dir=parent.state_dir, routes=runtime.routes,
        auto_pick=_auto_resolver(runtime=runtime, role_name=_effective_role_name, task_text=task_text,
                                 holder=_auto, routes=runtime.routes, requested=model_override),
    )
    # 2.0.2 review finding 7 (major): a decision-only/judge endpoint
    # (`Controller.set_model` auto-routes one to `roles.judge` rather than
    # ever installing it as the session model) can never carry the
    # built-in `Judge` agent's own HARD-CODED Explore tool set -- every
    # request it made raised `ToolsNotSupported` before the model ever
    # got to answer, and the user-facing error pointed back at "use the
    # judge role instead of the session model", which was already in use.
    # Tool-less instead whenever the RESOLVED model itself can't take
    # tools, regardless of which agent/role asked for it -- the registry
    # empties out (same shape `--tools ""` already supports) and the
    # prompt gets an explicit heads-up to decide from the text alone.
    # `model_profile` here is `halo_harness.model.ModelProfile` (context/
    # pricing/vision only -- no `tools_supported` field at all); decision-
    # only-ness is a `providers.profiles` concept, the SAME check
    # `Controller.set_model`/`headless.build_session` already make before
    # ever letting this ref become the session model.
    if model_ref.provider == "databricks":
        from halo_harness.providers.profiles import decision_only_notice
        if decision_only_notice(model_ref.model):
            ctx.tool_registry = parent.tool_registry.filtered([])
            ctx.system_prompt = (f"{ctx.system_prompt}\n\nThis endpoint supports no tool calls at all -- decide "
                                  f"and answer directly from the prompt text alone.")

    # Halo 2.0.3 pass-B fix (review finding 1, critical): a child used to
    # be built with creds=parent.creds, openrouter_base_url=parent.
    # openrouter_base_url and extra_headers=dict(parent.extra_headers)
    # UNCONDITIONALLY, whatever provider/host the CHILD's own model_ref
    # actually names -- 2.0.3 makes cross-provider children the normal
    # case (local ol:/hf:local models on supporting roles, `gym propose
    # --apply` writing researcher/subagent/judge roles onto local models,
    # any Agent(model=...) naming any route), so an `ol:`
    # child under an `or:` parent POSTed its whole prompt to the PARENT's
    # upstream with the PARENT's bearer key (an `oai:` child went to
    # OpenRouter too). Reused only when the child's route is actually the
    # SAME route as the parent's (provider, host, and the local/mlx flags
    # all match -- so two plain `or:` sessions, or two `hf:local` sessions
    # against the same named server, still share one real connection);
    # otherwise resolved fresh with the exact same per-entry resolver
    # `/model` and the fallback chain already use. A mismatched child
    # whose own creds resolve to None (its provider isn't configured at
    # all) raises here, before a Session for it is ever built -- every
    # caller of this function already wraps it in `try/except Exception`
    # and turns that into an `is_error` ToolResult (see `run_agent_call`'s
    # own call site below), so this reaches the model as that same
    # ToolResult, naming the missing credential via the provider's own
    # "not configured" sentence, with no request ever sent anywhere.
    _parent_ref = parent.model_ref
    _same_route_as_parent = (
        model_ref.provider == _parent_ref.provider
        and getattr(model_ref, "host", None) == getattr(_parent_ref, "host", None)
        and getattr(model_ref, "local", False) == getattr(_parent_ref, "local", False)
        and getattr(model_ref, "mlx", False) == getattr(_parent_ref, "mlx", False)
    )
    if _same_route_as_parent:
        child_creds = parent.creds
        child_openrouter_base_url = parent.openrouter_base_url
        child_extra_headers = dict(parent.extra_headers)
    else:
        from halo_harness.headless import _resolve_creds
        from halo_harness.providers.stream import ProviderNotConfigured
        child_creds = _resolve_creds(model_ref, parent.settings)
        child_openrouter_base_url = None
        child_extra_headers = {}
        _picked = _auto.get("pick")
        if child_creds is None and _picked is not None and not _picked.fallback:
            # 3.1.9.0 R2: an auto pick whose provider has no credentials here runs on the parent's model
            _picked.fall_back(_parent_ref.raw, f"{model_ref.raw} has no credentials here")
            model_ref, model_profile = _parent_ref, parent.model_profile
            child_creds, child_openrouter_base_url = parent.creds, parent.openrouter_base_url
            child_extra_headers = dict(parent.extra_headers)
        if child_creds is None:
            raise ProviderNotConfigured(_child_credential_message(model_ref))

    # Halo 2.0.2 (brief A.2): "sub-agent runs apply the role's effort
    # through the same path the session uses" -- resolved alongside (not
    # inside) `resolve_agent_model` so that function's return shape never
    # changes; applied below exactly where `spec.effort` already was,
    # one rung below it (an agent file's own explicit `effort:` still
    # wins) and one rung above blindly inheriting the parent's.
    from halo_harness.roles import role_effort_for
    _role_effort = role_effort_for(_effective_role_name, role_table=runtime.role_table,
                                    cli_overrides=runtime.cli_role_overrides)
    # Halo 2.0.2 round 3 (brief C): a `count`/`batch` fan-out job's own
    # per-item `effort` override (`_run_agent_fanout` below) -- one rung
    # ABOVE everything else here, same precedence `role_override`/`model_
    # override` already get over this agent's own file/role defaults.
    _effective_effort = effort_override or spec.effort or _role_effort or parent.effort

    # vibes/review.md finding 11: an agent FILE's frontmatter used to be
    # able to raise its own session above the parent's -- a cloned repo's
    # `.claude/agents/x.md` with `permissionMode: bypassPermissions` (or
    # `acceptEdits` to escape plan mode) overrode the owner's mode, and a
    # plugin/project agent's own `hooks:` were merged and run. Two rules
    # now: (1) `project:`/`plugin:`-sourced agent files (NOT the owner's
    # own `user`/`managed`/`cli-agents`/`built-in` ones) lose their
    # `permissionMode` entirely, same policy Claude Code applies; (2) no
    # agent, from any source, may run MORE permissive than its parent.
    # Review 3 item 4: the team template's `permissions.mode` is folded in
    # BEFORE the clamp (it used to be applied after it, unclamped); `plan`
    # is sticky (a write ban, not a rung: a plan parent always yields a
    # plan child); `dontAsk` ranks below `default` (it denies where
    # default asks), so neither can be escaped by a child's own request.
    _UNTRUSTED_AGENT_SOURCE = str(getattr(spec, "source", "") or "").startswith(("project:", "plugin:"))
    _PERMISSIVENESS_RANK = {"dontAsk": 0, "default": 1, "acceptEdits": 2, "auto": 3, "bypassPermissions": 4}
    _parent_mode = parent.permission_engine.mode
    team_perms = team_control.member_permissions() if team_control is not None else {}
    _requested_mode = (team_perms.get("mode") or (None if _UNTRUSTED_AGENT_SOURCE else spec.permission_mode)
                       or _parent_mode)
    if _parent_mode == "plan" or _requested_mode == "plan":
        permission_mode = "plan"
    elif _PERMISSIVENESS_RANK.get(_requested_mode, 99) > _PERMISSIVENESS_RANK.get(_parent_mode, 1):
        permission_mode = _parent_mode  # clamp: never above the parent
    else:
        permission_mode = _requested_mode
    # finding 14 (W6a): both of these used to root at `parent.cwd`
    # unconditionally -- for an `isolation: worktree` child (`child_cwd`
    # above, the worktree path), every edit landed OUTSIDE the engine's
    # own working directory: asked for in default/acceptEdits mode, and
    # flatly denied in print/background mode, no matter what the child
    # actually did.
    # Parity gap: the "user"/"local" memory scopes above resolve OUTSIDE
    # `child_cwd` (by design -- global or state-dir-rooted) -- added here
    # so Read/Write/Edit against the agent's own documented memory path
    # never has to ask (default mode) or get flatly denied (-p/
    # background) just because it is not literally inside the cwd.
    # `PermissionEngine.__init__` already copies this into its OWN new
    # list, so appending here never mutates the PARENT's own extra_dirs.
    child_extra_dirs = list(parent.permission_engine.extra_dirs)
    if memory_extra_dir is not None:
        child_extra_dirs.append(memory_extra_dir)
    if team_memory_dir is not None:
        child_extra_dirs.append(team_memory_dir)
    if pack_memory_dir is not None:  # 3.2.0.0 R2: the pack bio's own memory folder
        child_extra_dirs.append(pack_memory_dir)
    # Halo 2.0.5 round 5 "team control": the template's `permissions`
    # section applies to every member ON TOP of the bio's own -- mode,
    # deny/ask/allow rules in the same settings.json grammar the parent
    # engine already takes, and `offline` (checked at the spawn point in
    # `run_agent_call`, since offline mode is process-global here).
    child_mode = permission_mode
    _team_deny: list = []
    _team_ask: list = []
    _team_allow: list = []
    if team_control is not None:
        _team_deny, _team_ask, _team_allow = team_perms["deny"], team_perms["ask"], team_perms["allow"]
    child_engine = PermissionEngine(
        deny_rules=list(parent.permission_engine.deny_rules) + _team_deny,
        ask_rules=list(parent.permission_engine.ask_rules) + _team_ask,
        allow_rules=list(parent.permission_engine.allow_rules) + _team_allow,
        mode=child_mode,
        cwd=child_cwd, extra_dirs=child_extra_dirs,
        print_mode=parent.permission_engine.print_mode,
    )
    # Halo 3.0.6.0 R7: a mission part's claim guard holds for its sub-agents too (fleet/mission_guard.py).
    from halo_harness.fleet.mission_guard import inherit as _inherit_guards
    _inherit_guards(parent.permission_engine, child_engine)

    # Parity gap: `Session.plugin_roots` reads `cli_flags["resolved_
    # plugin_roots"]` -- a child's own `cli_flags` dict below used to
    # carry only the worktree key, so `self.plugin_roots` was always `[]`
    # for every sub-agent regardless of what the PARENT session's own
    # `--plugin-dir`/`--plugin-url` roots were, and a model-invoked Skill
    # tool call inside that sub-agent could never find one of those
    # skills at all (`tools/skill.py` reads `ctx.plugin_roots`, itself
    # read from `Session.plugin_roots`). Every OTHER cli_flags-driven
    # behavior still stays off for a child, unchanged.
    _child_cli_flags: dict = {}
    if parent.plugin_roots:
        _child_cli_flags["resolved_plugin_roots"] = parent.plugin_roots

    hook_runner = None
    if parent.hook_runner is not None:
        # Halo 2.0.5 round 5 (deliverable 2): a member bio's own `hooks`
        # (plus a template assignment's `hooks` override, and an AgentSpec
        # frontmatter `hooks` of the same shape for a non-team agent) run
        # through THIS child's own HookRunner -- the same runner, matcher
        # and env machinery a settings hook already uses -- with the
        # agent's name in the environment as HALO_AGENT. `scope: "agent"`
        # keeps them out of the parent's own hook map entirely.
        from halo_harness.hooks import agent_hooks_to_hookdefs
        member_hooks = {}
        if team_control is not None:
            member_hooks = team_control.member_hooks(_effective_role_name)
        elif isinstance(getattr(spec, "hooks", None), dict) and not _UNTRUSTED_AGENT_SOURCE:
            # finding 11: hooks from a project:/plugin:-sourced agent file
            # are NOT merged (a cloned repo's agent file shipping its own
            # hook commands is someone else's code escalating into the
            # child's lifecycle); the owner's own agent files keep them.
            member_hooks = spec.hooks
        _child_hooks_by_event = parent.hook_runner.hooks_by_event
        if member_hooks:
            from halo_harness.hooks import merge_hook_maps
            _child_hooks_by_event = merge_hook_maps(
                _child_hooks_by_event, agent_hooks_to_hookdefs(member_hooks))
        _child_effective_env = dict(parent.hook_runner.effective_env or {})
        _child_effective_env["HALO_AGENT"] = spec.name
        hook_runner = HookRunner(
            _child_hooks_by_event, cwd=child_cwd, session_id=child_log.session_id,
            transcript_path=str(child_log.path), effective_env=_child_effective_env,
            permission_mode=permission_mode, effort=_effective_effort,
            mcp_manager=parent.mcp_manager, prompt_caller=parent.hook_runner.prompt_caller,
            enabled=parent.hook_runner.enabled, agent_id=agent_id, agent_type=spec.name,
        )

    child = Session(
        cwd=child_cwd, model_ref=model_ref, model_profile=model_profile, creds=child_creds,
        state_dir=parent.state_dir, model_label=model_ref.raw, session_context=ctx,
        small_model_ref=parent.small_model_ref, small_model_effort=getattr(parent, "small_model_effort", None),
        session_log=child_log,
        max_turns=(spec.max_turns or parent.max_turns), effort=_effective_effort,
        permission_engine=child_engine, session_catalog=None, mcp_manager=parent.mcp_manager,
        hook_runner=hook_runner,
        # Halo 2.0.3 round 5e: so `roles.role_escalation_enabled` can see
        # which role this CHILD was actually resolved under -- the main
        # session passes no role name at all (`Session.__init__`'s own
        # default), so hybrid escalation is unaffected by this for a
        # top-level session.
        role_name=_effective_role_name,
        # pass-B finding 1: `child_openrouter_base_url`/`child_extra_
        # headers` (computed above, alongside `child_creds`) carry the
        # PARENT's own custom routing (a mock upstream in tests; a
        # self-hosted proxy via BRIDGE_OPENROUTER_BASE_URL in real use)
        # only when the child's route actually IS the parent's route --
        # a cross-provider/cross-host child gets neither, so it falls back
        # to its own freshly-resolved `creds.base_url`/no extra headers
        # (`providers/stream.py`: "base_url = req.openrouter_base_url or
        # req.creds.base_url"), never the parent's.
        openrouter_base_url=child_openrouter_base_url, extra_headers=child_extra_headers,
        # H6 scope B must-do ("sub-agents reuse steer/abort/... plumbing"):
        # share the PARENT's own abort Event rather than letting Session's
        # default (a fresh, private Event) leave the child deaf to it --
        # `_run_child_to_completion` below is a bare drain loop with no
        # abort check of its own, so without this an Esc/kill during a
        # running sub-agent had NO effect at all until the child finished
        # organically; sharing the object means every existing
        # `self.abort.is_set()` check already threaded through the
        # child's own `_step`/retry waits/streaming now reacts to the
        # SAME signal, with no new logic needed on either side.
        # H9 whole-tree review finding 10: a BACKGROUND child gets its OWN
        # abort Event instead of sharing the parent's -- sharing meant Esc
        # on a LATER, unrelated FOREGROUND turn (or Ctrl+C on an empty
        # prompt while idle) cut a background child mid-stream with no
        # relationship to what the user was actually looking at (verified:
        # Esc on an unrelated turn interrupted a running background
        # sub-agent). Only `quit()`/`TaskStop(task_id=...)` on THIS
        # specific task may ever set it (see `run_agent_call` below, which
        # stashes it on `runtime.tasks[task_id]["abort_event"]`).
        abort=(parent.abort if not background else threading.Event()),
        # H9: MUST be passed at construction time, not set afterward --
        # `Session.__init__` reads `self.agent_id` synchronously (critical
        # review finding 16: a child never fires the user's own
        # SessionStart hooks, only SubagentStart) before this call even
        # returns. Also namespaces `_permission_waiters` keys (finding 2,
        # see `Session.__init__`'s own docstring on `agent_id`) so this
        # child can never collide with a sibling's live waiter slot in the
        # dict shared with the parent just below.
        agent_id=agent_id,
        # H9 whole-tree review finding 3: share the PARENT's own
        # JobRegistry instead of letting Session's default (a fresh,
        # private one) leave a background Bash job THIS child starts
        # unreachable by the parent's `kill_all()` on quit and its
        # completion notice stranded on a Session object nobody drains
        # again once this call returns -- see loop.py's own `job_registry=`
        # param docstring for the full failure mode this closes.
        job_registry=parent.job_registry,
        # finding 14 (W6a): the ONLY purpose of this is so `Session.
        # __init__`'s own (already-built, already-tested) `_fire_
        # worktree_created` fires for THIS child too -- it reads exactly
        # this key and no other (a child never gets cli_flags otherwise;
        # every OTHER cli_flags-driven behavior stays off, unchanged).
        cli_flags=({**_child_cli_flags, "_worktree_created_path": str(isolation_worktree_path)}
                    if isolation_worktree_path is not None else (_child_cli_flags or None)),
        # vibes/review.md finding 61: an agent FILE's `tools: Agent(X)`
        # content restriction (`allowed_subagent_types()`) reaches a
        # sub-agent too, not only the top-level `--agent` session -- the
        # SAME check `run_agent_call` below enforces.
        agent_type_restriction=spec.allowed_subagent_types(),
    )
    if hook_runner is not None:
        hook_runner.prompt_caller = child._call_model_for_hook
    # finding 14 (W6a): read back by `run_agent_call`'s own completion
    # handling (foreground and background alike) once this child's run
    # ends, to remove a CLEAN tree or surface a DIRTY one's path/branch.
    child._isolation_worktree_path = isolation_worktree_path
    child._isolation_worktree_branch = isolation_worktree_branch
    child._isolation_worktree_repo_root = parent.cwd
    child.interactive = False  # deliberately NEVER True -- ExitPlanMode stays out of scope (see module docstring)
    # H5c finding 8 / W4a: a live, answerable permission card (and, as of
    # W4a, AskUserQuestion too) for ANY child of an interactive parent,
    # foreground OR background -- `_run_child_to_completion`'s `on_event`
    # forwards a foreground child's events into the parent's own live `turn()`
    # stream; `_bg_run` below forwards a BACKGROUND child's through `parent.
    # _event_sink` directly instead (there is no live `turn()` consumer for
    # it to ride along with). `_question_waiters` is shared exactly like
    # `_permission_waiters` already was -- both namespaced by agent_id in
    # `_resolve_tool_call` for the same reason (parallel/sequential children's
    # own tool_use ids can collide).
    child._subagent_live_asks = bool(parent.interactive)
    child._permission_waiters = parent._permission_waiters
    child._question_waiters = parent._question_waiters
    child.agent_runtime = AgentRuntime(parent=child, agents=runtime.agents, routes=runtime.routes,
                                        role_table=runtime.role_table, cli_role_overrides=runtime.cli_role_overrides,
                                        depth=runtime.depth + 1, tasks=runtime.tasks, lock=runtime.lock,
                                        # Halo 2.0.2 round 2 (brief B): propagated to EVERY descendant, not
                                        # just this one hop -- the depth/concurrency caps survive the
                                        # whole tree, not reset to the module defaults one level down.
                                        max_depth=runtime.max_depth, max_concurrent=runtime.max_concurrent,
                                        # Halo 2.0.5 round 5: the team's enforced lineup travels down the
                                        # whole tree too (grandchildren can never spawn per the depth cap,
                                        # but `_build_child_session` still copies it for consistency, same
                                        # rule as role_table above).
                                        team_control=getattr(runtime, "team_control", None),
                                        # finding 10: the SAME semaphore object, never a fresh one -- see
                                        # AgentRuntime.concurrency_semaphore's own docstring.
                                        concurrency_semaphore=runtime.concurrency_semaphore)
    # Halo 3.1.9.0 R2: an auto pick's reason rides on the child (its agent
    # row's `model_reason`, its meta.json) and opens its transcript.
    from halo_harness.models_auto_spawn import record as _record_auto_pick
    _model_reason = _record_auto_pick(child, _auto.get("pick"), ran_on=model_ref.raw)
    # Halo 3.0.5.0 (Fleet): the child joins the session's live agent tree.
    _agent_tree.register_child(parent, child, agent_id=agent_id, spec=spec, model=model_ref.raw,
                               role=_effective_role_name, background=background, team_control=team_control,
                               model_reason=_model_reason)
    _write_meta(meta_path, {
        "agent_id": agent_id, "type": spec.name, "description": spec.description,
        "model": model_ref.raw, "parent_tool_use_id": parent_tool_use_id,
        "started": time.time(), "status": "running", "session_id": child_log.session_id,
        # 3.0.5.0 R3: Live Roles' history (studio/fleet_api.py) lists past runs by role
        "role": _effective_role_name, "lineup": getattr(team_control, "name", None),
        **({"model_reason": _model_reason} if _model_reason else {}),
    })
    return child, meta_path


def _fire_task_hook(parent, event_name: str, *, task_id: str, spec_name: str, description: str) -> None:
    """W4a: TaskCreated/TaskCompleted -- "background jobs and sub-agents"
    (removed from NOT_EMITTED_V1). Fires on the PARENT's own hook_runner
    (never the child's, unlike SubagentStart/Stop) -- a task_id is the
    PARENT's own bookkeeping concept (`runtime.tasks`), so this is the
    session whose hooks should see it created/completed. `agent/jobs.py`'s
    background Bash jobs fire the SAME two events from their own call
    sites for the other half of "background jobs and sub-agents"."""
    if parent.hook_runner is None or not parent.hook_runner.has_hooks(event_name):
        return
    payload = parent.hook_runner.payload(event_name, extra={
        "task_id": task_id, "subagent_type": spec_name, "description": description,
    })
    try:
        parent._run_hook(event_name, payload, matched=spec_name)
    except Exception:
        pass


def _fire_subagent_hook(child, event_name: str) -> None:
    """W3b item 11: `child._run_hook`/`_run_hook_stop` (never the bare
    `child.hook_runner.run(...)` this used to call directly) so a child's
    own SubagentStart/SubagentStop lands in ITS OWN per-turn timeline
    (`child._timeline`, never the parent's or the shared module-level
    default) -- the exact per-session isolation this round's own gap list
    asks for."""
    if child.hook_runner is None:
        return
    try:
        if event_name == "SubagentStop":
            child._run_hook_stop("SubagentStop")
        else:
            child._run_hook(event_name, child.hook_runner.payload(event_name))
    except Exception:
        pass


def _team_forward_prefix(parent) -> str:
    """Halo 2.0.5 round 5: `delegation.forward_text: true` -- the parent's
    own LATEST user message, capped, as leading context for the child. ""
    when the parent has no user text yet (or no message list at all)."""
    for msg in reversed(getattr(parent, "messages", None) or []):
        if not isinstance(msg, dict) or msg.get("role") != "user":
            continue
        content = msg.get("content")
        if isinstance(content, list):
            texts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
        else:
            texts = [str(content or "")]
        text = "\n".join(t for t in texts if t).strip()
        if text:
            return "Context from the delegating session's latest user message:\n" + text[:2000]
    return ""


def _team_queue_report(parent, line: str, *, from_role: "Optional[str]" = None) -> None:
    """Halo 2.0.5 round 5: lineup reporting -- a member's one-line report
    lands on the ROOT session's pending-notice queue (the same queue a
    background sub-agent's completion notice uses, so the next turn
    delivers it as a user-role notice), and any `on: message, from:
    <role>` trigger armed on the root's scheduler fires."""
    root = parent
    hops = 0
    while getattr(root, "agent_depth", 0) > 0 and getattr(root, "agent_id", None) is not None and hops < 8:
        runtime = getattr(root, "agent_runtime", None)
        up = getattr(runtime, "parent", None) if runtime is not None else None
        if up is None:
            break
        root = up
        hops += 1
    lock = getattr(root, "_agent_notices_lock", None)
    notices = getattr(root, "_pending_agent_notices", None)
    if lock is not None and notices is not None:
        with lock:
            notices.append(line)
    scheduler = getattr(root, "_team_scheduler", None)
    if scheduler is not None and from_role:
        scheduler.notify_message(from_role)


def _tag(ev, *, agent_id: str, parent_tool_use_id: str):
    """Finding 6 (major): a delegate's own events (a grandchild's under a
    child, at depth > 1) used to have their `agent_id` OVERWRITTEN at every
    level they bubble up through -- each ancestor's own `_run_child_to_
    completion` called this with ITS OWN `agent_id`, unconditionally,
    even for an event a DEEPER call already tagged with the real
    originator's id. Verified: `_tag(Event(agent_id="vp000001"),
    agent_id="ceo00001")` gave `agent_id == "ceo00001"` while `ev.data.
    agent_id` stayed `"vp000001"` -- the dock keys cards by `ev.agent_id`,
    so the VP's own card got the CEO's key, orphaning the CEO's real card
    (never finished, ticks "thinking Ns" forever) and misrouting the VP's
    text into it. Only set when not already set, so the DEEPEST
    (innermost/real) agent_id survives every hop back up -- `root_agent_
    id` records the outermost hop's own id for anything that wants it."""
    if not getattr(ev, "agent_id", None):
        ev.agent_id = agent_id
    if isinstance(ev.data, dict):
        extra = {"parent_tool_use_id": parent_tool_use_id}
        if "root_agent_id" not in ev.data:
            extra["root_agent_id"] = agent_id
        ev.data = {**ev.data, **extra}
    return ev


def _bg_phase_word(state: "Optional[str]", kind: "Optional[str]") -> "Optional[str]":
    """Halo 2.0.2 round C: the SAME (state, kind) -> short display word
    mapping `tui/dispatch.py`'s own `_phase_word_for` uses for the main
    status bar/a foreground child's card -- kept as its own small private
    copy here (never imported from `tui/`, which would make this agent-
    loop module depend on the UI layer) so a BACKGROUND child's `_bg_run`
    can translate a `phase` event into the narrower `subagent_progress`
    kind (see events.py's own docstring on it) without that import.
    `None` for a `phase` state that never changes the word on its own,
    exactly like the function it mirrors."""
    if state in ("request_sent", "headers"):
        return "thinking"
    if state == "first_token":
        if kind == "reasoning":
            return "thinking"
        if kind == "tool":
            return "tool"
        return "writing"
    if state == "waiting_for_model":
        return "waiting"
    return None


def _run_child_to_completion(child, prompt_text: str, *, agent_id: str, parent_tool_use_id: str,
                              on_event=None) -> list:
    """H5c finding 8: `on_event`, when given, is called SYNCHRONOUSLY on
    THIS thread with each tagged event the INSTANT it is produced -- never
    buffered -- so a live caller (loop.py's `_run_agent_batch_live`) can
    forward it (most importantly a `permission_request`, right before the
    child's OWN thread then blocks waiting for that exact card's answer)
    to a live stream while the child is still mid-turn. The full list is
    still returned too (unchanged contract: `tools/agent.py`'s direct-call
    fallback, and a background child's own parity/debuggability copy,
    still just want the whole thing at the end, no live channel needed)."""
    out = []
    for ev in child.turn(prompt_text):
        tagged = _tag(ev, agent_id=agent_id, parent_tool_use_id=parent_tool_use_id)
        out.append(tagged)
        if on_event is not None:
            on_event(tagged)
    return out


def _final_text_from_log(child) -> str:
    for node in reversed(child.log.nodes()):
        if node.get("type") == "assistant":
            parts = [b.get("text", "") for b in (node.get("content") or [])
                     if isinstance(b, dict) and b.get("type") == "text"]
            text = "".join(parts).strip()
            if text:
                return _fleet_handback(child, text)  # 3.0.5.0: "stopped by ..." for a child stopped from Studio
    return _fleet_handback(child, "(the sub-agent finished without producing a final text answer)")


def _one_line_preview(text: str, *, limit: int = 140) -> str:
    """Halo 2.0.2 round C: the short, single-line result summary a
    BACKGROUND child's live completion note shows (`tui/dispatch.py`'s
    own `subagent_end` handler, via `end_ev`'s `result_preview` below) --
    the first non-blank line of the child's own final answer, collapsed
    and capped, never the full (possibly multi-KB) text this module
    already caps separately for the model-facing notice (`RESULT_CAP`)."""
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line[:limit] + ("…" if len(line) > limit else "")
    return ""


# H9 whole-tree review finding 26: `turn_done` reasons that mean the child's
# run did NOT end normally -- its own last logged assistant text (what
# `_final_text_from_log` returns) may be a stale, mid-thought fragment from
# BEFORE whatever went wrong, never a real, complete report.
#
# "interrupted" is deliberately NOT in this set: an Esc/Ctrl+C-interrupted
# child is a normal, user-INTENDED stop condition (H5c finding 7's own
# tests pin this exactly: the parent's abort-batch pool result for a
# genuinely-started-then-interrupted child is `is_error=False`, matching
# how an interrupted tool call reads elsewhere in this harness), and
# `synthesize_missing_results` already stamps its own text with "[Request
# interrupted by user]" -- truthful on its own, with no need for (and no
# use duplicating) the "did not finish normally" framing this set exists
# for.
_ABNORMAL_TURN_DONE_REASONS = frozenset({"error", "max_turns", "blocked"})


def _child_turn_outcome(child_events: list) -> "tuple[bool, Optional[str]]":
    """`(is_error, reason)` from the LAST `turn_done` event the child
    actually produced (never raises; `reason` is None only if the child
    somehow never yielded one at all -- shouldn't happen for a real
    `child.turn()` run, but this must never crash the parent's turn over
    it either way). H9 whole-tree review finding 26: verified bug -- a
    provider failure partway through a child handed the parent whatever
    "Let me look at X…" text was logged last, presented as if it were the
    finished report, with no signal at all that the child never actually
    finished."""
    # NOTE: every event in `child_events` is already tagged with this ONE
    # child's own `agent_id` (by `_tag()` in `_run_child_to_completion`,
    # before it's ever appended to this list) -- no further agent_id
    # filtering needed or correct here.
    reason = None
    for ev in child_events:
        if getattr(ev, "kind", None) == "turn_done":
            reason = (ev.data or {}).get("reason") if isinstance(ev.data, dict) else None
    return (reason in _ABNORMAL_TURN_DONE_REASONS), reason


def _last_child_error_text(child_events: list) -> "Optional[str]":
    """2.0.7 dead-model-id round: the LAST `error` event's message from a
    child's own stream -- the 404's own words ("no endpoints found for
    model deepseek/..."), the exact thing a SILENT empty handback used to
    hide. Only ever used to DECORATE an already-abnormal handback (never
    a healthy one), so a transient early error that a later retry
    survived stays invisible, as it should."""
    last = None
    for ev in child_events:
        if getattr(ev, "kind", None) == "error":
            msg = (ev.data or {}).get("message") if isinstance(ev.data, dict) else None
            if isinstance(msg, str) and msg.strip():
                last = msg.strip()
    return last


def _forward_child_escalation_decisions(parent, child, spec) -> None:
    """2.0.6 round 12 (the carried C-5 minor): a background or foreground
    child's own hybrid-escalation decisions (agent/loop.py::_maybe_
    escalate appends to the CHILD session's list) used to die with the
    child -- the main session's /escalation view and the result JSON's
    escalations field never saw them. Copy any onto the PARENT's list,
    tagged with the agent's name so the view can say whose escalation it
    was. Best-effort: never lets a forwarding failure break the handback."""
    try:
        child_decisions = list(getattr(child, "_escalation_decisions", []) or [])
        if not child_decisions:
            return
        parent_list = getattr(parent, "_escalation_decisions", None)
        if parent_list is None:
            return
        for d in child_decisions:
            note = (getattr(d, "note", "") or "")
            tagged = f"[{spec.name}] {note}" if note else f"[{spec.name}]"
            if isinstance(d, dict):
                parent_list.append({**d, "note": tagged})
            else:
                from dataclasses import replace
                parent_list.append(replace(d, note=tagged))
    except Exception:
        pass


def _return_acceptance_for(spec, role_name: "Optional[str]", team_control, child) -> "Optional[dict]":
    """2.0.6 round 3: the bio's own `acceptance` block for THIS return --
    the team assignment's bio first (a team member's criteria are the
    team's), else the bio of the same name resolved against the CHILD's
    own cwd/state (project scope first, then user). None when neither has
    one (the byte-for-byte old path: no gate, no retry)."""
    if team_control is not None and role_name:
        try:
            bio = team_control.bio_for(role_name) or {}
            acceptance = bio.get("acceptance")
            if acceptance:
                return acceptance
        except Exception:
            pass
    from halo_harness.agents_yaml import resolve_agent_bio
    try:
        bio = resolve_agent_bio(spec.name, cwd=getattr(child, "cwd", None),
                                state_dir=getattr(child, "state_dir", None)) or {}
    except Exception:
        return None
    acceptance = bio.get("acceptance")
    return acceptance if isinstance(acceptance, dict) else None


def _check_return_acceptance(spec, role_name: "Optional[str]", team_control, child,
                             text: str) -> "tuple[bool, Optional[str]]":
    """`(ok, note)` -- note is None when no criteria applied (accepted by
    default, and the caller knows not to record a verdict). The check
    itself is `agents_doctor.check_expectation`, the SAME one the teams
    doctor and the pipeline gates use (a prompt-driven judge check is the
    doctor's own path; a live return stays local and deterministic)."""
    acceptance = _return_acceptance_for(spec, role_name, team_control, child)
    if not acceptance:
        return True, None
    from halo_harness.agents_doctor import check_expectation
    expect = acceptance.get("expect") or "non-empty"
    ok = bool(check_expectation(text or "", expect))
    return ok, f"acceptance {expect!r}"


def _acceptance_critique(spec, role_name: "Optional[str]", team_control, child, note: str) -> str:
    """The retry prompt: the bio's own `critique` wording when it has one,
    else a default that names the failed criterion. Sent as a SECOND user
    turn on the SAME child session (it keeps its context)."""
    acceptance = _return_acceptance_for(spec, role_name, team_control, child) or {}
    custom = acceptance.get("critique")
    if isinstance(custom, str) and custom.strip():
        return custom.strip()
    return ("Your previous result did not meet your acceptance criteria and was rejected. "
            f"Failed check: {note}. Re-read the criteria, fix the result, and return it again.")


def _record_outcome(parent, child, spec, role_name, team_control, agent_id: str, **verdict) -> None:
    """3.1.8.0 R3: the child's evidence.json beside its transcript and its outcomes.jsonl row
    (outcomes/session.py; never raises). `verdict`: is_error, stopped, acceptance, stage."""
    from halo_harness.outcomes.session import record_subagent
    record_subagent(parent, child, spec_name=spec.name, role_name=role_name, team_control=team_control,
                    agent_id=agent_id, **verdict)


def _rollup_child_cost_into_parent(parent, child, *, agent_id: str, since_index: int = 0,
                                    role: Optional[str] = None, ok: Optional[bool] = None,
                                    bio: Optional[str] = None) -> None:
    """H9 whole-tree review finding 13: a child's usage/cost used to be
    visible ONLY in its own `subagents/agent-<id>.jsonl` -- never reaching
    `parent.cost_meter` (so `--max-budget-usd`, which reads the PARENT's
    own `message_end.cost_usd`, could never trip on sub-agent spend, and
    the TUI's live status-bar total silently excluded it) nor the parent's
    OWN log (so `/stats`/`stats`, which read one session's `log.nodes()`,
    under-reported both tokens and cost). Called once a child's run ends
    (foreground `run_agent_call`, background `_bg_run`, and `_resume_task`
    -- every path that produces real model-call usage).

    `since_index`: a RESUMED child's `child.log.nodes()` includes every
    PRIOR turn's own "usage" nodes too (the log is reloaded from disk) --
    summing the whole file on every resume would roll up the same historic
    tokens again on top of what an earlier call already rolled up. Only
    nodes appended DURING *this* invocation (index `since_index` onward,
    captured by the caller right after `_build_child_session` returns, before
    `_run_child_to_completion` ever runs) are summed -- `child.cost_meter`
    itself is already scoped this way (a fresh CostMeter every Session
    construction, resumed or not), which is what makes `.turns`/`.total_usd`
    below correct as "this invocation's own total", no slicing needed for
    those two.

    `role` (V2c/H15, additive): this call's own resolved role name
    (`tool_input.get("role") or spec.role`, computed once by the caller),
    tagged onto the SAME rolled-up "usage" node `agent_id` already is --
    `telemetry.py`'s per-role aggregation (`stats --roles`) reads it back;
    `None` (every pre-V2c call site, and any role-less agent) logs no
    `role` field at all, exactly as before this parameter existed."""
    if child.cost_meter.turns <= 0:
        return
    combined: dict = {}
    # review finding 84: which (model, provider, route) the child spent on
    # -- the heaviest by tokens when it used more than one -- so `stats
    # --models` charges the child's row, not the parent's.
    spent_by: dict = {}
    for node in child.log.nodes()[since_index:]:
        if node.get("type") != "usage":
            continue
        usage = node.get("usage") or {}
        weight = 0
        for key in ("input_tokens", "output_tokens", "cache_read_input_tokens",
                    "cache_creation_input_tokens", "reasoning_tokens"):
            value = usage.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                combined[key] = combined.get(key, 0) + value
                weight += value
        if node.get("model"):
            ident = (node["model"], node.get("provider"), node.get("route"))
            spent_by[ident] = spent_by.get(ident, 0) + weight + 1
    child_model = max(spent_by, key=spent_by.get) if spent_by else (
        getattr(getattr(child, "model_ref", None), "raw", None), None, None)
    child_cost = child.cost_meter.total_usd if child.cost_meter.has_cost_data else None
    # `SessionLog.append_usage` locks internally (safe from any thread on
    # its own); `CostMeter.add_child_total` does not -- both a background
    # child's OWN thread (`_bg_run`) and several FOREGROUND children
    # running concurrently (a real ThreadPoolExecutor batch, per this
    # module's own docstring) can reach this at the same moment, so the
    # `total_usd +=` inside it is guarded with the SAME lock `_bg_run`
    # already uses for every other write to shared parent state.
    parent.log.append_usage(combined, child_cost, agent_id=agent_id, role=role, ok=ok, bio=bio,
                            model=child_model[0] if isinstance(child_model[0], str) else None,
                            provider=child_model[1], route=child_model[2])
    with parent._agent_notices_lock:
        parent.cost_meter.add_child_total(cost_usd=child_cost, has_cost_data=child.cost_meter.has_cost_data,
                                           turns=child.cost_meter.turns)


def _wrap_task_result(text: str, task_id: str) -> str:
    """H6 scope F (OpenCode adopt item): resumable sub-agent tasks -- a
    later `Agent(task_id=..., prompt=...)` resumes the SAME child session
    with its full prior context (via `Session.__init__`'s own resume path,
    reached because `_child_log_paths` preloads the existing log)."""
    return f'<task_result task_id="{task_id}">\n{text}\n</task_result>'


def _finalize_child_isolation_worktree(child) -> "Optional[str]":
    """finding 14 (W6a): the other half of `isolation: worktree` -- called
    once THIS child's run has fully ended (foreground and background
    alike). A no-op (`None`) when this child never got its own worktree
    (`_isolation_worktree_path` is None -- isolation wasn't requested, or
    creation fell back to the parent's own cwd). A CLEAN tree (`git
    status` empty) is removed -- firing WorktreeRemoved -- and its own
    `halo-worktree-*` branch deleted with it; a DIRTY one (the point of
    isolating it in the first place, most of the time) is left alone, and
    this returns a note naming its path/branch for the caller to append
    to the Agent result text, so the child's own work is never silently
    stranded under `~/.halo/worktrees` with no way for the user to find
    it again. Never raises."""
    wt_path = getattr(child, "_isolation_worktree_path", None)
    if wt_path is None:
        return None
    branch = getattr(child, "_isolation_worktree_branch", None)
    repo_root = getattr(child, "_isolation_worktree_repo_root", None) or wt_path.parent
    try:
        from halo_harness.shadow import git_status_dirty_paths
        dirty = git_status_dirty_paths(wt_path)
    except Exception:
        dirty = None
    if dirty:  # a real, non-empty set of uncommitted changes
        return (f"(this sub-agent's isolated worktree has uncommitted changes and was kept at "
                f"{wt_path}{f' on branch {branch}' if branch else ''} -- remove it yourself with "
                f"`halo worktree rm {wt_path}` once you're done with it)")
    if dirty is None:  # could not determine (not a repo somehow, git unreachable, ...) -- never guess
        return f"(this sub-agent's isolated worktree at {wt_path} was kept -- its status could not be checked)"
    try:
        from halo_harness.worktree import remove_worktree
        # review finding 28: `remove_worktree` now deletes the worktree's
        # own branch itself, right after a successful removal -- the
        # separate `git branch -D` this used to run again here (after
        # already passing its OWN upfront dirty check above, before
        # `remove_worktree` grew the identical check internally) is gone;
        # `_reason` is only ever "dirty"/"failed" when `removed` is False,
        # already covered above/below.
        removed, _reason = remove_worktree(wt_path, repo_root_hint=repo_root)
    except Exception:
        removed = False
    if removed:
        try:
            child._fire_worktree_removed(wt_path)
        except Exception:
            pass
    return None


def _hydrate_tasks_from_disk(runtime: AgentRuntime) -> None:
    """H9 whole-tree review finding 27 (task-map persistence half):
    `runtime.tasks` is in-memory only, so a fresh process (a `-c` resume,
    most commonly, but also a brand new launch someone points at an
    existing session id) starts with it EMPTY -- every task_id the model
    remembers from before the restart would otherwise come back "Unknown
    task_id", even though its child log and meta.json are sitting right
    there on disk. Runs at most ONCE per runtime (guarded by
    `tasks_hydrated`, checked/set under `runtime.lock` alongside every
    other mutation of `runtime.tasks`): globs THIS session's own
    `subagents/agent-*.meta.json` -- the exact directory `_child_log_paths`
    writes into, unchanged across a `-c` resume since that reuses the SAME
    session_id/dir -- and reinserts one `runtime.tasks[task_id]` entry per
    file that has one. A meta.json from before this finding was fixed has
    no `task_id` field and is silently skipped; that task is unrecoverable,
    same as before this fix (no regression, just not a NEW capability for
    OLD sessions).

    `abort_event` is always None for a reconstructed entry: the real
    `threading.Event` lived only in the OLD process's memory and died with
    it. That is not a gap needing a workaround, though -- `_bg_run` runs on
    a `daemon=True` thread specifically because a background sub-agent must
    never outlive the process that started it (same rule Bash background
    jobs follow, see `agent/jobs.py`), so a task whose meta.json still says
    `"background": True` after a restart was, definitionally, killed
    mid-flight along with the old process; there is no live thread left
    anywhere to signal, abort or race against. `tools/task_stop.py` checks
    `abort_event is None` and reports it as nothing-to-stop rather than
    claiming a foreground-only task, using the persisted `"background"`
    flag (`reconstructed`/`was_background` below) to word that correctly.
    """
    with runtime.lock:
        if runtime.tasks_hydrated:
            return
        runtime.tasks_hydrated = True
    parent = runtime.parent
    subdir = parent.log.dir / parent.log.session_id / "subagents"
    if not subdir.is_dir():
        return
    for meta_path in sorted(subdir.glob("agent-*.meta.json")):
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        task_id = data.get("task_id")
        session_id = data.get("session_id")
        spec_name = data.get("type")
        if not (isinstance(task_id, str) and task_id and isinstance(session_id, str)
                and isinstance(spec_name, str)):
            continue
        with runtime.lock:
            if task_id in runtime.tasks:
                continue  # already known -- e.g. hydration raced a call that just created it
            runtime.tasks[task_id] = {
                "child_session_id": session_id, "spec_name": spec_name, "cwd": str(parent.cwd),
                "abort_event": None, "reconstructed": True, "running_in_process": False,
                "was_background": bool(data.get("background")),
                **{k: data[k] for k in _OVERRIDE_KEYS if isinstance(data.get(k), str) and data[k]},
            }


def _override_fields(role: "Optional[str]", model: "Optional[str]", effort: "Optional[str]") -> dict:
    """vibes/review.md finding 56: the per-call `role=`/`model=`/`effort=`
    a task was spawned with, as the keys stored on its `runtime.tasks`
    record and in its meta.json (only the ones actually set), so a later
    `Agent(task_id=...)` resume keeps resolving the same way."""
    return {k: v for k, v in (("role_override", role), ("model_override", model),
                              ("effort_override", effort)) if isinstance(v, str) and v}


_OVERRIDE_KEYS = ("role_override", "model_override", "effort_override")


def _invalid_role_error(role: "Optional[str]", runtime: "Optional[AgentRuntime]" = None) -> "Optional[str]":
    """2.0.2 review finding 22: `None` when `role` is unset or a KNOWN
    role name; otherwise an error string listing the known roles. Shared
    by every `Agent(role=...)` surface (single call, batch/count fan-out
    items, and task resume) -- none of them checked this before, so a
    typo'd role silently fell through to resolving against the session
    model instead of erroring the way an unknown `subagent_type` already
    does."""
    if not role:
        return None
    from halo_harness.roles import known_role_names
    # vibes/review.md finding 60: a role the active team (or the session's
    # resolved role table) defines is a valid name for `Agent(role=...)`,
    # not only the built-ins and the persisted config table.
    extra: list = []
    if runtime is not None:
        extra.append(getattr(runtime, "role_table", None))
        _tc = getattr(runtime, "team_control", None)
        extra.append(getattr(_tc, "aliases", None) if _tc is not None else None)
    known = known_role_names(*[t for t in extra if isinstance(t, dict)])
    if role in known:
        return None
    return f"Unknown role {role!r}. Known roles: {', '.join(known)}"


def _prepare_fanout_jobs(spec: AgentSpec, tool_input: dict,
                         runtime: "Optional[AgentRuntime]" = None) -> "tuple[Optional[list], Optional[str]]":
    """Parses `count`/`batch` into a list of per-job dicts (`prompt`,
    `role`, `model`, `effort`, `description`) -- `(jobs, None)` on
    success, `(None, error_text)` on a bad shape. The caller only reaches
    this when at least one of `count`/`batch` is not None; `batch` wins
    if somehow both were given."""
    description = tool_input.get("description") or spec.description[:60]
    batch = tool_input.get("batch")
    if batch is not None:
        if not isinstance(batch, list) or not batch:
            return None, "batch must be a non-empty list of {prompt, role?, model?, effort?} objects"
        jobs = []
        for i, item in enumerate(batch):
            if not isinstance(item, dict) or not item.get("prompt"):
                return None, f"batch[{i}] must be an object with a non-empty 'prompt' field"
            item_role = item.get("role") or tool_input.get("role")
            # finding 22: an unknown role in a batch item (or the shared
            # top-level one) used to silently resolve to the session model.
            role_error = _invalid_role_error(item_role, runtime)
            if role_error is not None:
                return None, f"batch[{i}]: {role_error}"
            jobs.append({
                "prompt": item["prompt"], "role": item_role,
                "model": item.get("model") or tool_input.get("model"),
                # 2.0.2 review finding 21: a batch item used to drop the
                # top-level `effort` entirely when it had none of its own,
                # although docs/SUBAGENTS.md says it falls back.
                "effort": item.get("effort") or tool_input.get("effort"),
                "description": (item.get("description") or description)[:60],
            })
        return jobs, None
    try:
        n = int(tool_input.get("count"))
    except (TypeError, ValueError):
        return None, "count must be a positive integer"
    if n <= 0:
        return None, "count must be a positive integer"
    if n > 50:
        return None, "count may not exceed 50 in one call"
    prompt = tool_input.get("prompt") or spec.initial_prompt or description
    if not prompt:
        return None, "The prompt parameter is required"
    role_error = _invalid_role_error(tool_input.get("role"), runtime)  # finding 22
    if role_error is not None:
        return None, role_error
    jobs = [{"prompt": prompt, "role": tool_input.get("role"), "model": tool_input.get("model"),
             # finding 21: `count` used to ignore the call's own `effort`
             # outright -- every job got `None` regardless of what was asked.
             "effort": tool_input.get("effort"), "description": description[:60]} for _ in range(n)]
    return jobs, None


def _run_agent_fanout(*, runtime: AgentRuntime, spec: AgentSpec, tool_id: str, tool_input: dict,
                       on_event=None) -> "tuple[list, object]":
    """Halo 2.0.2 round 3 (brief C): `count`/`batch` -- spawns several
    children of `spec` and waits for ALL of them, capped at `effective_
    max_concurrent(runtime)` the same way several separate Agent tool_use
    blocks in one turn already are (`agent/loop.py`'s own `_run_agent_
    batch`). Excess jobs QUEUE: every job's own agent_id/task_id is
    minted and a `subagent_queued` event fired for it, in SPAWN order,
    BEFORE any pool worker has even started picking them up -- so the
    tasks panel shows every job immediately, never only once a slot
    frees. Returns ONE combined ToolResult: one `<task_result>` section
    per child, in SPAWN order (never completion order -- a slow 2nd
    child must not reshuffle a fast 5th one ahead of it in the model's
    own reading of the result). `on_event`, same contract as `run_agent_
    call`'s own: None means no genuinely LIVE consumer exists, so a
    child's own live permission/question asks are disabled (same
    `_subagent_live_asks` guard the single-spawn path already applies)
    rather than risking a child parked forever waiting for an answer
    nothing will ever deliver."""
    from halo_harness.tools.base import ToolResult

    jobs, error = _prepare_fanout_jobs(spec, tool_input, runtime)
    if error is not None:
        return [], ToolResult(error, is_error=True)
    n = len(jobs)
    if n > 1:
        for i, job in enumerate(jobs):
            job["description"] = f"{job['description']} ({i + 1}/{n})"

    parent = runtime.parent
    live_asks_ok = on_event is not None
    all_events: list = []
    events_lock = threading.Lock()

    def _emit(ev) -> None:
        with events_lock:
            all_events.append(ev)
        if on_event is not None:
            on_event(ev)

    prepared = []  # [(agent_id, task_id, job), ...], in spawn order
    for job in jobs:
        agent_id = _new_agent_id()
        new_task_id = uuid.uuid4().hex[:12]
        with runtime.lock:
            runtime.tasks[new_task_id] = {"child_session_id": f"agent-{agent_id}", "spec_name": spec.name,
                                           "cwd": str(parent.cwd), "abort_event": None,
                                           "running_in_process": True, "status": "queued",
                                           **_override_fields(job["role"], job["model"], job["effort"])}
        # A minimal meta.json stub, written up front -- the tasks panel
        # reads meta.json (what survives a `-c` resume), not just this
        # in-memory dict, so it must see "queued" right away; `_build_
        # child_session` (inside `_run_one_fanout_child`) naturally
        # overwrites/merges this SAME file with "running" once this job
        # actually starts (`_write_meta` merges onto existing content).
        _, meta_path = _child_log_paths(parent, agent_id)
        _write_meta(meta_path, {"agent_id": agent_id, "type": spec.name, "description": job["description"],
                                 "status": "queued", "task_id": new_task_id, "parent_tool_use_id": tool_id})
        queued_ev = events.Event("subagent_queued", {"agent_id": agent_id, "name": spec.name,
                                                        "description": job["description"],
                                                        "parent_tool_use_id": tool_id, "task_id": new_task_id})
        queued_ev.agent_id = agent_id
        _emit(queued_ev)
        _agent_tree.register_queued(parent, agent_id, name=spec.name, task=job["prompt"],
                                    role=job["role"] or spec.role)
        prepared.append((agent_id, new_task_id, job))

    results: list = [None] * n

    def _run_one(index: int) -> None:
        agent_id, new_task_id, job = prepared[index]
        try:
            results[index] = _run_one_fanout_child(
                runtime=runtime, spec=spec, agent_id=agent_id, new_task_id=new_task_id, job=job,
                tool_id=tool_id, on_event=_emit, live_asks_ok=live_asks_ok,
            )
        except Exception as e:  # this module's own contract: never raise out of a spawn path
            log.exception("fan-out child dispatch failed for task_id=%r", new_task_id)
            results[index] = (f"Sub-agent dispatch failed: {type(e).__name__}: {e}", True)

    max_workers = min(effective_max_concurrent(runtime), n)
    # 2.0.2 review finding 10: `wrap_for_pool`, called on THIS (the
    # submitting) thread -- see `SessionConcurrencyGate`'s own docstring
    # for why a bare `threading.local` cannot do this across the thread
    # boundary a fresh pool worker always is.
    with runtime.concurrency_semaphore.pool(max_workers=max_workers, limit=effective_max_concurrent(runtime)) as pool:
        for f in [pool.submit(_run_one, i) for i in range(n)]:
            f.result()

    sections = []
    any_error = False
    for i, ((_agent_id, new_task_id, _job), (text, is_error)) in enumerate(zip(prepared, results, strict=True)):
        any_error = any_error or is_error
        sections.append(f"--- child {i + 1}/{n} (task_id={new_task_id}) ---\n{text}")
    # 2.0.2 review finding 27: each section is individually uncapped
    # (`AgentTool.result_cap=None` -- "this tool manages its own
    # truncation", unlike every other tool, which `spill_and_truncate`
    # in agent/loop.py caps generically) -- `count=50` could return
    # ~1.5M chars in one tool_result. Capped the same way the single-
    # spawn/resume paths already cap THEIR own result (`RESULT_CAP`,
    # head/tail + a spill file for the full combined text).
    from halo_harness.tools.truncate import spill_and_truncate
    combined = spill_and_truncate("\n\n".join(sections), cap=RESULT_CAP,
                                   session_dir=parent.log.dir / parent.log.session_id, tool_use_id=tool_id)
    return all_events, ToolResult(combined, is_error=any_error)


def _run_one_fanout_child(*, runtime: AgentRuntime, spec: AgentSpec, agent_id: str, new_task_id: str,
                           job: dict, tool_id: str, on_event, live_asks_ok: bool) -> "tuple[str, bool]":
    """One `count`/`batch` job's own full build-run-finalize sequence --
    the same steps `run_agent_call`'s single-spawn foreground path runs,
    parameterized by a PRE-MINTED `agent_id`/`task_id` (minted by `_run_
    agent_fanout` before this job ever reached a pool slot, so it could
    be announced as "queued" immediately) and this job's own prompt/
    role/model/effort. `on_event` here is always a real callable (`_run_
    agent_fanout`'s own `_emit`, which both collects and optionally
    forwards); `live_asks_ok` carries whether the ORIGINAL caller gave
    `_run_agent_fanout` a genuinely live channel -- a bare `_emit` with
    nothing live downstream must still disable `_subagent_live_asks`,
    exactly like the single-spawn path's own `on_event is None` check."""
    from halo_harness.tools.truncate import spill_and_truncate

    parent = runtime.parent
    role_name = job["role"] or spec.role
    try:
        # 2.0.2 review finding 11 (major): after Esc, every QUEUED fan-out
        # job used to still build a child session (a worktree included,
        # when isolated), fire SubagentStart/TaskCreated + SubagentStop/
        # TaskCompleted, and write logs -- undoing H5c finding 7's own
        # abort-batch contract, which `_run_agent_batch` (several separate
        # Agent tool_use blocks in one turn) already enforces. A job
        # already past this point shares `runtime.parent.abort` with every
        # OTHER foreground child (`_build_child_session`'s own `abort=`),
        # so it already reacts to Esc mid-turn with no change needed here.
        if parent.abort.is_set():
            _, not_started_meta_path = _child_log_paths(parent, agent_id)
            _write_meta(not_started_meta_path, {"status": "not_started", "is_error": True, "finished": time.time()})
            return "Sub-agent not started: interrupted by the user.", True
        child, meta_path = _build_child_session(
            runtime=runtime, spec=spec, agent_id=agent_id, model_override=job["model"],
            parent_tool_use_id=tool_id, background=False, role_override=job["role"],
            effort_override=job["effort"], task_text=f"{job.get('description') or ''}\n{job.get('prompt') or ''}",
        )
        if not live_asks_ok:
            child._subagent_live_asks = False
        since_index = len(child.log.nodes())
        runtime.live_children[agent_id] = child
        _write_meta(meta_path, {"task_id": new_task_id, "background": False,
                                **_override_fields(job["role"], job["model"], job["effort"])})
        with runtime.lock:
            entry = runtime.tasks.get(new_task_id)
            if entry is not None:
                entry["status"] = "running"

        _dock_name = spec.name
        start_ev = events.Event("subagent_start", {"agent_id": agent_id, "name": _dock_name,
                                                     "description": job["description"],
                                                     "parent_tool_use_id": tool_id, "task_id": new_task_id})
        start_ev.agent_id = agent_id
        _fire_subagent_hook(child, "SubagentStart")
        _fire_task_hook(parent, "TaskCreated", task_id=new_task_id, spec_name=spec.name,
                         description=job["description"])
        on_event(start_ev)

        try:
            # 2.0.2 review finding 10: the session-wide cap, not just
            # this one fan-out call's own pool (sized separately, below).
            with runtime.concurrency_semaphore:
                child_events = _run_child_to_completion(child, job["prompt"], agent_id=agent_id,
                                                          parent_tool_use_id=tool_id, on_event=on_event)
        finally:
            child.close_runtimes()
            runtime.live_children.pop(agent_id, None)

        text = _final_text_from_log(child)
        is_error, abnormal_reason = _child_turn_outcome(child_events)
        _fire_subagent_hook(child, "SubagentStop")
        _fire_task_hook(parent, "TaskCompleted", task_id=new_task_id, spec_name=spec.name,
                         description=job["description"])
        _write_meta(meta_path, {"status": "completed", "is_error": is_error, "finished": time.time()})
        _rollup_child_cost_into_parent(parent, child, agent_id=agent_id, since_index=since_index, role=role_name,
                                       ok=not is_error, bio=spec.name)
        _forward_child_escalation_decisions(parent, child, spec)
        with parent._agent_notices_lock:
            parent.permission_denials.extend(child.permission_denials)
        _record_outcome(parent, child, spec, role_name, runtime.team_control, agent_id, is_error=is_error,
                        stopped=_fleet_stopped(child))  # 3.1.8.0 R3
        end_ev = events.Event("subagent_end", {"agent_id": agent_id, "name": _dock_name,
                                                  "parent_tool_use_id": tool_id, "task_id": new_task_id,
                                                  "is_error": is_error})
        end_ev.agent_id = agent_id
        on_event(end_ev)
        if is_error:
            # 2.0.7 dead-model-id round: same decoration the fresh-spawn
            # path got -- the child's own last error message rides the
            # handback (the 404's own words, never a silent empty result).
            _child_err = _last_child_error_text(child_events)
            if _child_err:
                text = (f"[sub-agent did not finish normally ({abnormal_reason}): {_child_err}\n"
                        f"this may be a stale/partial answer]\n{text}")
            else:
                text = (f"[sub-agent did not finish normally ({abnormal_reason}) -- this may be a "
                         f"stale/partial answer]\n{text}")
        worktree_note = _finalize_child_isolation_worktree(child)
        if worktree_note:
            text = f"{text}\n\n{worktree_note}"
        wrapped = _wrap_task_result(text, new_task_id)
        capped = spill_and_truncate(wrapped, cap=RESULT_CAP, session_dir=parent.log.dir / parent.log.session_id,
                                     tool_use_id=f"{tool_id}-{agent_id}")
        return capped, is_error
    finally:
        with runtime.lock:
            entry = runtime.tasks.get(new_task_id)
            if entry is not None:
                entry["running_in_process"] = False


def run_agent_call(*, runtime: AgentRuntime, tool_id: str, tool_input: dict, tool_name: str,
                    on_event=None, on_child=None) -> "tuple[list, object]":
    """`(events, ToolResult)` for ONE Agent/Task tool_use. Never raises --
    every failure mode becomes an `is_error` ToolResult so a sub-agent's
    own bug can never crash the parent's turn. `on_event` (H5c finding 8):
    forwarded to the FOREGROUND child's own `_run_child_to_completion` so
    its events (most importantly `permission_request`) reach a live caller
    the instant they happen -- never used for a background child (see
    `_bg_run`, whose events are not forwarded to any live stream).

    Halo 2.0.7 round 0c: `on_child`, when given, is called ONCE with the
    child Session right after it is built (before its turn ever runs) --
    agent/loop.py's agent-batch runner uses it to keep a handle on each
    live child so a steer typed while the batch runs can be FORWARDED
    into it, and so a forwarded steer the child never got to apply can be
    handed back to the parent when the child finishes."""
    from halo_harness.tools.base import ToolResult
    from halo_harness.tools.truncate import spill_and_truncate

    _hydrate_tasks_from_disk(runtime)
    # The runtime's own `max_depth` (a lineup's delegation.max_depth,
    # propagated to every descendant by `_build_child_session`) overrides
    # the `agents.max_depth` config knob when set -- see `effective_
    # max_depth`'s own docstring.
    _max_depth = effective_max_depth(runtime)
    if runtime.depth >= _max_depth:
        return [], ToolResult(
            "Sub-agents cannot spawn further sub-agents (depth limit reached) -- finish this task "
            "yourself instead of delegating further.", is_error=True,
        )

    tool_input = tool_input if isinstance(tool_input, dict) else {}
    parent = runtime.parent
    task_id = tool_input.get("task_id")
    if task_id:
        return _resume_task(runtime, task_id, tool_input, tool_id, on_event=on_event)

    subagent_type = tool_input.get("subagent_type") or "general-purpose"
    spec = runtime.agents.get(subagent_type)
    if spec is None:
        known = ", ".join(sorted(runtime.agents)) or "(none discovered)"
        return [], ToolResult(f"Unknown subagent_type {subagent_type!r}. Known types: {known}", is_error=True)
    restriction = getattr(parent, "agent_type_restriction", None)
    if restriction is not None and subagent_type not in restriction:
        return [], ToolResult(f"This session may not spawn subagent_type {subagent_type!r}.", is_error=True)
    # Halo 2.0.5 round 5 "team control": a team budget that is out stops
    # DELEGATION right here, before any model call, with its one-line
    # reason -- same shape as the depth check above. `agents_may_
    # exceed: true` keeps members running (the budget is advisory); the
    # line is still recorded so `escalation.triggers: budget_exhausted`
    # and `/teams` reporting can see it.
    team_control = getattr(runtime, "team_control", None)
    if team_control is not None:
        team_refusal = team_control.budget_refusal()
        if team_refusal and not team_control.budget.get("agents_may_exceed"):
            return [], ToolResult(team_refusal, is_error=True)

    # Halo 2.0.2 round 3 (brief C): `count` (N identical prompts) / `batch`
    # (a list of per-child prompt+role+model+effort overrides) spawn
    # several children of `subagent_type` in ONE call, capped at `agents.
    # max_concurrent` the same way several separate Agent tool_use blocks
    # in one turn already are -- see `_run_agent_fanout`'s own docstring.
    if tool_input.get("count") is not None or tool_input.get("batch") is not None:
        if bool(tool_input.get("run_in_background")) or spec.background:
            return [], ToolResult("count/batch cannot be combined with run_in_background -- the parent "
                                   "already waits on every fan-out child; run them one at a time in the "
                                   "background instead if that's what you need.", is_error=True)
        return _run_agent_fanout(runtime=runtime, spec=spec, tool_id=tool_id, tool_input=tool_input,
                                  on_event=on_event)

    description = tool_input.get("description") or spec.description[:60]
    prompt = tool_input.get("prompt") or spec.initial_prompt or description
    background = bool(tool_input.get("run_in_background")) or spec.background
    model_override = tool_input.get("model")
    # V2c (H15): `Agent(role=...)` overrides this agent's own file/built-in
    # role for just this one call; `role_name` (used below for the cost
    # rollup's own `stats --roles` tag) mirrors exactly what `resolve_agent_
    # model` inside `_build_child_session` resolves the role AGAINST.
    role_override = tool_input.get("role")
    # finding 22: a typo'd/unknown `Agent(role=...)` used to silently
    # resolve against the session model instead of erroring the way an
    # unknown subagent_type already does.
    role_error = _invalid_role_error(role_override, runtime)
    if role_error is not None:
        return [], ToolResult(role_error, is_error=True)
    role_name = role_override or spec.role
    # Halo 2.0.2 round 3 (brief C): `Agent(effort=...)` overrides this
    # agent's own file/role/parent-inherited effort for just this one
    # call -- same rung `_run_one_fanout_child`'s own per-job `effort`
    # already occupies (see `_build_child_session`'s own `_effective_
    # effort` precedence chain).
    effort_override = tool_input.get("effort")
    # Halo 2.0.5 round 5 "team control": under a team, `routing` maps the
    # task to a role/alias (the model's own explicit `role=` still wins),
    # and `pipeline` gates stages in order -- a `required` gate that has
    # not passed blocks every later stage with its one-line reason. The
    # routed target rides the SAME `role_override` slot an Agent(role=...)
    # call already uses, so `_build_child_session`/`resolve_agent_model`
    # resolve the member's model through the role table the template
    # filled (`teams_yaml.resolve_role_table`). Explicit count/batch
    # fan-outs (returned from above) skip routing by design: they already
    # name their own per-child roles.
    team_stage = None
    if team_control is not None:
        team_kind, team_target = team_control.route_call(tool_input, description)
        if team_target and not role_override:
            # The routed target is one of THIS team's aliases/roles (the
            # template's own resolved table may never have been persisted
            # -- `--team` runs without touching config), so validate
            # against the team's OWN alias map first, the global role
            # table second.
            if team_target not in team_control.aliases:
                role_error = _invalid_role_error(team_target, runtime)
                if role_error is not None:
                    return [], ToolResult(role_error, is_error=True)
            role_override = team_target
            role_name = team_target
        # Halo 3.0.7.0 R1 "tiers": a member spawns only into the next tier
        # down, and the target tier's `max_parallel` counts its live members
        # across the whole tree -- one line naming the rule, same shape as
        # the gate stop below. The top session is the main agent; a child
        # is the alias it was resolved under. No `tiers` = every spawn passes.
        tier_caller = team_control.main_alias() if runtime.depth == 0 else getattr(parent, "role_name", None)
        tier_stop = team_control.spawn_refusal(tier_caller, role_name, root=runtime.depth == 0)
        if tier_stop is not None:
            return [], ToolResult(tier_stop, is_error=True)
        team_stage = team_control.stage_for(team_kind, team_target)
        gate_stop = team_control.gate_block(team_stage)
        if gate_stop is not None:
            return [], ToolResult(gate_stop, is_error=True)
        # `delegation.forward_text: true` hands the child the parent's own
        # latest user text as leading context (capped); the default (false)
        # keeps the delegation prompt exactly what the model typed.
        if team_control.delegation.get("forward_text"):
            forward = _team_forward_prefix(parent)
            if forward:
                prompt = f"{forward}\n\n{prompt}"

    agent_id = _new_agent_id()
    try:
        child, meta_path = _build_child_session(
            runtime=runtime, spec=spec, agent_id=agent_id, model_override=model_override, parent_tool_use_id=tool_id,
            background=background, role_override=role_override, effort_override=effort_override,
            task_text=f"{description}\n{prompt}",
        )
    except Exception as e:
        # 2.0.2 review finding 4 (major): this module's own docstring says
        # "Never raises" -- an unresolvable model (a bad bio `model:`, or
        # a `/role` pointed at a bogus ref) raised InvalidModelError
        # straight out of here instead. A minimal meta.json is written here too, so the tasks
        # panel shows this attempt as a real, finished (errored) entry
        # instead of nothing at all.
        _, failed_meta_path = _child_log_paths(parent, agent_id)
        _write_meta(failed_meta_path, {"agent_id": agent_id, "type": spec.name, "description": description,
                                        "status": "completed", "is_error": True, "finished": time.time(),
                                        "parent_tool_use_id": tool_id})
        return [], ToolResult(f"Could not start sub-agent '{spec.name}': {type(e).__name__}: {e}", is_error=True)
    # finding 10 (W6a): `_build_child_session` sets `_subagent_live_asks`
    # from `parent.interactive` ALONE, with no way to know whether THIS
    # caller actually gave it a live channel to forward an ask through --
    # a `context: fork`/`agent` Skill (tools/skill.py) calls this directly
    # with no `on_event` at all, so a foreground child of an interactive
    # parent got the live/blocking ask path (`_await_permission_decision`/
    # `_await_reply`) with its `permission_request`/`question` event
    # reaching no live consumer whatsoever -- the turn hung until Esc,
    # nothing ever visibly asked. A BACKGROUND child is unaffected: it has
    # its OWN separate live-ask channel (`_bg_run`'s own `on_event`, built
    # below from `parent._event_sink`), unrelated to this `on_event`
    # parameter.
    if not background and on_event is None:
        child._subagent_live_asks = False
    # 2.0.7 round 0c: the caller's child handle (see this function's own
    # docstring) -- before anything can fail, so a caller that wants to
    # forward steers always has it.
    if on_child is not None:
        try:
            on_child(child)
        except Exception:
            pass
    # Halo 2.0.5 round 5: team `permissions.offline` -- offline mode is
    # process-global in this harness (env/config), so a per-member "runs
    # offline" is enforced at the SPAWN point instead: a member whose
    # resolved model lives on a non-loopback, non-allowlisted host never
    # starts, with the same host rule the real request gate applies.
    if team_control is not None and team_control.member_permissions().get("offline"):
        from halo_harness.providers.http import _is_loopback_host, allowlisted_local_hosts
        # vibes/review.md finding 24: this block read a bare `model_ref` that
        # has never existed in this scope (pyflakes F821) -- every Agent call
        # on a team template with `permissions.offline: true` died as a
        # NameError instead of producing this explanatory ToolResult, and the
        # failed-meta write below never happened either (the child "leaked" in
        # the tasks panel as forever-running). The child session's OWN
        # resolved ref is what the host rule must judge.
        _host = getattr(child.model_ref, "host", None)
        if not _is_loopback_host(_host) and (_host or "").strip().lower() not in allowlisted_local_hosts():
            _, failed_meta_path = _child_log_paths(parent, agent_id)
            _write_meta(failed_meta_path, {"agent_id": agent_id, "type": spec.name, "description": description,
                                            "status": "completed", "is_error": True, "finished": time.time(),
                                            "parent_tool_use_id": tool_id})
            return [], ToolResult(
                f"team permissions.offline: member {spec.name!r} resolves to {child.model_ref.raw} (host {_host or '?'}) "
                f"-- a network host this team runs offline against; point the role at a local model "
                f"or drop permissions.offline from the template.", is_error=True)
    # H9 whole-tree review finding 13: captured BEFORE the child ever makes
    # a model call -- a resumed child's own log already carries every PRIOR
    # invocation's "usage" nodes (reloaded from disk); only nodes appended
    # from here on belong to THIS call. A fresh (non-resumed) child's log
    # is empty at this point, so this is just 0.
    since_index = len(child.log.nodes())
    # H11b finding 14: registered before the child's own turn ever runs --
    # `close_runtimes()` (this module's `_bg_run`/foreground `finally` below)
    # needs to find it here even if the child's very first turn never
    # completes normally.
    runtime.live_children[agent_id] = child
    if team_control is not None:
        team_control.tier_claim(agent_id, role_name)  # 3.0.7.0 R1: counts against its tier's max_parallel
    new_task_id = uuid.uuid4().hex[:12]
    with runtime.lock:
        runtime.tasks[new_task_id] = {"child_session_id": child.log.session_id, "spec_name": spec.name,
                                        "cwd": str(parent.cwd),
                                        # H9 whole-tree review finding 10:
                                        # only present (and only meaningful)
                                        # for a background child -- a
                                        # foreground one shares the
                                        # parent's own Event, already
                                        # reachable through the normal Esc
                                        # path. tools/task_stop.py reads
                                        # this to implement
                                        # `TaskStop(task_id=<agent task>)`.
                                        "abort_event": (child.abort if background else None),
                                        # H9 whole-tree review finding 27
                                        # (concurrent-resume half): True from
                                        # here until `_bg_run`'s own
                                        # `finally` flips it back, ALWAYS
                                        # scoped to THIS process (never
                                        # reconstructed as True by
                                        # `_hydrate_tasks_from_disk`, since a
                                        # restart always means the thread
                                        # that would have flipped it is
                                        # gone) -- `_resume_task` refuses a
                                        # resume while this is True instead
                                        # of racing `_bg_run`'s own appends
                                        # to the SAME child log file.
                                        "running_in_process": background,
                                        **_override_fields(role_override, model_override, effort_override)}
    # H9 whole-tree review finding 27 (task-map persistence half): the
    # task_id just minted lives ONLY in the in-memory dict updated above --
    # a fresh process (a `-c` resume, most commonly) would never see it and
    # would call every one of the model's own task_ids "Unknown". Persist
    # it (and whether this task is backgrounded) into the SAME meta.json
    # `_build_child_session` already wrote a "status"/"session_id"/"type"
    # for, so `_hydrate_tasks_from_disk` can reconstruct this exact entry
    # (minus `abort_event`, which cannot survive a process restart -- see
    # that function's own docstring) on a later process's first Agent or
    # TaskStop call.
    _write_meta(meta_path, {"task_id": new_task_id, "background": background,
                            **_override_fields(role_override, model_override, effort_override)})

    _dock_name = spec.name
    start_ev = events.Event("subagent_start", {"agent_id": agent_id, "name": _dock_name, "description": description,
                                                 "parent_tool_use_id": tool_id, "task_id": new_task_id})
    start_ev.agent_id = agent_id
    _fire_subagent_hook(child, "SubagentStart")
    _fire_task_hook(parent, "TaskCreated", task_id=new_task_id, spec_name=spec.name, description=description)
    if on_event is not None:
        # H5c finding 8: emitted LIVE too (not just in the returned list),
        # so a streaming caller's UI shows "sub-agent started" before the
        # child's own first event, not only once the whole call returns.
        on_event(start_ev)

    if background:
        _write_meta(meta_path, {"status": "background"})

        def _bg_run():
            # H9 whole-tree review finding 27 (concurrent-resume half):
            # everything below runs inside try/finally purely so the
            # `finally` can flip `running_in_process` back to False NO
            # MATTER HOW this thread ends, including a bug/exception deep
            # in `_run_child_to_completion` -- leaving it stuck True would
            # permanently refuse any future resume of this task_id, a worse
            # outcome than the race this flag exists to prevent.
            try:
                # W4a: forwards this BACKGROUND child's live ASKS
                # (permission/question/plan) straight into the parent's own
                # live event queue (`Session._event_sink`, set by `run()` --
                # the TUI's worker-thread command pump; None for a `-p`/
                # bare-Session run, where this is exactly the old no-
                # forwarding behaviour) -- the SAME dock a foreground
                # child's asks already reach.
                #
                # Halo 2.0.2 round C (the owner's own background-streaming
                # report): ALSO translates `phase`/`tool_use_ready` into the
                # narrower `subagent_progress` kind (events.py's own
                # docstring on it explains why a raw, unfiltered forward
                # isn't used here) so this child's `SubAgentCard` keeps
                # ticking with a real phase word/tool count while it runs,
                # instead of sitting on "thinking, 0 tools" until
                # `subagent_end`. Still deliberately narrower than a
                # foreground child's own full `on_event` forwarding: no
                # text/thinking content, no tool-card/phase-line widgets --
                # "not making a background task's whole output stream
                # suddenly live" (it still reports the real answer via the
                # existing completion notice).
                bg_sink = getattr(parent, "_event_sink", None)

                def on_event(ev, _sink=bg_sink):
                    if _sink is None:
                        return
                    if ev.kind in ("permission_request", "question", "plan_review"):
                        _sink(ev)
                    elif ev.kind == "phase":
                        word = _bg_phase_word(ev.data.get("state"), ev.data.get("kind"))
                        if word:
                            progress = events.subagent_progress(phase_word=word)
                            progress.agent_id = agent_id
                            _sink(progress)
                    elif ev.kind == "tool_use_ready":
                        progress = events.subagent_progress(tool_call=True)
                        progress.agent_id = agent_id
                        _sink(progress)

                if bg_sink is None:
                    on_event = None
                with runtime.concurrency_semaphore:  # 2.0.2 review finding 10: session-wide, not just one pool's own
                    child_events = _run_child_to_completion(child, prompt, agent_id=agent_id,
                                                             parent_tool_use_id=tool_id, on_event=on_event)
                text = _final_text_from_log(child)
                _fire_subagent_hook(child, "SubagentStop")
                _fire_task_hook(parent, "TaskCompleted", task_id=new_task_id, spec_name=spec.name, description=description)
                # 2.0.6 round 2: the bg path never computed the outcome
                # before its rollup -- `ok` needs it (per-role cost
                # attribution: accepted vs failed tasks per role).
                bg_is_error, _bg_reason = _child_turn_outcome(child_events)
                _write_meta(meta_path, {"status": "completed", "is_error": bg_is_error, "finished": time.time()})
                # H9 whole-tree review finding 13: roll this background child's
                # own usage/cost into the parent BEFORE the completion notice
                # is queued, so by the time the parent's next turn (which
                # applies that notice) actually runs, `--max-budget-usd`/
                # `/stats` already reflect it.
                _rollup_child_cost_into_parent(parent, child, agent_id=agent_id, since_index=since_index, role=role_name,
                                               ok=not bg_is_error, bio=spec.name)
                _forward_child_escalation_decisions(parent, child, spec)
                # Halo 2.0.5 round 5 "team control" -- the background
                # completion half of the foreground block below: budget
                # accounting, the stage gate, the handoff shape, and the
                # member's one-line report. `child.cost_meter.total_usd`
                # is already scoped to exactly this call (a fresh CostMeter
                # per Session construction).
                bg_stage = None  # 3.1.8.0 R3: the stage gate's verdict, for the outcome row
                if team_control is not None:
                    team_control.record_spend(child.cost_meter.total_usd)
                    team_control.record_turn(getattr(child, "turn_count", 0) or 0)
                    if team_stage is not None:
                        ok, gate_line = team_control.evaluate_stage(team_stage, text)
                        team_control.record_stage(team_stage, ok, gate_line)
                        bg_stage = (ok, gate_line)
                        if not ok:
                            text = (f"{text}\n\nstage {team_stage.get('name')!r} gate did not pass "
                                    f"({gate_line})" + (" -- the next stage stays blocked"
                                                        if team_stage.get("gate") == "required" else ""))
                    text = team_control.handoff_text(role_name, text, cost_usd=child.cost_meter.total_usd,
                                                     child_log_path=str(child.log.path))
                    report_line = team_control.record_report(
                        # vibes/review.md finding 25: read the OUTCOME the bg
                        # path actually computed (`bg_is_error`, line ~2135) --
                        # the bare `is_error` here has no assignment anywhere
                        # in this scope (pyflakes F821), so a background
                        # sub-agent under a team raised NameError mid-report,
                        # died with no completion notice, and left the parent
                        # waiting on it forever.
                        role_name, f"{spec.name} {'failed' if bg_is_error else 'finished'}"
                                   f" (${child.cost_meter.total_usd:.4f})")
                    if team_control.reports_for(role_name):  # 3.1.9.0 R2: the default lineup reports its cards only
                        _team_queue_report(parent, report_line)
                # H6/D10 (see the foreground path's own comment): merge even
                # for a background sub-agent, under the same lock its own
                # pending-notice append already uses.
                with parent._agent_notices_lock:
                    parent.permission_denials.extend(child.permission_denials)
                # H9 whole-tree review finding 10: `permission_denials` is a
                # print-mode-only channel (the TUI never renders it) -- a
                # background child's own denied tool calls used to be
                # completely invisible in the TUI, which only ever sees this
                # notice text. Same for an interrupted (quit/TaskStop) child:
                # say so plainly instead of presenting whatever partial text
                # it managed as if it were a normal, complete answer.
                status_bits = []
                if child.abort.is_set():
                    status_bits.append("interrupted")
                if child.permission_denials:
                    names = ", ".join(sorted({d.get("tool_name", "?") for d in child.permission_denials}))
                    status_bits.append(f"{len(child.permission_denials)} tool call(s) denied ({names})")
                # H9 whole-tree review finding 26: same treatment as the
                # foreground path -- a provider failure/max_turns also gets
                # flagged here, not just an abort/denial (the two cases
                # `child.abort.is_set()`/`permission_denials` already covered).
                is_error, abnormal_reason = _child_turn_outcome(child_events)
                # Halo 2.0.2 round 3 (brief C): the tasks panel's own
                # "finished agents stay listed ... with their final
                # status" reads THIS field (meta.json has no other record
                # of is_error -- `_write_meta` above fired before this was
                # known) plus a stamped finish time, so a closed panel
                # reopened later still shows the real outcome, not just
                # "completed" for both a clean and a failed run alike.
                _write_meta(meta_path, {"is_error": is_error, "finished": time.time()})
                _record_outcome(parent, child, spec, role_name, team_control, agent_id, is_error=is_error,
                                stopped=child.abort.is_set() or _fleet_stopped(child), stage=bg_stage)  # 3.1.8.0 R3
                # review finding 20: the foreground path always emits
                # `subagent_end` (see the mirror-image `end_ev` below the
                # foreground `try/finally`); `_bg_run` never did, so a live
                # TUI's SubAgentCard (mounted on `subagent_start`, which DOES
                # reach the dock via `bg_sink`) never got `card.finish()`
                # and kept ticking "thinking Ns" forever, even after the
                # completion notice landed right below. Reuses the same
                # `bg_sink` the live-ask forwarder above already resolved --
                # None for a `-p`/bare-Session run, exactly like start_ev's
                # own live forwarding, so headless callers see no behavior
                # change at all.
                end_ev = events.Event("subagent_end", {"agent_id": agent_id, "name": _dock_name,
                                                          "parent_tool_use_id": tool_id,
                                                          "task_id": new_task_id, "is_error": is_error,
                                                          # round C: "a one-line result summary and a
                                                          # `/tasks` pointer" -- see tui/dispatch.py's
                                                          # own subagent_end handler.
                                                          "result_preview": _one_line_preview(text)})
                end_ev.agent_id = agent_id
                if bg_sink is not None:
                    bg_sink(end_ev)
                if abnormal_reason and abnormal_reason not in ("interrupted",):
                    status_bits.append(abnormal_reason)
                status_suffix = f" [{'; '.join(status_bits)}]" if status_bits else ""
                if is_error:
                    text = f"(this sub-agent may not have finished normally)\n{text}"
                worktree_note = _finalize_child_isolation_worktree(child)
                if worktree_note:
                    text = f"{text}\n\n{worktree_note}"
                notice = (f"[Background sub-agent '{spec.name}' finished (task_id={new_task_id}){status_suffix}]\n"
                          f"{_wrap_task_result(text, new_task_id)}")
                with parent._agent_notices_lock:
                    parent._pending_agent_notices.append(notice)
                del child_events  # collected for parity/debuggability only; not forwarded (parent turn has ended)
            finally:
                # H11b finding 14: whatever this background child keeps
                # running beside its turns is closed THE MOMENT this call
                # ends, not left running until the whole halo process quits.
                child.close_runtimes()
                runtime.live_children.pop(agent_id, None)
                if team_control is not None:
                    team_control.tier_release(agent_id)
                with runtime.lock:
                    entry = runtime.tasks.get(new_task_id)
                    if entry is not None:
                        entry["running_in_process"] = False

        threading.Thread(target=_bg_run, daemon=True, name=f"subagent-{agent_id}").start()
        result = ToolResult(
            f"Sub-agent '{spec.name}' started in the background (task_id={new_task_id}). Its result "
            f"will be reported to you as a notice once it finishes -- continue with other work."
        )
        return [start_ev], result

    try:
        with runtime.concurrency_semaphore:  # 2.0.2 review finding 10: session-wide, not just one pool's own
            child_events = _run_child_to_completion(child, prompt, agent_id=agent_id, parent_tool_use_id=tool_id,
                                                     on_event=on_event)
    finally:
        # H11b finding 14: whatever a foreground child keeps running beside
        # its turns is closed the moment its ONE call ends --
        # `_build_child_session` builds a brand new one on
        # every Agent/task_id-resume call, so there is never a reason to
        # keep it alive past this point.
        child.close_runtimes()
        runtime.live_children.pop(agent_id, None)
        if team_control is not None:
            team_control.tier_release(agent_id)
    text = _final_text_from_log(child)
    # H9 whole-tree review finding 26: `text` alone can't tell the parent
    # whether the child actually finished normally -- a provider failure/
    # max_turns/interruption partway through used to hand back whatever
    # was logged last with no signal it wasn't a real, complete answer.
    is_error, abnormal_reason = _child_turn_outcome(child_events)
    # Halo 2.0.6 round 3 (acceptance-gated returns): check the hand-back
    # against the bio's own `acceptance` criteria; a failure gets ONE
    # retry -- the critique as a second user turn on the SAME child (it
    # keeps its context, so "address this and return again" is all the
    # prompt needs) -- and a second failure escalates with the failure
    # MARKED: the hand-back carries the note, the rollup's ok (round 2's
    # cost-per-accepted) counts it failed, and the task meta records it.
    # A run that errored never retries on acceptance (a dead run is not
    # a rejected result); a bio with no acceptance block is byte-for-byte
    # the old path.
    acceptance_failed = None
    had_acceptance = False
    if not is_error and not _fleet_stopped(child):  # 3.0.5.0: a stopped child is not sent back for a retry
        acc_ok, acc_note = _check_return_acceptance(spec, role_name, team_control, child, text)
        had_acceptance = acc_note is not None
        if not acc_ok:
            critique = _acceptance_critique(spec, role_name, team_control, child, acc_note)
            retry_events = _run_child_to_completion(
                child, critique, agent_id=agent_id, parent_tool_use_id=tool_id, on_event=on_event)
            child_events = retry_events
            text = _final_text_from_log(child)
            is_error, abnormal_reason = _child_turn_outcome(child_events)
            if not is_error:
                acc_ok2, acc_note2 = _check_return_acceptance(spec, role_name, team_control, child, text)
                if not acc_ok2:
                    acceptance_failed = (f"acceptance failed after 2 attempts "
                                         f"({acc_note2}; first attempt: {acc_note})")
    accepted = (not is_error) and acceptance_failed is None
    acceptance_rec = ({"met": accepted, "why": acceptance_failed or acc_note, "attempts": 1 if acc_ok else 2}
                      if had_acceptance else None)  # 3.1.8.0 R3: the verdict its evidence records (outcomes/session.py)
    _fire_subagent_hook(child, "SubagentStop")
    _fire_task_hook(parent, "TaskCompleted", task_id=new_task_id, spec_name=spec.name, description=description)
    # Halo 2.0.2 round 3 (brief C): `is_error`/`finished` -- see _bg_run's
    # own matching comment just above.
    _write_meta(meta_path, {"status": "completed", "is_error": is_error,
                            # 2.0.6 round 3: the acceptance verdict rides
                            # the task meta -- True/False when criteria
                            # existed, absent when they never did.
                            **({"accepted": accepted} if had_acceptance else {}),
                            **({"acceptance_note": acceptance_failed} if acceptance_failed else {}),
                            "finished": time.time()})
    # H9 whole-tree review finding 13: see the background path's own
    # comment above -- a FOREGROUND child's usage/cost gets the same
    # rollup, just synchronously here instead of at the end of `_bg_run`.
    # 2.0.6 round 3: `ok` is the ACCEPTED outcome now -- a result that
    # ran cleanly but failed its acceptance twice counts as a failed
    # task in round 2's cost-per-accepted.
    _rollup_child_cost_into_parent(parent, child, agent_id=agent_id, since_index=since_index, role=role_name,
                                   ok=accepted, bio=spec.name)
    _forward_child_escalation_decisions(parent, child, spec)
    # Halo 2.0.5 round 5 "team control" -- the foreground completion half
    # (the background half lives in `_bg_run`): the team's own budget
    # counts this call's spend/turns, a pipeline stage records its gate
    # result (a `required` gate that fails blocks the NEXT stage), the
    # `delegation.handoff` shape wraps the hand-back, and the completion
    # becomes the member's one-line report.
    team_note, stage_verdict = None, None
    if team_control is not None:
        team_control.record_spend(child.cost_meter.total_usd)
        team_control.record_turn(getattr(child, "turn_count", 0) or 0)
        if team_stage is not None:
            ok, gate_line = team_control.evaluate_stage(team_stage, text)
            team_control.record_stage(team_stage, ok, gate_line)
            stage_verdict = (ok, gate_line)
            if not ok and team_stage.get("gate") == "required":
                team_note = f"stage {team_stage.get('name')!r} gate did not pass ({gate_line}) -- the next stage stays blocked"
            elif not ok:
                team_note = f"stage {team_stage.get('name')!r} gate did not pass ({gate_line}) -- recorded, optional gate continues"
        text = team_control.handoff_text(role_name, text, cost_usd=child.cost_meter.total_usd,
                                         child_log_path=str(child.log.path))
        report_line = team_control.record_report(
            role_name, f"{spec.name} {'failed' if is_error else 'finished'} (${child.cost_meter.total_usd:.4f})")
        if team_control.reports_for(role_name):  # 3.1.9.0 R2: the default lineup reports its cards only
            _team_queue_report(parent, report_line)
    # H6 known v1 gap (D10) / B must-do: a non-interactive child's own
    # "ask" denials (agent/loop.py's `_resolve_tool_call`) land in the
    # CHILD's own `permission_denials` list, which nothing outside this
    # function would otherwise ever read -- merged into the PARENT's here
    # so print mode's top-level result (headless.py reads `session.
    # permission_denials`, the TOP session only) actually surfaces a
    # sub-agent's denied tool calls instead of silently losing them.
    parent.permission_denials.extend(child.permission_denials)
    _record_outcome(parent, child, spec, role_name, team_control, agent_id, is_error=is_error,
                    stopped=_fleet_stopped(child), acceptance=acceptance_rec, stage=stage_verdict)
    end_ev = events.Event("subagent_end", {"agent_id": agent_id, "name": _dock_name, "parent_tool_use_id": tool_id,
                                             "task_id": new_task_id, "is_error": is_error})
    end_ev.agent_id = agent_id
    if on_event is not None:
        on_event(end_ev)  # H5c finding 8: live too, same reasoning as start_ev above

    if is_error:
        # 2.0.7 dead-model-id round: the child's OWN last error message
        # rides the handback -- a 404'd model id used to hand back a
        # silently-empty/partial answer with the actual "no endpoints
        # found for model X" nowhere in sight.
        _child_err = _last_child_error_text(child_events)
        if _child_err:
            text = (f"[sub-agent did not finish normally ({abnormal_reason}): {_child_err}\n"
                    f"this may be a stale/partial answer]\n{text}")
        else:
            text = f"[sub-agent did not finish normally ({abnormal_reason}) -- this may be a stale/partial answer]\n{text}"
    if acceptance_failed:
        # 2.0.6 round 3: the escalation mark -- the result IS returned (the
        # parent decides what to do with it), but never silently.
        text = (f"[acceptance gate: {acceptance_failed} -- the result below failed its bio's "
                f"acceptance criteria twice and is returned marked]\n{text}")
    worktree_note = _finalize_child_isolation_worktree(child)
    if worktree_note:
        text = f"{text}\n\n{worktree_note}"
    if team_note:
        text = f"{text}\n\n{team_note}"
    wrapped = _wrap_task_result(text, new_task_id)
    capped = spill_and_truncate(wrapped, cap=RESULT_CAP, session_dir=parent.log.dir / parent.log.session_id,
                                 tool_use_id=tool_id)
    return [start_ev, *child_events, end_ev], ToolResult(capped, is_error=is_error)


def _resume_task(runtime: AgentRuntime, task_id: str, tool_input: dict, tool_id: str, *, on_event=None):
    """vibes/review.md finding 54: the in-flight guard is CLAIMED here,
    check-and-set under `runtime.lock` -- two `Agent(task_id=X)` calls in
    one assistant message used to both read False before either set True
    (the old check ran at the top, the set far below), so both built a
    Session over the same child log. The loser gets the same "still
    running" error; the winner's claim is released in the `finally`
    whatever path the resume takes (the inner body resets it too)."""
    from halo_harness.tools.base import ToolResult

    record = runtime.tasks.get(task_id)
    if record is None:
        return [], ToolResult(f"Unknown task_id {task_id!r} -- it may belong to a different session.", is_error=True)
    with runtime.lock:
        if record.get("running_in_process"):
            return [], ToolResult(
                f"Task {task_id!r} is still running in the background -- resuming it now would race its own "
                f"in-progress work. Wait for its completion notice before sending it another prompt.",
                is_error=True,
            )
        record["running_in_process"] = True
    try:
        return _resume_task_claimed(runtime, task_id, tool_input, tool_id, on_event=on_event)
    finally:
        with runtime.lock:
            record["running_in_process"] = False


def _resume_task_claimed(runtime: AgentRuntime, task_id: str, tool_input: dict, tool_id: str, *, on_event=None):
    from halo_harness.tools.base import ToolResult
    from halo_harness.tools.truncate import spill_and_truncate

    parent = runtime.parent
    record = runtime.tasks.get(task_id)
    # H9 whole-tree review finding 27 (concurrent-resume half): a
    # background child still has its OWN `_bg_run` thread appending to
    # this exact task_id's child log/meta.json -- resuming NOW would build
    # a second, independent Session on top of the same files and both
    # would write to them at once. `running_in_process` is per-PROCESS
    # in-memory state (see its own comment where it's set), so this can
    # never be a stale True surviving a `-c` restart -- a reconstructed
    # task (`record.get("reconstructed")`) is never True here, because the
    # thread that would have set it died with the old process.
    spec = runtime.agents.get(record["spec_name"])
    if spec is None:
        return [], ToolResult(f"The agent type for task_id {task_id!r} is no longer available.", is_error=True)

    agent_id = record["child_session_id"][len("agent-"):] if record["child_session_id"].startswith("agent-") \
        else record["child_session_id"]
    # V2c (H15): a resume may itself carry a fresh `role=` override; else
    # this resumed call keeps resolving against the SAME agent's own role.
    role_override = tool_input.get("role")
    # finding 22: same check as the single-spawn path above -- a resume's
    # own fresh `role=` override was never validated either.
    role_error = _invalid_role_error(role_override, runtime)
    if role_error is not None:
        return [], ToolResult(role_error, is_error=True)
    # vibes/review.md finding 56: a resume without its own overrides keeps
    # the ones the task was spawned with (stored on the record / meta.json)
    # instead of falling back to the agent file's defaults; an explicit
    # value on the resume call still wins and becomes the new stored one.
    role_override = role_override or record.get("role_override")
    model_override = tool_input.get("model") or record.get("model_override")
    effort_override = tool_input.get("effort") or record.get("effort_override")
    role_name = role_override or spec.role
    try:
        child, meta_path = _build_child_session(
            runtime=runtime, spec=spec, agent_id=agent_id, model_override=model_override,
            parent_tool_use_id=tool_id, background=False,  # a resume always runs in the foreground
            role_override=role_override, effort_override=effort_override,
            task_text=f"{tool_input.get('description') or ''}\n{tool_input.get('prompt') or ''}",
        )
    except Exception as e:
        # Finding 4: same "never raises" contract run_agent_call's own
        # single-spawn path now guards with -- an unresolvable model (a
        # bad `model=` override on the resume call, or a bio whose
        # own `model:` only went bad after this task was created) used to
        # raise straight out of here.
        _, failed_meta_path = _child_log_paths(parent, agent_id)
        # 3.0.1.0 review item 123: the original run's own outcome stays as
        # it was; the failed resume is recorded beside it. Only a task with
        # no meta.json at all gets a failed status written.
        _attempt = {"last_resume_error": f"{type(e).__name__}: {e}", "last_resume_at": time.time()}
        if not failed_meta_path.exists():
            _attempt.update({"status": "completed", "is_error": True, "finished": time.time()})
        _write_meta(failed_meta_path, _attempt)
        return [], ToolResult(f"Could not resume sub-agent for task_id {task_id!r}: {type(e).__name__}: {e}",
                               is_error=True)
    # H9 whole-tree review finding 13: see run_agent_call's own comment on
    # its identically-named local -- a resume's own child log already
    # carries every PRIOR call's usage nodes; only what's appended from
    # here on is THIS call's own new spend.
    since_index = len(child.log.nodes())
    runtime.live_children[agent_id] = child  # H11b finding 14, see run_agent_call's own comment
    # external review finding 10 (2026-10-08), double-writer half: the
    # in-flight guard checked above was never SET for a foreground
    # resume, so two Agent(task_id=X) calls in ONE assistant message both
    # passed it and built two independent Sessions over the same child
    # log files -- interleaved JSONL writers. Set for the duration, reset
    # in the same finally that pops live_children (same "never stuck
    # True" reasoning _bg_run's own comment gives).
    record["running_in_process"] = True  # already claimed by `_resume_task`; kept for direct callers
    record.update(_override_fields(role_override, model_override, effort_override))
    _dock_name = spec.name
    _desc = tool_input.get("description") or record.get("description") or "resume"
    start_ev = events.Event("subagent_start", {"agent_id": agent_id, "name": _dock_name,
                                               "description": _desc, "parent_tool_use_id": tool_id,
                                               "task_id": task_id})
    start_ev.agent_id = agent_id
    _fire_subagent_hook(child, "SubagentStart")
    _fire_task_hook(parent, "TaskCreated", task_id=task_id, spec_name=spec.name, description=_desc)
    if on_event is not None:
        on_event(start_ev)
    prompt = tool_input.get("prompt") or "Please continue."
    try:
        # finding 10: the session-wide cap, never just one pool's own.
        with runtime.concurrency_semaphore:
            child_events = _run_child_to_completion(child, prompt, agent_id=agent_id, parent_tool_use_id=tool_id,
                                                     on_event=on_event)
    finally:
        child.close_runtimes()
        runtime.live_children.pop(agent_id, None)
        # finding 10: reset the in-flight guard the same finally owns.
        with runtime.lock:
            entry = runtime.tasks.get(task_id)
            if isinstance(entry, dict):
                entry["running_in_process"] = False
    text = _final_text_from_log(child)
    # H9 whole-tree review finding 26: same treatment as run_agent_call's
    # own foreground path -- see its comment.
    is_error, abnormal_reason = _child_turn_outcome(child_events)
    # external review finding 10 (2026-10-08), hooks half: a resume used
    # to fire ZERO hooks/events -- no SubagentStart/Stop, no TaskCreated/
    # Completed, no subagent_start/end -- so a resumed task was invisible
    # to every hook and every dock. Same shapes the fresh-spawn path
    # fires, in the same order.
    _fire_subagent_hook(child, "SubagentStop")
    _fire_task_hook(parent, "TaskCompleted", task_id=task_id, spec_name=spec.name, description=_desc)
    _record_outcome(parent, child, spec, role_name, getattr(runtime, "team_control", None), agent_id,
                    is_error=is_error, stopped=_fleet_stopped(child))  # 3.1.8.0 R3: a resumed task records again
    end_ev = events.Event("subagent_end", {"agent_id": agent_id, "name": _dock_name,
                                           "result_preview": _one_line_preview(text), "task_id": task_id})
    end_ev.agent_id = agent_id
    if on_event is not None:
        on_event(end_ev)
    _write_meta(meta_path, {"status": "completed", "is_error": is_error, "finished": time.time()})
    _rollup_child_cost_into_parent(parent, child, agent_id=agent_id, since_index=since_index, role=role_name,
                                   ok=not is_error, bio=spec.name)
    # 2.0.6 round 12: the child's own escalation decisions reach the
    # parent's /escalation view (the C-5 remainder).
    _forward_child_escalation_decisions(parent, child, spec)
    parent.permission_denials.extend(child.permission_denials)  # H6/D10, see run_agent_call's own comment
    if is_error:
        # 2.0.7 dead-model-id round: same decoration the fresh-spawn path
        # got -- the child's own last error message rides the handback.
        _child_err = _last_child_error_text(child_events)
        if _child_err:
            text = (f"[sub-agent did not finish normally ({abnormal_reason}): {_child_err}\n"
                    f"this may be a stale/partial answer]\n{text}")
        else:
            text = f"[sub-agent did not finish normally ({abnormal_reason}) -- this may be a stale/partial answer]\n{text}"
    worktree_note = _finalize_child_isolation_worktree(child)
    if worktree_note:
        text = f"{text}\n\n{worktree_note}"
    wrapped = _wrap_task_result(text, task_id)
    capped = spill_and_truncate(wrapped, cap=RESULT_CAP, session_dir=parent.log.dir / parent.log.session_id,
                                 tool_use_id=tool_id)
    return child_events, ToolResult(capped, is_error=is_error)


def _walk_live_children(runtime: "AgentRuntime"):
    """Yields `(agent_id, child_session)` for every CURRENTLY live
    descendant reachable from `runtime`, at any depth -- each child's
    own `agent_runtime.live_children` is a FRESH dict (never shared by
    reference across the tree, unlike `tasks`/`lock`), so a grandchild's
    liveness is only visible by recursing into its own parent's dict."""
    for agent_id, child in list(runtime.live_children.items()):
        yield agent_id, child
        child_runtime = getattr(child, "agent_runtime", None)
        if child_runtime is not None:
            yield from _walk_live_children(child_runtime)


# 2.0.2 review finding 17 (major): keyed by (size, mtime) -- see
# `_agent_log_nodes`'s own docstring. A plain dict/lock (never an LRU
# cap): one entry per sub-agent log this process has ever looked at,
# which is bounded by how many sub-agents a session actually ran, not
# by poll frequency.
_agent_log_nodes_cache: "dict[str, tuple]" = {}
_agent_log_nodes_cache_lock = threading.Lock()


def _agent_log_nodes(log_path: Path) -> list:
    """A bare, dependency-free read of one `agent-*.jsonl` file's lines
    -- used for a `tool_count`/cost lookup without constructing a real
    `SessionLog` (which also wants to create directories etc.). Missing/
    unreadable file or a malformed line is silently skipped, never
    raised -- this is a best-effort reporting path, not core machinery.

    2.0.2 review finding 17 (major): cached by (size, mtime) -- the
    tasks panel's own 1Hz poll used to re-read and re-parse EVERY sub-
    agent's WHOLE jsonl log on every tick just to count tools, even one
    that hadn't grown since the last tick (the overwhelmingly common
    case once a run has more than a couple of agents -- most are
    already finished). Verified: 20 synthetic ~1MB logs took 0.22s PER
    call before this. A cache HIT (unchanged size/mtime) skips the
    read+parse entirely; a MISS (grown, shrunk, or never seen) still
    re-reads the whole file -- not fully incremental, but the dominant
    real-world cost (re-scanning FINISHED agents' static logs every
    tick) is gone."""
    key = str(log_path)
    try:
        st = log_path.stat()
        stamp = (st.st_size, st.st_mtime)
    except OSError:
        with _agent_log_nodes_cache_lock:
            _agent_log_nodes_cache.pop(key, None)
        return []
    with _agent_log_nodes_cache_lock:
        cached = _agent_log_nodes_cache.get(key)
    if cached is not None and cached[0] == stamp:
        return cached[1]
    nodes: list = []
    try:
        with log_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    nodes.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        pass
    with _agent_log_nodes_cache_lock:
        _agent_log_nodes_cache[key] = (stamp, nodes)
    return nodes


def _tool_count_from_log(nodes: list) -> int:
    count = 0
    for node in nodes:
        if node.get("type") != "assistant":
            continue
        for block in (node.get("content") or []):
            if isinstance(block, dict) and block.get("type") == "tool_use":
                count += 1
    return count


def _cost_for_agent_from_log(nodes: list, agent_id: str) -> "Optional[float]":
    cost = None
    for node in nodes:
        if node.get("type") == "usage" and node.get("agent_id") == agent_id:
            c = node.get("cost_usd")
            if isinstance(c, (int, float)) and not isinstance(c, bool):
                cost = c
    return cost


def list_agent_task_rows(session) -> list:
    """Halo 2.0.2 round 3 (brief C): every running, queued, background
    and finished sub-agent of THIS session -- the tasks panel's own data
    source (`Controller.list_agent_tasks()`). A flat list of row dicts,
    tree position included (`depth`/`parent_agent_id`, derived from the
    directory nesting `_child_log_paths` already produces, never from
    cross-referencing tool_use ids -- see this function's own `rel_parts`
    math): {agent_id, task_id, title, model, status, is_error, tool_count,
    cost_usd, started, elapsed_s, depth, parent_agent_id, log_path}.
    Reads disk (meta.json + each child's own jsonl log) rather than any
    in-memory event history, so it reports correctly even for a `-c`-
    resumed session that never re-ran a single turn yet; a still-RUNNING
    child's cost is read live off its own `cost_meter` (via `runtime.
    live_children`, walked recursively) when reachable, falling back to
    whatever its own parent's log already rolled up (the usual place a
    FINISHED child's cost lives -- `_rollup_child_cost_into_parent`)."""
    top_subdir = session.log.dir / session.log.session_id / "subagents"
    rows: list = []
    if not top_subdir.is_dir():
        return rows
    live_by_id: dict = {}
    runtime = getattr(session, "agent_runtime", None)
    if runtime is not None:
        live_by_id = dict(_walk_live_children(runtime))
    # 2.0.2 review finding 25: `Path.__lt__` compares the PARTS tuple, not
    # the joined string -- `("agent-P", "subagents", "agent-C.meta.json")`
    # sorts BEFORE `("agent-P.meta.json",)` (a tuple whose first element,
    # the bare folder name "agent-P", is a strict PREFIX of the sibling's
    # first element "agent-P.meta.json", and a prefix always sorts before
    # the longer string it prefixes) -- every child's own meta.json used
    # to sort ahead of its own parent's, and siblings sorted by whatever
    # order their random agent_ids happened to fall in. Collected here in
    # whatever order `rglob` yields (not meaningful either way) and
    # reordered into parent-before-children, `started`-ordered siblings
    # right before returning, below.
    for meta_path in top_subdir.rglob("agent-*.meta.json"):
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        agent_id = data.get("agent_id")
        if not isinstance(agent_id, str) or not agent_id:
            continue
        rel_parts = meta_path.relative_to(top_subdir).parts
        depth = (len(rel_parts) - 1) // 2
        parent_agent_id = None
        parent_log_path = None
        if len(rel_parts) >= 3:
            parent_dir = meta_path.parent.parent  # the "agent-<parent>" folder itself
            parent_agent_id = parent_dir.name[len("agent-"):]
            parent_log_path = parent_dir.parent / f"{parent_dir.name}.jsonl"
        log_name = meta_path.name
        if log_name.endswith(".meta.json"):
            log_name = log_name[: -len(".meta.json")] + ".jsonl"
        log_path = meta_path.parent / log_name
        nodes = _agent_log_nodes(log_path)
        started = data.get("started")
        finished = data.get("finished")
        elapsed = None
        if isinstance(started, (int, float)):
            end = finished if isinstance(finished, (int, float)) else time.time()
            elapsed = max(0.0, end - started)
        cost = None
        live_child = live_by_id.get(agent_id)
        if live_child is not None:
            cm = getattr(live_child, "cost_meter", None)
            if cm is not None and getattr(cm, "has_cost_data", False):
                cost = cm.total_usd
        if cost is None:
            source_nodes = session.log.nodes() if parent_log_path is None else _agent_log_nodes(parent_log_path)
            cost = _cost_for_agent_from_log(source_nodes, agent_id)
        rows.append({
            "agent_id": agent_id, "task_id": data.get("task_id"), "title": data.get("type") or "?",
            "model": data.get("model"), "status": data.get("status") or "running",
            "is_error": bool(data.get("is_error")), "tool_count": _tool_count_from_log(nodes),
            "cost_usd": cost, "started": started, "elapsed_s": elapsed, "depth": depth,
            "parent_agent_id": parent_agent_id, "log_path": str(log_path),
        })
    return _order_task_rows_by_tree(rows)


def _order_task_rows_by_tree(rows: list) -> list:
    """finding 25: parent-before-children, pre-order; siblings (and every
    root) ordered by `started` (missing/non-numeric sorts last, agent_id
    as a stable tiebreak so the order is deterministic run to run)."""
    by_parent: "dict[Optional[str], list]" = {}
    for row in rows:
        by_parent.setdefault(row.get("parent_agent_id"), []).append(row)

    def _sort_key(row: dict):
        started = row.get("started")
        return (0, started) if isinstance(started, (int, float)) else (1, row["agent_id"])
    for children in by_parent.values():
        children.sort(key=_sort_key)

    ordered: list = []
    seen: set = set()

    def _walk(row: dict) -> None:
        if row["agent_id"] in seen:
            return  # a malformed/cyclic parent_agent_id must never infinite-loop this
        seen.add(row["agent_id"])
        ordered.append(row)
        for child in by_parent.get(row["agent_id"], []):
            _walk(child)
    for root in by_parent.get(None, []):
        _walk(root)
    # Any row whose own parent_agent_id didn't match a REAL row in this
    # same batch (the parent finished and its meta.json was cleaned up
    # mid-scan, or any other inconsistency) is still shown, appended at
    # the end rather than silently dropped.
    for row in rows:
        if row["agent_id"] not in seen:
            _walk(row)
    return ordered
