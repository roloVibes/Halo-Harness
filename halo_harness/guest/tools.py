"""halo_harness.guest.tools -- the bridge's MCP side with hand-outs ON (Halo 3.6.0.26 H; `guest.hand_out local`).
With the setting off none of this is imported: the bridge is release 1's (guest/bridge.py `answer`, `mcp_loop`).

Five tools (names as Claude Code shows them: `mcp__plugin_halo-guest_halo-guest__<name>`), each description at most
600 characters, and the server's `instructions` (three lines): WORDS, INSTRUCTIONS. The loop keeps reading while a
job runs (a ping, a `notifications/cancelled`, other calls): each `tools/call` answers from its own thread, every
write goes through one lock. `halo_hand_out` with `wait` answers when the job ends, sending `notifications/progress`
at most once a second while it runs, only when the request carried a progress token; a cancel of that request stops
its job.
"""

from __future__ import annotations

import json
import threading
import time
from typing import Optional

from halo_harness.guest import hand_out as H

INSTRUCTIONS = ("Halo shows this Claude Code session in Studio; the person turned hand-outs on.\n"
                "halo_hand_out gives one bounded task to an agent on one of his own local models; halo_models lists them.\n"
                "A hand-out agent reads at most: it never edits, runs no command and never uses a paid or cloud model.")
WORDS = {
    "halo_models": (
        "Lists the local models this person's Halo may hand a task to: the models on his own Ollama hosts (his machine "
        "or his network; never an account with a key). Each row says only what Halo knows: the trained and verified "
        "window, the measured speed and cold load, whether it calls tools, and the tuner's guide line marked as the "
        "tuner's. What is not known says so. It starts nothing."),
    "halo_hand_out": (
        "Hands one bounded task to an agent Halo runs on one of this person's local models, on his own machine or the "
        "Ollama host he named (never a paid or cloud model). mode none: the agent has no tools and answers from what "
        "you send. mode read_only: it may read and search files in this project folder; it changes nothing and runs "
        "no command. wait (the default): the call answers when the job ends; wait false: a job_id at once. Caps: 12 "
        "turns (up to 40), 10 minutes (up to 60), two jobs at once, one per host."),
    "halo_job": (
        "The state of one hand-out job: running, done, failed or stopped; its model, the step it is on, its turns, "
        "tokens and minutes. It changes nothing."),
    "halo_job_result": (
        "The result of one hand-out job: the agent's answer text (in parts of 20,000 characters: part 2, 3 and on "
        "read the rest), its answer to each acceptance check (or not answered), what it was denied, turns, tokens and "
        "cost. It changes nothing."),
    "halo_job_stop": (
        "Stops one hand-out job: Halo asks the agent to end at its next step, then ends its process. The answer says "
        "whether the stop was asked or the job has already ended."),
}
_JOB = {"type": "object", "properties": {"job_id": {"type": "string", "description": "the job_id halo_hand_out gave"}},
        "required": ["job_id"], "additionalProperties": False}
SCHEMAS = {
    "halo_models": {"type": "object", "properties": {}, "additionalProperties": False},
    "halo_hand_out": {"type": "object", "properties": {
        "goal": {"type": "string", "maxLength": 4000, "description": "the task, in plain words"},
        "acceptance": {"type": "array", "maxItems": 10, "items": {"type": "string", "maxLength": 300},
                       "description": "checks the answer must meet; the agent answers each yes or no"},
        "files": {"type": "array", "maxItems": 50, "items": {"type": "string", "maxLength": 500},
                  "description": "paths in the project folder the task is about (read_only: the agent reads them)"},
        "model": {"type": "string", "description": "a ref from halo_models; left out: Halo's default model when it is local"},
        "mode": {"type": "string", "enum": ["none", "read_only"]},
        "max_turns": {"type": "integer", "minimum": 1, "maximum": H.TURNS_CAP},
        "max_minutes": {"type": "integer", "minimum": 1, "maximum": H.MINUTES_CAP},
        "wait": {"type": "boolean"}},
        "required": ["goal", "mode"], "additionalProperties": False},
    "halo_job": _JOB,
    "halo_job_result": {"type": "object", "properties": {**_JOB["properties"], "part": {"type": "integer", "minimum": 1}},
                        "required": ["job_id"], "additionalProperties": False},
    "halo_job_stop": _JOB,
}
_READ_ONLY = {"halo_models", "halo_job", "halo_job_result"}


def tool_list() -> list:
    return [{"name": n, "description": WORDS[n], "inputSchema": SCHEMAS[n],
             "annotations": {"readOnlyHint": n in _READ_ONLY, "openWorldHint": False}} for n in WORDS]


def _text(obj, error: bool = False) -> dict:
    return {"content": [{"type": "text", "text": obj if isinstance(obj, str) else json.dumps(obj, indent=1)}],
            "isError": error}


class Tools:
    """The tools of one bridge (`bridge` None: sessions open no socket here, so no Studio rows)."""

    def __init__(self, bridge, project, *, claude_pid: int, directory, sid: str = "", state_dir=None) -> None:
        tree = None
        if bridge is not None and bridge.handle is not None:
            from halo_harness.agent.agent_registry import tree_for
            tree = tree_for(bridge.handle.session)
            sid = bridge.handle.session_id
        self.jobs = H.HandOuts(project, sid=sid or f"guest-{claude_pid}", directory=directory, claude_pid=claude_pid,
                               tree=tree, state_dir=state_dir, notify=self._progress)
        if bridge is not None and bridge.handle is not None:
            bridge.handle.hand_outs = self.jobs
            if bridge.handle.feed is not None:
                bridge.handle.feed.on_hand_out = self.jobs.saw_call
        self._wlock = threading.Lock()
        self._wf = None
        self._waiting: dict = {}  # job id -> {"rid", "token", "sent": monotonic}
        self._by_request: dict = {}  # request id (json) -> job id
        self._cancelled: set = set()  # request ids (json) cancelled: no answer is sent for them
        self._calls: set = set()  # request ids (json) of tools/call still running (a cancel may come before the job)
        self._clock = threading.Lock()  # the three above

    # ---- the loop ----------------------------------------------------------------------------------------------------
    def write(self, obj: dict) -> None:
        with self._wlock:
            try:
                self._wf.write((json.dumps(obj) + "\n").encode("utf-8"))
                self._wf.flush()
            except (OSError, ValueError):
                pass

    def loop(self, rf, wf) -> None:
        """Answer until the input closes; a call runs on its own thread."""
        from halo_harness.guest.bridge import answer
        self._wf = wf
        for raw in iter(rf.readline, b""):
            try:
                msg = json.loads(raw.decode("utf-8", "replace"))
            except ValueError:
                continue
            if not isinstance(msg, dict):
                continue
            method = msg.get("method")
            if method == "notifications/cancelled":
                self.cancelled((msg.get("params") or {}).get("requestId"))
                continue
            if method == "tools/call" and "id" in msg:
                with self._clock:
                    self._calls.add(json.dumps(msg["id"]))
                threading.Thread(target=self._call, args=(msg,), daemon=True, name="halo-guest-call").start()
                continue
            reply = answer(msg, hand_outs=True)
            if reply is not None:
                self.write(reply)

    def _call(self, msg: dict) -> None:
        rid = msg["id"]
        params = msg.get("params") if isinstance(msg.get("params"), dict) else {}
        try:
            result = self.call(str(params.get("name") or ""), params.get("arguments") or {}, rid,
                               ((params.get("_meta") or {}) if isinstance(params.get("_meta"), dict) else {}).get("progressToken"))
        except Exception as e:
            result = _text(f"the call failed in Halo: {type(e).__name__}: {e}", True)
        key = json.dumps(rid)
        with self._clock:
            self._calls.discard(key)
            if key in self._cancelled:
                self._cancelled.discard(key)
                return
        self.write({"jsonrpc": "2.0", "id": rid, "result": result})

    # ---- the calls ---------------------------------------------------------------------------------------------------
    def call(self, name: str, args, rid=None, token=None) -> dict:
        args = args if isinstance(args, dict) else {}
        if name == "halo_models":
            return _text(H.models(self.jobs.state_dir))
        if name == "halo_hand_out":
            return self.hand_out(args, rid, token)
        if name in ("halo_job", "halo_job_result", "halo_job_stop"):
            job = self.jobs.get(args.get("job_id"))
            if job is None:
                return _text(f"no hand-out job {str(args.get('job_id') or '')[:64]!r} in this session", True)
            if name == "halo_job":
                return _text(job.brief())
            if name == "halo_job_stop":
                return _text({"job_id": job.id, "said": job.stop("asked (halo_job_stop)"), "state": job.state})
            part = args.get("part")
            return _text(job.packet(part if isinstance(part, int) and not isinstance(part, bool) else 1))
        return _text(f"no tool {name[:64]!r}: the tools are {', '.join(WORDS)}", True)

    def hand_out(self, args: dict, rid, token) -> dict:
        job, why = self.jobs.start(args)
        if job is None:
            return _text(why, True)
        key = json.dumps(rid)
        with self._clock:  # a cancel that came while the job was being checked and started: it stops it now
            self._by_request[key] = job.id
            cancelled = key in self._cancelled
        if cancelled:
            job.stop("the call was cancelled")
        if not job.task["wait"] or cancelled:
            with self._clock:
                self._by_request.pop(key, None)
            return _text({"job_id": job.id, "state": job.state, "model": job.model})
        self._waiting[job.id] = {"rid": rid, "token": token, "sent": 0.0}
        try:
            job.done.wait()
        finally:
            self._waiting.pop(job.id, None)
            with self._clock:
                self._by_request.pop(key, None)
        return _text(job.packet(1))

    def _progress(self, job) -> None:
        w = self._waiting.get(job.id)
        if not w or w.get("token") is None or time.monotonic() - w["sent"] < H.POLL_S:
            return
        w["sent"] = time.monotonic()
        b = job.brief()
        self.write({"jsonrpc": "2.0", "method": "notifications/progress",
                    "params": {"progressToken": w["token"], "progress": job.step,
                               "message": f"{job.model}: {b['step'] or 'thinking'} (turn {b['turns']}, {b['minutes']} min)"}})

    def cancelled(self, rid) -> None:
        """A `notifications/cancelled` for a waiting hand-out stops its job (its call then answers nothing more); one
        for a call whose job is still being checked and started is kept, and stops that job once it exists."""
        key = json.dumps(rid)
        with self._clock:
            job = self.jobs.get(self._by_request.get(key))
            if job is None and key not in self._calls:
                return  # not a call of this bridge's that still runs
            self._cancelled.add(key)
        if job is not None:
            job.stop("the call was cancelled")

    def close(self) -> None:
        self.jobs.close()


def status_of(jobs: Optional["H.HandOuts"]) -> dict:
    """The bridge's `status`: the setting this bridge read and the jobs that run."""
    if jobs is None:
        return {"hand_out": "off", "jobs": []}
    return {"hand_out": "local", "jobs": [j.brief() for j in jobs.running()]}
