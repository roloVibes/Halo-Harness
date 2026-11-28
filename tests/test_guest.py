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
             "started": 2.0}]
    real = registry.list_live
    with _Home() as home:
        try:
            registry.list_live = lambda *a, **kw: [dict(r) for r in rows]
            local_view.forget()
            ctx.check(f"sessions(): the Halo session only, got {[r['session_id'] for r in remote.sessions()]}",
                      [r["session_id"] for r in remote.sessions()] == ["h-1"])
            ctx.check("connect() to the guest: None", remote.connect("g-1", timeout=1) is None)
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


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="guest"))
