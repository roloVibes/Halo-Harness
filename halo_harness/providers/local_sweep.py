"""halo_harness.providers.local_sweep -- Halo 3.6.0.25 T: the sweep's rules and its record (the run itself is
providers/local_sweep_run.py; `halo local bench --sweep MODEL` and Studio's "Find the best window").

    next_window(rows, *, start, top) -> the window to measure next, or None (the sweep has its answer)
    mark(rows)                     -> rows, each with its `state` (on the card / spilled / on the card, but slow /
                                      did not load) and `slow` (past the cliff)
    pick(rows, *, top, trained, ...) -> (window or None, the one line that says why)
    load(state_dir, host_url, model, digest=, server=) / save(state_dir, record)

The steps: from the start (Halo's own estimate) up by 16,384 (8,192 under 32,768) while the load is wholly on the
card with room and no cliff, or down when the start itself spills, to at most `top` (the model's trained window, the
host's max_ctx, Halo's 131,072 cap: the pick's line names which one bound it). A window whose /api/ps did not answer is
"unknown": never a spill, never picked. The cliff: a window whose reply speed is more than 40 % below the best reply speed of a smaller
window of the same sweep (on Windows a load can spill into shared memory while the server still says it is wholly on
the card). The pick: the largest measured window wholly on the card, with at least 300 MiB free on the card where
that is known, and before the cliff: the measured TIGHT window (`tight_ctx`). The safe window (`max_full_gpu_ctx`)
keeps the measuring ladder's own headroom rule (`safe_window`). The record sits in `<state>/ollama-fit.json` under `sweeps`, keyed by the
host's url and the model, and holds only under the digest and the server (version + fit settings) it was measured
under: another one is no record at all.
"""

from __future__ import annotations

import time
from typing import Optional

STEP_BIG, STEP_SMALL, SMALL_UNDER = 16384, 8192, 32768
FLOOR = 4096
MAX_LOADS = 6
CLIFF = 0.40          # more than 40 % below the best smaller window's reply speed: past the cliff
NOISE = 0.40          # a reply speed more than 40 % off the window before: one more timed call
ROOM_MIB = 300
ON, SPILLED, SLOW, FAILED = "on the card", "spilled", "on the card, but slow", "did not load"
UNKNOWN = "unknown: /api/ps did not answer"  # no size or size_vram read: never a spill, never picked


def step_up(w: int) -> int:
    return w + (STEP_BIG if w >= SMALL_UNDER else STEP_SMALL)


def step_down(w: int) -> Optional[int]:
    n = w - (STEP_BIG if w - STEP_BIG >= SMALL_UNDER else STEP_SMALL)
    return n if n >= STEP_SMALL else (FLOOR if w > FLOOR else None)


def grid(w: int) -> int:
    """The start on the steps' grid: a multiple of 8,192 at or under `w` (at least 8,192)."""
    return max(STEP_SMALL, (int(w) // STEP_SMALL) * STEP_SMALL)


def room_ok(r: dict) -> bool:
    return not isinstance(r.get("free_mib"), (int, float)) or r["free_mib"] >= ROOM_MIB


def good(r: dict) -> bool:
    return r.get("state") == ON and room_ok(r)


def headroom_ok(r: dict) -> bool:
    """The measuring ladder's own headroom rule (ollama_calibrate_steps): at least max(8 % of the card, 1.5 GiB) free
    on the card. Free memory unknown: never."""
    from halo_harness.providers.ollama_calibrate_steps import HEADROOM_FRACTION, HEADROOM_MIN_BYTES
    free, used = r.get("free_mib"), r.get("used_mib")
    if not isinstance(free, (int, float)) or not isinstance(used, (int, float)):
        return False
    total = (free + used) * 2 ** 20
    return total > 0 and free * 2 ** 20 >= max(HEADROOM_FRACTION * total, HEADROOM_MIN_BYTES)


def safe_window(rows: list) -> Optional[int]:
    """After the ruling on fault 7: the largest swept window a pick could be (wholly on the card, room, before the
    cliff) that also meets the ladder's headroom rule: the window Halo calls safe (`max_full_gpu_ctx`); else None."""
    cliff = min((r["window"] for r in rows if r.get("slow")), default=None)
    return max((r["window"] for r in rows if good(r) and headroom_ok(r) and (cliff is None or r["window"] < cliff)),
               default=None)


def safe_line(rec: dict) -> str:
    """The one more short line under the pick when the safe window is another (smaller) one; else ""."""
    pick, safe = rec.get("pick"), rec.get("safe")
    if not pick or not isinstance(safe, int) or safe >= pick:
        return ""
    return ("the pick is tight: it fits with nothing else on the card; with other programs on the card the safe "
            f"window is {safe:,}")


def mark(rows: list) -> list:
    for r in rows:
        if r.get("error"):
            r.update(state=FAILED, slow=False)
            continue
        if r.get("on_card") is False:
            r.update(state=SPILLED, slow=False)
            continue
        if r.get("on_card") is None:
            r.update(state=UNKNOWN, slow=False)
            continue
        best = max((x["tok_s"] for x in rows if x["window"] < r["window"] and x.get("on_card") and not x.get("error")
                    and isinstance(x.get("tok_s"), (int, float))), default=None)
        slow = bool(best and isinstance(r.get("tok_s"), (int, float)) and r["tok_s"] < (1 - CLIFF) * best)
        r.update(state=SLOW if slow else ON, slow=slow, best_before=best if slow else None)
    return rows


def next_window(rows: list, *, start: int, top: int) -> Optional[int]:
    if not rows:
        return min(start, top)
    first = rows[0]
    if first.get("state") in (FAILED, UNKNOWN):
        return None
    if not good(first):  # the start spills (or leaves no room): down to the first window that does not
        if any(good(r) for r in rows if r["window"] < first["window"])                 or any(r.get("state") in (FAILED, UNKNOWN) for r in rows):
            return None
        return step_down(min(r["window"] for r in rows))
    up = [r for r in rows if r["window"] >= first["window"]]
    hi = max(up, key=lambda r: r["window"])
    if not good(hi) or hi["window"] >= top:
        return None
    return min(step_up(hi["window"]), top)


def _times(a: float, b: float) -> str:
    r = round(a / b, 1) if b else 0
    return f"{r:g}x"


def pick(rows: list, *, top: int, trained: Optional[int], cap: Optional[int] = None, loads_left: int = 1,
         stopped: bool = False) -> "tuple[Optional[int], str]":
    cliff = min((r["window"] for r in rows if r.get("slow")), default=None)
    ok = [r for r in rows if good(r) and (cliff is None or r["window"] < cliff)]
    if not ok:
        bad = min((r["window"] for r in rows), default=None)
        if bad is None:
            return None, "nothing measured yet"
        r = min(rows, key=lambda x: x["window"])
        if r.get("state") == FAILED:
            return None, f"{r['window']:,}: it did not load ({r.get('error')})"
        if r.get("state") == UNKNOWN:
            return None, f"{r['window']:,}: /api/ps did not answer, so whether it sits wholly on the card is unknown"
        return None, f"no window from {bad:,} down stays wholly on the card with {ROOM_MIB} MiB free"
    p = max(ok, key=lambda r: r["window"])
    w = p["window"]
    above = sorted((r for r in rows if r["window"] > w), key=lambda r: r["window"])
    if above:
        n = above[0]
        if n.get("state") == SPILLED:
            why = "the next step spilled"
        elif n.get("state") == SLOW:
            why = f"the next step was {_times(n.get('best_before') or 0, n.get('tok_s') or 0)} slower"
        elif n.get("state") == FAILED:
            why = "the next step did not load"
        elif n.get("state") == UNKNOWN:
            why = "the next step could not be read (/api/ps did not answer)"
        else:
            why = f"the next step left {int(n['free_mib'])} MiB free on the card (under {ROOM_MIB})"
    elif trained and w >= trained:
        why = "the model's own limit"
    elif cap and w >= cap:
        why = "the host's max_ctx"
    elif w >= top:
        why = f"Halo's {top:,} cap"
    elif stopped:
        why = "the largest measured before the Stop (start it again to go on)"
    elif loads_left <= 0:
        why = "the largest measured; the loads were used (start it again with more loads to go on)"
    else:
        why = "the largest measured so far"
    return w, f"{w:,}: {why}"


# ---- the record -------------------------------------------------------------------------------------------------

def _key(host_url: str, model: str) -> str:
    from halo_harness.providers.ollama_calibrate import _model_key
    return _model_key(host_url, model)


def load(state_dir, host_url: str, model: str, *, digest: Optional[str] = None, server: Optional[dict] = None,
         any_build: bool = False) -> Optional[dict]:
    """The sweep of (host, model) measured under this digest and this server, else None (`any_build`: whatever is
    kept, for a page that says it is from another build)."""
    from halo_harness.providers.ollama_calibrate import load_fit_store
    rec = (load_fit_store(state_dir).get("sweeps") or {}).get(_key(host_url, model))
    if not isinstance(rec, dict):
        return None
    if any_build:
        return rec
    if digest is not None and rec.get("digest") != digest:
        return None
    if server is not None and rec.get("server") != server:
        return None
    return rec


def save(state_dir, rec: dict) -> None:
    from halo_harness.filelock import file_lock
    from halo_harness.providers.ollama_calibrate import _fit_store_path, load_fit_store, save_fit_store
    rec["at"] = time.time()
    with file_lock(_fit_store_path(state_dir)):
        store = load_fit_store(state_dir)
        sweeps = store.get("sweeps") if isinstance(store.get("sweeps"), dict) else {}
        sweeps[_key(rec["host_url"], rec["model"])] = rec
        store["sweeps"] = sweeps
        save_fit_store(state_dir, store)


def row_line(r: dict) -> str:
    free = f"{int(r['free_mib']):,} MiB free" if isinstance(r.get("free_mib"), (int, float)) else "free unknown"
    sp = lambda v: f"{v:g}" if isinstance(v, (int, float)) else "?"  # noqa: E731
    if r.get("state") == FAILED:
        return f"{r['window']:,}: did not load ({r.get('error')})"
    return (f"{r['window']:,}: {r.get('state') or '?'}, {free}, prompt {sp(r.get('prompt_tok_s'))} tok/s, reply "
            f"{sp(r.get('tok_s'))} tok/s" + (" (timed twice)" if r.get("timed") == 2 else ""))


def lines(rec: dict) -> list:
    """The sweep's lines for the CLI and the tuning report: each window, then the pick and its reason."""
    out = [row_line(r) for r in sorted(rec.get("windows") or [], key=lambda r: r["window"])]
    out.append(f"the pick: {rec['why']}" if rec.get("pick") else f"no pick: {rec.get('why') or 'nothing measured'}")
    return out + [x for x in (safe_line(rec),) if x]
