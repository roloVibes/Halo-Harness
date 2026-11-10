"""halo_harness.workflows.receipts -- every hand-off to a square, written where it is seen (Halo 3.3.16.0
R3, docs/WORKFLOWS-squares.md "Receipts").

    the transcript   one `receipt` node in the calling session's log (agent/log.py NODE_TYPES; never sent
                     to a model): which square, what went in (the need, the files' NAMES -- never their
                     content), what came back, the cost, the one line
    the Live tree    the square's node under the agent that called it: a session square's own agent row
                     gets `square: {name, engine}`; an orchestra square is a node of its own (`sq-<n>`)
    the cost         a session square's child rolls its usage into the parent as every sub-agent does; an
                     orchestra square's run cost is one `usage` node (agent_id `square:<ref>`), so the
                     session total counts it once
    an Orchestra run a lane's hand-off is one row of `<run>/squares.jsonl`; the run's report lists them
                     (`report_part`, `report_lines`)
"""

from __future__ import annotations

import itertools
import json
import os
import time
from pathlib import Path

_N = itertools.count(1)


def make(route, outcome, *, need: str = "", files=(), engine: str = "") -> dict:
    sq = route.square
    return {"type": "receipt", "kind": "workflow", "square": sq.ref if sq is not None else "", "engine": engine,
            "role": getattr(route, "role", "") or "",  # 3.3.16.2: the lineup's role took it (lineup_roles.py)
            "need": need or ",".join(route.gaps), "gaps": list(route.gaps), "files": [Path(str(f)).name for f in files or ()],
            "why": route.why, "status": "not-started" if route.refused else outcome.status,
            "back": ",".join(sq.contract.gives) if sq is not None and not route.refused else "",
            "gives_miss": "" if route.refused else outcome.gives_miss, "stop": "" if route.refused else outcome.stop,
            "cost_usd": 0.0 if route.refused else round(float(outcome.cost_usd or 0.0), 6),
            "run": "" if route.refused else outcome.run_id, "model": "" if route.refused else outcome.model}


def line(rec: dict) -> str:
    """The receipt's one line: `square media · in pdf (a.pdf) · back text · $0.0123 -- <why>`."""
    if rec.get("status") == "not-started":
        return f"square {rec.get('square') or '-'} did not start -- {rec.get('why')}"
    files = f" ({', '.join(rec['files'])})" if rec.get("files") else ""
    tail = "; ".join(x for x in (rec.get("stop") and f"stopped: {rec['stop']}", rec.get("gives_miss")) if x)
    who = f"role {rec['role']}" if rec.get("role") else f"square {rec['square']}"
    return (f"{who} · in {rec.get('need') or 'the task'}{files} · back {rec.get('back') or '-'} · "
            f"${float(rec.get('cost_usd') or 0):.4f} -- {rec.get('why')}" + (f" ({tail})" if tail else ""))


def write(session, rec: dict) -> None:
    log = getattr(session, "log", None)
    if log is not None and hasattr(log, "_append"):
        try:
            log._append(dict(rec, line=line(rec)))
        except Exception:
            pass
    run = os.environ.get("HALO_ORCHESTRA_RUN")
    if run and Path(run).is_dir():
        try:
            with open(Path(run) / "squares.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": round(time.time(), 3), **{k: rec.get(k) for k in ("square", "need", "status", "cost_usd")}}) + "\n")
        except OSError:
            pass


def mark_child(session, child, ref: str, engine: str) -> None:
    """A session square's own agent: its row says it is the square (the Live tree draws it so)."""
    try:
        from halo_harness.agent.agent_registry import tree_for
        aid = getattr(child, "agent_id", None)
        if aid:
            tree_for(session).update(aid, square={"name": ref, "engine": engine})
    except Exception:
        pass


def node(session, ref: str, engine: str, *, state: str, cost_usd: float = 0.0, key: str = "") -> str:
    """An orchestra square's node under the agent that called it; returns its key (pass it back to update)."""
    try:
        from halo_harness.agent.agent_registry import agent_key, tree_for
        tree = tree_for(session)
        if not key:
            key = f"sq-{next(_N)}"
            tree.add(key, parent=agent_key(session), name=ref, kind="square", state=state, task=f"square {ref}",
                     square={"name": ref, "engine": engine}, since=time.time())
        else:
            tree.update(key, state=state, cost_usd=round(float(cost_usd or 0.0), 6))
    except Exception:
        pass
    return key


def add_cost(session, ref: str, cost_usd: float) -> None:
    """An orchestra square's cost, once, in the session's usage (a session square's child already rolls up)."""
    log = getattr(session, "log", None)
    if log is None or not cost_usd:
        return
    try:
        log.append_usage({}, round(float(cost_usd), 6), agent_id=f"square:{ref}")
    except Exception:
        pass


def report_part(run_dir) -> dict:
    """`{"squares": [{square, need, status, cost_usd}, ...]}` in the order the run used them; {} for none."""
    rows = []
    try:
        for raw in (Path(run_dir) / "squares.jsonl").read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(raw))
            except ValueError:
                continue
    except OSError:
        return {}
    return {"squares": rows} if rows else {}


def report_lines(report: dict) -> "list[str]":
    rows = report.get("squares") or []
    if not rows:
        return []
    return ["  squares: " + " -> ".join(f"{r.get('square')} ({r.get('status')}, ${float(r.get('cost_usd') or 0):.4f})"
                                         for r in rows)]
