"""halo_harness.live.timeline -- one session as a time axis (Halo 3.4.1.0 R1 "Time"): what the scrubber under
Agents -> Live draws and what a replay file carries, built from live/history.py's read of the transcripts on disk.
Nothing here calls a model.

    marks(hist) -> [{t, kind, agent_id, name, text, to?}]   kind: spawn | handoff | ask | fail | finish, in time order
    bands(hist) -> [{t0, t1, phase}]                        the session's phase over time (the 3.3.16.2 words)
    of(hist)    -> {marks, bands}

A mark is one fact a person scrubs to: a sub-agent started (its task, `to` its parent), it handed back (the first line
of its answer, `to` its parent), an agent asked the owner (a question's or plan review's words from its tool call; a
permission card from the turn's timeline record, its words from 3.4.1.0 on, else "a permission card" and how it was
answered), an agent failed, an agent or the session finished. A band is the busiest thing any agent did over a stretch, by the order waiting > tool > thinking > writing >
idle; each entry's phase lasts until that agent's next entry, at most PHASE_CAP seconds.
"""

from __future__ import annotations

from typing import Optional

from halo_harness.live.history import ASK_TOOLS

MARK_KINDS = ("spawn", "handoff", "ask", "fail", "finish")
PHASES = ("idle", "writing", "thinking", "tool", "waiting")  # the order the bands pick by (last wins)
PHASE_CAP = 120.0
TEXT_CAP = 160
MAX_BANDS = 600


def _line(text, cap: int = TEXT_CAP) -> str:
    s = " ".join(str(text or "").split())
    return s if len(s) <= cap else s[: cap - 3] + "..."


def _question(entry: dict) -> str:
    """The words of a question or plan review the agent put to the owner (its tool call's input), else ""."""
    inp = entry.get("input") if isinstance(entry.get("input"), dict) else {}
    if entry.get("name") == "ExitPlanMode":
        return "review the plan"
    qs = inp.get("questions")
    first = qs[0] if isinstance(qs, list) and qs and isinstance(qs[0], dict) else inp
    return _line(first.get("question") or entry.get("label") or "a question")


def _phase(entry: dict) -> Optional[str]:
    kind = entry.get("kind")
    if kind == "tool_call" and entry.get("name") in ASK_TOOLS:
        return "waiting"
    if kind == "thinking":
        return "thinking"
    if kind in ("tool_call", "spawn"):
        return "tool"
    if kind == "ask":
        return "waiting"
    if kind in ("text", "handback"):
        return "writing"
    return None


def _ts(entry: dict) -> Optional[float]:
    t = entry.get("ts")
    return float(t) if isinstance(t, (int, float)) and not isinstance(t, bool) else None


def marks(hist: dict) -> list:
    agents = hist.get("agents") or []
    names = {str(a.get("agent_id")): str(a.get("name") or a.get("agent_id")) for a in agents}
    entries = hist.get("entries") or {}
    out: list = []
    for a in agents:
        aid, parent = str(a.get("agent_id")), a.get("parent")
        name = names.get(aid, aid)
        if parent and isinstance(a.get("since"), (int, float)):
            out.append({"t": float(a["since"]), "kind": "spawn", "agent_id": aid, "name": name, "to": str(parent),
                        "text": _line(a.get("task"))})
        for e in entries.get(aid) or []:
            t = _ts(e)
            if t is None:
                continue
            if e.get("kind") == "ask":
                out.append({"t": t, "kind": "ask", "agent_id": aid, "name": name,
                            "text": _line(e.get("what") or e.get("name") or "asks you")})
            elif e.get("kind") == "tool_call" and e.get("name") in ASK_TOOLS:
                out.append({"t": t, "kind": "ask", "agent_id": aid, "name": name, "text": _question(e)})
            elif e.get("kind") == "handback" and parent:
                out.append({"t": t, "kind": "handoff", "agent_id": aid, "name": name, "to": str(parent),
                            "text": _line(e.get("text"))})
        for k in (k for k in hist.get("asks") or [] if str(k.get("agent_id")) == aid):
            said = f"answered {k.get('decision') or 'not'} after {max(0.0, k['t1'] - k['t0']):.0f} s"
            out.append({"t": float(k["t0"]), "kind": "ask", "agent_id": aid, "name": name,
                        "text": _line(f"{k['what']} ({said})" if k.get("what") else f"a permission card ({said})")})
        ended = a.get("ended")
        if isinstance(ended, (int, float)) and a.get("state") in ("done", "failed"):
            kind = "fail" if a.get("state") == "failed" else "finish"
            out.append({"t": float(ended), "kind": kind, "agent_id": aid, "name": name,
                        "text": f"{name} {'failed' if kind == 'fail' else 'finished'}"})
    return sorted(out, key=lambda m: (m["t"], MARK_KINDS.index(m["kind"]), m["agent_id"]))


def _segments(hist: dict) -> list:
    """(t0, t1, phase) per entry of every agent: until that agent's next entry or its end, capped."""
    ends = {str(a.get("agent_id")): a.get("ended") for a in hist.get("agents") or []}
    out = []
    for aid, ents in (hist.get("entries") or {}).items():
        timed = [(t, e) for t, e in ((_ts(e), e) for e in ents or []) if t is not None]
        timed.sort(key=lambda x: x[0])
        for i, (t, e) in enumerate(timed):
            phase = _phase(e)
            if not phase:
                continue
            nxt = timed[i + 1][0] if i + 1 < len(timed) else ends.get(aid)
            t1 = min(float(nxt) if isinstance(nxt, (int, float)) else t + 1.0, t + PHASE_CAP)
            out.append((t, max(t1, t + 0.5), phase))
    out += [(float(k["t0"]), max(float(k["t1"]), float(k["t0"]) + 0.5), "waiting") for k in hist.get("asks") or []]
    return out


def bands(hist: dict) -> list:
    segs = _segments(hist)
    t0, t1 = hist.get("started"), hist.get("ended")
    if not segs or not isinstance(t0, (int, float)) or not isinstance(t1, (int, float)):
        return []
    points = sorted({float(t0), float(t1)} | {s[0] for s in segs} | {s[1] for s in segs})
    events: dict = {}
    for a, b, p in segs:
        events.setdefault(a, []).append((p, 1))
        events.setdefault(b, []).append((p, -1))
    live = {p: 0 for p in PHASES}
    out: list = []
    for i, x in enumerate(points[:-1]):
        for p, d in events.get(x, ()):
            live[p] += d
        if x < t0 or x >= t1:
            continue
        phase = next((p for p in reversed(PHASES) if live[p] > 0), "idle")
        y = min(points[i + 1], float(t1))
        if out and out[-1]["phase"] == phase and abs(out[-1]["t1"] - x) < 1e-6:
            out[-1]["t1"] = y
        elif y > x:
            out.append({"t0": x, "t1": y, "phase": phase})
    while len(out) > MAX_BANDS:  # a long session: fold the shortest band into its neighbour
        i = min(range(len(out)), key=lambda k: out[k]["t1"] - out[k]["t0"])
        j = i - 1 if i > 0 else i + 1
        lo, hi = min(i, j), max(i, j)
        keep = out[lo] if PHASES.index(out[lo]["phase"]) >= PHASES.index(out[hi]["phase"]) else out[hi]
        out[lo:hi + 1] = [{"t0": out[lo]["t0"], "t1": out[hi]["t1"], "phase": keep["phase"]}]
    return out


def of(hist: dict) -> dict:
    return {"marks": marks(hist), "bands": bands(hist)}
