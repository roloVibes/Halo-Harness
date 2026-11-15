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
    names = [line.split()[0] for line in out.getvalue().splitlines()]
    ctx.check(f"the twelve steps in order, got {names}", rc == 0 and names == [
        "starts", "first-run", "theme", "question", "turn", "studio", "packs", "local", "update", "closing",
        "no-reuse", "idle-cpu"])
    ctx.check("an unknown step: exit 2", m.main(["--only", "no-such-step"]) == 2)


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


@test
def test_the_browser_stand_in_writes_the_url_it_is_asked_to_open(ctx: Ctx):
    root = Path(tempfile.mkdtemp(prefix="rc-browser-"))
    cmd, out = fakes.browser_command(root)
    url = "http://127.0.0.1:1/?mode=setup&first=1#t=abc"
    rc = subprocess.run([cmd, url], timeout=60).returncode
    ctx.check(f"exit 0 and the whole URL written down, got {fakes.opened_urls(out)}", rc == 0 and fakes.opened_urls(out) == [url])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
