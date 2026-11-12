"""halo_harness.live.report_card -- a finished run's report card (Halo 3.4.1.0 R3 "Time"; docs/REPLAY.md "The report
card"), rendered FROM THE RECORD: never hand-written, no model call. A run is anything with a replay -- a session of this
machine, a goal run of this repo, a saved `.halo-replay` file made anywhere (live/compare.resolve reads all three) -- so a
file opened on another machine gives the same card.

The figures are R2's, not a second set: live/replay_facts.figures and live/compare_text.cells (the nine cells Compare's
rows show), live/compare.lanes (each agent's block and phase segments). On top of them, from the replay's marks, bands,
states and facts: the story in order in about ten lines (who was asked what, what each handed back), where the time went
(by phase, by block), where the money went (by model, by block), what failed and what happened next, what waited on you
and for how long, which model did what, the files it wrote, and what this record cannot show, said in plain words.

    resolve(state_dir, ref, cwd) -> (payload, from_file)    ref: session:<id> | run:<id> | file:<id> | a path | a bare id
    card(p, ref="", from_file=False) -> {format, kind, id, ref, title, started, ended, halo, file, how, ok, cells, story,
                        story_more, time, money, failures, waits, models, artefacts, cannot}
    Markdown: live/report_card_text.markdown(card)
"""

from __future__ import annotations

import re
import time
from typing import Optional

from halo_harness.live.compare_text import bare, secs

FORMAT = "halo-report-card"
STORY_MAX = 10
PHASE_WORDS = {"waiting": "waiting on you", "tool": "running a tool", "thinking": "thinking", "writing": "writing", "idle": "idle"}


def _num(v) -> Optional[float]:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def clock(s: Optional[float]) -> str:
    if s is None:
        return "?:??"
    s = max(0, int(round(s)))
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def _who(a: Optional[dict], with_model: bool = True) -> str:
    if not a:
        return "an agent"
    name = str(a.get("name") or a.get("agent_id") or "an agent")
    return f"{name} ({bare(a['model'])})" if with_model and a.get("model") else name


_ANSWERED = re.compile(r"\(answered \w+ after (\d+(?:\.\d+)?) s\)")


def wait_secs(p: dict, m: dict) -> Optional[float]:
    """How long the agent waited from mark `m`, None when not recorded. 3.4.1.1 (62): a permission card's mark says it
    itself ("answered allow after 30 s", the turn's own record), so that figure is taken first -- the states around a
    headless session's card read 0 s, and an older session's 17 cards were left out of the total; else its waiting
    state there until its next state."""
    said = _ANSWERED.search(str(m.get("text") or ""))
    if said:
        return float(said.group(1))
    pts = sorted((s for s in p.get("states") or [] if str(s.get("agent_id")) == str(m.get("agent_id")) and _num(s.get("t")) is not None),
                 key=lambda s: s["t"])
    for i, s in enumerate(pts):
        if s.get("state") == "waiting" and abs(s["t"] - m["t"]) <= 1.0:
            nxt = next((x["t"] for x in pts[i + 1:] if x.get("state") != "waiting"), None)
            return round(nxt - s["t"], 1) if nxt is not None else None
    return None


def _say(p: dict, m: dict, names: dict, facts: dict, top: dict, how: str) -> str:
    a, parent, kind = names.get(str(m.get("agent_id"))), names.get(str(m.get("to") or "")), m.get("kind")
    if kind == "spawn":
        return f"{_who(parent, False)} asked {_who(a)}: {m.get('text') or 'a task (not recorded)'}"
    if kind == "handoff":
        return f"{_who(a, False)} handed back to {_who(parent, False)}: {m.get('text') or '(empty)'}"
    if kind == "ask":
        w = wait_secs(p, m)
        said = str(m.get("text") or "a question")
        return f"{_who(a, False)} asked you: {said}" + (f" (waited {secs(w)})" if w is not None and "answered" not in said else "")
    if kind == "fail":
        return f"{_who(a, False)} failed"
    if a is top and p.get("kind") == "run":
        return f"The run ended: {how}"
    if a is top:
        return f"{_who(a, False)} finished" + (f" and answered: {facts['answer']}" if facts.get("answer") else "")
    return f"{_who(a, False)} finished (no hand-back recorded)"


def _story(p: dict, names: dict, facts: dict, top: dict, how: str, t0: float) -> "tuple[list, int]":
    handed = {str(m.get("agent_id")) for m in p.get("marks") or [] if m.get("kind") == "handoff"}
    first = (f"You set the goal, for {_who(top)}: {p.get('title') or top.get('task') or '(not recorded)'}" if p.get("kind") == "run"
             else f"You asked {_who(top)}: {top.get('task') or p.get('title') or '(the first prompt is not recorded)'}")
    rows = [(t0, "start", 2, first)]
    for m in p.get("marks") or []:
        a = names.get(str(m.get("agent_id")))
        if _num(m.get("t")) is None or (m.get("kind") == "finish" and a is not top and str(m.get("agent_id")) in handed):
            continue
        rows.append((m["t"], m["kind"], 2 if m["kind"] in ("ask", "fail") or a is top else 1, _say(p, m, names, facts, top, how)))
    rows.sort(key=lambda r: r[0])
    pri = [i for i, r in enumerate(rows) if r[2] == 2]
    keep = set(range(len(rows))) if len(rows) <= STORY_MAX else set(pri[: STORY_MAX - 1] + pri[-1:])
    for i in range(len(rows)):  # the rest in time order, up to about ten lines
        if len(keep) >= STORY_MAX:
            break
        keep.add(i)
    kept = [rows[i] for i in sorted(keep)]
    return [{"t": round(t - t0, 1), "at": clock(t - t0), "kind": k, "text": text} for t, k, _w, text in kept], len(rows) - len(kept)


def _time(p: dict, lanes: list, wall: Optional[float]) -> dict:
    by: dict = {}
    for b in p.get("bands") or []:
        if _num(b.get("t0")) is not None and _num(b.get("t1")) is not None:
            by[b.get("phase")] = by.get(b.get("phase"), 0.0) + max(0.0, b["t1"] - b["t0"])
    phases = [{"phase": k, "words": PHASE_WORDS.get(str(k), str(k)), "secs": round(v, 1), "share": round(v / wall, 4) if wall else None}
              for k, v in sorted(by.items(), key=lambda kv: -kv[1]) if v > 0]
    blocks: dict = {}
    for ln in lanes:
        row = blocks.setdefault(ln["block"], {"block": ln["block"], "agents": 0, "secs": 0.0, "busy": 0.0})
        row["agents"] += 1
        row["secs"] += max(0.0, ln["to"] - ln["from"])
        row["busy"] += sum(max(0.0, s["t1"] - s["t0"]) for s in ln.get("segs") or [])
    return {"wall_s": wall, "phases": phases,
            "blocks": [{**b, "secs": round(b["secs"], 1), "busy": round(b["busy"], 1)} for b in sorted(blocks.values(), key=lambda b: -b["secs"])]}


def _money(p: dict, fig: dict, lanes: list) -> dict:
    unknown = set(fig.get("cost_unknown") or [])
    models = [{"model": m["model"], "cost_usd": m.get("cost_usd"), "share": m.get("cost_share"), "unknown": m["model"] in unknown}
              for m in fig.get("models") or [] if m.get("cost_usd") or m["model"] in unknown]
    models += [{"model": m, "cost_usd": None, "share": None, "unknown": True} for m in sorted(unknown) if m not in {x["model"] for x in models}]
    block_of = {ln["agent_id"]: ln["block"] for ln in lanes}
    blocks: dict = {}
    for a in p.get("agents") or []:
        b = block_of.get(str(a.get("agent_id")), "session")
        row = blocks.setdefault(b, {"block": b, "cost_usd": 0.0, "unknown": False})
        row["cost_usd"] = round(row["cost_usd"] + (_num(a.get("cost_usd")) or 0.0), 6)
        row["unknown"] = row["unknown"] or str(a.get("model") or "") in unknown
    return {"total": fig.get("cost_usd"), "known": bool(fig.get("cost_known")), "unknown": sorted(unknown), "models": models,
            "blocks": sorted(blocks.values(), key=lambda b: -b["cost_usd"])}


def _failures(p: dict, story_of, names: dict, t0: float) -> list:
    marks = [m for m in p.get("marks") or [] if _num(m.get("t")) is not None]
    out = []
    for i, m in enumerate(marks):
        if m.get("kind") != "fail":
            continue
        nxt = next((x for x in marks[i + 1:] if not (x.get("kind") in ("fail", "finish") and x.get("agent_id") == m.get("agent_id"))), None)
        out.append({"t": round(m["t"] - t0, 1), "at": clock(m["t"] - t0), "who": _who(names.get(str(m.get("agent_id")))),
                    "next": f"{clock(nxt['t'] - t0)} {story_of(nxt)}" if nxt else "nothing after it: the record ends there"})
    return out


def resolve(state_dir, ref: str, cwd=None) -> "tuple[dict, bool]":
    """The replay `ref` names (live/compare.resolve; CompareError when none) and whether it was read from a saved file."""
    from pathlib import Path
    from halo_harness.live import compare, replay_file
    if ref.startswith("mission:"):
        raise compare.CompareError("a mission's report is the fleet pack's mission page (halo fleet mission report)")
    p = compare.resolve(state_dir, ref, cwd=cwd)
    rid = ref.split(":", 1)[1] if ref.split(":", 1)[0] in ("session", "run", "file") else ref
    from_file = ref.startswith("file:") or (not ref.startswith(("session:", "run:")) and (
        replay_file.path_for(state_dir, rid) is not None or rid.endswith(replay_file.SUFFIX) or Path(rid).expanduser().is_file()))
    return p, bool(from_file)


def card(p: dict, ref: str = "", from_file: bool = False) -> dict:
    """The report card of replay `p` (a session's, a goal run's, a saved file's)."""
    from halo_harness.live.compare import lanes as lanes_of
    from halo_harness.live.compare_text import cells
    from halo_harness.live.replay_facts import figures
    from halo_harness.live.report_card_sections import cannot, models_did
    facts = p.get("facts") if isinstance(p.get("facts"), dict) else {}
    fig, lanes = figures(p), lanes_of(p)
    agents = [a for a in p.get("agents") or [] if isinstance(a, dict)]
    names = {str(a.get("agent_id")): a for a in agents}
    top = next((a for a in agents if not a.get("parent")), {}) or {}
    t0 = _num(p.get("started")) or 0.0
    how = str(fig.get("how") or "unknown")
    story, more = _story(p, names, facts, top, how, t0)
    marks = [m for m in p.get("marks") or [] if m.get("kind") == "ask" and _num(m.get("t")) is not None]
    waits = [{"t": round(m["t"] - t0, 1), "at": clock(m["t"] - t0), "who": _who(names.get(str(m.get("agent_id"))), False),
              "text": str(m.get("text") or "a question"), "secs": wait_secs(p, m)} for m in marks]
    started, spend = _num(p.get("started")), _money(p, fig, lanes)
    return {"format": FORMAT, "kind": p.get("kind") or "session", "id": p.get("run_id") or p.get("session_id") or p.get("id"),
            "ref": ref, "title": p.get("title") or "", "started": started, "ended": _num(p.get("ended")),
            "when": time.strftime("%Y-%m-%d %H:%M", time.localtime(started)) if started else "when unknown",
            "halo": (p.get("halo") or "") if from_file else "", "file": p.get("id") if from_file else None,
            "how": how, "ok": fig.get("ok"), "cells": cells(fig), "story": story, "story_more": more,
            "time": _time(p, lanes, fig.get("wall_s")), "money": spend,
            "failures": _failures(p, lambda m: _say(p, m, names, facts, top, how), names, t0),
            "failed_calls": int(facts.get("failed_calls") or 0), "retries": fig.get("retries"),
            "waits": waits, "waited_s": round(sum(w["secs"] or 0 for w in waits), 1),
            "models": models_did(agents, fig), "artefacts": facts.get("artefacts") if isinstance(facts.get("artefacts"), list) else None,
            "cannot": cannot(p, facts, waits, spend)}
