"""tests.test_guest -- 3.6.0.25 G: a Claude Code session in Studio, watch only (halo_harness/guest).

1. the hook (note.py) with each documented event's JSON (the field names of Claude Code's hooks page): the line, the
   cuts; no bridge (no `.on`): nothing written; garbage, a missing folder, a full disk: exit 0, nothing printed; it
   imports only the standard library; the Windows launcher step of its parent pid, fed a process table;
2. the bridge fed a spool of a whole small session: the rows, the plan, the objective, the children's goals, "goal
   not known" for an unsure pairing, lines out of order, a line of another folder dropped and counted;
3. nothing of the Claude login: no file of the package names a login variable or a credential file;
4. `halo guest install` into a scratch folder: the files, valid JSON, this Python's absolute path, the printed
   commands; uninstall removes them; Halo's own plugin reader never starts the bridge nor runs its hooks;
5. the MCP side: no tools, the description, the end at the input's end.
The registry row (its end, the sweep) is in tests/test_remote_registry.py; the socket's "watch only" answers in
tests/test_remote_control_socket.py.
Run: python -m tests.test_guest
"""
from __future__ import annotations

import ast
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
PKG = Path(__file__).resolve().parent.parent / "halo_harness" / "guest"
NOTE = PKG / "note.py"
PID = 424242
CWD = str(Path(tempfile.gettempdir()) / "guest-project")


class _Home:
    """A scratch Halo home (BRIDGE_TEST_HOME), put back exactly as found."""

    def __init__(self):
        self._saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
        os.environ.pop("BRIDGE_STATE_DIR", None)
        self.path = Path(tempfile.mkdtemp(prefix="guest-home-"))
        os.environ["BRIDGE_TEST_HOME"] = str(self.path)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        return False


def _ev(event, **fields):
    return {"session_id": "s-1", "transcript_path": "/x/t.jsonl", "cwd": CWD, "permission_mode": "default",
            "hook_event_name": event, **fields}


def _spool_dir(on=True):
    d = Path(tempfile.mkdtemp(prefix="guest-spool-"))
    from halo_harness.guest import note
    on_path, spool = note.paths(d, PID)
    if on:  # the `.on` names its bridge: this process stands for a running one
        from halo_harness.guest.bridge import _start_mark
        Path(on_path).write_text(json.dumps({"bridge_pid": os.getpid(), "bridge_start": _start_mark(os.getpid())}))
    Path(spool).write_bytes(b"")
    return d, Path(spool)


def _lines(spool: Path) -> list:
    return [json.loads(x) for x in spool.read_text(encoding="utf-8").splitlines() if x.strip()]


@test
def test_the_hook_writes_one_cut_line_per_documented_event(ctx: Ctx):
    from halo_harness.guest import note
    d, spool = _spool_dir()
    big = "x" * 5000
    todos = [{"content": f"step {i} " + "y" * 300, "status": "completed" if i < 3 else "pending", "activeForm": "z"}
             for i in range(40)]
    cases = [
        _ev("SessionStart", source="startup", model="claude-opus-x"),
        _ev("UserPromptSubmit", prompt="p" * 500),
        _ev("PreToolUse", tool_name="Bash", tool_use_id="t1", tool_input={"command": "echo hi\n" + big, "timeout": 5}),
        _ev("PostToolUse", tool_name="Bash", tool_use_id="t1", tool_input={"command": "echo hi"},
            tool_response={"stdout": big}, duration_ms=12),
        _ev("PostToolUseFailure", tool_name="Bash", tool_use_id="t2", tool_input={"command": "false"}, error=big,
            is_interrupt=False),
        _ev("PreToolUse", tool_name="TodoWrite", tool_use_id="t3", tool_input={"todos": todos}),
        _ev("PreToolUse", tool_name="Agent", tool_use_id="t4",
            tool_input={"description": "Find the tests", "prompt": "Look for every test\nof the login", "subagent_type": "Explore"}),
        _ev("SubagentStart", agent_id="a1", agent_type="Explore"),
        _ev("SubagentStop", agent_id="a1", agent_type="Explore", agent_transcript_path="/x/a.jsonl",
            last_assistant_message=big, stop_hook_active=False),
        _ev("TaskCreated", task_id="k1", task_subject="Write the fix", task_description="d"),
        _ev("TaskCompleted", task_id="k1", task_subject="Write the fix"),
        _ev("Notification", message="Claude needs your permission", notification_type="permission_prompt"),
        _ev("Stop", last_assistant_message="done", stop_hook_active=False),
        _ev("StopFailure", error="rate_limit", error_details="slow down"),
        _ev("PreCompact", trigger="auto", custom_instructions=""),
        _ev("SessionEnd", reason="prompt_input_exit"),
    ]
    for c in cases:
        ctx.check(f"{c['hook_event_name']} wrote a line", note.write(json.dumps(c).encode(), d, PID))
    got = _lines(spool)
    ctx.check(f"one line per event, got {len(got)}", len(got) == len(cases))
    ctx.check("every line has its stamp, its event, the session and the folder",
              all(isinstance(g["ts"], int) and g["session_id"] == "s-1" and g["cwd"] == CWD for g in got))
    ctx.check("no line keeps the transcript's path or the permission mode",
              all("transcript_path" not in g and "agent_transcript_path" not in g and "permission_mode" not in g for g in got))
    ctx.check("every line is 8 KB at most", all(len(json.dumps(g).encode()) <= note.LINE_MAX for g in got))
    by = {g["hook_event_name"] + str(i): g for i, g in enumerate(got)}
    ctx.check("the prompt: its first 200 characters", got[1]["prompt"] == "p" * 200)
    tool_in = got[2]["tool_input"]
    ctx.check(f"a tool's input is one line of 300 characters at most: {tool_in}",
              len(json.dumps(tool_in)) <= 300 and "\n" not in json.dumps(tool_in) and tool_in["command"].startswith("echo hi"))
    ctx.check("a tool's response: 2 KB", len(got[3]["tool_response"].encode()) <= 2048 and got[3]["duration_ms"] == 12)
    ctx.check("an error: 2 KB", len(got[4]["error"].encode()) <= 2048 and got[4]["is_interrupt"] is False)
    plan = got[5]["tool_input"]
    ctx.check(f"a TodoWrite list: 30 steps of 160 characters, the true counts, got {plan.get('todo_count')}",
              len(plan["todos"]) == 30 and all(len(t["content"]) <= 160 for t in plan["todos"])
              and plan["todo_count"] == {"all": 40, "done": 3})
    ctx.check(f"an Agent call: its description, type and prompt's first line, got {got[6]['tool_input']}",
              got[6]["tool_input"] == {"description": "Find the tests", "subagent_type": "Explore",
                                       "prompt": "Look for every test"})
    ctx.check("a sub-agent's start: its id and type", got[7]["agent_id"] == "a1" and got[7]["agent_type"] == "Explore")
    ctx.check("a sub-agent's end: its last words cut, no transcript path",
              len(got[8]["last_assistant_message"].encode()) <= 2048)
    ctx.check("the task, notification, stop, compaction and end fields",
              got[9]["task_subject"] == "Write the fix" and got[11]["notification_type"] == "permission_prompt"
              and got[13]["error"] == "rate_limit" and got[14]["trigger"] == "auto" and got[15]["reason"] == "prompt_input_exit")
    ctx.check("nothing of another event name", not note.write(json.dumps(_ev("PermissionRequest")).encode(), d, PID))
    ctx.check(f"{len(by)} lines read back", len(by) == len(cases))


@test
def test_no_bridge_no_line_and_a_full_disk_never_raises(ctx: Ctx):
    from halo_harness.guest import note
    d, spool = _spool_dir(on=False)
    ctx.check("no .on: nothing written", not note.write(json.dumps(_ev("Stop")).encode(), d, PID) and spool.read_bytes() == b"")
    d2, spool2 = _spool_dir()
    spool2.unlink()
    ctx.check("an .on but no spool: nothing written, nothing made",
              not note.write(json.dumps(_ev("Stop")).encode(), d2, PID) and not spool2.exists())
    d3, spool3 = _spool_dir()
    spool3.write_bytes(b"x" * (note.SPOOL_MAX - 10))
    ctx.check("a spool at its 4 MB cap takes no more", not note.write(json.dumps(_ev("Stop")).encode(), d3, PID)
              and spool3.stat().st_size == note.SPOOL_MAX - 10)
    d4, spool4 = _spool_dir()
    spool4.unlink()
    spool4.mkdir()  # the full disk's stand-in: the open or the write fails
    ctx.check("a write that fails returns False and raises nothing", not note.write(json.dumps(_ev("Stop")).encode(), d4, PID))
    ctx.check("garbage: nothing", not note.write(b"\xff{not json", d, PID))


@test
def test_the_hook_writes_nothing_when_the_bridge_of_the_on_is_not_alive(ctx: Ctx):
    """A bridge ended hard (halo update's stop on Windows, a closed console) leaves its `.on`: the hook must not keep
    adding the session's words to a spool nobody reads."""
    from halo_harness.guest import note
    from halo_harness.guest.bridge import _start_mark
    stop = json.dumps(_ev("Stop", last_assistant_message="the words")).encode()
    d, spool = _spool_dir()
    on = Path(note.paths(d, PID)[0])
    gone = subprocess.Popen([sys.executable, "-c", "pass"])
    gone.wait(60)
    on.write_text(json.dumps({"bridge_pid": gone.pid, "bridge_start": "1"}))
    ctx.check("an .on of a bridge that ended: nothing written", not note.write(stop, d, PID) and spool.read_bytes() == b"")
    on.write_text(json.dumps({"bridge_pid": gone.pid}))
    ctx.check("the same with no start mark (the macOS form)", not note.write(stop, d, PID) and spool.read_bytes() == b"")
    if _start_mark(os.getpid()) is not None:
        on.write_text(json.dumps({"bridge_pid": os.getpid(), "bridge_start": "1"}))
        ctx.check("a running pid that began at another time (a pid given to another program): nothing written",
                  not note.write(stop, d, PID) and spool.read_bytes() == b"")
    for text in ("{}", "", "not json"):
        on.write_text(text)
        ctx.check(f"an .on that names no bridge ({text!r}): nothing written", not note.write(stop, d, PID))
    on.write_text(json.dumps({"bridge_pid": os.getpid(), "bridge_start": _start_mark(os.getpid())}))
    ctx.check("the running bridge: the line is written", note.write(stop, d, PID) and len(_lines(spool)) == 1)


@test
def test_the_hook_process_exits_0_and_prints_nothing_whatever_it_is_given(ctx: Ctx):
    d, _spool = _spool_dir()
    runs = [([str(d)], b"garbage \x00\xff"), ([str(d)], json.dumps(_ev("Stop")).encode()), ([], b"{}"),
            ([str(d / "missing")], json.dumps(_ev("Stop")).encode()), ([str(d)], b"")]
    for args, given in runs:
        p = subprocess.run([sys.executable, "-I", str(NOTE), *args], input=given, capture_output=True, timeout=60)
        ctx.check(f"{args} -> exit {p.returncode}, out {p.stdout!r}, err {p.stderr!r}",
                  p.returncode == 0 and p.stdout == b"" and p.stderr == b"")


@test
def test_the_hook_imports_only_the_standard_library(ctx: Ctx):
    tree = ast.parse(NOTE.read_text(encoding="utf-8"))
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            mods.add((node.module or "").split(".")[0])
    std = set(getattr(sys, "stdlib_module_names", ())) or {"json", "os", "sys", "threading", "time", "ctypes"}
    ctx.check(f"only the standard library: {sorted(mods)}", mods and mods <= std)
    src = NOTE.read_text(encoding="utf-8")
    for word in ("print(", "additionalContext", "decision", "exit(2", "sys.exit("):
        ctx.check(f"the hook never says {word!r}", word not in src)


@test
def test_the_launcher_between_claude_code_and_the_hook_is_stepped_over(ctx: Ctx):
    from halo_harness.guest import note
    table = {30: (20, "python.exe"), 20: (10, "node.exe"), 40: (30, "python.exe"), 31: (21, "python3.12.exe"),
             21: (11, "claude.exe"), 50: (60, "cmd.exe"), 60: (70, "node.exe")}
    ctx.check("a launcher: its parent", note.claude_pid(30, table) == 20)
    ctx.check("python3.12.exe is a launcher too", note.claude_pid(31, table) == 21)
    ctx.check("cmd.exe between them", note.claude_pid(50, table) == 60)
    ctx.check("Claude Code itself: kept", note.claude_pid(20, table) == 20)
    ctx.check("at most two steps", note.claude_pid(40, table) == 20)
    ctx.check("a pid not in the table: kept", note.claude_pid(99, table) == 99)
    if os.name != "nt":
        ctx.check("macOS and Linux: the parent", note.claude_pid() == os.getppid())


def _session_lines() -> list:
    """A whole small session, as the hook writes it: a prompt, tools, a TodoWrite, two sub-agents with tools of their
    own, two at once of one type, a failed tool, a line of another folder, a stop. Stamps in order of the list."""
    todos = [{"content": "Read the code", "status": "completed", "activeForm": "Reading"},
             {"content": "Fix the bug", "status": "in_progress", "activeForm": "Fixing the bug"},
             {"content": "Run the tests", "status": "pending", "activeForm": "Running"}]
    raw = [
        _ev("SessionStart", source="startup", model="claude-opus-x"),
        _ev("UserPromptSubmit", prompt="Please fix the login page bug today"),
        _ev("PreToolUse", tool_name="Read", tool_use_id="r1", tool_input={"file_path": "/w/login.py"}),
        _ev("PostToolUse", tool_name="Read", tool_use_id="r1", tool_input={"file_path": "/w/login.py"}, tool_response="ok"),
        _ev("PreToolUse", tool_name="TodoWrite", tool_use_id="w1", tool_input={"todos": todos}),
        _ev("PostToolUse", tool_name="TodoWrite", tool_use_id="w1", tool_input={"todos": todos}, tool_response="ok"),
        _ev("PreToolUse", tool_name="Agent", tool_use_id="g1",
            tool_input={"description": "Find the login tests", "prompt": "Find them", "subagent_type": "Explore"}),
        _ev("SubagentStart", agent_id="a1", agent_type="Explore"),
        _ev("PreToolUse", tool_name="Grep", tool_use_id="q1", tool_input={"pattern": "login"}, agent_id="a1", agent_type="Explore"),
        _ev("PostToolUse", tool_name="Grep", tool_use_id="q1", tool_input={"pattern": "login"}, tool_response="3 files",
            agent_id="a1", agent_type="Explore"),
        _ev("SubagentStop", agent_id="a1", agent_type="Explore", last_assistant_message="Found three test files"),
        _ev("PostToolUse", tool_name="Agent", tool_use_id="g1", tool_input={}, tool_response="Found three"),
        _ev("PreToolUse", tool_name="Agent", tool_use_id="g2", tool_input={"description": "Plan A", "subagent_type": "Plan"}),
        _ev("PreToolUse", tool_name="Agent", tool_use_id="g3", tool_input={"description": "Plan B", "subagent_type": "Plan"}),
        _ev("SubagentStart", agent_id="b1", agent_type="Plan"),
        _ev("SubagentStart", agent_id="b2", agent_type="Plan"),
        _ev("PreToolUse", tool_name="Glob", tool_use_id="q2", tool_input={"pattern": "*.py"}, agent_id="b2", agent_type="Plan"),
        _ev("PreToolUse", tool_name="Bash", tool_use_id="x1", tool_input={"command": "pytest"}),
        _ev("PostToolUseFailure", tool_name="Bash", tool_use_id="x1", tool_input={"command": "pytest"}, error="1 failed"),
        {**_ev("PreToolUse", tool_name="Bash", tool_use_id="o1", tool_input={"command": "rm -rf /"}),
         "cwd": str(Path(tempfile.gettempdir()) / "another-project")},
        {**_ev("PreToolUse", tool_name="Bash", tool_use_id="o2", tool_input={"command": "ls"}), "session_id": "s-other"},
        _ev("Stop", last_assistant_message="The bug is fixed"),
    ]
    from halo_harness.guest import note
    return [json.loads(note.line_of(d, ts=1_000 + i)) for i, d in enumerate(raw)]


def _feed():
    from types import SimpleNamespace
    from halo_harness.agent.agent_registry import tree_for
    from halo_harness.guest.bridge import GuestSession
    from halo_harness.guest.feed import GuestFeed
    from halo_harness.remote.feed import EventHub
    session = GuestSession("guest-1")
    hub = EventHub()
    seen = []
    hub.add_observer(seen.append)
    return GuestFeed(tree_for(session), hub, session, CWD), seen, SimpleNamespace(session=session)


@test
def test_the_bridge_draws_a_whole_small_session(ctx: Ctx):
    feed, seen, _ = _feed()
    lines = _session_lines()
    head, tail = lines[:6], lines[6:]
    feed.take(list(reversed(head)))  # out of order inside one read: ordered by their stamps
    feed.take([tail[3]])  # a1's Grep result, a read before its call and before a1's start (async hooks)
    feed.take(tail[:3] + tail[4:])
    t = feed.tree
    main = t.row("main")
    ctx.check(f"main: role Claude Code, its model, done after the stop; got {main['role']}, {main['model']}, {main['state']}",
              main["role"] == "Claude Code" and main["model"] == "claude-opus-x" and main["state"] == "done")
    ctx.check(f"the objective from the prompt, got {main['objective']!r}", main["objective"] == "Please fix the login page bug today")
    ctx.check(f"the plan from the TodoWrite, got {main['plan_count']}",
              [p["content"] for p in main["plan"] or []] == ["Read the code", "Fix the bug", "Run the tests"]
              and main["plan_count"] == {"all": 3, "done": 1})
    ctx.check("main's last words", main["last_text"] == "The bug is fixed")
    a1 = t.row("a1")
    ctx.check(f"a1: a child of main, its goal the Agent call's description; got {a1}",
              a1["parent"] == "main" and a1["task"] == "Find the login tests" and a1["spawn"]["description"] == "Find the login tests"
              and a1["state"] == "done" and a1["last_text"] == "Found three test files" and a1["name"] == "Explore")
    for aid in ("b1", "b2"):
        row = t.row(aid)
        ctx.check(f"{aid}: two Plan agents at once: goal not known, never the other's; got {row['task']!r}",
                  row["task"] == "goal not known" and row["spawn"]["description"] == "goal not known")
    tails = feed.entries("a1")
    ctx.check(f"a1's own tool is under a1: {[e.get('name') for e in tails]}",
              any(e.get("kind") == "tool_call" and e.get("name") == "Grep" for e in tails))
    ctx.check("b2's own tool is under b2", "Glob" in (t.row("b2")["current"] or ""))
    results = [ev for ev in seen if ev.kind == "tool_result"]
    ctx.check("the failed Bash is a result that is not ok", any(ev.data["id"] == "x1" and ev.data["ok"] is False for ev in results))
    ctx.check("the early result is paired by its id: one call and one result for q1, its late call skipped",
              sum(1 for ev in results if ev.data["id"] == "q1") == 1
              and sum(1 for ev in seen if ev.kind == "tool_use_start" and ev.data["id"] == "q1") == 1)
    ctx.check("a1 counted once as main's helper", (main["turn"] or {}).get("helpers") == 3)
    ctx.check(f"the other folder's line and the other session's are dropped and counted, got {feed.dropped}",
              feed.dropped == 2 and not any(ev.data.get("id") in ("o1", "o2") for ev in seen if ev.kind == "tool_use_start"))
    ctx.check("a user_message frame for the prompt", any(ev.kind == "user_message" for ev in seen))
    ctx.check("main's turn: one tool of its own counted per own call", (main["turn"] or {}).get("tools") == 3)


@test
def test_a_late_call_never_gives_its_goal_to_the_next_agent(ctx: Ctx):
    from halo_harness.guest import note
    feed, _seen, _ = _feed()
    mk = lambda i, d: json.loads(note.line_of(d, ts=i))  # noqa: E731
    feed.take([mk(1, _ev("SubagentStart", agent_id="c1", agent_type="Explore"))])
    feed.take([mk(0, _ev("PreToolUse", tool_name="Agent", tool_use_id="g9",
                         tool_input={"description": "Goal of c1", "subagent_type": "Explore"}))])
    feed.take([mk(3, _ev("SubagentStart", agent_id="c2", agent_type="Explore"))])
    ctx.check("c1: its call came late: goal not known", feed.tree.row("c1")["task"] == "goal not known")
    ctx.check("c2: never c1's goal", feed.tree.row("c2")["task"] == "goal not known")


def _landing(feed, seq, t0=10**12):
    """Feed `seq` [(ms after t0, line)] one line per read, in that order (each async hook lands on its own)."""
    from halo_harness.guest import note
    for ms, d in seq:
        feed.take([json.loads(note.line_of(d, ts=t0 + ms * 1_000_000))])


def _agent_call(tid, goal, typ):
    return _ev("PreToolUse", tool_name="Agent", tool_use_id=tid, tool_input={"description": goal, "subagent_type": typ})


@test
def test_a_start_before_its_call_then_two_calls_never_gives_c2_the_goal_of_c1(ctx: Ctx):
    """The check's case A: c1's start lands before its call, a second call g10 lands, then c1's own late call g9."""
    for gap in (1, 1500):  # inside the settle window, and the late call past it
        feed, _seen, _ = _feed()
        _landing(feed, [(0, _ev("SubagentStart", agent_id="c1", agent_type="Explore")),
                        (gap, _agent_call("g10", "Goal of c2", "Explore")),
                        (2 * gap, _agent_call("g9", "Goal of c1", "Explore")),
                        (2 * gap + 1, _ev("SubagentStart", agent_id="c2", agent_type="Explore"))])
        got = (feed.tree.row("c1")["task"], feed.tree.row("c2")["task"])
        ctx.check(f"{gap} ms apart: c1 and c2 goal not known, never c1's goal on c2; got {got}",
                  got == ("goal not known", "goal not known") and feed.tree.row("c2")["spawn"]["description"] == "goal not known")


@test
def test_two_plan_calls_of_one_message_landing_interleaved_are_not_sure(ctx: Ctx):
    """The check's case B: call g2, start b1, call g3, start b2: b1 may be g3's agent."""
    feed, _seen, _ = _feed()
    _landing(feed, [(0, _agent_call("g2", "Plan A", "Plan")), (1, _ev("SubagentStart", agent_id="b1", agent_type="Plan")),
                    (2, _agent_call("g3", "Plan B", "Plan")), (3, _ev("SubagentStart", agent_id="b2", agent_type="Plan"))])
    got = (feed.tree.row("b1")["task"], feed.tree.row("b2")["task"])
    ctx.check(f"b1 and b2: goal not known (b1's goal taken back when g3 landed), got {got}",
              got == ("goal not known", "goal not known") and feed.tree.row("b1")["spawn"]["description"] == "goal not known")
    _landing(feed, [(10_000, _agent_call("g4", "Plan C", "Plan")), (10_001, _ev("SubagentStart", agent_id="b3", agent_type="Plan")),
                    (20_000, _agent_call("g5", "Plan D", "Plan"))])
    ctx.check(f"a lone call and its start, nothing of the type near: sure, and a call ten seconds later leaves it; got "
              f"{feed.tree.row('b3')['task']!r}", feed.tree.row("b3")["task"] == "Plan C")


@test
def test_task_events_feed_the_plan_and_a_clear_resets_it(ctx: Ctx):
    from halo_harness.guest import note
    feed, _seen, _ = _feed()
    mk = lambda i, d: json.loads(note.line_of(d, ts=i))  # noqa: E731
    feed.take([mk(0, _ev("SessionStart", source="startup")), mk(1, _ev("UserPromptSubmit", prompt="Make the page load faster now")),
               mk(2, _ev("TaskCreated", task_id="k1", task_subject="Measure")),
               mk(3, _ev("TaskCreated", task_id="k2", task_subject="Cache it")),
               mk(4, _ev("TaskCompleted", task_id="k1", task_subject="Measure"))])
    main = feed.tree.row("main")
    ctx.check(f"the Task events are the plan, got {main['plan']}",
              [(p["content"], p["status"]) for p in main["plan"]] == [("Measure", "completed"), ("Cache it", "pending")]
              and main["plan_count"] == {"all": 2, "done": 1})
    feed.take([{**mk(5, _ev("SessionStart", source="clear")), "session_id": "s-2"}])
    main = feed.tree.row("main")
    ctx.check("a /clear (a new session id): no plan, no objective", main["plan"] is None and main["objective"] is None)
    ctx.check("the new id is the session's now", feed.sid == "s-2")


@test
def test_with_no_start_line_the_first_line_gives_the_id_and_a_clear_still_resets(ctx: Ctx):
    """A real session's SessionStart lands before the bridge is up and is never written."""
    from halo_harness.guest import note
    feed, _seen, _ = _feed()
    mk = lambda i, d: json.loads(note.line_of(d, ts=i))  # noqa: E731
    feed.take([mk(1, _ev("UserPromptSubmit", prompt="Make the page load faster now")),
               mk(2, _ev("TaskCreated", task_id="k1", task_subject="Measure")),
               mk(3, _ev("TaskCreated", task_id="k2", task_subject="Cache it"))])
    ctx.check(f"the first line's id is the session's, got {feed.sid!r}", feed.sid == "s-1")
    before = feed.dropped
    feed.take([{**mk(4, _ev("PreToolUse", tool_use_id="o1", tool_name="Bash", tool_input={"command": "ls"})),
                "session_id": "s-OTHER"}])
    ctx.check(f"a line of another id is dropped and counted (dropped {before} -> {feed.dropped})",
              feed.dropped == before + 1 and "o1" not in feed.ready)
    feed.take([{**mk(5, _ev("SessionStart", source="clear")), "session_id": "s-2"}])
    main = feed.tree.row("main")
    ctx.check(f"a /clear: no plan, no objective, got {main['plan']} / {main['objective']!r}",
              main["plan"] is None and main["objective"] is None and feed.sid == "s-2")
    feed.take([mk(6, _ev("TaskCreated", task_id="k3", task_subject="Old one"))])
    ctx.check("a line of the old id after the /clear is dropped", feed.tree.row("main")["plan"] is None)


@test
def test_no_file_of_the_package_names_the_claude_login(ctx: Ctx):
    words = ("ANTHROPIC", "CLAUDE_CODE_OAUTH", "OAUTH_TOKEN", "API_KEY", "credentials", ".credentials.json",
             "claude_auth", "claude_config_dir", "keychain", "apiKeyHelper")
    for path in sorted(PKG.rglob("*.py")):
        src = path.read_text(encoding="utf-8")
        for w in words:
            ctx.check(f"{path.name} never names {w!r}", w.lower() not in src.lower())


@test
def test_install_writes_the_plugin_and_prints_the_commands_uninstall_removes_it(ctx: Ctx):
    import contextlib
    with _Home() as home:
        from halo_harness.guest import install
        root = home.path / "plugin-here"
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = install.cmd_install(["--to", str(root)])
        text = out.getvalue()
        plugin = root / "halo-guest"
        made = {p: json.loads(p.read_text(encoding="utf-8")) for p in
                (root / ".claude-plugin" / "marketplace.json", plugin / ".claude-plugin" / "plugin.json",
                 plugin / "hooks" / "hooks.json", plugin / ".mcp.json")}
        ctx.check("exit 0 and the files are valid JSON", code == 0 and len(made) == 4)
        manifest = made[plugin / ".claude-plugin" / "plugin.json"]
        ctx.check(f"the manifest: halo-guest, defaultEnabled false: {manifest}",
                  manifest["name"] == "halo-guest" and manifest["defaultEnabled"] is False)
        py = os.path.abspath(sys.executable)  # never resolved: a venv's bin/python is a link to the base interpreter
        hooks = made[plugin / "hooks" / "hooks.json"]["hooks"]
        from halo_harness.guest.note import EVENTS
        ctx.check(f"a hook for each of the {len(EVENTS)} events", sorted(hooks) == sorted(EVENTS))
        every = [h for groups in hooks.values() for g in groups for h in g["hooks"]]
        ctx.check("each an async exec-form command of this Python's absolute path running the plugin's note.py",
                  all(h["type"] == "command" and h["async"] is True and h["command"] == py and Path(h["command"]).is_absolute()
                      and h["args"][:2] == ["-I", "${CLAUDE_PLUGIN_ROOT}/note.py"] for h in every))
        server = made[plugin / ".mcp.json"]["mcpServers"]["halo-guest"]
        ctx.check(f"the MCP entry: this Python, the bridge: {server}",
                  server["command"] == py and server["args"][:3] == ["-m", "halo_harness.guest", "serve"]
                  and server["env"]["BRIDGE_TEST_HOME"] == str(home.path))
        ctx.check("the plugin carries its copy of note.py", (plugin / "note.py").read_bytes() == NOTE.read_bytes())
        for cmd in ("claude plugin marketplace add", "claude plugin install halo-guest@halo-local", "claude plugin enable halo-guest"):
            ctx.check(f"printed: {cmd}", cmd in text)
        ctx.check("it says Halo runs none of them", "Halo runs no command of Claude Code's" in text)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            install.cmd_uninstall(["--to", str(root)])
        ctx.check("uninstall removes the folder", not root.exists())
        ctx.check("and prints the commands that remove the plugin",
                  "claude plugin uninstall halo-guest@halo-local" in out.getvalue())


def _linked_python(where: Path):
    """This interpreter reached through a link (a venv's bin/python is one on Linux and macOS): a symlink, or on
    Windows a junction to its folder. None when the system makes neither."""
    exe = Path(os.path.abspath(sys.executable))
    try:
        os.symlink(exe, where / exe.name)
        return where / exe.name, None
    except (OSError, NotImplementedError, AttributeError):
        pass
    try:
        import _winapi
        _winapi.CreateJunction(str(exe.parent), str(where / "j"))
        return where / "j" / exe.name, where / "j"
    except (ImportError, OSError, AttributeError):
        return None, None


@test
def test_the_plugin_names_this_halos_python_as_it_was_started_never_the_link_resolved(ctx: Ctx):
    """The check: resolving a venv's (or a uv tool's) python loses the venv, and the bridge then imports no Halo or
    another one. The plugin names the interpreter by the path it runs under, a link kept as a link."""
    from halo_harness.guest import install
    where = Path(tempfile.mkdtemp(prefix="guest-py-"))
    linked, junction = _linked_python(where)
    if linked is None:
        ctx.check("this system makes no link (nothing to tell apart)", True)
        return
    real = sys.executable
    try:
        sys.executable = str(linked)
        with _Home() as home:
            made = install.files(home.path / "p")
        hooks = next(v for k, v in made.items() if Path(k).name == "hooks.json")["hooks"]
        mcp = next(v for k, v in made.items() if Path(k).name == ".mcp.json")["mcpServers"]["halo-guest"]
        cmds = {h["command"] for groups in hooks.values() for g in groups for h in g["hooks"]} | {mcp["command"]}
        ctx.check(f"every command is the link's own path {linked}, got {cmds}", cmds == {str(linked)})
    finally:
        sys.executable = real
        if junction is not None:
            os.rmdir(junction)  # the junction only, never what it points at
        else:
            os.unlink(linked)
        os.rmdir(where)


@test
def test_halo_never_starts_the_bridge_nor_runs_its_hooks_in_its_own_sessions(ctx: Ctx):
    with _Home() as home:
        from halo_harness.guest import install
        root = install.install(home.path / "p")
        from halo_harness.config import plugins
        resolved, notices = {}, []
        plugins._discover_one_plugin_root_mcp_servers("halo-guest", root / "halo-guest", env={}, resolved=resolved,
                                                     notices=notices)
        ctx.check(f"Halo's plugin reader skips the bridge, got {sorted(resolved)}", resolved == {})
        other = home.path / "other-plugin"
        (other / "hooks").mkdir(parents=True)
        (other / "hooks" / "hooks.json").write_text(json.dumps({"hooks": {"Notification": [
            {"hooks": [{"type": "command", "command": "true"}]}]}}), encoding="utf-8")
        from halo_harness import headless
        saved = plugins.load_installed_plugins, plugins._plugin_roots
        plugins.load_installed_plugins = lambda *a, **kw: {"version": 2, "plugins": {}}
        plugins._plugin_roots = lambda *a, **kw: [("halo-guest", root / "halo-guest"), ("other", other)]
        try:
            runner = headless.build_hook_runner(settings=None, cwd=home.path, session_id="s", transcript_path="",
                                                effort=None, permission_mode="default", mcp_manager=None, bare=False)
        finally:
            plugins.load_installed_plugins, plugins._plugin_roots = saved
        from halo_harness.guest.note import EVENTS
        ctx.check(f"Halo's hook loader read the other plugin's hooks, got {sorted(runner.hooks_by_event)}",
                  runner.has_hooks("Notification"))
        ctx.check("and loaded none of halo-guest's", not any(runner.has_hooks(e) for e in EVENTS if e != "Notification")
                  and len(runner.hooks_by_event.get("Notification") or []) == 1)


@test
def test_a_guest_row_is_never_offered_to_a_transport_nor_to_the_lan_voice_door(ctx: Ctx):
    """The check: ext.remote (the seam a pack carries Halo to a phone or a chat through) listed and connected to a
    guest row, and its socket serves subscribe and agent_tail: a Claude Code session's words could leave the machine."""
    import socket
    from halo_harness.ext import remote
    from halo_harness.peers import local_view
    from halo_harness.remote import registry
    from halo_harness.voice import turn
    lst = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    lst.bind(("127.0.0.1", 0))
    lst.listen(8)
    ep = f"tcp:127.0.0.1:{lst.getsockname()[1]}"
    rows = [{"session_id": "h-1", "title": "my own work", "cwd": CWD, "pid": os.getpid(), "endpoint": ep, "kind": "tui",
             "started": 1.0},
            {"session_id": "g-1", "title": "Claude Code", "cwd": CWD, "pid": os.getpid(), "endpoint": ep, "kind": "guest",
             "started": 2.0},
            # 3.6.0.26 H, after the review (finding 6): a hand-out worker carries the goal Claude Code sent
            {"session_id": "w-1", "title": "Claude Code hand-out", "cwd": CWD, "pid": os.getpid(), "endpoint": ep,
             "kind": "print", "parent": "guest:g-1", "started": 3.0}]
    real = registry.list_live
    with _Home() as home:
        try:
            registry.list_live = lambda *a, **kw: [dict(r) for r in rows]
            local_view.forget()
            ctx.check(f"sessions(): the Halo session only, got {[r['session_id'] for r in remote.sessions()]}",
                      [r["session_id"] for r in remote.sessions()] == ["h-1"])
            ctx.check("connect() to the guest: None", remote.connect("g-1", timeout=1) is None)
            ctx.check("connect() to its hand-out worker: None", remote.connect("w-1", timeout=1) is None)
            text = "\n".join(remote.live_lines())
            ctx.check(f"live_lines(): one live session, the guest not named: {text!r}",
                      "1 live session(s)" in text and "Claude Code" not in text and "my own work" in text)
            (home.path / "run").mkdir(parents=True, exist_ok=True)
            (home.path / "run" / "sessions.json").write_text(json.dumps({"sessions": rows}), encoding="utf-8")
            got = [r["session_id"] for r in turn.sessions(home.path)]
            ctx.check(f"halo host's voice door lists the Halo session only, got {got}", got == ["h-1"])
        finally:
            registry.list_live = real
            local_view.forget()
            lst.close()


@test
def test_a_guest_row_keeps_nothing_halo_started_running(ctx: Ctx):
    """The check: the home watch (closing_home_watch.halos_alive) and a model server's 'another Halo still runs'
    counted Claude Code's bridge as a Halo, so a server Halo started outlived the last Halo session."""
    from halo_harness import closing_home_watch as W
    from halo_harness.providers import local_server
    from halo_harness.remote import registry
    with _Home() as home:
        (home.path / "run").mkdir(parents=True, exist_ok=True)
        import time
        row = {"session_id": "g-1", "pid": os.getppid(), "kind": "guest", "started": time.time(), "endpoint": "tcp:127.0.0.1:9"}
        (home.path / "run" / "sessions.json").write_text(json.dumps({"sessions": [row]}), encoding="utf-8")
        ctx.check("the home watch: a guest row alone is no Halo alive",
                  W.halos_alive(str(home.path), (0, "")) is False)
        (home.path / "run" / "sessions.json").write_text(json.dumps({"sessions": [{**row, "kind": "tui"}]}), encoding="utf-8")
        ctx.check("a Halo session's row still is", W.halos_alive(str(home.path), (0, "")) is True)
        real = registry.list_live
        try:
            registry.list_live = lambda *a, **kw: [{**row, "pid": os.getppid()}]
            ctx.check("a model server: a guest row is no other Halo", local_server._others_alive(home.path) is False)
            registry.list_live = lambda *a, **kw: [{**row, "pid": os.getppid(), "kind": "tui"}]
            ctx.check("a Halo session's row is", local_server._others_alive(home.path) is True)
        finally:
            registry.list_live = real


@test
def test_the_mcp_side_offers_no_tools_and_ends_at_the_inputs_end(ctx: Ctx):
    from halo_harness.guest import bridge
    msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "x"}},
            {"jsonrpc": "2.0", "id": 4, "method": "ping"}]
    rf = io.BytesIO(b"".join((json.dumps(m) + "\n").encode() for m in msgs) + b"not json\n")
    wf = io.BytesIO()
    bridge.mcp_loop(rf, wf)
    got = [json.loads(x) for x in wf.getvalue().decode().splitlines()]
    ctx.check(f"four answers (no answer to a notification), got {len(got)}", [g["id"] for g in got] == [1, 2, 3, 4])
    info = got[0]["result"]
    ctx.check(f"the description: {info['serverInfo']}", info["serverInfo"]["description"] == "Halo: shows this session in Studio (watch only)"
              and "instructions" not in info)
    ctx.check("no tools", got[1]["result"] == {"tools": []})
    ctx.check("a call answers watch only", got[2]["error"]["message"].startswith("watch only"))


# ---- 3.6.0.26 H: hand-outs (a bounded task handed to an agent on the person's own local model) -----------------------
REPO = Path(__file__).resolve().parent.parent
GONE_S = 45.0  # a worker's pid is gone this long after its bridge (slow Windows runners: the polite stop is 10 s)


class _Env:
    """os.environ entries set for a test and put back exactly as found."""

    def __init__(self, **values):
        self.values = values
        self.saved = {k: os.environ.get(k) for k in values}

    def __enter__(self):
        for k, v in self.values.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        return self

    def __exit__(self, *exc):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        return False


def _write_config(home: Path, **cfg) -> None:
    d = home / ".halo"
    d.mkdir(parents=True, exist_ok=True)
    (d / "config.json").write_text(json.dumps(cfg), encoding="utf-8")


def _mock(*steps, model="qwen3:30b"):
    from tests.helpers.mock_ollama import MockUpstream
    from tests.helpers.ollama_turns import _Script
    return MockUpstream(scenarios={model: _Script(list(steps))}).start()


def _said(text: str) -> list:
    from tests.helpers.ollama_turns import _done
    return _done(text)


def _tool(name: str, **args) -> list:
    return [{"message": {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": name, "arguments": args}}]},
             "done": True, "done_reason": "stop", "prompt_eval_count": "real", "eval_count": 6}]  # "real": the mock counts


def _slow(stop, seconds: float, text: str = "late"):
    """A chat step that holds its answer `seconds` (or until the test ends: `stop` set)."""
    from tests.helpers.mock_ollama import _finish_chat

    def step(handler, _body):
        stop.wait(seconds)
        _finish_chat(handler, _said(text))
    return step


def _bridge_env(home: Path, mock_url: str) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("HALO_") or k == "HALO_TEST_NO_PROC"}
    env.pop("BRIDGE_STATE_DIR", None)
    env.update({"BRIDGE_TEST_HOME": str(home), "OLLAMA_HOST": mock_url, "HALO_NO_UPDATER": "1",
                "BRIDGE_TEST_NO_BACKGROUND_NET": "1", "PYTHONPATH": str(REPO), "PYTHONIOENCODING": "utf-8"})
    return env


class _Mcp:
    """The test as Claude Code: the bridge (`python -m halo_harness.guest serve`) as its child, newline JSON-RPC on
    its input, every message it writes kept in order."""

    def __init__(self, home: Path, project: Path, mock_url: str, *, flags: int = 0):
        import queue
        import threading
        self.log = home / "bridge.log"
        self.q, self.got = queue.Queue(), []
        kw = {"creationflags": flags} if flags else {}
        with open(self.log, "ab") as err:
            self.proc = subprocess.Popen([sys.executable, "-m", "halo_harness.guest", "serve", "--project", str(project)],
                                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err, cwd=str(REPO),
                                         env=_bridge_env(home, mock_url), **kw)
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for raw in iter(self.proc.stdout.readline, b""):
            try:
                self.q.put(json.loads(raw.decode("utf-8")))
            except ValueError:
                self.q.put({"not_json": raw[:200].decode("utf-8", "replace")})

    def send(self, obj: dict) -> None:
        self.proc.stdin.write((json.dumps(obj) + "\n").encode("utf-8"))
        self.proc.stdin.flush()

    def ask(self, rid, method: str, params=None) -> None:
        self.send({"jsonrpc": "2.0", "id": rid, "method": method, **({"params": params} if params is not None else {})})

    def wait(self, pred, seconds: float):
        import queue
        import time
        end = time.monotonic() + seconds
        for m in self.got:
            if pred(m):
                return m
        while time.monotonic() < end:
            try:
                m = self.q.get(timeout=0.2)
            except queue.Empty:
                continue
            self.got.append(m)
            if pred(m):
                return m
        return None

    def reply(self, rid, seconds: float = 120.0):
        return self.wait(lambda m: m.get("id") == rid and ("result" in m or "error" in m), seconds)

    def call(self, rid, name: str, seconds: float = 120.0, meta=None, **args):
        self.ask(rid, "tools/call", {"name": name, "arguments": args, **({"_meta": meta} if meta else {})})
        r = self.reply(rid, seconds)
        if not r or "result" not in r:
            return None, r
        res = r["result"]
        text = res["content"][0]["text"]
        try:
            return json.loads(text), res
        except ValueError:
            return text, res

    def end(self) -> None:
        try:
            if self.proc.poll() is None:
                self.proc.kill()
            self.proc.wait(30)
        except Exception:
            pass


def _workers() -> list:
    from halo_harness import children
    try:
        rows = json.loads(children.registry_path().read_text(encoding="utf-8")).get("children") or []
    except (OSError, ValueError):
        return []
    return [r for r in rows if r.get("what") == "guest-worker"]


def _wait_worker(seconds: float = 60.0) -> "dict | None":
    import time
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        rows = _workers()
        if rows:
            return rows[0]
        time.sleep(0.2)
    return None


def _alive(row: dict) -> bool:
    from halo_harness import children
    return children.same_process(row["pid"], row.get("start_time"))


def _gone(row: dict, seconds: float) -> bool:
    import time
    end = time.monotonic() + seconds
    while time.monotonic() < end and _alive(row):
        time.sleep(0.2)
    return not _alive(row)


def _end_pid(row: "dict | None") -> None:
    """Ends a worker the test's bridge started, by its pid and start time, if a failed check left it."""
    if row and _alive(row):
        from halo_harness.children_stop import terminate
        terminate(row["pid"], timeout=5.0, recorded=row.get("start_time"))


def _job_files(home: Path) -> list:
    d = home / ".halo" / "run" / "guest"
    return sorted(d.glob("*.job.*.json")) if d.is_dir() else []


def _hand_outs(home: Path, project: Path, tree=None):
    from halo_harness.guest.hand_out import HandOuts
    d = home / ".halo" / "run" / "guest"
    d.mkdir(parents=True, exist_ok=True)
    return HandOuts(project, sid="guest-test", directory=d, claude_pid=PID, tree=tree, state_dir=home / ".halo")


@test
def test_hand_outs_off_the_bridge_is_release_1s_and_installs_nothing(ctx: Ctx):
    """With the setting off (and with an unknown value): no tools, a call refused, closing.install never called; with
    it on, install runs before the bridge opens anything."""
    import contextlib
    from halo_harness import closing
    from halo_harness.guest import bridge
    seen = []
    real_install, real_start = closing.install, bridge.GuestBridge.start
    msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "halo_hand_out", "arguments": {}}}]
    for value in (None, "off", "local+paid"):
        with _Home() as home, _Env(OLLAMA_HOST="http://127.0.0.1:9"):
            _write_config(home.path, **({"guest": {"hand_out": value}} if value else {}))
            stdin = type("In", (), {"buffer": io.BytesIO(b"".join((json.dumps(m) + "\n").encode() for m in msgs))})()
            out = io.BytesIO()
            stdout = type("Out", (), {"buffer": out, "write": lambda *_a: None, "flush": lambda *_a: None})()
            saved = sys.stdin, sys.stdout
            try:
                closing.install = lambda *a, **kw: seen.append(("install", value))
                bridge.GuestBridge.start = lambda self: seen.append(("start", value)) and None
                sys.stdin, sys.stdout = stdin, stdout
                with contextlib.redirect_stderr(io.StringIO()):
                    bridge.serve(["--project", str(home.path)])
            finally:
                sys.stdin, sys.stdout = saved
                closing.install, bridge.GuestBridge.start = real_install, real_start
            got = [json.loads(x) for x in out.getvalue().decode().splitlines()]
            ctx.check(f"{value}: no tools, the call refused watch only, no instructions; got {got}",
                      got[1]["result"] == {"tools": []} and got[2]["error"]["message"].startswith("watch only")
                      and "instructions" not in got[0]["result"])
    ctx.check(f"off: closing.install never called, got {seen}", not any(s[0] == "install" for s in seen))
    with _Home() as home, _Env(OLLAMA_HOST="http://127.0.0.1:9"):
        _write_config(home.path, guest={"hand_out": "local"})
        stdin = type("In", (), {"buffer": io.BytesIO(b"")})()
        stdout = type("Out", (), {"buffer": io.BytesIO(), "write": lambda *_a: None, "flush": lambda *_a: None})()
        saved, order = (sys.stdin, sys.stdout), []
        try:
            closing.install = lambda *a, **kw: order.append("install")
            bridge.GuestBridge.start = lambda self: order.append("bridge") and None
            sys.stdin, sys.stdout = stdin, stdout
            with contextlib.redirect_stderr(io.StringIO()):
                bridge.serve(["--project", str(home.path)])
        finally:
            sys.stdin, sys.stdout = saved
            closing.install, bridge.GuestBridge.start = real_install, real_start
        ctx.check(f"local: closing.install first, then the bridge; got {order}", order == ["install", "bridge"])


@test
def test_the_setting_reads_off_for_any_other_value_and_doctor_says_so(ctx: Ctx):
    from halo_harness.guest import hand_out as H
    with _Home() as home:
        for raw, want in ((None, "off"), ("off", "off"), ("local", "local"), ("LOCAL ", "local"), ("local+paid", "off"),
                          (True, "off")):
            _write_config(home.path, **({"guest": {"hand_out": raw}} if raw is not None else {}))
            ctx.check(f"{raw!r} reads {want}", H.setting()[0] == want)
        _write_config(home.path, guest={"hand_out": "local+paid"})
        from halo_harness.guest import install
        line = install.doctor_line()
        ctx.check(f"doctor names the value it does not read, got {line!r}",
                  "hand-outs: off (guest.hand_out is 'local+paid': only off or local are read)" in line)
        _write_config(home.path, guest={"hand_out": "local"})
        ctx.check("and says local when on", "hand-outs: local" in install.doctor_line())


@test
def test_a_client_revision_this_server_does_not_implement_is_answered_with_its_newest(ctx: Ctx):
    """Never an echo of a revision this server does not implement, hand-outs on or off; a revision it implements is
    answered as asked (as release 1 answered it)."""
    from halo_harness.guest import bridge
    init = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2026-07-28"}}
    got = bridge.answer(init, hand_outs=True)
    ctx.check(f"on, an unknown revision: the newest implemented, got {got['result']['protocolVersion']}",
              got["result"]["protocolVersion"] == bridge.REVISIONS[-1] != "2026-07-28")
    got = bridge.answer({**init, "params": {"protocolVersion": "2025-06-18"}}, hand_outs=True)
    ctx.check("on, a known one is kept", got["result"]["protocolVersion"] == "2025-06-18")
    got = bridge.answer(init)
    ctx.check(f"off, an unknown revision: the newest implemented too, got {got['result']['protocolVersion']}",
              got["result"]["protocolVersion"] == bridge.REVISIONS[-1])
    got = bridge.answer({**init, "params": {"protocolVersion": "2025-06-18"}})
    ctx.check("off, a known one is kept (release 1's answer)", got["result"]["protocolVersion"] == "2025-06-18")


@test
def test_the_tools_words_and_the_instructions_are_short_and_plain(ctx: Ctx):
    from halo_harness.guest import bridge, tools
    names = [t["name"] for t in tools.tool_list()]
    ctx.check(f"five tools, got {names}", names == ["halo_models", "halo_hand_out", "halo_job", "halo_job_result", "halo_job_stop"])
    for t in tools.tool_list():
        ctx.check(f"{t['name']}: at most 600 characters ({len(t['description'])})", len(t["description"]) <= 600)
        ctx.check(f"{t['name']}: never 'always use'", "always use" not in t["description"].lower())
    hand = next(t for t in tools.tool_list() if t["name"] == "halo_hand_out")
    ctx.check("halo_hand_out says where it runs and what the agent may do",
              "own machine" in hand["description"] and "read_only" in hand["description"] and "no tools" in hand["description"])
    ctx.check(f"no edits mode is offered: {hand['inputSchema']['properties']['mode']}",
              hand["inputSchema"]["properties"]["mode"]["enum"] == ["none", "read_only"])
    lines = tools.INSTRUCTIONS.splitlines()
    ctx.check(f"the instructions: three lines at most, they say he turned it on: {lines}",
              len(lines) <= 3 and "turned hand-outs on" in tools.INSTRUCTIONS and "always use" not in tools.INSTRUCTIONS.lower())
    got = bridge.answer({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}, hand_outs=True)
    ctx.check("on: initialize carries the instructions", got["result"]["instructions"] == tools.INSTRUCTIONS)


@test
def test_the_frame_a_worker_is_sent_is_pinned(ctx: Ctx):
    from halo_harness.guest.hand_out import frame
    want = ("Halo hands you one task from a Claude Code session. Do only this task, then answer in plain text.\n"
            "You may read and search files in the project folder; you change nothing and run no command.\n"
            "\nThe task:\nFind where the session id is set\n"
            "\nFiles the task is about:\n- halo_harness/guest/feed.py\n"
            "\nChecks your answer must meet:\n1. names the function\n"
            "\nEnd your answer with one line of JSON that answers each check, in order, like this:\n"
            '{"acceptance": [{"n": 1, "met": "yes", "why": "one short line"}]}\n')
    got = frame("Find where the session id is set", ["names the function"], ["halo_harness/guest/feed.py"], "read_only")
    ctx.check(f"read_only, with files and a check: the frame word for word, got {got!r}", got == want)
    bare = frame("Say hello", [], [], "none")
    ctx.check(f"none, nothing else: two lines and the task, got {bare!r}",
              bare == "Halo hands you one task from a Claude Code session. Do only this task, then answer in plain text.\n"
                      "You have no tools: answer from what is written here.\n\nThe task:\nSay hello\n")


@test
def test_acceptance_answers_only_in_the_asked_shape_else_not_answered(ctx: Ctx):
    from halo_harness.guest.hand_out import answers
    checks = ["names the file", "says the line"]
    good = 'It is in feed.py.\n{"acceptance": [{"n": 1, "met": "yes", "why": "feed.py"}, {"n": 2, "met": "no", "why": "not sure"}]}'
    ctx.check("the asked shape: each answer", [a["answer"] for a in answers(good, checks)] == ["yes: feed.py", "no: not sure"])
    for bad in ("It is in feed.py.", '{"acceptance": [{"n": 1, "met": "yes"}]}', '{"acceptance": "yes"}',
                '{"acceptance": [{"met": "maybe"}, {"met": "yes"}]}', "{not json"):
        ctx.check(f"not the shape ({bad[:30]!r}): every check not answered",
                  [a["answer"] for a in answers(bad, checks)] == ["not answered", "not answered"])


@test
def test_only_his_own_local_models_are_allowed_and_a_refusal_starts_nothing(ctx: Ctx):
    with _Home() as home, _Env(OLLAMA_HOST="http://127.0.0.1:9"):
        mock = _mock(_said("hello"))
        try:
            _write_config(home.path, ollama={"hosts": [{"name": "mine", "url": mock.base_url, "default": True},
                                                        {"name": "cloud-box", "url": mock.base_url, "api_key": "k-example"}]})
            from halo_harness.guest import hand_out as H
            rows = H.models(home.path / ".halo")["models"]
            refs = sorted(r["ref"] for r in rows)
            ctx.check(f"halo_models: the keyless host's models only, got {refs}",
                      refs == ["ol:gpt-oss:20b@mine", "ol:qwen3:30b@mine"])
            q = next(r for r in rows if r["ref"] == "ol:qwen3:30b@mine")
            ctx.check(f"what Halo knows, nothing invented: {q}",
                      q["trained_window"] == 40960 and q["tool_calling"] == "yes" and q["tok_s"] == "not known"
                      and q["cold_load_s"] == "not known" and "tuner_guide" not in q)
            ctx.check("halo_models says nothing of hf: (Ollama hosts only)", "hf:" not in json.dumps(H.models(home.path / ".halo")))
            jobs = _hand_outs(home.path, home.path)
            for model in ("ol:qwen3:30b@cloud-box", "or:vendor/model", "ant:opus", "dbx:databricks-gpt-5-mini",
                          "claude-opus-4-5", "sonnet", "--tools=Bash", "hf:local/qwen3", "hf:mlx/org/qwen3",
                          "oai:gpt-x", "local:qwen3"):
                job, why = jobs.start({"goal": "say hi", "mode": "none", "model": model})
                ctx.check(f"{model}: refused with the allowed ones named (Ollama only), got {why!r}",
                          job is None and "allowed: ol:<model>" in why and "hf:" not in why.split("allowed:", 1)[1])
            cfg = json.loads((home.path / ".halo" / "config.json").read_text(encoding="utf-8"))
            cfg["ollama"]["hosts"].append({"name": "pub", "url": "https://ollama.example.com"})
            _write_config(home.path, **cfg)
            job, why = jobs.start({"goal": "say hi", "mode": "none", "model": "ol:qwen3:30b@pub"})
            ctx.check(f"a keyless entry on a public address is not his machine: refused, got {why!r}",
                      job is None and "is not local" in why)
            ctx.check("and not listed", not any(r["host"] == "pub" for r in H.models(home.path / ".halo")["models"]))
            with _Env(OLLAMA_HOST="https://ollama.example.com"):
                _write_config(home.path)
                ref, _h, why = H.choose("ol:qwen3:30b", home.path / ".halo")
                ctx.check(f"the default host on a public address: refused, got {why!r}", not ref and "is not local" in why)
            _write_config(home.path, **cfg)
            job, why = jobs.start({"goal": "say hi", "mode": "edits", "model": "ol:qwen3:30b@mine"})
            ctx.check(f"mode edits is refused, got {why!r}", job is None and why.startswith("mode is none"))
            ctx.check("nothing was started: no job, no worker in the ledger, no chat sent",
                      not jobs.jobs and not _workers() and not any(r.get("path") == "/api/chat" for r in mock.requests))
            _write_config(home.path, model="ant:opus", ollama={"hosts": [{"name": "mine", "url": mock.base_url}]})
            job, why = jobs.start({"goal": "say hi", "mode": "none"})
            ctx.check(f"no model given and a cloud default: refused, got {why!r}",
                      job is None and why.startswith("no model given and Halo's default model ant:opus is not local"))
            _write_config(home.path, model="ol:nope:1b@mine", ollama={"hosts": [{"name": "mine", "url": mock.base_url}]})
            job, why = jobs.start({"goal": "say hi", "mode": "none"})
            ctx.check(f"the default is local but not on the host: said before a start, got {why!r}",
                      job is None and why.startswith("nope:1b is not on mine"))
            _write_config(home.path, ollama={"hosts": [{"name": "mine", "url": "http://127.0.0.1:9"}]})
            job, why = jobs.start({"goal": "say hi", "mode": "none", "model": "ol:qwen3:30b@mine"})
            ctx.check(f"the host does not answer: said before a start, got {why!r}",
                      job is None and why.startswith("the Ollama host mine does not answer") and not _workers())
        finally:
            mock.stop()


@test
def test_a_third_job_and_a_second_on_one_host_are_refused_with_one_line(ctx: Ctx):
    import threading
    from types import SimpleNamespace
    with _Home() as home, _Env(OLLAMA_HOST="http://127.0.0.1:9"):
        mock = _mock(_said("hello"))
        try:
            _write_config(home.path, ollama={"hosts": [{"name": "mine", "url": mock.base_url, "default": True},
                                                        {"name": "gpu-box", "url": mock.base_url}]})
            jobs = _hand_outs(home.path, home.path)
            busy = SimpleNamespace(done=threading.Event(), key="ollama:mine")
            jobs.jobs["a"] = busy
            job, why = jobs.start({"goal": "x", "mode": "none", "model": "ol:qwen3:30b@mine"})
            ctx.check(f"one job per host, got {why!r}", job is None and why == "a hand-out runs on mine now: one job per host at a time")
            jobs.jobs["b"] = SimpleNamespace(done=threading.Event(), key="ollama:gpu-box")
            job, why = jobs.start({"goal": "x", "mode": "none", "model": "ol:qwen3:30b@gpu-box"})
            ctx.check(f"a third job: refused, no queue; got {why!r}",
                      job is None and why.startswith("2 hand-outs run now: wait for one to end"))
            ctx.check("nothing started", not _workers())
        finally:
            mock.stop()


def _run_job(home: Path, args: dict, *steps, seconds: float = 120.0, setup=None, quiet_net: bool = True):
    """One hand-out run in THIS process (the worker a real `halo -p` child of the test) against the mock."""
    mock = _mock(*steps)
    jobs = job = None
    try:
        _write_config(home, ollama={"hosts": [{"name": "mine", "url": mock.base_url, "default": True}]})
        project = home / "proj"
        project.mkdir(exist_ok=True)
        (project / "a.txt").write_text("alpha\n", encoding="utf-8")
        with _Env(OLLAMA_HOST=mock.base_url, HALO_NO_UPDATER="1", BRIDGE_TEST_NO_BACKGROUND_NET="1" if quiet_net else None,
                  PYTHONPATH=str(REPO)):
            jobs = _hand_outs(home, project)
            if setup:
                setup(jobs)
            job, why = jobs.start({"model": "ol:qwen3:30b@mine", **args})
            if job is None:
                return None, why, mock
            job.done.wait(seconds)
        return job, "", mock
    finally:
        if job is not None and not job.done.is_set():
            job.end_hard()
        mock.stop()


@test
def test_a_hand_out_in_none_returns_the_packet(ctx: Ctx):
    with _Home() as home:
        text = 'The answer is 42.\n{"acceptance": [{"n": 1, "met": "yes", "why": "it says 42"}]}'
        job, why, mock = _run_job(home.path, {"goal": "What is six times seven?", "mode": "none",
                                              "acceptance": ["gives a number"]}, _said(text))
        ctx.check(f"started ({why})", job is not None and job.done.is_set())
        p = job.packet()
        ctx.check(f"done, the text whole, the check answered: {p}",
                  p["state"] == "done" and p["summary"] == text and p["parts"] == 1
                  and p["acceptance"] == [{"check": "gives a number", "answer": "yes: it says 42"}])
        ctx.check(f"tokens as counted, the cost in Halo's words, no invented figure: {p['usage']}, {p['cost']}",
                  p["cost"] == "free (local)" and p["num_turns"] >= 1 and isinstance(p["usage"], dict))
        chat = [r for r in mock.requests if r.get("path") == "/api/chat"]
        body = chat[0].get("body") or {}
        ctx.check("none: the worker was given no tools", not body.get("tools"))
        users = [m for m in body.get("messages") or [] if m.get("role") == "user"]
        ctx.check("the frame went as the user's prompt", users and "Halo hands you one task" in str(users[-1].get("content")))
        ctx.check("the worker is gone from the ledger and its file is kept while the bridge lives",
                  not _workers() and len(_job_files(home.path)) == 1)


@test
def test_read_only_denies_a_write_and_an_ask_and_a_check_not_followed_reads_not_answered(ctx: Ctx):
    """read_only's tools are Read, Grep and Glob: a Write is no tool of its (never run); an ask (a read outside the
    project folder) is a recorded denial, never a hang."""
    with _Home() as home:
        outside = home.path / "elsewhere.txt"
        outside.write_text("OUTSIDE-TEXT-31\n", encoding="utf-8")
        job, why, mock = _run_job(home.path, {"goal": "Change a.txt", "mode": "read_only", "acceptance": ["a.txt changed"]},
                                  _tool("Write", file_path="a.txt", content="beta"),
                                  _tool("Read", file_path=str(outside)), _said("I could not change it."))
        ctx.check(f"started ({why})", job is not None and job.done.is_set())
        p = job.packet()
        denied = [str(d.get("tool_name") or d.get("tool") or d) for d in p["permission_denials"]]
        ctx.check(f"the ask (a read outside the project) is a recorded denial, never a hang: {p['permission_denials']}",
                  any("Read" in d for d in denied))
        sent = json.dumps([r.get("body") for r in mock.requests if r.get("path") == "/api/chat"])
        ctx.check("the write was never run (no tool of read_only's) and the outside text never reached the model",
                  "Unknown tool" in sent and "OUTSIDE-TEXT-31" not in sent)
        ctx.check("a.txt is unchanged", (home.path / "proj" / "a.txt").read_text(encoding="utf-8") == "alpha\n")
        ctx.check(f"the check not answered, the text still returned: {p['acceptance']}, {p['summary']!r}",
                  p["acceptance"] == [{"check": "a.txt changed", "answer": "not answered"}]
                  and "could not change" in p["summary"] and p["state"] == "done")


@test
def test_read_only_runs_no_command_reads_no_login_and_writes_nothing_under_claude(ctx: Ctx):
    """The check's probe: in read_only a `cat` of a file outside the project (a Claude login file) is never run, the
    worker is offered Read, Grep and Glob only (no Bash, Agent, Workflow, web), and plan mode's plan file goes to the
    job's own folder, removed with the job: the scratch home's ~/.claude is exactly as it was."""
    with _Home() as home:
        cred = home.path / ".claude" / ".credentials.json"
        cred.parent.mkdir(parents=True)
        cred.write_text('{"claudeAiOauth": {"accessToken": "FAKE-LOGIN-TOKEN-7"}}', encoding="utf-8")
        before = sorted(str(p.relative_to(home.path)) for p in (home.path / ".claude").rglob("*"))
        job, why, mock = _run_job(home.path, {"goal": "Look around", "mode": "read_only"},
                                  _tool("Bash", command=f"cat {cred.as_posix()}"), _said("I did not read it."))
        ctx.check(f"started ({why})", job is not None and job.done.is_set())
        chats = [r for r in mock.requests if r.get("path") == "/api/chat"]
        offered = {(t.get("function") or {}).get("name") for t in ((chats[0].get("body") or {}).get("tools") or [])} \
            if chats else set()
        ctx.check(f"only Read, Grep and Glob are offered, got {sorted(offered)}", offered == {"Read", "Grep", "Glob"})
        ctx.check("the login file's text never reached the model",
                  chats and not any("FAKE-LOGIN-TOKEN-7" in json.dumps(r.get("body")) for r in chats))
        ctx.check("plan mode's note names the job's own folder", any(".plans" in json.dumps(r.get("body")) for r in chats))
        after = sorted(str(p.relative_to(home.path)) for p in (home.path / ".claude").rglob("*"))
        ctx.check(f"~/.claude unchanged: {before} -> {after}", before == after)
        left = list((home.path / ".halo" / "run" / "guest").glob("*.plans"))
        ctx.check(f"the job's plan folder went with the job, left {left}", not left)
        p = job.packet()
        ctx.check(f"the packet says done with the text: {p['state']}, {p['summary']!r}",
                  p["state"] == "done" and "did not read" in p["summary"])


def _files(root: Path) -> dict:
    return {str(p.relative_to(root)).replace("\\", "/"): p for p in root.rglob("*") if p.is_file()}


def _seal(home: Path, project: Path, outside: Path, marks: Path) -> None:
    """The person's own settings, as full as they get: Claude Code's user settings and the project's, each with
    command hooks that write a marker, allow rules, an added folder outside the project, an `env` block with a
    token; his CLAUDE.md and the project's. A sealed worker takes in none of it."""
    py = Path(sys.executable).as_posix()

    def hook(name):
        code = f"open(r'{(marks / name).as_posix()}', 'w').write('ran')"
        return [{"hooks": [{"type": "command", "command": f'"{py}" -c "{code}"'}]}]
    events = ("SessionStart", "UserPromptSubmit", "PreToolUse", "Stop", "SessionEnd")
    cc = home / ".claude"
    cc.mkdir(exist_ok=True)
    (cc / "settings.json").write_text(json.dumps({
        "env": {"ANTHROPIC_AUTH_TOKEN": "TOK-FROM-SETTINGS-77", "OLLAMA_API_KEY": "TOK-FROM-SETTINGS-78"},
        "permissions": {"allow": ["Read", "Glob", "Grep"], "additionalDirectories": [str(outside)],
                        "defaultMode": "bypassPermissions"},
        "hooks": {e: hook(f"user-{e}") for e in events}}), encoding="utf-8")
    (cc / "CLAUDE.md").write_text("USER-RULE-TEXT-6\n", encoding="utf-8")
    (cc / ".claude.json").write_text(json.dumps({"projects": {str(project): {"hasTrustDialogAccepted": True},
                                                              project.as_posix(): {"hasTrustDialogAccepted": True}}}))
    (project / ".claude").mkdir(exist_ok=True)
    (project / ".claude" / "settings.json").write_text(json.dumps({
        "permissions": {"allow": ["Read"]}, "hooks": {e: hook(f"project-{e}") for e in events}}), encoding="utf-8")
    (project / "CLAUDE.md").write_text("PROJECT-RULE-TEXT-5\n", encoding="utf-8")


@test
def test_a_worker_is_a_sealed_run_in_each_mode(ctx: Ctx):
    """After the review (findings 1-4): no settings file of the person's, of Claude Code's or of the project changes
    what a worker may do -- no hook of any source runs, no allow rule or added folder lets a read outside the project
    through (it is a recorded denial, a Glob with `..` too), no `env` token reaches a request, no instruction file
    goes to the model -- and nothing of the worker is kept: no transcript, no history entry, nothing new under
    ~/.claude; while the bridge lives only its job file holds the job's words, after its close nothing does."""
    for mode in ("none", "read_only"):
        with _Home() as home:
            h = home.path
            outside, marks = h / "elsewhere", h / "marks"
            outside.mkdir()
            marks.mkdir()
            (outside / "s.txt").write_text("OUTSIDE-TEXT-31\n", encoding="utf-8")
            (outside / "listed-name-42.txt").write_text("x\n", encoding="utf-8")
            seen = {}

            def setup(jobs):
                _seal(h, jobs.project, outside, marks)
                seen["jobs"], seen["before"] = jobs, set(_files(h))
            steps = [_said("SEALED-ANSWER-8")] if mode == "none" else [
                _tool("Read", file_path=str(outside / "s.txt")), _tool("Glob", pattern="../elsewhere/*"),
                _said("SEALED-ANSWER-8")]
            with _Env(CLAUDE_CONFIG_DIR=str(h / ".claude")):
                job, why, mock = _run_job(h, {"goal": "SEALED-GOAL-9", "mode": mode}, *steps, setup=setup)
            ctx.check(f"{mode}: started and done ({why})", job is not None and job.packet()["state"] == "done")
            ctx.check(f"{mode}: no hook of any source ran, got {sorted(os.listdir(marks))}", os.listdir(marks) == [])
            sent = json.dumps(mock.requests)
            ctx.check(f"{mode}: no settings token in any request the mock saw", "TOK-FROM-SETTINGS" not in sent)
            ctx.check(f"{mode}: no instruction file of his or of the project went to the model",
                      "USER-RULE-TEXT-6" not in sent and "PROJECT-RULE-TEXT-5" not in sent and "SEALED-GOAL-9" in sent)
            if mode == "read_only":
                denied = sorted(str(d.get("tool_name")) for d in job.packet()["permission_denials"])
                ctx.check(f"read_only: the allowed and added outside read and the `..` Glob are recorded denials, "
                          f"got {denied}", denied == ["Glob", "Read"])
                ctx.check("read_only: nothing outside reached the model (no text, no file name)",
                          "OUTSIDE-TEXT-31" not in sent and "listed-name-42" not in sent)
            new = {k: p for k, p in _files(h).items() if k not in seen["before"]}
            ctx.check(f"{mode}: no transcript, no history entry, nothing under ~/.claude: "
                      f"{sorted(k for k in new if k.startswith(('.halo/sessions', '.claude')))}",
                      not any(k.startswith((".halo/sessions", ".claude")) for k in new))
            words = lambda p: any(w in p.read_bytes() for w in (b"SEALED-GOAL-9", b"SEALED-ANSWER-8"))  # noqa: E731
            holders = sorted(k for k, p in new.items() if words(p))
            ctx.check(f"{mode}: while the bridge lives only its job file holds the job's words, got {holders}",
                      len(holders) == 1 and ".job." in holders[0] and holders[0].endswith(".json"))
            seen["jobs"].close()
            after = {k: p for k, p in _files(h).items() if k not in seen["before"]}
            ctx.check(f"{mode}: after the bridge's close nothing holds them, got {sorted(k for k, p in after.items() if words(p))}",
                      not any(words(p) for p in after.values()))
            ctx.check(f"{mode}: and nothing of the job is left in the run folder",
                      not [n for n in os.listdir(h / ".halo" / "run" / "guest") if ".job." in n])


@test
def test_a_worker_calls_only_his_own_local_models_whatever_his_roles_say(ctx: Ctx):
    """After the review (finding 5): `roles.small`, `roles.judge` and `routing.escalation` pointed at a paid account
    behind a loopback gateway (a local router in front of a paid API) -- `--offline` lets loopback through, so only
    the worker mark holds: that gateway is never hit, and the hand-out still answers."""
    gateway = _mock(_said("PAID-ANSWER"), _said("PAID-ANSWER"), _said("PAID-ANSWER"), model="paid-x")
    try:
        with _Home() as home:
            def setup(_jobs):
                cfg = json.loads((home.path / ".halo" / "config.json").read_text(encoding="utf-8"))
                paid = "local:paid-x@gw"
                cfg.update({"local": {"servers": {"gw": {"base_url": f"{gateway.base_url}/v1", "api_key": "paid-key"}}},
                            "roles": {"small": paid, "judge": paid},
                            "routing": {"escalation": {"to": paid, "when": ["low_confidence", "tool_failures"], "ask": False}}})
                _write_config(home.path, **cfg)
            with _Env(HALO_MODEL_SMALL="local:paid-x@gw"):
                job, why, mock = _run_job(home.path, {"goal": "Say hi", "mode": "none"}, _said("hi there"),
                                          _said("yes"), _said("yes"), setup=setup)
            ctx.check(f"started ({why})", job is not None)
            p = job.packet()
            ctx.check(f"the hand-out still answers: {p['state']}, {p['summary']!r}",
                      p["state"] == "done" and "hi there" in p["summary"])
            ctx.check(f"the gateway was never hit, got {[r.get('path') for r in gateway.requests]}", not gateway.requests)
    finally:
        gateway.stop()


@test
def test_the_sweep_removes_a_dead_bridges_plan_folder(ctx: Ctx):
    from halo_harness.guest import bridge
    with _Home() as home:
        d = home.path / ".halo" / "run" / "guest"
        plans = d / f"{PID}.job.{'a' * 32}.plans"
        plans.mkdir(parents=True)
        (plans / "ridge-cedar-bright.md").write_text("", encoding="utf-8")
        # after the review (finding 1): a worker ended hard left its transcript and history entry; its job file names it
        from halo_harness.agent import sessions as agent_sessions
        from halo_harness.config.paths import state_slug
        project, sid = home.path / "proj", "b" * 32
        logs = home.path / ".halo" / "sessions" / state_slug(project)
        logs.mkdir(parents=True)
        (logs / f"{sid}.jsonl").write_text('{"type": "user", "text": "THE GOAL"}\n', encoding="utf-8")
        (logs / "index.json").write_text(json.dumps({sid: {"title": "THE GOAL"}}), encoding="utf-8")
        (d / f"{PID}.job.{'a' * 32}.json").write_text(json.dumps({"job": {}, "session": {"id": sid, "project": str(project)}}),
                                                      encoding="utf-8")
        bridge.sweep(d)
        ctx.check(f"no bridge runs for {PID}: its job file and plan folder are swept, left {sorted(os.listdir(d))}",
                  os.listdir(d) == [])
        ctx.check(f"and its worker's transcript and history entry, left {sorted(os.listdir(logs)) if logs.exists() else []}",
                  not logs.exists() and sid not in agent_sessions.load_index(project))


@test
def test_a_worker_starts_no_claude_even_with_connector_discovery_on(ctx: Ctx):
    """`connectors.discover_on_start: true` makes a print session run `claude auth status` and discovery; a worker
    (--strict-mcp-config) never does: the fake claude's argv log stays empty."""
    with _Home() as home:
        log = home.path / "claude-argv.log"

        def setup(_jobs):
            cfg = json.loads((home.path / ".halo" / "config.json").read_text(encoding="utf-8"))
            cfg["connectors"] = {"discover_on_start": True}
            _write_config(home.path, **cfg)
        fake = f'"{sys.executable}" "{REPO / "tests" / "helpers" / "fake_claude_cc.py"}"'
        with _Env(HALO_CLAUDE_EXE=fake, FAKE_CLAUDE_CC_ARGV_LOG=str(log), BRIDGE_TEST_CC_AUTH_STATUS=None,
                  FAKE_CLAUDE_CC_CONNECTORS='[{"name": "Docs Fake", "url": "https://example.invalid/mcp"}]'):
            job, why, _m = _run_job(home.path, {"goal": "Say hi", "mode": "none"}, _said("hi"), setup=setup,
                                    quiet_net=False)
        ctx.check(f"started ({why})", job is not None and job.done.is_set() and job.packet()["state"] == "done")
        got = log.read_text(encoding="utf-8") if log.exists() else ""
        ctx.check(f"no claude was started, got {got[:300]!r}", got == "")


@test
def test_the_worker_is_given_no_login_and_no_provider_secret(ctx: Ctx):
    """The worker's environment: Claude Code's login and keys (CLAUDE_CODE_OAUTH_TOKEN, ANTHROPIC_*) and Halo's own
    provider secrets are dropped; the rest (OLLAMA_HOST, the parent mark) goes."""
    from halo_harness import subprocess_safe
    from halo_harness.guest import hand_out as H
    seen = {}

    def popen(argv, **kw):
        seen.update(kw.get("env") or {})
        raise OSError("the test's stand-in starts nothing")
    secrets = {"CLAUDE_CODE_OAUTH_TOKEN": "fake-oauth", "ANTHROPIC_API_KEY": "fake-a", "ANTHROPIC_AUTH_TOKEN": "fake-b",
               "ANTHROPIC_BASE_URL": "http://127.0.0.1:9", "OPENROUTER_API_KEY": "fake-or", "OLLAMA_API_KEY": "fake-ol",
               # after the review: no secret at all, Bedrock and Vertex logins, the shell's model choices, a proxy
               "AWS_SECRET_ACCESS_KEY": "fake-aws", "AWS_SESSION_TOKEN": "fake-aws2", "AWS_BEARER_TOKEN_BEDROCK": "fake-b3",
               "AWS_PROFILE": "fake-profile", "GOOGLE_APPLICATION_CREDENTIALS": "/x/fake-adc.json", "GH_TOKEN": "fake-gh",
               "Probe_Db_Password": "fake-pw", "HF_TOKEN": "fake-hf", "HALO_MODEL": "ant:fake-opus",
               "HALO_MODEL_SMALL": "ant:fake-haiku", "HTTPS_PROXY": "http://u:pw@proxy.example.com:8080",
               "http_proxy": "http://u:pw@proxy.example.com:8080", "CLAUDE_CONFIG_DIR": "/somewhere/.claude"}
    with _Home() as home, _Env(OLLAMA_HOST="http://127.0.0.1:9", NO_PROXY="localhost", **secrets):
        jobs = _hand_outs(home.path, home.path)
        task, _why = H.task_of({"goal": "x", "mode": "none"})
        job = H.Job(jobs, task, "ol:qwen3:30b@mine", "ollama:mine", {"goal": "x", "mode": "none"})
        real = subprocess_safe.Popen
        try:
            subprocess_safe.Popen = popen
            job.run()
        finally:
            subprocess_safe.Popen = real
        ctx.check("the stand-in was reached", bool(seen))
        kept = {k.upper() for k in seen}  # Windows' environment names are upper case
        left = sorted(k for k in secrets if k.upper() in kept and k != "CLAUDE_CONFIG_DIR")
        ctx.check(f"no login and no secret in the worker's env, got {left}", not left)
        ctx.check(f"the values never went either, got {[k for k, v in secrets.items() if v in seen.values()]}",
                  not any(v in seen.values() for k, v in secrets.items() if k != "ANTHROPIC_BASE_URL"))  # its value is OLLAMA_HOST's here
        ctx.check("OLLAMA_HOST, NO_PROXY and the parent mark go", seen.get("OLLAMA_HOST") == "http://127.0.0.1:9"
                  and seen.get("NO_PROXY") == "localhost" and str(seen.get("HALO_SESSION_PARENT") or "").startswith("guest:"))
        from halo_harness.guest import WORKER_MARK
        ctx.check(f"the worker mark is set and its Claude config folder is the job's own, got "
                  f"{seen.get(WORKER_MARK)!r}, {seen.get('CLAUDE_CONFIG_DIR')!r}",
                  seen.get(WORKER_MARK) == "1" and seen.get("CLAUDE_CONFIG_DIR") == str(jobs.plans(job)))
        ctx.check("the job's folder went with the job", not jobs.plans(job).exists())
        ctx.check(f"the job says failed, never a hang: {job.state}", job.state == "failed" and job.done.is_set())


@test
def test_a_host_whose_key_is_in_the_env_file_is_not_his_own(ctx: Ctx):
    """The key of an `ollama.hosts` entry kept in the env file (`api_key_env`, the shape 3.3.13.1's migration writes),
    not loaded into the bridge: the entry is still an account (refused, not listed, its catalog never read); the same
    for the synthesized default host with OLLAMA_API_KEY only in the env file."""
    from halo_harness.guest import hand_out as H
    with _Home() as home:
        envf = home.path / "halo.env"
        envf.write_text("PROBE_CLOUD_KEY=k-probe\nOLLAMA_API_KEY=k-probe2\n", encoding="utf-8")
        mock = _mock(_said("hello"))
        try:
            with _Env(HALO_ENV_FILE=str(envf), PROBE_CLOUD_KEY=None, OLLAMA_API_KEY=None, OLLAMA_HOST=mock.base_url):
                _write_config(home.path, ollama={"hosts": [{"name": "acct", "url": mock.base_url,
                                                            "api_key_env": "PROBE_CLOUD_KEY"}]})
                ref, _h, why = H.choose("ol:qwen3:30b@acct", home.path / ".halo")
                ctx.check(f"an api_key_env entry: refused, got {why!r}", not ref and "is not local" in why)
                rows = H.models(home.path / ".halo")["models"]
                ctx.check(f"not listed and its catalog never read: {rows}, {len(mock.requests)} requests",
                          rows == [] and not mock.requests)
                _write_config(home.path)
                ref, _h, why = H.choose("ol:qwen3:30b", home.path / ".halo")
                ctx.check(f"the default host with OLLAMA_API_KEY in the env file: refused, got {why!r}",
                          not ref and "is not local" in why)
                ctx.check("the env file was read purely (nothing loaded here)",
                          "PROBE_CLOUD_KEY" not in os.environ and "OLLAMA_API_KEY" not in os.environ)
                envf.write_text("", encoding="utf-8")
                ref, _h, why = H.choose("ol:qwen3:30b", home.path / ".halo")
                ctx.check(f"and with no key anywhere it is his own, got {why!r}", ref == "ol:qwen3:30b")
        finally:
            mock.stop()


@test
def test_a_cancel_that_comes_while_the_job_is_being_started_stops_it(ctx: Ctx):
    """A `notifications/cancelled` that arrives while halo_hand_out still checks the model and reads the host list
    (before the job exists) is kept: the job is stopped as soon as it exists and the call answers nothing."""
    import queue
    import threading
    from halo_harness.guest.tools import Tools

    class In:
        def __init__(self):
            self.q = queue.Queue()

        def readline(self):
            return self.q.get()

    class Out:
        def __init__(self):
            self.lines = []

        def write(self, b):
            self.lines.append(json.loads(b.decode("utf-8")))

        def flush(self):
            pass

    class FakeJob:
        id, model, state = "j" * 32, "ol:qwen3:30b@mine", "running"
        task = {"wait": True}

        def __init__(self):
            self.done, self.stopped = threading.Event(), threading.Event()

        def stop(self, why):
            self.stopped.set()
            self.done.set()
            return "asked"

        def packet(self, part=1):
            return {"state": "stopped"}
    with _Home() as home:
        d = home.path / ".halo" / "run" / "guest"
        d.mkdir(parents=True)
        tools = Tools(None, home.path, claude_pid=PID, directory=d, state_dir=home.path / ".halo")
        gate, fake = threading.Event(), FakeJob()

        def slow_start(_args):
            gate.wait(30)  # the model checked, the host's list being read
            tools.jobs.jobs[fake.id] = fake
            return fake, ""
        tools.jobs.start = slow_start
        rf, wf = In(), Out()
        loop = threading.Thread(target=tools.loop, args=(rf, wf), daemon=True)
        loop.start()
        try:
            def send(obj):
                rf.q.put((json.dumps(obj) + "\n").encode("utf-8"))
            send({"jsonrpc": "2.0", "id": 7, "method": "tools/call",
                  "params": {"name": "halo_hand_out", "arguments": {"goal": "x", "mode": "none"}}})
            send({"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 7}})
            send({"jsonrpc": "2.0", "id": 8, "method": "ping"})
            import time
            end = time.monotonic() + 30
            while time.monotonic() < end and not any(m.get("id") == 8 for m in wf.lines):
                time.sleep(0.05)
            ctx.check("the loop read the cancel (the ping after it is answered)", any(m.get("id") == 8 for m in wf.lines))
            gate.set()
            ctx.check("the job is stopped once it exists", fake.stopped.wait(30))
            end = time.monotonic() + 2.0
            while time.monotonic() < end and not any(m.get("id") == 7 for m in wf.lines):
                time.sleep(0.05)
            ctx.check(f"the cancelled call answers nothing, got {[m for m in wf.lines if m.get('id') == 7]}",
                      not any(m.get("id") == 7 for m in wf.lines))
        finally:
            gate.set()
            fake.done.set()
            rf.q.put(b"")
            loop.join(10)


@test
def test_the_turn_cap_and_the_wall_clock_stop_a_job_with_what_it_had(ctx: Ctx):
    import threading
    from halo_harness.guest import hand_out as H
    with _Home() as home:
        job, why, _m = _run_job(home.path, {"goal": "Read a.txt", "mode": "read_only", "max_turns": 2},
                                _tool("Read", file_path="a.txt"))
        ctx.check(f"started ({why})", job is not None and job.done.is_set())
        p = job.packet()
        ctx.check(f"the turn cap: stopped, said so: {p['state']}, {p.get('stopped_by')}",
                  p["state"] == "stopped" and p.get("stopped_by") == "the turn cap (2 turns)")
    stop = threading.Event()
    saved = H.MINUTE_S, H.POLITE_S
    with _Home() as home:
        try:
            H.MINUTE_S, H.POLITE_S = 4.0, 2.0
            job, why, _m = _run_job(home.path, {"goal": "Say hi", "mode": "none", "max_minutes": 1},
                                    _slow(stop, 120.0), seconds=90.0)
        finally:
            H.MINUTE_S, H.POLITE_S = saved
            stop.set()
        ctx.check(f"started ({why})", job is not None)
        ctx.check("the wall clock ended it", job.done.is_set())
        p = job.packet()
        ctx.check(f"stopped by the wall clock, with what it had: {p['state']}, {p.get('stopped_by')}",
                  p["state"] == "stopped" and p.get("stopped_by") == "the wall clock (1 minutes)" and "summary" in p)
        ctx.check("its pid is gone and out of the ledger", job.proc.poll() is not None and not _workers())


def _rows_rig():
    from halo_harness.guest.hand_out import Job
    feed, _seen, _ = _feed()
    home = Path(tempfile.mkdtemp(prefix="guest-rows-"))
    jobs = _hand_outs(home, Path(CWD), tree=feed.tree)
    feed.on_hand_out = jobs.saw_call
    for aid in ("s1", "s2"):
        feed._child(aid, "Explore", None)

    def job(goal: str):
        args = {"goal": goal, "mode": "none"}
        j = Job(jobs, {"goal": goal, "mode": "none", "acceptance": [], "files": [], "turns": 12, "minutes": 10,
                       "wait": True}, "ol:qwen3:30b", "ollama:default", args)
        jobs.jobs[j.id] = j
        jobs._row(j)
        return j, args
    return feed, jobs, job


def _hook(feed, aid: str, args: dict, tid: str, ts: int) -> None:
    from halo_harness.guest import note
    feed.take([json.loads(note.line_of(_ev("PreToolUse", tool_name="mcp__plugin_halo-guest_halo-guest__halo_hand_out",
                                           tool_use_id=tid, tool_input=args, **({"agent_id": aid} if aid else {})), ts=ts))])


@test
def test_a_workers_row_goes_under_the_calling_sub_agent_only_when_sure(ctx: Ctx):
    import time
    feed, jobs, job = _rows_rig()
    j0, a0 = job("Read the logs for errors")
    row = feed.tree.row(j0.aid)
    ctx.check(f"the row: under main, Halo: <model>, the goal, kind halo-worker; got {row}",
              row["parent"] == "main" and row["name"] == "Halo: ol:qwen3:30b" and row["task"] == "Read the logs for errors"
              and row["kind"] == "halo-worker" and row["state"] == "running")
    j1, a1 = job("Summarise the README")
    j2, a2 = job("List the test files")
    now = time.time_ns()
    _hook(feed, "s1", a1, "t1", now)
    _hook(feed, "s2", a2, "t2", now)
    ctx.check(f"two calls of one tool, two goals: each under its caller; got {feed.tree.row(j1.aid)['parent']}, "
              f"{feed.tree.row(j2.aid)['parent']}", feed.tree.row(j1.aid)["parent"] == "s1" and feed.tree.row(j2.aid)["parent"] == "s2")
    j3, a3 = job("Same goal twice")
    j4, a4 = job("Same goal twice")
    _hook(feed, "s1", a3, "t3", time.time_ns())
    _hook(feed, "s2", a4, "t4", time.time_ns())
    ctx.check("identical goals: both under main", feed.tree.row(j3.aid)["parent"] == "main" and feed.tree.row(j4.aid)["parent"] == "main")
    j5, a5 = job("A goal long ago")
    _hook(feed, "s1", a5, "t5", time.time_ns() - 60_000_000_000)
    ctx.check("a line far from the call in time: main", feed.tree.row(j5.aid)["parent"] == "main")


@test
def test_stop_on_a_worker_row_stops_its_job_and_every_other_row_stays_watch_only(ctx: Ctx):
    from halo_harness.guest.bridge import GuestHandle, GuestSession
    from halo_harness.remote import protocol
    from halo_harness.remote.base import HandleError
    feed, jobs, job = _rows_rig()
    j, _a = job("Read the logs")
    asked = []
    j.stop = lambda why: asked.append(why) or "the stop is asked"
    handle = GuestHandle(feed.session, CWD, PID)
    handle.feed, handle.hand_outs = feed, jobs
    got = protocol.run_cmd(handle, {"cmd": "agent_stop", "agent_id": j.aid, "via": "Studio"}, None)
    ctx.check(f"agent_stop on the worker's row stops its job, got {got} {asked}",
              asked == ["Studio (its Stop)"] and got["agent_id"] == j.aid)
    for req in ({"cmd": "agent_stop", "agent_id": "main"}, {"cmd": "agent_stop", "agent_id": "s1"},
                {"cmd": "agent_steer", "agent_id": j.aid, "text": "x"}, {"cmd": "submit", "text": "x"}):
        try:
            protocol.run_cmd(handle, req, None)
            said = ""
        except HandleError as e:
            said = str(e)
        ctx.check(f"{req['cmd']} {req.get('agent_id', '')}: watch only, got {said!r}", said.startswith("watch only"))
    ctx.check("a guest without hand-outs: agent_stop watch only as before",
              GuestHandle(GuestSession("g"), CWD, PID).serve_own("agent_stop", {"agent_id": j.aid}) is None)


@test
def test_the_bridge_hands_out_answers_ping_meanwhile_and_cuts_a_long_answer_into_parts(ctx: Ctx):
    """The real bridge, the test as Claude Code: tools listed, a wait call with progress while ping is answered, a
    wait false job read in parts, a cancel that stops its job and gets no answer."""
    import threading
    import time
    stop = threading.Event()
    long = "".join(f"line {i:05d} of the long answer\n" for i in range(1500))  # 45,000 characters
    with _Home() as home:
        mock = _mock(_slow(stop, 3.0, "Hello from the local model"), _said(long), _slow(stop, 120.0))
        mcp = None
        try:
            _write_config(home.path, guest={"hand_out": "local"}, model="ol:qwen3:30b",
                          ollama={"hosts": [{"name": "mine", "url": mock.base_url, "default": True}]})
            project = home.path / "proj"
            project.mkdir()
            mcp = _Mcp(home.path, project, mock.base_url)
            mcp.ask(1, "initialize", {"protocolVersion": "2025-06-18"})
            init = mcp.reply(1, 60)
            ctx.check(f"initialize: the instructions, got {init}", bool(init) and "instructions" in init["result"])
            mcp.ask(2, "tools/list")
            names = [t["name"] for t in (mcp.reply(2, 30) or {}).get("result", {}).get("tools", [])]
            ctx.check(f"five tools, got {names}", len(names) == 5 and "halo_hand_out" in names)
            mcp.ask(3, "tools/call", {"name": "halo_hand_out", "arguments": {"goal": "Say hello", "mode": "none"},
                                      "_meta": {"progressToken": "p-1"}})
            time.sleep(1.0)
            mcp.ask(4, "ping")
            pong = mcp.reply(4, 30)
            done = mcp.reply(3, 180)
            ctx.check("ping answered while the job ran (before its answer)",
                      bool(pong) and bool(done) and mcp.got.index(pong) < mcp.got.index(done))
            packet = json.loads(done["result"]["content"][0]["text"])
            ctx.check(f"the packet: done, its text, got {packet.get('state')} {packet.get('summary')!r}",
                      packet["state"] == "done" and packet["summary"] == "Hello from the local model")
            prog = [m["params"] for m in mcp.got if m.get("method") == "notifications/progress"]
            ctx.check(f"progress for its token, increasing, at most one a second: {prog}",
                      prog and all(p["progressToken"] == "p-1" for p in prog)
                      and all(b["progress"] > a["progress"] for a, b in zip(prog, prog[1:])))
            started, _r = mcp.call(5, "halo_hand_out", goal="Write a long answer", mode="none", wait=False)
            ctx.check(f"wait false: a job_id at once, got {started}", isinstance(started, dict) and len(started.get("job_id", "")) == 32)
            jid = started["job_id"]
            end = time.monotonic() + 120
            state, n = None, 100
            while time.monotonic() < end:
                n += 1
                state, _r = mcp.call(n, "halo_job", job_id=jid)
                if state and state.get("state") != "running":
                    break
                time.sleep(0.5)
            ctx.check(f"halo_job: done, got {state}", bool(state) and state["state"] == "done")
            p1, _r = mcp.call(7, "halo_job_result", job_id=jid)
            p3, _r = mcp.call(8, "halo_job_result", job_id=jid, part=3)
            ctx.check(f"parts of 20,000 characters, the cut said: {p1.get('parts')} {p1.get('cut')!r}",
                      p1["parts"] == 3 and len(p1["summary"]) == 20000 and "halo_job_result with part 2" in p1["cut"]
                      and p1["summary"] + "" == long[:20000] and p3["summary"] == long[40000:])
            mcp.ask(9, "tools/call", {"name": "halo_hand_out", "arguments": {"goal": "Never ends", "mode": "none"}})
            row = _wait_worker(60)
            ctx.check("its worker is in the ledger", row is not None)
            mcp.send({"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 9, "reason": "Esc"}})
            ctx.check(f"the cancel ends its worker within {GONE_S:.0f} s", row is not None and _gone(row, GONE_S))
            files = _job_files(home.path)
            last = json.loads(files[-1].read_text(encoding="utf-8")) if files else {}
            time.sleep(1.0)
            ctx.check(f"its job: stopped by the cancel, got {last.get('job')}",
                      any((json.loads(f.read_text(encoding='utf-8')).get("job") or {}).get("stopped_by") == "the call was cancelled"
                          for f in files))
            ctx.check("no answer to the cancelled call", mcp.reply(9, 2.0) is None)
            mcp.proc.stdin.close()
            mcp.proc.wait(60)
            ctx.check("the input closed: the bridge ended and removed its job files", not _job_files(home.path))
        finally:
            stop.set()
            if mcp is not None:
                mcp.end()
            _end_pid(_wait_worker(0.1))
            mock.stop()


def _kill_leg(ctx: Ctx, how: str) -> None:
    """The bridge as the test's child starts a worker on the mock, then is ended `how`; the worker's pid is gone
    within GONE_S and the job files are swept."""
    import threading
    stop = threading.Event()
    with _Home() as home:
        mock = _mock(_slow(stop, 300.0))
        mcp = row = job = None
        k32 = None
        try:
            _write_config(home.path, guest={"hand_out": "local"}, model="ol:qwen3:30b",
                          ollama={"hosts": [{"name": "mine", "url": mock.base_url, "default": True}]})
            project = home.path / "proj"
            project.mkdir()
            flags = 0x4 if how == "outer-job" else 0  # CREATE_SUSPENDED: into the strict Job before its first instruction
            mcp = _Mcp(home.path, project, mock.base_url, flags=flags)
            if how == "outer-job":
                from tests.test_kept_outlives_starter import _no_breakaway_job
                from halo_harness import closing
                k32, job = _no_breakaway_job()
                ctx.check("the bridge is in the test's strict Job", k32.AssignProcessToJobObject(job, int(mcp.proc._handle)))
                closing._nt_resume(mcp.proc)
            mcp.ask(1, "initialize", {"protocolVersion": "2025-06-18"})
            ctx.check("the bridge answers", mcp.reply(1, 60) is not None)
            started, _r = mcp.call(2, "halo_hand_out", goal="Never ends", mode="none", wait=False)
            ctx.check(f"a job started, got {started}", isinstance(started, dict) and "job_id" in started)
            row = _wait_worker(60)
            import time
            end = time.monotonic() + 90
            while time.monotonic() < end and not any(r.get("path") == "/api/chat" for r in mock.requests):
                time.sleep(0.2)
            ctx.check(f"{how}: its worker runs, its model call held at the mock (not a vacuous check)",
                      row is not None and _alive(row) and any(r.get("path") == "/api/chat" for r in mock.requests))
            if how == "input-closes":
                mcp.proc.stdin.close()
            else:
                mcp.proc.kill()  # hard, by the test's own handle: no Python runs in the bridge
            ctx.check(f"{how}: the worker (pid {row and row['pid']}) is gone within {GONE_S:.0f} s",
                      row is not None and _gone(row, GONE_S))
            mcp.proc.wait(60)
            if how == "input-closes":  # after the review (finding 8): the bridge's own close left nothing, before any sweep
                ctx.check(f"{how}: no job file is left by the bridge's close, before any sweep, got {_job_files(home.path)}",
                          not _job_files(home.path))
            from halo_harness.guest import sweep_dead
            sweep_dead()
            ctx.check(f"{how}: no job file is left after the sweep, got {_job_files(home.path)}", not _job_files(home.path))
            kept = sorted(str(p) for p in (home.path / ".halo" / "sessions").rglob("*.jsonl"))
            ctx.check(f"{how}: and no transcript of the worker is kept, got {kept}", not kept)
        finally:
            stop.set()
            if mcp is not None:
                mcp.end()
            _end_pid(row)
            if job is not None:
                k32.CloseHandle(job)
            mock.stop()


@test
def test_closing_a_worker_ends_when_the_bridges_input_closes(ctx: Ctx):
    _kill_leg(ctx, "input-closes")


@test
def test_closing_a_worker_ends_when_the_bridge_is_killed_hard(ctx: Ctx):
    _kill_leg(ctx, "killed-hard")


@test
def test_closing_a_worker_ends_when_the_bridge_is_killed_hard_inside_a_strict_outer_job(ctx: Ctx):
    if os.name != "nt":
        ctx.check("Windows only: Job objects (POSIX: the leg above is the owner watch's)", True)
        return
    _kill_leg(ctx, "outer-job")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="guest"))
