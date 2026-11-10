"""scripts/prepush.py -- everything CI checks, on this box, before a push (Halo 3.3.16.0).

    python scripts/prepush.py                 # the whole gate
    python scripts/prepush.py --quick         # the static checks and the fast tier only (no Chrome, no TUI pilots)
    python scripts/prepush.py --jobs 6        # fewer parallel shards (default: half the cores, 2 to 12)
    python scripts/prepush.py --ui            # build Studio's UI even when no ui/ file differs from origin/master
    python scripts/prepush.py --status        # what the last run said, and whether it is this tree's

What it runs, in this order (a red static check stops the run; the suites all run so one pass lists every red):

  1. pyflakes: no undefined name in halo_harness/ or bridge.py (CI's gate).
  2. Studio's UI, when a file under halo_harness/studio/ui differs from origin/master or --ui is given:
     `npm run build`, then the committed static/dist must be what the build wrote.
  3. `halo audit privacy` with a scratch home.
  4. The fast tier of tests/run_all.py as N shards side by side (`--fast --shard i/N`, the flag CI's matrix uses),
     with test_bridge.py beside them. Every shard is run_all itself, so each module still gets its own fresh
     BRIDGE_TEST_HOME and the run still fails when a test touches the real ~/.halo.
  5. The full tier (`--tier full`: headless Chrome and the TUI pilots) as --chrome-jobs shards (default 4), each
     with its own temp directory and so its own Chrome lock (one Chrome per shard), with test_tui.py beside them;
     docs/harness/tui-snapshots is put back afterwards unless --keep-snapshots.
  6. A shard that went red beside the others is run once more alone. Green alone = "contended" (said in the
     summary, the gate still passes: look at it, a test that needs a quiet box is a test to fix); red alone = red.

Logs go to .prepush/<sha>/<step>.log and the verdict to .prepush/last.json (sha, dirty tree or not, each step).
The gate is green only for the exact tree it ran on: commit first, run, then push that sha.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / ".prepush"
UI = REPO / "halo_harness" / "studio" / "ui"
SNAPSHOTS = "docs/harness/tui-snapshots"


def git(*args: str) -> str:
    r = subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return (r.stdout or "").strip()


def tree_state() -> dict:
    dirty = [ln for ln in git("status", "--porcelain").splitlines() if ln.strip() and SNAPSHOTS not in ln]
    return {"sha": git("rev-parse", "HEAD"), "dirty": bool(dirty), "dirty_files": [ln[3:] for ln in dirty][:20]}


def suite_env() -> dict:
    env = {k: v for k, v in os.environ.items() if k not in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
    env.update(PYTHONPATH=str(REPO), BRIDGE_TEST_NO_BACKGROUND_NET="1", PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    return env


def own_temp(name: str) -> dict:
    """A suite environment with its own temp directory. tests/helpers/chrome_lock.py keeps the one-Chrome-at-a-time
    lock under <temp>/halo-tests, so a shard with its own temp has its own lock: one Chrome per shard, not per box."""
    env = suite_env()
    tmp = Path(tempfile.mkdtemp(prefix=f"prepush-{name}-"))
    env.update(TEMP=str(tmp), TMP=str(tmp), TMPDIR=str(tmp))
    return env


def start(name: str, cmd: list, logdir: Path, cwd: Path = REPO, env: "dict | None" = None) -> dict:
    log = logdir / f"{name}.log"
    fh = open(log, "w", encoding="utf-8", errors="replace")
    shell = os.name == "nt" and cmd[0] in ("npm", "npx")
    proc = subprocess.Popen(cmd, cwd=cwd, env=env or suite_env(), stdout=fh, stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL, shell=shell)
    return {"name": name, "cmd": cmd, "proc": proc, "fh": fh, "log": log, "t0": time.time()}


def wait(jobs: list, ok=lambda code, log: code == 0) -> list:
    done = []
    for j in jobs:
        code = j["proc"].wait()
        j["fh"].close()
        secs = round(time.time() - j["t0"])
        code = 0 if ok(code, j["log"]) else 1
        print(f"  [{'ok ' if code == 0 else 'RED'}] {j['name']:<16} {secs:>5}s  {j['log'].relative_to(REPO)}", flush=True)
        done.append({"name": j["name"], "ok": code == 0, "seconds": secs, "log": str(j["log"].relative_to(REPO)),
                     "cmd": j["cmd"]})
    return done


def run_step(name: str, cmd: list, logdir: Path, ok=None, **kw) -> dict:
    return wait([start(name, cmd, logdir, **kw)], **({"ok": ok} if ok else {}))[0]


def undefined_names(log: Path) -> list:
    """pyflakes exits 1 on any note; only an undefined name (or no pyflakes at all) is this gate's red, as in CI."""
    text = log.read_text(encoding="utf-8", errors="replace")
    return [ln for ln in text.splitlines() if "undefined name" in ln or "No module named pyflakes" in ln]


def red_lines(log: str, limit: int = 12) -> list:
    """The lines of a suite log that say what failed: the module header before a [FAIL], and the [FAIL] itself."""
    out, module = [], ""
    try:
        text = (REPO / log).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    for ln in text.splitlines():
        if ln.startswith("=== "):
            module = ln.strip("= ").strip()
        elif ln.lstrip().startswith("[FAIL]") or "IMPORT FAILED" in ln.upper():
            out.append(f"{module}: {ln.strip()}" if module else ln.strip())
    return out[:limit]


def ui_differs() -> bool:
    return bool(git("diff", "--name-only", "origin/master", "--", "halo_harness/studio/ui"))


def static_checks(args, logdir: Path) -> list:
    steps = []
    py = sys.executable
    flakes = run_step("pyflakes", [py, "-m", "pyflakes", "halo_harness", "bridge.py"], logdir,
                      ok=lambda code, log: not undefined_names(log))
    flakes["note"] = "; ".join(undefined_names(REPO / flakes["log"])[:5])
    steps.append(flakes)
    if args.ui or ui_differs():
        if not shutil.which("npm"):
            steps.append({"name": "studio-ui", "ok": False, "note": "npm is not on PATH (node 22, see ui/.nvmrc)"})
        else:
            if not (UI / "node_modules").is_dir():
                steps.append(run_step("studio-ui-ci", ["npm", "ci"], logdir, cwd=UI, env=dict(os.environ)))
            build = run_step("studio-ui", ["npm", "run", "build"], logdir, cwd=UI, env=dict(os.environ))
            stale = git("status", "--porcelain", "--", "halo_harness/studio/static/dist")
            if build["ok"] and stale:
                build["ok"], build["note"] = False, "static/dist is not what the build writes: commit the rebuilt dist"
            steps.append(build)
    home = tempfile.mkdtemp(prefix="prepush-audit-")
    env = suite_env()
    env.update(BRIDGE_TEST_HOME=home, HALO_HOME=home)
    steps.append(run_step("audit-privacy", [py, "-m", "halo_harness", "audit", "privacy"], logdir, env=env))
    shutil.rmtree(home, ignore_errors=True)
    return steps


def suites(args, logdir: Path) -> list:
    py, n = sys.executable, args.jobs
    print(f"fast tier: {n} shards side by side, test_bridge beside them", flush=True)
    jobs = [start(f"fast-{i}of{n}", [py, "tests/run_all.py", "--fast", "--shard", f"{i}/{n}"], logdir) for i in range(n)]
    jobs.append(start("test_bridge", [py, "test_bridge.py"], logdir))
    steps = wait(jobs)
    if not args.quick:
        print("full tier (Chrome, TUI pilots) as shards, each with its own Chrome lock; test_tui beside them", flush=True)
        k = max(1, min(args.chrome_jobs, n))
        jobs = [start(f"full-{i}of{k}", [py, "tests/run_all.py", "--tier", "full", "--shard", f"{i}/{k}"], logdir,
                      env=own_temp(f"full-{i}")) for i in range(k)]
        steps += wait(jobs + [start("test_tui", [py, "test_tui.py"], logdir)])
        if not args.keep_snapshots:
            git("checkout", "--", SNAPSHOTS)
    for s in [s for s in steps if not s["ok"]]:
        print(f"once more, alone: {s['name']}", flush=True)
        again = run_step(s["name"] + "-alone", s["cmd"], logdir, env=own_temp(s["name"] + "-alone"))
        s["first_log"], s["log"] = s["log"], again["log"]
        if again["ok"]:
            s["ok"], s["contended"] = True, True
        if s["name"] == "test_tui" and not args.keep_snapshots:
            git("checkout", "--", SNAPSHOTS)
    return steps


def status() -> int:
    try:
        last = json.loads((OUT / "last.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print("prepush: no run recorded (python scripts/prepush.py)")
        return 2
    now = tree_state()
    same = last.get("sha") == now["sha"] and not now["dirty"] and not last.get("dirty")
    print(f"prepush: {last.get('verdict')} for {str(last.get('sha'))[:8]}"
          f"{' (dirty tree)' if last.get('dirty') else ''}, {last.get('scope')}, {last.get('finished')}")
    print(f"prepush: this tree is {now['sha'][:8]}{' (dirty)' if now['dirty'] else ''}: "
          + ("the run covers it" if same else "the run does NOT cover it"))
    return 0 if same and last.get("verdict") == "green" and last.get("scope") == "whole gate" else 1


def main(argv: "list | None" = None) -> int:
    p = argparse.ArgumentParser(prog="prepush.py", description="Everything CI checks, on this box, before a push.")
    p.add_argument("--quick", action="store_true", help="static checks and the fast tier only")
    p.add_argument("--jobs", type=int, default=max(2, min(12, (os.cpu_count() or 4) // 2)))
    p.add_argument("--chrome-jobs", type=int, default=4, help="shards of the full tier, one Chrome each (default 4)")
    p.add_argument("--ui", action="store_true", help="build Studio's UI even when no ui/ file differs from origin/master")
    p.add_argument("--keep-snapshots", action="store_true", help="leave test_tui's re-rendered SVGs in the tree")
    p.add_argument("--status", action="store_true", help="print the last run's verdict and whether it is this tree's")
    args = p.parse_args(argv)
    if args.status:
        return status()
    state = tree_state()
    logdir = OUT / state["sha"][:12]
    shutil.rmtree(logdir, ignore_errors=True)
    logdir.mkdir(parents=True)
    t0 = time.time()
    print(f"prepush: {state['sha'][:8]}{' + uncommitted changes' if state['dirty'] else ''}, logs in "
          f"{logdir.relative_to(REPO)}", flush=True)
    steps = static_checks(args, logdir)
    if all(s["ok"] for s in steps):
        steps += suites(args, logdir)
    else:
        print("a static check is red: the suites were not run", flush=True)
    red = [s for s in steps if not s["ok"]]
    contended = [s for s in steps if s.get("contended")]
    record = {"sha": state["sha"], "dirty": state["dirty"], "dirty_files": state["dirty_files"],
              "scope": "quick" if args.quick else "whole gate", "verdict": "red" if red else "green",
              "seconds": round(time.time() - t0), "finished": time.strftime("%Y-%m-%d %H:%M:%S"),
              "steps": [{k: v for k, v in s.items() if k != "cmd"} for s in steps]}
    (OUT / "last.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    print("-" * 78)
    for s in contended:
        print(f"contended (red beside the others, green alone): {s['name']}  first log {s['first_log']}")
        for ln in red_lines(s["first_log"], 6):
            print(f"    {ln}")
    for s in red:
        print(f"RED {s['name']}: {s.get('note') or s.get('log', '')}")
        for ln in red_lines(s.get("log", "")):
            print(f"    {ln}")
    mins = record["seconds"] / 60
    if red:
        print(f"prepush: RED ({len(red)} step(s)) in {mins:.1f} min -- do not push {state['sha'][:8]}")
        return 1
    tail = " -- commit, then run again: a green is for the tree it ran on" if state["dirty"] else ""
    print(f"prepush: green ({record['scope']}) for {state['sha'][:8]} in {mins:.1f} min{tail}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
