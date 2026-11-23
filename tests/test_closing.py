"""tests.test_closing -- Halo 3.6.0.0 R10: when Halo closes, everything it started closes (halo_harness/closing.py).

For each kind of child (tests/helpers/closing_owner.py starts it through Halo's own code under a small real owner),
the owner is ended each of the five ways -- a normal exit, Ctrl+C, SIGTERM, a closed terminal (SIGHUP), a hard kill
-- and within five seconds no process it started is alive (checked by pid and start time, and on POSIX by the
HALO_OWNER marker in every process's environment). A kept child survives and is named on the way out. The sweep at
start stops a planted orphan (the Studio an older `halo init` left with no owner) and leaves a kept one. A launch
never attaches to a Studio it did not start. Halo's own Python children never import from the working folder
(a project holding a `halo_harness/` folder or a `json.py`), and "Studio did not start" says why.

Windows cannot send Ctrl+C to another console group (CTRL_BREAK stands in, mapped to KeyboardInterrupt as Ctrl+C
is), and has no SIGTERM or SIGHUP: TerminateProcess (what `kill` and a closed window come to) stands in for both.
Every process a test starts uses a scratch home and is ended by pid and start time; nothing is killed by name.
Run: python -m tests.test_closing
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
OWNER = REPO / "tests" / "helpers" / "closing_owner.py"
SLEEPER = REPO / "tests" / "helpers" / "closing_sleeper.py"
SCRUB = ("OPENROUTER_", "DATABRICKS_", "ANTHROPIC_", "BRIDGE_", "HALO_", "ROLO_CLAUDE_", "TYPESAFE_", "OPENAI_",
         "PACKS_TEST_")
WIN = os.name == "nt"
WAYS = ("normal", "ctrl_c", "sigterm", "sighup", "kill")
BOUND_S = 5.0


def _env(home: Path) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith(SCRUB) or k == "HALO_TEST_NO_PROC"}  # macOS's path
    env.update(BRIDGE_TEST_HOME=str(home), BRIDGE_TEST_NO_BACKGROUND_NET="1", PYTHONPATH=str(REPO),
               PYTHONIOENCODING="utf-8", HALO_NO_BROWSER="1", OLLAMA_HOST="http://127.0.0.1:9")
    return env


def _start_time(pid: int):
    from halo_harness.bg_run import process_start_time
    return process_start_time(pid)


def _same(pid: int, start) -> bool:
    from halo_harness.children import same_process
    return same_process(pid, start)


def _end_tree_we_started(pid: int, start) -> None:
    """Only a pid this test started (its start time still matches)."""
    if not _same(pid, start):
        return
    try:
        if WIN:
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, timeout=15)
        else:
            os.kill(pid, signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        pass


def _owner(kind: str, tmp: Path, cwd: "Path | None" = None, home: "Path | None" = None, extra_env: "dict | None" = None):
    out = tmp / "out"
    out.mkdir(parents=True, exist_ok=True)
    env = dict(_env(home or tmp / "home"), **(extra_env or {}))
    kw: dict = {"stdout": subprocess.PIPE, "stderr": subprocess.PIPE, "stdin": subprocess.DEVNULL, "text": True,
                "encoding": "utf-8", "errors": "replace", "env": env, "cwd": str(cwd or tmp)}
    if WIN:
        kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    proc = subprocess.Popen([sys.executable, str(OWNER), kind, str(out)], **kw)
    deadline = time.time() + (90 if kind == "studio" else 30)
    while time.time() < deadline:
        try:
            return proc, out, json.loads((out / "ready.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            if proc.poll() is not None:
                break
            time.sleep(0.1)
    try:
        proc.kill()
    except OSError:
        pass
    _o, err = proc.communicate(timeout=10)
    raise AssertionError(f"the owner never got ready (exit {proc.returncode}): {err[-800:]}")


def _end(proc, out: Path, way: str) -> None:
    if way == "normal":
        (out / "quit").write_text("", encoding="utf-8")
    elif way == "ctrl_c":
        os.kill(proc.pid, signal.CTRL_BREAK_EVENT if WIN else signal.SIGINT)
    elif way == "sigterm":
        proc.terminate()  # SIGTERM; Windows: TerminateProcess
    elif way == "sighup":
        if WIN:
            proc.kill()  # a closed console window ends in TerminateProcess after its handler
        else:
            os.kill(proc.pid, signal.SIGHUP)
    else:
        proc.kill()


def _marked(marker: str) -> list:
    from halo_harness.closing import marker_pids
    return sorted(marker_pids(marker)) if marker and not WIN else []


def _run_ways(ctx: Ctx, kind: str, *, kept: bool = False) -> None:
    for way in WAYS:
        tmp = Path(tempfile.mkdtemp(prefix=f"halo-r10-{kind}-{way}-"))
        kids: list = []
        try:
            proc, out, ready = _owner(kind, tmp)
            kids = ready["kids"]
            marker = ready["marker"]
            ctx.check(f"{kind}/{way}: the owner set its own marker, got {marker!r}",
                      bool(marker) and marker.startswith(f"{ready['owner']}-"))
            if kind in ("tool", "ledger", "grandchild", "mcp"):
                ctx.check(f"{kind}/{way}: the child carries the owner's HALO_OWNER, got {kids[0].get('marker')!r}",
                          kids[0].get("marker") == marker)
            if kind == "studio":
                sj = kids[0].get("studio_json") or {}
                ctx.check(f"studio/{way}: studio.json records its owner, got {sj.get('owner_pid')} vs {ready['owner']}",
                          sj.get("owner_pid") == ready["owner"])
            _end(proc, out, way)
            try:
                _o, err = proc.communicate(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
                _o, err = proc.communicate(timeout=10)
                ctx.check(f"{kind}/{way}: the owner ended within 15 s", False)
            t0 = time.monotonic()
            while time.monotonic() - t0 < BOUND_S and any(_same(k["pid"], k["start"]) for k in kids):
                time.sleep(0.05)
            alive = [k["pid"] for k in kids if _same(k["pid"], k["start"])]
            if alive and not kept:  # a pid caught mid-exit reads alive once (bg_run.pid_alive): look again
                time.sleep(0.3)
                alive = [k["pid"] for k in kids if _same(k["pid"], k["start"])]
            if kept:
                ctx.check(f"kept/{way}: the kept child outlives its owner, alive {alive}", alive == [kids[0]["pid"]])
                if way in ("normal", "ctrl_c") or (way in ("sigterm", "sighup") and not WIN):  # Windows: TerminateProcess
                    ctx.check(f"kept/{way}: the owner named it on the way out with the command, got {err[-400:]!r}",
                              "left running on purpose" in err and str(kids[0]["pid"]) in err)
                continue
            ctx.check(f"{kind}/{way}: nothing the owner started is alive {BOUND_S:.0f} s after it went "
                      f"(alive: {alive}; owner stderr: {err[-300:]!r})", not alive)
            if not WIN:  # the reaper itself carries the marker while it acts: the bound is from the owner's end
                stray = _marked(marker)
                while stray and time.monotonic() - t0 < BOUND_S:
                    time.sleep(0.05)
                    stray = _marked(marker)
                ctx.check(f"{kind}/{way}: no process carries the owner's marker {BOUND_S:.0f} s on, got {stray}",
                          not stray)
        finally:
            for k in kids:
                _end_tree_we_started(k["pid"], k["start"])
            shutil.rmtree(tmp, ignore_errors=True)


@test
def test_studio_server_never_outlives_the_launch_that_started_it(ctx: Ctx):
    """Inventory row 1: the Studio `halo init` starts (launch_detached), each of the five ways."""
    _run_ways(ctx, "studio")


@test
def test_someone_elses_binary_ends_with_its_owner(ctx: Ctx):
    """Rows 6-10, 15-17: a long-lived process in no ledger (a tool command, an MCP server): the Job object on
    Windows, the marker sweep and the reaper on POSIX."""
    _run_ways(ctx, "tool")


@test
def test_a_ledger_child_ends_with_its_owner(ctx: Ctx):
    """Rows 5, 10, 14: a child recorded in children.json as this owner's (a schedule fire, a model server)."""
    _run_ways(ctx, "ledger")


@test
def test_a_kept_child_survives_and_is_named(ctx: Ctx):
    """Rows 12-14, 18: what a person asked to keep (`halo --bg`) outlives its owner every way, and is named."""
    _run_ways(ctx, "kept", kept=True)


def _plant(state: Path, what: str, owner_pid, owner_start, keep: bool = False) -> dict:
    from halo_harness import children as C
    tmp = Path(tempfile.mkdtemp(prefix="halo-r10-plant-"))
    proc = subprocess.Popen([sys.executable, str(SLEEPER), str(tmp / "c.json")], stdin=subprocess.DEVNULL)
    deadline = time.time() + 20
    while not (tmp / "c.json").exists() and time.time() < deadline:
        time.sleep(0.05)
    entry = C.register(proc.pid, what, ["sleeper"], owner_pid=owner_pid, state_dir=state, keep=keep or None)
    if owner_pid is not None and owner_start is not None:  # an owner that is gone: its own recorded start
        rows = C.load(state)
        for r in rows:
            if r["pid"] == proc.pid:
                r["owner_start"] = owner_start
        C._write(C.registry_path(state), rows)
    if owner_pid is None:
        rows = C.load(state)
        for r in rows:
            if r["pid"] == proc.pid:
                r["owner_pid"], r["owner_start"] = None, None
        C._write(C.registry_path(state), rows)
    return {"proc": proc, "pid": proc.pid, "start": entry["start_time"]}


def _dead_owner() -> "tuple[int, str]":
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    start = _start_time(p.pid)
    p.wait(timeout=30)
    return p.pid, start or "gone"


@test
def test_the_sweep_at_start_stops_a_planted_orphan_and_leaves_a_kept_one(ctx: Ctx):
    from halo_harness import closing
    state = Path(tempfile.mkdtemp(prefix="halo-r10-sweep-")) / ".halo"
    state.mkdir(parents=True)
    dead_pid, dead_start = _dead_owner()
    orphan = _plant(state, "studio", dead_pid, dead_start)
    old_init = _plant(state, "studio", None, None)  # what an older `halo init` left: a Studio with no owner
    kept = _plant(state, "schedule", dead_pid, dead_start, keep=True)
    live = _plant(state, "schedule", os.getpid(), _start_time(os.getpid()))
    try:
        lines: list = []
        closing.sweep(state, say=lines.append)
        ctx.check(f"the orphan and the ownerless Studio are stopped, got {lines}",
                  not _same(orphan["pid"], orphan["start"]) and not _same(old_init["pid"], old_init["start"]))
        ctx.check(f"one line each, 'stopped a Studio server left from', got {lines}",
                  len(lines) == 2 and all(line.startswith("halo: stopped a Studio server left from") for line in lines))
        ctx.check("the kept one and a live owner's child are left alone",
                  _same(kept["pid"], kept["start"]) and _same(live["pid"], live["start"]))
        again: list = []
        closing.sweep(state, say=again.append)
        ctx.check(f"a second sweep finds nothing, got {again}", again == [])
    finally:
        for p in (orphan, old_init, kept, live):
            _end_tree_we_started(p["pid"], p["start"])
            try:
                p["proc"].wait(timeout=10)
            except Exception:
                pass


@test
def test_a_launch_never_attaches_to_a_studio_it_did_not_start(ctx: Ctx):
    from halo_harness.studio import launch
    state = Path(tempfile.mkdtemp(prefix="halo-r10-attach-")) / ".halo"
    state.mkdir(parents=True)
    other = subprocess.Popen([sys.executable, str(SLEEPER), str(state / "c.json")], stdin=subprocess.DEVNULL)
    try:
        start = _start_time(other.pid)
        info = {"pid": other.pid, "port": 9, "token": "t", "pstart": start, "owner_pid": other.pid + 100000}
        ctx.check("another launch's Studio is not this process's", launch.owned_by_me(info) is False)
        ctx.check("an ownerless Studio is not this process's",
                  launch.owned_by_me({k: v for k, v in info.items() if k != "owner_pid"}) is False)
        from halo_harness.closing import me
        pid, mine = me()
        ctx.check("one this process started is", launch.owned_by_me(dict(info, owner_pid=pid, owner_start=mine)) is True)
        (state / "studio.json").write_text(json.dumps(info), encoding="utf-8")
        ctx.check("own_url answers '' for a Studio this process did not start", launch.own_url(state) == "")
    finally:
        _end_tree_we_started(other.pid, _start_time(other.pid))
        other.wait(timeout=10)


@test
def test_studio_did_not_start_says_why(ctx: Ctx):
    from halo_harness import selfexec
    from halo_harness.studio import launch
    state = Path(tempfile.mkdtemp(prefix="halo-r10-why-")) / ".halo"
    state.mkdir(parents=True)
    saved = selfexec.python_argv
    selfexec.python_argv = lambda *a, **k: [sys.executable, "-c", "import sys; print('boom: no Studio here'); sys.exit(3)", "--"]
    try:
        url = launch.launch_detached("setup", cwd=state, state_dir=state, open_browser=False, timeout=20)
        why = launch.failure_line()
    finally:
        selfexec.python_argv = saved
    ctx.check(f"no URL, and why: the exit code and the last line, got {url!r} {why!r}",
              url == "" and "code 3" in why and "boom: no Studio here" in why)
    from halo_harness.studio.edit_open import _describe
    line = _describe("", "failed", "setup", {"cli": "halo studio --edit setup"})
    ctx.check(f"the door's line carries it, got {line!r}", "boom: no Studio here" in line)


def _poisoned_project(tmp: Path) -> "tuple[Path, Path]":
    proj = tmp / "project"
    (proj / "halo_harness").mkdir(parents=True)
    flag = tmp / "imported-from-the-project.txt"
    poison = f"open({str(flag)!r}, 'a').write(__name__ + '\\n')\n"
    (proj / "halo_harness" / "__init__.py").write_text(poison, encoding="utf-8")
    (proj / "json.py").write_text(poison, encoding="utf-8")
    (proj / "yaml.py").write_text(poison, encoding="utf-8")
    return proj, flag


@test
def test_halos_own_python_never_imports_from_the_working_folder(ctx: Ctx):
    from halo_harness.selfexec import BOOT, python_argv
    tmp = Path(tempfile.mkdtemp(prefix="halo-r10-wf-"))
    proj, flag = _poisoned_project(tmp)
    env = _env(tmp / "home")
    try:
        old = subprocess.run([sys.executable, "-m", "halo_harness", "--version"], cwd=str(proj), env=env,
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=120)
        ctx.check(f"the old `python -m halo_harness` from that folder ran the folder's code (the hole), got "
                  f"{old.returncode} {flag.exists()}", flag.exists())
        flag.unlink(missing_ok=True)
        heads = {"python_argv()": python_argv(), "python_argv(cli)": python_argv("halo_harness.cli"),
                 "unbuffered": python_argv(unbuffered=True),
                 "the 3.10 bootstrap": [sys.executable, "-c", BOOT.format(module="halo_harness")]}
        for name, head in heads.items():
            r = subprocess.run(head + ["--version"], cwd=str(proj), env=env, capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=120)
            ctx.check(f"{name}: starts normally from that folder, got {r.returncode} {r.stderr[-300:]!r}",
                      r.returncode == 0 and "halo" in (r.stdout + r.stderr).lower())
            ctx.check(f"{name}: nothing of that folder was imported, got {flag.read_text() if flag.exists() else ''!r}",
                      not flag.exists())
            flag.unlink(missing_ok=True)
        proc, out, ready = _owner("studio", tmp / "owner", cwd=proj)
        kid = ready["kids"][0]
        try:
            ctx.check(f"Studio started the way `halo init` starts it, from that folder, got {kid}",
                      _same(kid["pid"], kid["start"]))
            ctx.check(f"and imported nothing of it, got {flag.read_text() if flag.exists() else ''!r}", not flag.exists())
        finally:
            (out / "quit").write_text("", encoding="utf-8")
            proc.communicate(timeout=30)
            _end_tree_we_started(kid["pid"], kid["start"])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _gone_within(kids: list, seconds: float = BOUND_S) -> list:
    t0 = time.monotonic()
    while time.monotonic() - t0 < seconds and any(_same(k["pid"], k["start"]) for k in kids):
        time.sleep(0.05)
    alive = [k["pid"] for k in kids if _same(k["pid"], k["start"])]
    if alive:
        time.sleep(0.3)
        alive = [k["pid"] for k in kids if _same(k["pid"], k["start"])]
    return alive


def _quit(proc, out: Path) -> str:
    (out / "quit").write_text("", encoding="utf-8")
    try:
        return proc.communicate(timeout=30)[1]
    except subprocess.TimeoutExpired:
        proc.kill()
        return proc.communicate(timeout=10)[1]


@test
def test_two_sessions_of_one_home_never_touch_each_others_things(ctx: Ctx):
    """Two halos in two terminals, one home: when the first ends (a normal exit, a hard kill), its closing procedure
    and a later launch's sweep leave the second one's Studio running."""
    for way in ("normal", "kill"):
        tmp = Path(tempfile.mkdtemp(prefix=f"halo-r10-two-{way}-"))
        home = tmp / "home"
        kids: list = []
        b = None
        try:
            a_proc, a_out, a = _owner("studio", tmp / "a", home=home)
            kids += a["kids"]
            b_proc, b_out, b = _owner("studio", tmp / "b", home=home)
            kids += b["kids"]
            ctx.check(f"{way}: the second launch started its own Studio, got {a['kids'][0]['pid']} / {b['kids'][0]['pid']}",
                      a["kids"][0]["pid"] != b["kids"][0]["pid"])
            _end(a_proc, a_out, way)
            a_proc.communicate(timeout=30)
            ctx.check(f"{way}: the first one's Studio is gone", not _gone_within(a["kids"]))
            bk = b["kids"][0]
            ctx.check(f"{way}: the second one's Studio still runs", _same(bk["pid"], bk["start"]))
            r = subprocess.run([sys.executable, "-c", "from halo_harness import closing; closing.install()"],
                               env=_env(home), capture_output=True, text=True, encoding="utf-8", errors="replace",
                               timeout=120, cwd=str(tmp))
            ctx.check(f"{way}: a later launch's sweep leaves it running, got {r.stderr[-300:]!r}",
                      _same(bk["pid"], bk["start"]) and "stopped" not in r.stderr)
            _quit(b_proc, b_out)
            ctx.check(f"{way}: and it ends with its own launch", not _gone_within(b["kids"]))
        finally:
            for k in kids:
                _end_tree_we_started(k["pid"], k["start"])
            shutil.rmtree(tmp, ignore_errors=True)


@test
def test_a_halo_given_a_sessions_variables_but_not_started_by_it_ends_only_its_own(ctx: Ctx):
    """A `halo` that inherited a running session's HALO_OWNER and HALO_OWNER_WATCH without being started by it (a tmux
    pane, a terminal that kept them) is a root of its own (judge item 4). Ended (normally, or hard), it ends what IT
    started and never the session's things; what it starts carries its own id, not the session's."""
    for way in ("normal", "kill"):
        tmp = Path(tempfile.mkdtemp(prefix=f"halo-r10-nested-{way}-"))
        home = tmp / "home"
        kids: list = []
        try:
            p_proc, p_out, p = _owner("ledger", tmp / "p", home=home)
            kids += p["kids"]
            inherited = {"HALO_OWNER": p["marker"], "HALO_OWNER_WATCH": f"{p['owner']}:{_start_time(p['owner']) or ''}"}
            n_proc, n_out, n = _owner("tool", tmp / "n", home=home, extra_env=inherited)
            kids += n["kids"]
            ctx.check(f"{way}: the nested halo marks its own children with its own id, got {n['kids'][0]['marker']!r}",
                      n["kids"][0]["marker"] == n["marker"] and n["marker"] != p["marker"])
            _end(n_proc, n_out, way)
            n_proc.communicate(timeout=30)
            ctx.check(f"{way}: what the nested halo started is gone", not _gone_within(n["kids"]))
            pk = p["kids"][0]
            ctx.check(f"{way}: the session's own child still runs", _same(pk["pid"], pk["start"]))
            ctx.check(f"{way}: and the session itself", p_proc.poll() is None)
            _quit(p_proc, p_out)
            ctx.check(f"{way}: the session's child ends with the session", not _gone_within(p["kids"]))
        finally:
            for k in kids:
                _end_tree_we_started(k["pid"], k["start"])
            shutil.rmtree(tmp, ignore_errors=True)


@test
def test_a_sub_agent_killed_hard_ends_only_its_own(ctx: Ctx):
    """Judge item 1: a sub-agent (any Halo another Halo started: an orchestra worker, a nested `halo -p`) ended -- by a
    timeout's SIGKILL, or normally -- ends what IT started; its parent, the parent's own child and the parent's reaper
    live on. Red at 18fbd47e on POSIX: the sub's reaper killed everything that carried the parent's marker."""
    for way in ("normal", "kill"):
        tmp = Path(tempfile.mkdtemp(prefix=f"halo-r10-sub-{way}-"))
        kids: list = []
        try:
            proc, out, ready = _owner("sub", tmp)
            sub_ready = ready["sub"]
            kids += ready["kids"] + sub_ready["kids"]
            ctx.check(f"{way}: the sub marks its child with its own id, got {sub_ready['kids'][0]['marker']!r} "
                      f"(sub {sub_ready['marker']!r}, parent {ready['marker']!r})",
                      sub_ready["kids"][0]["marker"] == sub_ready["marker"] != ready["marker"])
            sub_pid, sub_start = sub_ready["owner"], sub_ready["start"]
            if way == "kill":
                if WIN:
                    subprocess.run(["taskkill", "/PID", str(sub_pid), "/F"], capture_output=True, timeout=15)
                elif _same(sub_pid, sub_start):
                    os.kill(sub_pid, signal.SIGKILL)
            else:
                (out / "sub" / "quit").write_text("", encoding="utf-8")
            ctx.check(f"{way}: the sub's own child is gone within {BOUND_S:.0f} s", not _gone_within(sub_ready["kids"]))
            time.sleep(1.0)  # the sub's reaper has acted by now
            own = ready["kids"][0]
            ctx.check(f"{way}: the parent still runs", proc.poll() is None)
            ctx.check(f"{way}: the parent's own child still runs", _same(own["pid"], own["start"]))
            if ready.get("reaper"):
                ctx.check(f"{way}: the parent's reaper still runs",
                          _same(ready["reaper"]["pid"], ready["reaper"]["start"]))
            _quit(proc, out)
            ctx.check(f"{way}: the parent's child ends with the parent", not _gone_within(ready["kids"]))
        finally:
            for k in kids:
                _end_tree_we_started(k["pid"], k["start"])
            shutil.rmtree(tmp, ignore_errors=True)


@test
def test_an_mcp_server_ends_with_its_owner(ctx: Ctx):
    """An MCP stdio server started through mcp/stdio.connect (the MCP SDK's own spawn, not subprocess_safe) carries the
    owner's marker and is gone within five seconds of the owner, each of the five ways (a hard kill included)."""
    _run_ways(ctx, "mcp")


@test
def test_a_grandchild_ends_with_its_owner(ctx: Ctx):
    """A tool command's own child, started with the plain standard library (its command line names no marker; it
    inherited it in its environment), is gone within five seconds of the owner, each of the five ways."""
    _run_ways(ctx, "grandchild")


def _studio_we_started(info: dict, popen_pid: int, parent_of) -> bool:
    """studio.json names the Studio this test started: its pid is Popen's, or Popen's pid is its parent (fx jb13: a
    Windows virtual environment's python.exe is a launcher that runs the base interpreter as its child, so the Studio
    that writes studio.json is the launcher's child, never the pid Popen returned)."""
    pid = info.get("pid")
    return isinstance(pid, int) and (pid == popen_pid or parent_of(pid) == popen_pid)


def _parent_of(pid: int):
    from halo_harness import closing
    return closing._parent(pid, {})


def _root_studio(home: Path, extra_env: "dict | None" = None):
    from halo_harness.selfexec import python_argv
    env = dict(_env(home), **(extra_env or {}))
    kw: dict = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "env": env}
    if WIN:
        kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    proc = subprocess.Popen(python_argv() + ["studio", "--no-open"], **kw)
    info_path = home / ".halo" / "studio.json"
    deadline = time.time() + 90
    while time.time() < deadline:
        try:
            info = json.loads(info_path.read_text(encoding="utf-8"))
            if _studio_we_started(info, proc.pid, _parent_of):
                return proc, info
        except (OSError, ValueError):
            pass
        if proc.poll() is not None:
            break
        time.sleep(0.1)
    _stop_popen_tree(proc)  # fx jb13: a Studio that never matched is not left running behind the failure
    raise AssertionError(f"halo studio did not write studio.json (exit {proc.poll()})")


def _stop_popen_tree(proc) -> None:
    """The process this test's Popen started and its children (a venv launcher's interpreter): Popen still holds its
    handle, so the pid cannot have been reused."""
    if proc.poll() is None:
        try:
            if WIN:
                subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, timeout=15)
            else:
                proc.kill()
        except (OSError, subprocess.SubprocessError):
            pass
    try:
        proc.wait(timeout=15)
    except Exception:
        pass


def _stop_root_studio(proc, info: dict) -> None:
    _end_tree_we_started(info.get("pid"), info.get("pstart"))  # the Studio itself (a venv launcher's child, fx jb13)
    _stop_popen_tree(proc)


@test
def test_a_studio_behind_a_venv_launcher_is_found_by_its_parent(ctx: Ctx):
    """fx jb13 (CI, Windows, the venv's python): four tests waited 90 s for studio.json to name Popen's pid, while the
    Studio that wrote it was the launcher's child. Fed a launcher/child pair, studio.json is the one this test
    started; a Studio of someone else (another parent) is not; a direct start (no launcher) still matches."""
    parents = {5002: 5001, 6002: 6001}
    ctx.check("through a launcher: studio.json's pid is Popen's child",
              _studio_we_started({"pid": 5002}, 5001, parents.get))
    ctx.check("no launcher: studio.json's pid is Popen's", _studio_we_started({"pid": 5001}, 5001, parents.get))
    ctx.check("another launcher's Studio is not ours", not _studio_we_started({"pid": 6002}, 5001, parents.get))
    ctx.check("no pid recorded is not ours", not _studio_we_started({}, 5001, parents.get))
    ctx.check("this process's own parent is found", _parent_of(os.getpid()) == os.getppid())


@test
def test_a_persons_own_halo_studio_is_never_an_orphan(ctx: Ctx):
    """Judge item 2: `halo studio` run in a terminal is its own owner: `halo ps` says owner alive, the doctor has no
    row, `halo stop --orphans` does not pick it. Red at 18fbd47e (owner "none", picked as an orphan)."""
    from halo_harness import ps_cli
    from halo_harness.doctor import _check_orphans
    home = Path(tempfile.mkdtemp(prefix="halo-r10-own-studio-"))
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
    proc, info = _root_studio(home)
    try:
        os.environ["BRIDGE_TEST_HOME"] = str(home)
        os.environ.pop("BRIDGE_STATE_DIR", None)
        ctx.check(f"studio.json names it as its own owner, got {info.get('owner_pid')} vs {info['pid']}",
                  info.get("owner_pid") == info["pid"])
        row = next((r for r in ps_cli.rows() if r["pid"] == info["pid"]), None)
        ctx.check(f"`halo ps`: owner alive, got {row}", bool(row) and row["owner"] == "alive")
        ctx.check(f"no doctor row, got {_check_orphans(home / '.halo')!r}", _check_orphans(home / ".halo") is None)
        picked, _u = ps_cli.pick(ps_cli.rows(), [], orphans=True)
        ctx.check(f"`halo stop --orphans` does not pick it, got {picked}", all(r["pid"] != info["pid"] for r in picked))
        ctx.check("and it still runs", _same(info["pid"], info.get("pstart")))
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        _stop_root_studio(proc, info)
        shutil.rmtree(home, ignore_errors=True)


_INIT_DOOR = ("from halo_harness import closing\n"
              "closing.install()\n"
              "from halo_harness.studio.setup_door import SetupTarget, cli_door\n"
              "cli_door(SetupTarget(first=True), terminal_cli='halo init --terminal', fallback='wizard', "
              "say=lambda l: print(l, flush=True), wait=True)\n")


def _init_door(home: Path, tmp: Path):
    return subprocess.run([sys.executable, "-c", _INIT_DOOR], env=_env(home), cwd=str(tmp), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=180)


@test
def test_init_uses_a_live_owned_studio_and_leaves_it_and_stops_a_leftover(ctx: Ctx):
    """Judge item 3: with a Studio of this home whose owner is alive (a person's `halo studio`), `halo init`'s door
    opens Setup in it, says whose it is, and leaves it running when it exits. With a Studio whose recorded owner is
    gone, the sweep at start stops it with one line and init starts (and owns) its own. Red at 18fbd47e (init got no
    URL: "it exited with code 0")."""
    tmp = Path(tempfile.mkdtemp(prefix="halo-r10-init-"))
    home = tmp / "home"
    proc, info = _root_studio(home)
    try:
        r = _init_door(home, tmp)
        text = r.stdout + r.stderr
        ctx.check(f"init opened Setup in the running Studio, got {text[-600:]!r}",
                  f"127.0.0.1:{info['port']}/" in text and "?mode=setup" in text)
        ctx.check(f"and said whose it is, got {text[-600:]!r}", "Using the Studio already running" in text
                  and str(info["pid"]) in text)
        time.sleep(1.0)
        ctx.check("the Studio still runs after init exited", _same(info["pid"], info.get("pstart")))
    finally:
        _stop_root_studio(proc, info)
    proc2, info2 = _root_studio(home)
    try:
        dead_pid, dead_start = _dead_owner()
        path = home / ".halo" / "studio.json"
        rec = json.loads(path.read_text(encoding="utf-8"))
        rec.update(owner_pid=dead_pid, owner_start=dead_start)
        path.write_text(json.dumps(rec), encoding="utf-8")
        r = _init_door(home, tmp)
        text = r.stdout + r.stderr
        gone = not _gone_within([{"pid": info2["pid"], "start": info2.get("pstart")}])
        ctx.check(f"the leftover is stopped with one line, got {text[-600:]!r}",
                  "stopped a Studio server left from" in text and gone)
        ctx.check(f"and init started its own, got {text[-600:]!r}", "?mode=setup" in text
                  and f"127.0.0.1:{info2['port']}/" not in text)
    finally:
        _stop_root_studio(proc2, info2)
        shutil.rmtree(tmp, ignore_errors=True)


@test
def test_a_stale_owner_watch_never_ends_a_new_halo(ctx: Ctx):
    """Judge item 4: a `halo` whose environment carries HALO_OWNER_WATCH of a halo that is gone, or of a live one that
    did not start it (a tmux server kept them), starts and stays up as a root; `halo --tmux` hands tmux no owner
    variables. Red at 18fbd47e (it ended itself in 0.2 s)."""
    from halo_harness import bg_run
    tmp = Path(tempfile.mkdtemp(prefix="halo-r10-stale-"))
    dead_pid, dead_start = _dead_owner()
    other = subprocess.Popen([sys.executable, str(SLEEPER), str(tmp / "other.json")], stdin=subprocess.DEVNULL)
    other_start = None
    try:
        deadline = time.time() + 20
        while not (tmp / "other.json").exists() and time.time() < deadline:
            time.sleep(0.05)
        other_start = _start_time(other.pid)
        cases = (("a gone owner", f"{dead_pid}:{dead_start}"),
                 ("a live owner that did not start it", f"{other.pid}:{other_start}"))
        for i, (name, watch) in enumerate(cases):
            home = tmp / f"home-{i}"
            proc, info = _root_studio(home, {"HALO_OWNER_WATCH": watch, "HALO_OWNER": "1-0123456789"})
            try:
                if i == 1:
                    _end_tree_we_started(other.pid, other_start)
                time.sleep(3.0)
                ctx.check(f"{name}: the new halo is still up 3 s on",
                          proc.poll() is None and _same(info["pid"], info.get("pstart")))
                ctx.check(f"{name}: it is a root (its own owner), got {info.get('owner_pid')}",
                          info.get("owner_pid") == info["pid"])
            finally:
                _stop_root_studio(proc, info)
        seen: dict = {}

        def fake_call(cmd, **kw):
            seen.update(kw)
            return 0
        saved = {k: os.environ.get(k) for k in ("HALO_OWNER", "HALO_OWNER_WATCH")}
        os.environ.update(HALO_OWNER="4242-0123456789", HALO_OWNER_WATCH="4242:123")
        try:
            bg_run.run_in_tmux(["--version"], which=lambda _n: "/usr/bin/tmux", call=fake_call)
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        env = seen.get("env") or {}
        ctx.check(f"`halo --tmux` hands tmux no owner variables, got {[k for k in env if k.startswith('HALO_OWNER')]}",
                  bool(env) and not any(k.startswith("HALO_OWNER") for k in env))
    finally:
        _end_tree_we_started(other.pid, other_start)
        other.wait(timeout=10)
        shutil.rmtree(tmp, ignore_errors=True)


@test
def test_an_unreadable_start_time_is_never_signalled(ctx: Ctx):
    """Should-fix (c): a ledger row with no recorded start time is never signalled on its pid alone."""
    from halo_harness import children as C
    from halo_harness import closing
    state = Path(tempfile.mkdtemp(prefix="halo-r10-nostart-")) / ".halo"
    state.mkdir(parents=True)
    p = subprocess.Popen([sys.executable, str(SLEEPER), str(state / "c.json")], stdin=subprocess.DEVNULL)
    start = _start_time(p.pid)
    try:
        ctx.check("no start time: no proof", C.provably_same(p.pid, None) is False)
        ctx.check("the right start time: proof", C.provably_same(p.pid, start) is True)
        closing.stop_entries([{"pid": p.pid, "start_time": None, "what": "schedule"}], state_dir=state,
                             polite_s=0.3, hard_s=0.3)
        ctx.check("stop_entries left it running", _same(p.pid, start))
    finally:
        _end_tree_we_started(p.pid, start)
        p.wait(timeout=10)


@test
def test_kept_things_are_in_the_ledger_and_the_browser_is_never_halos(ctx: Ctx):
    """Should-fix (b): what a person asked to keep (host serve, the supervisor, the updater, a terminal window) is
    registered as kept, so `halo ps` lists it and the way out names it. Should-fix (a): the browser Halo opens for
    the person (Studio's page, an MCP login) carries none of Halo's owner variables."""
    import webbrowser
    from halo_harness import children as C
    from halo_harness import closing
    state = Path(tempfile.mkdtemp(prefix="halo-r10-keptreg-")) / ".halo"
    state.mkdir(parents=True)
    saved_env = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
    os.environ["BRIDGE_STATE_DIR"] = str(state)
    p = subprocess.Popen([sys.executable, str(SLEEPER), str(state / "k.json")], stdin=subprocess.DEVNULL)
    start = _start_time(p.pid)
    try:
        for what in ("host", "supervisor", "update", "terminal"):
            closing.register_kept(p, what, ["x"])
            row = next((r for r in C.load(state) if r["pid"] == p.pid), {})
            ctx.check(f"{what}: in the ledger as kept, got {row}", row.get("what") == what and row.get("keep") is True)
            ctx.check(f"{what}: kept for the closing procedure", closing.kept(row))
            ctx.check(f"{what}: the line names its own stop, got {closing._stop_line(row)!r}",
                      bool(closing._stop_line(row)) and "halo stop" not in closing._stop_line(row))
    finally:
        _end_tree_we_started(p.pid, start)
        p.wait(timeout=10)
        for k, v in saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    seen: list = []
    saved_open = webbrowser.open
    saved = {k: os.environ.get(k) for k in ("HALO_OWNER", "HALO_OWNER_WATCH")}
    os.environ.update(HALO_OWNER="4242-0123456789", HALO_OWNER_WATCH="4242:123")

    def fake_open(url, *a, **k):
        seen.append((url, os.environ.get("HALO_OWNER"), os.environ.get("HALO_OWNER_WATCH")))
        return True
    webbrowser.open = fake_open
    try:
        from halo_harness.studio.launch import _open
        _open("http://127.0.0.1:9/studio")
        from halo_harness.mcp import oauth
        ctx.check("the MCP login opens the browser through the same opener",
                  "open_url(authorize_url)" in Path(oauth.__file__).read_text(encoding="utf-8"))
        closing.open_url("http://127.0.0.1:9/login")
    finally:
        webbrowser.open = saved_open
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    ctx.check(f"both opened with no owner variables, got {seen}",
              len(seen) == 2 and all(s[1] is None and s[2] is None for s in seen))


def _halo(home: Path, *args, timeout: float = 120):
    from halo_harness.selfexec import python_argv
    return subprocess.run(python_argv() + list(args), env=_env(home), capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout, cwd=str(home))


def _served(home: Path) -> list:
    """The fake llama-server(s) `halo local serve` started for this home: [{pid, start}] from its registry."""
    try:
        rows = json.loads((home / ".halo" / "run" / "local-servers.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    rows = rows.get("servers", rows) if isinstance(rows, dict) else rows
    out = []
    for r in rows if isinstance(rows, list) else []:
        if isinstance(r, dict) and isinstance(r.get("pid"), int):
            out.append({"pid": r["pid"], "start": r.get("proc_start"), "owner": r.get("owner_pid")})
    return out


def _gguf(home: Path) -> str:
    f = home / "models" / "r10-tiny-Q4_K_M.gguf"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(b"GGUF" + b"\0" * 2048)
    fake = [sys.executable, str(REPO / "tests" / "helpers" / "fake_llama_server.py")]
    r = _halo(home, "config", "set", "huggingface.llama_server_bin", json.dumps(fake))
    assert r.returncode == 0, r.stderr[-400:]
    return str(f)


@test
def test_a_local_model_server_stops_with_the_last_halo_of_its_home(ctx: Ctx):
    """Real-use bug 2: `halo local serve` returns at once and says the server "stops when the last Halo process on
    this home exits". With no other Halo process the server is gone within five seconds; with one running (a `halo
    studio`) it stays, and it is gone within five seconds of that one ending -- Ctrl+C, SIGTERM, a closed terminal,
    a hard kill (its home watch outlives the hard kill; the server is someone else's binary)."""
    tmp = Path(tempfile.mkdtemp(prefix="halo-r10-serve-"))
    started: list = []
    try:
        home = tmp / "alone"
        model = _gguf(home)
        r = _halo(home, "local", "serve", model)
        rows = _served(home)
        started += rows
        ctx.check(f"alone: it started and said so, got {r.returncode} {r.stdout[-300:]!r}",
                  r.returncode == 0 and bool(rows) and "stops when the last Halo process" in r.stdout)
        ctx.check(f"alone: the server is gone within {BOUND_S:.0f} s (no Halo runs on this home)",
                  not _gone_within(rows))
        for way in ("ctrl_c", "sigterm", "sighup", "kill"):
            home = tmp / f"beside-{way}"
            model = _gguf(home)
            proc, info = _root_studio(home)
            try:
                r = _halo(home, "local", "serve", model)
                rows = _served(home)
                started += rows
                time.sleep(2.0)
                ctx.check(f"{way}: with a Halo of the home running, the server stays, got {r.returncode} {rows}",
                          bool(rows) and all(_same(s["pid"], s["start"]) for s in rows))
                if way == "ctrl_c":
                    os.kill(proc.pid, signal.CTRL_BREAK_EVENT if WIN else signal.SIGINT)
                elif way == "sigterm":
                    proc.terminate()
                elif way == "sighup" and not WIN:
                    os.kill(proc.pid, signal.SIGHUP)
                else:
                    proc.kill()
                try:
                    proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    proc.kill()
                ctx.check(f"{way}: the server is gone within {BOUND_S:.0f} s of the last Halo of its home",
                          not _gone_within(rows))
            finally:
                _stop_root_studio(proc, info)
    finally:
        for s in started:
            _end_tree_we_started(s["pid"], s["start"])
        shutil.rmtree(tmp, ignore_errors=True)


_HUNG = r'''
import socket, sys, threading, time, signal, os
sys.path.insert(0, sys.argv[1])
from halo_harness import closing
closing.install()
srv = socket.socket(); srv.bind(("127.0.0.1", 0)); srv.listen(8)
def call():  # a model call that never answers
    c = socket.create_connection(srv.getsockname()); c.recv(1)
from concurrent.futures import ThreadPoolExecutor
pool = ThreadPoolExecutor(2); pool.submit(call)  # a sub-agent's call in a pool thread
if hasattr(signal, "SIGHUP"):
    signal.signal(signal.SIGHUP, closing.signal_exit(129))
signal.signal(signal.SIGTERM, closing.signal_exit(143))
if hasattr(signal, "SIGBREAK"):  # Ctrl+Break behaves as Ctrl+C does (KeyboardInterrupt, when bytecode runs)
    signal.signal(signal.SIGBREAK, signal.default_int_handler)
closing.arm_second_ctrl_c()
open(sys.argv[2], "w").write("ready")
try:
    call()  # the main thread in its own call
except KeyboardInterrupt:
    closing.hard_exit(130)
    sys.exit(130)
'''


@test
def test_a_one_shot_with_calls_in_flight_ends_when_told(ctx: Ctx):
    """Real-use bugs 3 and 4: a process whose main thread and a pool thread (a sub-agent) both sit in model calls that
    never answer ends within the bound when told: SIGHUP (a closed terminal) and SIGTERM on POSIX -- interpreter exit
    used to join the pool thread for ever -- and on Windows a second Ctrl+C (the console's handler: the main thread in
    a socket read never sees the first). In-flight calls are abandoned; the exit code is the conventional one."""
    tmp = Path(tempfile.mkdtemp(prefix="halo-r10-hung-"))
    script = tmp / "hung.py"
    script.write_text(_HUNG, encoding="utf-8")
    ways = (("second Ctrl+C", 130),) if WIN else (("SIGHUP", 129), ("SIGTERM", 143), ("Ctrl+C", 130))
    try:
        for name, code in ways:
            flag = tmp / f"{code}.ready"
            kw: dict = {"stdin": subprocess.DEVNULL, "stdout": subprocess.PIPE, "stderr": subprocess.PIPE, "text": True,
                        "env": _env(tmp / "home")}
            if WIN:
                kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            proc = subprocess.Popen([sys.executable, str(script), str(REPO), str(flag)], **kw)
            deadline = time.time() + 60
            while not flag.exists() and time.time() < deadline and proc.poll() is None:
                time.sleep(0.05)
            time.sleep(0.5)
            if WIN:  # two console control events (Ctrl+Break stands in: Windows cannot send Ctrl+C to another group)
                os.kill(proc.pid, signal.CTRL_BREAK_EVENT)
                time.sleep(0.5)
                os.kill(proc.pid, signal.CTRL_BREAK_EVENT)
            else:
                sig = {"SIGHUP": signal.SIGHUP, "SIGTERM": signal.SIGTERM, "Ctrl+C": signal.SIGINT}[name]
                os.kill(proc.pid, sig)
            t0 = time.monotonic()
            try:
                proc.wait(timeout=BOUND_S + 1)
            except subprocess.TimeoutExpired:
                pass
            took = time.monotonic() - t0
            ended = proc.poll()
            if ended is None:
                proc.kill()
            proc.communicate(timeout=10)
            ctx.check(f"{name}: the process ended within {BOUND_S:.0f} s with {code}, got {ended} after {took:.1f} s",
                      ended == code and took <= BOUND_S)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


_STRICT_JOB = r'''
import ctypes, sys
from ctypes import wintypes
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.CreateJobObjectW.restype = wintypes.HANDLE
k32.GetCurrentProcess.restype = wintypes.HANDLE
k32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
job = k32.CreateJobObjectW(None, None)  # no BREAKAWAY_OK: what a CI runner's Job may be
assert job and k32.AssignProcessToJobObject(job, k32.GetCurrentProcess())
sys.path.insert(0, sys.argv[1])
from halo_harness import closing
from halo_harness import subprocess_safe as sp
p = sp.Popen([sys.executable, "-c", "print('started')"], stdout=sp.PIPE, text=True,
             **closing.kept_kwargs({"stdin": sp.DEVNULL, "stderr": sp.DEVNULL}))
print(p.communicate(timeout=60)[0].strip())
'''


@test
def test_a_kept_spawn_starts_inside_a_job_that_forbids_breakaway(ctx: Ctx):
    """Windows: inside a Job that does not allow breakaway (a CI runner's), a kept or home-tied spawn is retried
    without the breakaway flag -- and the retry must not hand the child the DEVNULL handle the failed attempt closed
    ([Errno 9] Bad file descriptor: every managed engine failed to start on the CI Windows runner)."""
    if not WIN:
        ctx.check("POSIX has no Job objects: nothing to break away from", True)
        return
    r = subprocess.run([sys.executable, "-c", _STRICT_JOB, str(REPO)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120, env=_env(Path(tempfile.mkdtemp())))
    ctx.check(f"it started, got {r.returncode} {r.stdout[-200:]!r} {r.stderr[-300:]!r}",
              r.returncode == 0 and r.stdout.strip().endswith("started"))


@test
def test_the_sweep_at_start_costs_milliseconds(ctx: Ctx):
    """A normal launch's sweep (a ledger of live children with living owners, or none) is a few milliseconds."""
    from halo_harness import children as C
    from halo_harness import closing
    state = Path(tempfile.mkdtemp(prefix="halo-r10-cost-")) / ".halo"
    state.mkdir(parents=True)
    empty = []
    for _ in range(5):
        t = time.perf_counter()
        closing.sweep(state, say=lambda _l: None)
        empty.append(time.perf_counter() - t)
    procs = [subprocess.Popen([sys.executable, str(SLEEPER), str(state / f"c{i}.json")], stdin=subprocess.DEVNULL)
             for i in range(5)]
    try:
        for p in procs:
            C.register(p.pid, "schedule", ["sleeper"], state_dir=state)
        full = []
        for _ in range(5):
            t = time.perf_counter()
            closing.sweep(state, say=lambda _l: None)
            full.append(time.perf_counter() - t)
        e_ms, f_ms = sorted(empty)[2] * 1000, sorted(full)[2] * 1000
        ctx.check(f"no ledger: {e_ms:.1f} ms (median of 5), under 50 ms", e_ms < 50)
        ctx.check(f"five live children of a living owner: {f_ms:.1f} ms (median of 5), under 250 ms", f_ms < 250)
        ctx.check("and nothing was stopped", all(p.poll() is None for p in procs))
    finally:
        for p in procs:
            _end_tree_we_started(p.pid, _start_time(p.pid))
            p.wait(timeout=10)


@test
def test_halo_ps_lists_a_planted_stray_and_halo_stop_ends_it(ctx: Ctx):
    """`halo ps` shows the ledger with each owner alive or gone and, on POSIX, a stray the ledger lost (found by its
    HALO_OWNER marker and this home in its environment); `halo stop --orphans` ends what has no living owner and not
    what was kept; the doctor's row counts them. Windows lists no strays (no cheap way to read another process's
    environment): the ledger part runs there."""
    import contextlib
    import io
    from halo_harness import closing, ps_cli
    from halo_harness.doctor import _check_orphans
    home = Path(tempfile.mkdtemp(prefix="halo-r10-ps-"))
    state = home / ".halo"
    state.mkdir(parents=True)
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
    os.environ["BRIDGE_TEST_HOME"] = str(home)
    os.environ.pop("BRIDGE_STATE_DIR", None)
    planted: list = []
    try:
        dead_pid, dead_start = _dead_owner()
        orphan = _plant(state, "schedule", dead_pid, dead_start)
        kept = _plant(state, "bg", dead_pid, dead_start, keep=True)
        planted += [orphan, kept]
        stray = None
        if not WIN:
            env = dict(_env(home), **{closing.MARKER: closing.ident(dead_pid, dead_start)})
            tmp = Path(tempfile.mkdtemp(prefix="halo-r10-stray-"))
            proc = subprocess.Popen([sys.executable, str(SLEEPER), str(tmp / "s.json")], env=env, stdin=subprocess.DEVNULL)
            deadline = time.time() + 20
            while not (tmp / "s.json").exists() and time.time() < deadline:
                time.sleep(0.05)
            stray = {"proc": proc, "pid": proc.pid, "start": _start_time(proc.pid)}
            planted.append(stray)
        table = ps_cli.rows()
        by = {r["pid"]: r for r in table}
        ctx.check(f"the orphan is listed, owner gone, not kept, got {by.get(orphan['pid'])}",
                  by.get(orphan["pid"], {}).get("owner") == "gone" and by[orphan["pid"]]["kept"] is False)
        ctx.check(f"the kept run is listed as kept, got {by.get(kept['pid'])}", by.get(kept["pid"], {}).get("kept") is True)
        if stray:
            ctx.check(f"the stray the ledger lost is listed by its marker, owner gone, got {by.get(stray['pid'])}",
                      by.get(stray["pid"], {}).get("kind") == "stray" and by[stray["pid"]]["owner"] == "gone")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            ps_cli.cmd_ps([])
        ctx.check(f"`halo ps` prints one row each, got {out.getvalue()!r}", str(orphan["pid"]) in out.getvalue()
                  and str(kept["pid"]) in out.getvalue() and "KIND" in out.getvalue())
        row = _check_orphans(state)
        n = 2 if stray else 1
        ctx.check(f"the doctor's row: {n} without a living owner, with the command, got {row!r}",
                  bool(row) and f"{n} process" in row and "halo stop --orphans" in row)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = ps_cli.cmd_stop(["--orphans"])
        ctx.check(f"`halo stop --orphans` ends them, got {rc} {out.getvalue()!r}", rc == 0
                  and not _same(orphan["pid"], orphan["start"]) and (not stray or not _same(stray["pid"], stray["start"])))
        ctx.check("and leaves the kept one", _same(kept["pid"], kept["start"]))
        ctx.check(f"the doctor's row is gone, got {_check_orphans(state)!r}", _check_orphans(state) is None)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = ps_cli.cmd_stop([str(kept["pid"])])
        ctx.check(f"`halo stop <pid>` ends a kept one, got {rc} {out.getvalue()!r}", rc == 0
                  and not _same(kept["pid"], kept["start"]))
        with contextlib.redirect_stderr(io.StringIO()):
            rc = ps_cli.cmd_stop(["999999999"])
        ctx.check(f"a pid that is not Halo's here: exit 1, nothing signalled, got {rc}", rc == 1)
    finally:
        for p in planted:
            _end_tree_we_started(p["pid"], p["start"])
            try:
                p["proc"].wait(timeout=10)
            except Exception:
                pass
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


@test
def test_a_kept_spawn_has_its_own_marker_and_no_owner_watch(ctx: Ctx):
    from halo_harness import closing
    kw = closing.kept_kwargs({"stdin": None}, env={"PATH": "x", closing.MARKER: "1-abc", closing.WATCH: "1:abc"})
    ctx.check(f"a kept marker, no watch, got {kw['env']}", kw["env"][closing.MARKER].startswith(closing.KEPT_PREFIX)
              and closing.WATCH not in kw["env"] and kw["env"]["PATH"] == "x")
    if WIN:
        ctx.check("Windows: it breaks away from the Job object", kw["creationflags"] & closing._BREAKAWAY)
    plain = closing.before_spawn({"env": {"PATH": "x"}})
    if os.environ.get(closing.MARKER):
        ctx.check("a caller's own environment still gets the tree's marker", plain["env"].get(closing.MARKER))


class _NoTimer:
    """closing's `threading` for a test that arms hard_exit for real: its timer thread is recorded, never started."""

    def __init__(self, started: list) -> None:
        import threading
        self._threading = threading
        self._started = started

    def __getattr__(self, name):
        return getattr(self._threading, name)

    def Thread(self, *a, **kw):  # noqa: N802 -- stands in for threading.Thread
        from types import SimpleNamespace
        return SimpleNamespace(start=lambda: self._started.append(kw.get("name")))


_Z3_KEYS = ("installed", "deadline", "closed", "hard_exit")


def _closing_state_saved() -> dict:
    from halo_harness import closing
    return {k: closing._STATE[k] for k in _Z3_KEYS if k in closing._STATE}


def _closing_state_back(saved: dict) -> None:
    from halo_harness import closing
    for k in _Z3_KEYS:
        if k in saved:
            closing._STATE[k] = saved[k]
        else:
            closing._STATE.pop(k, None)


def _way_out(installed: bool, code, quit_called: bool) -> dict:
    """BridgeApp._bound_the_way_out on a stand-in app, inside a running loop, with closing's state as `installed` says
    and hard_exit's timer never started (whatever it arms is recorded); everything it changed is put back."""
    import asyncio
    from types import SimpleNamespace
    from unittest import mock
    from halo_harness import closing
    from halo_harness.tui.app import BridgeApp
    app = SimpleNamespace(return_code=code, controller=SimpleNamespace(quit_called=quit_called))
    timers: list = []
    seen: dict = {}

    async def body():
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: None)
        first = getattr(loop, "_default_executor", None)
        BridgeApp._bound_the_way_out(app)
        seen.update(deadline=closing._STATE.get("deadline"), stop_asked=closing.stop_asked(),
                    fresh_pool=getattr(loop, "_default_executor", None) is not first)
    saved = _closing_state_saved()
    closing._STATE.update(installed=installed, deadline=None, closed=False)
    closing._STATE.pop("hard_exit", None)
    try:
        with mock.patch.object(closing, "threading", _NoTimer(timers)):
            asyncio.run(body())
    finally:
        _closing_state_back(saved)
    return {"timers": timers, **seen}


@test
def test_z3_at_unmount_the_terminal_app_arms_the_deadline_and_a_fresh_pool_never_the_bound(ctx: Ctx):
    """3.6.0.17 Z3-1 (rewrites Z2's `test_z2_the_terminal_apps_way_out_arms_the_bound_only_in_a_real_halo`): every way
    out of the terminal app passes its unmount; there a real halo arms the closing deadline and hands the loop a fresh
    pool (asyncio's join at the end of app.run waits on nothing the app started), and arms NO hard exit, on a quit, on
    the restart exit and on an exception exit alike: `closing.stop_asked()` stays false until the quit itself. A test's
    app (closing not installed) changes nothing."""
    off = _way_out(False, 0, True)
    ctx.check(f"a test's app arms nothing and keeps its pool, got {off}",
              off["timers"] == [] and off["deadline"] is None and not off["fresh_pool"])
    for name, code, quit_called in (("a confirmed quit", 0, True), ("the restart exit", 91, False),
                                    ("an exception exit", None, False)):
        row = _way_out(True, code, quit_called)
        ctx.check(f"{name}: the deadline is armed and the loop has a fresh pool, got {row}",
                  row["deadline"] is not None and row["fresh_pool"])
        ctx.check(f"{name}: no hard exit is armed at unmount and stop_asked() is still false, got {row}",
                  row["timers"] == [] and row["stop_asked"] is False)


def _terminal_way_out(code, *, raises: bool = False, restart_code: "int | None" = None, hand_off_s: float = 8.0):
    """tui/launch.py run_tui (and, for /update's restart exit, cli._run_full_screen with its hand-off) on a stand-in
    app and controller, in a 'real halo' (closing installed) whose hard_exit is armed for real with its timer never
    started. Returns the ordered events: the app's run and unmount, the controller's quit (with stop_asked() at that
    moment), launch.py's last line, the exit hooks run on the main path, each hard exit armed (with its code, its grace and the injected clock),
    and the hand-off's end on that clock (it takes `hand_off_s` there, no real sleep)."""
    import atexit
    import contextlib
    import io
    from types import SimpleNamespace
    from unittest import mock
    from halo_harness import cli, closing, privateio, theme, update_detached
    from halo_harness.tui import app as A
    from halo_harness.tui import console_mode, launch
    events: list = []
    clock = [0.0]
    timers: list = []
    real_hard_exit = closing.hard_exit

    class Controller:
        quit_called = False
        stopped_line_shown = False

        def quit(self):
            if not self.quit_called:
                events.append(("quit", closing.stop_asked()))
            self.quit_called = True
            return 0

        @property
        def stopped_line(self):
            events.append("last line")
            return "stopped: gpu-box helper (pid 4242)"

    class App:
        def __init__(self, controller, **_kw):
            self.controller, self.return_code = controller, None

        def run(self):
            events.append("app.run")
            self.return_code = code
            if code == 0:
                self.controller.quit()  # the app's own quit card ran it
            A.BridgeApp._bound_the_way_out(self)  # Textual's unmount
            events.append("unmount")
            if raises:
                raise RuntimeError("the driver failed")

    def hard_exit(c, g=closing.EXIT_GRACE_S):
        events.append(("hard_exit", c, g, clock[0]))
        real_hard_exit(c, g)

    def hand_off(**_kw):  # the updater's start, stood in: it takes `hand_off_s` on the injected clock
        clock[0] += hand_off_s
        events.append(("hand-off done", clock[0]))
        return 0
    ctl = Controller()
    args = SimpleNamespace(demo=True, cwd=None, stress=0, theme=None, prompt=None, no_inline_images=False,
                           no_intro=True)
    saved = _closing_state_saved()
    closing._STATE.update(installed=True, deadline=None, closed=False)
    closing._STATE.pop("hard_exit", None)
    out = io.StringIO()
    result: dict = {}
    try:
        with mock.patch.object(A, "BridgeApp", type("BridgeApp", (App,), {"_bound_the_way_out":
                                                                         A.BridgeApp._bound_the_way_out})), \
                mock.patch.object(launch, "_build_demo_controller", lambda _a: (ctl, None, None, None)), \
                mock.patch.object(theme, "load_persisted_theme", lambda: None), \
                mock.patch.object(theme, "removed_theme_notice", lambda *_a, **_k: ""), \
                mock.patch.object(console_mode, "install", lambda: SimpleNamespace(restore=lambda: None)), \
                mock.patch.object(privateio, "tighten_state_tree", lambda _p: 0), \
                mock.patch.object(closing, "close", lambda **_kw: events.append("close") or []), \
                mock.patch.object(atexit, "_run_exitfuncs", lambda: events.append("exit hooks")), \
                mock.patch.object(closing, "hard_exit", hard_exit), \
                mock.patch.object(closing, "threading", _NoTimer(timers)), \
                mock.patch.object(update_detached, "run_after_exit", hand_off), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            try:
                result["code"] = cli._run_full_screen(args, ["--demo"]) if restart_code else launch.run_tui(args)
            except RuntimeError as e:
                result["raised"] = str(e)
    finally:
        _closing_state_back(saved)
    return {"events": events, "timers": timers, **result}


@test
def test_z3_the_terminal_apps_bound_comes_last_with_its_code(ctx: Ctx):
    """3.6.0.17 Z3-1 (b): the terminal app's way out arms closing.hard_exit at its END: after controller.quit and
    after launch.py's own last line, right after the exit hooks ran on the main path in the normal exit's order, with the app's code and
    the plain grace: one timer. An exception escaping app.run leaves with Python's 1, its quit run before stop is
    asked."""
    from halo_harness import closing
    quit_ = _terminal_way_out(0)
    ev = quit_["events"]
    ctx.check(f"a quit: nothing is armed before the app's way out is done, the bound is the last thing, with code 0 "
              f"and the grace, after the exit hooks, got {ev}",
              ev[-2:] == ["exit hooks", ("hard_exit", 0, closing.EXIT_GRACE_S, 0.0)]
              and [e for e in ev if isinstance(e, tuple) and e[0] == "hard_exit"] == [ev[-1]]
              and "last line" in ev and ev.index("last line") < ev.index("exit hooks") and "close" not in ev)
    ctx.check(f"a quit: one timer, got {quit_['timers']}", quit_["timers"] == ["halo-hard-exit"])
    err = _terminal_way_out(None, raises=True)
    ev = err["events"]
    ctx.check(f"an exception exit: the error still goes up, got {err}", err.get("raised") == "the driver failed")
    ctx.check(f"an exception exit: its quit runs before any stop is asked, got {ev}", ("quit", False) in ev)
    ctx.check(f"an exception exit: the bound comes last, after the exit hooks, with Python's 1, got {ev}",
              ev[-2:] == ["exit hooks", ("hard_exit", 1, closing.EXIT_GRACE_S, 0.0)] and ev.index(("quit", False)) < len(ev) - 2)


@test
def test_z3_the_restart_exits_bound_comes_after_the_hand_off_to_the_updater(ctx: Ctx):
    """3.6.0.17 Z3-1 (b): /update's restart exit hands over to the updater after the app (cli.py
    `_apply_update_and_relaunch`); on a slow machine that takes longer than any grace (stood in: 8 s on an injected
    clock, no real sleep). The bound is armed only once the hand-off returned, with the hand-off's code, so it can
    never cut it; controller.quit runs before any stop is asked."""
    from halo_harness import closing
    from halo_harness.update import RESTART_EXIT_CODE
    row = _terminal_way_out(RESTART_EXIT_CODE, restart_code=RESTART_EXIT_CODE, hand_off_s=8.0)
    ev = row["events"]
    bounds = [e for e in ev if isinstance(e, tuple) and e[0] == "hard_exit"]
    ctx.check(f"the process leaves with the hand-off's code, got {row.get('code')}", row.get("code") == 0)
    ctx.check(f"no bound is armed before the hand-off returned (one armed earlier fires inside it), got {ev}",
              bounds and all(b[3] >= 8.0 for b in bounds))
    ctx.check(f"one bound, last, after the exit hooks, with the hand-off's code and the plain grace, got {ev}",
              bounds == [ev[-1]] and ev[-2:] == ["exit hooks", ("hard_exit", 0, closing.EXIT_GRACE_S, 8.0)])
    ctx.check(f"the quit ran before any stop was asked, got {ev}", ("quit", False) in ev)
    ctx.check(f"one timer, got {row['timers']}", row["timers"] == ["halo-hard-exit"])


@test
def test_z3_hard_exit_armed_with_0_holds(ctx: Ctx):
    """3.6.0.17 Z3-1 (d): `hard_exit` is idempotent for code 0 too: a SIGTERM or a console close during a quit's
    grace arms no second timer with another code; the process leaves with the first one's 0."""
    from unittest import mock
    from halo_harness import closing
    timers: list = []
    saved = _closing_state_saved()
    closing._STATE.pop("hard_exit", None)
    try:
        with mock.patch.object(closing, "threading", _NoTimer(timers)):
            closing.hard_exit(0)
            closing.hard_exit(1)
            code = closing._STATE.get("hard_exit")
    finally:
        _closing_state_back(saved)
    ctx.check(f"one timer, got {timers}", timers == ["halo-hard-exit"])
    ctx.check(f"it leaves with the first code 0, got {code}", code == 0)


# A halo stand-in: closing installed first (as cli.main does), then an exit hook registered later that stops its own
# child politely (as a pack policy's `stop_all` does: imported at session build, EOF on stdin). Mode "bound" ends the
# way the terminal app's quit now ends (launch.bound_the_end), mode "plain" as 3.6.0.16's normal exit.
_LATER_HOOK = r"""
import atexit, json, subprocess, sys
from halo_harness import closing
closing.install(sweep_at_start=False)
from halo_harness import subprocess_safe  # a pack policy starts its process this way: the marker scan arms
child = subprocess_safe.Popen([sys.executable, "-c", "import sys; sys.stdin.read()"], stdin=subprocess.PIPE)
from halo_harness.bg_run import process_start_time
with open(sys.argv[2], "w") as f:
    json.dump({"pid": child.pid, "start": process_start_time(child.pid)}, f)
def stop_all():
    print(f"hook: close already ran={closing._STATE['closed']}", flush=True)
    child.stdin.close()
    child.wait(timeout=30)
atexit.register(stop_all)
if sys.argv[1] == "bound":
    from halo_harness.tui.launch import bound_the_end
    bound_the_end(0)
"""


@test
def test_z3_the_bound_runs_the_exit_hooks_in_the_normal_exits_order(ctx: Ctx):
    """3.6.0.17 Z3-1 (c), after its check: the end of the terminal app's way out runs the exit hooks exactly as a
    normal exit runs them (last registered first, the closing procedure last), never `close()` ahead of them. A hook
    registered after closing (a pack policy's `stop_all`) stops its child its own way first, and the marker scan then
    finds nothing to end: no false 'halo: ended ..., left running by a tool command' line, the same lines as 3.6.0.16."""
    tmp = Path(tempfile.mkdtemp(prefix="halo-z3-hooks-"))
    kids: list = []
    runs: dict = {}
    try:
        for mode in ("plain", "bound"):
            home = tmp / mode / "home"
            home.mkdir(parents=True)
            info = tmp / mode / "child.json"
            try:
                r = subprocess.run([sys.executable, "-c", _LATER_HOOK, mode, str(info)], env=_env(home),
                                   cwd=str(tmp / mode), capture_output=True, text=True, encoding="utf-8",
                                   errors="replace", timeout=120, stdin=subprocess.DEVNULL)
                runs[mode] = r
            finally:
                if info.exists():
                    kids.append(json.loads(info.read_text(encoding="utf-8")))
        plain, bound = runs["plain"], runs["bound"]
        ctx.check(f"3.6.0.16's exit: the hook runs before close, got {plain.stdout!r} {plain.stderr[-300:]!r}",
                  "hook: close already ran=False" in plain.stdout and plain.returncode == 0)
        ctx.check(f"the bound: no false 'halo: ended' line, got {bound.stderr[-400:]!r}", "halo: ended" not in bound.stderr)
        ctx.check(f"the bound: the later hook runs before close, as at a normal exit, got {bound.stdout!r}",
                  "hook: close already ran=False" in bound.stdout and bound.returncode == 0)
        ctx.check(f"the bound: the same last lines as 3.6.0.16's exit, got {bound.stderr[-400:]!r} vs {plain.stderr[-400:]!r}",
                  bound.stderr == plain.stderr and bound.stdout == plain.stdout)
        ctx.check(f"both children are gone, got {kids}", len(kids) == 2 and not any(_same(k['pid'], k['start']) for k in kids))
    finally:
        for k in kids:
            _end_tree_we_started(k["pid"], k["start"])
        shutil.rmtree(tmp, ignore_errors=True)


@test
def test_z2_the_catalog_refresh_asks_no_further_provider_once_halo_is_leaving(ctx: Ctx):
    """3.6.0.17 Z2-3: the catalog refresh at launch fetches one provider after another; once Halo is leaving (a quit
    armed its deadline after the first fetch) it asks no further provider, and what it has is said as before."""
    from unittest import mock
    from types import SimpleNamespace
    from halo_harness import closing
    from halo_harness.providers import anthropic_catalog, databricks, enablement
    from halo_harness.tui.slash import catalog_auto_refresh_worker
    fetched: list = []
    notes: list = []

    def first(state_dir, env=None, **_kw):
        fetched.append("openrouter")
        closing._STATE["deadline"] = time.monotonic() + closing.QUIT_BUDGET_S  # the quit begins meanwhile
        return True

    def second(state_dir, env=None, **_kw):
        fetched.append("anthropic")
        return True
    app = SimpleNamespace(controller=SimpleNamespace(state_dir=Path(tempfile.mkdtemp(prefix="z2-cat-")),
                                                    settings=SimpleNamespace(effective_env={})),
                          call_from_thread=lambda fn, *a, **kw: fn(*a, **kw),
                          notify=lambda text, **kw: notes.append(text))
    saved_deadline = closing._STATE.get("deadline")
    saved_net = os.environ.pop("BRIDGE_TEST_NO_BACKGROUND_NET", None)
    try:
        with mock.patch.object(enablement, "is_enabled_with_env", lambda name, env=None: name in ("openrouter", "anthropic")), \
                mock.patch.object(databricks, "refresh_openrouter_catalog_if_stale", first), \
                mock.patch.object(databricks, "load_models_json", lambda _d: {"a": 1, "b": 2}), \
                mock.patch.object(anthropic_catalog, "refresh_anthropic_catalog_if_stale", second):
            catalog_auto_refresh_worker(app)
    finally:
        closing._STATE["deadline"] = saved_deadline
        if saved_net is not None:
            os.environ["BRIDGE_TEST_NO_BACKGROUND_NET"] = saved_net
    ctx.check(f"only the first provider was asked, got {fetched}", fetched == ["openrouter"])
    ctx.check(f"what it has is said as before, got {notes}", notes == ["Catalog refreshed: OpenRouter (2 models)"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
