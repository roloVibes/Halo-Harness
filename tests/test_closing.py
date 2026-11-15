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
    env = {k: v for k, v in os.environ.items() if not k.startswith(SCRUB)}
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
            if kind in ("tool", "ledger"):
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
def test_a_halo_run_from_a_sessions_shell_ends_only_its_own(ctx: Ctx):
    """A `halo` run from a session's own shell tool (or a sub-agent that runs halo) inherits the session's HALO_OWNER
    and HALO_OWNER_WATCH. Ended (normally, or hard), it ends what IT started and never the session's things; it runs
    no sweep; what it starts carries its own id, not the session's."""
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


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
