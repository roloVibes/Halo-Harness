"""halo_harness.guest.feed -- the spool's lines (guest/note.py) as rows of the guest's agent tree and frames of its
feed, through the kinds `agent_observe` already reads, so the plan, the objective, the Goal on a card and the Feed
work with no second path (agent/agent_observe.py, agent/agent_hooks.py `spawn_of`).

    SessionStart        main row: role "Claude Code", its model when sent; /clear or a resume: conversation_reset
    UserPromptSubmit    main's turn begins (`started`: the objective rule, running); a `user_message` frame
    PreToolUse          `tool_use_start` + `tool_use_ready` on the row of its `agent_id`, else main's
    PostToolUse(Failure) `tool_result` ok / not ok (a successful TodoWrite becomes `plan`)
    PreToolUse Agent    kept for the next sub-agent of its type (its goal)
    SubagentStart       a child row under main; its goal the kept Agent call's description when the pairing is sure,
                        else GOAL_NOT_KNOWN

The pairing (Claude Code documents no link from an Agent call to the sub-agent it starts, and async hooks land in
any order): a start is sure of its call only when that call is the one open call of its type AND no other call or
start of the type is stamped within SETTLE_NS of it, on either side. A start with no call makes its type unsure:
every call of the type stamped within the window is unsure, and a later one is unsure too while a start still waits
for its call (that call may be the waiting start's own). A call or start of the type that lands within the window of
a sure pairing takes that goal back to GOAL_NOT_KNOWN.
    SubagentStop        the child done, its last words
    TaskCreated / TaskCompleted   a step of that agent's plan added / done
    Notification        a permission or idle prompt: main waits; a `notification` frame
    Stop / StopFailure  main's turn ends: done / failed
    PreCompact          a `compaction` frame

Which lines are taken (`accepts`): a line whose `cwd` is not the bridge's project folder (or a folder inside it)
is dropped and counted; so is one of another `session_id` than the session's, unless it is a SessionStart (a /clear
or a resume gives Claude Code's same process a new id: the plan and the objective are reset). The session's id is
the first line's that names one (a real session's SessionStart lands before the bridge is up and is never written). Lines of one read are ordered by their stamp; a result whose call came
later is paired by `tool_use_id` (its call is drawn from the result's own input, the late call is then skipped).
"""

from __future__ import annotations

import os
import threading
from collections import OrderedDict, deque

from halo_harness import events
from halo_harness.agent.agent_hooks import spawn_of
from halo_harness.agent.agent_observe import LAST_TEXT, plan_of
from halo_harness.agent.agent_registry import MAIN
from halo_harness.agent.agent_transcript import entry_from_event, first_line
from halo_harness.guest import GOAL_NOT_KNOWN, TITLE
from halo_harness.guest.note import AGENT_TOOLS

KEPT_PER_AGENT = 200  # agent_tail's entries of one agent
DONE_IDS = 4096  # the finished tool ids remembered (a late call of one is skipped)
DEFAULT_TYPE = "general-purpose"  # an Agent call that names no subagent_type
SETTLE_NS = 2_000_000_000  # calls and starts of one type stamped this close together cannot be told apart
RECENT_PER_TYPE = 64  # the stamps of one type's calls and starts remembered for the window


def _place(path) -> str:
    return os.path.normcase(os.path.abspath(str(path))) if path else ""


class GuestFeed:
    def __init__(self, tree, hub, session, project) -> None:
        self.tree, self.hub, self.session = tree, hub, session
        self.project = _place(project)
        self.sid = ""  # Claude Code's session id, from the first line that names one
        self.model = None
        self.dropped = 0
        self.ready: dict = {}  # tool_use_id -> (agent, name, input)
        self.finished: "OrderedDict[str, None]" = OrderedDict()
        self.calls: list = []  # Agent calls of main not yet paired: {id, type, goal, spawn, unsure}
        self.orphans: dict = {}  # sub-agent type -> {"n": starts that found no call, "ts": the last one's stamp}
        self.recent: dict = {}  # sub-agent type -> deque of (stamp, call id or agent id) of its calls and starts
        self.sure: dict = {}  # agent id -> {"type", "ts": its start's stamp, "call", "call_ts"}: a goal given as sure
        self.tasks: dict = {}  # agent -> OrderedDict task_id -> step
        self.kept: dict = {}  # agent -> deque of transcript entries (agent_tail)
        self._kept_lock = threading.Lock()  # the spool's thread adds, a socket's thread reads
        self.on_hand_out = None  # 3.6.0.26 H: (agent, cut input, stamp) of a hand-out call's hook line (hand_out.saw_call)

    # ---- which lines ---------------------------------------------------------------------------------------------
    def _here(self, cwd) -> bool:
        place = _place(cwd)
        return bool(place) and (place == self.project or place.startswith(self.project.rstrip(os.sep) + os.sep))

    def accepts(self, d) -> bool:
        if not isinstance(d, dict) or not isinstance(d.get("hook_event_name"), str):
            self.dropped += 1
            return False
        if not self._here(d.get("cwd")):
            self.dropped += 1
            return False
        sid = d.get("session_id") or ""
        if not self.sid:
            self.sid = sid  # a real session's SessionStart is never written (the bridge is not up yet)
        elif sid and sid != self.sid and d["hook_event_name"] != "SessionStart":
            self.dropped += 1
            return False
        return True

    def take(self, lines: list) -> None:
        """One read's lines, in the order of their stamps."""
        for d in sorted((x for x in lines if isinstance(x, dict)), key=lambda x: x.get("ts") or 0):
            if self.accepts(d):
                getattr(self, "_" + d["hook_event_name"], lambda _d: None)(d)

    # ---- helpers ---------------------------------------------------------------------------------------------------
    def publish(self, aid: str, ev) -> None:
        ev.agent_id = None if aid == MAIN else aid
        self.tree.observe(aid, ev)
        entry = entry_from_event(ev)
        if entry is not None:
            self.keep(aid, entry)
        self.hub.publish(ev)

    def keep(self, aid: str, entry: dict) -> None:
        with self._kept_lock:
            self.kept.setdefault(aid, deque(maxlen=KEPT_PER_AGENT)).append(entry)

    def entries(self, aid: str) -> list:
        with self._kept_lock:
            return list(self.kept.get(aid) or ())

    def _agent(self, d) -> str:
        aid = d.get("agent_id") or ""
        if not aid or aid == MAIN:
            return MAIN
        if self.tree.row(aid) is None:  # its start is not here (yet): a child whose goal is not known
            self._child(aid, d.get("agent_type") or "", None)
        return aid

    def _child(self, aid: str, typ: str, call) -> None:
        goal = (call or {}).get("goal") or GOAL_NOT_KNOWN
        spawn = dict(call["spawn"]) if call else spawn_of(self.tree, MAIN, GOAL_NOT_KNOWN)
        if goal == GOAL_NOT_KNOWN:
            spawn["description"] = GOAL_NOT_KNOWN
        self.tree.add(aid, parent=MAIN, name=typ or "sub-agent", role=typ or None, kind="subagent", task=goal,
                      spawn=spawn, state="running", current="thinking")
        self.tree.helper_started(aid)

    def _done(self, tid: str) -> None:
        self.finished[tid] = None
        while len(self.finished) > DONE_IDS:
            self.finished.popitem(last=False)

    # ---- the events ------------------------------------------------------------------------------------------------
    def _SessionStart(self, d) -> None:
        sid = d.get("session_id") or ""
        if self.sid and sid and sid != self.sid:  # a /clear or a resume: another id in the same process
            self.tree.conversation_reset()  # another conversation in the same process: no plan, no objective
            self.tasks.pop(MAIN, None)
        self.sid = sid or self.sid
        self.model = d.get("model") or self.model
        self.tree.update(MAIN, role=TITLE, **({"model": self.model} if self.model else {}))

    def _UserPromptSubmit(self, d) -> None:
        text = d.get("prompt") or ""
        self.tree.turn_begun()
        self.tree.started(MAIN, self.session, text)
        self.publish(MAIN, events.user_message(text))

    def _PreToolUse(self, d) -> None:
        tid, name = str(d.get("tool_use_id") or ""), str(d.get("tool_name") or "?")
        if not tid or tid in self.finished or tid in self.ready:
            return
        aid = self._agent(d)
        given = d.get("tool_input") if isinstance(d.get("tool_input"), dict) else {}
        self.ready[tid] = (aid, name, given)
        if name in AGENT_TOOLS and aid == MAIN:
            self._call(tid, given, int(d.get("ts") or 0))
        if self.on_hand_out is not None and name.endswith("__halo_hand_out"):
            self.on_hand_out(aid, given, int(d.get("ts") or 0))
        self.publish(aid, events.Event("tool_use_start", {"id": tid, "name": name}))
        self.publish(aid, events.Event("tool_use_ready", {"id": tid, "name": name, "input": given}))
        if aid == MAIN and name not in AGENT_TOOLS:
            self.tree.own_tools(1)

    def _call(self, tid: str, given: dict, ts: int) -> None:
        typ = given.get("subagent_type") or DEFAULT_TYPE
        unsure = self._near(typ, ts, tid)
        orphan = self.orphans.get(typ)
        if orphan:  # a start of this type came with no call: this call may be its own, or not
            unsure = True
            if abs(ts - orphan["ts"]) > SETTLE_NS:  # past the window: taken as the waiting start's own (given nobody)
                orphan["n"] -= 1
                if orphan["n"] <= 0:
                    self.orphans.pop(typ, None)
        self._landed(typ, ts, tid)
        goal = given.get("description") or given.get("prompt") or ""
        self.calls.append({"id": tid, "type": typ, "goal": first_line(goal, 120), "ts": ts,
                           "spawn": spawn_of(self.tree, MAIN, goal), "unsure": unsure})

    def _near(self, typ: str, ts: int, *but) -> bool:
        """Another call or start of this type stamped within the window of `ts`, before or after it."""
        return any(abs(ts - t) <= SETTLE_NS for t, key in self.recent.get(typ, ()) if key not in but)

    def _landed(self, typ: str, ts: int, key: str) -> None:
        """A call or start of `typ` landed: a sure pairing of the type within its window is not sure any more."""
        for aid, p in list(self.sure.items()):
            if p["type"] != typ or key in (aid, p["call"]):
                continue
            if abs(ts - p["ts"]) <= SETTLE_NS or abs(ts - p["call_ts"]) <= SETTLE_NS:
                self._take_back(aid)
            elif ts - max(p["ts"], p["call_ts"]) > SETTLE_NS:
                self.sure.pop(aid, None)  # settled: nothing later can take it back
        self.recent.setdefault(typ, deque(maxlen=RECENT_PER_TYPE)).append((ts, key))

    def _take_back(self, aid: str) -> None:
        self.sure.pop(aid, None)
        row = self.tree.row(aid) or {}
        spawn = dict(row.get("spawn") or {})
        spawn["description"] = GOAL_NOT_KNOWN
        self.tree.update(aid, task=GOAL_NOT_KNOWN, spawn=spawn)

    def _result(self, d, ok: bool) -> None:
        tid = str(d.get("tool_use_id") or "")
        if not tid or tid in self.finished:
            return
        if tid not in self.ready:
            self._PreToolUse(d)  # its call is later in the spool (async hooks): drawn from the result's input
        if tid not in self.ready:
            return
        aid, name, given = self.ready.pop(tid)
        self._done(tid)
        text = str(d.get("tool_response") if ok else d.get("error") or "")
        self.publish(aid, events.Event("tool_result", {"id": tid, "name": name, "ok": ok, "is_error": not ok,
                                                        "summary": text[:200], "content": text}))
        if name == "TodoWrite" and ok:
            self._true_counts(aid, given)
        if name in AGENT_TOOLS:
            self.calls = [c for c in self.calls if c["id"] != tid]

    def _true_counts(self, aid: str, given: dict) -> None:
        """The hook cut the list as the row cuts it; the whole list's counts and step numbers are the hook's."""
        count, todos = given.get("todo_count"), given.get("todos")
        row = self.tree.row(aid) or {}
        plan = row.get("plan") or []
        if isinstance(count, dict) and isinstance(todos, list) and len(todos) == len(plan):
            plan = [{**p, "n": t.get("n", p["n"]) if isinstance(t, dict) else p["n"]} for p, t in zip(plan, todos)]
            self.tree.update(aid, plan=plan, plan_count={"all": int(count.get("all") or 0),
                                                         "done": int(count.get("done") or 0)})

    def _PostToolUse(self, d) -> None:
        self._result(d, True)

    def _PostToolUseFailure(self, d) -> None:
        self._result(d, False)

    def _SubagentStart(self, d) -> None:
        aid, typ = d.get("agent_id") or "", d.get("agent_type") or ""
        if not aid or aid == MAIN:
            return
        kind, ts = typ or DEFAULT_TYPE, int(d.get("ts") or 0)
        mine = [c for c in self.calls if c["type"] == kind]
        call = mine[0] if mine else None
        sure = len(mine) == 1 and not call["unsure"] and not self._near(kind, ts, aid, call["id"])
        if not sure:
            for c in mine:  # two of one type at once: none of them is sure of its start any more
                c["unsure"] = True
        self._landed(kind, ts, aid)
        if call is not None:
            self.calls.remove(call)
        else:
            orphan = self.orphans.setdefault(kind, {"n": 0, "ts": ts})
            orphan["n"], orphan["ts"] = orphan["n"] + 1, max(orphan["ts"], ts)
        self._child(aid, typ, call if sure else None)
        if sure:
            self.sure[aid] = {"type": kind, "ts": ts, "call": call["id"], "call_ts": call["ts"]}
        self.publish(aid, events.Event("subagent_start", {"agent_id": aid, "name": typ,
                                                          "description": (self.tree.row(aid) or {}).get("task")}))

    def _SubagentStop(self, d) -> None:
        aid = self._agent(d)
        if aid == MAIN:
            return
        last = str(d.get("last_assistant_message") or "")
        if last:
            self.tree.update(aid, last_text=last[-LAST_TEXT:])
            self.keep(aid, {"kind": "handback", "text": last, "ts": (d.get("ts") or 0) / 1e9})
        self.tree.ended(aid)
        self.hub.publish(events.Event("subagent_end", {"agent_id": aid, "name": d.get("agent_type") or "",
                                                       "is_error": False}, agent_id=aid))

    def _task(self, d, status: str) -> None:
        aid = self._agent(d)
        steps = self.tasks.setdefault(aid, OrderedDict())
        tid = str(d.get("task_id") or "") or f"subject:{d.get('task_subject')}"
        step = steps.setdefault(tid, {"content": str(d.get("task_subject") or "a task"), "status": "pending"})
        step["status"] = status
        plan, count = plan_of(list(steps.values()))
        self.tree.update(aid, plan=plan, plan_count=count)

    def _TaskCreated(self, d) -> None:
        self._task(d, "pending")

    def _TaskCompleted(self, d) -> None:
        self._task(d, "completed")

    def _Notification(self, d) -> None:
        if d.get("notification_type") in ("permission_prompt", "idle_prompt"):
            self.tree.update(MAIN, state="waiting")
        self.publish(MAIN, events.notification(str(d.get("message") or "Claude Code needs you")))

    def _stop(self, d, reason: str) -> None:
        last = str(d.get("last_assistant_message") or "")
        if last:
            self.tree.update(MAIN, last_text=last[-LAST_TEXT:])
            self.keep(MAIN, {"kind": "text", "text": last, "ts": (d.get("ts") or 0) / 1e9})
        self.publish(MAIN, events.turn_done(reason=reason))
        self.tree.turn_done()
        self.tree.ended(MAIN)

    def _Stop(self, d) -> None:
        self._stop(d, "end_turn")

    def _StopFailure(self, d) -> None:
        self._stop(d, "error")

    def _PreCompact(self, d) -> None:
        self.hub.publish(events.compaction(phase="start", trigger=str(d.get("trigger") or "auto")))

    def _SessionEnd(self, d) -> None:
        if (self.tree.row(MAIN) or {}).get("state") in ("running", "waiting"):
            self.tree.ended(MAIN)

    # ---- the session's own state --------------------------------------------------------------------------------
    def busy(self) -> bool:
        return (self.tree.row(MAIN) or {}).get("state") in ("running", "waiting")
