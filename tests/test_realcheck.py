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


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
