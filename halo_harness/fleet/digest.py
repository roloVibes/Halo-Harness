"""halo_harness.fleet.digest -- "while you were away", computed in code (Halo
3.0.5.0 "Fleet" round R4, D6): per harness, what happened since a moment:
sessions started and ended, the cost, the decisions answered and who
answered them, the files touched, the errors, the hand-offs. No model reads
or writes any of it.

    compute(home, since) -> {since, until, harnesses: [{id, name, local, started, ended, cost_usd, decisions,
                                                        files, errors, handoffs, missions, coach, quiet}], totals: {...}}
    parse_since("2h" | "45m" | "1d" | <unix seconds> | "2026-10-14T09:00") -> unix seconds

This harness is read from its transcripts on disk (`<home>/sessions/`: the
first and last line of each session, its usage lines, its Edit / Write
calls, its error lines and failed sub-agents, its take-over records); the
decisions answered from Studio, the hand-offs and every member harness come
from the hub's journal (fleet/journal.py), which Studio's fleet watcher
writes while it runs. 3.1.3.0 R1: this harness's `coach` rows, one per run
the post-run coach read since then (orchestra/coach_record.py's runs.json:
the run, its kind, its suggestions, how many are applied, the top card).
"""

from __future__ import annotations

import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from halo_harness.fleet import journal
from halo_harness.fleet.history import EDIT_TOOLS, read_nodes

MAX_SESSIONS = 300
CAP_BYTES = 3_000_000
LIST_CAP = 40


def parse_since(text, now: Optional[float] = None) -> float:
    now = time.time() if now is None else now
    s = str(text or "").strip()
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([smhd])", s)
    if m:
        return now - float(m.group(1)) * {"s": 1, "m": 60, "h": 3600, "d": 86400}[m.group(2)]
    if re.fullmatch(r"\d+(?:\.\d+)?", s):
        v = float(s)
        return v / 1000.0 if v > 1e11 else v  # milliseconds (a browser's Date.now()) or seconds
    try:
        return datetime.fromisoformat(s).timestamp()
    except ValueError:
        raise ValueError(f"since is 2h, 45m, 1d, unix seconds or an ISO time, got {text!r}") from None


def _rel(path: str, cwd) -> str:
    p, c = str(path).replace("\\", "/"), str(cwd or "").replace("\\", "/").rstrip("/")
    return p[len(c) + 1:] if c and p.lower().startswith(c.lower() + "/") else p


def _scan(nodes: list, since: float, out: dict, cwd, sid: str) -> None:
    for n in nodes:
        t = n.get("ts")
        if not isinstance(t, (int, float)) or t < since:
            continue
        kind = n.get("type")
        if kind == "usage" and isinstance(n.get("cost_usd"), (int, float)):
            out["cost_usd"] += float(n["cost_usd"])
        elif kind == "assistant":
            for b in n.get("content") or []:
                if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") in EDIT_TOOLS:
                    inp = b.get("input") if isinstance(b.get("input"), dict) else {}
                    f = inp.get("file_path") or inp.get("notebook_path")
                    if isinstance(f, str) and f:
                        out["_files"].setdefault(_rel(f, cwd), t)
        elif kind == "error":
            out["errors"].append({"session_id": sid, "text": str(n.get("message") or "")[:200], "ts": t})
        elif kind == "meta" and isinstance(n.get("fleet"), dict) and n["fleet"].get("handoff"):
            f = n["fleet"]
            out["handoffs"].append({"session_id": sid, "action": f.get("handoff"), "by": f.get("by"),
                                    "text": f.get("text"), "ts": t})


def local(home, since: float, live_ids=(), now: Optional[float] = None) -> dict:
    import json
    now = now or time.time()
    out = {"started": [], "ended": [], "cost_usd": 0.0, "_files": {}, "errors": [], "handoffs": [], "decisions": []}
    root = Path(home) / "sessions"
    logs = sorted((p for p in root.glob("*/*.jsonl") if p.stat().st_mtime >= since), key=lambda p: -p.stat().st_mtime) if root.is_dir() else []
    for p in logs[:MAX_SESSIONS]:
        nodes = read_nodes(p, CAP_BYTES)
        times = [n["ts"] for n in nodes if isinstance(n.get("ts"), (int, float))]
        if not times:
            continue
        cwd = next((n.get("cwd") for n in nodes if n.get("type") == "meta" and n.get("cwd")), None)
        title = next((n["title"] for n in reversed(nodes) if n.get("type") == "meta" and isinstance(n.get("title"), str) and n["title"]), "")
        row = {"session_id": p.stem, "title": title or Path(str(cwd or p.parent.name)).name, "ts": min(times)}
        if min(times) >= since:
            out["started"].append(row)
        if p.stem not in set(live_ids) and since <= max(times) <= now:
            out["ended"].append({**row, "ts": max(times)})
        _scan(nodes, since, out, cwd, p.stem)
        for child in (p.parent / p.stem).glob("subagents/**/agent-*.jsonl"):
            if child.stat().st_mtime >= since:
                _scan(read_nodes(child, CAP_BYTES), since, out, cwd, p.stem)
        for meta in (p.parent / p.stem).glob("subagents/**/agent-*.meta.json"):
            try:
                m = json.loads(meta.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(m, dict) and m.get("is_error") and float(m.get("finished") or 0) >= since:
                out["errors"].append({"session_id": p.stem, "text": f"{m.get('type') or 'a sub-agent'} failed",
                                      "ts": m.get("finished")})
    return out


def _bucket(hid, name, is_local) -> dict:
    return {"id": hid, "name": name, "local": is_local, "started": [], "ended": [], "cost_usd": 0.0, "_files": {},
            "errors": [], "handoffs": [], "decisions": [], "missions": [], "coach": []}


def _member_cost(rows: list, since: float) -> float:
    per: dict = {}
    for r in rows:
        if r.get("kind") == "cost" and isinstance(r.get("usd"), (int, float)):
            per.setdefault(r.get("session_id"), []).append((float(r["ts"]), float(r["usd"])))
    total = 0.0
    for points in per.values():
        before = [u for t, u in points if t < since]
        after = [u for t, u in points if t >= since]
        if after:
            total += max(0.0, after[-1] - (before[-1] if before else 0.0))
    return total


def compute(home, since: float, *, now: Optional[float] = None, local_id: Optional[str] = None,
            local_name: str = "this harness", live_ids=()) -> dict:
    now = now or time.time()
    rows = journal.read(home, 0.0)
    recent = [r for r in rows if float(r.get("ts") or 0) >= since]
    buckets: dict = {}
    if local_id is not None:
        b = buckets[local_id] = _bucket(local_id, local_name, True)
        for k, v in local(home, since, live_ids, now).items():
            b[k] = v
        from halo_harness.orchestra.coach_record import runs_since
        b["coach"] = runs_since(since, home)
    for r in recent:
        hid = r.get("harness")
        if not hid:
            continue
        b = buckets.setdefault(hid, _bucket(hid, r.get("harness_name") or str(hid)[:8], False))
        if r.get("harness_name") and not b["local"]:
            b["name"] = r["harness_name"]
        k = r.get("kind")
        if k == "decision":
            b["decisions"].append({k2: r.get(k2) for k2 in ("what", "answer", "by", "session_id", "row_kind", "ts")})
        elif k == "handoff":
            b["handoffs"].append({k2: r.get(k2) for k2 in ("action", "to", "issue", "path", "by", "agent", "ts")})
        elif str(k).startswith("mission_"):  # 3.0.6.0 R7: fleet missions (journaled by the hub)
            b["missions"].append({k2: r.get(k2) for k2 in ("kind", "mission", "part", "state", "on", "cost_usd", "reason", "by", "ts")})
        elif b["local"]:
            continue  # this harness's sessions, cost, files and errors come from its own transcripts
        elif k in ("session_start", "session_end"):
            # the watcher journals every session it finds when it starts: one row per session, by its own start
            st = r.get("started") if k == "session_start" and isinstance(r.get("started"), (int, float)) else r.get("ts")
            lst = b["started" if k == "session_start" else "ended"]
            if float(st or 0) >= since and all(x["session_id"] != r.get("session_id") for x in lst):
                lst.append({"session_id": r.get("session_id"), "title": r.get("title") or "", "ts": st})
        elif k == "file":
            b["_files"].setdefault(str(r.get("file")), r.get("ts"))
        elif k == "error":
            b["errors"].append({"session_id": r.get("session_id"), "text": r.get("text"), "ts": r.get("ts")})
    for hid, b in buckets.items():
        if not b["local"]:
            b["cost_usd"] = _member_cost([r for r in rows if r.get("harness") == hid], since)
        b["cost_usd"] = round(b["cost_usd"], 6)
        b["files"] = sorted(b.pop("_files"))[:200]
        for k in ("started", "ended", "errors", "handoffs", "decisions", "missions", "coach"):
            b[k] = b[k][-LIST_CAP:]
        b["quiet"] = not any(b[k] for k in ("started", "ended", "files", "errors", "handoffs", "decisions", "missions",
                                            "coach")) and not b["cost_usd"]
    hs = sorted(buckets.values(), key=lambda b: (not b["local"], str(b["name"]).lower()))
    totals = {k: sum(len(b[k]) for b in hs) for k in ("started", "ended", "files", "errors", "handoffs", "decisions", "missions")}
    totals["cost_usd"] = round(sum(b["cost_usd"] for b in hs), 6)
    return {"since": since, "until": now, "harnesses": hs, "totals": totals}


def text(d: dict) -> str:
    """The digest as plain lines (`halo fleet digest`)."""
    span = max(0, int(d["until"] - d["since"]))
    lines = [f"Since {time.strftime('%Y-%m-%d %H:%M', time.localtime(d['since']))} ({span // 3600}h {span % 3600 // 60}m): "
             f"${d['totals']['cost_usd']:.4f}, {d['totals']['started']} started, {d['totals']['ended']} ended, "
             f"{d['totals']['decisions']} decisions, {d['totals']['files']} files, {d['totals']['errors']} errors"]
    for b in d["harnesses"]:
        lines.append(f"\n{b['name']}{' (this harness)' if b['local'] else ''}: " + ("nothing happened" if b["quiet"] else
                     f"${b['cost_usd']:.4f}, {len(b['started'])} started, {len(b['ended'])} ended"))
        for s in b["started"][-5:]:
            lines.append(f"  started  {s.get('title') or s.get('session_id')}")
        for s in b["ended"][-5:]:
            lines.append(f"  ended    {s.get('title') or s.get('session_id')}")
        for x in b["decisions"][-5:]:
            lines.append(f"  decided  {x.get('what')}: {x.get('answer')} (by {x.get('by')})")
        for x in b["handoffs"][-5:]:
            lines.append(f"  hand-off {x.get('action')} {x.get('to') or ''} (by {x.get('by')})".rstrip())
        for x in [m for m in b["missions"] if m.get("kind") in ("mission_run", "mission_end")][-5:]:
            lines.append(f"  mission  {x.get('mission')} {x.get('state') or 'running'}" + (f": {x['reason']}" if x.get("reason") else ""))
        for x in b.get("coach", [])[-5:]:
            from halo_harness.orchestra.coach_record import summary_line
            lines.append(f"  coach    {x.get('kind')} {x.get('run')}: "
                         + summary_line(int(x.get("n") or 0), int(x.get("applied") or 0), str(x.get("top") or ""),
                                        str(x.get("probe") or ""))[7:])
        for x in b["errors"][-5:]:
            lines.append(f"  error    {x.get('text')}")
        if b["files"]:
            lines.append(f"  files    {', '.join(b['files'][:8])}{' ...' if len(b['files']) > 8 else ''}")
    return "\n".join(lines)
