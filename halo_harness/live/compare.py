"""halo_harness.live.compare -- two runs side by side (Halo 3.4.1.0 R2 "Time"; docs/REPLAY.md "Compare two runs").
3.6.0.3: resolve, lanes, CompareError and PHASE (the report card's) moved to live/card_data.py, re-exported here.

A run is anything with a replay: a session of this machine, a goal run of this repo, a saved `.halo-replay` file (one
made anywhere). Both are read as replays (live/replay_file.py, live/replay_run.py; nothing is written) and their
figures (live/replay_facts.py: the record's own, never a live counter) become ROWS, each with the better figure named
by a word; "what differed" is three plain lines derived from the rows. No model call. A run compared with itself is
split at a moment (before / after a steer): `split` seconds since its start, by default its first steer, else halfway.

    resolve(state_dir, ref, cwd) -> payload    ref: "session:<id>" | "run:<id>" | "file:<id>" | a path | a bare id
    cells(fig) -> {key: {value, text}}         one run's cells (the report card reads the same)
    rows(fa, fb) -> [{key, label, a, b, better, word}]      better: "a" | "b" | "same" | None (not compared)
    differed(rows, fa, fb) -> [line, line, line]
    compare(pa, pb, split=None, same=False) -> {a, b, rows, differed, split, axis}   a, b: {label, kind, id, title, started, window, figures, lanes}
"""

from __future__ import annotations

from typing import Optional

from halo_harness.live.card_data import (cells, CompareError, lanes, PHASE, resolve, secs)  # noqa: F401 (moved in 3.6.0.3)
from halo_harness.live.compare_text import differed  # the words: live/compare_text.py

# key, label, which way is better (-1: lower, +1: higher, 0: neither), the word for the better one
ROWS = (("ended", "How it ended", 1, "finished"), ("wall", "Wall time", -1, "faster"), ("cost", "Cost", -1, "cheaper"),
        ("tokens", "Tokens", -1, "fewer"), ("models", "Models used", 0, ""), ("agents", "Agents spawned", 0, ""),
        ("asks", "Asks to you", -1, "fewer"), ("failures", "Failures", -1, "fewer"), ("retries", "Retries", -1, "fewer"))


def _better(key: str, way: int, a, b) -> Optional[str]:
    va, vb = a.get("value"), b.get("value")
    if way == 0 or va is None or vb is None or a.get("unknown") or b.get("unknown"):
        return None
    if key == "ended":
        return "same" if va == vb else "a" if va else "b"
    if abs(float(va) - float(vb)) <= max(1e-9, 0.005 * max(abs(float(va)), abs(float(vb)))):
        return "same"
    return "a" if (float(va) - float(vb)) * way > 0 else "b"


def rows(fa: dict, fb: dict) -> list:
    ca, cb = cells(fa), cells(fb)
    out = []
    windows = bool(fa.get("window") or fb.get("window"))
    for key, label, way, word in ROWS:
        a, b = ca[key], cb[key]
        way = 0 if windows and key == "wall" else way  # two stretches of one run: a shorter stretch is not faster
        better = _better(key, way, a, b)
        out.append({"key": key, "label": label, "a": a, "b": b, "better": better,
                    "word": word if better in ("a", "b") else "same" if better == "same" else "unknown" if way and (a.get("unknown") or b.get("unknown")) else ""})
    return out


def _side(label: str, p: dict, window=None) -> dict:
    from halo_harness.live.card_facts import figures
    return {"label": label, "kind": p.get("kind") or "session", "id": p.get("run_id") or p.get("session_id") or p.get("id"),
            "file": p.get("id") if p.get("saved") else None, "title": p.get("title") or "", "started": p.get("started"),
            "figures": figures(p, window), "lanes": lanes(p, window)}


def compare(pa: dict, pb: dict, split: Optional[float] = None, same: bool = False) -> dict:
    """The comparison of two replays; `same` (one run named twice) splits it at `split` (seconds since its start)."""
    wa = wb = None
    if same:
        t0, t1 = float(pa.get("started") or 0.0), float(pa.get("ended") or pa.get("started") or 0.0)
        steers = [s for s in ((pa.get("facts") or {}).get("steers") or []) if t0 < s < t1]
        cut = t0 + split if split is not None else steers[0] if steers else (t0 + t1) / 2
        cut = min(max(cut, t0), t1)
        wa, wb = (t0, cut), (cut, t1)
    a, b = _side("A", pa, wa), _side("B", pb, wb)
    if same:
        a["title"], b["title"] = f"{a['title']} -- before {secs(wa[1] - wa[0])}", f"{b['title']} -- from {secs(wa[1] - wa[0])} on"
    r = rows(a["figures"], b["figures"])
    return {"a": a, "b": b, "rows": r, "differed": differed(r, a["figures"], b["figures"]),
            "split": round(wa[1] - wa[0], 1) if same else None,
            "axis": {"secs": max(a["figures"]["wall_s"] or 0, b["figures"]["wall_s"] or 0, 1)}}
