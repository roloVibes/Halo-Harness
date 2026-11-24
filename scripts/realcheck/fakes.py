"""scripts/realcheck/fakes.py -- what the steps talk to instead of the world, all on 127.0.0.1 and in this process.

`Provider` is the test suite's own fake OpenAI-dialect upstream (tests/helpers/mock_openai.MockUpstream), reached by
Halo through `BRIDGE_OPENROUTER_BASE_URL` with any `or:` model, answering by what the request says (the markers below),
never by model name, so a sub-agent or a workflow step on another model is answered too:

  RC-ASK                 a one-line answer, ANSWER
  RC-WORK file=P wf=W    a real turn: Read P, then an Agent spawn (RC-SUB), then Workflow W (RC-SUB), then WORK_DONE
  RC-PACK agent=A        an Agent spawn to the agent named A (RC-SUB), then PACK_DONE
  RC-HANG                an Agent spawn whose sub-agent's model call never answers until `release()` (mid-run)
  RC-SLOW                the main model call itself never answers until `release()`
  RC-BASH                a Bash call `SHELL_HOLD` (a job in the background and one in front: the turn holds in the shell)
  RC-BGBASH              a Bash call `SHELL_BACKGROUND` with run_in_background, then ANSWER (the job outlives the turn)
  RC-MAPBUILD            one Builder call: the workflow review (coder, then reviewer) in a box on the new map review-flow,
                         then MAPBUILD_DONE + the sentence the result says to repeat
  RC-MAPASK              MAPASK_DONE
  RC-PERM                a Bash call `PERM_CMD` (a write: the default mode asks permission first), then ANSWER
  RC-AUTOGROUPS          scene 2's five replies (`AUTOGROUPS_REPLIES`: three researchers in one message, coder, reviewer,
                         an Agent and a Task with no task), each child RC-SUBWAIT, then AUTOGROUPS_DONE
  RC-AUTOBUILD           one Builder call `AUTO_BUILD_CHANGES` (the agent checker, the workflow review: no map), then
                         AUTOBUILD_DONE
  RC-AUTOUSE             one Workflow call to review whose step children carry RC-SUBHANG, then AUTOUSE_DONE
  RC-COPYONE / RC-COPYTWO  COPY_ONE / COPY_TWO (copy-drag: two answers, the first one dragged over)
  RC-BROWSER url=U       3.6.0.6 W: Browser open U, click "Press me", screenshot, close, then BROWSER_DONE + the click
                         result's line that holds BROWSER_AFTER (the page's text after the click)
  RC-BROWSERHOLD url=U   Browser open U, then the next model call is held until `release()` (the step ends halo hard)
  RC-LIVESCENE           3.6.0.14 K1 (live-scene): ONE message of five Agent calls, the last a batch of three
                         (`LIVE_CALLS`, `LIVE_REPLY`): seven helpers, then
                         LIVESCENE_DONE. Its children:
  RC-LIVEDONE            SUB_DONE at once
  RC-LIVETOOL            a Bash call `LIVE_SLEEP` (it ends with the session), then SUB_DONE
  RC-LIVETEST            the first to ask: SUB_DONE once `release()` opened the gate; the later ones once `release_late()`
                         opened the second gate (`release()` alone leaves them held)
  RC-LIVEASK             a Bash call `LIVE_ASK_CMD` (a write: the default mode asks him), then SUB_DONE
  RC-LIVELONG            held until `release()`, then one call of `LIVE_TOOL` (the suite's fake MCP server's slow_tool,
                         30 s; the server is `alwaysLoad`, so main's catalog holds the tool and the
                         general-purpose helper is given it), then SUB_DONE once
                         `release_last()` opened the third gate
  RC-SUBWAIT             SUB_DONE after SUBWAIT_S seconds (a fresh wait: `release()` never shortens it)
  RC-SUB / anything else  SUB_DONE / ANSWER

RC-MAPBUILD, RC-MAPASK and the three RC-AUTO markers are read from the current turn's own user nodes only (`_this_turn`): a note Halo puts at a
turn's start, before or after the typed line, and an earlier turn's Builder result never change what they answer.

Every request is kept (`requests`, with its size in bytes). `Ollama` is tests/helpers/mock_ollama_loads.
LoadCountingOllama (its load / unload counters are what step 8 reads). `browser_command(root)` makes the program a
person's browser would be (BROWSER): it writes each URL it is asked to open to a file and exits 0."""
from __future__ import annotations

import json
import os
import re
import stat
import sys
import threading
import time
from pathlib import Path

ANSWER, SUB_DONE, WORK_DONE, PACK_DONE = "RC-ANSWER-42", "RC-SUB-DONE", "RC-WORK-DONE", "RC-PACK-DONE"
SHELL_HOLD, SHELL_BACKGROUND = "sleep 6011 & sleep 6011", "sleep 6012"
MAPBUILD_DONE, MAPASK_DONE = "RC-MAPBUILD-DONE", "RC-MAPASK-DONE"
PERM_CMD = "mkdir rc-perm-dir"  # 3.6.0.2 P6: the step `prompt` answers its permission card from Studio
BUILD_PROMPT = "RC-MAPBUILD: build me a review workflow: a coder then a reviewer"
ASK_PROMPT = "RC-MAPASK: which workflow are you using?"
# the one Builder card RC-MAPBUILD asks for (3.6.0.2 section 11): coder and reviewer are shipped agents, so no agent
# is made; the map review-flow is made by the card itself (R36 gives it its use row), so no map_use is sent
BUILD_CHANGES = [
    {"tool": "workflow_make", "args": {"name": "review", "for": "review", "steps": [
        {"name": "code", "agents": ["coder"]}, {"name": "review", "agents": ["reviewer"]}]}},
    {"tool": "map_box_add", "args": {"map": "review-flow", "kind": "workflow", "ref": "review"}},
    {"tool": "map_line_add", "args": {"map": "review-flow", "from": "main", "to": "review", "when": "always"}},
]
# 3.6.0.5 section 6: scene 2 (auto-groups), scene 4's build on Auto and its "use it now" (auto-ready-lines)
AUTOGROUPS_PROMPT, AUTOGROUPS_DONE = "RC-AUTOGROUPS: five replies", "RC-AUTOGROUPS-DONE"
AUTOBUILD_PROMPT = "RC-AUTOBUILD: build me a review workflow: a coder then a checker"
AUTOBUILD_DONE = "RC-AUTOBUILD-DONE"
AUTOUSE_PROMPT, AUTOUSE_DONE = "RC-AUTOUSE: use it now", "RC-AUTOUSE-DONE"
SUBWAIT_S = 3.0  # each RC-SUBWAIT child answers after this long
# 3.6.0.6 C: copy-drag's two answers (steps_copy.DRAGGED is a run of words of the first)
COPY_ONE, COPY_TWO = "COPYDRAG-ALPHA with some words, then COPYDRAG-OMEGA.", "COPYDRAG-LAST only, the last one."
BROWSER_DONE, BROWSER_AFTER = "RC-BROWSER-DONE", "after the press, realcheck"  # 3.6.0.6 W: steps_browser.py


def _agent(desc: str, agent: str, task: "str | None" = None) -> dict:
    args = {"description": desc, "prompt": "RC-SUBWAIT: " + desc, "subagent_type": agent}
    if task is not None:
        args["task"] = task
    return args


# the five replies, each a list of (tool name, arguments, call id) as `tool_step` takes them; replies 4 and 5 carry no
# task (a call without it still runs, b/batch01 entry 1)
AUTOGROUPS_REPLIES = [
    [("Agent", _agent(f"read report {x}", "researcher", "compare the three reports"), f"call_rc_g1{x.lower()}")
     for x in "ABC"],
    [("Agent", _agent("fix the login bug", "coder", "fix the login bug"), "call_rc_g2")],
    [("Agent", _agent("review the fix", "reviewer", "Fix the login bug."), "call_rc_g3")],
    [("Agent", _agent("summarize the notes", "general-purpose"), "call_rc_g4")],
    [("Task", _agent("list the open bugs", "general-purpose"), "call_rc_g5")],
]
# the one card RC-AUTOBUILD asks for: on Auto the card makes no map and no use row (a/batch05 entry 1)
AUTO_BUILD_CHANGES = [
    {"tool": "agent_make", "args": {"name": "checker", "does": "checks the code against the request"}},
    {"tool": "workflow_make", "args": {"name": "review", "for": "review", "steps": [
        {"name": "code", "agents": ["coder"]}, {"name": "check", "agents": ["checker"]}]}},
]
# RC-AUTOGROUPS: which reply answers how many of this turn's tool results (any other count: the end, never a hang)
_AUTOGROUPS_AT = {0: 0, 3: 1, 4: 2, 5: 3, 6: 4}
# 3.6.0.14 K1 (live-scene, steps_live.py): seven helpers of one message, in start order (the drawing's group order).
# Auto runs four at once (templates/crew/plain/session.yaml `max_parallel: 4`): the writer ends at once, so the reviewer
# starts and asks; the tester and the chart's helper wait queued. Every name is invented.
LIVESCENE_PROMPT, LIVESCENE_DONE = "RC-LIVESCENE: seven helpers", "RC-LIVESCENE-DONE"
LIVE_SERVER = "rc_insert_chart_from_range"  # a long server name: the tool's name is 42 characters (three rows narrow)
LIVE_TOOL = f"mcp__{LIVE_SERVER}__slow_tool"
LIVE_SLEEP, LIVE_ASK_CMD = "sleep 6013", "mkdir rc-live-ask"
LIVE_LONG_S = 30  # the suite's fake MCP server caps slow_tool at 30 s
# The calls of the one message: (the call's agent, its task, [(the child's marker, what it does)]). One child: a lone
# spawn; three: a `batch`, one group. Halo runs at most four Agent calls at once (agent/loop.py's pool, `_cap`) and draws
# a lone helper only once it runs; a batch registers every child first (subagent.py _run_agent_fanout), so a child that
# waits for a slot is drawn queued. Hence: four lone helpers start (the writer ends at once); the batch starts on the
# writer's freed worker, one of its children takes the freed slot and two wait queued. The helpers that run a shell
# command or the MCP tool are general-purpose: on Auto a researcher and a reviewer get read-only tools (no Bash), and
# there is no `tester` card (each seen on the Linux VM).
LIVE_CALLS = [("writer", "write the changelog", [("RC-LIVEDONE", "write the changelog")]),
              ("general-purpose", "survey the TODOs", [("RC-LIVETOOL", "grep the TODOs")]),
              ("general-purpose", "review the money module", [("RC-LIVEASK", "check pay.py")]),
              ("general-purpose", "make the chart", [("RC-LIVELONG", "draw the chart")]),
              ("general-purpose", "run the tests", [("RC-LIVETEST", "run the unit tests"), ("RC-LIVETEST", "run the e2e tests"),
                                                    ("RC-LIVETEST", "run the lint")])]
# every helper in start order: (agent, task, marker, what it does: its member's description)
LIVE_HELPERS = [(agent, task, marker, what) for agent, task, kids in LIVE_CALLS for marker, what in kids]


def _live_call(agent: str, task: str, kids: list) -> dict:
    if len(kids) == 1:
        marker, what = kids[0]
        return {"description": what, "prompt": f"{marker}: {what}", "subagent_type": agent, "task": task}
    return {"description": task, "subagent_type": agent, "task": task,
            "batch": [{"prompt": f"{marker}: {what}", "description": what} for marker, what in kids]}


LIVE_REPLY = [("Agent", _live_call(*call), f"call_rc_live{i}") for i, call in enumerate(LIVE_CALLS, 1)]
# 3.6.0.15 K1 (made-at-once, steps_made.py): main starts the built-in Judge (held at the gate while he picks its model
# in the box's MODEL block), then, after its result, `judge` (the agent that pick made); RC-NOTED is a turn that only
# carries what main is told (N1 / N2). JUDGE_MODEL is the second model the step lists for its own run: the pick is never
# main's own model. RC-SAVED is the same kind of turn with its own words (3.6.0.19): the step asks it after RC-NOTED in
# the same session, and the terminal draws RC-NOTED's answer again when the next prompt is sent, so a second wait for
# the same done word was true before main had asked anything.
MADE_PROMPT, MADE_DONE = "RC-MADE: judge the draft, then again", "RC-MADE-DONE"
NOTED_PROMPT, NOTED_DONE = "RC-NOTED: anything new?", "RC-NOTED-DONE"
SAVED_PROMPT, SAVED_DONE = "RC-SAVED: anything new?", "RC-SAVED-DONE"
JUDGE_MODEL = "mock/realcheck-judge"
MADE_CALLS = [("Agent", {"subagent_type": "Judge", "description": "judge the draft", "prompt": "RC-MADEJ1: judge the draft"},
               "call_rc_made1"),
              ("Agent", {"subagent_type": "judge", "description": "judge it again", "prompt": "RC-MADEJ2: judge it again"},
               "call_rc_made2")]
# a child's tool calls before its answer, in order: an MCP tool is deferred (its schema loads by ToolSearch first, as
# the tool error itself tells a model)
_LIVE_CALLS = {"RC-LIVETOOL": [("Bash", {"command": LIVE_SLEEP, "description": "rc live tool"})],
               "RC-LIVEASK": [("Bash", {"command": LIVE_ASK_CMD, "description": "rc live ask"})],
               "RC-LIVELONG": [(LIVE_TOOL, {"seconds": LIVE_LONG_S})]}


def _text(content) -> str:
    if isinstance(content, str):
        return content
    return " ".join(str(p.get("text") or "") for p in content or [] if isinstance(p, dict))


def _last_user(body: dict) -> str:
    for m in reversed((body or {}).get("messages") or []):
        if isinstance(m, dict) and m.get("role") == "user":
            return _text(m.get("content"))
    return ""


def _this_turn(body: dict) -> "tuple[str, int, str]":
    """(this turn's own user text, the tool results since it began, the last of those results' text). The turn begins
    after the last assistant message that called no tool (the previous turn's answer); its user nodes (the typed line
    and any note Halo put at the turn's start, in either order) are joined with a newline."""
    msgs = [m for m in (body or {}).get("messages") or [] if isinstance(m, dict)]
    start = 0
    for i, m in enumerate(msgs):
        if m.get("role") == "assistant" and not m.get("tool_calls"):
            start = i + 1
    turn = msgs[start:]
    users = [_text(m.get("content")) for m in turn if m.get("role") == "user"]
    first = next((i for i, m in enumerate(turn) if m.get("role") == "user"), len(turn))
    tools = [_text(m.get("content")) for m in turn[first:] if m.get("role") == "tool"]
    return "\n".join(users), len(tools), (tools[-1] if tools else "")


def text_step(text: str) -> list:
    """One streamed assistant message (the chunks tests/helpers/session_rig.text_step makes)."""
    return [{"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
            {"choices": [{"index": 0, "delta": {"content": text}}]},
            {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}]


def tool_step(*calls) -> list:
    """One assistant message calling tools: `calls` = (name, arguments, call id)."""
    tcs = [{"index": i, "id": cid, "type": "function", "function": {"name": n, "arguments": json.dumps(a)}}
           for i, (n, a, cid) in enumerate(calls)]
    return [{"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
            {"choices": [{"index": 0, "delta": {"tool_calls": tcs}}]},
            {"choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}]}]


def _tool_results(body: dict) -> int:
    return sum(1 for m in (body or {}).get("messages") or [] if isinstance(m, dict) and m.get("role") == "tool")


class Provider:
    def __init__(self) -> None:
        from tests.helpers.mock_openai import SCENARIOS, MockUpstream
        self._scenarios = SCENARIOS
        self.mock = MockUpstream()
        self.mock.models_response = {"data": [{"id": "mock/realcheck", "name": "realcheck",
                                               "context_length": 131072, "pricing": {"prompt": "0", "completion": "0"},
                                               "supported_parameters": ["tools"]}]}
        self.gate = threading.Event()
        self.late_gate = threading.Event()  # RC-LIVELATE (release_late)
        self.last_gate = threading.Event()  # RC-LIVELONG's answer after its tool result (release_last)
        self.hung: list = []  # the markers of calls held at the gate
        self.tests_seen = 0  # RC-LIVETEST children asked so far (the first holds at the gate, the later at the late one)
        self._lock = threading.Lock()
        self.calls: list = []  # (marker, size) per POST

    _KEYS = ("realcheck", "model")
    _MISSING = object()

    def start(self) -> "Provider":
        # the mock's scenario table is one dict for the whole process: what these names held before is put back on
        # stop (popping "model" took the mock's own default answer from every later test in the same process)
        self._saved = {k: self._scenarios.get(k, self._MISSING) for k in self._KEYS}
        self._scenarios["realcheck"] = self._answer
        self._scenarios["model"] = self._answer  # any model name that is not mock/<x>
        self.mock.start()
        return self

    @property
    def base_url(self) -> str:
        return self.mock.base_url

    def release(self) -> None:
        self.gate.set()

    def release_late(self) -> None:
        self.late_gate.set()

    def release_last(self) -> None:
        self.last_gate.set()

    def rearm(self) -> None:
        self.gate = threading.Event()
        self.late_gate = threading.Event()
        self.last_gate = threading.Event()
        with self._lock:
            self.hung.clear()
            self.tests_seen = 0

    def with_model(self, model: str):
        """List `model` ("mock/<name>") beside mock/realcheck and play the same script for it; returns the function that
        puts back EXACTLY what it found (the models list and the scenario of that name), for a step's `finally`."""
        name = model.split("/", 1)[1]
        was_models, was_scenario = self.mock.models_response, self._scenarios.get(name, self._MISSING)
        rows = list((was_models or {}).get("data") or [])
        self.mock.models_response = {**(was_models or {}), "data": rows + [{**rows[0], "id": model, "name": name}]}
        self._scenarios[name] = self._answer

        def put_back() -> None:
            self.mock.models_response = was_models
            if self._scenarios.get(name) == self._answer:  # another owner took the name since: theirs now
                if was_scenario is self._MISSING:
                    self._scenarios.pop(name, None)
                else:
                    self._scenarios[name] = was_scenario
        return put_back

    def requests_with(self, marker: str) -> list:
        """The model calls whose user messages say `marker` (the text as typed: no JSON escaping)."""
        out = []
        for r in self.mock.requests:
            msgs = (r.get("body") or {}).get("messages") or [] if r.get("method") == "POST" else []
            if any(isinstance(m, dict) and m.get("role") == "user" and marker in _text(m.get("content")) for m in msgs):
                out.append(r)
        return out

    def size_of(self, req: dict) -> int:
        return len(json.dumps(req.get("body") or {}, ensure_ascii=False).encode("utf-8"))

    def _hold(self, marker: str) -> None:
        with self._lock:
            self.hung.append(marker)
        gate = {"RC-LIVELATE": self.late_gate, "RC-LIVELONG": self.last_gate}.get(marker, self.gate)
        gate.wait(180)

    def _answer(self, h, body) -> None:
        try:
            self._script(h, body)
        except OSError:  # the caller went away (a launch this step killed while its call was held): nothing to say
            pass

    def _script(self, h, body) -> None:
        from tests.helpers.mock_openai import _finish
        last, done = _last_user(body), _tool_results(body)
        with self._lock:
            self.calls.append((last[:40], len(json.dumps(body or {}))))
        turn, done_here, result = _this_turn(body)
        if "RC-COPYONE" in turn or "RC-COPYTWO" in turn:
            return _finish(h, text_step(COPY_ONE if "RC-COPYONE" in turn else COPY_TWO))
        if "RC-MAPASK" in turn:
            return _finish(h, text_step(MAPASK_DONE))
        if "RC-MAPBUILD" in turn:
            if done_here == 0:
                return _finish(h, tool_step(("Builder", {"changes": BUILD_CHANGES}, "call_rc_build")))
            tail = result.split("word for word: ", 1)[1].strip() if "word for word: " in result else ""
            return _finish(h, text_step((MAPBUILD_DONE + " " + tail).strip()))
        if "RC-PERM" in turn:
            if done_here == 0:
                return _finish(h, tool_step(("Bash", {"command": PERM_CMD, "description": "rc perm"}, "call_rc_perm")))
            return _finish(h, text_step(ANSWER))
        m = re.search(r"RC-BROWSER(HOLD)? url=(\S+)", turn)
        if m:
            return self._browser(h, body, m.group(2), bool(m.group(1)), done_here)
        if "RC-AUTOGROUPS" in turn:
            if done_here in _AUTOGROUPS_AT:
                return _finish(h, tool_step(*AUTOGROUPS_REPLIES[_AUTOGROUPS_AT[done_here]]))
            return _finish(h, text_step(AUTOGROUPS_DONE))
        if "RC-MADE:" in turn:
            if done_here < len(MADE_CALLS):
                return _finish(h, tool_step(MADE_CALLS[done_here]))
            return _finish(h, text_step(MADE_DONE))
        if "RC-MADEJ1" in last:
            self._hold("RC-MADEHOLD")  # running while he picks its model; release() lets it answer
            return _finish(h, text_step(SUB_DONE))
        if "RC-MADEJ2" in last:
            return _finish(h, text_step(SUB_DONE))
        if "RC-NOTED:" in turn:
            return _finish(h, text_step(NOTED_DONE))
        if "RC-SAVED:" in turn:
            return _finish(h, text_step(SAVED_DONE))
        if "RC-LIVESCENE" in turn:
            if done_here == 0:
                return _finish(h, tool_step(*LIVE_REPLY))
            return _finish(h, text_step(LIVESCENE_DONE))
        if "RC-LIVE" in last:
            return self._live_child(h, last, done)
        if "RC-AUTOBUILD" in turn:
            if done_here == 0:
                return _finish(h, tool_step(("Builder", {"changes": AUTO_BUILD_CHANGES}, "call_rc_autobuild")))
            return _finish(h, text_step(AUTOBUILD_DONE))
        if "RC-AUTOUSE" in turn:
            if done_here == 0:
                return _finish(h, tool_step(("Workflow", {"name": "review", "task": "RC-SUBHANG: fix the login bug"},
                                             "call_rc_autouse")))
            return _finish(h, text_step(AUTOUSE_DONE))
        if "RC-SUBWAIT" in last:
            threading.Event().wait(SUBWAIT_S)  # a fresh event: the shared gate's release never shortens it
            return _finish(h, text_step(SUB_DONE))
        if "RC-SUBHANG" in last:
            self._hold("RC-SUBHANG")
            return _finish(h, text_step(SUB_DONE))
        if "RC-SUB" in last:
            return _finish(h, text_step(SUB_DONE))
        if "RC-SLOW" in last:
            self._hold("RC-SLOW")
            return _finish(h, text_step(ANSWER))
        for marker, args in (("RC-BGBASH", {"command": SHELL_BACKGROUND, "run_in_background": True}),
                             ("RC-BASH", {"command": SHELL_HOLD})):
            if marker in last:
                if done == 0:
                    return _finish(h, tool_step(("Bash", dict(args, description="rc shell"), "call_rc_shell")))
                return _finish(h, text_step(ANSWER))
        if "RC-HANG" in last:
            if done == 0:
                return _finish(h, tool_step(("Agent", {"description": "rc hang", "prompt": "RC-SUBHANG: wait",
                                                       "subagent_type": "general-purpose"}, "call_rc_hang")))
            return _finish(h, text_step(ANSWER))
        m = re.search(r"RC-PACK agent=(\S+)", last)
        if m:
            if done == 0:
                return _finish(h, tool_step(("Agent", {"description": "rc pack", "subagent_type": m.group(1),
                                                       "prompt": "RC-SUB: review README.md in one line"}, "call_rc_pack")))
            return _finish(h, text_step(PACK_DONE))
        m = re.search(r"RC-WORK file=(\S+) wf=(\S+)", last)
        if m:
            steps = [("Read", {"file_path": m.group(1)}, "call_rc_read"),
                     ("Agent", {"description": "rc sub", "prompt": "RC-SUB: answer in one line",
                                "subagent_type": "general-purpose"}, "call_rc_agent"),
                     ("Workflow", {"name": m.group(2), "task": "RC-SUB: answer in one line"}, "call_rc_wf")]
            if done < len(steps):
                return _finish(h, tool_step(steps[done]))
            return _finish(h, text_step(WORK_DONE))
        return _finish(h, text_step(ANSWER))

    def _live_child(self, h, last: str, done: int) -> None:
        """A helper of RC-LIVESCENE, by its marker (the docstring's table)."""
        from tests.helpers.mock_openai import _finish
        if "RC-LIVELONG" in last and done == 0:
            self._hold("RC-LIVEHOLD")  # running, its first model call held; after release() its tools
        for marker, calls in _LIVE_CALLS.items():
            if marker in last:
                if done < len(calls):
                    tool, args = calls[done]
                    return _finish(h, tool_step((tool, args, f"call_{marker.lower().replace('-', '_')}_{done}")))
                if marker == "RC-LIVELONG":
                    self._hold(marker)
                return _finish(h, text_step(SUB_DONE))
        if "RC-LIVETEST" in last:
            with self._lock:
                self.tests_seen += 1
                first = self.tests_seen == 1
            self._hold("RC-LIVEHOLD" if first else "RC-LIVELATE")
        return _finish(h, text_step(SUB_DONE))

    def _browser(self, h, body, url: str, hold: bool, done_here: int) -> None:
        from tests.helpers.mock_openai import _finish
        steps = [{"action": "open", "url": url}, {"action": "click", "target": "Press me"}, {"action": "screenshot"},
                 {"action": "close"}]
        if hold and done_here >= 1:
            self._hold("RC-BROWSERHOLD")
            return _finish(h, text_step(ANSWER))
        if done_here < len(steps):
            return _finish(h, tool_step(("Browser", steps[done_here], f"call_rc_browser_{done_here}")))
        results = [_text(m.get("content")) for m in (body or {}).get("messages") or []
                   if isinstance(m, dict) and m.get("role") == "tool"]
        line = next((ln for r in results[-len(steps):] for ln in r.splitlines() if BROWSER_AFTER in ln), "")
        return _finish(h, text_step(f"{BROWSER_DONE} {line}".strip()))

    def stop(self) -> None:
        self.release()
        self.release_late()
        self.release_last()
        saved, self._saved = getattr(self, "_saved", {}), {}
        for k in self._KEYS:
            if self._scenarios.get(k) != self._answer:  # another owner took the name since: theirs now
                continue
            was = saved.get(k, self._MISSING)
            if was is self._MISSING:
                self._scenarios.pop(k, None)
            else:
                self._scenarios[k] = was
        try:
            self.mock.stop()
        except Exception:
            pass


def ollama(models: dict):
    """A load-counting fake Ollama on loopback (tests/helpers/mock_ollama_loads.py), started."""
    from tests.helpers.mock_ollama_loads import LoadCountingOllama
    return LoadCountingOllama(models).start()


BROWSER_SCRIPT = """import sys, time
with open({out!r}, "a", encoding="utf-8") as f:
    f.write(repr(time.time()) + " " + " ".join(sys.argv[1:]) + "\\n")
"""


def browser_command(root: Path) -> "tuple[str, Path]":
    """(the BROWSER value, the file the opened URLs land in). A person's browser opens the page; this one writes the
    URL down and exits 0, so Halo knows a browser took it. Windows: an .exe launcher made by distlib (pip's own), since
    a .cmd would split the URL at its '&'."""
    root = Path(root)
    out = root / "browser-opened.txt"
    script = root / "realcheck-browser.py"
    body = BROWSER_SCRIPT.format(out=str(out))
    if sys.platform != "win32":
        script.write_text("#!" + sys.executable + "\n" + body, encoding="utf-8")
        script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP)
        return str(script), out
    from pip._vendor.distlib.scripts import ScriptMaker
    script.write_text("#!python\n" + body, encoding="utf-8")  # distlib puts this Python in the launcher's shebang
    maker =ScriptMaker(str(root), str(root / "bin"), add_launchers=True)
    maker.executable = sys.executable
    made = maker.make(script.name)
    exe = next((p for p in made if p.endswith(".exe")), "")
    if not exe:
        raise RuntimeError(f"no browser launcher made: {made}")
    return exe, out


def opened_urls(out: Path) -> list:
    try:
        return [line.split(" ", 1)[1].strip() for line in out.read_text(encoding="utf-8").splitlines() if " " in line]
    except OSError:
        return []


def wait_opened(out: Path, timeout: float) -> str:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        got = opened_urls(out)
        if got:
            return got[-1]
        time.sleep(0.05)
    return ""


def free_port() -> int:
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def env_without(names_prefixes) -> dict:
    return {k: v for k, v in os.environ.items() if not k.startswith(tuple(names_prefixes))}
