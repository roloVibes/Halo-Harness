"""halo_harness.voice.latency -- the latency card of a voice turn (Halo 3.3.9.0 R2; docs/VOICE.md "The latency card"):

    Card(clock, budget_ms).mark(stamp)      the stamps, each once: spoke (the last speech frame), heard (the VAD's end),
                                            text (the transcript back), token (the reply's first text), audio (its first
                                            sound), last (its last sound)
    Card.stages() -> {heard, text, token, audio, last} in ms   heard = heard - spoke, text = text - heard, token = token -
                                            text, audio = audio - token, last = last - audio (how long it spoke)
    Card.total_ms() -> spoke -> first audio (the wait the person hears)      line(card) -> the status bar's one line
    record(state_dir, card, **extra)        one row in <state>/voice/turns.jsonl
    rows(state_dir, n=50) / stats(state_dir, n=50) / stats_lines(st)          `halo voice stats`: median and worst per
                                            stage over the newest n turns, and the slow stage named
    over(row) -> [stage]                    the stages over their share of the budget (the steward's voice-slow)
    3.3.9.0 R3: a card whose stt or tts is on another halo (voice/remote.py) carries `link` {kind: {host, ms}} and the
    `link` stage (the LAN round trip, inside text / audio, said beside them like `last`): "stt on pc over the LAN (+40 ms)"

The budget is `voice.latency_budget_ms`, else the bundle's `latency_budget_ms`, else 1,500 ms; Part K's measured local
loop is 750-900 ms, said as the target. A stage's share of the budget: heard 20 %, text 25 %, token 40 %, audio 15 %.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from statistics import median
from typing import Optional

STAGES = ("heard", "text", "token", "audio")
SHARE = {"heard": 0.20, "text": 0.25, "token": 0.40, "audio": 0.15}
BUDGET_MS = 1500
TARGET = "750-900 ms"
KEEP = 50
_ORDER = ("spoke", "heard", "text", "token", "audio", "last")


def budget(bundle_ms: Optional[int] = None) -> int:
    from halo_harness.theme import get_config_value
    v = get_config_value("voice.latency_budget_ms", default=None)
    for x in (v, bundle_ms):
        if isinstance(x, int) and not isinstance(x, bool) and x > 0:
            return x
    return BUDGET_MS


class Card:
    def __init__(self, clock=time.perf_counter, budget_ms: int = BUDGET_MS) -> None:
        self.clock, self.budget_ms = clock, int(budget_ms)
        self.t: dict = {}
        self.interrupted = self.steered = False
        self.text = ""
        self.link: dict = {}  # 3.3.9.0 R3: {kind: {host, ms}} -- a speech server on another halo, its LAN round trip

    def mark(self, stamp: str, at: Optional[float] = None) -> None:
        if stamp not in self.t:
            self.t[stamp] = self.clock() if at is None else at

    def _ms(self, a: str, b: str) -> Optional[int]:
        if a in self.t and b in self.t:
            return max(0, int(round((self.t[b] - self.t[a]) * 1000)))
        return None

    def stages(self) -> dict:
        return {b: self._ms(a, b) for a, b in zip(_ORDER, _ORDER[1:])}

    def total_ms(self) -> Optional[int]:
        return self._ms("spoke", "audio")

    def row(self) -> dict:
        st = self.stages()
        out = {"at": round(time.time(), 3), "total_ms": self.total_ms(), "stages": st, "budget_ms": self.budget_ms,
               "interrupted": self.interrupted, "steered": self.steered, "chars": len(self.text)}
        if self.link:  # the link stage: inside text / audio already, said beside them (like `last`, outside the sum)
            ms = [v.get("ms") for v in self.link.values() if isinstance(v.get("ms"), (int, float))]
            st["link"] = int(round(sum(ms))) if ms else None
            out["link"] = {k: dict(v) for k, v in self.link.items()}
        return out


def _s(ms) -> str:
    return "?" if ms is None else f"{ms / 1000:.1f}"


def over(row: dict) -> list:
    b = int(row.get("budget_ms") or BUDGET_MS)
    st = row.get("stages") or {}
    return [k for k in STAGES if isinstance(st.get(k), int) and st[k] > SHARE[k] * b]


def line(card) -> str:
    row = card.row() if isinstance(card, Card) else card
    st, total, b = row["stages"], row["total_ms"], row["budget_ms"]
    parts = " · ".join(f"{k} {_s(st.get(k))}" for k in STAGES)
    if total is None:
        return f"voice: no audio this turn ({parts})" + (" -- interrupted" if row.get("interrupted") else "")
    slow = over(row)
    head = (f"voice: {_s(total)} s of {_s(b)} s" if total <= b else f"voice: {_s(total)} s, over the {_s(b)} s budget")
    return f"{head} ({parts})" + (f" -- slow: {', '.join(slow)}" if slow and total > b else "") + link_words(row)


def link_words(row: dict) -> str:
    """ "; stt on pc over the LAN (+40 ms)" for each speech server on another halo (3.3.9.0 R3)."""
    bits = []
    for kind, v in sorted((row.get("link") or {}).items()):
        ms = v.get("ms") if isinstance(v, dict) else None
        word = "?" if not isinstance(ms, (int, float)) else (f"{ms:.0f}" if ms >= 10 else f"{ms:.1f}")
        bits.append(f"{kind} on {v.get('host')} over the LAN (+{word} ms)")
    return ("; " + ", ".join(bits)) if bits else ""


def path(state_dir) -> Path:
    return Path(state_dir) / "voice" / "turns.jsonl"


def record(state_dir, card, **extra) -> dict:
    row = {**(card.row() if isinstance(card, Card) else dict(card)), **extra}
    p = path(state_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    return row


def rows(state_dir, n: int = KEEP) -> list:
    try:
        text = path(state_dir).read_text(encoding="utf-8")
    except OSError:
        return []
    out = []
    for ln in text.splitlines():
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if isinstance(r, dict) and isinstance(r.get("stages"), dict):
            out.append(r)
    return out[-n:] if n else out


def stats(state_dir, n: int = KEEP) -> dict:
    rs = rows(state_dir, n)
    out = {"turns": len(rs), "stages": {}, "total": None, "slow": None, "budget_ms": None, "target": TARGET}
    if not rs:
        return out
    out["budget_ms"] = int(rs[-1].get("budget_ms") or BUDGET_MS)
    for k in STAGES + ("last", "link"):
        got = [r["stages"][k] for r in rs if isinstance(r["stages"].get(k), int)]
        out["stages"][k] = {"median": int(median(got)), "worst": max(got), "n": len(got)} if got else None
    tot = [r["total_ms"] for r in rs if isinstance(r.get("total_ms"), int)]
    out["total"] = {"median": int(median(tot)), "worst": max(tot), "n": len(tot)} if tot else None
    share = {k: out["stages"][k]["median"] / (SHARE[k] * out["budget_ms"]) for k in STAGES if out["stages"].get(k)}
    if share:
        k = max(share, key=lambda s: share[s])
        out["slow"] = {"stage": k, "of_share": round(share[k], 2)}
    return out


def stats_lines(st: dict) -> list:
    if not st["turns"]:
        return ["no voice turns yet: halo voice, say a sentence, and each turn leaves its card in voice/turns.jsonl"]
    b = st["budget_ms"]
    tot = st["total"]
    out = [f"the newest {st['turns']} voice turn(s), budget {b:,} ms (target {st['target']}):"]
    if tot:
        out.append(f"  total   median {tot['median']:>6,} ms  worst {tot['worst']:>6,} ms")
    for k in STAGES + ("last", "link"):
        s = st["stages"].get(k)
        if s:
            share = f"  (share {int(SHARE[k] * b):,} ms)" if k in SHARE else (
                "  (how long it spoke)" if k == "last" else "  (the LAN round trip to the speech servers)")
            out.append(f"  {k:<7} median {s['median']:>6,} ms  worst {s['worst']:>6,} ms{share}")
    slow = st.get("slow")
    if slow:
        word = "over" if slow["of_share"] > 1 else "within"
        out.append(f"the slow stage: {slow['stage']} ({slow['of_share']:g}x its share, {word} it)")
    return out
