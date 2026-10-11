"""halo_harness.controller -- the non-blocking UI-thread facade over the
agent loop (U2, D-Contract).

The rule this module exists to enforce: **every call here is made from the
UI thread and none of them may block it for more than a moment.** The agent
loop (`agent/loop.Session.run`) owns one worker thread; this class is the
only thing that talks to it.

Two directions, deliberately different mechanisms:

* UI -> loop. `submit`/`set_permission_mode`/`set_model` push a
  `events.Command` onto `self.commands` and return immediately -- the worker
  picks it up between turns. The three exceptions are `interrupt`,
  `answer_permission` and `answer_question`: those must affect a turn that is
  ALREADY in flight (the worker is parked inside that turn's generator, so it
  can never read the queue), and each has a thread-safe direct entry point on
  the Session (`abort.set()`, `resolve_permission`, `resolve_question`).

* loop -> UI. The worker pushes `events.Event`s onto `self.events` (a
  `queue.Queue`). Nothing here ever touches a widget; the TUI's 30 Hz drain
  timer is the only reader.

`quit()` is the one deliberately-blocking call: it asks the worker to stop
and joins it with a 5 s deadline (D-TUI), so a wedged turn can't stop the
process from exiting cleanly.
"""

from __future__ import annotations

import json
import queue
import threading
import uuid
from pathlib import Path
from typing import Callable, Optional

from halo_harness import events
from halo_harness.config.paths import bridge_home, project_slug
from halo_harness.textlines import split_lines
from halo_harness.permissions import Decision, add_allow_rule

QUIT_DEADLINE_S = 5.0


def _default_model_resolver(raw: str, *, state_dir: Path, routes: dict, settings=None):
    """`(ModelRef, ModelProfile, creds)` for a `--model`-style string --
    the same resolution headless.py does at startup, reused here so `/model`
    and `set_model` can never drift from it."""
    from halo_harness.headless import _resolve_creds
    from halo_harness.model import parse_model_ref, resolve_model_profile

    ref = parse_model_ref(raw, routes)
    profile = resolve_model_profile(ref, state_dir, routes)
    return ref, profile, _resolve_creds(ref, settings)


# pass-B finding 2 (critical): providers that need no credentials at
# all -- `cc:`/`cx:` are subprocess routes (the Claude Code / Codex CLI
# does its own auth), so `_resolve_creds` always returns None for them;
# that is the ordinary, expected shape for those two, never a reason to
# refuse a switch the way an actually-unconfigured cloud/local ref is.
_NO_CREDENTIALS_NEEDED_PROVIDERS = frozenset({"cc", "codex"})


def _not_configured_message(ref) -> str:
    """The provider's own "not configured" sentence for `ref`, matching
    providers/stream.py's phase-1 `ProviderNotConfigured` wording exactly
    (same text `_run_phase1`/`_run_phase1_anthropic`/`_run_phase1_ollama_
    attempt`/`_run_phase1_responses` would raise at request time) -- so
    `set_model` below can refuse a ref with no usable credentials BEFORE
    ever queuing the switch, with the same sentence the turn would have
    failed with anyway, instead of silently sending the transcript to
    whatever provider the session was already on."""
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


class Controller:
    """`session` is a fully built `agent.loop.Session`; `registry`/`facade`
    are the U0 slash-command surfaces (the facade is the TUI's own, so its
    `run()` implementations see live UI state)."""

    def __init__(
        self, *, session, cwd: Path, state_dir: Optional[Path] = None, routes: Optional[dict] = None,
        registry=None, facade=None, model_resolver: Optional[Callable] = None,
        mcp_status_fn: Optional[Callable] = None, reconnect_fn: Optional[Callable] = None,
        settings=None, mcp_manager: Optional[object] = None,
    ):
        self.session = session
        self.cwd = Path(cwd)
        self.state_dir = Path(state_dir) if state_dir else bridge_home()
        self.routes = routes or {}
        self.registry = registry
        self.facade = facade
        self.settings = settings
        self.model_resolver = model_resolver or (
            lambda raw: _default_model_resolver(raw, state_dir=self.state_dir, routes=self.routes,
                                                settings=self.settings))
        self._mcp_status_fn = mcp_status_fn
        self._reconnect_fn = reconnect_fn
        # tui/bootstrap.py hands this over so quit() can close every MCP
        # subprocess/loop cleanly (mirrors headless.py's own `finally:
        # mcp_manager.close_all()`); None for a print-mode-less bare
        # Session, a unit test, or `--bare`.
        self.mcp_manager = mcp_manager

        self.events: "queue.Queue" = queue.Queue()
        self.commands: "queue.Queue" = queue.Queue()
        self._worker: Optional[threading.Thread] = None
        self._stopped = threading.Event()
        self.quit_called = False
        self.exit_code = 0
        # set by the TUI right before quitting when `tui != "fullscreen"`:
        # the transcript is then printed to normal scrollback on exit.
        self.replay_messages: list = []
        # U5 scope A: `!cmd` inline shell's own persistent `cd` state --
        # deliberately separate from the real session's tool-dispatch
        # `bash_state` (agent/loop.py owns that one): an inline command
        # runs OUTSIDE the model loop entirely, so it gets its own small,
        # independent "current directory" memory across `!cmd` calls.
        self._inline_bash_state: dict = {}

    # ---- worker lifecycle -------------------------------------------------

    def start(self) -> "Controller":
        """Start the Session's command-pump thread. Returns self so a caller
        can write `controller = Controller(...).start()`."""
        if self._worker is not None:
            return self
        self.session.interactive = True  # the loop-side ask/question waits are only for a real UI

        def _target():
            try:
                self.exit_code = self.session.run(self.commands, self.events.put,
                                                  mcp_status_fn=self._mcp_status)
            finally:
                self.events.put(None)  # the sentinel the drain loop treats as "worker gone"

        self._worker = threading.Thread(target=_target, name="halo-session", daemon=True)
        self._worker.start()
        return self

    def _mcp_status(self) -> "Optional[dict]":
        # C-2 EXTRA (owner report): `None` in every "no real reading" case
        # -- no `mcp_status_fn` wired, the wired one raising, or returning
        # something that isn't even a dict -- never a fake "0/0". This is
        # passed straight through to `Session.run(mcp_status_fn=...)`,
        # whose own `status_event()` now follows the exact same rule
        # (see its docstring): a status built while none of these three
        # ever produced a real reading omits the `mcp` key entirely
        # instead of flashing a false "nothing connected".
        if self._mcp_status_fn is None:
            return None
        try:
            status = self._mcp_status_fn()
            return status if isinstance(status, dict) else None
        except Exception:
            return None

    @property
    def alive(self) -> bool:
        return self._worker is not None and self._worker.is_alive()

    def quit(self) -> int:
        """Ask the worker to finish and join it with the 5 s deadline
        (D-TUI). A turn still running when the deadline expires is
        interrupted first, so `quit` from the app's Ctrl+C path never leaves
        a Bash child behind."""
        if self.quit_called:
            return self.exit_code
        self.quit_called = True
        # review finding 2: set BEFORE `abort` / the sentinel is queued --
        # run()'s command loop checks this first, so a `user_input` typed
        # just before quitting (sitting ahead of the sentinel in the
        # queue) is drained without starting a whole new turn.
        self.session._stopping.set()
        self.session.abort.set()
        self.commands.put(None)
        try:
            if self._worker is not None:
                self._worker.join(QUIT_DEADLINE_S)
        finally:
            self._stopped.set()
            # H4 scope B: SessionEnd(quit) -- fired here, after the worker
            # has stopped touching the log but before MCP servers close (a
            # SessionEnd hook may itself want to reach an MCP server).
            try:
                self.session._fire_session_end("quit")
            except Exception:
                pass
            # H8 scope A: "jobs killed on quit" -- a background Bash job
            # (or one a timed-out foreground command was moved to) must
            # never outlive the session that started it.
            try:
                self.session.job_registry.kill_all()
            except Exception:
                pass
            # H11 Part B: a cc: session's own claude subprocess must never
            # outlive halo either -- a safe no-op when cc: was
            # never used this session.
            try:
                self.session.close_cc()
            except Exception:
                pass
            # Halo 2.0.3 round 5c (brief item 3): "stopped when Halo exits
            # unless keep: true" -- same belt-and-suspenders spot
            # headless.py's own print-mode finally/atexit pair uses.
            try:
                from halo_harness.providers.local_runtime import stop_all_managed_servers_except_kept
                stop_all_managed_servers_except_kept()
            except Exception:
                pass
            if self.mcp_manager is not None:
                self.mcp_manager.close_all()
        return self.exit_code

    # ---- UI -> loop (non-blocking) ---------------------------------------

    def submit(self, text: str, images: "Optional[list]" = None, pasted=None, meta=None) -> None:
        """scope 0(c): while a turn is running, new input steers it
        instead of queuing a whole separate turn -- `session.busy` is a
        plain Event read, safe from this (the UI) thread; `Session.steer`
        is the same kind of direct, thread-safe call as `interrupt()`/
        `answer_permission` (the worker is parked inside the running
        turn's generator and can't read `self.commands`).

        finding 5: `session.busy` here and the busy check INSIDE
        `steer()` are two separate reads -- the turn can finish in the
        (tiny) window between them, in which case `steer()` now correctly
        returns False (see its own docstring) instead of silently queuing
        text nothing will ever drain. That False is handled here by
        falling through to an ordinary fresh turn, so the text is never
        dropped either way. On success, `steer_queued` is pushed to
        `self.events` immediately (U5: shown the instant the user submits,
        not only once the turn reaches a safe point to actually apply
        it -- which can be much later, e.g. mid-tool-call).

        Halo 2.0.3.1: `images` (Anthropic-shaped blocks, `tui/app.py`'s own
        `_build_image_blocks`) rides on the queued `user_input` Command --
        `Session.run()`'s own command pump already reads `data.get(
        "images")` straight into `_pump_turn`/`Session.turn`, unchanged by
        this brief. A mid-turn STEER has no image channel of its own
        (`Session.steer` is text-only, see its docstring) -- an image
        attached while a turn is already busy is simply not carried by
        this fallback path; the chip itself is still cleared by `tui/
        app.py` either way, same as a plain pasted-text placeholder is."""
        if self.session.busy:
            if self.session.steer(text):
                self.events.put(events.steer_queued(text, turn=self.session.turn_count))
                return
            # else: the turn finished in the race window above -- fall
            # through and start a fresh turn instead of dropping the text.
        self.commands.put(events.Command("user_input", {"text": text, "images": images,
                                                           "pasted": pasted, "meta": meta}))

    def interrupt(self) -> None:
        """Esc / Ctrl+C during a turn. Direct, not queued: the worker is
        parked inside the turn's generator and only `abort` can reach it
        (the Bash tool polls this same Event to kill its process group)."""
        self.session.abort.set()

    def set_permission_mode(self, mode: str) -> None:
        """review finding 6: a plain string attribute write is atomic/
        thread-safe (like `abort.set()`) -- writing it directly, instead
        of queuing a `set_mode` Command that `run()` only reads BETWEEN
        turns, is what makes Shift+Tab to `auto` actually skip every
        remaining permission card of a turn already in progress (`auto` =
        uninterrupted, scope 0). The status event is emitted from here
        too, since the worker may be parked deep inside a turn and would
        otherwise never get a chance to push it."""
        if mode:
            self.session.permission_engine.mode = mode
        self.events.put(self.session.status_event())

    def set_model(self, model: str) -> Optional[str]:
        """Resolve `model` and hand the swap to the worker. Returns an error
        string (nothing sent) when the reference doesn't resolve.

        Halo 2.0.2 round 5 (Qwen-at-work brief, item 1): a decision-only/
        judge endpoint (`databricks-openjev-qwen35-4b` and any other
        `providers.profiles.decision_only_info` match) is NEVER installed
        as the session model, from either `/model <ref>` or picking it in
        the interactive picker (both funnel through this one method --
        `tui/slash.py`'s `_apply_model`) -- it is routed to the `judge`
        role automatically instead, and the returned string (shown the
        same way an unresolvable ref's error already is) says so plainly
        rather than silently doing nothing.

        Pass-B finding 2 (critical): this used to accept a ref whose
        credentials don't resolve and queue `set_model(..., creds=None)`
        regardless -- `Session.set_model` then kept the PREVIOUS model's
        creds (see its own docstring), so the NEXT turn sent the
        transcript to the OLD provider's URL with the OLD key under the
        NEW model id. Refused here instead, before anything is ever
        queued, with the same "not configured" sentence the request path
        itself would raise -- except for `cc:`/`cx:`, which need no
        credentials at all. An `hf:mlx/<repo>` ref gets one more step
        first: `build_session`/the TUI's own launch already start a
        managed `mlx_lm.server` for the SESSION's starting model, but
        `/model`/the picker switching to one mid-session never did, so
        the switch would otherwise always look "not configured" the
        first time anyone picks an mlx repo that way."""
        from halo_harness.model import parse_model_ref
        try:
            probe_ref = parse_model_ref(model, self.routes)
        except Exception:
            probe_ref = None
        if probe_ref is not None and probe_ref.provider == "huggingface" and getattr(probe_ref, "mlx", False):
            from halo_harness.headless import _ensure_mlx_server_for_ref
            _ensure_mlx_server_for_ref(probe_ref, self.state_dir)
        try:
            ref, profile, creds = self.model_resolver(model)
        except Exception as e:  # InvalidModelError and anything else a bad ref can raise
            return f"{e}"
        if creds is None and ref.provider not in _NO_CREDENTIALS_NEEDED_PROVIDERS:
            return _not_configured_message(ref)
        if ref.provider == "databricks":
            from halo_harness.providers.profiles import decision_only_notice
            notice = decision_only_notice(ref.model)
            if notice:
                from halo_harness.theme import set_config_value
                set_config_value("roles.judge", ref.raw)
                return f"{notice}\n`judge` role set to {ref.raw} -- the session model is unchanged."
        self.commands.put(events.Command("set_model", {"model_ref": ref, "model_profile": profile, "creds": creds}))
        return None

    def add_permission_rule(self, rule: str, scope: str = "session") -> Optional[Path]:
        """`session` -> in-memory only (the engine learns it now); anything
        else writes `<dest>/settings[.local].json` through
        `permissions.add_allow_rule` (D-CFG's escaping included). Returns
        the path written, or None for a session rule."""
        if not rule:
            return None
        if scope == "session":
            self.session.permission_engine.add_session_allow_rule(rule)
            return None
        return add_allow_rule(rule, scope, cwd=self.cwd)

    def answer_permission(self, request_id: str, decision) -> bool:
        """Direct (see class docstring): unblocks the parked worker."""
        if isinstance(decision, dict):
            decision = Decision(action=decision.get("action", "deny"),
                                 reason=decision.get("reason", ""),
                                 rule=decision.get("rule"),
                                 message=decision.get("message", ""))
        return self.session.resolve_permission(request_id, decision)

    def reevaluate_pending_permission(self, request_id: str) -> Optional[str]:
        """1.0.1 fixpass finding 4: Shift+Tab/`/permissions` mode-change
        re-evaluation for a still-parked ask -- see `Session.
        reevaluate_pending_permission`'s own docstring for the full
        contract. Returns "allow"/"deny" when it actually resolved the
        waiter, else None (still "ask" under the new mode, or nothing
        waiting for `request_id` any more)."""
        return self.session.reevaluate_pending_permission(request_id)

    def register_pending_permission(self, request_id: str, tool_name: str, tool_input: dict) -> None:
        """H15 Part D2.3: registers a slot in the session's own
        `_permission_waiters` for an ask that is resolved OUTSIDE the
        model loop entirely (today: `tui/app.py`'s `!cmd` inline-shell
        confirmation) so a mode change (Shift+Tab/`/permissions`) can reach
        it through the exact SAME `reevaluate_pending_permission` path a
        live tool-call ask already uses, instead of sitting there
        unaffected by mode changes until answered by hand. Safe by
        construction: no worker thread ever calls `_await_permission_
        decision`/blocks on this slot's own `event` (there is no such call
        for an inline command), so this can never wake a nonexistent
        waiter -- the slot exists purely so `decide()` can be re-run
        against the ORIGINAL `tool_name`/`tool_input` under the new mode,
        exactly like `_resolve_tool_call`'s own ask branch stashes them."""
        import threading
        self.session._permission_waiters[request_id] = {
            "event": threading.Event(), "decision": None,
            "tool_name": tool_name, "tool_input": tool_input, "tool": None,
        }

    def discard_pending_permission(self, request_id: str) -> None:
        """Removes a slot `register_pending_permission` added, once the ask
        is resolved through its own normal path (a digit press) -- without
        this, a stale, already-decided slot would sit in `_permission_
        waiters` forever (harmless -- nothing ever re-reads a request_id
        after its card is done -- but needless)."""
        self.session._permission_waiters.pop(request_id, None)

    def answer_question(self, request_id: str, answer) -> bool:
        return self.session.resolve_question(request_id, answer)

    def answer_approval(self, request_id: str, decision: dict) -> bool:
        """Halo 2.0.2 round D (brief item 2): `ApprovalCard`'s reply --
        direct (see class docstring), like `answer_permission`/`answer_
        question`/`answer_plan`: the worker is parked in `agent/
        subagent.py`'s `_ask_approval_live`, not polling the command
        queue. `decision` is `{"action": "accept"|"edit"|"stop",
        "instruction": str|None}`."""
        return self.session.resolve_approval(request_id, decision)

    def answer_plan(self, approved: bool, *, feedback: str = "", mode_after: Optional[str] = None) -> None:
        """`PlanCard`'s reply (D-Contract `plan_reply{approved, feedback,
        mode_after}`). Direct (see class docstring), like `answer_permission`/
        `answer_question`: the worker thread is parked inside `ExitPlanMode`'s
        own wait (`Session._handle_exit_plan_mode`, via `_await_reply`), not
        polling the command queue, so this must unblock it directly rather
        than going through `self.commands` -- a queued `plan_reply` would
        just sit there until the turn ends on its own, defeating the point.
        `Session.run()`'s own `plan_reply` branch calls `resolve_plan` too,
        as a safety net for a reply that arrives with no turn in flight."""
        self.session.resolve_plan({"approved": approved, "feedback": feedback, "mode_after": mode_after})

    def list_mcp_servers(self) -> list:
        """One dict per configured server (`McpManager.status()`'s own
        shape) for the `/mcp` dialog, PLUS one synthetic row per cached
        claude.ai connector (W4b connectors bridge -- `type: "connector"`,
        `mcp.connectors_bridge.connector_status_entry`) so the dialog shows
        them too, labelled `claude.ai connector (via claude)`. Cache-only
        (never spawns `claude` from the UI thread); `[]`/no connector rows
        when no manager was built this session or none are cached yet."""
        rows: list = []
        if self.mcp_manager is not None:
            try:
                rows = list(self.mcp_manager.status())
            except Exception:
                rows = []
        try:
            from halo_harness.mcp import connectors_bridge
            rows += [connectors_bridge.connector_status_entry(info) for info in connectors_bridge.get_connectors()]
        except Exception:
            pass
        # round6 brief deliverable 4: "/mcp shows ... the last diagnosis
        # per server" -- injected into each row dict here (the SAME place
        # `McpManager.status()` already injects `backoff_status`) so
        # `tui/dialogs/mcp_status.py`'s own `_row()` stays a pure function
        # of the row dict, never needing `state_dir` threaded through the
        # TUI layer at all.
        try:
            from halo_harness.mcp import doctor_deep
            for row in rows:
                name = row.get("name")
                if name:
                    row["last_diagnosis"] = doctor_deep.last_diagnosis_line(self.state_dir, name)
        except Exception:
            pass
        return rows

    def list_agent_tasks(self) -> list:
        """Halo 2.0.2 round 3 (brief C): every running/queued/background/
        finished sub-agent AND background Bash job of this session, for
        the `/tasks` panel -- sub-agent rows from `agent.subagent.list_
        agent_task_rows` (read straight off disk: meta.json + each
        child's own jsonl log, correct even right after a `-c` resume),
        PLUS one row per `agent.jobs.JobRegistry.list_jobs()` entry
        (H8 scope A's own docstring already named this exact use: "the
        `/tasks` slash command's own data source" -- written long before
        `/tasks` itself existed) adapted into the SAME row shape, `agent_
        id` prefixed `job-` so it can never collide with a real agent_id
        and `log_path` left None (no transcript viewer for a bash job --
        BashOutput/the pager already cover its captured output)."""
        rows: list = []
        if getattr(self.session, "agent_runtime", None) is not None:
            try:
                from halo_harness.agent.subagent import list_agent_task_rows
                rows = list_agent_task_rows(self.session)
            except Exception:
                rows = []
        job_registry = getattr(self.session, "job_registry", None)
        if job_registry is not None:
            import time
            now = time.time()
            for job in job_registry.list_jobs():
                started = job.get("started_at")
                rows.append({
                    "agent_id": f"job-{job['id']}", "task_id": job["id"],
                    "title": job.get("description") or (job.get("command") or "")[:60], "model": "(bash)",
                    "status": job.get("status") or "running",
                    "is_error": job.get("status") in ("failed", "killed"), "tool_count": 0, "cost_usd": None,
                    "started": started,
                    "elapsed_s": max(0.0, now - started) if isinstance(started, (int, float)) else None,
                    "depth": 0, "parent_agent_id": None, "log_path": None,
                })
        return rows

    def read_task_board(self) -> list:
        """Halo 2.0.2 round 3 (brief C): the shared task board (`TaskCreate`/
        `TaskUpdate`/`TaskList` tools) for the tasks panel's second tab --
        `tools.task_board.read_board`'s own list of `{id, title, status,
        owner, notes, result}` dicts, `[]` if nothing has been created yet
        or this session has no log directory at all."""
        try:
            from halo_harness.tools.task_board import read_board
            return read_board(self.session.log.dir / self.session.log.session_id)
        except Exception:
            return []

    def list_permission_rules(self) -> list:
        """`[{"action": "allow"|"ask"|"deny", "source": ..., "rule": ...},
        ...]` -- the live `PermissionEngine`'s own rule lists, for the
        `/permissions` dialog."""
        engine = self.session.permission_engine
        out: list = []
        for action, rules in (("deny", engine.deny_rules), ("ask", engine.ask_rules), ("allow", engine.allow_rules)):
            for r in rules:
                out.append({"action": action, "source": r.source or "?", "rule": r.raw or r.value or r.tool})
        return out

    # ---- slash commands ---------------------------------------------------

    def run_compact(self, instructions: str = "") -> str:
        """finding 11 (major, h4-h5-h3c review) / U5 must-do: `/compact`
        queued as a worker `Command` (`run_compact`) instead of running
        `session._run_compaction` to completion synchronously ON THIS (the
        UI) thread -- the old path froze the whole TUI (no repaint, no
        Esc) for the entire summarisation call. Deferred/refused outright
        while a turn is already running (`self.session.busy`), matching
        "handled between turns, deferred while busy" -- a compaction and
        an ordinary turn must never race over the same log. Its
        `compaction` events stream through the normal event pipe, so
        `tui/dispatch.py`'s new handler renders live progress instead of
        the UI just hanging."""
        # W4a misc: "`/compact` typed mid-turn is queued and runs when the
        # turn ends" -- queued onto the SAME worker Command queue either
        # way (it's already thread-safe FIFO); `run()`'s own pump loop only
        # ever reaches the NEXT Command once `_pump_turn` returns, so a busy
        # session naturally defers this to right after the current turn
        # ends, with no retyping needed. Only the returned NOTICE differs.
        self.commands.put(events.Command("run_compact", {"instructions": instructions.strip() or None}))
        if self.session.busy:
            return "A turn is already running -- /compact is queued and will run once it finishes."
        return ""

    def clear_session(self) -> str:
        """U5 must-do: `/clear` queued onto the worker thread (`run_clear`)
        -- `Session.clear()` fires real `SessionEnd(clear)`/
        `SessionStart(clear)` hooks (arbitrary user scripts) and builds a
        fresh log, so it gets the same off-the-UI-thread treatment as
        `run_compact`. The OLD behaviour only cleared the TUI's own
        transcript WIDGET -- the underlying log/context the next request
        would still derive from was completely untouched."""
        if self.session.busy:
            return "A turn is already running -- /clear will need to wait until it finishes."
        self.commands.put(events.Command("run_clear", {}))
        return ""

    def run_slash(self, name: str, args: str = "") -> str:
        """Resolve `name` through the U0 registry.

        * a `prompt`-kind command (custom command / skill) is expanded and
          submitted as the next user turn -- text comes back "" and the
          caller should not print anything;
        * `/compact` (finding 11) is queued onto the worker thread via
          `run_compact` instead of running synchronously here;
        * anything else runs through the TUI facade right here (it is local
          and fast) and its returned text is handed back as the result.
        """
        if self.registry is None:
            return f"No command registry is loaded: /{name}"
        cmd = self.registry.resolve(name)
        if cmd is None:
            return f"Unknown command: /{name} (try /help)"
        if name == "compact" and cmd.source == "builtin":
            return self.run_compact(args)
        if cmd.kind == "prompt" and cmd.run is not None:
            from halo_harness.commands.registry import expand_command_body, read_at_mention_snapshots

            body = cmd.run(args, self.facade)
            # finding 9: route through the real session's permission
            # engine + stripped tool env (see commands/registry.py's
            # `run_preexec_commands` docstring).
            result = expand_command_body(
                body, args, allowed_tools=getattr(cmd, "allowed_tools", None), cwd=self.cwd,
                permission_engine=getattr(self.session, "permission_engine", None),
                env=getattr(self.session, "tool_env", None),
            )
            if result.error:
                return result.error
            # H4 scope C: `@path` attachments in the EXPANDED body -- read
            # via the Read tool's own path resolution and appended as
            # snapshots (never inlined into the prompt text itself, same
            # as CLAUDE.md's own @import convention).
            # H5c finding 14: `queue_log_write` (never a direct
            # `self.session.log.append_snapshot`) -- this runs on the UI
            # thread, BEFORE `self.submit(result.text)` below decides
            # steer-vs-new-turn; a direct write here would race the worker
            # thread's own concurrent log writes while the session is busy,
            # same bug as `ingest_at_mentions`'s own two loops.
            for path_str, content in read_at_mention_snapshots(result.text, cwd=self.cwd):
                self.session.queue_log_write(
                    "snapshot", {"blocks": [{"type": "text", "text": f"@{path_str}\n{content}"}],
                                 "snapshot_kind": "at_mention"})
            # H8 scope E: `@server:resource` mentions in the expanded body.
            from halo_harness.mcp.mentions import read_server_resource_snapshots
            for label, content in read_server_resource_snapshots(
                    result.text, mcp_manager=getattr(self.session, "mcp_manager", None)):
                self.session.queue_log_write(
                    "snapshot", {"blocks": [{"type": "text", "text": f"@{label}\n{content}"}],
                                 "snapshot_kind": "at_mention"})
            # W4a: UserPromptExpansion -- see Session.fire_user_prompt_
            # expansion's own docstring for why THIS is the real expansion
            # point (never a plain typed prompt's own @mentions).
            if hasattr(self.session, "fire_user_prompt_expansion"):
                extra_ctx = self.session.fire_user_prompt_expansion(body, result.text)
                if extra_ctx:
                    self.session.queue_log_write(
                        "snapshot", {"blocks": [{"type": "text", "text": extra_ctx}], "snapshot_kind": "hook_context"})
            self.submit(result.text)
            return ""
        if cmd.run is None:
            return f"/{name} has no implementation in this build."
        try:
            return cmd.run(args, self.facade)
        except Exception as e:  # a command must never take the UI down with it
            return f"/{name} failed: {type(e).__name__}: {e}"

    # ---- read-only queries (UI thread, synchronous, cheap) ----------------

    def list_models(self) -> list:
        """`[{ref, context_tokens, max_output_tokens, price_in_per_m,
        price_out_per_m, provider, group, detail, dbu}, ...]` for the
        ModelPicker/init picker. Halo 2.0.4 round 4: this method is now a
        thin wrapper around `providers.model_enumeration.build_model_rows`
        -- the SAME cache-only row builder the roles wizard's own live
        enumeration (`enumerate_live`, in that same module) hands its
        freshly-refreshed catalogs to, so a row either surface shows is
        built by the exact same code (the brief's own "do not duplicate
        the picker's data source; share it") -- see that function's own
        docstring for the full field-by-field contract this preserves
        unchanged from before this round."""
        from halo_harness.providers.model_enumeration import build_model_rows
        # 1.0.1 part 2 fixpass finding 3: the session's own real `Settings.
        # effective_env` (shell < user < trusted project/local < policy) --
        # a credential living only in a settings.json `env` block is seen
        # here exactly like a real turn would resolve it, instead of this
        # listing surface disagreeing with it (a test-constructed Controller
        # with no `settings=` passes None, falling back to bare os.environ,
        # byte-for-byte unchanged from before this fix).
        env = self.settings.effective_env if self.settings is not None else None
        return build_model_rows(
            self.state_dir, env=env, routes=self.routes,
            current_ref=self.session.model_ref.raw,
            current_context_tokens=self.session.model_profile.context_tokens,
            current_max_output_tokens=self.session.model_profile.max_output_tokens,
            current_provider=self.session.model_ref.provider,
        )

    def list_sessions(self) -> list:
        """`[{id, cwd, mtime, summary, title, model, cost_usd, turns}, ...]`,
        newest first, for the `--resume`/`/resume` picker (U5 sessions UX:
        "title/age/cost/turns" -- `title` is whatever `/rename` or the
        after-first-turn auto-title last wrote as a `meta` node's own
        `title` field, `""` if never set; `cost_usd`/`turns` are summed/
        counted straight from that session's own `usage`/`user` nodes, the
        same source `/cost` and `/stats` read). `model` (H13 Part C: "/resume
        search... fuzzy over title, first prompt, cwd and model") is the
        LAST `meta` node's own `model` field seen, `""` if the session
        predates any `meta` node ever recording one. Reads OUR session logs
        only (~/.halo). Synchronous file I/O -- U5 must-do: callers on
        the UI thread (the `/resume` slash handler) run this on a worker,
        never inline (matches `_git_branch`'s own fix)."""
        slug = project_slug(self.cwd)
        directory = self.state_dir / "sessions" / slug
        out: list = []
        if not directory.is_dir():
            return out
        for path in sorted(directory.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True):
            summary, title, model, cost_usd, turns = "", "", "", 0.0, 0
            try:
                for line in split_lines(path.read_text(encoding="utf-8", errors="replace")):
                    try:
                        node = json.loads(line)
                    except ValueError:
                        continue
                    ntype = node.get("type")
                    if ntype == "user":
                        turns += 1
                        if not summary:
                            for block in node.get("content") or []:
                                if isinstance(block, dict) and block.get("type") == "text":
                                    summary = block.get("text", "")[:80]
                                    break
                    elif ntype == "meta":
                        if isinstance(node.get("title"), str) and node["title"]:
                            title = node["title"]
                        if isinstance(node.get("model"), str) and node["model"]:
                            model = node["model"]
                    elif ntype == "usage":
                        c = node.get("cost_usd")
                        if isinstance(c, (int, float)):
                            cost_usd += c
            except OSError:
                pass
            out.append({"id": path.stem, "cwd": str(self.cwd), "mtime": path.stat().st_mtime,
                        "summary": summary, "title": title, "model": model,
                        "cost_usd": cost_usd, "turns": turns})
        return out

    def resume(self, session_id: str) -> None:
        """Read a prior session's log and push ONE `replay` event carrying
        its renderable messages. The next prompt continues THAT session:
        the Session's own log is reopened on it (see
        `halo_harness.tui.app` for the swap)."""
        from halo_harness.agent.log import SessionLog
        from halo_harness.termtitle import set_terminal_title

        # Halo 2.0.2 W7 round 1 (brief F): "set it ... on resume" -- this
        # is the one method both the command palette's session pick
        # (tui/app.py's own `_on_palette_pick`) and the `/resume` picker
        # (tui/slash.py's `_open_resume_picker`) call, so hooking it here
        # covers both triggers with no duplication.
        set_terminal_title("halo")
        log = SessionLog(self.cwd, session_id=session_id)
        self.replay_messages = _messages_from_nodes(log.nodes())
        if self.replay_messages:
            self.events.put(events.replay(self.replay_messages))
        # vibes/review.md finding 65: the session's own LOG was never
        # reopened -- the picker showed the old history (the replay event
        # above) but the next prompt appended to the CURRENT session's
        # file, so /resume and Ctrl+P never actually switched anything.
        # Swapping `session.log` makes every later append/derive land on
        # the resumed session's file (its nodes are already loaded); the
        # per-session cost meter is rebuilt fresh so the two sessions'
        # stats don't mix.
        session = getattr(self, "session", None)
        if session is not None and getattr(session, "log", None) is not None:
            session.log = log
            cm = getattr(session, "cost_meter", None)
            if cm is not None:
                try:
                    from halo_harness.agent.loop import CostMeter
                    session.cost_meter = CostMeter(price_in=cm.price_in, price_out=cm.price_out)
                except Exception:
                    pass

    def mcp_status(self) -> "Optional[dict]":
        return self._mcp_status()

    def reconnect_mcp(self, name: str, abort=None) -> list:
        """`abort` (u2-h3b finding 9, default None -- unchanged for every
        existing sync caller): a `threading.Event` a caller running THIS
        on its own worker thread (never the UI thread itself -- see
        `tui/dialogs/mcp_status.py`) can set to cut a hung/slow reconnect's
        WAIT short, threaded down to `McpManager.reconnect`'s own
        abort-aware close/start waits. The reconnect keeps running
        regardless (same "abandoned, not stopped" caveat as everywhere
        else abort-aware waiting is used in this codebase) -- aborting
        just stops the CALLER from blocking on it."""
        if self._reconnect_fn is None:
            return [f"MCP support is not connected in this build ({name} unchanged)."]
        # H9 bug fix (item 11, MCP compatibility matrix): `McpManager.
        # reconnect()` (what `self._reconnect_fn` calls) only ever restarts
        # an ALREADY-KNOWN handle using its config from when the session
        # started -- neither it nor this method used to re-read
        # ~/.claude.json/.mcp.json at all, so a real on-disk edit to an
        # existing server's command/args/env/url, or a brand-new server
        # name added since, was invisible no matter how many times /mcp
        # reconnect ran. Re-resolve the config chain from a freshly re-read
        # ~/.claude.json (project/local/user scopes -- the same tiers
        # `resolve_server_configs` itself documents; launch-time-only
        # concerns like --mcp-config/--chrome/--playwright are deliberately
        # NOT re-applied here, since those are a NEW SESSION's decision,
        # not something reconnecting one server should reconsider) and
        # `resync_from` the live manager against it BEFORE the plain
        # restart below -- covers both "config changed" and "brand new
        # name" in one path. Best-effort: any failure here (no `mcp`
        # package, a malformed file, an unresolvable path) must never
        # block the plain reconnect that already worked before this fix.
        if self.mcp_manager is not None:
            try:
                from halo_harness.config.claude_json import load_claude_json
                from halo_harness.mcp.manager import resolve_server_configs
                fresh_configs, _notices = resolve_server_configs(
                    cwd=self.cwd, claude_json=load_claude_json(), settings=self.settings)
                self.mcp_manager.resync_from(fresh_configs)
            except Exception:
                pass
        try:
            result = self._reconnect_fn(name, abort=abort)
            # H3b must-do (unwired seam): a reconnected server's tool list
            # only ever entered the deferred pool once, at session start
            # (`SessionCatalog` built from `McpManager.all_tools()` THEN) --
            # without this, `/mcp reconnect` on a server whose tools
            # changed (or one added mid-session) leaves them permanently
            # unreachable through ToolSearch even though the reconnect
            # itself succeeded.
            catalog = getattr(self.session, "session_catalog", None)
            if catalog is not None:
                try:
                    catalog.refresh_deferred_for_server(name)
                except Exception:
                    pass
            return result if isinstance(result, list) else [str(result)]
        except Exception as e:
            return [f"reconnect {name} failed: {type(e).__name__}: {e}"]

    def approve_mcp_server(self, name: str, abort=None) -> list:
        """H3b must-do (unwired seam): completes the `.mcp.json`
        `pending_approval` interactive flow. Persists the approval via
        `mcp_setup.record_mcp_approval` -- keyed by the entry's own
        sha256 (D-CFG: an edited/tampered entry needs re-approval), read
        straight back off `<cwd>/.mcp.json` by name rather than needing a
        new field threaded through `mcp/manager.py`'s own config objects
        -- so the server stays approved on the NEXT launch too, not just
        this session, then reconnects it (which also now refreshes its
        deferred ToolSearch pool, see `reconnect_mcp`). `abort`: see
        `reconnect_mcp`'s own docstring -- threaded through to the
        reconnect this triggers."""
        if self.mcp_manager is None:
            return [f"MCP support is not connected in this build ({name} unchanged)."]
        handle = self.mcp_manager.handles.get(name)
        if handle is None:
            return [f"unknown MCP server: {name}"]
        if handle.config.scope != "project":
            return [f"{name} is not a .mcp.json (project-scope) server -- nothing to approve"]
        import json as _json

        mcp_json_path = self.cwd / ".mcp.json"
        try:
            raw = _json.loads(mcp_json_path.read_text(encoding="utf-8-sig"))
            raw_entry = (raw.get("mcpServers") or {})[name]
        except (OSError, ValueError, KeyError) as e:
            return [f"could not read {name}'s .mcp.json entry to approve it: {type(e).__name__}: {e}"]
        from halo_harness import mcp_setup
        mcp_setup.record_mcp_approval(name, raw_entry)
        handle.config.pending_approval = False
        return self.reconnect_mcp(name, abort=abort)

    def reconnect_all_mcp(self, abort=None) -> list:
        """round4 brief item 1: `R` in `/mcp` -- every configured server
        AND cached connector row, each through `reconnect_mcp` (so a
        connector name's own special handling, see `tui/bootstrap.py`'s
        `_reconnect_fn`, and the manual-reconnect backoff reset, see
        `McpManager.reconnect_manual`, both apply exactly as a single `r`
        would). Sequential, not parallel -- simple, and each call is
        already its own timeout-bounded, abortable wait; `abort` stops
        the whole loop between servers, not mid-reconnect of the one in
        flight (same "abandoned, not stopped" caveat as everywhere else)."""
        lines: list = []
        for row in self.list_mcp_servers():
            name = row.get("name")
            if not name:
                continue
            lines.extend(self.reconnect_mcp(name, abort=abort))
            if abort is not None and abort.is_set():
                lines.append("cancelled -- any remaining servers were left unchanged.")
                break
        if not lines:
            lines.append("No MCP servers configured.")
        return lines

    def login_mcp_server(self, name: str, abort=None, print_fn=None) -> list:
        """round4 brief item 1: `l` in `/mcp` -- the 2.0.1 OAuth flow for
        a local http/sse server (`mcp_cli.run_login`, the SAME helper
        `halo mcp login` uses), or, for a claude.ai connector row, the
        re-auth instructions line the bridge already produces (there is
        no local OAuth flow for one of those -- the login lives in
        claude.ai/claude itself).

        2.0.2 review finding 14: `abort` used to only ever reach the
        POST-login `reconnect_mcp` call below -- the login round trip
        itself (where the real, up-to-120s blocking wait actually lives)
        never saw it at all, so Esc on the TUI's own dialog could not
        actually cancel a login in progress. `print_fn` (new) is how that
        SAME dialog gets the "open this URL" line to show up somewhere
        visible at all -- Textual drops a bare `print()` from a worker
        thread entirely."""
        if name.startswith("connector__"):
            from halo_harness.mcp import connectors_bridge
            slug = name[len("connector__"):]
            info = next((c for c in connectors_bridge.get_connectors() if c.slug == slug), None)
            if info is None:
                return [f"{name}: no longer reported by `claude mcp list`."]
            text = connectors_bridge.reauth_instructions(info)
            return [text or f"{info.name}: already authorized -- nothing to do."]
        from halo_harness.mcp_cli import run_login
        lines, ok = run_login(name, self.cwd, settings=self.settings, abort=abort, print_fn=print_fn)
        if ok:
            lines += self.reconnect_mcp(name, abort=abort)
        return lines

    def test_mcp_server(self, name: str, abort=None) -> list:
        """round4 brief item 1: `t` in `/mcp` -- a `tools/list` round
        trip with timing, straight off `McpManager.test_server`."""
        if name.startswith("connector__"):
            return [f"{name}: claude.ai connectors are tested through `claude` itself, not halo's own manager."]
        if self.mcp_manager is None:
            return [f"MCP support is not connected in this build ({name} unchanged)."]
        result = self.mcp_manager.test_server(name, abort=abort)
        ms = result["elapsed_s"] * 1000
        if result["ok"]:
            return [f"{name}: tools/list ok in {ms:.0f}ms -- {result['tool_count']} tool(s)."]
        return [f"{name}: tools/list failed after {ms:.0f}ms -- {result['error']}"]

    def deep_dive_mcp_server(self, name: str, abort=None) -> list:
        """round6 brief ("MCP connectivity deep dive"): `D` in `/mcp` --
        `mcp.doctor_probe`'s bounded, evidenced probe plus `mcp.
        doctor_deep`'s propose-or-replay step; NEVER applies anything by
        itself (`apply_mcp_fix` below is the explicit yes)."""
        if name.startswith("connector__"):
            return [f"{name}: claude.ai connectors have no local config to deep-dive -- see claude's own logs."]
        return self._run_mcp_deep_dive(name, apply=False, abort=abort)

    def apply_mcp_fix(self, name: str, abort=None) -> list:
        """round6 brief: `A` in `/mcp` -- the explicit yes. Diagnoses
        `name` again (same evidence/propose-or-replay `D` runs) and, when
        the resulting proposal (a fresh one, or a learned replay) is one
        of the three mechanically-appliable kinds, writes it to the
        on-disk entry and re-tests -- a fix that verifies healthy is
        learned for next time (`providers.learned_rules.learn_mcp_fix`)."""
        if name.startswith("connector__"):
            return [f"{name}: claude.ai connectors have no local config to apply a fix to."]
        return self._run_mcp_deep_dive(name, apply=True, abort=abort)

    def _run_mcp_deep_dive(self, name: str, *, apply: bool, abort=None) -> list:
        from halo_harness.mcp import doctor_deep
        cfg = doctor_deep.resolve_one_config(name, cwd=self.cwd, settings=self.settings)
        if cfg is None:
            return [f"{name}: could not re-resolve its config to diagnose."]
        tool_env = doctor_deep.resolve_tool_env(self.cwd, self.settings)
        result = doctor_deep.diagnose(name, cfg, cwd=self.cwd, tool_env=tool_env, state_dir=self.state_dir,
                                        apply=apply, settings=self.settings, abort=abort)
        if result.applied and self.mcp_manager is not None:
            # A fix just landed on disk -- re-sync the LIVE manager the
            # same way an ordinary config edit (`e`) already does, so this
            # session's own tool dispatch sees it immediately rather than
            # only after a later manual reconnect.
            try:
                from halo_harness.config.claude_json import load_claude_json
                from halo_harness.mcp.manager import resolve_server_configs
                fresh, _notices = resolve_server_configs(cwd=self.cwd, claude_json=load_claude_json(),
                                                            settings=self.settings)
                self.mcp_manager.resync_from(fresh)
                handle = self.mcp_manager.handles.get(name)
                if handle is not None and handle.state == "pending":
                    handle.start(abort=abort)
            except Exception:
                pass
        return result.message.splitlines()

    def set_mcp_server_disabled(self, name: str, disabled: bool) -> list:
        """round4 brief item 1: `d` in `/mcp` -- scope-aware disable/
        enable (`mcp_cli.set_server_disabled_in_config`, Claude Code's own
        per-directory `disabledMcpServers`), plus the matching LIVE effect
        on this session's manager so the dialog reflects it immediately
        rather than only after a restart."""
        from halo_harness.mcp_cli import set_server_disabled_in_config
        try:
            where = set_server_disabled_in_config(name, cwd=self.cwd, disabled=disabled)
        except (OSError, ValueError) as e:
            return [f"{name}: could not update config: {type(e).__name__}: {e}"]
        if self.mcp_manager is None:
            return [f"{name}: {'disabled' if disabled else 'enabled'} ({where}); no live MCP session to update."]
        if disabled:
            handle = self.mcp_manager.handles.get(name)
            if handle is not None:
                handle.close(timeout=5.0)
                handle.state = "disabled"
                handle.error = "disabled by the user (`/mcp` d)"
                handle.config.disabled_reason = handle.error
            return [f"{name}: disabled ({where})."]
        try:
            from halo_harness.config.claude_json import load_claude_json
            from halo_harness.mcp.manager import resolve_server_configs
            fresh, _notices = resolve_server_configs(cwd=self.cwd, claude_json=load_claude_json(), settings=self.settings)
        except Exception:
            fresh = {}
        cfg = fresh.get(name)
        if cfg is None:
            return [f"{name}: enabled ({where}), but could not re-resolve its config -- restart halo to pick it up."]
        self.mcp_manager.resync_from({name: cfg})
        handle = self.mcp_manager.handles.get(name)
        if handle is not None and handle.state == "pending":
            handle.start()
        return [f"{name}: enabled ({where})."]

    def resolve_mcp_config(self, name: str):
        """round4 brief item 1: `e` in `/mcp` -- the LIVE, freshly re-
        resolved `McpServerConfig` for one server (scope/command/args/
        env/url/headers), straight from the same `resolve_server_configs`
        the session itself used, so the `$EDITOR` jump / inline form
        always reflects what's on disk right now. `None` for an unknown
        name (a connector row, or one no longer configured)."""
        from halo_harness.config.claude_json import load_claude_json
        from halo_harness.mcp.manager import resolve_server_configs
        try:
            resolved, _notices = resolve_server_configs(cwd=self.cwd, claude_json=load_claude_json(), settings=self.settings)
        except Exception:
            return None
        return resolved.get(name)

    def memory_path(self):
        from halo_harness.config.paths import memory_dir
        return memory_dir(str(self.cwd))

    def ingest_at_mentions(self, text: str) -> None:
        """`@file#L10-20` mentions (U5 scope A): resolve + read via the
        Read tool (the SAME path resolution/line-numbering a model's own
        Read call would use) and append each as a log snapshot -- the
        mention text ITSELF is left untouched in the submitted turn
        (matches `commands/registry.py`'s own `@path` convention for
        custom commands: never inlined, always a separate context block).
        Best-effort per mention: a path that doesn't resolve to a real
        file is silently skipped, never an error (the model still sees
        the literal `@mention` text and can ask/Read it itself)."""
        from halo_harness.tools.base import ToolContext
        from halo_harness.tools.read import ReadTool
        from halo_harness.tui.completion import parse_at_mentions

        # H9 whole-tree review finding 14: `@server:resource` mentions now
        # resolve on a background thread, never the CALLER's own (the UI
        # thread, for a live TUI submit/steer) -- `McpManager.resources()`
        # is one live `resources/list` RPC per connected server
        # (MCP_TIMEOUT, 30s, EACH), and used to run synchronously here,
        # BEFORE the `@path`-only early return below, on EVERY submit/steer
        # regardless of whether `text` even had an `@` in it. Verified with
        # a stub manager: "fix the failing test"/"why is the build red?"/
        # "thanks" each blocked for 1.5s; a genuinely hung server blocked
        # for its full 30s on every Enter. The same cheap regex `mcp.
        # mentions.extract_server_resource_mentions` itself now also runs
        # first is checked again here so the thread is never even spawned
        # for the common case (no `@name:uri`-shaped text at all) --
        # `queue_log_write` (the same thread-safe write every other
        # @mention here already uses -- see the `@path` loop below) is what
        # makes it safe for this to land whenever the fetch actually
        # finishes, possibly well after this method itself has returned.
        from halo_harness.mcp.mentions import _AT_SERVER_RESOURCE_RE
        mcp_manager = getattr(self.session, "mcp_manager", None)
        if mcp_manager is not None and _AT_SERVER_RESOURCE_RE.search(text or ""):
            threading.Thread(target=self._ingest_mcp_resource_mentions, args=(text, mcp_manager),
                              daemon=True, name="halo-mcp-mention-fetch").start()

        mentions = parse_at_mentions(text)
        if not mentions:
            return
        tool = ReadTool()
        # H8 scope B: `vision` threaded through so an `@path.png` mention
        # attaches a REAL image block (same gate/size rule as a model-issued
        # Read call), not just a "no vision" text note. `self.session` may
        # be a lightweight test double with no `model_profile` at all (e.g.
        # test_tui.py's `_real_controller`'s `_MinimalSession`) -- two
        # levels of getattr, never a bare attribute access, so that's a
        # quiet `vision=False` rather than an AttributeError that would
        # abort every @mention in the turn.
        model_profile = getattr(self.session, "model_profile", None)
        ctx = ToolContext(cwd=self.cwd, vision=getattr(model_profile, "vision", False))
        for raw, start, end in mentions:
            path = Path(raw).expanduser()
            if not path.is_absolute():
                path = self.cwd / path
            try:
                resolved = path.resolve()
            except OSError:
                continue
            if not resolved.is_file():
                continue
            input_data = {"file_path": str(resolved)}
            label = raw
            if start is not None:
                input_data["offset"] = max(0, start - 1)
                input_data["limit"] = max(1, (end or start) - start + 1)
                label = f"{raw}#L{start}" if not end or end == start else f"{raw}#L{start}-{end}"
            try:
                result = tool.run(input_data, ctx)
            except Exception:
                continue
            if isinstance(result.content, list):
                # An image block (or list of blocks) from _read_image --
                # keep it a REAL content block, never stringify it into
                # unreadable dict-repr text.
                blocks = [{"type": "text", "text": f"@{label}"}] + list(result.content)
            else:
                content = result.content if isinstance(result.content, str) else str(result.content)
                blocks = [{"type": "text", "text": f"@{label}\n{content}"}]
            try:
                # H5c finding 14: `queue_log_write` (never a direct
                # `self.session.log.append_snapshot`) -- this runs on the UI
                # thread, BEFORE `submit()` decides steer-vs-new-turn; while
                # the session is busy, a direct write here would race the
                # worker thread's own concurrent log writes (verified: a
                # steer carrying `@mention` typed while a Read tool runs
                # made the NEXT request's user message
                # `['text','tool_result','text']`, which Anthropic 400s on).
                # `_ingest_mcp_resource_mentions` below uses the SAME call,
                # from its own background thread.
                self.session.queue_log_write("snapshot", {"blocks": blocks, "snapshot_kind": "at_mention"})
            except Exception:
                pass

    def _ingest_mcp_resource_mentions(self, text: str, mcp_manager) -> None:
        """H9 whole-tree review finding 14: the actual `@server:resource`
        fetch -- `resources/list` (or, once cached, nothing) then
        `resources/read` per real match -- runs HERE, on the background
        thread `ingest_at_mentions` spawned, never on the caller's own.
        `queue_log_write` is thread-safe by design (see `Session.
        queue_log_write`'s own docstring), so this may finish anywhere from
        immediately to well after `ingest_at_mentions` itself already
        returned and the turn is already under way -- the snapshot lands
        in the log at the next safe point either way."""
        from halo_harness.mcp.mentions import read_server_resource_snapshots, unresolved_server_mentions
        try:
            snapshots = read_server_resource_snapshots(text, mcp_manager=mcp_manager)
        except Exception:
            snapshots = []
        for res_label, res_content in snapshots:
            try:
                self.session.queue_log_write(
                    "snapshot", {"blocks": [{"type": "text", "text": f"@{res_label}\n{res_content}"}],
                                 "snapshot_kind": "at_mention"})
            except Exception:
                pass
        # W4a misc: an `@name:uri` naming a server that ISN'T connected at
        # all (never the "server is fine, that exact uri just isn't listed"
        # case `read_server_resource_snapshots` already treats as silent)
        # gets a visible warning, naming the server -- queued the SAME
        # thread-safe way as the snapshots above so it lands in the
        # transcript regardless of whether a turn is already running.
        try:
            for server in unresolved_server_mentions(text, mcp_manager=mcp_manager):
                warning = f"@{server}:... does not match any currently connected MCP server named {server!r}."
                self.session.queue_log_write(
                    "snapshot", {"blocks": [{"type": "text", "text": warning}], "snapshot_kind": "at_mention"})
                # review finding 23 / parity gap: the snapshot above is
                # model-only context (same "never inlined, separate block"
                # rule every @mention here follows) -- the commit this
                # shipped in says the warning itself "warns visibly", which
                # only ever happened to the MODEL. A live TUI session gets
                # an actual notice too, the same sink a background sub-
                # agent's own live asks use (`_event_sink`, set by `run()`;
                # None for -p/a bare Session, where there is no live UI to
                # notice at all -- headless.py's own identical call site
                # prints a stderr line instead for that case).
                sink = getattr(self.session, "_event_sink", None)
                if sink is not None:
                    try:
                        sink(events.notification(warning))
                    except Exception:
                        pass
        except Exception:
            pass

    # ---- U5 scope A: `!cmd` inline shell -- through the Bash tool + the
    # SAME permission rules a model-issued call would get, but never
    # through the model loop (`agent/loop.py`'s command pump is untouched:
    # nothing here ever queues a `Command`). -----------------------------

    def decide_inline_shell(self, command: str) -> Decision:
        """The `Decision` a plain `Bash(command)` call would get under the
        CURRENT permission mode/rules -- read-only, no side effect.
        `tui/app.py`'s `!cmd` handling uses this to decide whether to run
        immediately, show a confirmation card, or refuse outright."""
        return self.session.permission_engine.decide("Bash", {"command": command})

    def run_inline_shell(self, command: str) -> "tuple[str, object]":
        """Execute `command` via the real Bash tool. Synchronous -- always
        called from a Textual worker THREAD (`tui/app.py`'s `run_worker
        (thread=True)`, same pattern as `_git_branch_worker`) -- a
        DIFFERENT thread from the session's OWN dedicated worker thread,
        and nothing here checks `session.busy` before running (by design:
        `!cmd` runs OUTSIDE the model loop entirely, on demand, regardless
        of whether a turn happens to be in flight). Returns `(tool_use_id,
        ToolResult)`; the command runs immediately either way, but H5c
        finding 14: the resulting tool_use/tool_result pair is queued
        (never written directly) so it can never race the session's own
        worker thread's concurrent log writes -- verified: an inline
        `!cmd` landing between an assistant `tool_use` and its own
        `tool_result` broke pairing on every route."""
        from halo_harness.tools.base import ToolContext
        from halo_harness.tools.bash import BashTool
        from halo_harness.hooks import env_file_path

        # finding 9: the session's own stripped tool_env (never a raw
        # os.environ read, which used to leak every provider API key into
        # an inline `!cmd`'s subprocess) + CLAUDE_ENV_FILE (finding 6),
        # same as a model-issued Bash call gets via _dispatch_tools.
        result = BashTool().run(
            {"command": command},
            ToolContext(cwd=self.cwd, bash_state=self._inline_bash_state,
                        env=getattr(self.session, "tool_env", None),
                        env_file=env_file_path(self.session.log.session_id)),
        )
        tool_use_id = f"inline_{uuid.uuid4().hex[:12]}"
        try:
            self.session.queue_log_write("inline_shell", {
                "tool_use_id": tool_use_id, "command": command,
                "content": result.content, "is_error": result.is_error,
            })
        except Exception:
            pass  # logging is best-effort -- the command already ran either way
        return tool_use_id, result

    # ---- U5 scope C: session titles/rename/fork/export/stats ----------

    def get_title(self) -> str:
        """The current session's own title (the last `meta` node carrying
        one), "" if never set."""
        for node in reversed(self.session.log.nodes()):
            if node.get("type") == "meta" and isinstance(node.get("title"), str) and node["title"]:
                return node["title"]
        return ""

    def rename_session(self, title: str) -> None:
        title = (title or "").strip()
        if title:
            self.session.log.append_meta(title=title)

    def maybe_autoname_title(self) -> Optional[str]:
        """After the FIRST turn completes (`tui/app.py`'s `turn_done`
        handling, `turn == 1`, from a worker thread): generate a short
        title via the small model (falling back to a heuristic on any
        failure) and store it, unless one is already set (`/rename` beat
        it, or this already ran). Returns the title actually stored, or
        None if one was already present / there's no first user turn yet."""
        if self.get_title():
            return None
        first_user = ""
        for node in self.session.log.nodes():
            if node.get("type") == "user":
                first_user = "".join(b.get("text", "") for b in node.get("content") or []
                                      if isinstance(b, dict) and b.get("type") == "text")
                break
        if not first_user.strip():
            return None
        title = _generate_title(self.session, first_user)
        self.rename_session(title)
        return title

    def fork_session(self) -> str:
        """Copy the current session's log into a brand-new session id
        under the same project slug (a real, independent file -- a
        `SessionLog` is append-only, so forking is a copy, never a
        symlink/shared-tail scheme) and switch this Controller onto it.
        Returns the new session id; the conversation continues unchanged,
        now diverging independently of the original.

        H11b finding 8: a live `cc:` claude subprocess (still tied to the
        OLD conversation id, now copied verbatim into the new log's own
        `cc_session_id` meta node) is closed here -- otherwise this
        Session would just keep talking to that SAME old process/
        conversation, never actually diverging on the claude side at all,
        and the NEXT restart (Esc/crash) would `--resume` an id that was
        never independently created. `_cc_fork_session` tells `ensure_cc_
        state`'s next start to use `--resume <that id> --fork-session`
        (claude's own "branch into a new conversation" flag) instead of a
        plain resume, which would just continue the SAME shared
        conversation the original session might still be using."""
        from halo_harness.agent.log import SessionLog

        new_id = uuid.uuid4().hex
        new_log = SessionLog(self.cwd, session_id=new_id)
        for node in self.session.log.nodes():
            new_log._append({k: v for k, v in node.items() if k != "seq"})
        self.session.log = new_log
        if getattr(self.session, "_cc_state", None) is not None:
            self.session.close_cc()
            self.session._cc_state = None
            self.session._cc_fork_session = True
        return new_id

    def export_session(self, *, sanitize: bool = False, path: Optional[str] = None) -> str:
        """Render the current session as Markdown (`/export [--sanitize]
        [file]`). Writes to `path` when given, else
        `<state_dir>/exports/<session_id>.md`. Returns the path written.
        `sanitize=True` redacts text shaped like a bearer token/API key/
        password assignment -- best-effort pattern matching, not a
        substitute for care about what gets exported."""
        log = self.session.log
        text = render_transcript_markdown(log.nodes(), session_id=log.session_id)
        if sanitize:
            text = sanitize_transcript(text)
        out_path = Path(path) if path else (self.state_dir / "exports" / f"{log.session_id}.md")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
        return str(out_path)

    def session_stats(self) -> dict:
        """`/stats`: tokens/cost per model + tool-call counts for the
        CURRENT session's log."""
        return compute_session_stats(self.session.log.nodes())

    # ---- U5 scope B: git-shadow rewind ---------------------------------

    def shadow_steps(self) -> list:
        from halo_harness.shadow import store_for_controller
        store = store_for_controller(self)
        return store.list_steps() if store is not None else []

    def turn_checkpoints(self) -> list:
        """2.0.6 round 6: one checkpoint per TURN that has shadow steps --
        `/rewind turn <N>`'s picker data."""
        from halo_harness.shadow import store_for_controller
        store = store_for_controller(self)
        return store.turn_checkpoints() if store is not None else []

    def rewind_turn(self, turn: int) -> Optional[dict]:
        """2.0.6 round 6: restore the working tree to the START of `turn`
        (the last step of the previous turn, or the session's own start
        when none). Same return shape as `rewind_apply`."""
        from halo_harness.shadow import store_for_controller
        store = store_for_controller(self)
        return store.rewind_to_turn_start(turn) if store is not None else None

    def rewind_preview_undo(self) -> Optional[dict]:
        from halo_harness.shadow import store_for_controller
        store = store_for_controller(self)
        return store.preview_undo() if store is not None else None

    def rewind_preview_redo(self) -> Optional[dict]:
        from halo_harness.shadow import store_for_controller
        store = store_for_controller(self)
        return store.preview_redo() if store is not None else None

    def rewind_apply(self, step_id: str, *, verb: str = "rewind") -> Optional[dict]:
        """Actually restore the working tree to `step_id` and log a
        `rewind` node (`agent/log.py`'s own minimal append helper).
        Returns `{"step", "files"}` (`ShadowStore.rewind_to`'s own shape),
        or None if `step_id` matches no recorded step."""
        from halo_harness.shadow import store_for_controller
        store = store_for_controller(self)
        if store is None:
            return None
        result = store.rewind_to(step_id)
        if result is None:
            return None
        try:
            self.session.log.append_rewind(verb=verb, step_id=step_id, files=result.get("files") or [])
        except Exception:
            pass
        return result


def _messages_from_nodes(nodes: list) -> list:
    """The renderable subset of a session log: `{role, text}` for user and
    assistant text (tool calls/results are dropped -- a replay is a
    transcript, not a tool-by-tool reconstruction)."""
    out: list = []
    for node in nodes:
        ntype = node.get("type")
        if ntype == "user":
            text = "".join(b.get("text", "") for b in node.get("content") or []
                           if isinstance(b, dict) and b.get("type") == "text")
            if text:
                out.append({"role": "user", "text": text})
        elif ntype == "assistant":
            text = "".join(b.get("text", "") for b in node.get("content") or []
                           if isinstance(b, dict) and b.get("type") == "text")
            if text.strip():
                out.append({"role": "assistant", "text": text})
    return out


# ============================================================================
# U5 scope C: session titles, export, stats -- pure helpers over a session
# log's own node list, kept module-level (no `self`) so they're directly
# unit-testable against a plain list of dicts, no Session/Controller needed.
# ============================================================================

def _heuristic_title(text: str) -> str:
    """A short title with no model call: the first ~6 words of the first
    user message. Always available, used as `_generate_title`'s fallback
    and its own return value when there's no `session` to ask."""
    title = " ".join(text.strip().split()[:6])
    return title[:60] if title else "Untitled session"


def _clean_title(raw: str) -> str:
    """The small model's raw reply -> a bare title: first line only,
    surrounding quotes/punctuation/whitespace stripped, capped at 60
    chars."""
    first_line = (raw or "").strip().splitlines()[0].strip() if (raw or "").strip() else ""
    return first_line.strip(" \t\"'.,;:-")[:60]


def _generate_title(session, first_user_text: str) -> str:
    """The small model's own one-line title for `first_user_text`,
    falling back to `_heuristic_title` on any failure (no small model
    configured, a network error, an empty/unusable reply, ...) -- title
    generation must never be able to fail a session or block on a dead
    provider. `session._call_model_for_hook` (agent/loop.py) already
    implements "one-shot small-model call, never logged" for hooks; reused
    here with a title-specific prompt rather than duplicating the request-
    building plumbing."""
    heuristic = _heuristic_title(first_user_text)
    caller = getattr(session, "_call_model_for_hook", None)
    if not callable(caller):
        return heuristic
    try:
        raw = caller(
            "Reply with ONLY a short 3-6 word title (no quotes, no trailing punctuation) "
            f"summarizing this conversation's request:\n\n{first_user_text[:2000]}",
            4.0,
        )
    except Exception:
        return heuristic
    cleaned = _clean_title(raw)
    return cleaned or heuristic


def render_transcript_markdown(nodes: list, *, session_id: str) -> str:
    """`/export`'s own Markdown rendering of a session log's node list --
    user/assistant text, tool calls (as a fenced JSON block of their
    input), tool results, and rewind markers, in log order."""
    lines = [f"# halo session {session_id}", ""]
    for node in nodes:
        ntype = node.get("type")
        if ntype == "user":
            text = "".join(b.get("text", "") for b in node.get("content") or []
                           if isinstance(b, dict) and b.get("type") == "text")
            if text:
                lines.append(f"## User\n\n{text}\n")
        elif ntype == "assistant":
            blocks = node.get("content") or []
            text = "".join(b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text")
            if text.strip():
                lines.append(f"## Assistant\n\n{text}\n")
            for call in blocks:
                if isinstance(call, dict) and call.get("type") == "tool_use":
                    body = json.dumps(call.get("input", {}), indent=2, default=str, ensure_ascii=False)
                    lines.append(f"### Tool call: {call.get('name', '?')}\n\n```json\n{body}\n```\n")
        elif ntype == "tool_result":
            content = node.get("content")
            text = content if isinstance(content, str) else json.dumps(content, default=str, ensure_ascii=False)
            label = " (error)" if node.get("is_error") else ""
            lines.append(f"### Tool result{label}\n\n```\n{text[:4000]}\n```\n")
        elif ntype == "rewind":
            lines.append(f"### Rewind ({node.get('verb')}) to step {node.get('step_id')}\n")
    return "\n".join(lines)


def sanitize_transcript(text: str) -> str:
    """`/export --sanitize`'s own redaction -- best-effort, not a security
    boundary (see `export_session`'s own note).

    H9 whole-tree review finding 4: this used to be a SEPARATE regex
    (`\\b((?:api|secret|access)?[-_]?(?:key|token|password...)\\s*[:=]\\s*)`)
    from `halo export --sanitize`'s own -- and a broken one: it
    requires a `\\b` word boundary immediately before the literal "key"/
    "token"/etc, but a namespaced name like `OPENROUTER_API_KEY` has NO
    such boundary there (`_` and the following letter are both `\\w`, so
    `\\b` can never fire between them) -- verified, this regex matched a
    bare `token=...`/`api_key: ...` but missed `OPENROUTER_API_KEY=...`
    entirely (5 of 6 verified leak cases; only `Bearer` was ever caught).
    Delegates to `export_cli.sanitize_text` now -- the ONE sanitizer both
    `/export --sanitize` (this function) and `halo export
    --sanitize` (export_cli.cmd_export) use, so a fix to one is a fix to
    both."""
    from halo_harness.export_cli import sanitize_text
    return sanitize_text(text)


# H9 whole-tree review finding 29: a "user" log node carrying one of these
# `kind` tags (agent/log.py's own `append_user(kind=...)`) is NOT a genuine
# new user prompt -- a background sub-agent/job completion notice, a
# Stop-hook continuation, a steer's own text, or a compaction's own
# summary/re-appended tail. Untagged (every node from before this tagging
# existed, AND the one real case: `Session.turn()`'s own new-prompt
# append) counts as a real turn -- old session logs keep reporting exactly
# what they always did; only NEW logs get the more accurate count.
_NON_PROMPT_USER_KINDS = frozenset({
    "compaction_summary", "compaction_tail", "continuation", "agent_notice", "job_notice", "steer",
})


def format_cache_tokens_suffix(bucket: dict) -> str:
    """H9 whole-tree review finding 29: a short ", Ncr/Mcw cache" suffix
    for a stats display line, empty when a route never reported either
    field (Databricks, most non-Claude models) -- shared by the TUI's own
    `/stats` (commands/builtins.py) and the headless `stats_cli.py` so
    both surfaces show cache tokens identically, once, from one place."""
    cache_read = bucket.get("cache_read_input_tokens", 0)
    cache_write = bucket.get("cache_creation_input_tokens", 0)
    if not cache_read and not cache_write:
        return ""
    return f", {cache_read}cr/{cache_write}cw cache tok"


def compute_session_stats(nodes: list) -> dict:
    """`/stats`: `{turns, total_cost_usd, subscription_turns,
    subscription_cost_usd, per_model: {model: {input_tokens,
    output_tokens, cache_read_input_tokens, cache_creation_input_tokens,
    cost_usd, subscription_cost_usd, subscription_turns, calls}},
    tool_counts: {name: n}}`.

    Halo 2.0.5 round 1 (cc: route v2, brief item H6 "Cost line"): a
    `cc:`-route usage node carries `estimate: true` (`agent/log.py`'s
    `append_usage`) -- its cost routes into `subscription_cost_usd`/
    `subscription_turns` (both session-wide AND per-model) instead of
    `cost_usd`/`total_cost_usd`, so `/stats` never counts Claude Code's
    own cumulative-delta ESTIMATE as if it were real per-token spend."""
    per_model: dict = {}
    tool_counts: dict = {}
    # 2.0.6 round 2 (per-role cost attribution): role -> {calls, tasks,
    # accepted, cost_usd, subscription_cost_usd} -- the session's own
    # nodes, so `/stats` answers "who spent what" without touching disk.
    per_role: dict = {}
    total_cost = 0.0
    subscription_cost = 0.0
    subscription_turns = 0
    turns = 0
    current_model = "?"
    for node in nodes:
        ntype = node.get("type")
        if ntype == "meta" and node.get("model"):
            current_model = node["model"]
        elif ntype == "user":
            # finding 29: count real prompts only -- see _NON_PROMPT_USER_KINDS.
            if node.get("kind") not in _NON_PROMPT_USER_KINDS:
                turns += 1
        elif ntype == "assistant":
            for block in node.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    name = block.get("name", "?")
                    tool_counts[name] = tool_counts.get(name, 0) + 1
        elif ntype == "usage":
            # review finding 84: a sub-agent rollup is charged to the
            # child's own model, not the session's current one.
            usage_model = node["model"] if (node.get("agent_id") and node.get("model")) else current_model
            bucket = per_model.setdefault(usage_model, {
                "input_tokens": 0, "output_tokens": 0,
                # finding 29: a cached Claude route's own `message_start`
                # reports ONLY the uncached portion in `input_tokens` (see
                # agent/loop.py's own H5b finding 4 comment on this exact
                # split) -- omitting these two under-reported a heavily
                # cached session's real input by however much was served
                # from cache.
                "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0,
                "cost_usd": 0.0, "calls": 0,
                "subscription_cost_usd": 0.0, "subscription_turns": 0,
            })
            usage = node.get("usage") or {}
            bucket["input_tokens"] += int(usage.get("input_tokens") or 0)
            bucket["output_tokens"] += int(usage.get("output_tokens") or 0)
            bucket["cache_read_input_tokens"] += int(usage.get("cache_read_input_tokens") or 0)
            bucket["cache_creation_input_tokens"] += int(usage.get("cache_creation_input_tokens") or 0)
            cost = node.get("cost_usd")
            if node.get("estimate"):
                if isinstance(cost, (int, float)):
                    bucket["subscription_cost_usd"] += cost
                    subscription_cost += cost
                bucket["subscription_turns"] += 1
                subscription_turns += 1
            elif isinstance(cost, (int, float)):
                bucket["cost_usd"] += cost
                total_cost += cost
            bucket["calls"] += 1
            # 2.0.6 round 2: the role bucket on the SAME pass -- "main"
            # for the session's own calls (tagged by `_account_usage`/
            # `_log_call_failure` since this round), a sub-agent's
            # resolved role on a rollup node. A rollup node (agent_id
            # set) is one TASK; its `ok` decides accepted.
            role = node.get("role")
            if role:
                rb = per_role.setdefault(role, {"calls": 0, "tasks": 0, "accepted": 0,
                                                "cost_usd": 0.0, "subscription_cost_usd": 0.0})
                rb["calls"] += 1
                if node.get("agent_id"):
                    rb["tasks"] += 1
                    if node.get("ok") is True:
                        rb["accepted"] += 1
                if node.get("estimate"):
                    if isinstance(cost, (int, float)):
                        rb["subscription_cost_usd"] += cost
                elif isinstance(cost, (int, float)):
                    rb["cost_usd"] += cost
    return {"turns": turns, "total_cost_usd": total_cost, "subscription_turns": subscription_turns,
            "subscription_cost_usd": subscription_cost, "per_model": per_model, "tool_counts": tool_counts,
            "per_role": per_role}
