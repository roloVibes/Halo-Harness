"""halo_harness.ps_cli -- `halo ps` and `halo stop`: every live process of Halo on this machine, and the way to end
them (Halo 3.6.0.0 R10, closing.py; docs/PROCESSES.md).

    halo ps [--json]                       the ledger of this home (children.json, the model servers' registry, the
                                           Studio of studio.json) and the processes a scan finds with Halo's
                                           HALO_OWNER marker that the ledger lost: kind, pid, age, owner (alive /
                                           gone / none), kept on purpose or not
    halo stop <pid>|<kind> ... [--json]    stop those (a kind: studio, bg, schedule, supervisor, host, llama, mlx, stray)
    halo stop --orphans                    stop what has no living owner and was not asked to stay (the sweep a launch
                                           runs at start)
    halo stop --all                        stop every one listed for this home, kept ones too

Never this process, never a pid Halo did not start: a ledger entry is checked by pid and start time, a stray by its
marker and start time, before every signal. The scan reads /proc on Linux and `ps -E` on macOS; Windows lists no
strays (another process's environment is not readable there; Halo's Job object ends its children instead). A stray
is only this home's when its environment names this home.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Optional


def _age(since) -> str:
    if not isinstance(since, (int, float)):
        return "?"
    s = max(0, int(time.time() - since))
    return f"{s}s" if s < 120 else f"{s // 60}m" if s < 7200 else f"{s // 3600}h"


def _owner_word(entry: dict) -> str:
    from halo_harness import children as C
    if entry.get("owner_pid") is None:
        return "none"
    return "alive" if C.owner_alive(entry) else "gone"


def _environ(pid: int) -> str:
    try:
        with open(f"/proc/{pid}/environ", "rb") as fh:
            return fh.read().decode("utf-8", "replace")
    except OSError:
        return ""


def _state_of(env: dict) -> str:
    """The Halo home a process's environment points at (the same rule as config.paths.bridge_home)."""
    if env.get("BRIDGE_STATE_DIR"):
        return env["BRIDGE_STATE_DIR"]
    base = env.get("BRIDGE_TEST_HOME") or env.get("HOME") or env.get("USERPROFILE") or ""
    return os.path.join(base, ".halo") if base else ""


def _of_home(pid: int, home: str) -> bool:
    raw = _environ(pid)
    if raw:
        env = dict(item.split("=", 1) for item in raw.split(chr(0)) if "=" in item)
    elif sys.platform == "darwin":  # `ps -E` shows the environment beside the command
        try:
            import subprocess as _sp
            r = _sp.run(["/bin/ps", "-E", "-ww", "-o", "command=", "-p", str(pid)], capture_output=True, text=True,
                        timeout=5)
        except Exception:
            return False
        env = dict(tok.split("=", 1) for tok in (r.stdout or "").split() if "=" in tok and tok[0].isupper())
    else:
        return False
    mine = _state_of(env)
    norm = lambda p: os.path.normcase(os.path.abspath(p))  # noqa: E731
    return bool(mine) and norm(mine) == norm(home)


def rows(state_dir=None) -> list:
    """Every live process of Halo for this home: dicts {kind, pid, start_time, age, owner, kept, source, cmd}."""
    from halo_harness import children as C
    from halo_harness import closing
    from halo_harness.children_stop import studio_entry
    home = C._state(state_dir)
    out: list = []
    seen: set = set()
    entries = closing._entries(state_dir)
    st = studio_entry(state_dir)
    if st and all(e.get("pid") != st["pid"] for e in entries):
        info = {}
        try:
            from halo_harness.studio.launch import read_info
            info = read_info(home) or {}
        except Exception:
            pass
        st = dict(st, owner_pid=info.get("owner_pid"), owner_start=info.get("owner_start"))
        entries.append(st)
    for e in entries:
        if e.get("pid") == os.getpid() or not C.alive(e):
            continue
        seen.add(e["pid"])
        out.append({"kind": e.get("what") or "halo", "pid": e["pid"], "start_time": e.get("start_time"),
                    "age": _age(e.get("since")), "owner": _owner_word(e), "owner_pid": e.get("owner_pid"),
                    "kept": closing.kept(e), "source": e.get("source") or "children.json",
                    "cmd": " ".join(e.get("cmd") or [])[:120]})
    for pid, mark in sorted(closing.marker_pids().items()):
        if pid in seen or pid == os.getpid() or not _of_home(pid, str(home)):
            continue
        alive = closing.marker_owner_alive(mark)
        out.append({"kind": "stray", "pid": pid, "start_time": closing._start(pid), "age": "?",
                    "owner": "kept" if alive is None else ("alive" if alive else "gone"), "owner_pid": None,
                    "kept": mark.startswith(closing.KEPT_PREFIX), "source": "marker", "marker": mark, "cmd": ""})
    return out


def _print(table: list) -> None:
    if not table:
        print("no process of Halo is running for this home")
        return
    print(f"{'KIND':<11}{'PID':>8}  {'AGE':>5}  {'OWNER':<6} KEPT  COMMAND")
    for r in table:
        print(f"{r['kind']:<11}{r['pid']:>8}  {r['age']:>5}  {r['owner']:<6} {'yes ' if r['kept'] else 'no  '}  {r['cmd']}")


def cmd_ps(argv: list) -> int:
    p = argparse.ArgumentParser(prog="halo ps", description="Every live process of Halo for this home: the ledger, "
                                "and any stray a scan finds by Halo's HALO_OWNER marker.")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    table = rows()
    if a.json:
        print(json.dumps({"processes": table}, indent=2))
    else:
        _print(table)
    return 0


def _stop_rows(targets: list, state_dir=None) -> list:
    from halo_harness import children as C
    from halo_harness import closing
    ledger = [t for t in targets if t["source"] != "marker"]
    strays = [t for t in targets if t["source"] == "marker"]
    entries = [{"pid": t["pid"], "start_time": t["start_time"], "what": t["kind"], "since": 0,
                "source": t["source"] if t["source"] == "local-servers" else None,
                "model": None} for t in ledger]
    if any(t["source"] == "local-servers" for t in ledger):
        by_pid = {e["pid"]: e for e in C.local_servers(state_dir)}
        entries = [dict(e, **{k: by_pid[e["pid"]].get(k) for k in ("model", "source")}) if e["pid"] in by_pid else e
                   for e in entries]
    gone = {e["pid"] for e in closing.stop_entries(entries, state_dir=state_dir)}
    for t in strays:  # its marker and start time again, then the signal
        if C.same_process(t["pid"], t["start_time"]):
            closing._signal_tree(t["pid"], hard=False)
    closing._wait([{"pid": t["pid"], "start_time": t["start_time"]} for t in strays], closing.POLITE_S)
    for t in strays:
        if C.same_process(t["pid"], t["start_time"]):
            closing._signal_tree(t["pid"], hard=True)
    closing._wait([{"pid": t["pid"], "start_time": t["start_time"]} for t in strays], closing.HARD_S)
    gone |= {t["pid"] for t in strays if not C.same_process(t["pid"], t["start_time"])}
    return [dict(t, stopped=t["pid"] in gone) for t in targets]


def pick(table: list, words: list, *, orphans: bool = False, every: bool = False) -> "tuple[list, list]":
    """(targets, unknown words)."""
    if every:
        return list(table), []
    if orphans:
        return [r for r in table if not r["kept"] and (r["owner"] == "gone" or
                (r["kind"] == "studio" and r["owner"] == "none"))], []
    targets, unknown = [], []
    for w in words:
        hit = [r for r in table if (w.isdigit() and r["pid"] == int(w)) or r["kind"] == w]
        if not hit:
            unknown.append(w)
        targets += [r for r in hit if r not in targets]
    return targets, unknown


def cmd_stop(argv: list) -> int:
    p = argparse.ArgumentParser(prog="halo stop", description="Stop processes of Halo for this home (see halo ps).")
    p.add_argument("what", nargs="*", help="a pid or a kind (studio, bg, schedule, supervisor, host, llama, mlx, stray)")
    p.add_argument("--orphans", action="store_true", help="what has no living owner and was not asked to stay")
    p.add_argument("--all", action="store_true", help="every process of Halo listed for this home, kept ones too")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    if not (a.what or a.orphans or a.all):
        p.print_usage(sys.stderr)
        print("halo stop: name a pid or a kind, or --orphans / --all (halo ps lists them)", file=sys.stderr)
        return 2
    table = rows()
    targets, unknown = pick(table, a.what, orphans=a.orphans, every=a.all)
    done = _stop_rows(targets) if targets else []
    if a.json:
        print(json.dumps({"stopped": [d for d in done if d["stopped"]], "left": [d for d in done if not d["stopped"]],
                          "unknown": unknown}, indent=2))
    else:
        for d in done:
            print(f"{'stopped' if d['stopped'] else 'still running'}: {d['kind']} (pid {d['pid']})")
        for w in unknown:
            print(f"halo stop: nothing of Halo here is {w!r} (halo ps lists them)", file=sys.stderr)
        if not done and not unknown:
            print("nothing to stop")
    return 1 if unknown or any(not d["stopped"] for d in done) else 0


def doctor_line(state_dir=None) -> Optional[str]:
    """The doctor's row: None when every process of Halo here has a living owner (or was kept)."""
    try:
        table = rows(state_dir)
    except Exception:
        return None
    lost, _u = pick(table, [], orphans=True)
    if not lost:
        return None
    n = len(lost)
    return f"{n} process{'es' if n != 1 else ''} of Halo {'have' if n != 1 else 'has'} no living owner"
