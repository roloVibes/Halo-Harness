"""tests.test_realcheck -- the machinery of scripts/realcheck.py (3.6.0.0 R11), against tiny stand-in commands, so
the checker itself is trusted: step selection and the one line per step, the time budget, a failed step not stopping
the rest, the process scan (a scratch path in the environment, a child with a stripped one, Halo's marker, never a
process of another home), the kill that refuses a pid whose start time changed, the terminal (Ctrl+C, a closed
window, a hard kill), the beep and palette readers, the environment a launch gets, the fake provider's script and
the browser stand-in. No `halo` is started here; the script's own run is the CI job `realcheck`."""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from contextlib import redirect_stdout
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from realcheck import core, fakes, procs, report, screen  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
SLEEP = "import time; time.sleep(60)"


def _main_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("realcheck_main", REPO / "scripts" / "realcheck.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _gone(p: subprocess.Popen) -> None:
    if p.poll() is None:
        p.kill()
    try:
        p.wait(10)
    except subprocess.TimeoutExpired:
        pass


@test
def test_list_names_every_step_and_an_unknown_step_is_a_usage_error(ctx: Ctx):
    m = _main_module()
    out = io.StringIO()
    with redirect_stdout(out):
        rc = m.main(["--list"])
    lines = out.getvalue().splitlines()
    names = [line.split()[0] for line in lines]
    ctx.check(f"the twenty steps in order, got {names}", rc == 0 and names == [
        "starts", "first-run", "theme", "question", "turn", "copy-drag", "studio", "prompt", "session-map",
        "auto-groups", "auto-ready-lines", "live-scene", "made-at-once", "browser", "packs", "local", "update", "closing",
        "no-reuse", "idle-cpu"])
    # 3.6.0.2 P6: `prompt` (one prompt in two views) after `studio`; 3.6.0.5: the two Auto steps after `session-map`;
    # 3.6.0.7: `copy-drag` (a drag over an earlier answer in a terminal session) after `turn`; 3.6.0.8: `browser`,
    # the built-in Browser tool, after the two Auto steps; 3.6.0.14 K1: `live-scene` (the drawing of a running session
    # on Auto) after them, before `browser`; K2: idle-cpu measures its minute with Agents -> Live open; 3.6.0.15 K1:
    # `made-at-once` (a pick in a running helper's box acts at once) right after live-scene
    win = sys.platform == "win32"
    for step, want, words in (("copy-drag", "120s" if win else "60s", "120 s on Windows, 60 s elsewhere"),
                              ("session-map", "180s" if win else "120s", "180 s on Windows, 120 s elsewhere"),
                              ("auto-groups", "150s" if win else "90s", "150 s on Windows, 90 s elsewhere"),
                              ("auto-ready-lines", "180s" if win else "120s", "180 s on Windows, 120 s elsewhere"),
                              ("live-scene", "180s" if win else "120s", "180 s on Windows, 120 s elsewhere"),
                              ("made-at-once", "180s" if win else "120s", "180 s on Windows, 120 s elsewhere"),
                              ("browser", "180s" if win else "120s", "180 s on Windows, 120 s elsewhere"),
                              ("idle-cpu", "240s" if win else "180s", "240 s on Windows, 180 s elsewhere")):
        budget = next((line.split()[1] for line in lines if line.split()[0] == step), "")
        ctx.check(f"{step}'s budget is {want} here ({words}), got {budget!r}", budget == want)
    ctx.check("an unknown step: exit 2", m.main(["--only", "no-such-step"]) == 2)
    # 3.6.0.16: no step is on request any more: live-scene runs in a plain run, and so in CI (3.6.0.14 and 3.6.0.15
    # left it out). The rule itself stays for a later step, and is held below with a stand-in list
    marked = [line.split()[0] for line in lines if "[runs only with --only" in line]
    ctx.check(f"--list marks no step as running only with --only, got {marked}", marked == [] and m.ON_REQUEST == ())
    from unittest import mock
    ran: list = []

    def fake_run(chosen, **kw):
        ran.append([s[0] for s in chosen])
        return [], "halo 0"
    with mock.patch.object(m, "run", fake_run), redirect_stdout(io.StringIO()):
        m.main([])
        m.main(["--only", "live-scene"])
        m.main(["--only", "starts", "live-scene"])
        listed = io.StringIO()
        with mock.patch.object(m, "ON_REQUEST", ("live-scene",)):
            m.main([])
            with redirect_stdout(listed):
                m.main(["--list"])
    ctx.check(f"a plain run is all twenty steps, live-scene and made-at-once among them, got {ran[:1]}",
              len(ran) == 4 and ran[0] == names and len(ran[0]) == 20 and "live-scene" in ran[0]
              and "made-at-once" in ran[0])
    ctx.check(f"--only live-scene runs it, alone or with others, got {ran[1:3]}",
              ran[1:3] == [["live-scene"], ["starts", "live-scene"]])
    held = [line.split()[0] for line in listed.getvalue().splitlines() if "[runs only with --only" in line]
    ctx.check(f"a step put in ON_REQUEST is left out of a plain run and marked by --list, got {ran[3:]} {held}",
              ran[3:] == [[n for n in names if n != "live-scene"]] and held == ["live-scene"])


@test
def test_auto_ready_lines_summary_says_what_it_judges(ctx: Ctx):
    """3.6.0.15 K2 (i): since UN the step judges P1 alone (ready in this session now), so its line in --list says that,
    not "saved for the next session"."""
    what = next((s[2] for s in _main_module()._steps() if s[0] == "auto-ready-lines"), "")
    ctx.check(f"the summary names what the step judges, got {what!r}",
              "ready in this session now" in what and "saved for the next session" not in what)


@test
def test_each_step_runs_a_failure_does_not_stop_the_rest_and_over_budget_is_a_fail(ctx: Ctx):
    m = _main_module()
    seen = []

    def ok(c):
        seen.append("ok")
        return "fine", {"n": 1}

    def bad(c):
        seen.append("bad")
        raise core.Fail("a person saw X", {"k": 2}, "R10")

    def skip(c):
        raise core.Skip("no Chrome")

    def slow(c):
        time.sleep(1.2)
        return "slow but fine", {}

    def broken(c):
        raise KeyError("oops")
    lines = []
    steps = [("a", 10, "", ok), ("b", 10, "", bad), ("c", 10, "", skip), ("d", 1, "", slow), ("e", 10, "", broken),
             ("f", 10, "", ok)]
    results, _v = m.run(steps, root=tempfile.mkdtemp(prefix="rc-test-"), probe_version=False, say=lines.append)
    st = [(r.name, r.status) for r in results]
    ctx.check(f"every step ran, in order, got {st}", st == [("a", "PASS"), ("b", "FAIL"), ("c", "SKIP"), ("d", "FAIL"),
                                                            ("e", "FAIL"), ("f", "PASS")] and seen == ["ok", "bad", "ok"])
    ctx.check(f"over budget says the time, got {results[3].detail!r}", results[3].detail.startswith("took 1s, budget 1s"))
    ctx.check("the checker's own error is named as the checker's", results[4].detail.startswith("realcheck itself failed: KeyError"))
    ctx.check(f"one line per step, the expected-until note on the FAIL, got {lines[1]!r}",
              len(lines) == 6 and lines[1].startswith("b") and "FAIL" in lines[1] and "a person saw X" in lines[1]
              and "[expected until R10 lands]" in lines[1])
    doc = json.loads(report.to_json(results, report.run_info("halo 0", "checkout")))
    ctx.check("the JSON says not ok and keeps the evidence", doc["ok"] is False and doc["steps"][1]["evidence"] == {"k": 2})
    md = report.markdown(results, {"platform": "x", "python": "3", "halo": "halo 0"})
    ctx.check("the summary table has a row per step and the count", md.count("\n| ") == 7 and "2 passed, 3 failed, 1 skipped" in md)


@test
def test_the_scan_finds_a_scratch_homes_processes_and_nothing_else(ctx: Ctx):
    scratch = Path(tempfile.mkdtemp(prefix="rc-scan-"))
    other = Path(tempfile.mkdtemp(prefix="rc-other-"))
    bare = {k: os.environ[k] for k in ("SYSTEMROOT", "PATH") if k in os.environ}
    child = ("import os, subprocess, sys, time; subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], "
             f"env={bare!r}); time.sleep(60)")
    a = subprocess.Popen([sys.executable, "-c", child], env=dict(os.environ, BRIDGE_TEST_HOME=str(scratch)))
    b = subprocess.Popen([sys.executable, "-c", SLEEP, str(scratch / "x")], env=bare)
    c = subprocess.Popen([sys.executable, "-c", SLEEP], env=dict(bare, BRIDGE_TEST_HOME=str(other)))
    d = subprocess.Popen([sys.executable, "-c", SLEEP], env=dict(bare, HALO_OWNER="rc-owner-7"))
    e = subprocess.Popen([sys.executable, "-c", SLEEP], env=dict(bare, HALO_OWNER="rc-owner-8"))
    found: dict = {}
    try:
        time.sleep(1.5)
        found = procs.belonging(procs.snapshot(), procs.needles_for(scratch), owners={"rc-owner-7"})
        whys = {pid: p.why for pid, p in found.items()}
        kids = [pid for pid, why in whys.items() if why == f"child of pid {a.pid}"]
        ctx.check(f"by environment, by command line, the child with a stripped environment, the marker: {whys}",
                  whys.get(a.pid) == "scratch path in its environment" and whys.get(b.pid) == "scratch path in its command line"
                  and len(kids) == 1 and whys.get(d.pid, "").startswith("HALO_OWNER="))
        ctx.check("never another home's process, never another marker's", c.pid not in found and e.pid not in found)
        stale = procs.Proc(b.pid, 0, "x", started=12345.0)
        ctx.check("a pid whose start time is not the scan's is refused", procs.kill(stale) is False and procs.alive(b.pid))
        killed = [procs.kill(p) for p in found.values()]
        time.sleep(1.0)
        ctx.check(f"each one found is ended, got {killed}", all(killed) and not any(procs.alive(p) for p in found))
        ctx.check("the others live on", procs.alive(c.pid) and procs.alive(e.pid))
    finally:
        for p in (a, b, c, d, e):
            _gone(p)
        for p in found.values():  # a's grandchild too: a failed check must not leave it sleeping for 60 s
            if procs.alive(p.pid):
                procs.kill(p)


CHILD = ("import sys, time\nprint('tty', sys.stdin.isatty(), sys.stdout.isatty(), flush=True)\n"
         "try:\n    time.sleep(60)\nexcept KeyboardInterrupt:\n    print('GOT CTRL-C', flush=True)\n    sys.exit(7)\n")


@test
def test_the_terminal_gives_a_tty_and_ends_a_child_three_ways(ctx: Ctx):
    from realcheck.term import Terminal, ctrl_c_probe
    probe = ctrl_c_probe(tempfile.gettempdir())
    ctx.check(f"the probe's child had a terminal, got {probe}", probe.get("tty") is True)
    if probe["delivered"]:
        ctx.check(f"a typed Ctrl+C or the console's event reached it, got {probe}", probe["via"] in ("typed", "console event"))
    else:  # an honest outcome: only where a launcher switched Ctrl+C off for its children, and with the reason and Break
        ctx.check(f"not deliverable is a Windows host's answer and says why, got {probe}",
                  sys.platform == "win32" and "ignore Ctrl+C" in probe["why"] and probe["break_works"] is not None)
    ways = ("ctrl_c" if probe["delivered"] else "ctrl_break", "close_window", "hard_kill")
    for how in ways:
        t = Terminal([sys.executable, "-c", CHILD], env=dict(os.environ), cwd=tempfile.gettempdir())
        try:
            up = t.wait_for(lambda s: "tty True True" in s, 30)
            if how == "ctrl_c" and probe["via"] == "console event":
                t.console_event(0)
            else:
                getattr(t, how)()
            code = t.wait(15)
            ctx.check(f"{how}: a terminal on stdin and stdout, then the child ended (exit {code})", up and code is not None)
            if how == "ctrl_c":
                # the child's last line can reach the reader after its exit code does (a pseudoconsole drains its
                # output after the process ends: exit 7 with the line not read yet was this test's red on Windows)
                end = time.monotonic() + 5
                while "GOT CTRL-C" not in t.plain() and time.monotonic() < end:
                    time.sleep(0.05)
                ctx.check(f"Ctrl+C reached it as an interrupt, got exit {code} {t.plain()[-80:]!r} (probe {probe})",
                          code == 7 and "GOT CTRL-C" in t.plain())
        finally:
            t.hard_kill()
            t.cleanup()


@test
def test_beeps_palette_and_the_page_theme_are_read_from_the_bytes(ctx: Ctx):
    got = screen.beeps(b"\x1b]0;halo\x07hello\x07 there")
    ctx.check(f"an OSC's BEL is not a beep; a bare one is, got {got}", got["bare"] == 1 and got["osc"] == ["0"])
    frame = b"\x1b[48;2;7;9;12mx\x1b[48;2;7;9;12my\x1b[48;2;11;14;18mz"
    pal = screen.palette_of(frame, {"instrument": {"#07090c", "#0b0e12"}, "paper": {"#f7f3ea"}})
    ctx.check(f"the frame's backgrounds name the palette, got {pal}", pal["theme"] == "instrument" and pal["truecolor"])
    ctx.check("the page's data-theme", screen.page_theme(b'<html lang="en" data-theme="paper">') == "paper")


@test
def test_a_launch_gets_a_scratch_home_and_none_of_this_shells_halo_or_provider_variables(ctx: Ctx):
    c = core.Ctx(REPO, Path(tempfile.mkdtemp(prefix="rc-env-")))
    saved = {k: os.environ.get(k) for k in ("HALO_THEME", "ANTHROPIC_API_KEY", "OLLAMA_HOST")}
    os.environ.update(HALO_THEME="paper", ANTHROPIC_API_KEY="sk-ant-real", OLLAMA_HOST="http://gpu-box:11434")
    try:
        h = c.home("env")
        env = c.env(h, EXTRA="1", COLORTERM=None)
        ctx.check("HOME, the test home and TMP are the scratch home's", env["HOME"] == str(h.home) == env["BRIDGE_TEST_HOME"]
                  and env["TMP"] == str(h.tmp) and env["USERPROFILE"] == str(h.home))
        ctx.check("no HALO_ or provider variable of this shell", "HALO_THEME" not in env and env.get("ANTHROPIC_API_KEY") is None)
        ctx.check("Ollama is a dead loopback port", env["OLLAMA_HOST"] == core.DEAD_OLLAMA)
        ctx.check("an extra is set and a None removes", env["EXTRA"] == "1" and "COLORTERM" not in env)
        ctx.check(f"the scan's needles are the launch's own folder, got {h.needles()}",
                  h.needles()[0] == procs.norm(str(h.dir)).rstrip("/"))
    finally:
        for k, v in saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        c.close()


def _post(url: str, body: dict) -> str:
    req = urllib.request.Request(url + "/chat/completions", data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=10) as r:
        return r.read().decode("utf-8")


@test
def test_the_fake_provider_scripts_a_real_turn_by_what_the_request_says(ctx: Ctx):
    from tests.helpers.mock_openai import SCENARIOS
    before = {k: SCENARIOS.get(k) for k in ("model", "realcheck")}
    try:
        _fake_provider_turn(ctx)
    finally:
        # the mock's scenario table is the whole process's: the stand-in puts back what it borrowed (popping "model"
        # once took the mock's default answer from every later module of a CI shard: test_w6a_release_fixes' 404s)
        ctx.check(f"stopped, the table holds what it held before, got {[SCENARIOS.get(k) for k in before]}",
                  all(SCENARIOS.get(k) is v for k, v in before.items()) and before["model"] is not None)


def _fake_provider_turn(ctx: Ctx) -> None:
    p = fakes.Provider().start()
    try:
        ask = {"model": "any/thing", "stream": True, "messages": [{"role": "user", "content": "RC-WORK file=/x/n.txt wf=w"}]}
        first = _post(p.base_url, ask)
        ask["messages"] += [{"role": "assistant", "content": None}, {"role": "tool", "content": "1 n"}]
        second = _post(p.base_url, ask)
        ask["messages"] += [{"role": "assistant", "content": None}, {"role": "tool", "content": "sub"}]
        third = _post(p.base_url, ask)
        ask["messages"] += [{"role": "assistant", "content": None}, {"role": "tool", "content": "wf"}]
        last = _post(p.base_url, ask)
        ctx.check("Read, then Agent, then Workflow, then the end", '"Read"' in first and '"Agent"' in second
                  and '"Workflow"' in third and fakes.WORK_DONE in last)
        ctx.check("any other model call is answered", fakes.ANSWER in _post(p.base_url, {"model": "x", "messages": [
            {"role": "user", "content": "hello"}]}))
        ctx.check("the calls are kept, found by their text", len(p.requests_with("RC-WORK file=/x/n.txt")) == 4)
    finally:
        p.stop()


def _stream(text: str) -> "tuple[str, list]":
    """(the streamed answer's text, its tool calls as [(name, arguments parsed)]) from the fake's SSE body."""
    said, calls = [], {}
    for line in text.splitlines():
        if not line.startswith("data: ") or line[6:].strip() == "[DONE]":
            continue
        for ch in json.loads(line[6:]).get("choices") or []:
            d = ch.get("delta") or {}
            said.append(d.get("content") or "")
            for tc in d.get("tool_calls") or []:
                got = calls.setdefault(tc.get("index", 0), ["", ""])
                fn = tc.get("function") or {}
                got[0] += fn.get("name") or ""
                got[1] += fn.get("arguments") or ""
    return "".join(said), [(n, json.loads(a or "{}")) for n, a in calls.values()]


@test
def test_the_fake_provider_plays_the_map_build_and_the_question(ctx: Ctx):
    """3.6.0.2 section 11: RC-MAPBUILD is ONE Builder call (the workflow review: coder, then reviewer, in a box on the
    new map review-flow, the line main -> review), then a line ending in the sentence the result says to repeat;
    RC-MAPASK is one plain line. Both read the current turn only: a facts note at the turn's start, before or after the
    typed line, or the first turn's Builder result in the history never confuses them."""
    from tests.helpers.mock_openai import SCENARIOS
    before = {k: SCENARIOS.get(k) for k in ("model", "realcheck")}
    try:
        _map_build_and_ask(ctx)
    finally:
        ctx.check("stopped, the table holds what it held before",
                  all(SCENARIOS.get(k) is v for k, v in before.items()))


S13 = ("This session keeps running on Auto (the default), as it started. Start a new session to run on "
       "review-flow.")
NOTE = ("[Halo] This session runs on Auto (the default), as it started at 10:24. New sessions will run on "
        "review-flow (switched on at 10:25, by this session).")
BUILD, ASK = "RC-MAPBUILD: build me a review workflow: a coder then a reviewer", "RC-MAPASK: which workflow are you using?"
BUILD_DONE, ASK_DONE = "RC-MAPBUILD-DONE", "RC-MAPASK-DONE"


def _map_build_and_ask(ctx: Ctx) -> None:
    p = fakes.Provider().start()
    try:
        msgs = [{"role": "user", "content": BUILD}]
        said, calls = _stream(_post(p.base_url, {"model": "any/thing", "stream": True, "messages": msgs}))
        want = [{"tool": "workflow_make", "args": {"name": "review", "for": "review", "steps": [
                    {"name": "code", "agents": ["coder"]}, {"name": "review", "agents": ["reviewer"]}]}},
                {"tool": "map_box_add", "args": {"map": "review-flow", "kind": "workflow", "ref": "review"}},
                {"tool": "map_line_add", "args": {"map": "review-flow", "from": "main", "to": "review", "when": "always"}}]
        ctx.check(f"(a) RC-MAPBUILD: one Builder call with the three changes, got {said!r} {calls}",
                  len(calls) == 1 and calls[0][0] == "Builder" and calls[0][1] == {"changes": want}
                  and getattr(fakes, "BUILD_CHANGES", None) == want)
        msgs += [{"role": "assistant", "content": None, "tool_calls": [
                     {"id": "call_rc_build", "type": "function",
                      "function": {"name": "Builder", "arguments": json.dumps({"changes": want})}}]},
                 {"role": "tool", "tool_call_id": "call_rc_build",
                  "content": "Written: the map review-flow (new). Undo: u1. Tell the person, word for word: " + S13}]
        said, calls = _stream(_post(p.base_url, {"model": "any/thing", "stream": True, "messages": msgs}))
        ctx.check(f"(b) after the result: MAPBUILD_DONE ending in the sentence, got {said!r} {calls}",
                  not calls and BUILD_DONE in said and said.endswith(S13))
        msgs.append({"role": "assistant", "content": said})
        for order in ((NOTE, ASK), (ASK, NOTE)):
            turn = msgs + [{"role": "user", "content": u} for u in order]
            said, calls = _stream(_post(p.base_url, {"model": "any/thing", "stream": True, "messages": turn}))
            ctx.check(f"(c) RC-MAPASK with the note {'first' if order[0] == NOTE else 'last'}: one plain line, "
                      f"got {said!r} {calls}", not calls and ASK_DONE in said)
        msgs += [{"role": "user", "content": NOTE}, {"role": "user", "content": ASK},
                 {"role": "assistant", "content": ASK_DONE}, {"role": "user", "content": "RC-ASK turn two"}]
        said, calls = _stream(_post(p.base_url, {"model": "any/thing", "stream": True, "messages": msgs}))
        ctx.check(f"(d) a later turn is answered by its own words, not the history's RC-MAPBUILD, got {said!r} {calls}",
                  not calls and said == fakes.ANSWER)
        without = [{"role": "user", "content": BUILD},
                   {"role": "assistant", "content": None, "tool_calls": [
                       {"id": "call_rc_build", "type": "function", "function": {"name": "Builder", "arguments": "{}"}}]},
                   {"role": "tool", "tool_call_id": "call_rc_build", "content": "Applied 1 line(s)."}]
        said, calls = _stream(_post(p.base_url, {"model": "any/thing", "stream": True, "messages": without}))
        ctx.check(f"a result with no words to repeat: MAPBUILD_DONE alone, got {said!r}",
                  not calls and said.strip() == BUILD_DONE)
        ctx.check("the step and this test read the same words", [getattr(fakes, n, None) for n in (
            "BUILD_PROMPT", "ASK_PROMPT", "MAPBUILD_DONE", "MAPASK_DONE")] == [BUILD, ASK, BUILD_DONE, ASK_DONE])
    finally:
        p.stop()


@test
def test_the_fake_provider_plays_auto_groups_build_and_use(ctx: Ctx):
    """3.6.0.5 section 6: RC-AUTOGROUPS is scene 2's five replies (three researchers with the task "compare the three
    reports" in ONE message, then coder, reviewer, an Agent and a Task with no task), each sub-agent answering after
    SUBWAIT_S; RC-AUTOBUILD is ONE Builder call (the agent checker, the workflow review: no map); RC-AUTOUSE is ONE
    Workflow call to review whose step children are held at the gate. Each reads the current turn only."""
    from tests.helpers.mock_openai import SCENARIOS
    before = {k: SCENARIOS.get(k) for k in ("model", "realcheck")}
    try:
        _auto_groups_build_and_use(ctx)
    finally:
        ctx.check("stopped, the table holds what it held before",
                  all(SCENARIOS.get(k) is v for k, v in before.items()))


AUTOGROUPS, AUTOGROUPS_DONE = "RC-AUTOGROUPS: five replies", "RC-AUTOGROUPS-DONE"
AUTOBUILD, AUTOBUILD_DONE = "RC-AUTOBUILD: build me a review workflow: a coder then a checker", "RC-AUTOBUILD-DONE"
AUTOUSE, AUTOUSE_DONE = "RC-AUTOUSE: use it now", "RC-AUTOUSE-DONE"


def _ask(p, msgs: list) -> "tuple[str, list]":
    return _stream(_post(p.base_url, {"model": "any/thing", "stream": True, "messages": msgs}))


def _called(msgs: list, calls: list, results: int) -> list:
    """`msgs` with one assistant message calling `calls` and `results` tool results after it."""
    tcs = [{"id": f"c{i}", "type": "function", "function": {"name": n, "arguments": json.dumps(a)}}
           for i, (n, a) in enumerate(calls)]
    return msgs + [{"role": "assistant", "content": None, "tool_calls": tcs}] + [
        {"role": "tool", "tool_call_id": f"c{i}", "content": "done"} for i in range(results)]


def _auto_groups_build_and_use(ctx: Ctx) -> None:
    p = fakes.Provider().start()
    try:
        replies = getattr(fakes, "AUTOGROUPS_REPLIES", None) or []
        want = [[(n, a) for n, a, _cid in r] for r in replies]
        msgs = [{"role": "user", "content": AUTOGROUPS}]
        said, calls = _ask(p, msgs)
        ctx.check(f"(a) RC-AUTOGROUPS: one message with the three Agent calls of reply 1, got {said!r} {calls}",
                  len(want) == 5 and len(calls) == 3 and calls == want[0] and all(n == "Agent" for n, _a in calls)
                  and all(a.get("task") == "compare the three reports" for _n, a in calls))
        done = 3
        convo = _called(msgs, calls, 3)
        for k in range(1, 5):
            said, calls = _ask(p, convo)
            ctx.check(f"(a) after {done} results: reply {k + 1}, got {said!r} {calls}",
                      len(want) == 5 and calls == want[k])
            done += 1
            convo = _called(convo, calls, 1) if calls else convo  # this turn's results now number `done`
        if len(want) == 5:
            ctx.check("(a) replies 4 and 5 hold no task key; reply 5 is a Task call",
                      "task" not in want[3][0][1] and "task" not in want[4][0][1] and want[4][0][0] == "Task"
                      and want[3][0][0] == "Agent")
        said, calls = _ask(p, convo)
        ctx.check(f"(a) after 7 results: no call, the text AUTOGROUPS_DONE, got {said!r} {calls}",
                  not calls and said == AUTOGROUPS_DONE)
        t0 = time.monotonic()
        said, calls = _ask(p, [{"role": "user", "content": "RC-SUBWAIT: read report A"}])
        took = time.monotonic() - t0
        ctx.check(f"(b) a RC-SUBWAIT sub-agent answers SUB_DONE no sooner than 2.5 s, got {said!r} after {took:.2f} s",
                  not calls and said == fakes.SUB_DONE and took >= 2.5)
        msgs = [{"role": "user", "content": AUTOBUILD}]
        said, calls = _ask(p, msgs)
        build = getattr(fakes, "AUTO_BUILD_CHANGES", None)
        ctx.check(f"(c) RC-AUTOBUILD: one Builder call with AUTO_BUILD_CHANGES, got {said!r} {calls}",
                  build is not None and calls == [("Builder", {"changes": build})]
                  and [c["tool"] for c in build] == ["agent_make", "workflow_make"])
        said, calls = _ask(p, _called(msgs, calls, 1))
        ctx.check(f"(c) after its result: AUTOBUILD_DONE, got {said!r} {calls}", not calls and said == AUTOBUILD_DONE)
        msgs = [{"role": "user", "content": AUTOUSE}]
        said, calls = _ask(p, msgs)
        ctx.check(f"(d) RC-AUTOUSE: one Workflow call to review held at the gate, got {said!r} {calls}",
                  calls == [("Workflow", {"name": "review", "task": "RC-SUBHANG: fix the login bug"})])
        said, calls = _ask(p, _called(msgs, calls, 1))
        ctx.check(f"(d) after its result: AUTOUSE_DONE, got {said!r} {calls}", not calls and said == AUTOUSE_DONE)
        later = [{"role": "user", "content": AUTOGROUPS}, {"role": "assistant", "content": AUTOGROUPS_DONE},
                 {"role": "user", "content": "RC-ASK"}]
        said, calls = _ask(p, later)
        ctx.check(f"(e) a later turn RC-ASK after an RC-AUTOGROUPS turn: ANSWER, got {said!r} {calls}",
                  not calls and said == fakes.ANSWER)
        ctx.check("(f) the step and this test read the same words", [getattr(fakes, n, None) for n in (
            "AUTOGROUPS_PROMPT", "AUTOGROUPS_DONE", "AUTOBUILD_PROMPT", "AUTOBUILD_DONE", "AUTOUSE_PROMPT",
            "AUTOUSE_DONE")] == [AUTOGROUPS, AUTOGROUPS_DONE, AUTOBUILD, AUTOBUILD_DONE, AUTOUSE, AUTOUSE_DONE])
    finally:
        p.stop()


@test
def test_the_browser_stand_in_writes_the_url_it_is_asked_to_open(ctx: Ctx):
    root = Path(tempfile.mkdtemp(prefix="rc-browser-"))
    cmd, out = fakes.browser_command(root)
    url = "http://127.0.0.1:1/?mode=setup&first=1#t=abc"
    rc = subprocess.run([cmd, url], timeout=60).returncode
    ctx.check(f"exit 0 and the whole URL written down, got {fakes.opened_urls(out)}", rc == 0 and fakes.opened_urls(out) == [url])


class _StepCtx:
    """A step's ctx with no `halo` behind it: `run` answers with the text given, nothing is left running."""

    def __init__(self, repo: Path, help_text: str) -> None:
        self.repo, self.help_text = Path(repo), help_text

    def home(self, name: str):
        return name

    def run(self, h, *args, timeout: float = 60, **kw):
        out = "halo 3.6.0.0\n" if args == ("--version",) else self.help_text
        return core.Ran(0, out, "", 0.1)

    def left_after(self, h, seconds: float = 5.0) -> list:
        return []

    def end_leftovers(self, h=None) -> list:
        return []

    def ctrl_c(self) -> dict:
        return {"delivered": True, "via": "typed", "why": "", "break_works": True}


@test
def test_the_starts_step_looks_for_every_command_the_registry_lists_and_never_passes_on_none(ctx: Ctx):
    """3.6.0.0 R16 moved every command into halo_harness/cli_commands.py; the step read cli.py only and passed with
    "--help names all 0 commands" whatever the help said."""
    from halo_harness import cli_commands
    from realcheck import steps_a
    listed = [c.name for c in cli_commands.listed()]
    left_out = {c.name for c in cli_commands.COMMANDS if c.kind}
    verbs, skipped = steps_a._commands_in_source(REPO)
    ctx.check(f"every listed command is looked for ({len(listed)}), got {len(verbs)}: {verbs}",
              bool(listed) and set(listed) <= set(verbs))
    ctx.check(f"the internal and retired ones are not counted, got {skipped}",
              left_out <= set(skipped) and not left_out & set(verbs))
    full = cli_commands.help_text()
    line, _ev = steps_a.starts(_StepCtx(REPO, full))
    ctx.check(f"the real help passes and says how many, got {line!r}", f"names all {len(verbs)} commands" in line)
    short = "\n".join(n for n in listed if n not in ("local", "host"))  # (other rows' purposes say "local" too)
    try:
        steps_a.starts(_StepCtx(REPO, short))
        said = "PASS"
    except core.Fail as e:
        said = e.detail
    ctx.check(f"a help without `local` and `host` fails and names them, got {said!r}",
              said != "PASS" and "local" in said and "host" in said)
    bare = Path(tempfile.mkdtemp(prefix="rc-bare-"))
    (bare / "halo_harness").mkdir()
    (bare / "halo_harness" / "cli.py").write_text("GONE_VERBS = {\n}\n", encoding="utf-8")
    try:
        steps_a.starts(_StepCtx(bare, full))
        said = "PASS"
    except core.Fail as e:
        said = e.detail
    ctx.check(f"a tree where no command can be found fails, got {said!r}", "found no command" in said)


@test
def test_the_closing_step_fails_untagged_and_names_every_program_left(ctx: Ctx):
    """CI's Windows realcheck: "init / Ctrl+C: 16 left (pid 7796 (msedge.exe) ...) [expected until R10 lands]" -- R10 is
    in this tree, and one program per row hid whatever else was left behind the first."""
    from realcheck import steps_close
    left = ['pid 7796 (msedge.exe) "C:/x/msedge.exe" --single-argument http://127.0.0.1:1/ [scratch path]',
            "pid 7800 (msedge.exe) C:/x/msedge.exe --type=renderer [child of pid 7796]",
            "pid 7900 (python.exe) python -m halo_harness studio [scratch path in its environment]"]
    rows = {("init", "Ctrl+C"): {"target": "init", "how": "Ctrl+C", "left": left}}
    saved = steps_close.one_close, steps_close.serve_alone
    steps_close.one_close = lambda c, target, how: dict(rows.get((target, how), {"target": target, "how": how, "left": []}))
    steps_close.serve_alone = lambda c: {"target": "serve", "how": "it returned", "left": []}
    try:
        steps_close.closing(_StepCtx(REPO, ""))
        got = None
    except core.Fail as e:
        got = e
    finally:
        steps_close.one_close, steps_close.serve_alone = saved
    ctx.check(f"a leftover fails the step, got {got and got.detail!r}", got is not None and "init / Ctrl+C: 3 left" in got.detail)
    ctx.check(f"no round is named as fixing it, got {got and got.expected_until!r}", got is not None and not got.expected_until)
    ctx.check("every distinct program left is named", got is not None and "msedge.exe" in got.detail
              and "python.exe" in got.detail)


@test
def test_no_step_calls_a_failure_expected_until_a_round_that_is_in_this_tree(ctx: Ctx):
    """3.6.0.0's rounds R10-R16 are all in this tree: a FAIL tagged "expected until R1x lands" hides a real fault."""
    import ast
    tagged = []
    for f in sorted((REPO / "scripts" / "realcheck").glob("*.py")):
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if not (isinstance(node, ast.Call) and getattr(node.func, "id", "") == "Fail"):
                continue
            tags = node.args[2:3] + [k.value for k in node.keywords if k.arg == "expected_until"]
            for t in tags:
                for c in ast.walk(t):
                    if isinstance(c, ast.Constant) and isinstance(c.value, str) and c.value.startswith("R1"):
                        tagged.append(f"{f.name}:{node.lineno} {c.value}")
    ctx.check(f"no landed round named, got {tagged}", not tagged)


class _Term:
    """A terminal with nothing on it (the first-run step's `halo init` stand-in)."""
    started_at = 0.0

    def plain(self) -> str:
        return ""

    def raw(self) -> bytes:
        return b""

    def poll(self):
        return 0

    def cleanup(self) -> None:
        pass


class _FirstRunCtx(_StepCtx):
    """The first-run step's ctx: a home whose stand-in browser file is `opened`, a terminal that prints nothing."""

    def __init__(self, root: Path) -> None:
        super().__init__(REPO, "")
        self.root = root

    def home(self, name: str):
        d = self.root / name
        d.mkdir(parents=True, exist_ok=True)
        return core.Home(name, d, d, d, d, "", d / "browser-opened.txt")

    def terminal(self, h, *args, **kw):
        return _Term()

    def env(self, h, **kw) -> dict:
        return {}


def _first_run(root: Path, opened: list, address: str = "http://127.0.0.1:4321/?mode=setup&first=1#t=abc"):
    """steps_a.first_run against stand-ins: `halo init` printed `address` and its browser was asked to open `opened`
    (written into the home's stand-in file before the step looks); everything else a person would see is right."""
    from realcheck import steps_a
    ctx = _FirstRunCtx(root)
    h = ctx.home("first-run")
    if opened:
        h.opened.write_text("".join(f"1.0 {u}\n" for u in opened), encoding="utf-8")
    frame = {"ready_s": 1.0, "theme": "instrument", "top_bg": [], "beeps": {"bare": 0}, "traceback": False}
    saved = (steps_a.wait_address, steps_a.http_get, steps_a.tui_first_frame, screen.quit_with_ctrl_c,
             steps_a.BROWSER_WAIT_S if hasattr(steps_a, "BROWSER_WAIT_S") else None)
    steps_a.wait_address = lambda c, hh, t, limit=60: (address, 0.3, [])
    steps_a.http_get = lambda url, token="", timeout=10: (200, b'<html data-theme="instrument">', 0.05)
    steps_a.tui_first_frame = lambda c, hh, env=None: dict(frame, theme=(n := "instrument-ansi" if env is not None
                                                                         else "instrument"), themes=[n])
    screen.quit_with_ctrl_c = lambda t, wait=0.0: "Ctrl+C"
    steps_a.BROWSER_WAIT_S = 0.5
    try:
        return steps_a.first_run(ctx)
    except core.Fail as e:
        return e
    finally:
        steps_a.wait_address, steps_a.http_get, steps_a.tui_first_frame, screen.quit_with_ctrl_c, wait = saved
        if wait is None:
            del steps_a.BROWSER_WAIT_S
        else:
            steps_a.BROWSER_WAIT_S = wait


@test
def test_the_first_run_step_fails_when_init_never_asked_the_browser_to_open_its_page(ctx: Ctx):
    """CI's Windows realcheck: `browser_opened: []` and first-run PASS -- Halo had opened the system's own browser (a
    real one on the runner's desktop) and the step only wrote the empty list down. A step that never looks at what it
    records passes while checking nothing."""
    root = Path(tempfile.mkdtemp(prefix="rc-first-"))
    got = _first_run(root / "a", [])
    ctx.check(f"no page opened in the browser Halo was given: FAIL naming it, got {getattr(got, 'detail', got)!r}",
              isinstance(got, core.Fail) and "BROWSER" in got.detail and got.evidence.get("browser_opened") == [])
    got = _first_run(root / "b", ["http://127.0.0.1:9999/?mode=setup&first=1#t=abc"])
    ctx.check(f"a page of another address is not this Studio's: FAIL, got {getattr(got, 'detail', got)!r}",
              isinstance(got, core.Fail) and "BROWSER" in got.detail)
    got = _first_run(root / "c", ["http://127.0.0.1:4321/?mode=setup&first=1#t=abc"])
    ctx.check(f"the printed address opened in the given browser: PASS, got {getattr(got, 'detail', got)!r}",
              isinstance(got, tuple) and got[1]["browser_opened"] == ["http://127.0.0.1:4321/?mode=setup&first=1#t=abc"])


class _UpdateCtx(_StepCtx):
    """The update step's ctx: `halo update --check` prints `check`; the repo is a git checkout of two commits."""

    def __init__(self, repo: Path, check: str) -> None:
        super().__init__(repo, "")
        self.check = check

    def run(self, h, *args, timeout: float = 60, env=None, **kw):
        if args[:1] == ("update",):
            return core.Ran(0, self.check, "", 0.2)
        return core.Ran(0, "", "", 0.1)  # `halo config get update.channel`: unset

    def env(self, h, **kw) -> dict:
        return {}


def _two_commits() -> "tuple[Path, str, str]":
    """A git checkout whose second commit (the candidate) is a day after its first (the channel's head)."""
    repo = Path(tempfile.mkdtemp(prefix="rc-git-"))
    shas = []
    for n, when in ((1, "2026-11-01T10:00:00+00:00"), (2, "2026-11-02T10:00:00+00:00")):
        (repo / "f.txt").write_text(str(n), encoding="utf-8")
        env = dict(os.environ, GIT_AUTHOR_DATE=when, GIT_COMMITTER_DATE=when, GIT_AUTHOR_NAME="rc",
                   GIT_AUTHOR_EMAIL="rc@example.invalid", GIT_COMMITTER_NAME="rc", GIT_COMMITTER_EMAIL="rc@example.invalid")
        for cmd in ((["init", "-q"] if n == 1 else []), ["add", "f.txt"], ["commit", "-q", "-m", f"c{n}"]):
            if cmd:
                subprocess.run(["git", "-C", str(repo), *cmd], env=env, check=True, capture_output=True, timeout=30)
        shas.append(subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True,
                                   timeout=30).stdout.strip())
    return repo, shas[0], shas[1]


def _update_step(repo: Path, check: str):
    from realcheck import steps_c
    try:
        return steps_c.update(_UpdateCtx(repo, check))
    except (core.Fail, core.Skip) as e:
        return e


@test
def test_the_update_step_on_a_candidate_ahead_of_its_channel_judges_what_the_check_says(ctx: Ctx):
    """CI's realcheck on rc/3.6.0.0-cand, all three platforms: "update FAIL `halo update --check` (online) offers
    master, older than this build, and does not say so" -- the check said "differs from (main)", Halo's own words
    (update_cli: git confirmed the installed commit is NOT behind the offer). The step is red on every candidate
    commit, the only commits the release gate reads; an offer older than the build announced as "available" stays a
    FAIL."""
    repo, main_head, cand = _two_commits()
    said = (f"installed: halo 3.6.0.0 ({cand[:7]}, rc/3.6.0.0-cand)\n"
            f"differs from (main): {main_head[:7]}, master\n"
            "to apply: halo update  (it runs: git -C /x pull --ff-only origin main)\n")
    got = _update_step(repo, said)
    ctx.check(f"a candidate ahead of main, told \"differs from\": not a FAIL, got {getattr(got, 'detail', got)!r}",
              isinstance(got, tuple) and got[1]["online"]["offer_is_older"])
    wrong = said.replace("differs from (main)", "available (main)")
    got = _update_step(repo, wrong)
    ctx.check(f"the older commit offered as \"available\": FAIL, got {getattr(got, 'detail', got)!r}",
              isinstance(got, core.Fail) and "older than this build" in got.detail)
    newer = (f"installed: halo 3.6.0.0 ({main_head[:7]}, main)\navailable (main): {cand[:7]}, master\n"
             "to apply: halo update  (it runs: git -C /x pull --ff-only origin main)\n")
    got = _update_step(repo, newer)
    ctx.check(f"a newer commit offered as available: PASS, got {getattr(got, 'detail', got)!r}",
              isinstance(got, tuple) and not got[1]["online"]["offer_is_older"])


@test
def test_the_update_step_takes_the_same_version_sentence_as_saying_so(ctx: Ctx):
    """CI's realcheck on rc/3.6.0.1-join, the three checkout legs: "update FAIL `halo update --check` (stable) offers
    v3.6.0.0 ..., older than this build, and does not say so". The first candidate after a release still carries that
    release's version, and Halo's own sentence for it (update_cli.older_release) is "the newest release, 3.6.0.0, is
    the same version as, but not the commit of, this build ...; `halo update` would move you back": that says so. The
    same offer with no such sentence stays a FAIL."""
    repo, main_head, cand = _two_commits()
    head = (f"installed: halo 3.6.0.0 ({cand[:7]}, rc/3.6.0.1-join)\n"
            f"available (stable): {main_head[:7]}, v3.6.0.0\n")
    said = head + (f"the newest release, 3.6.0.0, is the same version as, but not the commit of, this build (3.6.0.0, "
                   f"{cand[:7]}); `halo update` would move you back. `halo update --channel main` follows the main "
                   "line; `halo update --to v3.6.0.0` moves back on purpose\n")
    got = _update_step(repo, said)
    ctx.check(f"the same version on an older commit, told it would move you back: not a FAIL, got "
              f"{getattr(got, 'detail', got)!r}", isinstance(got, tuple) and got[1]["stable"]["offer_is_older"])
    got = _update_step(repo, head + "to apply: halo update  (it runs: git -C /x pull --ff-only origin main)\n")
    ctx.check(f"the same offer with no word about it: FAIL, got {getattr(got, 'detail', got)!r}",
              isinstance(got, core.Fail) and "older than this build" in got.detail)


class _Chrome:
    """A page whose Prompt panel never shows the reply: every wait for it times out; the page reads say what is on it."""

    def __init__(self) -> None:
        self.typed = ""

    def go(self, url: str) -> None:
        pass

    def call(self, method: str, **params):
        return {}

    def click_on(self, expr: str, *a) -> None:
        pass

    def type_text(self, text: str) -> None:
        self.typed += text

    def wait(self, expr: str, timeout: float = 20):
        if "RC-ANSWER-42" in expr:
            raise TimeoutError(f"waited {timeout:.0f}s for: {expr}")
        return "sess-1" if "dataset.session" in expr else "form"

    def js(self, expr: str):
        if "prompt-text" in expr:
            return "RC-ASK from the Studio prompt"
        if "prompt-detail" in expr:
            return "Prompt sess-1 thinking..."
        return ""


@test
def test_a_studio_prompt_with_no_reply_says_what_the_panel_showed_and_whether_the_model_was_asked(ctx: Ctx):
    """CI's Linux realcheck: "a prompt from Studio's Prompt panel: TimeoutError: waited 60s" and nothing else -- not
    what the panel showed, not whether the question reached the model; four runs on a Linux VM answered in 0.1-0.3 s,
    so the next red one must carry its own evidence."""
    from realcheck import steps_b
    ev, bad = {}, []
    steps_b._prompt(_Chrome(), lambda q: q, ev, bad, asked=lambda: 0)
    p = ev.get("prompt") or {}
    ctx.check(f"a FAIL line, got {bad}", len(bad) == 1 and "TimeoutError" in bad[0])
    ctx.check(f"the panel's text and the model calls are in the evidence, got {p}",
              "RC-ASK from the Studio prompt" in str(p.get("page")) and p.get("model_calls") == 0)
    ctx.check(f"the line says the question never reached the model, got {bad}", "never reached the model" in bad[0])


@test
def test_a_section_counts_as_drawn_only_when_its_content_is_there_not_its_wrapper(ctx: Ctx):
    """Local, Setup and Packs were "drawn" as soon as `.section-view` existed (App.tsx draws it on the first render,
    before any of the section's reads answer), so their 5 s budget measured the shell: a Local or Setup whose content
    came after 30 s passed. Each section's ready test must name content the section draws once read, never a wrapper,
    and every name must be one Studio's source draws."""
    import re
    from realcheck import steps_b
    ui = REPO / "halo_harness" / "studio" / "ui" / "src"
    source = "\n".join(p.read_text(encoding="utf-8") for p in ui.rglob("*.tsx"))
    wrappers = {"agents", "flows", "crew-list", "flow-list", "local-room", "local-page", "local-resources", "setup-page",
                "setup-step-page", "pm-installed"}  # drawn before the section's own read answers
    for name, _query, ready in steps_b.SECTIONS:
        ids = re.findall(r'data-testid="([^"]+)"', ready)
        ctx.check(f"{name}: ready names content by data-testid, not the wrapper, got {ready!r}",
                  bool(ids) and ".section-view" not in ready and not set(ids) & wrappers)
        missing = [t for t in ids if f'data-testid="{t}"' not in source and f'testid="{t}"' not in source]
        ctx.check(f"{name}: every name is drawn by Studio's source, missing {missing}", not missing)


def _frame256(bg: list, fg: list) -> bytes:
    """A first frame on a 256-colour terminal: each (number, uses) as 48;5 backgrounds and 38;5 text."""
    return (b"".join(b"\x1b[48;5;%dm." % n * k for n, k in bg) + b"".join(b"\x1b[38;5;%dm." % n * k for n, k in fg))


@test
def test_the_palette_reader_names_a_256_colour_frame_and_tells_a_palette_from_its_ansi_sibling(ctx: Ctx):
    """CI's Linux realcheck: `tui_ansi = {"truecolor": false, "top_bg": [], "theme": ""}` and the step passed. The
    reader read 24-bit colours only, so on a terminal without truecolor (Apple Terminal) any palette, or none, passed.
    The frames are bare `halo`'s first frames on the Linux VM with TERM=xterm-256color and no COLORTERM."""
    fresh = screen.palette_of(_frame256([(16, 333), (59, 140), (253, 2)], [(71, 40), (231, 20), (247, 18), (226, 15),
                                                                           (244, 10), (51, 5), (80, 3), (115, 3)]))
    ctx.check(f"a fresh home's frame reads as instrument-ansi, not instrument, got {fresh}",
              not fresh["truecolor"] and "instrument-ansi" in fresh["themes"] and "instrument" not in fresh["themes"])
    forced = screen.palette_of(_frame256([(16, 337), (59, 138), (253, 2)], [(71, 40), (247, 30), (195, 20), (214, 15),
                                                                            (45, 5), (80, 3), (115, 3), (208, 2)]))
    ctx.check(f"instrument's own colours downgraded read as instrument (same background 16), got {forced}",
              forced["themes"] == ["instrument"])
    paper = screen.palette_of(_frame256([(230, 278), (59, 56), (188, 33), (224, 16)], [(241, 21), (71, 19), (94, 15),
                                                                                       (58, 6), (24, 5), (244, 4)]))
    ctx.check(f"a picked paper drawn on 256 colours reads as paper, got {paper}", paper["themes"] == ["paper"])
    cc = screen.palette_of(_frame256([(16, 289), (59, 173), (17, 14)], [(71, 40), (109, 21), (189, 20), (223, 15),
                                                                        (245, 8), (111, 5)]))
    ctx.check(f"claude-dark drawn on 256 colours reads as claude-dark, got {cc}", cc["themes"] == ["claude-dark"])
    ctx.check(f"a frame with no colour names nothing, got {screen.palette_of(b'plain')}",
              screen.palette_of(b"plain")["themes"] == [] and screen.palette_of(b"plain")["theme"] == "")
    win = screen.palette_of(b"\x1b[48;2;0;0;0mx" * 5 + b"\x1b[38;2;255;255;255my\x1b[38;2;0;255;255mz")
    ctx.check(f"the 16 colours drawn as 24-bit ones (a Windows console) read as the dark -ansi set, got {win}",
              win["truecolor"] and win["theme"] == "instrument-ansi" and "instrument" not in win["themes"]
              and "paper-ansi" not in win["themes"])


class _ThemeCtx(_FirstRunCtx):
    """The theme step's ctx over a stand-in Halo: `halo config set theme X` records X; the terminal and the page
    draw what `draws` says for the home (a terminal without truecolor is the call with an env)."""

    def __init__(self, root: Path, beats_pick: bool) -> None:
        super().__init__(root)
        self.beats_pick, self.picked = beats_pick, ""

    def run(self, h, *args, timeout: float = 60, **kw):
        if args[:3] == ("config", "set", "theme"):
            self.picked = args[3]
        return core.Ran(0, "", "", 0.1)

    def draws(self, h) -> str:
        """Halo's theme order: the pick beats a theme in Claude Code's settings, unless `beats_pick` (3.5.0's bug)."""
        f = h.home / ".claude" / "settings.json"
        cc = json.loads(f.read_text(encoding="utf-8")).get("theme") if f.is_file() else None
        return cc if (cc and self.beats_pick) or not self.picked else self.picked


def _theme_step(root: Path, beats_pick: bool, ansi_draws=None):
    from realcheck import steps_a
    c = _ThemeCtx(root, beats_pick)
    seen = {}

    def frame(cc, h, env=None):
        name = c.draws(h) if env is None or ansi_draws is None else ansi_draws
        seen.setdefault("frames", []).append("ansi" if env is not None else "truecolor")
        return {"ready_s": 1.0, "theme": name, "themes": [name] if name else [], "top_bg": [], "beeps": {"bare": 0},
                "traceback": False}
    saved = (steps_a.wait_address, steps_a.http_get, steps_a.tui_first_frame, screen.quit_with_ctrl_c)
    steps_a.wait_address = lambda cc, hh, t, limit=60: ("http://127.0.0.1:4321/#t=abc", 0.3, [])
    steps_a.http_get = lambda url, token="", timeout=10: (200, f'<html data-theme="{c.draws(c.home("theme"))}">'.encode(), 0.05)
    steps_a.tui_first_frame = frame
    screen.quit_with_ctrl_c = lambda t, wait=0.0: "Ctrl+C"
    try:
        got = steps_a.theme_pick(c)
    except core.Fail as e:
        got = e
    finally:
        steps_a.wait_address, steps_a.http_get, steps_a.tui_first_frame, screen.quit_with_ctrl_c = saved
    return got, seen


@test
def test_the_theme_step_fails_when_a_theme_in_claude_codes_settings_beats_the_one_picked_in_halo(ctx: Ctx):
    """3.5.0.1's bug: a `theme` left in Claude Code's settings files beat the one picked in Halo. The step used a fresh
    home with no Claude Code settings, so it passed with that bug back; its terminal was a truecolor one only."""
    root = Path(tempfile.mkdtemp(prefix="rc-theme-"))
    got, seen = _theme_step(root / "bug", beats_pick=True)
    ctx.check(f"Claude Code's theme drawn over the pick: FAIL naming it, got {getattr(got, 'detail', got)!r}",
              isinstance(got, core.Fail) and "claude-dark" in got.detail)
    got, seen = _theme_step(root / "ok", beats_pick=False)
    ctx.check(f"the pick drawn in the terminal and the page: PASS, got {getattr(got, 'detail', got)!r}",
              isinstance(got, tuple))
    ctx.check(f"the terminal without truecolor is looked at too, got {seen}", seen.get("frames") == ["truecolor", "ansi"])
    got, _seen = _theme_step(root / "blank", beats_pick=False, ansi_draws="")
    ctx.check(f"no palette read on the terminal without truecolor: FAIL, got {getattr(got, 'detail', got)!r}",
              isinstance(got, core.Fail) and "without truecolor" in got.detail)


# `ps -axww -o pid=,ppid=,stat=,time=,command=` and `ps -axwwE -o pid=,command=` on a Mac (a home with a space in it)
MAC_PLAIN = ("  101     1 S      0:00.10 /usr/bin/python3 -m halo_harness studio\n"
             "  102   101 S      0:00.00 /bin/sleep 600\n"
             "  103     1 Z      0:00.00 <defunct>\n"
             "  104     1 S      0:01.50 /Applications/Other.app/Contents/MacOS/Other --flag\n")
MAC_WITH_ENV = ("  101 /usr/bin/python3 -m halo_harness studio USER=dev BRIDGE_TEST_HOME=/tmp/rc home/h PATH=/usr/bin "
                "HALO_OWNER=o-1\n"
                "  102 /bin/sleep 600 HOME=/tmp/rc home/h\n"
                "  104 /Applications/Other.app/Contents/MacOS/Other --flag LANG=C\n")


@test
def test_the_mac_scan_keeps_the_command_apart_from_its_environment(ctx: Ctx):
    snap = procs._mac_parse(MAC_PLAIN, MAC_WITH_ENV)
    ctx.check(f"every live process, the zombie left out, got {sorted(snap)}", sorted(snap) == [101, 102, 104])
    s = snap[101]
    ctx.check(f"the command is the command alone, got {s.cmdline!r}", s.cmdline == "/usr/bin/python3 -m halo_harness studio")
    ctx.check(f"the environment is read from what follows it (a value with a space kept whole), got {s.env}",
              s.env == {"USER": "dev", "BRIDGE_TEST_HOME": "/tmp/rc home/h", "PATH": "/usr/bin", "HALO_OWNER": "o-1"})
    ctx.check(f"no environment word in an evidence line, got {s.short()!r}", "USER=" not in s.short() and "PATH=" not in s.short())
    ctx.check(f"names and cpu, got {[(p.name, p.cpu) for p in snap.values()]}",
              (s.name, snap[102].name, snap[104].name, s.cpu, snap[104].cpu) == ("python3", "sleep", "Other", 0.1, 1.5))
    ctx.check(f"a process -E did not list keeps its command and no environment, got {snap[104].env}",
              snap[104].env == {"LANG": "C"} and procs._mac_parse(MAC_PLAIN, "")[101].env == {})
    found = procs.belonging(dict(snap), procs.needles_for("/tmp/rc home/h"))
    whys = {pid: p.why for pid, p in found.items()}
    ctx.check(f"matched by its environment, not said to be by its command line, got {whys}",
              whys.get(101) == "scratch path in its environment" and whys.get(102) == "scratch path in its environment"
              and 104 not in whys)


def _shell_of(text: str) -> dict:
    for line in text.splitlines():
        if '"tool_calls"' in line:
            data = json.loads(line[len("data: "):] if line.startswith("data: ") else line)
            call = data["choices"][0]["delta"]["tool_calls"][0]["function"]
            return {"name": call["name"], **json.loads(call["arguments"])}
    return {}


@test
def test_the_closing_step_ends_shells_the_bash_tool_started_mid_turn_and_in_the_background(ctx: Ctx):
    from realcheck import steps_close
    from tests.helpers.mock_openai import SCENARIOS
    before = {k: SCENARIOS.get(k) for k in ("model", "realcheck")}
    p = fakes.Provider().start()
    try:
        calls = {}
        for marker in ("RC-BASH", "RC-BGBASH"):
            ask = {"model": "any/thing", "stream": True, "messages": [{"role": "user", "content": f"{marker} go"}]}
            calls[marker] = _shell_of(_post(p.base_url, ask))
            ask["messages"] += [{"role": "assistant", "content": None}, {"role": "tool", "content": "started"}]
            calls[marker + " then"] = _post(p.base_url, ask)
        fg, bg = calls["RC-BASH"], calls["RC-BGBASH"]
        ctx.check(f"RC-BASH: a Bash call holding the turn in a shell with a job in the background, got {fg}",
                  fg.get("name") == "Bash" and "sleep" in fg.get("command", "") and " & " in fg.get("command", "")
                  and not fg.get("run_in_background"))
        ctx.check(f"RC-BGBASH: a Bash call run in the background, got {bg}",
                  bg.get("name") == "Bash" and "sleep" in bg.get("command", "") and bg.get("run_in_background") is True)
        ctx.check("each turn ends once its tool answered", fakes.ANSWER in calls["RC-BASH then"]
                  and fakes.ANSWER in calls["RC-BGBASH then"])
    finally:
        p.stop()
    names = list(steps_close.TARGETS)
    ctx.check(f"a one-shot with the Bash tool mid-run and a session with a background Bash job are closed, got {names}",
              "one-shot, Bash tool mid-run" in names and "session, background Bash job" in names)
    h = type("H", (), {})()
    h.home = Path(tempfile.mkdtemp(prefix="rc-bash-"))
    args = steps_close.TARGETS["one-shot, Bash tool mid-run"][0](None, h)
    rules = json.loads((h.home / ".claude" / "settings.json").read_text(encoding="utf-8"))["permissions"]["allow"]
    ctx.check(f"the one-shot asks for RC-BASH; the home allows the command as a person would, got {args} {rules}",
              args[0] == "-p" and "RC-BASH" in args[1] and rules == ["Bash(sleep:*)"])
    shell = procs.Proc(1, 0, "sleep.exe" if sys.platform == "win32" else "sleep", "sleep 6011")
    ctx.check("up once a sleep runs under the home", steps_close._is_shell(shell)
              and not steps_close._is_shell(procs.Proc(2, 0, "python", "python -m halo_harness -p RC-BASH")))
    ctx.check("the provider put back what it borrowed", all(SCENARIOS.get(k) is v for k, v in before.items()))


def _installed_leg_problems(text: str) -> list:
    """What the realcheck CI job lacks to drive an INSTALLED halo on each system (empty: nothing)."""
    import yaml
    job = yaml.safe_load(text)["jobs"]["realcheck"]
    bad = []
    matrix = job["strategy"]["matrix"]
    if set(matrix.get("os") or []) != {"linux", "macos", "windows"} or "installed" not in (matrix.get("install") or []):
        bad.append(f"no installed leg per system: {matrix}")
    runs = [(s.get("if", ""), s.get("run", "")) for s in job["steps"]]
    inst = [r for cond, r in runs if "installed" in cond and "pip wheel" in r and "venv" in r]
    if not inst or "pip install -e" in inst[0] or "GITHUB_PATH" not in inst[0]:
        bad.append("no step builds the wheel, installs it into a fresh venv and puts its halo first on PATH")
    rc = [r for _c, r in runs if "scripts/realcheck.py" in r]
    if not rc or "--installed" not in rc[0]:
        bad.append("realcheck is never run with --installed")
    if not any("windows" in c and "installed" in c and "HALO_VENV_PY" in r and "tests.test_closing" in r
               for c, r in runs):
        bad.append("Windows never runs tests/test_closing.py with the venv's python")
    if "matrix.install" not in str(job["steps"][-1].get("with", {}).get("name", "")):
        bad.append("the two legs of one system upload under the same artifact name")
    return bad


@test
def test_ci_drives_an_installed_halo_on_every_system(ctx: Ctx):
    text = (REPO / ".github" / "workflows" / "suites.yml").read_text(encoding="utf-8")
    bad = _installed_leg_problems(text)
    ctx.check(f"a realcheck leg per system against the wheel in a fresh venv, got {bad}", bad == [])
    checkout = text.replace("        install: [checkout, installed]\n", "")
    ctx.check("the check sees a job without that leg", _installed_leg_problems(checkout) != [])


@test
def test_the_browser_steps_judge_passes_only_a_whole_clean_run(ctx: Ctx):
    """3.6.0.6 W: the `browser` step's verdict (steps_browser.judge) on what it saw: the page's text after the click in
    the reply, a PNG, no listener, nothing left after a hard and a normal end, no profile folder."""
    _main_module()
    from realcheck import fakes
    from realcheck.steps_browser import judge
    reply = f"{fakes.BROWSER_DONE} {fakes.BROWSER_AFTER}"
    ctx.check("a whole clean run passes", judge(reply, ["page-1.png"], [], [], [], []) == [])
    for args, word in (((fakes.BROWSER_DONE, ["p"], [], [], [], []), "after the click"),
                       ((reply, [], [], [], [], []), "no PNG"),
                       ((reply, ["p"], ["LISTEN 127.0.0.1:9222 pid=7,"], [], [], []), "listened"),
                       ((reply, ["p"], [], ["pid 9 (chrome)"], [], []), "hard end"),
                       ((reply, ["p"], [], [], ["pid 9 (chrome)"], []), "still ran"),
                       ((reply, ["p"], [], [], [], ["clean-1-2-3"]), "profile folder")):
        got = judge(*args)
        ctx.check(f"{word}: one problem that says so, got {got}", len(got) == 1 and word in got[0])
    got = judge(reply, ["p"], [], [], [], [], temps=["4242-1-1"])  # W batch 3 entry 1
    ctx.check(f"the browser's temp folder left: one problem that says so, got {got}",
              len(got) == 1 and "temp folder" in got[0])


def _browser_steps(m) -> list:
    """realcheck's own steps that open a browser (studio, idle-cpu), as main() would choose them."""
    return [s for s in m._steps() if s[0] in ("studio", "idle-cpu")]


@test
def test_browser_none_skips_each_browser_step_by_name_before_any_halo_or_chrome_starts(ctx: Ctx):
    """3.6.0.1: a person running realcheck on their own machine can say no browser may be used here (--browser none,
    or REALCHECK_BROWSER=none): each step that opens one is a counted SKIP that names the switch, and neither a
    `halo studio` nor a Chrome is started for it."""
    from unittest import mock
    from tests.helpers import chrome_driver
    m = _main_module()
    calls: list = []

    def no_terminal(self, *a, **k):
        calls.append("terminal")
        raise RuntimeError("a halo was started")
    with mock.patch.object(core.Ctx, "terminal", no_terminal), \
            mock.patch.object(chrome_driver, "find_chrome", lambda *a, **k: calls.append("find") or "chrome"), \
            mock.patch.object(chrome_driver, "open_chrome", lambda *a, **k: calls.append("open")), \
            mock.patch.dict(os.environ, {"REALCHECK_BROWSER": ""}):
        results, _v = m.run(_browser_steps(m), root=tempfile.mkdtemp(prefix="rc-test-"), probe_version=False,
                            say=lambda s: None, browser="none")
        got = [(r.name, r.status, r.detail) for r in results]
        ctx.check(f"both browser steps are a SKIP naming the switch, got {got}",
                  [(n, s) for n, s, _d in got] == [("studio", "SKIP"), ("idle-cpu", "SKIP")]
                  and all(d == "no browser may be used here (--browser none)" for _n, _s, d in got))
        ctx.check(f"no halo and no Chrome was started or looked for, got {calls}", calls == [])
        with mock.patch.dict(os.environ, {"REALCHECK_BROWSER": "none"}):
            results, _v = m.run(_browser_steps(m), root=tempfile.mkdtemp(prefix="rc-test-"), probe_version=False,
                                say=lambda s: None)
        got = [(r.status, r.detail) for r in results]
        ctx.check(f"REALCHECK_BROWSER=none does the same, got {got}",
                  got == [("SKIP", "no browser may be used here (REALCHECK_BROWSER=none)")] * 2 and calls == [])
    seen: dict = {}

    def fake_run(chosen, **kw):
        seen.update(kw, names=[s[0] for s in chosen])
        return [report.Result(s[0], report.SKIP, 0.0, s[1], "no browser may be used here (--browser none)")
                for s in chosen], "halo 0"
    out = io.StringIO()
    with mock.patch.object(m, "run", fake_run), redirect_stdout(out):
        rc = m.main(["--only", "studio", "idle-cpu", "--browser", "none"])
    ctx.check(f"main takes --browser and counts the steps as skipped, got rc {rc}, {seen}, {out.getvalue()!r}",
              rc == 0 and seen.get("browser") == "none" and "0 passed, 0 failed, 2 skipped" in out.getvalue())


@test
def test_session_map_step_is_a_skip_with_browser_none_before_any_halo(ctx: Ctx):
    """3.6.0.2 section 11: the step session-map opens a browser, so --browser none makes it a counted SKIP naming the
    switch, and no `halo` and no Chrome is started or looked for first."""
    from unittest import mock
    from tests.helpers import chrome_driver
    m = _main_module()
    chosen = [s for s in m._steps() if s[0] == "session-map"]
    ctx.check(f"realcheck has the step session-map, got {[s[0] for s in m._steps()]}", len(chosen) == 1)
    if len(chosen) != 1:
        return
    calls: list = []

    def no_terminal(self, *a, **k):
        calls.append("terminal")
        raise RuntimeError("a halo was started")
    with mock.patch.object(core.Ctx, "terminal", no_terminal), \
            mock.patch.object(chrome_driver, "find_chrome", lambda *a, **k: calls.append("find") or "chrome"), \
            mock.patch.object(chrome_driver, "open_chrome", lambda *a, **k: calls.append("open")), \
            mock.patch.dict(os.environ, {"REALCHECK_BROWSER": ""}):
        results, _v = m.run(chosen, root=tempfile.mkdtemp(prefix="rc-test-"), probe_version=False,
                            say=lambda s: None, browser="none")
    got = [(r.name, r.status, r.detail) for r in results]
    ctx.check(f"one SKIP naming the switch, got {got}",
              got == [("session-map", "SKIP", "no browser may be used here (--browser none)")])
    ctx.check(f"no halo and no Chrome was started or looked for, got {calls}", calls == [])


@test
def test_auto_steps_are_skips_with_browser_none_before_any_halo(ctx: Ctx):
    """3.6.0.5 section 6: the steps auto-groups and auto-ready-lines open a browser, so --browser none makes each a
    counted SKIP naming the switch, and no `halo` (not even the `halo workflows copy` of auto-ready-lines) and no Chrome
    is started or looked for first."""
    from unittest import mock
    from tests.helpers import chrome_driver
    m = _main_module()
    chosen = [s for s in m._steps() if s[0] in ("auto-groups", "auto-ready-lines")]
    ctx.check(f"realcheck has the two Auto steps, got {[s[0] for s in m._steps()]}", len(chosen) == 2)
    if len(chosen) != 2:
        return
    calls: list = []

    def no_halo(self, *a, **k):
        calls.append("halo")
        raise RuntimeError("a halo was started")
    with mock.patch.object(core.Ctx, "terminal", no_halo), mock.patch.object(core.Ctx, "run", no_halo), \
            mock.patch.object(chrome_driver, "find_chrome", lambda *a, **k: calls.append("find") or "chrome"), \
            mock.patch.object(chrome_driver, "open_chrome", lambda *a, **k: calls.append("open")), \
            mock.patch.dict(os.environ, {"REALCHECK_BROWSER": ""}):
        results, _v = m.run(chosen, root=tempfile.mkdtemp(prefix="rc-test-"), probe_version=False,
                            say=lambda s: None, browser="none")
    got = [(r.name, r.status, r.detail) for r in results]
    ctx.check(f"two SKIPs naming the switch, got {got}",
              got == [(n, "SKIP", "no browser may be used here (--browser none)")
                      for n in ("auto-groups", "auto-ready-lines")])
    ctx.check(f"no halo and no Chrome was started or looked for, got {calls}", calls == [])


def _steps_auto():
    from realcheck import steps_auto
    return steps_auto


@test
def test_auto_groups_waits_end_when_the_drawer_and_main_are_drawn(ctx: Ctx):
    """3.6.0.5 k repair: a wait of the step ends only on a true value that comes back through returnByValue (an element
    comes back as {}, which Python reads as false, so the wait ran its whole 30 s twice). Each wait expression of the
    before-any-call half is evaluated by node against a page stand-in where everything is drawn: it must give true,
    and false where nothing is drawn."""
    import shutil
    from tests.helpers.runner import SkipTest
    node = shutil.which("node")
    if not node:
        raise SkipTest("no node on this box")
    s = _steps_auto()
    exprs = {"main drawn": s.MAIN_DRAWN, "a page drawn": s._drawn_expr("live-world|map-bar")}
    js = ("const el = {dataset: {}, querySelector: () => el};"
          "const page = (drawn) => ({querySelector: () => drawn ? el : null});"
          f"const exprs = {json.dumps(exprs)}; const out = {{}};"
          "for (const [k, e] of Object.entries(exprs)) for (const drawn of [true, false]) {"
          "  const v = new Function('document', 'return (' + e + ');')(page(drawn));"
          "  out[k + (drawn ? ' / drawn' : ' / not drawn')] = JSON.parse(JSON.stringify(v === undefined ? null : v)); }"
          "process.stdout.write(JSON.stringify(out));")
    r = subprocess.run([node, "-e", js], capture_output=True, text=True, timeout=60)
    ctx.check(f"node ran the expressions, got {r.returncode}: {r.stderr[-300:]}", r.returncode == 0)
    got = json.loads(r.stdout or "{}")
    for k in exprs:
        ctx.check(f"{k}: true when drawn, got {got.get(k + ' / drawn')!r}", got.get(k + " / drawn") is True)
        ctx.check(f"{k}: false when not drawn, got {got.get(k + ' / not drawn')!r}", got.get(k + " / not drawn") is False)


# == 3.6.0.14 K1: live-scene; K2: idle-cpu with Agents -> Live open ===================================================
def _steps_live():
    from realcheck import steps_live
    return steps_live


def _no_halo_skip(ctx: Ctx, name: str) -> None:
    from unittest import mock
    from tests.helpers import chrome_driver
    m = _main_module()
    chosen = [s for s in m._steps() if s[0] == name]
    ctx.check(f"realcheck has the step {name}, got {[s[0] for s in m._steps()]}", len(chosen) == 1)
    if len(chosen) != 1:
        return
    calls: list = []

    def no_terminal(self, *a, **k):
        calls.append("terminal")
        raise RuntimeError("a halo was started")

    def no_run(self, *a, **k):
        calls.append("run")
        raise RuntimeError("a halo was run")
    with mock.patch.object(core.Ctx, "terminal", no_terminal), mock.patch.object(core.Ctx, "run", no_run), \
            mock.patch.object(chrome_driver, "find_chrome", lambda *a, **k: calls.append("find") or "chrome"), \
            mock.patch.object(chrome_driver, "open_chrome", lambda *a, **k: calls.append("open")), \
            mock.patch.dict(os.environ, {"REALCHECK_BROWSER": ""}):
        results, _v = m.run(chosen, root=tempfile.mkdtemp(prefix="rc-test-"), probe_version=False,
                            say=lambda s: None, browser="none")
    got = [(r.name, r.status, r.detail) for r in results]
    ctx.check(f"one SKIP naming the switch, got {got}",
              got == [(name, "SKIP", "no browser may be used here (--browser none)")])
    ctx.check(f"no halo and no Chrome was started or looked for, got {calls}", calls == [])


@test
def test_live_scene_step_is_a_skip_with_browser_none_before_any_halo(ctx: Ctx):
    """3.6.0.14 K1: the step live-scene opens a browser, so --browser none makes it ONE counted SKIP naming the switch,
    and no `halo` and no Chrome is started or looked for first (each patch put back by its `with`)."""
    _no_halo_skip(ctx, "live-scene")


def _live_ask(p, msgs: list, out: list) -> "threading.Thread":
    import threading
    th = threading.Thread(target=lambda: out.append(_ask(p, msgs)), daemon=True)
    th.start()
    return th


@test
def test_the_fake_provider_plays_the_live_scene(ctx: Ctx):
    """3.6.0.14 K1: RC-LIVESCENE is ONE message of four lone Agent calls and a batch of three (task, child markers,
    start order: seven helpers); its children: RC-LIVETOOL a Bash `sleep 6013`, RC-LIVEASK a Bash `mkdir rc-live-ask`,
    each SUB_DONE after its result; RC-LIVEDONE at once; RC-LIVELONG held until `release()`, then one call of the long
    MCP tool with 30 s (the server is `alwaysLoad`: main's catalog holds it, so the helper is given it), then held until
    `release_last()`; the first
    RC-LIVETEST held until `release()`, the later ones until `release_late()` (a `release()` alone leaves them held);
    `rearm()` re-arms every gate; main after five results LIVESCENE_DONE."""
    from tests.helpers.mock_openai import SCENARIOS
    before = {k: SCENARIOS.get(k) for k in ("model", "realcheck")}
    p = fakes.Provider().start()
    try:
        prompt = getattr(fakes, "LIVESCENE_PROMPT", None)
        ctx.check(f"the markers exist, got {prompt!r}", prompt == "RC-LIVESCENE: seven helpers"
                  and getattr(fakes, "LIVE_TOOL", "") == "mcp__rc_insert_chart_from_range__slow_tool")
        if prompt is None:
            return
        msgs = [{"role": "user", "content": prompt}]
        said, calls = _ask(p, msgs)
        want = [("writer", "write the changelog", ["RC-LIVEDONE: write the changelog"]),
                ("general-purpose", "survey the TODOs", ["RC-LIVETOOL: grep the TODOs"]),
                ("general-purpose", "review the money module", ["RC-LIVEASK: check pay.py"]),
                ("general-purpose", "make the chart", ["RC-LIVELONG: draw the chart"]),
                ("general-purpose", "run the tests", ["RC-LIVETEST: run the unit tests", "RC-LIVETEST: run the e2e tests",
                                                      "RC-LIVETEST: run the lint"])]
        got = [(a.get("subagent_type"), a.get("task"), [a["prompt"]] if "prompt" in a else [b.get("prompt") for b in a.get("batch") or []])
               for n, a in calls if n == "Agent"]
        ctx.check(f"ONE message of five Agent calls in order, the last a batch of three, got {said!r} {got}",
                  len(calls) == 5 and got == want and ["batch" in a for _n, a in calls] == [False] * 4 + [True])
        said, calls = _ask(p, _called(msgs, calls, 5))
        ctx.check(f"after five results: LIVESCENE_DONE, got {said!r} {calls}", not calls and said == fakes.LIVESCENE_DONE)
        for marker, tool, args in (("RC-LIVETOOL: grep the TODOs", "Bash", {"command": "sleep 6013"}),
                                   ("RC-LIVEASK: check pay.py", "Bash", {"command": "mkdir rc-live-ask"})):
            child = [{"role": "user", "content": marker}]
            said, calls = _ask(p, child)
            ctx.check(f"{marker}: one {tool} call {args}, got {calls}", len(calls) == 1 and calls[0][0] == tool
                      and all(calls[0][1].get(k) == v for k, v in args.items()))
            said, calls = _ask(p, _called(child, calls, 1))
            ctx.check(f"{marker}: SUB_DONE after its result, got {said!r}", not calls and said == fakes.SUB_DONE)
        said, calls = _ask(p, [{"role": "user", "content": "RC-LIVEDONE: write the changelog"}])
        ctx.check(f"RC-LIVEDONE answers SUB_DONE at once, got {said!r}", not calls and said == fakes.SUB_DONE)
        out: list = []
        long_out: list = []

        def held(*want) -> bool:  # the provider's own record of the calls held at a gate (no wall-clock margin)
            end = time.monotonic() + 30
            while time.monotonic() < end:
                with p._lock:
                    if sorted(p.hung) == sorted(want):
                        return True
                time.sleep(0.05)
            return False
        first = _live_ask(p, [{"role": "user", "content": "RC-LIVETEST: run the unit tests"}], out)
        ctx.check(f"the first RC-LIVETEST is held at the gate, got {p.hung}", held("RC-LIVEHOLD"))
        later = _live_ask(p, [{"role": "user", "content": "RC-LIVETEST: run the lint"}], out)
        ctx.check(f"a later RC-LIVETEST is held at the late gate, got {p.hung}", held("RC-LIVEHOLD", "RC-LIVELATE"))
        long_child = [{"role": "user", "content": "RC-LIVELONG: draw the chart"}]
        long_first = _live_ask(p, long_child, long_out)
        ctx.check(f"RC-LIVELONG's first call is held at the gate, got {p.hung}",
                  held("RC-LIVEHOLD", "RC-LIVELATE", "RC-LIVEHOLD"))
        p.release()
        for th in (first, long_first):
            th.join(30)
        calls = long_out[0][1] if long_out else []
        ctx.check(f"release(): the first tester answered SUB_DONE, the later one still held (its gate shut); RC-LIVELONG "
                  f"calls the long tool at once with 30 s (alwaysLoad: no ToolSearch), got {out} {calls}",
                  not first.is_alive() and later.is_alive() and not p.late_gate.is_set()
                  and out and out[0][0] == fakes.SUB_DONE and calls == [(fakes.LIVE_TOOL, {"seconds": 30})])
        last = _live_ask(p, _called(long_child, calls, 1), out)
        ctx.check(f"RC-LIVELONG's answer after its result is held at the last gate, got {p.hung}",
                  held("RC-LIVEHOLD", "RC-LIVELATE", "RC-LIVEHOLD", "RC-LIVELONG"))
        p.release_late()
        later.join(30)
        ctx.check("release_late(): the later tester answered; RC-LIVELONG's answer after its result still held",
                  not later.is_alive() and last.is_alive() and not p.last_gate.is_set())
        p.release_last()
        last.join(30)
        ctx.check(f"release_last(): RC-LIVELONG answered SUB_DONE, got {out}", not last.is_alive()
                  and len(out) == 3 and all(s == fakes.SUB_DONE for s, _c in out))
        p.rearm()
        again = _live_ask(p, [{"role": "user", "content": "RC-LIVETEST: run the unit tests"}], out)
        ctx.check(f"rearm(): the first tester holds again at the gate, got {p.hung}", held("RC-LIVEHOLD") and again.is_alive())
        p.release()
        again.join(10)
    finally:
        p.stop()
        ctx.check("stopped, the table holds what it held before", all(SCENARIOS.get(k) is v for k, v in before.items()))


NB = " "


def _live_scene_read() -> dict:
    """A read of Agents -> Live as the scene draws it (made-up rows): seven members, six groups, the view's foot at 800."""
    def m(raw, now, group, kind="", state=""):
        return {"raw": raw, "now": now, "kind": kind, "state": state or f"glm-5 · {raw}", "group": group}
    members = {"w1": m("done", f"done in 2{NB}s", "group:1"), "r1": m("running", "Bash · 4 s", "group:2", "tool"),
               "r2": m("running", "waiting for a model reply · 4 s", "group:2"),
               "c1": m("running", "waiting for a model reply · 1 min 02 s", "group:3"),
               "v1": m("waiting", "waiting for you · 3 s", "group:4", "wait"),
               "t1": m("queued", "queued · 4 s", "group:5", state="glm-5 · queued"),
               "g1": m("queued", "queued · 4 s", "group:6", state="queued")}
    names = ["write the changelog", "survey the TODOs", "fix the login bug", "review the money module", "run the tests",
             "make the chart"]
    counts = [f"1 agent · all done · $0.00 · 2{NB}s", "2 agents · 2 working", "1 agent · 1 working",
              "1 agent · 1 waiting on you", "1 agent · 1 queued", "1 agent · 1 queued"]
    tops = [10, 100, 260, 820, 920, 1020]
    groups = {f"group:{i}": {"name": n, "counts": c, "rect": [300, t, 200, 80]}
              for i, (n, c, t) in enumerate(zip(names, counts, tops), 1)}
    return {"members": members, "groups": groups, "view": [0, 0, 800, 800],
            "main": {"now": "Agent · 5 s", "turn": "This turn: started 5 helpers"},
            "slot": {"text": "↓ review the money module · waits on you · and 2 more groups below", "arrow": "down"},
            "lines": {"v1": "reviewer: check pay.py"}}


@test
def test_live_scene_judges_what_the_page_drew(ctx: Ctx):
    """3.6.0.14 K1 (1)-(3): each judge is a pure function of a read; the scene's read gives no failure, and each fault
    exactly its own named failure (no browser here)."""
    import copy
    s = _steps_live()
    ok = _live_scene_read()
    for name, got in (("NOW", s.judge_live_now(ok, {"x": 2, "y": 400, "over": False})), ("heads", s.judge_live_heads(ok)),
                      ("slot", s.judge_live_slot(ok, {"seen": True, "sheet": False}))):
        ctx.check(f"{name}: the scene as drawn gives no failure, got {got}", got == [])

    def one(judge, change, word, *more):
        r = copy.deepcopy(ok)
        change(r)
        got = judge(r, *more)
        ctx.check(f"{word}: exactly one failure that says so, got {got}", len(got) == 1 and word in got[0])
    one(s.judge_live_now, lambda r: r["members"]["t1"].update(now="waiting for a model reply · 3 s"), "(1)")
    one(s.judge_live_heads, lambda r: r["members"]["w1"].update(raw="stopped", now=f"stopped after 4{NB}s"),
        "1 agent · 1 stopped")
    one(s.judge_live_heads, lambda r: r["main"].update(turn="This turn: started 6 helpers"), "This turn: started 5 helpers")
    one(s.judge_live_slot, lambda r: r["slot"].update(text="↓ review the money module · waits on you"),
        "and 2 more groups below")
    one(s.judge_live_slot, lambda r: r["slot"].update(text="↓ review the money module · waits on you and 2 more below"),
        "(3) the slot reads")
    high = copy.deepcopy(ok)  # 3.6.0.15 K2 (a): the asking group drawn high (the order the page drew): the up form
    high["groups"]["group:4"]["rect"] = [300, -200, 200, 80]
    high["slot"] = {"text": "↑ review the money module · waits on you · and 2 more groups below", "arrow": "up"}
    got = s.judge_live_slot(high, {"seen": True, "sheet": False})
    ctx.check(f"(3) the asking group wholly above the view, the slot's up form: no failure, got {got}", got == [])
    got = s.judge_live_now(ok, {"x": 2, "y": 400, "over": True})
    ctx.check(f"a pointer over the drawing: exactly the not-judged line, got {got}",
              got == ["(1) not judged: the pointer at (2, 400) is over the drawing"])


@test
def test_live_scene_judges_rest_rings_sheet_and_motion(ctx: Ctx):
    """3.6.0.14 K1 (4)-(8): each judge names exactly its fault; a correct product under reduced motion passes (the
    sheet's data-unfold / data-fold are not judged there)."""
    import copy
    s = _steps_live()
    rects = {"box:main": [10, 10, 184, 120], "member:h1": [10, 200, 184, 90], "box:group:1": [10, 180, 200, 300]}
    ctx.check("(4) still: no failure", s.judge_live_rest(rects, copy.deepcopy(rects), ("", "")) == [])
    moved = copy.deepcopy(rects)
    moved["member:h1"][1] += 2
    got = s.judge_live_rest(rects, moved, ("", ""))
    ctx.check(f"(4) a rect 2 px off: one failure, got {got}", len(got) == 1 and "member:h1 moved by 2.0 px" in got[0])
    tool = fakes.LIVE_TOOL
    held = {"held": "a tool · 3 s", "whole": tool + " · 6 s", "h0": 90.0, "h1": 107.0, "h2": 107.0,
            "others0": {"member:a": 90.0}, "others2": {"member:a": 90.0}}
    ctx.check(f"(5) as drawn: no failure, got {s.judge_live_held(held)}", s.judge_live_held(held) == [])
    for change, word in ((dict(held=tool + " · 3 s"), "not 'a tool"), (dict(h1=90.0, h2=90.0), "did not grow"),
                         (dict(h2=124.0), "a second time"), (dict(others2={"member:a": 107.0}), "member:a's height")):
        got = s.judge_live_held(dict(held, **change))
        ctx.check(f"(5) {word}: one failure, got {got}", len(got) == 1 and word in got[0])
    got = s.judge_live_held(dict(held, not_given="not found: " + tool))
    ctx.check(f"(5) the helper not given the tool: exactly that line, got {got}",
              got == [f"(5) not judged: the chart's helper was not given the MCP server's tool (not found: {tool})"])
    got = s.judge_live_held(dict(held, ended_early=True))
    ctx.check(f"(5) ended early: exactly the not-judged line, got {got}",
              got == ["(5) not judged: the long tool ended before the pointer left"])
    ring = {"id": "h1", "group": "group:1", "frame": 10, "rect": [10, 200, 184, 90], "view": [0, 100, 400, 600],
            "under": "", "underGroup": "", "sheet": None, "reduced": False}
    ctx.check("(6) a ring in view: no failure", s.judge_live_rings([ring]) == [])
    for change, word in ((dict(rect=[10, 690, 184, 90]), "out of view"), (dict(under="h1"), "under the pointer"),
                         (dict(underGroup="h1"), "under the pointer"), (dict(sheet=[0, 250, 300, 300]), "under the open box"),
                         (dict(id="main"), "main's box rang")):
        got = s.judge_live_rings([dict(ring, **change)])
        ctx.check(f"(6) {word}: one failure, got {got}", len(got) == 1 and word in got[0])
    got = s.judge_live_rings([dict(ring, id=f"h{i}") for i in range(5)])
    ctx.check(f"(6) five in one frame: one failure, got {got}", len(got) == 1 and "5 rings in one frame" in got[0])
    ctx.check("(6) a reduced-motion row is (8)'s", s.judge_live_rings([dict(ring, id="main", reduced=True)]) == [])
    geo = {"side": "corner", "anchor": [300, 200, 200, 90], "view": [100, 100, 1200, 700], "words": 300}
    sheet = {"open": True, "unfold": 3, "opened": 12, "place": "sheet", "rect": [300, 200, 440, 300], "geo": geo,
             "moved": {"box:main": 0.0}, "now": "waiting for you · 4 s", "pause": [[310, 260, 76, 28]] * 4,
             "texts": ["Resume", "Pause"], "gone": True, "moved_after": {"box:main": 0.0}}
    ctx.check(f"(7) as built: no failure, got {s.judge_live_sheet(sheet)}", s.judge_live_sheet(sheet) == [])
    ctx.check("(7) clamped 8 px inside the view's left: no failure",
              s.judge_live_sheet(dict(sheet, rect=[108, 200, 440, 300], geo=dict(geo, anchor=[90, 200, 200, 90]))) == [])
    for change, word in ((dict(rect=[305, 200, 440, 300]), "corner is off"), (dict(moved={"box:main": 3.0}), "moved by 3.0"),
                         (dict(pause=[[310, 260, 76, 28]] * 3 + [[310, 262, 76, 28]]), "Pause moved after Resume"),
                         (dict(unfold=0), "did not unfold"), (dict(gone=False), "Escape did not close")):
        got = s.judge_live_sheet(dict(sheet, **change))
        ctx.check(f"(7) {word}: one failure, got {got}", len(got) == 1 and word in got[0])
    cv = {"on": "v1", "pre": True, "place": "drawer", "raw": "done", "rang0": "", "rang1": "", "rows": []}
    ctx.check("(7c) covered and quiet: no failure", s.judge_live_covered(cv) == [])
    got = s.judge_live_covered(dict(cv, rang1="1"))
    ctx.check(f"(7c) the covered tester rang: one failure, got {got}", len(got) == 1 and "rang under the open box" in got[0])
    ctx.check("(7c) no cover: exactly the not-judged line",
              s.judge_live_covered(dict(cv, pre=False)) == ["(7c) not judged: the sheet does not cover the tester"])
    red = {"open": True, "durations": ["0s", "0s"], "anims": [], "runs": [], "gone": True, "raw": "done", "rang0": "",
           "rang1": "", "rings": [], "member_anims": [], "unfold": 4, "fold": 9}
    ctx.check(f"(8) reduced as built (data-unfold / data-fold set): no failure, got {s.judge_live_reduced(red)}",
              s.judge_live_reduced(red) == [])
    for change, word in ((dict(runs=[{"sheet": True, "prop": "clip-path"}]), "a transition ran"),
                         (dict(durations=["0.16s"]), "transition-duration"), (dict(anims=["sheet-unfold"]), "the box animated"),
                         (dict(rings=[{"id": "g1", "reduced": True}]), "rang under reduced motion")):
        got = s.judge_live_reduced(dict(red, **change))
        ctx.check(f"(8) {word}: one failure, got {got}", len(got) == 1 and word in got[0])
    got = s.judge_live_sheet(dict(sheet, texts=["Pause", "Pause"]))  # 3.6.0.15 K2 (f): the button never read "Resume"
    ctx.check(f"(7) Pause never read Resume: exactly that line, got {got}",
              got == ["(7) Pause then Resume read ['Pause', 'Pause'], want ['Resume', 'Pause']"])


@test
def test_live_scene_judges_the_slot_by_where_the_asking_group_lies(ctx: Ctx):
    """3.6.0.15 K2 (a): the step reads the order the page drew (one message cannot start the lone helpers in a fixed
    order), so (3) judges the slot's down form when the asking group lies wholly below the view, its up form (letter
    for letter groupWords.ts slotWords, arrow "up") when it lies wholly above, and names the group in the view."""
    import copy
    s = _steps_live()
    ctx.check("slot_words writes the up form", s.slot_words("review the money module", 2, "up")
              == "↑ review the money module · waits on you · and 2 more groups below"
              and s.slot_words("review the money module", 0) == "↓ review the money module · waits on you")
    high = _live_scene_read()
    high["groups"]["group:4"]["rect"] = [300, -200, 200, 80]
    high["slot"] = {"text": "↑ review the money module · waits on you · and 2 more groups below", "arrow": "up"}
    ctx.check("the up form over a group wholly above: no failure", s.judge_live_slot(high, {"seen": True, "sheet": False}) == [])
    down = copy.deepcopy(high)
    down["slot"]["text"] = "↓ review the money module · waits on you · and 2 more groups below"
    got = s.judge_live_slot(down)
    ctx.check(f"the down form while the group lies above: one line naming the up form, got {got}", len(got) == 1
              and "want '↑ review the money module · waits on you · and 2 more groups below'" in got[0])
    got = s.judge_live_slot(dict(high, slot=dict(high["slot"], arrow="down")))
    ctx.check(f"the arrow 'down' while the group lies above: one line, got {got}", got == ["(3) the slot's arrow is 'down', not 'up'"])
    inview = _live_scene_read()
    inview["groups"]["group:4"]["rect"] = [300, 300, 200, 80]
    got = s.judge_live_slot(inview)
    order = ["write the changelog", "survey the TODOs", "fix the login bug", "review the money module", "run the tests",
             "make the chart"]
    ctx.check(f"the group in the view: exactly the not-judged line with the order the page drew, got {got}",
              got == [f"(3) not judged: the group 'review the money module' lies in the view at 1440 x 900 ({order})"])
    part = _live_scene_read()  # the group partly above the view, its waiting member wholly above it: the up form
    part["groups"]["group:4"]["rect"] = [300, -60, 200, 200]
    part["members"]["v1"]["rect"] = [310, -50, 180, 40]
    part["slot"] = {"text": "↑ review the money module · waits on you · and 2 more groups below", "arrow": "up"}
    got = s.judge_live_slot(part)
    ctx.check(f"the waiting member above the view (its group partly in it): the up form, got {got}", got == [])
    part["members"]["v1"]["rect"] = [310, 20, 180, 40]
    got = s.judge_live_slot(part)
    ctx.check(f"the waiting member wholly in the view: the not-judged line, got {got}", len(got) == 1 and "lies in the view" in got[0])


@test
def test_live_scene_covered_names_a_missing_member(ctx: Ctx):
    """3.6.0.15 K2 (b): (7c) never clicks an empty member id: the member to open not found is its own named line (the
    key "on" present and empty); a read without "on" is judged as before."""
    s = _steps_live()
    lines = {"w1": "writer: write the changelog"}
    got = s.judge_live_covered({"on": "", "pre": False, "lines": lines})
    ctx.check(f"no member to open: exactly the not-run line, got {got}",
              got == [f"(7c) not run: the member to open was not found in Session's drawer ({lines})"])
    ctx.check("no \"on\" key: judged as before", s.judge_live_covered({"pre": False})
              == ["(7c) not judged: the sheet does not cover the tester"])
    r = _live_scene_read()  # the testers' group:5 at top 920; group:4 (820) waits on you, group:3 (260) runs
    for x in r["members"].values():
        x["rect"] = [300, 0, 180, 60]
    got = (s.above_tests(r, ["t1"]), s.above_tests(dict(r, folded=["group:4"]), ["t1"]), s.above_tests(r, ["nobody"]))
    ctx.check(f"the member to open: of the open group drawn directly above the testers', a folded group never; none "
              f"without testers, got {got}", got == (("v1", "review the money module"), ("c1", "fix the login bug"), ("", "")))


@test
def test_live_scene_judges_the_rest_point(ctx: Ctx):
    """3.6.0.15 K2 (c): the resting point read at the rest, before the long tool is let go and with the second rects:
    off the page or not on the drawing is the STEP's failure (not judged); on it while the drawing is not held is the
    product's, with both readings."""
    s = _steps_live()
    p = {"x": 700.0, "y": 400.0, "w": 1440, "h": 900, "on": True, "held": "1", "head": 150.0}
    ctx.check("on the drawing and held: no failure", s.judge_live_rest_point([p, p, p]) == [])
    off = "(4) not judged: the resting point (700.0, 1838.0) is not on the drawing (page 1440 x 900)"
    got = s.judge_live_rest_point([dict(p, y=1838.0, on=False), p, p])
    ctx.check(f"a rest past the page: exactly the not-judged line, got {got}", got == [off])
    got = s.judge_live_rest_point([p, dict(p, y=1838.0, on=True), p])
    ctx.check(f"a point past the page counts as off even if read as on: exactly the not-judged line, got {got}", got == [off])
    got = s.judge_live_rest_point([dict(p, held=""), p, p])
    ctx.check(f"on the drawing, not held at the rest: exactly the not-held line, got {got}", got == [
        "(4) the drawing was not held under a pointer resting on it (data-held '' at the rest, '1' before the long tool "
        "was let go)"])
    ctx.check("nothing read: not judged", s.judge_live_rest_point([])[:1] == [
        "(4) not judged: the resting point was not read"])


@test
def test_live_scene_names_the_drawer_head_that_grew(ctx: Ctx):
    """3.6.0.15 K2 repair: when Session's drawer head changes height under a resting pointer (every box below it moves
    with it), (4) says so with the words that came new, so a report names the cause (a counts line that wrapped)."""
    s = _steps_live()
    p = {"x": 700.0, "y": 400.0, "w": 1440, "h": 900, "on": True, "held": "1", "head": 150.0,
         "words": "Live\n2 agents working · waiting for you · $0.0180"}
    grew = dict(p, head=167.0, words="Live\n2 agents working on mcp__rc_chart__slow_tool {\"seconds\": 9} · waiting for "
                                     "you · $0.0180")
    got = s.judge_live_rest_point([p, p, grew])
    ctx.check(f"the head grew: one line with both heights and the new words, got {got}", got == [
        "(4) Session's drawer head went from 150.0 to 167.0 px under a resting pointer (its new words: ['2 agents working "
        "on mcp__rc_chart__slow_tool {\"seconds\": 9} · waiting for you · $0.0180'])"])
    got = s.judge_live_rest_point([p, p, dict(p, head=167.0)])
    ctx.check(f"the head grew with the same words: says so, got {got}", got == [
        "(4) Session's drawer head went from 150.0 to 167.0 px under a resting pointer (its words did not change)"])
    ctx.check("the head kept its height: no line", s.judge_live_rest_point([p, p, dict(p, head=150.4)]) == [])
    got = s.judge_live_rest_point([dict(p, head=None), p, p])
    ctx.check(f"3.6.0.16: no head read at the rest: its own line, never a pass, got {got}", got == [
        "(4) Session's drawer head was not read (None at the rest, 150.0 at the last point): no .mp-down-head on the "
        "page, so its height was not checked"])
    got = s.judge_live_rest_point([p, p, {k: v for k, v in p.items() if k != "head"}])
    ctx.check(f"3.6.0.16: no head read at the last point: the same line, got {got}", got == [
        "(4) Session's drawer head was not read (150.0 at the rest, None at the last point): no .mp-down-head on the "
        "page, so its height was not checked"])


@test
def test_live_scene_waits_for_the_fold_past_the_fold_time(ctx: Ctx):
    """3.6.0.15 K2 repair: the writer's group folds FOLD_S after its end (foldRule.ts), so the scene's wait for it is the
    fold time plus the step's own wait, never the step's wait alone (a hosted runner is five to ten times slower)."""
    import re
    s = _steps_live()
    rule = (Path(__file__).resolve().parents[1] / "halo_harness/studio/ui/src/routes/crew/map/foldRule.ts").read_text(
        encoding="utf-8")
    m = re.search(r"export const FOLD_S = (\d+(?:\.\d+)?);", rule)
    ctx.check(f"foldRule.ts states FOLD_S, got {bool(m)}", bool(m))
    ctx.check(f"the step's FOLD_S is foldRule.ts's, got {getattr(s, 'FOLD_S', None)}",
              bool(m) and getattr(s, "FOLD_S", None) == float(m.group(1)))
    ctx.check(f"the fold wait is FOLD_S + LIVE_WAIT_S, got {getattr(s, 'FOLD_WAIT_S', None)}",
              getattr(s, "FOLD_WAIT_S", None) == getattr(s, "FOLD_S", 0) + s.LIVE_WAIT_S)


@test
def test_live_scene_counts_take_the_cost_as_the_page_writes_it(ctx: Ctx):
    """3.6.0.15 K2 (d): a group's cost as the page writes it since F5 ("$0.0024", "<$0.0001", and "$0.00"), in the
    all-done form and the counts form; a cost of one decimal is still wrong."""
    s = _steps_live()
    for cost in ("$0.0024", "<$0.0001", "$0.00"):
        r = _live_scene_read()
        r["groups"]["group:1"]["counts"] = f"1 agent · all done · {cost} · 2{NB}s"
        r["groups"]["group:3"]["counts"] = f"1 agent · 1 working · {cost}"
        got = s.judge_live_heads(r)
        ctx.check(f"{cost} in both forms: no failure, got {got}", got == [])
    r = _live_scene_read()
    r["groups"]["group:3"]["counts"] = "1 agent · 1 working · $0.0"
    got = s.judge_live_heads(r)
    ctx.check(f"'$0.0': one failure, got {got}", len(got) == 1 and "fix the login bug" in got[0])
    r = _live_scene_read()
    r["groups"]["group:1"]["counts"] = f"1 agent · all done · $0.0 · 2{NB}s"
    ctx.check("'$0.0' all done: one failure", len(s.judge_live_heads(r)) == 1)


@test
def test_live_scene_judges_the_mcp_tool_given_and_run(ctx: Ctx):
    """3.6.0.15 K2 (e): the chart's helper was given the server's tool at once (alwaysLoad) with ToolSearch in its
    FIRST request (F2), and the tool ran (the fake server answers "slept 30.0s": `seconds: float`); read from the
    requests the provider got."""
    s = _steps_live()
    tool = fakes.LIVE_TOOL
    tools = ["Read", tool, "ToolSearch"]
    ctx.check("given and run: no failure", s.judge_live_mcp({"tools": tools, "result": "slept 30.0s"}) == []
              and s.judge_live_mcp({"tools": tools, "result": "slept 30s"}) == [])
    got = s.judge_live_mcp({"tools": ["Read", "ToolSearch"], "result": "slept 30.0s"})
    ctx.check(f"the tool missing: exactly the not-given line, got {got}", got == [
        f"(5) the chart's helper was not given {tool} at once (alwaysLoad) with ToolSearch: ['Read', 'ToolSearch']"])
    got = s.judge_live_mcp({"tools": ["Read", tool], "result": "slept 30.0s"})
    ctx.check(f"ToolSearch missing: exactly the not-given line, got {got}", len(got) == 1 and "not given" in got[0])
    got = s.judge_live_mcp({"tools": tools, "result": "tool failed"})
    ctx.check(f"the tool did not run: exactly the not-run line, got {got}",
              got == ["(5) the long tool did not run: its result reads 'tool failed', not \"slept 30.0s\""])

    def req(user, tools=(), results=()):
        msgs = [{"role": "user", "content": user}] + [{"role": "tool", "content": x} for x in results]
        return {"body": {"messages": msgs, "tools": [{"type": "function", "function": {"name": n}} for n in tools]}}
    reqs = [req("RC-LIVESCENE: seven helpers", ["Agent"]), req("RC-LIVELONG: draw the chart", tools),
            req("RC-LIVETEST: run the lint", ["Bash"]), req("RC-LIVELONG: draw the chart", tools, ["slept 30.0s"])]
    got = s.live_mcp(reqs)
    ctx.check(f"read from the requests: the chart helper's first tools and the long tool's result, got {got}",
              got == {"tools": tools, "result": "slept 30.0s"})


@test
def test_away_is_shared_from_steps_map(ctx: Ctx):
    """3.6.0.15 K2 (g): `_away` and the wide Chrome live in steps_map.py, the module the steps share; no module of the
    check imports realcheck.steps_live for a helper; Session's spot is the page's last pixel, read from the page."""
    import re
    from realcheck import steps_map
    ctx.check("steps_map has _away and _wide_chrome", callable(getattr(steps_map, "_away", None))
              and callable(getattr(steps_map, "_wide_chrome", None)))
    here = REPO / "scripts" / "realcheck"
    live = (here / "steps_live.py").read_text(encoding="utf-8")
    ctx.check("steps_live defines neither", not re.search(r"^def (_away|_chrome|_wide_chrome)\b", live, re.M))
    users = [f.name for f in sorted(here.glob("*.py")) if f.name != "steps_live.py"
             and re.search(r"realcheck\.steps_live|from realcheck import [^\n]*\bsteps_live\b", f.read_text(encoding="utf-8"))]
    ctx.check(f"no module of the check imports steps_live, got {users}", users == [])

    class Page:
        def __init__(self):
            self.moves = []

        def js(self, expr):
            return False if "elementFromPoint" in expr else [1279, 799]

        def mouse(self, kind, x, y):
            self.moves.append((kind, x, y))
    c = Page()
    got = steps_map._away(c, "session")
    ctx.check(f"Session's spot is the page's last pixel, read from the page, got {got} {c.moves}",
              got == {"x": 1279, "y": 799, "over": False} and c.moves == [("mouseMoved", 1279, 799)])
    c = Page()
    ctx.check("Agents' spot is the rail", steps_map._away(c, "live") == {"x": 2, "y": 400, "over": False})


@test
def test_live_scene_waits_end_only_on_a_true_value(ctx: Ctx):
    """3.6.0.14 K1: every wait expression of live-scene gives true against a page stand-in where its state is drawn and
    false where it is not (an element comes back through returnByValue as {}, which never ends a wait: 3.6.0.5)."""
    import shutil
    from tests.helpers.runner import SkipTest
    node = shutil.which("node")
    if not node:
        raise SkipTest("no node on this box")
    s = _steps_live()
    # 3.6.0.15 K4 (b): the wait for the server's note is read on the terminal (TERMINAL), not on a page
    exprs = {k: v for k, v in s.waits().items() if k not in s.TERMINAL}
    ctx.check(f"(1) waits for the done member's NOW as drawn (the done time may reach the page after the done state), "
              f"got {sorted(exprs)}", "done_now" in exprs)
    ctx.check(f"3.6.0.15 K2 (a): the wait for the writer's all-done group to fold is listed, got {sorted(exprs)}",
              "folded" in exprs)
    js = ("const el = (o = {}) => ({dataset: o.dataset || {}, textContent: o.text ?? '', clientTop: 0, clientLeft: 0,"
          " clientHeight: 100, clientWidth: 100, getBoundingClientRect: () => { const [l, t, w, h] = o.rect || [0, 0, 100, 100];"
          " return {left: l, top: t, width: w, height: h, right: l + w, bottom: t + h}; },"
          " querySelector: (x) => (o.q || {})[x] ?? null, querySelectorAll: (x) => (o.all || {})[x] ?? []});"
          "const doc = (q) => ({querySelector: (x) => q[x] ?? null});"
          "const mem = (o = {}) => Object.assign(el({dataset: {raw: o.raw || 'running'}, rect: o.rect || [10, 10, 50, 40],"
          " q: {':scope > [data-testid=map-member-now]': el({text: o.now || ''})}}),"
          " {closest: (x) => (x === '[data-box]' ? {hasAttribute: (a) => a === 'data-folded' && !!o.folded} : null)});"
          "const root = (m, all) => el({q: {'[data-member=\"a1\"]': m, '[data-member]': m}, all: {'[data-member]': all || []}});"
          "const raws = (xs) => xs.map((r) => el({dataset: {raw: r}}));"
          "const sheet = (w) => el({q: {'[data-testid=map-step-in-pause]': el({text: ' ' + w + ' '})}});"
          f"const SCENE = {json.dumps(s.SCENE_RAWS)}, TOOL = {json.dumps(fakes.LIVE_TOOL)}, K = '[data-testid=map-step-in][data-open]';"
          "const pages = {drawn: [doc({'#root': root(null, raws(SCENE))}), doc({'#root': root(null, raws(SCENE.slice(1)))})],"
          " live: [doc({'#root': root(mem())}), doc({'#root': root(null)})],"
          " done_now: [doc({'#root': root(null, [mem({raw: 'done', now: 'done in 2\\u00a0s'}), mem()])}),"
          "  doc({'#root': root(null, [mem({raw: 'done', now: ''}), mem()])})],"
          " drawer: [doc({'[data-testid=session-lit-map]': el()}), doc({})], open: [doc({[K]: el()}), doc({})],"
          " gone: [doc({}), doc({'.mp-step-in': el()})],"
          " held: [doc({'#root': root(mem({now: 'a tool · 3 s'}))}), doc({'#root': root(mem({now: 'Bash · 3 s'}))})],"
          " whole: [doc({'#root': root(mem({now: TOOL + ' · 3 s'}))}), doc({'#root': root(mem({now: 'a tool · 3 s'}))})],"
          " raw: [doc({'#root': root(mem({raw: 'done'}))}), doc({'#root': root(mem({raw: 'running'}))})],"
          " folded: [doc({'#root': root(mem({raw: 'done', folded: true}))}), doc({'#root': root(mem({raw: 'done'}))})],"
          " seen: [doc({'#root': root(mem()), '#scroll': el()}), doc({'#root': root(mem({rect: [10, 80, 50, 40]})), '#scroll': el()})],"
          " resume: [doc({[K]: sheet('Resume')}), doc({[K]: sheet('Pause')})],"
          " pause: [doc({[K]: sheet('Pause')}), doc({[K]: sheet('Resume')})]};"
          f"const exprs = {json.dumps(exprs)}; const out = {{}};"
          "for (const [k, e] of Object.entries(exprs)) { const p = pages[k] || []; for (const [i, d] of p.entries()) {"
          "  const v = new Function('document', 'return (' + e + ');')(d);"
          "  out[k + (i ? ' / not drawn' : ' / drawn')] = JSON.parse(JSON.stringify(v === undefined ? null : v)); } }"
          "process.stdout.write(JSON.stringify(out));")
    r = subprocess.run([node, "-e", js], capture_output=True, text=True, timeout=60)
    ctx.check(f"node ran the expressions, got {r.returncode}: {r.stderr[-300:]}", r.returncode == 0)
    got = json.loads(r.stdout or "{}")
    for k in exprs:
        ctx.check(f"{k}: true when drawn, got {got.get(k + ' / drawn')!r}", got.get(k + " / drawn") is True)
        ctx.check(f"{k}: false when not drawn, got {got.get(k + ' / not drawn')!r}", got.get(k + " / not drawn") is False)


@test
def test_live_scene_hands_the_chart_out_after_the_server_connected(ctx: Ctx):
    """3.6.0.15 K4 (b): the scene's one task (it hands the chart out) is typed only once the terminal said its MCP server
    is in, in the words halo_harness/mcp/manager.py writes; the wait is listed in waits() and read on the terminal; a run
    where the note never came fails with that as its named reason and types nothing (never "Unknown tool")."""
    from types import SimpleNamespace
    s = _steps_live()
    exprs = s.waits()
    ctx.check(f"the server's wait is listed and read on the terminal, got {exprs.get('server')!r} / {getattr(s, 'TERMINAL', None)}",
              exprs.get("server") == "mcp: 1 server(s) connected" and "server" in s.TERMINAL)
    src = (REPO / "halo_harness" / "mcp" / "manager.py").read_text(encoding="utf-8")
    ctx.check("the words are the manager's note", "line = (f\"mcp: {len(out['connected'])} server(s) connected\"" in src)
    ctx.check("the note read in a terminal's text, wrapped or not",
              s.server_in("halo\nmcp: 1 server(s) connected\n") and s.server_in("mcp: 1\n server(s) connected")
              and not s.server_in("mcp: 0 server(s) connected, 1 failed"))

    class Term:
        def __init__(self, text: str):
            self.text, self.waited, self.started_at = text, [], time.monotonic()

        def wait_for(self, pred, timeout: float) -> bool:
            self.waited.append(timeout)
            return bool(pred(self.text))

        def plain(self) -> str:
            return self.text  # no way to type: a step that typed here would raise
    t, ev, bad = Term("halo · Auto · ready"), {}, []
    try:
        s._scene(SimpleNamespace(provider=None), None, t, ev, bad)
        raised = ""
    except Exception as e:
        raised = f"{type(e).__name__}: {e}"
    ctx.check(f"no note: one failure naming it, nothing typed, got {bad} / {raised}",
              not raised and len(bad) == 1 and "never said 'mcp: 1 server(s) connected'" in bad[0]
              and "Unknown tool" not in bad[0] and ev.get("server_s") is None and t.waited == [s.SERVER_WAIT_S])
    ctx.check("the note said: the wait ends with its seconds", s.server_wait(Term("mcp: 1 server(s) connected")) is not None)


@test
def test_auto_groups_reads_a_folded_groups_members_from_its_card(ctx: Ctx):
    """3.6.0.15 K4 (a): (6) takes, per member, "Why this model:" read in its hover (an open group) OR in its group's card,
    its row chosen (a folded group: LW folds an all-done group to its head, OP4's card lists every member), and names
    where; a member read nowhere is a failure that says so; every wait (6) makes ends only on a true value."""
    import shutil
    s = _steps_auto()
    why = "Why this model: code work"
    card = ["fix the login bug", "2 agents · all done · $0.0180 · 40 s", why]
    seen = {"m0": {"group": "1", "hover": "researcher · glm-5 · working\n" + why},
            "m1": "researcher · glm-5 · working\n" + why,
            **{f"m{i}": {"group": "2", "card": card} for i in range(2, 7)}}
    ctx.check(f"hover or card: no failure, got {s.judge_why(seen)}", s.judge_why(seen) == [])
    where = {k: s.why_where(v) for k, v in seen.items()}
    ctx.check(f"each member says where it was read, got {where}",
              where == {"m0": "hover", "m1": "hover", **{f"m{i}": "card" for i in range(2, 7)}})
    got = s.judge_why(dict(seen, m3={"group": "2", "card": card[:2]}))
    ctx.check(f"a folded member whose card has no such line: one failure naming it and the card, got {got}",
              len(got) == 1 and "m3" in got[0] and "folded group 2" in got[0] and "card" in got[0])
    got = s.judge_why(dict(seen, m3={"group": "2", "card": ["the reviewer said: " + why]}))
    ctx.check(f"the words inside another line are not the card's line, got {got}", len(got) == 1 and "m3" in got[0])
    got = s.judge_why(dict(seen, m4={"group": "2", "card_note": "no card opened in 5 s at a click on the group's head"}))
    ctx.check(f"a card that never opened is named, got {got}", len(got) == 1 and "no card opened" in got[0])
    got = s.judge_why(dict(seen, m0={"group": "1", "hover": ""}))
    ctx.check(f"an open member with an empty hover is named, got {got}", len(got) == 1 and "the hover of the member m0" in got[0])
    node = shutil.which("node")
    if not node:
        return
    exprs = s.why_waits()
    js = ("const el = (o = {}) => ({dataset: o.dataset || {}, hasAttribute: (a) => (o.attrs || []).includes(a),"
          " querySelector: (x) => (o.q || {})[x] ?? null, querySelectorAll: (x) => (o.all || {})[x] ?? []});"
          "const doc = (q) => ({querySelector: (x) => q[x] ?? null});"
          "const MAP = '[data-testid=session-lit-map]', G1 = '[data-testid=session-map-group][data-group=\"1\"]',"
          " K = '[data-testid=map-step-in][data-open]', R = '[data-testid=map-step-in-row]';"
          "const map = (g) => el({q: {[G1]: g}}), card = (rows) => el({all: {[R]: rows}});"
          "const pages = {folded: [doc({[MAP]: map(el({attrs: ['data-folded']}))}), doc({[MAP]: map(el())})],"
          " open: [doc({[K]: el()}), doc({})],"
          " chosen: [doc({[K]: card([el({dataset: {key: 'h|s|a0'}}), el({dataset: {key: 'h|s|a1'}, attrs: ['data-chosen']})])}),"
          "  doc({[K]: card([el({dataset: {key: 'h|s|a0'}, attrs: ['data-chosen']}), el({dataset: {key: 'h|s|a1'}})])})],"
          " gone: [doc({}), doc({'.mp-step-in': el()})]};"
          f"const exprs = {json.dumps(exprs)}; const out = {{}};"
          "for (const [k, e] of Object.entries(exprs)) { for (const [i, d] of (pages[k] || []).entries()) {"
          "  const v = new Function('document', 'return (' + e + ');')(d);"
          "  out[k + (i ? ' / not drawn' : ' / drawn')] = JSON.parse(JSON.stringify(v === undefined ? null : v)); } }"
          "process.stdout.write(JSON.stringify(out));")
    r = subprocess.run([node, "-e", js], capture_output=True, text=True, timeout=60)
    ctx.check(f"node ran the expressions, got {r.returncode}: {r.stderr[-300:]}", r.returncode == 0)
    out = json.loads(r.stdout or "{}")
    for k in exprs:
        ctx.check(f"{k}: true when drawn, got {out.get(k + ' / drawn')!r}", out.get(k + " / drawn") is True)
        ctx.check(f"{k}: false when not drawn, got {out.get(k + ' / not drawn')!r}", out.get(k + " / not drawn") is False)


def _steps_made():
    from realcheck import steps_made
    return steps_made


@test
def test_made_at_once_step_is_a_skip_with_browser_none_before_any_halo(ctx: Ctx):
    """3.6.0.15 K1: the step made-at-once opens a browser, so --browser none makes it ONE counted SKIP naming the switch,
    and no `halo` and no Chrome is started or looked for first."""
    _no_halo_skip(ctx, "made-at-once")


@test
def test_the_fake_provider_plays_made_at_once(ctx: Ctx):
    """3.6.0.15 K1: RC-MADE: one Agent call of the built-in Judge, after its result one of `judge`, after that MADE_DONE;
    the Judge's child (RC-MADEJ1) is held until `release()`, judge's (RC-MADEJ2) answers at once; RC-NOTED: NOTED_DONE
    (a later turn: RC-MADE is not played again); `with_model` lists the second model and plays the script for it, and
    its put-back (and `stop`) leave the models list and the scenario table as they were."""
    from tests.helpers.mock_openai import SCENARIOS
    keys = ("model", "realcheck", "realcheck-judge")
    before = {k: SCENARIOS.get(k, "<none>") for k in keys}
    p = fakes.Provider().start()
    try:
        prompt = getattr(fakes, "MADE_PROMPT", None)
        ctx.check(f"the markers exist, got {prompt!r}", prompt == "RC-MADE: judge the draft, then again"
                  and getattr(fakes, "MADE_DONE", "") == "RC-MADE-DONE" and getattr(fakes, "NOTED_PROMPT", "") ==
                  "RC-NOTED: anything new?" and getattr(fakes, "NOTED_DONE", "") == "RC-NOTED-DONE"
                  and getattr(fakes, "JUDGE_MODEL", "") == "mock/realcheck-judge")
        if prompt is None:
            return
        msgs = [{"role": "user", "content": prompt}]
        said, calls = _ask(p, msgs)
        ctx.check(f"first: one Agent call of the built-in Judge, got {said!r} {calls}", calls == [("Agent", {
            "subagent_type": "Judge", "description": "judge the draft", "prompt": "RC-MADEJ1: judge the draft"})])
        msgs = _called(msgs, calls, 1)
        said, calls = _ask(p, msgs)
        ctx.check(f"after one result: one Agent call of judge, got {said!r} {calls}", calls == [("Agent", {
            "subagent_type": "judge", "description": "judge it again", "prompt": "RC-MADEJ2: judge it again"})])
        msgs = _called(msgs, calls, 1)
        said, calls = _ask(p, msgs)
        ctx.check(f"after two results: MADE_DONE, got {said!r} {calls}", not calls and said == fakes.MADE_DONE)
        said, calls = _ask(p, msgs + [{"role": "assistant", "content": said},
                                      {"role": "user", "content": fakes.NOTED_PROMPT}])
        ctx.check(f"a later RC-NOTED turn: NOTED_DONE, got {said!r} {calls}", not calls and said == fakes.NOTED_DONE)
        # 3.6.0.19: the turn after the save has its own words; (d)'s done word is never the answer of (c)'s turn
        said, calls = _ask(p, msgs + [{"role": "assistant", "content": fakes.MADE_DONE},
                                      {"role": "user", "content": fakes.NOTED_PROMPT},
                                      {"role": "assistant", "content": fakes.NOTED_DONE},
                                      {"role": "user", "content": getattr(fakes, "SAVED_PROMPT", "RC-SAVED: missing")}])
        ctx.check(f"a RC-SAVED turn after it: SAVED_DONE, its own word, got {said!r} {calls}",
                  not calls and said == getattr(fakes, "SAVED_DONE", None) and fakes.NOTED_DONE not in said)
        out: list = []
        held = _live_ask(p, [{"role": "user", "content": "RC-MADEJ1: judge the draft"}], out)
        end = time.monotonic() + 30
        while time.monotonic() < end and "RC-MADEHOLD" not in p.hung:
            time.sleep(0.05)
        ctx.check(f"RC-MADEJ1 is held at the gate, got {p.hung}", p.hung == ["RC-MADEHOLD"] and held.is_alive())
        said, calls = _ask(p, [{"role": "user", "content": "RC-MADEJ2: judge it again"}])
        ctx.check(f"RC-MADEJ2 answers SUB_DONE at once, got {said!r}", not calls and said == fakes.SUB_DONE)
        p.release()
        held.join(30)
        ctx.check(f"release(): RC-MADEJ1 answers SUB_DONE, got {out}", not held.is_alive() and out
                  and out[0][0] == fakes.SUB_DONE)
        models = p.mock.models_response
        put_back = p.with_model(fakes.JUDGE_MODEL)
        ids = [m.get("id") for m in p.mock.models_response.get("data") or []]
        ctx.check(f"with_model lists the second model beside the first, got {ids}",
                  ids == ["mock/realcheck", "mock/realcheck-judge"] and SCENARIOS.get("realcheck-judge") == p._answer)
        said, calls = _stream(_post(p.base_url, {"model": fakes.JUDGE_MODEL, "stream": True, "messages": [
            {"role": "user", "content": "RC-MADEJ2: judge it again"}]}))
        ctx.check(f"a call on the second model plays the same script, got {said!r}", said == fakes.SUB_DONE)
        put_back()
        ctx.check("the put-back leaves the models list and the scenario as they were",
                  p.mock.models_response is models and SCENARIOS.get("realcheck-judge", "<none>") == before["realcheck-judge"])
    finally:
        p.stop()
    after = {k: SCENARIOS.get(k, "<none>") for k in keys}
    ctx.check(f"the scenario table holds what it held before, got {after}", after == before)


@test
def test_made_at_once_reads_the_words_that_ship(ctx: Ctx):
    """3.6.0.15 K1: every line the step judges is the product's own, letter for letter (studio/crew_model_api.py for a
    BUILT-IN in a session that takes it now, crew/kinds_note.py N1 / N2); the name a Judge pick writes in an empty home
    is `judge`. If these differ, the step's words are wrong, never the product's."""
    import shutil
    from unittest import mock
    from halo_harness.crew import kinds_note as kn
    from halo_harness.crew.spec import agent_spec
    from halo_harness.studio import crew_model_api as cm
    d = _steps_made()
    ref = "or:mock/realcheck-judge"
    ctx.check("LINE_NOW is the BUILT-IN line of a session that takes it now",
              d.LINE_NOW == cm.LINES[(cm.BUILTIN, True)].format(X="Judge", name="judge", card=""))
    ctx.check("KEEPS is the product's, and KEEPS_RE reads it with any model",
              d.KEEPS == cm.KEEPS and d.KEEPS_RE.fullmatch(cm.KEEPS.format(model="or:mock/realcheck")) is not None)
    ctx.check("MADE is MADE_NOW for judge", d.MADE.format(ref=ref) == cm.MADE_NOW.format(name="judge", model=ref))
    ctx.check("TAKEN is TAKEN_BACK for judge", d.TAKEN == cm.TAKEN_BACK.format(name="judge"))
    sorter = agent_spec({"format": "agent/1", "name": "sorter", "does": d.SORTER_DOES, "model": "auto"})
    ctx.check(f"N1_SORTER is n1 for sorter, got {kn.n1('sorter', sorter)!r}", d.N1_SORTER == kn.n1("sorter", sorter))
    ctx.check("N2_JUDGE is N2_GONE for judge", d.N2_JUDGE == kn.N2_GONE.format(name="judge"))
    ctx.check("N1_JUDGE_RE reads N1 and N1_BARE for judge, not another name",
              d.N1_JUDGE_RE.fullmatch(kn.N1.format(name="judge", words="pass or fail a result")) is not None
              and d.N1_JUDGE_RE.fullmatch(kn.N1_BARE.format(name="judge")) is not None
              and not d.N1_JUDGE_RE.search(kn.N1_BARE.format(name="judge-2")))
    tmp = Path(tempfile.mkdtemp(prefix="rc-made-"))
    try:
        (tmp / "state").mkdir()
        (tmp / "proj").mkdir()
        with mock.patch.dict(os.environ, {"BRIDGE_STATE_DIR": str(tmp / "state")}):
            name = cm.name_of(cm.BUILTIN, {}, {}, {"name": "Judge"}, tmp / "proj", tmp / "proj")
        ctx.check(f"a Judge pick in an empty home writes judge, got {name!r}", name == "judge")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _made_req(model: str, users: list, tools: bool = True) -> dict:
    body = {"model": model, "messages": [{"role": "user", "content": u} for u in users]}
    if tools:
        body["tools"] = [{"type": "function", "function": {"name": "Agent"}}]
    return {"method": "POST", "path": "/chat/completions", "body": body}


@test
def test_made_at_once_judges_what_it_read(ctx: Ctx):
    """3.6.0.15 K1: the step's judges are pure: a read as built gives no line; each fault gives exactly its own line."""
    d = _steps_made()
    ref = "or:mock/realcheck-judge"
    block = {"kind": "BUILT-IN", "before": [d.LINE_NOW, "This helper keeps or:mock/realcheck until it ends."],
             "after": [d.MADE.format(ref=ref)], "undo_word": "Undo", "ref": ref, "file": True, "file_model": ref}
    ctx.check(f"(a) as built: nothing, got {d.judge_made_block(block)}", d.judge_made_block(block) == [])
    for change, head in (({"kind": "ROUTED"}, "(a) the block's kind is 'ROUTED'"),
                         ({"before": [d.LINE_NOW]}, "(a) before the pick the block reads"),
                         ({"after": ["Not saved: no."]}, "(a) after the pick the block reads"),
                         ({"undo_word": ""}, "(a) no Undo after the pick"),
                         ({"file": False}, "(a) judge.yaml was not written as his agent on " + ref),
                         ({"file_model": "auto"}, "(a) judge.yaml was not written as his agent on " + ref)):
        got = d.judge_made_block({**block, **change})
        ctx.check(f"(a) {change}: exactly its line, got {got}", len(got) == 1 and got[0].startswith(head))
    n1 = "[Halo] A new helper you can start now: judge (pass or fail a result)."
    main = fakes.MADE_PROMPT

    def raw(first_main=(main, n1), early=(main,), j2="mock/realcheck-judge", title=False) -> list:
        out = [_made_req("x/main", list(early)), _made_req("x/main", ["RC-MADEJ1: judge the draft"])]
        if title:
            out.append(_made_req("x/main", [main], tools=False))  # a call with no tools (a title): not main's turn
        out.append(_made_req("x/main", list(first_main)))
        if j2:
            out.append(_made_req(j2, ["RC-MADEJ2: judge it again"]))
        return out
    reqs = d.made_reqs(raw(), 2)
    ctx.check(f"made_reqs tags main, the Judge's and judge's calls and the pick's mark, got "
              f"{[(r['who'], r['after']) for r in reqs]}",
              [(r["who"], r["after"]) for r in reqs] == [("main", False), ("j1", False), ("main", True), ("j2", True)])
    ctx.check(f"(b) as built: nothing, got {d.judge_made_requests(reqs, ref)}", d.judge_made_requests(reqs, ref) == [])
    titled = d.made_reqs(raw(title=True), 2)
    ctx.check("(b) a call with no tools is not main's", d.judge_made_requests(titled, ref) == []
              and [r["who"] for r in titled][2] == "")
    for kw, head in (({"early": (main, n1)}, "(b) a request before the pick carried N1 for judge"),
                     ({"first_main": (main,)}, "(b) main's first request after the pick does not carry N1 for judge"),
                     ({"first_main": (main, n1, n1)}, "(b) main's first request after the pick carries N1 for judge 2 times"),
                     ({"j2": ""}, "(b) main never started judge (no request of RC-MADEJ2)"),
                     ({"j2": "x/main"}, "(b) judge's request went to 'x/main', not the picked 'or:mock/realcheck-judge'")):
        got = d.judge_made_requests(d.made_reqs(raw(**kw), 2), ref)
        ctx.check(f"(b) {kw}: exactly its line, got {got}", len(got) == 1 and got[0].startswith(head))
    n2 = "[Halo] Taken back: judge can no longer be started in this session."
    undo = {"rows": [d.TAKEN], "file": False, "reqs": d.made_reqs([_made_req("x/main", [main, n1, fakes.NOTED_PROMPT, n2])], 0)}
    ctx.check(f"(d) as built: nothing, got {d.judge_made_undo(undo)}", d.judge_made_undo(undo) == [])
    for change, head in (({"rows": ["Not undone: no."]}, "(d) after Undo the block reads"),
                         ({"file": True}, "(d) judge.yaml is still there after Undo"),
                         ({"reqs": d.made_reqs([_made_req("x/main", [main, fakes.NOTED_PROMPT])], 0)},
                          "(d) main's first request after Undo does not carry N2 for judge"),
                         ({"reqs": d.made_reqs([_made_req("x/main", [main, n2, n2])], 0)},
                          "(d) main's first request after Undo carries N2 for judge 2 times")):
        got = d.judge_made_undo({**undo, **change})
        ctx.check(f"(d) {list(change)}: exactly its line, got {got}", len(got) == 1 and got[0].startswith(head))
    save = {"note": "Saved sorter.", "live": [{"session_id": "s-1", "took": True, "why": ""}],
            "reqs": d.made_reqs([_made_req("x/main", [main, fakes.NOTED_PROMPT, d.N1_SORTER])], 0)}
    ctx.check(f"(c) as built: nothing, got {d.judge_made_save(save, 's-1')}", d.judge_made_save(save, "s-1") == [])
    for change, head in (({"note": "Not saved yet."}, '(c) the form did not say "Saved sorter."'),
                         ({"live": [{"session_id": "s-1", "took": False, "why": "unreached"}]},
                          "(c) the save's answer does not say this session took sorter"),
                         ({"live": [{"session_id": "s-2", "took": True, "why": ""}]},
                          "(c) the save's answer does not say this session took sorter"),
                         ({"reqs": d.made_reqs([_made_req("x/main", [main, fakes.NOTED_PROMPT])], 0)},
                          "(c) main's first request after the save does not carry N1 for sorter")):
        got = d.judge_made_save({**save, **change}, "s-1")
        ctx.check(f"(c) {list(change)}: exactly its line, got {got}", len(got) == 1 and got[0].startswith(head))


@test
def test_made_at_once_waits_end_only_on_a_true_value(ctx: Ctx):
    """3.6.0.15 K1: every wait expression of made-at-once gives true against a page stand-in where its state is drawn and
    false where it is not (an element comes back through returnByValue as {}, which never ends a wait), the wait for the
    picker's row of the second model among them (its rows come from a live read, after the search box)."""
    import shutil
    from tests.helpers.runner import SkipTest
    node = shutil.which("node")
    if not node:
        raise SkipTest("no node on this box")
    exprs = _steps_made().waits()
    ctx.check(f"the picker's row wait and the form's waits are listed, got {sorted(exprs)}",
              {"member", "open", "toggle", "content", "listed", "row", "changed", "gone", "new", "form", "note", "saved"} <= set(exprs))
    js = ("const el = (o = {}) => ({dataset: o.dataset || {}, textContent: o.text ?? '', value: o.value ?? '',"
          " querySelector: (x) => (o.q || {})[x] ?? null, querySelectorAll: (x) => (o.all || {})[x] ?? [],"
          " closest: (x) => (o.up || {})[x] ?? null});"
          "const doc = (q) => ({querySelector: (x) => q[x] ?? null});"
          "const ROOT = '[data-testid=session-lit-map]', K = '[data-testid=map-step-in][data-open]';"
          "const mem = (raw, line) => el({dataset: {raw, member: 'a1'}, q: {'[data-testid=map-member-line]': el({text: line})}});"
          "const lines = (xs) => el({all: {'[data-testid=map-step-in-model-line] p': xs.map((t) => el({text: t}))}});"
          "const content = (kind, xs) => Object.assign(lines(xs), {dataset: kind ? {kind} : {}});"
          "const row = el({dataset: {ref: 'or:mock/realcheck-judge'}});"
          "const field = (r, fresh = null) => { const f = el({q: {'[data-testid$=\"-row\"][data-ref$=\"realcheck-judge\"]': r,"
          " '[data-testid=model-select-refresh]:not([disabled])': fresh}}); f.closest = (x) => (x === '.msel' ? f : null); return f; };"
          "const sheet = (o = {}) => el({q: {'[data-testid=map-step-in-model-toggle]': o.toggle ?? null,"
          " '[data-testid=map-step-in-model-content]': o.content ?? null, '[data-testid=map-step-in-model-select]': o.field ?? null}});"
          "const win = (calls) => ({__rcm: {calls}});"
          "const post = (body) => ({method: 'POST', path: '/api/crew/agent/sorter', status: 200, body});"
          "const pages = {"
          " member: [doc({[ROOT]: el({all: {'[data-member]': [mem('running', 'Judge: judge the draft')]}})}),"
          "  doc({[ROOT]: el({all: {'[data-member]': [mem('done', 'Judge: judge the draft')]}})})],"
          " open: [doc({[K]: sheet()}), doc({})],"
          " toggle: [doc({[K]: sheet({toggle: el()})}), doc({[K]: sheet()})],"
          " content: [doc({[K]: sheet({content: content('BUILT-IN', ['a', 'b'])})}),"
          "  doc({[K]: sheet({content: content('', [\"Reading this helper's agent...\"])})})],"
          " row: [doc({[K]: sheet({field: field(row)})}), doc({[K]: sheet({field: field(null, el())})})],"
          " listed: [doc({[K]: sheet({field: field(null, el())})}), doc({[K]: sheet({field: field(null)})})],"
          " changed: [doc({[K]: sheet({content: content('BUILT-IN', ['y'])})}), doc({[K]: sheet({content: content('BUILT-IN', ['x'])})})],"
          " gone: [doc({}), doc({'.mp-step-in': el()})],"
          " new: [doc({'[data-testid=crew-empty-new]': el()}), doc({})],"
          " form: [doc({'[data-testid=crew-form]': el()}), doc({})],"
          " note: [doc({'[data-testid=crew-note]': el({text: 'Saved sorter.'})}), doc({'[data-testid=crew-note]': el({text: 'Not saved yet.'})})],"
          " saved: [[doc({}), win([post({live: []})])], [doc({}), win([post(null)])]]};"
          f"const exprs = {json.dumps(exprs)}; const out = {{}};"
          "for (const [k, e] of Object.entries(exprs)) { const p = pages[k] || []; for (const [i, d] of p.entries()) {"
          "  const [dd, w] = Array.isArray(d) ? d : [d, {}];"
          "  let v; try { v = new Function('document', 'window', 'return (' + e + ');')(dd, w); } catch (err) { v = 'threw: ' + err; }"
          "  out[k + (i ? ' / not drawn' : ' / drawn')] = JSON.parse(JSON.stringify(v === undefined ? null : v)); } }"
          "process.stdout.write(JSON.stringify(out));")
    r = subprocess.run([node, "-e", js], capture_output=True, text=True, timeout=60)
    ctx.check(f"node ran the expressions, got {r.returncode}: {r.stderr[-300:]}", r.returncode == 0)
    got = json.loads(r.stdout or "{}")
    for k in exprs:
        ctx.check(f"{k}: true when drawn, got {got.get(k + ' / drawn')!r}", got.get(k + " / drawn") is True)
        ctx.check(f"{k}: false when not drawn, got {got.get(k + ' / not drawn')!r}", got.get(k + " / not drawn") is False)


@test
def test_idle_cpu_judges_the_share_and_the_timers(ctx: Ctx):
    """3.6.0.14 K2: steps_close.judge_idle is pure: the share against 5% and the page's live interval timers A (before
    Live), B (with it), C (box open), D (closed), E (after the minute), each fault exactly its own line."""
    from realcheck import steps_close as z
    live = getattr(z, "LIVE_INTERVALS", None)
    ctx.check("the pin LIVE_INTERVALS exists", isinstance(live, int))
    if live is None:
        return
    a = [1000, 15000, 2000]
    b = a + [1000] * live
    ok = {"A": a, "B": b, "C": list(b), "D": list(b), "E": list(b)}
    ctx.check(f"share 0.049, counts as before: no failure, got {z.judge_idle(0.049, ok, live)}", z.judge_idle(0.049, ok, live) == [])
    got = z.judge_idle(0.05, ok, live)
    ctx.check(f"share 0.05: the share's line alone, got {got}",
              got == ["an idle Studio with Agents -> Live open used 5.0% of one core over 60s (budget 5%)"])
    for k, line in (("C", "the open sheet added 1 interval timer"), ("D", "the closed sheet left 1 interval timer"),
                    ("E", "the idle minute ended with 1 interval timer more")):
        got = z.judge_idle(0.01, dict(ok, **{k: b + [500]}), live)
        ctx.check(f"{k} = B + 1: exactly {line!r}, got {got}", got == [line])
    got = z.judge_idle(0.01, dict(ok, A=a[1:]), live)
    ctx.check(f"B - A = LIVE_INTERVALS + 1: Live's line naming both, got {got}",
              got == [f"Agents -> Live added {live + 1} interval timer{'' if live + 1 == 1 else 's'}; before the drawing "
                      f"it added {live}"])
    got = z.judge_idle(0.01, dict(ok, C=None), live)
    ctx.check(f"a count missing: exactly the hook's line, got {got}", got == ["the page's timers could not be counted"])


@test
def test_idle_cpu_budget_follows_the_speed_factor_measured_in_the_same_run(ctx: Ctx):
    """3.6.0.21 T3/T4: tests/helpers/cpu_factor.py: the factor is the work's time over the reference, never under 1,
    at most 4; idle-cpu's 5% is times it, and its line names the factor when it is not 1; a busy page (tens of
    percent of a core) still fails at the cap; the helper's own measure runs here and gives a time."""
    from tests.helpers import cpu_factor as cf
    from realcheck import steps_close as z
    r = cf.REFERENCE_S
    for measured, want in ((r / 2, 1.0), (r, 1.0), (r * 1.3, 1.3), (r * 2, 2.0), (r * 10, 4.0), (0.0, 1.0)):
        ctx.check(f"factor of {measured:.3f} s against {r} s is {want}, got {cf.factor(measured)}", cf.factor(measured) == want)
    m = cf.measure(1)
    ctx.check(f"measure() gives a positive CPU time, got {m}", isinstance(m, float) and m > 0)
    f = cf.factor()
    ctx.check(f"factor() measured now is in [1, 4], got {f}", 1.0 <= f <= cf.CAP)
    ctx.check("said() names the factor only when it is not 1",
              cf.said("5%", 1.0) == "5%" and cf.said("5%", 1.3) == "5% x 1.3 for this machine's speed")
    live = z.LIVE_INTERVALS
    a = [1000, 15000, 2000]
    b = a + [1000] * live
    ok = {"A": a, "B": b, "C": list(b), "D": list(b), "E": list(b)}
    ctx.check("6.1% with a factor of 1.3: within 6.5%", z.judge_idle(0.061, ok, live, 60.0, 1.3) == [])
    got = z.judge_idle(0.07, ok, live, 60.0, 1.3)
    ctx.check(f"7% with a factor of 1.3: the share's line naming the factor, got {got}",
              got == ["an idle Studio with Agents -> Live open used 7.0% of one core over 60s "
                      "(budget 5% x 1.3 for this machine's speed)"])
    for busy in (0.2, 0.3, 0.6):
        got = z.judge_idle(busy, ok, live, 60.0, cf.factor(r * 100))
        ctx.check(f"a busy page at {busy:.0%} of a core fails even at the cap, got {got}", len(got) == 1 and "x 4" in got[0])


@test
def test_idle_cpu_reads_count_a_only_once_the_session_row_is_drawn(ctx: Ctx):
    """3.6.0.14 K2 (the checker): Session's row of the session not drawn within the wait is a FAIL that says so; count A
    is never read off a page in another state (stand-ins for the terminal, the page and steps_map's helpers, each put
    back in a `finally`)."""
    from types import SimpleNamespace
    from realcheck import steps_close as z, steps_map
    from realcheck.core import Fail
    read: list = []

    class Page:
        def go(self, url): pass

        def wait(self, expr, timeout):
            raise TimeoutError(expr)

        def js(self, expr):
            read.append(expr)
            return []

        def call(self, *a, **k):
            return {}
    term =SimpleNamespace(wait_for=lambda f, t: True, plain=lambda: "")
    sctx = SimpleNamespace(terminal=lambda h, cols=0, rows=0: term)
    saved = (screen.tui_ready, steps_map._followed, steps_map._started, steps_map._say)
    screen.tui_ready = lambda s, t: True
    steps_map._followed = lambda c, ev, bad, sid: True
    steps_map._started = lambda h: "s1"
    steps_map._say = lambda t, text: None
    got = ""
    try:
        z._idle_page(sctx, None, Page(), "http://127.0.0.1:1/#t=abc", {}, {})
    except Fail as e:
        got = str(e)
    finally:
        screen.tui_ready, steps_map._followed, steps_map._started, steps_map._say = saved
    ctx.check(f"no row drawn: a FAIL naming the session's row, count A never read, got {got!r} {read}",
              "session's row" in got and z.COUNT not in read)


@test
def test_idle_cpu_interval_hook_counts_live_timers(ctx: Ctx):
    """3.6.0.14 K2: steps_close.INTERVALS in node against a stand-in window: two set (1000, 15000), one cleared -> one
    live timer of 1000; the hook evaluated twice wraps once; a clear of an id never set changes nothing."""
    import shutil
    from tests.helpers.runner import SkipTest
    from realcheck import steps_close as z
    node = shutil.which("node")
    if not node:
        raise SkipTest("no node on this box")
    hook, count = getattr(z, "INTERVALS", ""), getattr(z, "COUNT", "")
    ctx.check("INTERVALS and COUNT exist", bool(hook and count))
    if not (hook and count):
        return
    js = ("let next = 1; const window = {setInterval: () => next++, clearInterval: () => undefined};"
          f"const hook = new Function('window', {json.dumps(hook)}), count = new Function('window', 'return ' + {json.dumps(count)});"
          "hook(window); window.setInterval(() => 0, 1000); const b = window.setInterval(() => 0, 15000); window.clearInterval(b);"
          "hook(window); window.clearInterval(999);"
          "process.stdout.write(JSON.stringify(count(window)));")
    r = subprocess.run([node, "-e", js], capture_output=True, text=True, timeout=60)
    ctx.check(f"node ran the hook, got {r.returncode}: {r.stderr[-300:]}", r.returncode == 0)
    ctx.check(f"one live timer of 1000 ms, got {r.stdout!r}", json.loads(r.stdout or "null") == [1000])


def _scene2_read() -> "tuple[dict, dict, list, dict]":
    """(the groups' read, group 1's first record, the line records, the lines at the end) as scene 2 draws them."""
    s = _steps_auto()
    cols = {"1": "rgb(1, 1, 1)", "2": "rgb(2, 2, 2)", "3": "rgb(3, 3, 3)", "4": "rgb(4, 4, 4)"}
    lines = {1: ["researcher: read report A", "researcher: read report B", "researcher: read report C"],
             2: ["coder: fix the login bug", "reviewer: review the fix"], 3: ["general-purpose: summarize the notes"],
             4: ["general-purpose: list the open bugs"]}
    groups = [{"n": str(n), "colour": str(n), "top": 10 + 100 * (n - 1), "bottom": 90 + 100 * (n - 1), "name": name,
               "border": cols[str(n)], "own": cols[str(n)], "members": lines[n]} for n, name, _a in s.GROUPS]
    read = {"groups": groups, "probes": {"--accent": "rgb(9, 9, 9)", "--warn": "rgb(8, 8, 8)", "--ok": "rgb(7, 7, 7)",
                                         "--bad": "rgb(6, 6, 6)"}}
    records = [{"to": f"group:{n}", "lit": "live", "hops": 0} for n in (1, 2, 3, 4)] + [
        {"to": f"group:{n}", "lit": "trace", "hops": 1} for n in (1, 2, 3, 4)]
    last = {f"group:{n}": {"lit": "trace", "hops": 1} for n in (1, 2, 3, 4)}
    return read, {"top": 10, "members": 3, "name": "compare the three reports"}, records, last


@test
def test_auto_groups_judges_what_the_page_drew(ctx: Ctx):
    """3.6.0.5 section 6: each judge of auto-groups is a pure function of what the page drew: a read as scene 2 draws
    it gives no failure, and each fault gives exactly its own named failure (no browser here)."""
    import copy
    s = _steps_auto()
    w15 = ("This session runs on Auto (the default), as it started at 10:24. Main picks who works on each task; each "
           "task shows as a named, coloured group.")
    pages = [{"page": n, "drawn": True, "starter": []} for n, _q, _i in s.PAGES]
    pages[0]["live"] = {"map": "auto", "groups": 0}
    before = {"map": "auto", "boxes": ["main"], "groups": 0, "truth": w15, "pages": pages}
    read, first, records, last = _scene2_read()
    rec = {"spawn": 1000.0, "full": 1000.0 + 1000 * (s.GROUP_FIRST_S - 1), "first": {"1": first}, "lines": 8}
    live = {"map": "auto", "main": 300.0, "groups": [{"n": str(n), "name": name, "left": 320.0} for n, name, _a in s.GROUPS]}
    why = {f"m{i}": "researcher · glm-5 · working\nWhy this model: code work" for i in range(7)}
    cut = {"small": [], "cut": []}

    def lines_all(recs, lst):
        return [x for n in (1, 2, 3, 4) for x in s.judge_lines(recs, lst, n)]
    ok = (s.judge_before(before) + s.judge_record(rec) + s.judge_groups(read, first) + lines_all(records, last)
          + s.judge_why(why) + s.judge_cut(cut) + s.judge_live(live))
    ctx.check(f"scene 2 as drawn: no failure, got {ok}", ok == [])

    def one(name: str, got: list, word: str) -> None:
        ctx.check(f"{name}: exactly one failure naming {word!r}, got {got}", len(got) == 1 and word in got[0])

    b = copy.deepcopy(before)
    b["map"] = "starter"
    one("a drawer with data-map starter", s.judge_before(b), "'starter', not auto")
    b = copy.deepcopy(before)
    b["boxes"] = ["main", "planner"]
    one("a second box beside main", s.judge_before(b), "not main alone")
    b = copy.deepcopy(before)
    b["pages"][1]["starter"] = ["Pick a map: starter (the default)"]
    one("a page text with starter (the default)", s.judge_before(b), "Agents: Map says starter")
    b = copy.deepcopy(before)
    b["pages"][-1]["starter"] = ["Running: starter (the default)"]
    one("the Session page's text with starter (the default)", s.judge_before(b), "Session says starter")
    g = copy.deepcopy(read)
    g["groups"][1]["top"] = g["groups"][0]["bottom"] - 1
    one("group 2's top 1 px above group 1's bottom", s.judge_groups(g, first), "above group 1's bottom")
    one("group 1's top 1 px off its first top", s.judge_groups(read, dict(first, top=11)), "group 1 moved")
    g = copy.deepcopy(read)
    g["groups"][0]["members"] = g["groups"][0]["members"][:2]
    one("a group with 2 members where 3 are due", s.judge_groups(g, first), "group 1 holds")
    g = copy.deepcopy(read)
    g["groups"][0]["border"] = g["groups"][0]["own"] = read["probes"]["--accent"]
    one("a border equal to the --accent probe", s.judge_groups(g, first), "--accent")
    g = copy.deepcopy(read)
    g["groups"][1]["members"].reverse()
    one("reviewer before coder in group 2", s.judge_groups(g, first), "group 2 holds ['reviewer', 'coder']")
    r = [x for x in records if not (x["to"] == "group:2" and x["lit"] == "live")]
    one("a line never live", lines_all(r, last), "group 2 was never drawn live")
    lst = dict(last, **{"group:3": {"lit": "trace", "hops": 0}})
    one("a line with hops 0 at the end", lines_all(records, lst), "0 hand-off(s)")
    w = dict(why, m3="coder · glm-5 · working")
    one("a member's hover without WHY", s.judge_why(w), "m3")
    one("a text of 11.5 px", s.judge_cut({"small": [["mp-member-line", 11.5]], "cut": []}), "11.5 px")
    one("a member with scrollHeight 40 over clientHeight 38",
        s.judge_cut({"small": [], "cut": [["mp-member", 40, 38, 100, 100]]}), "is cut")
    lv = copy.deepcopy(live)
    lv["groups"][2]["left"] = 299.0
    one("a Live group 1 px left of main's right", s.judge_live(lv), "group 3's left")
    got = s.judge_record({"spawn": 0, "full": 2000.0, "first": {"1": first}, "lines": 8})
    one("a recorder that saw no spawn frame", got, "nothing of the first spawn frame")
    got = s.judge_record({"spawn": 0, "full": 0, "first": {}, "lines": 0})
    ctx.check(f"a recorder that saw nothing: one failure per thing it missed, got {got}",
              len(got) == 4 and all("recorder saw nothing" in x for x in got))
    ctx.check("no recorder at all is a failure", len(s.judge_record(None)) == 1)
    late = dict(rec, full=rec["spawn"] + 1000 * (s.GROUP_FIRST_S + 0.1))
    one("group 1 full GROUP_FIRST_S + 0.1 s after the spawn frame", s.judge_record(late), "after the first spawn frame")


def _boxed(text: str, width: int = 80) -> str:
    """`text` wrapped at `width` columns inside box-drawing characters, as a terminal card draws it."""
    import textwrap
    return "\n".join("│ " + line.ljust(width - 4) + " │" for line in textwrap.wrap(text, width - 4))


@test
def test_auto_ready_lines_reads_the_card_and_the_lines_in_any_wrap(ctx: Ctx):
    """3.6.0.5 section 6: auto-ready-lines reads A15 and the line through a wrap and box-drawing characters; P1 counts
    only in the Builder card's header (between its '⏺' and its '✓' status row), alone (3.6.0.15 U4: the card's agent is
    ready now too, so one line names both); a map row or a use row, A15 with another agent, a second line or a pair
    each give their named failure (no browser here)."""
    s = _steps_auto()
    card = "⏺ Builder: apply these 2 changes?\n" + _boxed(s.A15) + "\n" + _boxed("Make the agent checker") + "\n"
    ctx.check(f"the card wrapped at 80 columns: no failure, got {s.judge_card(card)}", s.judge_card(card) == [])
    got = s.judge_card(card + _boxed("Make a new map review-flow"))
    ctx.check(f"a map row: its failure, got {got}", len(got) == 1 and "Make a new map" in got[0])
    got = s.judge_card(card + _boxed("New sessions run on review-flow."))
    ctx.check(f"a use row: its failure, got {got}", len(got) == 1 and "New sessions run on" in got[0])
    got = s.judge_card(card.replace("checker)", "reviewer)"))
    ctx.check(f"A15 with reviewer for checker: its failure, got {got}", len(got) == 1 and "does not say" in got[0])
    head = "⏺ Builder(2 changes)\n"
    body = _boxed("Written: the agent checker, the workflow review. Undo: u1.") + "\n"
    folded = head + _boxed(s.P1) + "\n  ✓ done · 0.4 s\n" + body
    ctx.check(f"P1 in the header, wrapped: no failure, got {s.judge_ready_lines(folded)}",
              s.judge_ready_lines(folded) == [])
    old = "Ready in this session now: the workflow review."
    got = s.judge_ready_lines(head + _boxed(old) + "\n  ✓ done\n")
    ctx.check(f"P1 without the agent: its failure, got {got}", len(got) == 1 and "does not say" in got[0])
    p2 = "Saved for your next session: the agent checker (this session's list of agents was fixed when it started)."
    got = s.judge_ready_lines(head + _boxed(s.P1) + "\n" + _boxed(p2) + "\n  ✓ done\n")
    ctx.check(f"a P2 after P1 in the header: its failure, got {got}", len(got) == 1 and "another ready line" in got[0])
    got = s.judge_ready_lines(head + "  ✓ done · 0.4 s\n" + body + _boxed(s.P1) + "\n")
    ctx.check(f"P1 only in the body, below the status row: its failure, got {got}",
              len(got) == 1 and "body, not its header" in got[0])
    good = {"head": s.H1, "buttons": [s.OPEN_WF], "lines": [s.P1], "pair": False, "map": "auto"}
    ctx.check(f"the head as t draws it: no failure, got {s.judge_head(good)}", s.judge_head(good) == [])
    for name, bad, word in (("a head read with starter for the map", dict(good, map="starter"), "'starter'"),
                            ("a second ready line", dict(good, lines=[s.P1, s.P1]), "not P1 alone"),
                            ("a pair", dict(good, pair=True), "pair")):
        got = s.judge_head(bad)
        ctx.check(f"{name}: its failure, got {got}", len(got) == 1 and word in got[0])
    # k/batch02 entry 3 rewrote this half to the truth: a group below the fold is a failure only when the slot does not
    # name it or its press does not bring it up (test_auto_ready_lines_use_it_now_in_view_or_named_and_brought_up)
    use = _use_read(s)
    ctx.check(f"the workflow's group in view: no failure, got {s.judge_use(use)}", s.judge_use(use) == [])
    got = s.judge_use(dict(use, rect=[10, 700, 400, 820]))
    ctx.check(f"a group below the drawing's fold the slot does not name: its failure, got {got}",
              len(got) == 1 and "slot does not name it" in got[0])


@test
def test_auto_ready_lines_waits_a_turn_its_budget_and_says_a_turn_still_running_alone(ctx: Ctx):
    """3.6.0.21 T2: step (2)'s waits are the turn's budget on a slow runner (TURN_S, never 30 s), and a turn still running
    when it runs out is ONE line saying so, never also "the folded card does not say P1"; a turn that ended with P1
    missing still fails on the card's words (a stand-in terminal: each wait answers at once and records its bound)."""
    from realcheck import fakes
    s = _steps_auto()
    head = "⏺ Builder(2 changes)\n"
    folded = head + _boxed(s.P1) + "\n  ✓ done · 0.4 s\n"

    class Term:
        def __init__(self, text: str):
            self.text, self.waits = text, []

        def plain(self) -> str:
            return self.text

        def wait_for(self, pred, timeout):
            self.waits.append(timeout)
            return bool(pred(self.text))

    for name, text, want in (
            ("the card folded, the turn ended", folded + fakes.AUTOBUILD_DONE, []),
            ("the turn still running, the card unfolded", head + "⠦ tool Builder 45 s", ["turn never ended in", "not judged"]),
            ("the card folded, the turn still running", folded, ["turn never ended in"]),
            ("the turn ended, P1 missing", head + "  ✓ done\n" + fakes.AUTOBUILD_DONE, ["does not say"])):
        t, bad = Term(text), []
        s._folded(t, 0, {}, bad)
        ctx.check(f"{name}: exactly {want or 'no failure'}, got {bad}",
                  len(bad) == len(want[:1]) and all(w in (bad[0] if bad else "") for w in want))
        ctx.check(f"{name}: no turn's wait shorter than TURN_S ({s.TURN_S}), got {t.waits}",
                  max(t.waits) >= s.TURN_S and all(w in (s.TURN_S, 15) for w in t.waits))
        if bad and "turn never ended" in bad[0]:
            ctx.check(f"{name}: the line names the budget, got {bad[0]!r}", f"{s.TURN_S:.0f} s" in bad[0])


_STILL ={"head": [0, 40, 1280, 96], "main": [190, 140, 374, 247], "draw": [100, 12, 184, 107]}


def _use_read(s, **kw) -> dict:
    """What "use it now" reads (steps_auto.USE_READ and STILL_READ): the workflow's group in view, nothing moved."""
    return {"found": True, "map": "auto", "name": s.USE_HEAD, "group": "2", "rect": [10, 100, 400, 180],
            "visible": [0, 60, 1280, 800], "slot": None, "before": dict(_STILL), "after": dict(_STILL), **kw}


@test
def test_auto_ready_lines_use_it_now_in_view_or_named_and_brought_up(ctx: Ctx):
    """k/batch02 entry 3: after "use it now" the workflow's group is in the drawing with its name and step line word for
    word, and EITHER wholly inside the visible box OR named by the slot with ONE press putting its head at the top within
    1 s; the head and main's box did not move (nor main in the drawing with the press); the room is put on record (the
    visible box's height, the group's height) and a failure says it."""
    s = _steps_auto()
    view = _use_read(s)
    ctx.check(f"in view: no failure, got {s.judge_use(view)}", s.judge_use(view) == [])
    below = dict(view, rect=[10, 700, 400, 820], visible=[0, 640, 1280, 780])
    slot = {"text": "↓ workflow review · working · and 1 more group below", "group": "2"}
    pressed = dict(below, slot=slot, press={"top": 340.5, "d": 0.2}, pressed=dict(_STILL))
    ctx.check(f"below the fold, named by the slot, up in 340 ms, nothing moved: no failure, got {s.judge_use(pressed)}",
              s.judge_use(pressed) == [])
    ctx.check(f"the room on record, got {s.use_room(pressed)}", s.use_room(pressed) == {"visible_h": 140, "group_h": 120})
    for name, read, word in (
            ("below the fold, no slot", below, "slot does not name it"),
            ("the slot names another group", dict(pressed, slot=dict(slot, group="1")), "slot does not name it"),
            ("the slot names another name", dict(pressed, slot=dict(slot, text="↓ part 2 · working")), "slot does not name it"),
            ("the press took 1.5 s", dict(pressed, press={"top": 1500.0, "d": 0.0}), "within 1 s"),
            ("the press never brought it up", dict(pressed, press={"top": None, "d": 212.0}), "within 1 s"),
            ("the press moved main in the drawing", dict(pressed, pressed=dict(_STILL, draw=[100, 12, 184, 56])), "in the drawing"),
            ("the head moved with use it now", dict(view, after=dict(_STILL, head=[0, 40, 1280, 120])), "the head"),
            ("main's box moved with use it now", dict(view, after=dict(_STILL, main=[190, 140, 374, 196])), "main's box"),
            ("the step line is not step 1 of 2", dict(view, name="workflow review · step 2 of 2"), "named"),
            ("the drawer is not on auto", dict(view, map="my-map"), "not auto")):
        got = s.judge_use(read)
        ctx.check(f"{name}: one failure saying {word!r}, got {got}", len(got) == 1 and word in got[0])
    got = s.judge_use(dict(pressed, slot=None))
    ctx.check(f"a failure out of sight puts the room on record, got {got}", got and "140 px" in got[0] and "120 px" in got[0])
    ctx.check(f"no group at all: its failure, got {s.judge_use({'found': False, 'names': []})}",
              len(s.judge_use({"found": False, "names": []})) == 1)


class _UsePage:
    """The page of "use it now" stood in for: USE_READ answers from `reads` one read at a time (the last one stays),
    STILL_READ answers `still`; the press lands at once; every call is logged."""

    def __init__(self, s, reads: list, still) -> None:
        self.s, self.reads, self.still, self.calls, self.clicks = s, list(reads), still, [], 0

    def js(self, expr: str):
        self.calls.append(expr)
        if expr == self.s.USE_READ:
            return dict(self.reads.pop(0) if len(self.reads) > 1 else self.reads[0])
        if expr == self.s.STILL_READ:
            return dict(self.still) if self.still is not None else {}
        if expr == self.s.NEXT_FRAME:
            return 1
        return None

    def click_on(self, expr: str, *a) -> None:
        self.clicks += 1

    def wait(self, expr: str, timeout: float = 20):
        return {"top": 33.0, "d": 0.0} if expr == self.s.PRESS_DONE else True


@test
def test_use_it_now_polls_until_the_slot_names_the_group(ctx: Ctx):
    """r/batch02 entry 1: "use it now" waits by polling ONE of two facts (the group wholly inside the drawing's visible
    box, or the slot naming it), not by a fixed half-second sleep and one read: a slot that names the group only at its
    THIRD read is still judged named, pressed and landed; when neither fact arrives in the bound the failure names both
    and what the slot read last; no fixed sleep is left in the two checks (steps_auto `_use` / `use_now`, the VM
    driver's `use`)."""
    import ast
    s = _steps_auto()
    below = dict(_use_read(s), rect=[10, 700, 400, 820], visible=[0, 640, 1280, 780])
    del below["before"], below["after"]
    named = dict(below, slot={"text": "↓ workflow review · working", "group": "2"})
    page = _UsePage(s, [below, below, named], _STILL)
    got = s.use_now(page, dict(_STILL), wait_s=5)
    reads = page.calls.count(s.USE_READ)
    ctx.check(f"it read the page three times, a frame between reads, got {reads} reads, "
              f"{page.calls.count(s.NEXT_FRAME)} frames", reads == 3 and page.calls.count(s.NEXT_FRAME) >= 2)
    ctx.check(f"the slot named it at the third read: ONE press, got {page.clicks}", page.clicks == 1)
    ctx.check(f"named, pressed, landed: no failure, got {s.judge_use(got)}", s.judge_use(got) == [])
    never = _UsePage(s, [dict(below, slot={"text": "↓ part 2 · working", "group": "1"})], _STILL)
    got = s.use_now(never, dict(_STILL), wait_s=0.3)
    says = s.judge_use(got)
    ctx.check(f"neither fact in the bound: one failure naming both facts and the slot's last words, got {says}",
              len(says) == 1 and "wholly inside the drawing's visible box" in says[0] and "the slot naming it" in says[0]
              and "↓ part 2 · working" in says[0] and never.clicks == 0)
    inside = _UsePage(s, [_use_read(s)], _STILL)
    got = s.use_now(inside, dict(_STILL), wait_s=5)
    ctx.check(f"in view at the first read: one read, no press, no failure, got {inside.calls.count(s.USE_READ)} reads, "
              f"{s.judge_use(got)}", inside.calls.count(s.USE_READ) == 1 and inside.clicks == 0 and s.judge_use(got) == [])
    for path, names in ((REPO / "scripts" / "realcheck" / "steps_auto.py", ("_use", "use_now", "still_now")),
                        (REPO / "tests" / "helpers" / "studio_auto.py", ("use",))):
        text = path.read_text(encoding="utf-8")
        for node in ast.parse(text).body:
            if isinstance(node, ast.FunctionDef) and node.name in names:
                src = ast.get_source_segment(text, node) or ""
                ctx.check(f"{path.name} {node.name}: no fixed sleep", "time.sleep(" not in src)


@test
def test_use_it_now_a_missing_head_is_never_standing_still(ctx: Ctx):
    """r/batch02 entry 1: a rect that is missing is never "the same": when the head over the drawing is found neither
    before nor after "use it now" (or only on one side), judge_use FAILS and says the head was not found."""
    s = _steps_auto()
    view = _use_read(s)
    no_head = dict(_STILL, head=None)
    for name, read in (("before and after", dict(view, before=dict(no_head), after=dict(no_head))),
                       ("before", dict(view, before=dict(no_head))),
                       ("after", dict(view, after=dict(no_head)))):
        got = s.judge_use(read)
        ctx.check(f"the head missing {name}: one failure saying the head was not found, got {got}",
                  len(got) == 1 and "the head was not found" in got[0])
    pressed = dict(view, rect=[10, 700, 400, 820], visible=[0, 640, 1280, 780],
                   slot={"text": "↓ workflow review · working", "group": "2"}, press={"top": 30.0, "d": 0.0},
                   pressed=dict(_STILL, draw=None))
    got = s.judge_use(pressed)
    ctx.check(f"main missing from the drawing after the press: its failure, got {got}",
              len(got) == 1 and "not found" in got[0])


@test
def test_auto_steps_read_the_words_that_ship(ctx: Ctx):
    """3.6.0.5 section 6: one place for the words: the step's A15 is the product's FIRST_WORKFLOW_AUTO for this card,
    and its P1 is what ready_now.p_lines gives for this card's answer (ready review; the agent checker ready too, its
    put took: 3.6.0.15 U4). If they differ, the step's words are wrong, never the product's."""
    from halo_harness.crew import map_facts, ready_now
    s = _steps_auto()
    a15 = map_facts.FIRST_WORKFLOW_AUTO.format(words="review", W="review", steps="coder, then checker")
    ctx.check(f"A15 is the product's, got {s.A15!r} vs {a15!r}", s.A15 == a15)
    answer = {"ready": ["review"], "ready_agents": ["checker"], "later": [], "p3": []}
    lines = ready_now.p_lines(answer)
    ctx.check(f"P1 is the product's, got {[s.P1]} vs {lines}", [s.P1] == lines and not hasattr(s, "P2"))


@test
def test_session_map_reads_the_card_by_section_4_words_in_either_case(ctx: Ctx):
    """3.6.0.2 section 4: the card's question is "Builder: apply these {n} changes?" (the base says "Apply these N
    changes? ..."). The step finds the card by either, reads its three rows through a wrap, and calls the use row
    ticked only inside that question (not under a "Line <k>" question, not "not ticked")."""
    from realcheck import steps_map as M
    rows = f"  1. {M.R37_ROW}\n  2. {M.CREATE_ROW} (main, then the boxes below)\n"
    use = M.USE_ROW[:60] + "\n   " + M.USE_ROW[60:]  # the terminal wraps it
    for head in ("Builder: apply these 3 changes?", "Apply these 3 changes? (none lets an agent do more)"):
        got = M.card_seen(f"> RC-MAPBUILD\n{head}\n{rows}  3. [x] {use}\n  1. Apply  2. Cancel\n")
        ctx.check(f"{head!r}: shown, no row missing, the use row ticked, got {got}",
                  got == {"shown": True, "missing": [], "ticked": True})
    got = M.card_seen(f"builder: apply these 2 changes?\n{rows}Line 3 of 3: {M.USE_ROW} (not ticked)\n")
    ctx.check(f"a use row under its own Line question is not ticked, got {got}",
              got["shown"] and not got["ticked"] and got["missing"] == [])
    got = M.card_seen("Thinking... RC-ANSWER-42")
    ctx.check(f"no card: not shown, every row missing, got {got}",
              got == {"shown": False, "missing": ["R37 row", "create row", "use row"], "ticked": False})


@test
def test_session_map_answers_a_waiting_card_with_tab_then_its_key(ctx: Ctx):
    """P8 batch 2 (judge E, must 1): since the card rules (P5) a card shown within 1.5 s of a key into the box WAITS
    and Enter in the box never answers it; the fake provider answers at once, so the Builder card waits. The step
    does what a person does: with the card's wait line on screen (the product's own words) Tab, then Enter; with the
    card holding the focus, Enter; never a key in the card's first moments (CARD_FRESH_S); and it says which way it
    went. Red on fc214582: the step had no `_answer` and pressed Enter at once."""
    import time as _t

    from halo_harness.tui.keys import CARD_FRESH_S
    from halo_harness.tui.widgets.cards import HELD_PLACEHOLDER, WAIT_LINE
    from realcheck import steps_map as M
    answer = getattr(M, "_answer", None)
    ctx.check("steps_map has _answer (how the step answers the card)", callable(answer))
    if not callable(answer):
        return

    class Term:
        def __init__(self, screen: str, late: str = "", late_s: float = 0.0) -> None:
            self.screen, self.keys, self.t0 = screen, [], _t.monotonic()
            self.late, self.late_s = late, late_s

        def plain(self) -> str:
            if self.late and _t.monotonic() - self.t0 >= self.late_s:
                self.screen, self.late = self.screen + self.late, ""
            return self.screen

        def write(self, data: bytes) -> None:
            self.keys.append((data, _t.monotonic() - self.t0))
            if data == b"\t":
                self.screen += "\n" + " " * 60  # the redraw that takes the wait line down

        def wait_for(self, pred, timeout: float) -> bool:
            end = _t.monotonic() + timeout
            while _t.monotonic() < end:
                if pred(self.plain()):
                    return True
                _t.sleep(0.02)
            return bool(pred(self.plain()))

    card = "> RC-MAPBUILD\nBuilder: apply these 3 changes?\n  1. Apply them  2. Leave them\n"
    for name, line in (("the wait line", WAIT_LINE.format(kind="Question")), ("the held box", HELD_PLACEHOLDER)):
        t = Term(card + line + "\n")
        how = answer(t, 0)
        keys = [k for k, _at in t.keys]
        ctx.check(f"{name} on screen: Tab, then Enter, after the card's first moments; said so, got {keys} {how!r}",
                  keys == [b"\t", b"\r"] and t.keys[0][1] > CARD_FRESH_S and how.startswith("Tab, then Enter"))
    # P8 batch 2 repair (its checker): on a runner 5-10x slower than the PC the wait line is drawn late; a line that
    # shows 2.5 s after the card is still a waiting card (red on bf2ed077: Enter after 1.8 s, Apply never happened)
    t = Term(card, WAIT_LINE.format(kind="Question") + "\n", 2.5)
    how = answer(t, 0)
    keys = [k for k, _at in t.keys]
    ctx.check(f"a wait line drawn 2.5 s late: Tab, then Enter, after it showed; got {keys} {how!r}",
              keys == [b"\t", b"\r"] and t.keys[0][1] >= 2.5 and how.startswith("Tab, then Enter"))
    sign = getattr(M, "CARD_SIGN_S", 0)
    ctx.check(f"the step looks for the wait line a slow runner's while (at least 8 s), got {sign}", sign >= 8)
    before = getattr(M, "CARD_SIGN_S", None)
    M.CARD_SIGN_S = 1.0  # the focus case waits out the whole look: shortened here only
    try:
        t = Term(card)
        how = answer(t, 0)
    finally:
        if before is not None:
            M.CARD_SIGN_S = before
    keys = [k for k, _at in t.keys]
    ctx.check(f"the card has the focus: Enter alone, after its first moments; said so, got {keys} {how!r}",
              keys == [b"\r"] and t.keys[0][1] > CARD_FRESH_S and how.startswith("Enter: the card had the focus"))


@test
def test_session_map_reads_the_truth_block_once_it_says_s13(ctx: Ctx):
    """P8 batch 2 repair (seen on the Linux VM once the card and the word were right): the truth block reads the
    status row (R28), which reaches the page about 0.3 s after the `builder_done` frame; (3) read the drawer 0.07 s
    after Live was pressed and found the sentence before it. (3) now waits (WORD_S at most) for the truth block to say
    S13 before it reads the drawer, and records how long that took. Red on bf2ed077: no wait on the truth block."""
    from realcheck import steps_map as M
    calls: list = []

    class Page:
        def click_on(self, sel) -> None:
            calls.append("click")

        def call(self, *a, **k) -> None:
            pass

        def wait(self, expr: str, timeout: float):
            calls.append(("wait", expr, timeout))
            return True

        def js(self, expr: str):
            calls.append("js")
            return {"map": "review-flow", "truth": M.S13 + " New session", "new_session": True, "boxes": [],
                    "zoom": 1, "small_px": [], "ellipsis": []}
    ev, bad = {}, []
    M._drawn(Page(), ev, bad)
    waits = [i for i, x in enumerate(calls) if isinstance(x, tuple) and "session-truth" in x[1]
             and "keeps running on Auto (the default)" in x[1] and x[2] >= M.WORD_S]
    first_js = calls.index("js") if "js" in calls else -1
    ctx.check(f"(3) waits for the truth block to say S13 before it reads the drawer, got {calls}",
              bool(waits) and 0 <= waits[0] < first_js)
    ctx.check(f"how long it took is evidence, got {ev.get('drawn', {}).get('truth_s', 'none')!r}",
              "truth_s" in (ev.get("drawn") or {}))


@test
def test_session_map_types_once_studio_follows_the_session(ctx: Ctx):
    """P8 batch 2 repair (its checker's must 1; seen on the Linux VM): Studio's feed attaches a new session on its
    2-s scan, and the rig typed and applied the card within about 2.5 s of the page's load, so the `builder_done`
    frame was sent before Studio followed the session and never reached the page (the word `new` never showed). A
    person's Studio follows the session long before he has typed a request: the step waits for Studio's feed to list
    the session (its `sessions` frame, read by the hook) before it types, and says how long that took. The hook also
    raises the resource-timing buffer, so (6)'s count of fleet reads never stops at the browser's 250 entries."""
    import inspect

    from realcheck import steps_map as M
    hook = M.HOOK
    ctx.check("the hook reads the feed's `sessions` frames into window.__rcb.followed",
              "addEventListener('sessions'" in hook and "followed" in hook)
    ctx.check("the hook raises the resource-timing buffer before the page's first request",
              "setResourceTimingBufferSize(100000)" in hook)
    followed = getattr(M, "_followed", None)
    ctx.check("steps_map has _followed (the wait for Studio to follow the session)", callable(followed))
    if not callable(followed):
        return
    src = inspect.getsource(M.session_map)
    ctx.check("session_map waits for _followed before (1) types the request",
              0 <= src.find("_followed(") < src.find("_card,"))

    class Page:
        def __init__(self, ok: bool) -> None:
            self.ok, self.asked = ok, []

        def wait(self, expr: str, timeout: float):
            self.asked.append((expr, timeout))
            if not self.ok:
                raise TimeoutError(expr)
            return True
    for ok in (True, False):
        page, ev, bad = Page(ok), {}, []
        got = followed(page, ev, bad)
        ctx.check(f"followed={ok}: returns {ok}, says how long, a fault only when Studio never followed; got {got} "
                  f"{ev} {bad}", got is ok and ("followed_s" in ev) and (bool(bad) is (not ok))
                  and all("followed" in e and t >= 20 for e, t in page.asked))


@test
def test_session_map_waits_for_studio_to_follow_the_session_it_started(ctx: Ctx):
    """P8 batch 3 (the batch 2 checker's should; red on dc72c152): `_followed` waited for ANY session in the feed's
    `sessions` frame. The step now reads the id of the terminal session it started (Studio's session list, the one tui
    row of its scratch home) and waits for THAT id in the frame; another session listed is not a follow."""
    import inspect

    from realcheck import steps_map as M
    followed = getattr(M, "_followed", None)
    params = inspect.signature(followed).parameters if callable(followed) else {}
    ctx.check(f"_followed takes the session id the step started, got {list(params)}", "sid" in params)
    if "sid" not in params:
        return
    src = inspect.getsource(M.session_map)
    ctx.check("session_map passes the terminal session's id to _followed", "_followed(c, ev, bad, sid)" in src)

    class Page:
        def __init__(self, listed: list) -> None:
            self.listed, self.asked = listed, []

        def wait(self, expr: str, timeout: float):
            self.asked.append(expr)
            import json as _j
            want = _j.loads(expr.split("includes(", 1)[1].split(")", 1)[0]) if "includes(" in expr else None
            if want is None or want not in self.listed:
                raise TimeoutError(expr)
            return True
    for listed, ok in ((["s-other", "s-mine"], True), (["s-other"], False)):
        page, ev, bad = Page(listed), {}, []
        got = followed(page, ev, bad, "s-mine")
        ctx.check(f"listed {listed}: followed is {ok} (only the step's own session counts), got {got} {bad} {page.asked}",
                  got is ok and bool(bad) is (not ok) and all("s-mine" in e for e in page.asked))


@test
def test_prompt_check_4_looks_for_an_identity_not_a_word(ctx: Ctx):
    """The step `prompt`'s check (4) on a machine whose account is an ordinary word (the CI runners' `runner`): the
    word in a sentence ("still runs on the step runner") is no finding; the login, `by <user>`, a home path of the
    account and the host name are, each named. An account that is no common word is found as a word, as before."""
    from unittest import mock
    from realcheck import steps_prompt as sp

    def check(user: str, log: str, shown: str = "") -> list:
        with mock.patch("getpass.getuser", lambda: user), mock.patch("socket.gethostname", lambda: "box-7"):
            return sp._check_private(log, shown)[0]
    # The home paths below are joined from parts: no literal home path with an account name stands in the tracked tree
    # (tests/test_privacy_scan.py reads this file too).
    sentence = '{"text": "the tool still runs on the step runner, then the Runner reads it"}'
    got = check("runner", sentence, "the step runner is done")
    ctx.check(f"`runner` in running text, the log and the screen, is no finding, got {got}", got == [])
    for log, shape in (('{"by": "runner@box-7"}', "<user>@<host>"), ('{"by": "runner"}', '"by": "<user>"'),
                       ("the turn was steered by runner from Studio", "by <user>"),
                       ('{"cwd": "' + "/".join(("", "home", "runner", "work", "x")) + '"}', "/home/<user>/"),
                       ('{"cwd": "' + "/".join(("", "Users", "runner", "x")) + '"}', "/Users/<user>/"),
                       ('{"cwd": "D:\\\\Users\\\\runner\\\\x"}', "Users\\\\<user>"),
                       ("asked on box-7 at noon", "on <host> at")):
        got = check("runner", sentence + "\n" + log)
        ctx.check(f"{log!r} is a finding that shows {shape!r}, got {got}",
                  len(got) == 1 and got[0].startswith("(4) the machine's ") and shape in got[0])
    got = check("runner", "", "steered by runner")
    ctx.check(f"the screen is read the same way, got {got}", len(got) == 1 and "session's screen" in got[0])
    got = check("jqzorbel", "a line that names jqzorbel in passing")
    ctx.check(f"an account that is no common word is found as a word, as before, got {got}",
              len(got) == 1 and "user name" in got[0] and "names <user> in" in got[0])
    ctx.check("and a text without it passes", check("jqzorbel", sentence, "the step runner") == [])


@test
def test_browser_names_the_browser_the_steps_use_and_one_that_names_nothing_fails_them(ctx: Ctx):
    """--browser <path or command name>: that browser (HALO_CHROME for the run, put back after); one that names no
    browser is a FAIL of each browser step that says so, never the person's own installed Chrome."""
    from unittest import mock
    m = _main_module()
    tmp = Path(tempfile.mkdtemp(prefix="rc-browser-"))
    mine = tmp / "my-chromium"
    mine.write_text("", encoding="utf-8")
    missing = str(tmp / "no-such-chromium")
    used: list = []

    def step(c):
        used.append((core.browser(c), os.environ.get("HALO_CHROME")))
        return "ok", {}
    before = os.environ.get("HALO_CHROME")
    with mock.patch.dict(os.environ, {"REALCHECK_BROWSER": ""}):
        results, _v = m.run([("studio", 10, "", step)], root=tempfile.mkdtemp(prefix="rc-test-"), probe_version=False,
                            say=lambda s: None, browser=str(mine))
        ctx.check(f"the named browser is the one used, got {used}",
                  results[0].status == "PASS" and used == [(str(mine), str(mine))])
        ctx.check("HALO_CHROME is put back after the run", os.environ.get("HALO_CHROME") == before)
        with mock.patch("shutil.which", lambda name, *a, **k: str(tmp / "installed-chrome")), \
                mock.patch.object(core.Ctx, "terminal", lambda *a, **k: used.append("terminal") or 1 / 0):
            results, _v = m.run(_browser_steps(m), root=tempfile.mkdtemp(prefix="rc-test-"), probe_version=False,
                                say=lambda s: None, browser=missing)
    got = [(r.status, r.detail) for r in results]
    ctx.check(f"a browser that names nothing fails each browser step, saying so, got {got}",
              got == [("FAIL", f"the browser named by --browser does not exist: {missing}")] * 2)


@test
def test_copy_drag_judges_the_dragged_words_the_last_answer_and_nothing(ctx: Ctx):
    """3.6.0.6 C: copy-drag's pure judge -- per gesture, what reached the clipboard (None: nothing)."""
    from realcheck.steps_copy import judge
    words, last = "ALPHA with some words", "the last one."
    ctx.check("all four right: nothing to say", judge([words, words, words, last], words, last) == [])
    said = judge([last, words, words, last], words, last)
    ctx.check(f"the drag copied the last answer: said so, got {said}",
              said == [f"letting go of the drag copied the LAST answer, not {words!r}"])
    said = judge([None, None, None, None], words, last)
    ctx.check(f"nothing copied: each gesture said, got {said}", said == [
        "letting go of the drag put nothing on the clipboard", "the same drag again put nothing on the clipboard",
        "Ctrl+C after the drag put nothing on the clipboard", "Ctrl+C with nothing selected put nothing on the clipboard"])
    said = judge([words, words, "ALPHA with some", words], words, last)
    ctx.check(f"other words: the words shown, got {said}", len(said) == 2 and "'ALPHA with some'" in said[0]
              and said[1] == f"Ctrl+C with nothing selected copied {words!r}, not {last!r}")


@test
def test_copy_drag_reads_the_screen_and_the_clipboard_program(ctx: Ctx):
    """3.6.0.6 C: the screen copy-drag reads (cursor moves, erases, a wide character, Windows' re-draws), the mouse
    sequences it sends, and clip.exe's UTF-16 with its BOM read back as text."""
    from realcheck.steps_copy import cells, drag_bytes, find, read_copy
    raw = ("\x1b[?1049h\x1b[2J\x1b[3;5Hold words here\x1b[3;5H\x1b[K\x1b[38;2;1;2;3m"
           "日x ALPHA with\x1b[1C" "some\x1b[m\r\n\x1b[4;1Hnext \x1b]0;title\x07row\x1b[4;3H\x1b[2X").encode("utf-8")
    grid = cells(raw, 40, 6)
    row = "".join(grid[2])
    ctx.check(f"the erased line holds only the new text, got {row!r}", row.rstrip() == "    日x ALPHA with some")
    ctx.check(f"a word is found by its cell (the wide character takes two), got {find(grid, 'ALPHA')}",
              find(grid, "ALPHA") == (8, 2))
    ctx.check(f"an erase of two cells, got {''.join(grid[3])!r}", "".join(grid[3]).rstrip() == "ne   row")
    ctx.check("a word not on the screen: None", find(grid, "words here") is None)
    seqs = drag_bytes((8, 2), (20, 2))
    ctx.check(f"press, two moves, release, 1-based, got {seqs}", seqs == [
        b"\x1b[<0;9;3M", b"\x1b[<32;15;3M", b"\x1b[<32;21;3M", b"\x1b[<0;21;3m"])
    ctx.check("clip.exe's UTF-16LE with its BOM", read_copy(b"\xff\xfe" + "déjà".encode("utf-16-le")) == "déjà")
    ctx.check("UTF-8 elsewhere", read_copy("déjà".encode("utf-8")) == "déjà")


@test
def test_the_checkers_own_end_is_named_by_its_parent(ctx: Ctx):
    """3.6.0.9: at 3.6.0.8's gate the checker passed all 18 steps on Windows, printed its last line, and then ended with
    a status the shell could only call 127, with no line of its own (twice in one CI attempt, never again on a rerun).
    A process cannot say how it ended; its parent can. `--name-the-end` runs the checker as a child and names the end."""
    _main_module()
    from realcheck import named_end as N
    for code in (0, 1, 2):
        got = N.run_named([sys.executable, "-c", f"import sys; sys.exit({code})"], say=lambda _l: ctx.check(
            f"an end of the checker's own ({code}) gets no line", False))
        ctx.check(f"the checker's own exit code {code} passes through, got {got}", got == code)
    said: list = []
    if os.name == "nt":
        crash = ("import ctypes; k = ctypes.windll.kernel32; k.TerminateProcess.argtypes = [ctypes.c_void_p, "
                 "ctypes.c_uint]; k.GetCurrentProcess.restype = ctypes.c_void_p; "
                 "k.TerminateProcess(k.GetCurrentProcess(), 0xC00000FD)")  # the status a stack overflow leaves
        got = N.run_named([sys.executable, "-c", crash], say=said.append)
        ctx.check(f"a crash-kind status is named in hex with its kind, got {got} {said}",
                  got == 1 and len(said) == 1 and "0xC00000FD" in said[0] and "stack overflow" in said[0])
    else:
        got = N.run_named([sys.executable, "-c", "import os, signal; os.kill(os.getpid(), signal.SIGSEGV)"],
                          say=said.append)
        ctx.check(f"an end by a signal is named, got {got} {said}",
                  got == 1 and len(said) == 1 and "signal 11" in said[0] and "SIGSEGV" in said[0])
    ctx.check(f"the line begins as the checker's lines do, got {said}", said[0].startswith("realcheck: "))
    line = N.end_line(0xC000013A, ["12:00:01 SIGBREAK"])
    ctx.check(f"a console control event is named, and one the parent saw is said with its time, got {line!r}",
              "0xC000013A" in line and "console control event" in line and "12:00:01 SIGBREAK" in line)
    ctx.check(f"a status the line does not know is still said in hex, got {N.end_line(0xC0000999, [])!r}",
              "0xC0000999" in N.end_line(0xC0000999, []))
    text = (REPO / ".github" / "workflows" / "suites.yml").read_text(encoding="utf-8")
    runs = [ln for ln in text.splitlines() if "scripts/realcheck.py" in ln and "run:" in ln]
    ctx.check(f"CI's real-use step asks for it, got {runs}", bool(runs) and all("--name-the-end" in ln for ln in runs))
    # and Python's own fault reporter is on in the checker: a fault says where each thread was
    probe = ("import faulthandler, importlib.util, io, sys; from contextlib import redirect_stdout; "
             f"spec = importlib.util.spec_from_file_location('rc', r'{REPO / 'scripts' / 'realcheck.py'}'); "
             "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); before = faulthandler.is_enabled()\n"
             "with redirect_stdout(io.StringIO()):\n    m.main(['--list'])\n"
             "print(before, faulthandler.is_enabled())")
    r = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, timeout=120)
    ctx.check(f"the checker's main turns the fault reporter on, got {r.stdout.strip()!r} {r.stderr[-200:]!r}",
              r.stdout.strip() == "False True")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
