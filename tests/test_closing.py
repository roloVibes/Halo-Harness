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
                    fresh_pool=getattr(loop, "_default_executor", None) is not first,
                    kept_pool=first is not None and getattr(app, "_pool_at_unmount", None) is first)
        if getattr(loop, "_default_executor", None) is not first:
            first.shutdown(wait=True)  # asyncio.run ends only the loop's own (fresh) pool
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
    app (closing not installed) changes nothing. 3.6.0.17 Z4-1: the pool taken from the loop is kept on the app
    (`_pool_at_unmount`), for run_tui to join first."""
    off = _way_out(False, 0, True)
    ctx.check(f"a test's app arms nothing and keeps its pool, got {off}",
              off["timers"] == [] and off["deadline"] is None and not off["fresh_pool"] and not off["kept_pool"])
    for name, code, quit_called in (("a confirmed quit", 0, True), ("the restart exit", 91, False),
                                    ("an exception exit", None, False)):
        row = _way_out(True, code, quit_called)
        ctx.check(f"{name}: the deadline is armed and the loop has a fresh pool, got {row}",
                  row["deadline"] is not None and row["fresh_pool"])
        ctx.check(f"{name}: 3.6.0.17 Z4-1: the app keeps the pool it took from the loop (run_tui joins it), got {row}",
                  row["kept_pool"])
        ctx.check(f"{name}: no hard exit is armed at unmount and stop_asked() is still false, got {row}",
                  row["timers"] == [] and row["stop_asked"] is False)


def _terminal_way_out(code, *, raises: bool = False, restart_code: "int | None" = None, hand_off_s: float = 8.0,
                      pool: str = "done", fail: "str | None" = None):
    """tui/launch.py run_tui (and, for /update's restart exit, cli._run_full_screen with its hand-off) on a stand-in
    app and controller, in a 'real halo' (closing installed) whose hard_exit is armed for real with its timer never
    started. Returns the ordered events: the app's run and unmount, the controller's quit (with stop_asked() at that
    moment), launch.py's last line, the exit hooks run on the main path, each hard exit armed (with its code, its grace and the injected clock),
    and the hand-off's end on that clock (it takes `hand_off_s` there, no real sleep).
    3.6.0.17 Z4-1: the app keeps the pool it had at unmount (`pool`: "done", a worker that has ended; "stuck", one
    that never ends, whose join only moves the injected clock on; "join-kbi", a Ctrl+C in that join); the pool's
    shut-down and the end of its join are events. `fail`: "quit-kbi" / "quit-error" (controller.quit raises a
    KeyboardInterrupt / a RuntimeError), "line-kbi" / "line-error" (the stopped line's print raises a
    KeyboardInterrupt / an OSError)."""
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
            if fail == "quit-kbi":
                raise KeyboardInterrupt
            if fail == "quit-error":
                raise RuntimeError("a stop failed")
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
            if code == 0 and fail is None:
                self.controller.quit()  # the app's own quit card ran it
            A.BridgeApp._bound_the_way_out(self)  # Textual's unmount
            self._pool_at_unmount = Pool()  # (outside a running loop _bound_the_way_out keeps none of its own)
            events.append("unmount")
            if raises:
                raise RuntimeError("the driver failed")

    class Worker:  # a pool thread
        def is_alive(self):
            if pool == "join-kbi":
                raise KeyboardInterrupt
            if pool == "done":
                events.append("pool joined")
            return pool != "done"

        def join(self, timeout=None):  # a stuck worker's join: the injected clock moves on, no real sleep
            clock[0] += timeout or 0.0

    class Pool:
        def __init__(self):
            self._threads = {Worker()}

        def shutdown(self, wait=True, *, cancel_futures=False):
            events.append(("pool shut down", wait, cancel_futures))

    class Out(io.StringIO):
        def write(self, s):
            if fail in ("line-kbi", "line-error") and "stopped:" in s:
                raise KeyboardInterrupt if fail == "line-kbi" else OSError("the terminal is gone")
            return super().write(s)

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
    out = Out()
    result: dict = {}
    pool_state = dict(getattr(launch, "_POOL", {}))
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
                mock.patch.object(launch, "_clock", lambda: clock[0], create=True), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            try:
                result["code"] = cli._run_full_screen(args, ["--demo"]) if restart_code else launch.run_tui(args)
            except (RuntimeError, OSError, KeyboardInterrupt) as e:
                result["raised"], result["raised_type"] = str(e), type(e).__name__
    finally:
        _closing_state_back(saved)
        if hasattr(launch, "_POOL"):
            launch._POOL.clear()
            launch._POOL.update(pool_state)
    return {"events": events, "timers": timers, "clock": clock[0], **result}


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
def test_z4_the_old_pool_is_joined_first_then_the_quit_then_the_exit_hooks(ctx: Ctx):
    """3.6.0.17 Z4-1 (b): the pool the app took from the loop at unmount is shut down without waiting (nothing new
    starts, queued work is cancelled) and joined as the FIRST step after app.run, before controller.quit, the last
    line, the hand-off and the exit hooks: a worker only in flight (a short git, the status line, `claude auth
    status`) ends with its child before the closing procedure's scan, as asyncio's join did in 3.6.0.16."""
    from halo_harness.update import RESTART_EXIT_CODE
    for name, row in (("a quit", _terminal_way_out(0)),
                      ("the restart exit", _terminal_way_out(RESTART_EXIT_CODE, restart_code=RESTART_EXIT_CODE)),
                      ("an exception exit", _terminal_way_out(None, raises=True))):
        ev = row["events"]
        after = ev[ev.index("unmount") + 1:]
        ctx.check(f"{name}: right after the app, its pool is shut down (no wait, queued work cancelled) and joined, "
                  f"before anything else of the way out, got {ev}",
                  after[:2] == [("pool shut down", False, True), "pool joined"])
        ctx.check(f"{name}: then the quit's last line and the exit hooks, the bound last, got {ev}",
                  "last line" in after and after.index("last line") < after.index("exit hooks")
                  and after[-1][0] == "hard_exit")
        if name != "a quit":
            ctx.check(f"{name}: controller.quit runs after the join, got {ev}", ("quit", False) in after)


@test
def test_z4_a_stuck_worker_is_given_up_at_one_bound_and_the_grace_is_then_short(ctx: Ctx):
    """3.6.0.17 Z4-1 (c): a worker that never ends is joined within ONE bound (closing.EXIT_GRACE_S, never past the
    closing deadline; an injected clock, no real sleep), then abandoned: the way out goes on, and the bound is armed
    with the short grace (the interpreter cannot end by itself then). With every worker done it is EXIT_GRACE_S."""
    from halo_harness import closing
    from halo_harness.tui import launch
    from halo_harness.update import RESTART_EXIT_CODE
    short = getattr(launch, "STUCK_GRACE_S", None)
    ctx.check(f"the short grace has its own name and is shorter than EXIT_GRACE_S, got {short}",
              short is not None and 0 < short < closing.EXIT_GRACE_S)
    stuck = _terminal_way_out(0, pool="stuck")
    ev = stuck["events"]
    ctx.check(f"the join gave up at its one bound on the injected clock, got {stuck['clock']}",
              abs(stuck["clock"] - closing.EXIT_GRACE_S) < 0.1)
    ctx.check(f"the way out went on, the bound last with the short grace, got {ev}",
              "last line" in ev and ev[-2:] == ["exit hooks", ("hard_exit", 0, short, stuck["clock"])])
    done = _terminal_way_out(0)
    ctx.check(f"every worker done: the plain grace, got {done['events']}",
              done["events"][-1] == ("hard_exit", 0, closing.EXIT_GRACE_S, 0.0))
    restart = _terminal_way_out(RESTART_EXIT_CODE, restart_code=RESTART_EXIT_CODE, pool="stuck", hand_off_s=8.0)
    ctx.check(f"the restart exit with a stuck worker: the bound after the hand-off, with the short grace, got "
              f"{restart['events']}", restart["events"][-1][:3] == ("hard_exit", 0, short)
              and restart["events"][-1][3] >= 8.0)


@test
def test_z4_the_bound_is_armed_whatever_the_way_outs_end_raises(ctx: Ctx):
    """3.6.0.17 Z4-1 (d): a step of run_tui's finally that raises (controller.quit, the stopped line's print, a
    Ctrl+C there or in the pool's join) still arms the bound, with the code cli.main gives that exit (130 for a
    Ctrl+C, as cli.main's own Ctrl+C; 1 for an error cli.main does not turn into a line of its own), and the exception
    goes on. An error controller.quit raises is swallowed there as before (the plain code)."""
    from halo_harness import closing
    from halo_harness.update import RESTART_EXIT_CODE
    g = closing.EXIT_GRACE_S
    for name, row, code, raised in (
            ("a Ctrl+C in controller.quit", _terminal_way_out(0, fail="quit-kbi"), 130, "KeyboardInterrupt"),
            ("a Ctrl+C in the stopped line's print", _terminal_way_out(0, fail="line-kbi"), 130, "KeyboardInterrupt"),
            ("an error in the stopped line's print", _terminal_way_out(0, fail="line-error"), 1, "OSError"),
            ("an error in controller.quit", _terminal_way_out(0, fail="quit-error"), 0, None),
            # 3.6.0.18 L (rewritten to the truth): run_tui's caller (cli._run_full_screen) takes that Ctrl+C once
            # the bound is armed: cli.main's one line and 130 returned, no exception goes on
            ("the restart exit, a Ctrl+C in controller.quit",
             _terminal_way_out(RESTART_EXIT_CODE, restart_code=RESTART_EXIT_CODE, fail="quit-kbi"), 130, None),
            ("a Ctrl+C in the pool's join", _terminal_way_out(None, pool="join-kbi"), 130, "KeyboardInterrupt")):
        ev = row["events"]
        ctx.check(f"{name}: the exception goes on, got {row.get('raised_type')}", row.get("raised_type") == raised)
        if raised is None and code == 130:
            ctx.check(f"{name}: run_tui's caller returns 130, got {row.get('code')}", row.get("code") == 130)
        ctx.check(f"{name}: the bound is armed last, after the exit hooks, with code {code}, got {ev}",
                  ev[-2:] == ["exit hooks", ("hard_exit", code, g, 0.0)])
        if name == "a Ctrl+C in the pool's join":
            ctx.check(f"{name}: the quit and its last line still ran, got {ev}",
                      ("quit", False) in ev and "last line" in ev)
        ctx.check(f"{name}: the hand-off never started, got {ev}", not any(
            isinstance(e, tuple) and e[0] == "hand-off done" for e in ev))


@test
def test_z4_the_way_out_starts_at_unmount_whatever_the_title_steps_raise(ctx: Ctx):
    """3.6.0.17 Z4-1 (e): BridgeApp.on_unmount's two title steps (deactivate_tui_mode, set_tui_driver) raising
    still arm the closing deadline, hand the loop a fresh pool and keep the old one; the error goes on."""
    import asyncio
    from types import SimpleNamespace
    from unittest import mock
    from halo_harness import closing, termtitle
    from halo_harness.tui.app import BridgeApp

    def boom(*_a):
        raise RuntimeError("the title could not be put back")
    for step in ("deactivate_tui_mode", "set_tui_driver"):
        app = SimpleNamespace(return_code=0, controller=SimpleNamespace(quit_called=True))
        app._bound_the_way_out = lambda app=app: BridgeApp._bound_the_way_out(app)
        seen: dict = {}

        async def body():
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, lambda: None)
            first = loop._default_executor
            try:
                BridgeApp.on_unmount(app)
            except RuntimeError as e:
                seen["raised"] = str(e)
            seen.update(deadline=closing._STATE.get("deadline"), fresh=loop._default_executor is not first,
                        kept=getattr(app, "_pool_at_unmount", None) is first)
            if loop._default_executor is not first:
                first.shutdown(wait=True)
        saved = _closing_state_saved()
        closing._STATE.update(installed=True, deadline=None, closed=False)
        try:
            with mock.patch.object(termtitle, step, boom):
                asyncio.run(body())
        finally:
            _closing_state_back(saved)
        ctx.check(f"{step} raising: the error goes on, got {seen}", seen.get("raised") == "the title could not be put back")
        ctx.check(f"{step} raising: the deadline armed, a fresh pool, the old one kept, got {seen}",
                  seen.get("deadline") is not None and seen.get("fresh") and seen.get("kept"))


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


# 3.6.0.18 L: a halo stand-in (closing installed first, as cli.main does) whose Ctrl+C comes in /update's hand-off
# ("hand-off") or escapes the terminal app ("app-held": the pool the unmount kept has a worker in a read that does not
# answer; "app-none": no worker). The held worker lets go only once the test writes the file argv[2].
_CTRL_C_WAY_OUT = r"""
import concurrent.futures, os, sys, time
from types import SimpleNamespace
from halo_harness import closing
closing.install(sweep_at_start=False)
from halo_harness import cli, privateio, theme, update_detached
from halo_harness.tui import app as A
from halo_harness.tui import console_mode, launch
mode, release = sys.argv[1], sys.argv[2]

def held():
    while not os.path.exists(release):
        time.sleep(0.05)

def held_pool():
    pool = concurrent.futures.ThreadPoolExecutor()
    pool.submit(held)
    return pool

def ctrl_c(**_kw):
    raise KeyboardInterrupt

if mode == "hand-off":
    update_detached.run_after_exit = ctrl_c  # a Ctrl+C in the hand-off's scans, its pin or the updater's start
    held_pool().shutdown(wait=False, cancel_futures=True)  # the worker the pool's join gave up on
    sys.exit(cli._apply_update_and_relaunch([]))

class Controller:
    quit_called, stopped_line, stopped_line_shown = True, "", False
    def quit(self):
        return 0

class App:
    def __init__(self, controller, **_kw):
        self.controller, self.return_code = controller, None
    def run(self):
        self._pool_at_unmount = held_pool() if mode == "app-held" else None  # what the unmount kept
        raise KeyboardInterrupt  # a Ctrl+C that escapes the app

A.BridgeApp = App
launch._build_demo_controller = lambda _a: (Controller(), None, None, None)
theme.load_persisted_theme = lambda: None
theme.removed_theme_notice = lambda *_a, **_k: ""
console_mode.install = lambda: SimpleNamespace(restore=lambda: None)
privateio.tighten_state_tree = lambda _p: 0
args = SimpleNamespace(demo=True, cwd=None, stress=0, theme=None, prompt=None, no_inline_images=False, no_intro=True)
sys.exit(cli._run_full_screen(args, ["--demo"]))
"""
_CTRL_C_BUDGET_S = 90.0  # a ceiling for the slowest runner, never a margin: what is read is the order of the events


def _ctrl_c_way_out(mode: str) -> dict:
    """The stand-in above in a child: its exit code, its stderr, and whether it was gone while its worker was still
    held (the test writes the release file only after the child is gone, or once the ceiling passed)."""
    tmp = Path(tempfile.mkdtemp(prefix="halo-l-ctrl-c-"))
    home = tmp / "home"
    home.mkdir()
    release = tmp / "release"
    proc = subprocess.Popen([sys.executable, "-c", _CTRL_C_WAY_OUT, mode, str(release)], env=_env(home),
                            cwd=str(tmp), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", errors="replace")
    row: dict = {}
    try:
        try:
            _out, err = proc.communicate(timeout=_CTRL_C_BUDGET_S)
            row["gone_while_held"] = not release.exists()
        except subprocess.TimeoutExpired:
            row["gone_while_held"] = False
            release.write_text("go", encoding="utf-8")
            _out, err = proc.communicate(timeout=_CTRL_C_BUDGET_S)
        row.update(code=proc.returncode, err=err)
    finally:
        if not release.exists():
            release.write_text("go", encoding="utf-8")
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=30)
        shutil.rmtree(tmp, ignore_errors=True)
    return row


@test
def test_l_a_ctrl_c_in_the_update_hand_off_still_ends_through_the_bound_with_one_line_and_130(ctx: Ctx):
    """3.6.0.18 L (entry 1): a Ctrl+C while /update hands over to the updater (its process scans, its pin, the
    updater's start) reaches `bound_the_end` as every other way out of `_apply_update_and_relaunch` does: the process
    is gone with 130 and one line while a worker the pool's join gave up on is still held (before: no bound, and the
    interpreter's own join of that worker kept halo alive as long as the worker was)."""
    row = _ctrl_c_way_out("hand-off")
    err = row.get("err") or ""
    line = ("halo: interrupted while starting the update. `halo --version` shows what is installed; "
            "`halo update` starts it again.")
    ctx.check(f"gone while the worker was still held, got {row}", row.get("gone_while_held") is True)
    ctx.check(f"left with 130, got {row.get('code')}", row.get("code") == 130)
    ctx.check(f"the one line, once, and no traceback, got {err[-600:]!r}",
              err.count(line) == 1 and "Traceback" not in err)


@test
def test_l_a_ctrl_c_out_of_the_terminal_app_leaves_with_one_line_and_130(ctx: Ctx):
    """3.6.0.18 L (entry 2): a Ctrl+C that escapes the terminal app leaves with cli.main's own line for a Ctrl+C and
    130 on every system, stuck or not, and no traceback (before: Python's own code for an uncaught Ctrl+C and a
    traceback; 130 only when a stuck worker let the bound's grace end it)."""
    from halo_harness import cli
    line = getattr(cli, "INTERRUPTED_LINE", "\nhalo: interrupted").strip()
    for mode in ("app-held", "app-none"):
        row = _ctrl_c_way_out(mode)
        err = row.get("err") or ""
        ctx.check(f"{mode}: gone while the worker was still held, got {row}", row.get("gone_while_held") is True)
        ctx.check(f"{mode}: left with 130, got {row.get('code')}", row.get("code") == 130)
        ctx.check(f"{mode}: cli.main's one line, once, and no traceback, got {err[-600:]!r}",
                  err.count(line) == 1 and "Traceback" not in err)


@test
def test_l_a_ctrl_c_before_the_terminal_app_runs_still_arms_the_bound(ctx: Ctx):
    """3.6.0.18 L: a Ctrl+C raised in run_tui BEFORE its own try/finally (the session's setup) is caught by
    `cli._run_full_screen` too: the same one line and 130, and the bound is armed there (run_tui's finally never ran,
    so nobody else armed it; a stuck thread would hold the interpreter's end)."""
    import contextlib
    import io
    from unittest import mock
    from halo_harness import cli
    from halo_harness.tui import launch
    armed: list = []

    def interrupted(_args):
        raise KeyboardInterrupt()
    err = io.StringIO()
    with mock.patch.object(launch, "run_tui", interrupted), \
            mock.patch.object(launch, "bound_the_end", lambda code: armed.append(code)), \
            contextlib.redirect_stderr(err):
        code = cli._run_full_screen(object(), [])
    ctx.check(f"130, got {code}", code == 130)
    ctx.check(f"the bound armed once with 130, got {armed}", armed == [130])
    ctx.check(f"the one line, got {err.getvalue()!r}", err.getvalue().count(cli.INTERRUPTED_LINE.strip()) == 1)


@test
def test_l_a_thread_worker_posted_while_unmount_runs_never_holds_app_run(ctx: Ctx):
    """3.6.0.18 L (entry 4): a call posted to the loop while Unmount runs (a worker thread's call_from_thread) that
    starts a thread worker after the way out began: the loop's executor then runs nothing, so `app.run()` returns while
    that worker would still be held (before: the fresh pool ran it and asyncio's join at the end of `app.run()` waited
    for it, without limit on 3.10 and 3.11), and the quit's code is unchanged by the refused worker."""
    import asyncio
    import threading
    from textual.app import App
    from halo_harness import closing
    from halo_harness.tui.app import BridgeApp
    gate = threading.Event()
    seen: list = []

    def held():
        seen.append("worker started")
        gate.wait(_CTRL_C_BUDGET_S)
        seen.append("worker let go")

    class Late(App):
        _bound_the_way_out = BridgeApp._bound_the_way_out

        def on_mount(self) -> None:
            self.call_later(self.exit)

        def on_unmount(self) -> None:
            loop = asyncio.get_running_loop()

            async def start_late():  # what a worker's call_from_thread posts
                self.run_worker(held, thread=True, exit_on_error=True, name="late")
            poster = threading.Thread(target=lambda: asyncio.run_coroutine_threadsafe(start_late(), loop))
            poster.start()
            poster.join()
            self._bound_the_way_out()
    saved = _closing_state_saved()
    closing._STATE.update(installed=True, deadline=None, closed=False)
    app = Late()
    try:
        app.run(headless=True)
        seen.append("app.run returned")
    finally:
        gate.set()
        _closing_state_back(saved)
        old = getattr(app, "_pool_at_unmount", None)
        if old is not None:
            old.shutdown(wait=True)
    ctx.check(f"app.run returned while the late worker would still be held, got {seen}",
              "app.run returned" in seen and "worker let go" not in seen[:seen.index("app.run returned")])
    ctx.check(f"the late worker never ran, got {seen}", "worker started" not in seen)
    ctx.check(f"the quit's code is unchanged by the refused worker, got {app.return_code}", app.return_code == 0)


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
    import shutil
    folder = Path(tempfile.mkdtemp(prefix="z2-cat-"))
    app = SimpleNamespace(controller=SimpleNamespace(state_dir=folder,
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
        shutil.rmtree(folder, ignore_errors=True)  # 3.6.0.17 Z4 (S4): the test's own folder goes with it
    ctx.check(f"only the first provider was asked, got {fetched}", fetched == ["openrouter"])
    ctx.check(f"what it has is said as before, got {notes}", notes == ["Catalog refreshed: OpenRouter (2 models)"])


@test
def test_l_the_balance_refresh_makes_no_second_request_and_calls_nobody_back_once_halo_is_leaving(ctx: Ctx):
    """3.6.0.18 L (batch 2, entry 3): the OpenRouter balance refresh reads `/key`, then (with a management key)
    `/credits`; a quit that begins after the first request ends it there: one request, no call back into the app. The
    Experiential Labs worker (one request) calls nobody back either once Halo is leaving (before: two requests and a
    call back each)."""
    from unittest import mock
    from types import SimpleNamespace
    from halo_harness import closing
    from halo_harness.providers import config as pconfig, enablement, experiential_account, openrouter_account as ora
    from halo_harness.tui.slash import experiential_balance_refresh_worker, or_balance_refresh_worker
    asked: list = []
    called_back: list = []

    def key_info(base_url, api_key):
        asked.append("/key")
        closing._STATE["deadline"] = time.monotonic() + closing.QUIT_BUDGET_S  # the quit begins meanwhile
        return ora.OrKeyInfo(label="gpu-box", limit=None, usage=0.0180, limit_remaining=None, is_free_tier=False)

    def credits(base_url, management_key):
        asked.append("/credits")
        return ora.OrCredits(total_credits=10.0, total_usage=0.0180)

    def xp_credits(env=None):
        asked.append("xp /credits")
        closing._STATE["deadline"] = time.monotonic() + closing.QUIT_BUDGET_S
        return {"total_credits": 10.0, "total_usage": 0.0180}
    app = SimpleNamespace(controller=None, status_bar=SimpleNamespace(set_or_balance=None, set_provider_balance=None),
                          call_from_thread=lambda fn, *a, **kw: called_back.append(getattr(fn, "__name__", fn)))
    orc = SimpleNamespace(base_url="https://openrouter.ai/api/v1", api_key="sk-example")
    saved_deadline = closing._STATE.get("deadline")
    saved_cache = (ora._balance_cache, ora._balance_last_attempt_at)
    saved_net = os.environ.pop("BRIDGE_TEST_NO_BACKGROUND_NET", None)
    try:
        with mock.patch.object(enablement, "is_enabled_with_env", lambda name, env=None: True), \
                mock.patch.object(pconfig, "resolve_openrouter", lambda env=None: orc), \
                mock.patch.object(pconfig, "resolve_openrouter_management_key", lambda env=None: "mk-example"), \
                mock.patch.object(ora, "fetch_key_info", key_info), mock.patch.object(ora, "fetch_credits", credits), \
                mock.patch.object(experiential_account, "fetch_experiential_credits", xp_credits):
            closing._STATE["deadline"] = None
            or_balance_refresh_worker(app, force=True)
            or_asked, or_called = list(asked), list(called_back)
            closing._STATE["deadline"] = None
            experiential_balance_refresh_worker(app)
    finally:
        closing._STATE["deadline"] = saved_deadline
        ora._balance_cache, ora._balance_last_attempt_at = saved_cache
        if saved_net is not None:
            os.environ["BRIDGE_TEST_NO_BACKGROUND_NET"] = saved_net
    ctx.check(f"OpenRouter: one request, never /credits after the quit began, got {or_asked}", or_asked == ["/key"])
    ctx.check(f"OpenRouter: no call back into the app, got {or_called}", or_called == [])
    ctx.check(f"Experiential: its one request, then no call back, got {asked[len(or_asked):]} {called_back}",
              asked[len(or_asked):] == ["xp /credits"] and called_back == [])


# 3.6.0.18 L (batch 2, entry 1): a halo stand-in whose workers start programs around close(): "late" starts one after
# close() returned (an abandoned worker whose read answered late), "held" was already inside its start (past
# before_spawn) when close() began and creates its program only after close() returned. The thread that ran close()
# then starts a short program of its own (the way out's own), and the kept door is asked. Then the bound's end.
_LATE_START = r"""
import json, os, sys, threading, time
from halo_harness import closing, subprocess_safe
closing.install(sweep_at_start=False)
from halo_harness.bg_run import process_start_time
out = sys.argv[1]
rows = {}
LONG = [sys.executable, "-c", "import time; time.sleep(120)"]
closed, entered, release = threading.Event(), threading.Event(), threading.Event()
orig = closing.before_spawn

def held_before_spawn(kw, what=None):
    kw = orig(kw, what)
    if threading.current_thread().name == "held":
        entered.set()
        release.wait(60)
    return kw
closing.before_spawn = held_before_spawn

def start(name):
    try:
        p = subprocess_safe.Popen(LONG, stdin=subprocess_safe.DEVNULL, stdout=subprocess_safe.DEVNULL,
                                  stderr=subprocess_safe.DEVNULL)
        rows[name] = {"pid": p.pid, "start": process_start_time(p.pid)}
    except OSError as e:
        rows[name] = {"refused": str(e)}

def late():
    closed.wait(60)
    start("late")
    try:
        closing.before_spawn(closing.kept_kwargs(env=dict(os.environ)))
        rows["kept"] = "started"
    except OSError as e:
        rows["kept"] = str(e)

held = threading.Thread(target=start, args=("held",), name="held")
held.start()
entered.wait(60)
lines = closing.close(say=lambda _l: None)
closed.set()
release.set()
worker = threading.Thread(target=late, name="late")
worker.start()
worker.join(60)
held.join(60)
rows["own"] = subprocess_safe.run([sys.executable, "-c", "pass"], stdin=subprocess_safe.DEVNULL, timeout=60).returncode
with open(out, "w") as f:
    json.dump(rows, f)
closing.hard_exit(0, 0.5)
time.sleep(120)
"""


@test
def test_l_once_closed_nothing_new_starts_and_the_last_scan_ends_a_start_already_under_way(ctx: Ctx):
    """3.6.0.18 L (batch 2, entry 1): once close() has run, a worker's new program is refused ("halo is closing: nothing
    new is started"), a kept start is not, and the way out's own thread still starts what it needs. A start that was
    already under way when close() began creates its program after the marker scan: on Linux and macOS the bound's end
    scans once more and ends it, with its line (before: both programs outlived halo, their parent 1)."""
    tmp = Path(tempfile.mkdtemp(prefix="halo-l-late-"))
    home, out = tmp / "home", tmp / "rows.json"
    home.mkdir()
    rows: dict = {}
    try:
        r = subprocess.run([sys.executable, "-c", _LATE_START, str(out)], env=_env(home), cwd=str(tmp),
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
                           stdin=subprocess.DEVNULL)
        if out.exists():
            rows = json.loads(out.read_text(encoding="utf-8"))
        ctx.check(f"the stand-in ran to its end, got {r.returncode} {r.stderr[-400:]!r}", r.returncode == 0 and rows)
        late, held = rows.get("late") or {}, rows.get("held") or {}
        ctx.check(f"the late start is refused with the line, got {late}",
                  late.get("refused") == "halo is closing: nothing new is started")
        ctx.check(f"a kept start is never refused, got {rows.get('kept')}", rows.get("kept") == "started")
        ctx.check(f"the way out's own thread still starts its program, got {rows.get('own')}", rows.get("own") == 0)
        ctx.check(f"the start under way had its program, got {held}", bool(held.get("pid")))
        for name, row in (("late", late), ("held", held)):
            if row.get("pid"):
                ctx.check(f"{name}: its program is gone with halo, got {row}", not _same(row["pid"], row.get("start")))
        if not WIN and held.get("pid"):
            ctx.check(f"the last scan names what it ended, got {r.stderr[-400:]!r}",
                      f"(pid {held['pid']}), left running by a tool command" in r.stderr)
    finally:
        if not rows and out.exists():
            rows = json.loads(out.read_text(encoding="utf-8"))
        for row in rows.values():
            if isinstance(row, dict) and row.get("pid"):
                _end_tree_we_started(row["pid"], row.get("start"))
        shutil.rmtree(tmp, ignore_errors=True)


_REFUSED_ON_THE_WAY_OUT = r"""
import atexit, sys, threading
from pathlib import Path
from halo_harness import closing, subprocess_safe
mode, tmp = sys.argv[1], Path(sys.argv[2])
closing.install(sweep_at_start=False)  # the real process's first call: a pack policy's exit hook comes after it
from halo_harness.packs import policy
START = [sys.executable, "-c", "import sys; open(sys.argv[1], 'w').close()"]

class _Proc:  # a pack policy's process whose stop starts a program (a stand-in for a stop command)
    def stop(self):
        (tmp / "stop-ran").write_text("1")
        subprocess_safe.run(START + [str(tmp / "stop-started")], stdin=subprocess_safe.DEVNULL, timeout=60)

def hook():  # an exit hook that starts a program
    (tmp / "hook-ran").write_text("1")
    subprocess_safe.run(START + [str(tmp / "hook-started")], stdin=subprocess_safe.DEVNULL, timeout=60)

with policy._lock:
    policy._procs[("example-pack", "guard")] = _Proc()
atexit.register(hook)
other = threading.Thread(target=lambda: closing.close(say=lambda _l: None), name="other")  # hard_exit, the console
other.start()
other.join(60)
(tmp / "closed").write_text(str(bool(closing._STATE["closed"])))
if mode == "bound":
    from halo_harness.tui.launch import bound_the_end
    bound_the_end(0)
"""


@test
def test_a_start_refused_after_close_ends_an_exit_hook_and_a_stop_quietly(ctx: Ctx):
    """3.6.0.21 R5: when close() ran first on another thread, an exit hook and a pack's stop that start a program are
    refused (the refusal stays: its own type, a subclass of OSError) and end quietly: nothing is started, no "Exception
    ignored in atexit callback" or traceback reaches the person, and with the close trace on one line names each
    refusal. Both ways the exit hooks run: the interpreter's own exit and the terminal app's bound."""
    from halo_harness import closing
    ctx.check("the refusal is its own type, an OSError", issubclass(closing.ClosingRefused, OSError)
              and closing.ClosingRefused is not OSError)
    for mode in ("exit", "bound"):
        tmp = Path(tempfile.mkdtemp(prefix="halo-r5-refused-"))
        home, trace = tmp / "home", tmp / "trace.txt"
        home.mkdir()
        try:
            env = dict(_env(home), **{closing.TRACE: str(trace)})
            r = subprocess.run([sys.executable, "-c", _REFUSED_ON_THE_WAY_OUT, mode, str(tmp)], env=env, cwd=str(tmp),
                               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
                               stdin=subprocess.DEVNULL)
            ran = [n for n in ("closed", "hook-ran", "stop-ran") if (tmp / n).exists()]
            ctx.check(f"{mode}: close() ran first, then the hook and the stop ran, got {ran} {r.returncode} "
                      f"{r.stderr[-300:]!r}", ran == ["closed", "hook-ran", "stop-ran"]
                      and (tmp / "closed").read_text() == "True" and r.returncode == 0)
            started = [n for n in ("hook-started", "stop-started") if (tmp / n).exists()]
            ctx.check(f"{mode}: nothing was started, got {started}", not started)
            ctx.check(f"{mode}: no traceback for the person, got {r.stderr[-600:]!r}",
                      "Exception ignored" not in r.stderr and "Traceback" not in r.stderr
                      and "ClosingRefused" not in r.stderr and "halo is closing" not in r.stderr)
            lines = [ln for ln in (trace.read_text(encoding="utf-8").splitlines() if trace.exists() else [])
                     if "refused" in ln]
            ctx.check(f"{mode}: one trace line names each refusal, got {lines}",
                      len(lines) == 2 and all("python" in ln.lower() for ln in lines))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


@test
def test_a_tool_server_start_refused_after_close_names_its_program_in_the_trace(ctx: Ctx):
    """3.6.0.21 R5 (after the check): the third caller of before_spawn, a stdio tool server's start (mcp/stdio.py),
    passes its argv too, so the one trace line names the program, never "a program". In process: close() is marked
    as run, the trace points at a scratch file, and everything is put back exactly as found."""
    import asyncio
    from halo_harness import closing
    from halo_harness.mcp import stdio
    tmp = Path(tempfile.mkdtemp(prefix="halo-r5-stdio-"))
    trace = tmp / "trace.txt"
    saved = {k: closing._STATE[k] for k in ("closed", "spawned")}
    saved_trace = os.environ.get(closing.TRACE)
    try:
        os.environ[closing.TRACE] = str(trace)
        closing._STATE["closed"] = True
        refused = None
        try:
            asyncio.run(stdio.connect(command="example-server", args=["--serve"], env={}, cwd=None,
                                      errlog=None, connect_timeout=5.0))
        except closing.ClosingRefused as e:
            refused = e
        ctx.check(f"the start is refused, got {refused!r}", refused is not None)
        lines = [ln for ln in (trace.read_text(encoding="utf-8").splitlines() if trace.exists() else [])
                 if "refused" in ln]
        ctx.check(f"one trace line names the program, got {lines}",
                  len(lines) == 1 and "example-server --serve" in lines[0] and "a program" not in lines[0])
    finally:
        closing._STATE.update(saved)
        if saved_trace is None:
            os.environ.pop(closing.TRACE, None)
        else:
            os.environ[closing.TRACE] = saved_trace
        shutil.rmtree(tmp, ignore_errors=True)


@test
def test_l_every_spawn_of_the_closing_procedure_names_its_stdin(ctx: Ctx):
    """3.6.0.18 L (batch 2, entry 5c): closing.py's own tools (the `ps` looks, taskkill, the reaper, the WMI start)
    bypass subprocess_safe's rule for the terminal's input, so each names its stdin (a caller's spawn passed through
    with **kwargs names its own)."""
    import ast
    tree = ast.parse((REPO / "halo_harness" / "closing.py").read_text(encoding="utf-8"))
    bare = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ("run", "Popen")
                and isinstance(node.func.value, ast.Name) and node.func.value.id in ("sp", "_sp", "subprocess")):
            if not any(k.arg in ("stdin", None) for k in node.keywords):
                bare.append(node.lineno)
    ctx.check(f"no spawn of closing.py leaves its stdin unnamed, got lines {bare}", not bare)


# 3.6.0.18 L (batch 2, entry 2): Halo's own short check (a stand-in for `claude auth status`, longer than the join's
# bound) and a tool command's leftover both still run at close.
_OWN_CHECK = r"""
import contextlib, json, sys, threading, time
from halo_harness import closing, subprocess_safe
closing.install(sweep_at_start=False)
from halo_harness.bg_run import process_start_time
own_check = getattr(closing, "own_check", contextlib.nullcontext)
LONG = [sys.executable, "-c", "import time; time.sleep(120)"]

def check():
    try:
        with own_check():
            subprocess_safe.run(LONG, capture_output=True, stdin=subprocess_safe.DEVNULL, timeout=100)
    except Exception:
        pass
threading.Thread(target=check, daemon=True).start()
tool = subprocess_safe.Popen(LONG, stdin=subprocess_safe.DEVNULL, stdout=subprocess_safe.DEVNULL,
                             stderr=subprocess_safe.DEVNULL)

def found():
    # exactly the two stand-ins: the tool's command by its pid, the check by its mark. (Never "every pid with the
    # marker": on macOS the scan's own `ps` inherits the marker and lists itself, gone a moment later.)
    own = set()
    pids = closing.marker_pids(closing.marker(), own=own)
    return ([tool.pid] if tool.pid in pids else []) + sorted(p for p in own if p != tool.pid)
end = time.monotonic() + 60
while len(found()) < 2 and time.monotonic() < end:
    time.sleep(0.05)
kids = {p: process_start_time(p) for p in found()}
lines = closing.close(say=lambda _l: None)
print(json.dumps({"tool": tool.pid, "kids": kids, "lines": lines}), flush=True)
"""


@test
def test_l_halos_own_check_ended_at_close_is_never_named_a_tool_commands_leftover(ctx: Ctx):
    """3.6.0.18 L (batch 2, entry 2): a spawn inside `closing.own_check()` carries its mark; on Linux and macOS the
    marker scan at close still ends it but its line leaves it out, while a tool command's leftover beside it keeps its
    line word for word (before: "halo: ended python3 (pid N), left running by a tool command" for Halo's own check)."""
    from halo_harness import closing
    if not WIN:  # Windows: no marker scan and no line (the Job ends both)
        _own_check_at_close(ctx)
    own_check = getattr(closing, "own_check", None)
    ctx.check("closing has own_check()", callable(own_check))
    with own_check():
        inside = closing.before_spawn({"env": {"PATH": os.environ.get("PATH", "")}})
    outside = closing.before_spawn({"env": {"PATH": os.environ.get("PATH", "")}})
    ctx.check(f"a spawn inside carries the own-check mark, outside not, got {inside} {outside}",
              (inside["env"].get(closing.OWN_CHECK) == "1") and closing.OWN_CHECK not in outside["env"])


def _own_check_at_close(ctx: Ctx) -> None:
    from halo_harness import closing
    tmp = Path(tempfile.mkdtemp(prefix="halo-l-own-"))
    home = tmp / "home"
    home.mkdir()
    row: dict = {}
    try:
        r = subprocess.run([sys.executable, "-c", _OWN_CHECK], env=_env(home), cwd=str(tmp), capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=120, stdin=subprocess.DEVNULL)
        try:
            row = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            row = {}
        kids = {int(p): s for p, s in (row.get("kids") or {}).items()}
        ctx.check(f"both stand-ins ran at close, got {row} {r.stderr[-300:]!r}", len(kids) == 2)
        ended = [line for line in row.get("lines") or [] if line.startswith("halo: ended")]
        tool = row.get("tool")
        ctx.check(f"one line, naming only the tool command's leftover, got {ended}",
                  len(ended) == 1 and ended[0].count("(pid ") == 1 and f"(pid {tool}), left running by a tool command; "
                  "to keep one past Halo, the command starts it with HALO_OWNER=kept-<name> (docs/PROCESSES.md)" in ended[0])
        ctx.check(f"both are ended, got {kids}", not any(_same(p, s) for p, s in kids.items()))
    finally:
        for p, s in {int(p): s for p, s in (row.get("kids") or {}).items()}.items():
            _end_tree_we_started(p, s)
        shutil.rmtree(tmp, ignore_errors=True)


@test
def test_the_macos_marker_scan_leaves_its_own_ps_out_and_reads_odd_bytes(ctx: Ctx):
    """3.6.0.19: on macOS the scan's `ps` inherits the marker and listed itself, a pid that is gone a moment later; it
    is started with Popen and its own pid is left out. Its output is read with odd bytes replaced (before, one byte
    that is no UTF-8 in any process's command raised and the scan answered {}), and a `ps` that hangs is ended."""
    from unittest import mock

    from halo_harness import closing
    started: list = []
    killed: list = []

    class _Ps:
        pid = 4242
        hang = False

        def __init__(self, argv, **kw):
            started.append((list(argv), kw))
            self.calls = 0

        def communicate(self, timeout=None):
            self.calls += 1
            if self.hang and self.calls == 1:
                raise subprocess.TimeoutExpired("ps", timeout)
            return ("4242 /bin/ps -E -ww -A -o pid=,command= PATH=/bin HALO_OWNER=m1 LC_ALL=C\n"
                    "5000 sleep 30 PATH=/bin HALO_OWNER=m1 HALO_OWN_CHECK=1\n"
                    "5001 tool � HALO_OWNER=m1 X=1\n"
                    "5002 other HALO_OWNER=m2\n", None)

        def kill(self):
            killed.append(self.pid)

    real_isdir = os.path.isdir

    def scan() -> "tuple[dict, set]":
        own: set = set()
        with mock.patch.object(sys, "platform", "darwin"), \
                mock.patch.object(os.path, "isdir", lambda p: False if str(p) == "/proc" else real_isdir(p)), \
                mock.patch.object(subprocess, "Popen", _Ps):
            return closing.marker_pids("m1", own=own), own

    got, own = scan()
    ctx.check(f"the scan's own ps (pid 4242) is left out, the two marked programs are listed, got {got}",
              got == {5000: "m1", 5001: "m1"})
    ctx.check(f"Halo's own check is named as one, got {own}", own == {5000})
    kw = started[0][1] if started else {}
    ctx.check(f"ps is read with odd bytes replaced and reads no keyboard, got {kw.get('errors')!r} {kw.get('stdin')!r}",
              kw.get("errors") == "replace" and kw.get("stdin") == subprocess.DEVNULL)
    _Ps.hang = True
    got, own = scan()
    ctx.check(f"a ps that hangs is ended and the scan answers nothing, got {got} {killed}", got == {} and killed == [4242])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
