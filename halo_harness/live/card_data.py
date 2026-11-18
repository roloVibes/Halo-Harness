"""halo_harness.live.card_data -- the report card's data: a session's or a goal run's record read for the card (Halo
3.6.0.3 moved it here, with no change of behaviour, from the modules of the old playback, which then left Halo with it:
the payload and build, resolve and lanes, the cells and their words). Beside it: live/card_run.py (a
goal run's record), live/card_facts.py (the record's own figures), live/card_timeline.py (the marks and the bands).

    build(state_dir, sid, lineup=None, cwd=None) -> payload    a session's record as one payload; the payload's
                                                               "format" value (FORMAT) stays as it is (Z5)
    resolve(state_dir, ref, cwd) -> payload    ref: "session:<id>" | "run:<id>" | a bare id (a session, then a goal run)
    lanes(p, window=None) -> [lane]            each agent's block and phase segments
    cells(fig) -> {key: {value, text}}         one run's cells (the report card's nine)

3.6.0.3 B (Z13): a saved file of the old playback is no longer read here (live/report_card.resolve refuses one).
"""

from __future__ import annotations

import time
from typing import Optional


FORMAT = "halo-replay"
VERSION = 1
AGENT_KEYS = ("agent_id", "parent", "name", "role", "bio", "lineup", "model", "state", "since", "ended", "cost_usd", "task")


class ReplayError(ValueError):
    """A record this Halo cannot read (no such session or run, or the redactor failed); the message says which."""


class CompareError(ValueError):
    """A ref that names no run this machine can read; the message says which."""


PHASE = {"typing": "writing", "tool": "tool", "waiting": "waiting"}


def money(v: Optional[float]) -> str:
    if v is None:
        return "unknown"
    return f"${v:.2f}" if v >= 1 else f"${v:.4f}"  # Studio's cost() (orchestra/format.ts)


def secs(v: Optional[float]) -> str:
    if v is None:
        return "unknown"
    s = int(round(v))
    return f"{s // 3600} h {s % 3600 // 60:02d} min" if s >= 3600 else f"{s // 60} min {s % 60:02d} s" if s >= 60 else f"{s} s"


def kilo(n: int) -> str:
    return f"{n / 1_000_000:.1f}M" if n >= 1_000_000 else f"{n / 1000:.1f}k" if n >= 1000 else str(n)


def bare(ref: str) -> str:
    return str(ref).split(":", 1)[-1].split("/")[-1] or str(ref)


def _pct(x: Optional[float]) -> str:
    return "?" if x is None else f"{round(x * 100)} %"


def cells(f: dict) -> dict:
    """{key: {value, text, unknown?}} for one run's figures (live/card_facts.figures)."""
    cost, known = f.get("cost_usd"), bool(f.get("cost_known"))
    if cost is None or (not known and not cost):
        cost_text = "unknown" + (f" (no price for {', '.join(bare(m) for m in f.get('cost_unknown') or [])})" if f.get("cost_unknown") else "")
    else:
        cost_text = money(cost) + ("+" if not known else "")
    tok = f.get("tokens")
    tok_text = (f"{kilo(tok['in'] + tok['out'])} ({kilo(tok['in'])} in, {kilo(tok['out'])} out)" if tok
                else "not counted for part of a run" if f.get("window") else "unknown")
    models = f.get("models") or []
    m_text = "; ".join(f"{bare(m['model'])}: {_pct(m.get('cost_share'))} of cost, {_pct(m.get('time_share'))} of time" for m in models) or "none recorded"
    retries = f.get("retries")
    return {"ended": {"value": f.get("ok"), "text": str(f.get("how") or "unknown")},
            "wall": {"value": f.get("wall_s"), "text": secs(f.get("wall_s"))},
            "cost": {"value": cost if known else None, "text": cost_text, **({"unknown": True} if not known else {})},
            "tokens": {"value": tok["in"] + tok["out"] if tok else None, "text": tok_text, **({} if tok else {"unknown": True})},
            "models": {"value": [m["model"] for m in models], "text": m_text},
            "agents": {"value": f.get("agents"), "text": str(f.get("agents") or 0)},
            "asks": {"value": f.get("asks"), "text": str(f.get("asks") or 0)},
            "failures": {"value": f.get("failures"), "text": str(f.get("failures") or 0)},
            "retries": {"value": retries, "text": "unknown" if retries is None else str(retries), **({"unknown": True} if retries is None else {})}}


def plan_of(_lineup: Optional[str] = None, cwd=None, state_dir=None) -> Optional[dict]:
    """None: 3.6.0.0 R5b, lineups and their blocks are gone; the map a session ran on rides on each of its agents' rows."""
    return None


def includes(p: dict) -> list:
    n_agents = len(p.get("agents") or [])
    kinds: dict = {}
    for m in p.get("marks") or []:
        kinds[m.get("kind")] = kinds.get(m.get("kind"), 0) + 1
    marks = ", ".join(f"{n} {k}" for k, n in kinds.items()) or "no marks"
    plan = p.get("plan") or {}
    return [f"{n_agents} agent{'s' if n_agents != 1 else ''}: names, roles, models, tasks (first line), states, costs",
            f"{len(p.get('states') or [])} state changes and the cost over time; marks: {marks}"
            + ("; the record's figures (cost, tokens, models, retries)" if p.get("facts") else "")
            + ("; the files it wrote (paths inside the project) and the last answer's first line" if "artefacts" in (p.get("facts") or {}) else ""),
            "a goal run's record: the lead and its lanes, each lane's state changes (not each step)" if p.get("kind") == "run"
            else f"the lineup's blocks: {plan.get('lineup')}" if plan else "no lineup blocks (the lineup did not load)",
            "not included: prompts, tool inputs and outputs, thoughts, the working directory; a path is written relative to"
            " the project or as ~/... under your home; your user or machine name only where you typed it (the title, the"
            " lineup's names) or in a path inside the project",
            "every text passed the export redactor (`halo session export`'s rules)"]


def build(state_dir, sid: str, *, lineup: Optional[str] = None, cwd=None, live_states: Optional[dict] = None) -> dict:
    """The record of session `sid` on this machine, as one payload. Raises ReplayError when there is no such session."""
    from halo_harness import __version__
    from halo_harness.live import card_facts, card_timeline, history
    from halo_harness.privacy_redact import redact
    path = history.find(state_dir, sid)
    if path is None:
        raise ReplayError(f"no transcript of session {sid!r} on this machine")
    hist = history.read(path, live_states=live_states)
    p = {"format": FORMAT, "version": VERSION, "kind": "session", "id": "", "session_id": hist["session_id"],
         "title": hist.get("title") or "", "saved": round(time.time(), 3), "halo": __version__,
         "started": hist.get("started"), "ended": hist.get("ended"), "cost_usd": hist.get("cost_usd"),
         "agents": [{k: a.get(k) for k in AGENT_KEYS} for a in hist.get("agents") or []],
         "states": hist.get("states") or [], "costs": hist.get("costs") or [], "agent_costs": hist.get("agent_costs") or [],
         **card_timeline.of(hist), "plan": plan_of(lineup, cwd=cwd, state_dir=state_dir), "facts": card_facts.session_facts(path)}
    p["id"] = f"{p['session_id']}-{time.strftime('%Y%m%d-%H%M%S', time.localtime(p['saved']))}"
    from halo_harness.privacy_scrub import project_root  # 3.4.1.2: the one redaction (privacy_redact.py)
    p = redact(p, root=project_root(hist.get("cwd") or cwd))
    if "_sanitize_error" in p:
        raise ReplayError("the redactor could not clean this session's timeline; nothing was written")
    p["includes"] = includes(p)
    return p


def resolve(state_dir, ref: str, cwd=None) -> dict:
    """The record `ref` names: a session of this machine, then a goal run of this repo (3.6.0.3 B, Z13: no saved file)."""
    from halo_harness.live import card_run, history
    kind, _, rid = ref.partition(":") if ref.split(":", 1)[0] in ("session", "run") else ("", "", ref)
    try:
        if kind in ("", "session") and history.find(state_dir, rid) is not None:
            return build(state_dir, rid, cwd=cwd)
        if kind in ("", "run"):
            run_dir = card_run.find(cwd or ".", rid)
            if run_dir is not None:
                return card_run.build_run(state_dir, run_dir)
    except ReplayError as e:
        raise CompareError(str(e)) from None
    raise CompareError(f"{ref!r} is not a session of this machine or a goal run of this repo")


def lanes(p: dict, window=None) -> list:
    """Each agent as a lane of phase segments (seconds since the run's or the window's start), its block first."""
    t0 = (window or (p.get("started"),))[0] or p.get("started") or 0.0
    t1 = window[1] if window else (p.get("ended") or t0)
    by: dict = {}
    for s in p.get("states") or []:
        by.setdefault(str(s.get("agent_id")), []).append(s)
    out = []
    for a in p.get("agents") or []:
        aid = str(a.get("agent_id"))
        a0, a1 = a.get("since") if isinstance(a.get("since"), (int, float)) else t0, a.get("ended") if isinstance(a.get("ended"), (int, float)) else t1
        if a1 < t0 or a0 > t1:
            continue
        pts = sorted(by.get(aid) or [], key=lambda s: s["t"])
        segs = []
        for i, s in enumerate(pts):
            phase = PHASE.get(str(s.get("activity") or ""))
            nxt = pts[i + 1]["t"] if i + 1 < len(pts) else a1
            lo, hi = max(t0, s["t"]), min(t1, nxt)
            if phase and hi > lo:
                segs.append({"t0": round(lo - t0, 2), "t1": round(hi - t0, 2), "phase": phase})
        out.append({"agent_id": aid, "name": a.get("name") or aid, "role": a.get("role") or "", "model": a.get("model") or "",
                    "block": a.get("lineup") or ("goal run" if p.get("kind") == "run" else "session"), "state": a.get("state") or "",
                    "from": round(max(a0, t0) - t0, 2), "to": round(min(a1, t1) - t0, 2), "segs": segs[:400]})
    return out
