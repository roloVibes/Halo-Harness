"""halo_harness.packs.policy_audit -- every verdict a pack's policies gave, read back (Halo 3.3.10.0 R2;
docs/EXTENSION_API.md "Policy hooks", docs/COMMANDS-packs.md `halo pack policy log`).

The session's gate writes one `policy` row per verdict into the pack's events log (`{policy, tool, verdict, reason,
rule, scope, ms, session, agent, at: before | after, winner, of?, error?, sha256?}`) and the runner a `policy_proc`
row when a policy's process starts or stops (`{policy, change, pid, by}`). This module reads them for `halo pack
policy log`, the counts and processes of `halo pack policy status` and the Pack Manager's row.

    rows(pack_id, since=0, state_dir=None) -> the pack's policy rows, oldest first ({ts, pack, ...the row})
    counts(rows) -> {"allow": 2, "deny": 1}
    procs(pack_id, state_dir=None) -> {policy id: "running (pid 4242)" | "not running"}
    line(row) -> "12:00:01 policy-fence  deny -- fence: outside the project  (Write, 3 ms, rule outside-project)"
    since_ts("1h" | "30m" | "2d" | "<epoch seconds>" | "<ISO time>") -> epoch seconds (ValueError when unreadable)
    log_lines(pack_id | None, since=0, cwd=None, state_dir=None) -> the lines `halo pack policy log` prints
    manager_block(pack, state_dir=None) -> {"armed", "mode", "last", "counts"} | None (the Pack Manager row)
    armed_ids(cwd=None, state_dir=None) -> ["policy-fence/fence"]: what a fleet mission records as it is made
"""

from __future__ import annotations

import re
import time
from datetime import datetime

UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def rows(pack_id: str, since: float = 0.0, *, state_dir=None) -> "list[dict]":
    from halo_harness.packs.events_log import since as read
    out = []
    for e in read(f"{pack_id}:policy", since, state_dir=state_dir):
        if isinstance(e.get("data"), dict):
            out.append({"ts": e.get("ts"), "pack": pack_id, **e["data"]})
    return out


def counts(rs) -> "dict[str, int]":
    out: dict = {}
    for r in rs or []:
        v = str(r.get("verdict") or "?")
        out[v] = out.get(v, 0) + 1
    return out


def procs(pack_id: str, *, state_dir=None) -> "dict[str, str]":
    """Each policy's process as the last `policy_proc` row says, checked against the process table."""
    from halo_harness.bg_run import pid_alive
    from halo_harness.packs.events_log import since as read
    last: dict = {}
    for e in read(f"{pack_id}:policy_proc", 0.0, state_dir=state_dir):
        d = e.get("data") if isinstance(e.get("data"), dict) else {}
        if d.get("policy"):
            last[str(d["policy"])] = d
    out = {}
    for pid_, d in last.items():
        pid = d.get("pid")
        alive = d.get("change") == "start" and isinstance(pid, int) and pid_alive(pid)
        out[pid_] = f"running (pid {pid})" if alive else "not running"
    return out


def line(r: dict) -> str:
    try:
        at = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(r.get("ts") or 0)))
    except (TypeError, ValueError, OverflowError):
        at = "?"
    word = "after: " if r.get("at") == "after" else ""
    who = f", agent {r['agent']}" if r.get("agent") else ""
    won = ", the winner" if r.get("winner") and r.get("of") else ""
    err = f", error: {r['error']}" if r.get("error") else ""
    sha = f", original {r['sha256']}" if r.get("sha256") else ""
    return (f"{at} {r.get('pack', '?')}  {word}{r.get('verdict', '?')} -- {r.get('policy', '?')}: {r.get('reason', '')}  "
            f"({r.get('tool', '?')}, {r.get('ms', 0)} ms, rule {r.get('rule') or '-'}{who}{won}{err}{sha})")


def since_ts(text) -> float:
    """`1h`, `30m`, `2d`, `45s` ago; epoch seconds; or an ISO time (local when it has no zone)."""
    s = str(text or "").strip()
    m = re.fullmatch(r"(\d+)\s*([smhd])", s)
    if m:
        return time.time() - int(m.group(1)) * UNITS[m.group(2)]
    try:
        return float(s)
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except ValueError:
        raise ValueError(f"--since takes 30m, 2h, 1d, epoch seconds or an ISO time, not {s!r}") from None


def _policy_packs(cwd, state_dir) -> list:
    from halo_harness.packs import manifest_policy as MP
    from halo_harness.packs.registry import snapshot
    return [p.id for p in snapshot(cwd=cwd, state_dir=state_dir).packs if MP.policies_of(p.manifest)]


def log_lines(pack_id=None, since: float = 0.0, *, cwd=None, state_dir=None) -> "list[str]":
    ids = [pack_id] if pack_id else _policy_packs(cwd, state_dir)
    rs = sorted((r for i in ids for r in rows(i, since, state_dir=state_dir)), key=lambda r: float(r.get("ts") or 0))
    if not rs:
        where = f"{pack_id}'s policies" if pack_id else "a pack's policy"
        return [f"No verdict of {where} is logged" + (" in that time." if since else " yet.")]
    return [line(r) for r in rs]


def armed_ids(*, cwd=None, state_dir=None) -> "list[str]":
    """`<pack>/<policy>` for each policy that answers now, read without touching a running process (a fleet
    mission records them: 3.3.10.0 R2; Federation R6 enforces them on the far side)."""
    from halo_harness.packs import mode_state as M
    from halo_harness.packs import state as S
    from halo_harness.packs.policy import declared
    from halo_harness.packs.registry import snapshot
    try:
        snap = snapshot(cwd=cwd, state_dir=state_dir)
        out = []
        for pack in snap.active:
            if "hooks" not in S.granted(pack.id, snap.state):
                continue
            rec = M.read(pack.id, state_dir)
            out += [f"{pack.id}/{p.id}" for p in declared(pack) if p.id in rec["armed"] and (not p.modes or rec["mode"] in p.modes)]
        return out
    except Exception:  # a pack that cannot be read never stops a mission
        return []


def manager_block(pack, *, state_dir=None) -> "dict | None":
    from halo_harness.packs import manifest_policy as MP
    from halo_harness.packs import mode_state as M
    if not MP.policies_of(pack.manifest):
        return None
    rec = M.read(pack.id, state_dir)
    rs = rows(pack.id, state_dir=state_dir)
    last = rs[-1] if rs else None
    text = ""
    if last:
        word = "after: " if last.get("at") == "after" else ""
        text = f"{word}{last.get('verdict')} -- {last.get('policy')}: {last.get('reason', '')} ({last.get('tool', '?')})"
    return {"armed": list(rec["armed"]), "mode": rec["mode"], "last": text, "last_ts": last.get("ts") if last else None,
            "counts": counts(rs)}
