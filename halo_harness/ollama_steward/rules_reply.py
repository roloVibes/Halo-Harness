"""halo_harness.ollama_steward.rules_reply -- Halo 3.3.4.0 R3: the rules
for the reply and the session, the three bugs parked in 3.2.3.0
(knowledge/symptoms.md `reply-cut`, `window-full`,
`compaction-not-firing`, `no-reply-reserve`, `truncated-reply-resent`):

(c) replies cut (`done_reason: "length"`, the server's reply-cut and
    window-full lines) -> a `num_predict` reserve for that model: the
    reply's room is never squeezed under it (agent/ollama_window.py), the
    prompt compacts first.
(d) no compaction: a session whose prompt passed 80 % of the window sent
    with no compaction call after it -> compact earlier for that model
    (`compact_at`); compaction calls that ran and failed are said apart.
(e) a truncated reply resent: a cut reply, then the next call of the same
    session carrying it (its prompt grew by at least half the cut reply) or
    sent again unchanged and cut again -> flagged; the reserve, and the
    session no longer keeps a reply the window cut (ollama_window_steward).

3.3.13.1: the reserve is bounded (rules_reply_bound.py): its target comes
from the measured cut, never from the current value; never above the
model's context minus the prompt; one an hour per model (any session); never
twice for one cut; `reserve-loop` says when the old doubling was held.
"""

from __future__ import annotations

from halo_harness.ollama_steward.rules import finding, proposal
from halo_harness.ollama_steward.rules_reply_bound import RESERVE_MIN, loop_finding, reserve  # noqa: F401 (3.3.13.1)

PAST = 0.8
COMPACT_EARLIER = 0.7


def _at(x) -> str:
    return str(x.get("at") or "")


def _cut_id(x: dict) -> str:
    return f"{x.get('session')}|{x.get('at')}"


def replies_cut(g: dict, ctx: dict) -> list:
    cuts = g["stats"]["cuts"]
    events = [e for e in g["events"] if e.get("kind") in ("reply-cut", "window-full")]
    if not cuts and not events:
        return []
    full = [x for x in cuts if isinstance(x.get("num_ctx_sent"), int) and isinstance(x.get("prompt_eval_count"), int)
            and isinstance(x.get("eval_count"), int)
            and x["prompt_eval_count"] + x["eval_count"] >= 0.97 * x["num_ctx_sent"]]
    last = max(cuts, key=_at) if cuts else {}  # 3.3.13.1: the target from the measured cut (rules_reply_bound.py)
    to, held = reserve(g, ctx, reply=last.get("eval_count"), prompt=last.get("prompt_eval_count"),
                       sent=last.get("num_ctx_sent"), cut=_cut_id(last) if last else None)
    current = g["profile"].get("num_predict")
    if to is None and held.startswith("the reserve is already"):
        return loop_finding(g, ctx, held)
    what = (f"{len(cuts)} replies cut ({len(full)} at the window's end)" if cuts
            else f"{len(events)} replies cut by the window (the server's own lines)")
    return [finding("reply-cut", g, "warn", f"{what}: the reply had no room"
                    + (f" (no reserve proposed: {held})" if to is None else ""),
                    calls=cuts, events=events, numbers={"cuts": len(cuts), "at_window_end": len(full),
                                                        "server_lines": len(events),
                                                        **({"cut": _cut_id(last)} if last else {})},
                    proposal=None if to is None else proposal(
                        "num_predict", current, to,
                        "a reply reserve: the prompt compacts before the reply's room drops under it"))] \
        + (loop_finding(g, ctx, held) if to is None else [])


def _sessions(lines: list) -> dict:
    out: dict = {}
    for x in lines:
        if x.get("session") and x.get("kind") != "calibrate":
            out.setdefault((x.get("from"), x["session"]), []).append(x)
    for v in out.values():
        v.sort(key=_at)
    return out


def no_compaction(g: dict, ctx: dict) -> list:
    out = []
    for (machine, sid), lines in _sessions(g["lines"]).items():
        past = [x for x in lines if x.get("kind") == "turn" and x.get("dialect") in (None, "ollama")
                and isinstance(x.get("prompt_eval_count"), int) and isinstance(x.get("num_ctx_sent"), int)
                and x["prompt_eval_count"] >= PAST * x["num_ctx_sent"]]
        if not past:
            continue
        after = [x for x in lines if x.get("kind") == "compaction" and _at(x) >= _at(past[0])]
        failed = [x for x in after if x.get("status") != 200 or x.get("done_reason") == "length"]
        worst = max(past, key=lambda x: x["prompt_eval_count"] / x["num_ctx_sent"])
        nums = {"session": sid, "from": machine or "this machine", "calls_past": len(past),
                "worst": f"{worst['prompt_eval_count']} of {worst['num_ctx_sent']}"}
        if after and len(failed) < len(after):
            continue
        if failed:
            out.append(finding("compaction-failed", g, "warn",
                               f"session {sid} passed {int(PAST * 100)} % of the window and its {len(failed)} "
                               f"compaction calls failed ({', '.join(sorted({str(x.get('status')) for x in failed}))})",
                               calls=past[:3] + failed[:5], numbers=nums))
            continue
        current = g["profile"].get("compact_at")
        out.append(finding("no-compaction", g, "error",
                           f"session {sid} passed {int(PAST * 100)} % of the window ({nums['worst']}) on "
                           f"{len(past)} calls without compacting", calls=past, numbers=nums,
                           proposal=None if current and current <= COMPACT_EARLIER else
                           proposal("compact_at", current, COMPACT_EARLIER,
                                    "compact before the call once the prompt passes this share of the window")))
    return out[:3]


def cut_resent(g: dict, ctx: dict) -> list:
    out = []
    for (_machine, sid), lines in _sessions(g["lines"]).items():
        for a, b in zip(lines, lines[1:]):
            if a.get("done_reason") != "length" or not isinstance(a.get("prompt_eval_count"), int):
                continue
            pa, pb, ea = a["prompt_eval_count"], b.get("prompt_eval_count"), a.get("eval_count") or 0
            if not isinstance(pb, int):
                continue
            carried = ea > 0 and pb >= pa + 0.5 * ea
            unchanged = abs(pb - pa) <= 0.01 * max(pa, 1) and b.get("done_reason") == "length"
            if not (carried or unchanged):
                continue
            how = "carried in the next call" if carried else "sent again unchanged and cut again"
            current = g["profile"].get("num_predict")
            to, held = reserve(g, ctx, reply=ea, prompt=pa, sent=a.get("num_ctx_sent"), session=sid, cut=_cut_id(a))
            out.append(finding("cut-resent", g, "error",
                               f"session {sid}: a reply cut at {pa + ea} tokens was {how}"
                               + (f" (no reserve proposed: {held})" if to is None else ""), calls=[a, b],
                               numbers={"session": sid, "cut_prompt": pa, "cut_reply": ea, "next_prompt": pb,
                                        "cut": _cut_id(a)},
                               proposal=None if to is None else
                               proposal("num_predict", current, to, "room for the reply, so it is not cut and resent")))
            if to is None:
                out.extend(loop_finding(g, ctx, held))
            break
    return out[:3]


RULES = [replies_cut, no_compaction, cut_resent]
