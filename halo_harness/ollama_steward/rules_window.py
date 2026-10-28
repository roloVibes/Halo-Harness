"""halo_harness.ollama_steward.rules_window -- Halo 3.3.4.0 R3: the window
rules (knowledge/symptoms.md, `prompt-trimmed`, `cpu-spill`; R1 and R2's
findings):

(a) too small: trims, cut replies, or a p95 prompt within 10 % of the
    window sent -> raise `num_ctx` toward the cap (the learned cap, else what
    the card fits, else `max_ctx`); at the cap, the tuned twin. A trim of a
    window sent at 4,096 or 8,192 is its own finding, "a small window was
    asked for" (every real trim on the measured host was one: 3.2.3.0's
    calibration bug), naming the call's kind and the window's source.
(b) too large: a p95 prompt far under the window, with reloads or a CPU
    spill -> lower it, never under the largest prompt seen plus its reply;
    a spill with prompts that need the window -> the tuned twin's line.
(h) two windows, one model: different halos (or sessions) send one model
    different windows; Ollama reloads it at every change -> one profile
    window for all of them.
(i) switch without fit (3.3.5.0 R0): a call whose model differs from the
    previous call's in the same session (`switched_from`) with no switch
    step before it (`fitted` false): the window, the tools and the history
    were the old model's.
"""

from __future__ import annotations

from halo_harness.ollama_steward.rules import finding, hint, proposal

NEAR = 0.9          # a p95 prompt within 10 % of the window
FAR = 0.4           # a p95 prompt under 40 % of the window
SMALL_ASKED = (4096, 8192)
REPLY_ROOM = 4096
MIN_WINDOW = 8192


def _pow2_ceil(n: int) -> int:
    p = 1
    while p < n:
        p *= 2
    return p


def _current(g: dict):
    return g["profile"].get("num_ctx") or g["stats"]["window"]


def too_small(g: dict, ctx: dict) -> list:
    s, out = g["stats"], []
    window = _current(g)
    small = [x for x in s["trims"] if x.get("num_ctx_sent") in SMALL_ASKED]
    small_ev = [e for e in g["events"] if e.get("kind") == "prompt-trimmed"
                and (e.get("data") or {}).get("window_sent") in SMALL_ASKED]
    if small or small_ev:
        src = sorted({f"{x.get('kind')} / {x.get('window_source')}" for x in small}) or ["the server log"]
        sent = sorted({x.get("num_ctx_sent") for x in small} | {(e.get("data") or {}).get("window_sent") for e in small_ev} - {None})
        out.append(finding("window-asked-small", g, "error",
                           f"a small window was asked for: {', '.join(str(w) for w in sent) or '4096 or 8192'} "
                           f"sent and the prompt trimmed ({', '.join(src)})",
                           calls=small, events=small_ev, numbers={"trims": len(small) + len(small_ev)},
                           kinds=sorted({x.get("kind") for x in small} - {None}),
                           sources=sorted({x.get("window_source") for x in small} - {None})))
    if not window:
        return out
    p95 = s["p95"]
    near = p95 is not None and p95 >= NEAR * window
    if not (s["trims"] or s["cuts"] or near):
        return out
    cap, cap_src = g["cap"], g["cap_source"]
    nums = {"window": window, "p95_prompt": p95, "trims": len(s["trims"]), "cuts": len(s["cuts"]), "cap": cap}
    why = (f"{len(s['trims'])} trims, {len(s['cuts'])} cut replies" + (f", p95 prompt {p95:.0f} of {window}" if near else ""))
    if cap and cap > window:
        want = max(2 * window, _pow2_ceil(int((p95 or 0) * 1.25) + REPLY_ROOM))
        to = min(cap, want)
        out.append(finding("window-small", g, "warn", f"the window {window} is too small for the prompts: {why}",
                           calls=(s["trims"] + s["cuts"])[:8], numbers=nums,
                           proposal=proposal("num_ctx", g["profile"].get("num_ctx"), to,
                                             f"{why}; raised toward the {cap_src} ({cap})")))
    elif cap and cap <= window:
        model, host = g["model"], g["host"]
        out.append(finding("window-small", g, "warn", f"the window {window} is at the {cap_src} and still too small: "
                           f"{why}", calls=(s["trims"] + s["cuts"])[:8], numbers=nums,
                           server_hint=hint(None, f"halo ollama tune {model} --host {host}",
                                            "a twin with every layer on the GPU and one fixed window; no disk")))
    else:
        out.append(finding("window-small", g, "warn", f"the window {window} is too small ({why}) and no cap is "
                           f"measured for it", calls=(s["trims"] + s["cuts"])[:8], numbers=nums,
                           server_hint=hint(None, f"halo ollama calibrate {g['model']} --host {g['host']}",
                                            "a few loads of the model, about a minute")))
    return out


def too_large(g: dict, ctx: dict) -> list:
    s = g["stats"]
    window, p95 = _current(g), s["p95"]
    if not window or p95 is None or p95 >= FAR * window or len(s["ok"]) < 5:
        return []
    spills = [e for e in g["events"] if e.get("kind") == "cpu-spill"]
    reloads = [e for e in g["events"] if e.get("kind") == "reloaded"]
    if not (spills or reloads or len(s["reloads"]) * 2 > len(s["ok"])):
        return []
    floor = max(MIN_WINDOW, _pow2_ceil(int((s["max_prompt"] or p95) * 1.25) + REPLY_ROOM))
    if floor >= window:
        return []
    why = (f"p95 prompt {p95:.0f} of {window}; " + ", ".join(
        t for t in (f"{len(spills)} CPU spills" if spills else "", f"{len(reloads) + len(s['reloads'])} reloads"
                    if reloads or s["reloads"] else "") if t))
    return [finding("window-large", g, "warn", f"the window {window} is far larger than the prompts and costs: {why}",
                    calls=s["reloads"][:4], events=(spills + reloads)[:8],
                    numbers={"window": window, "p95_prompt": p95, "max_prompt": s["max_prompt"],
                             "spills": len(spills), "reloads": len(reloads) + len(s["reloads"])},
                    proposal=proposal("num_ctx", g["profile"].get("num_ctx"), floor,
                                      f"{why}; the largest prompt seen still fits with room for the reply"))]


def two_windows(g: dict, ctx: dict) -> list:
    s = g["stats"]
    if len(s["windows"]) < 2 or g["profile"].get("num_ctx"):
        return []
    by_window: dict = {}
    for x in s["native"]:
        if isinstance(x.get("num_ctx_sent"), int):
            by_window.setdefault(x["num_ctx_sent"], set()).add(x.get("from") or "this machine")
    callers = set().union(*by_window.values())
    reloads = [e for e in g["events"] if e.get("kind") == "reloaded"]
    if len(callers) < 2 and not reloads:
        return []
    cap = g["cap"]
    fitting = [w for w in by_window if not cap or w <= cap]
    to = max(fitting or by_window)
    if s["max_prompt"] and to < s["max_prompt"] + REPLY_ROOM and cap and cap > to:
        to = min(cap, _pow2_ceil(s["max_prompt"] + REPLY_ROOM))
    windows = ", ".join(f"{w} from {', '.join(sorted(m))}" for w, m in sorted(by_window.items()))
    return [finding("two-windows", g, "warn", f"{g['model']} is asked with {len(by_window)} windows ({windows}): "
                    f"Ollama reloads it at every change", events=reloads, calls=s["reloads"][:4],
                    numbers={"windows": sorted(by_window), "reloaded_events": len(reloads),
                             "slow_loads": len(s["reloads"])},
                    proposal=proposal("num_ctx", None, to, "one window for every halo, so the model stays loaded"))]


def spilled(g: dict, ctx: dict) -> list:
    """CPU spills the window rules did not answer (no ledger window to lower,
    or prompts that need the window): R1 found llama.cpp's fit margin behind
    them, so the line is the tuned twin (every layer on), never a smaller
    window for prompts that need it."""
    spills = [e for e in g["events"] if e.get("kind") == "cpu-spill"]
    s = g["stats"]
    window = _current(g)
    if not spills or (window and s["p95"] is not None and s["p95"] < FAR * window):
        return []
    return [finding("cpu-spill", g, "warn", f"{len(spills)} CPU spills of {g['model']}: llama.cpp kept its fit margin "
                    "or another program holds the card", events=spills, numbers={"spills": len(spills)},
                    server_hint=hint(None, f"halo ollama tune {g['model']} --host {g['host']}",
                                     "a twin with every layer on the GPU and one fixed window; no disk"))]


def switch_without_fit(g: dict, ctx: dict) -> list:
    bad = [x for x in g["lines"] if x.get("switched_from") and x.get("fitted") is False
           and x.get("kind") in (None, "turn", "compaction")]
    if not bad:
        return []
    frm = sorted({str(x.get("switched_from")) for x in bad})
    return [finding("switch-without-fit", g, "warn",
                    f"{len(bad)} call{'' if len(bad) == 1 else 's'} to {g['model']} followed a call to {', '.join(frm)} "
                    "in the same session with no switch step before it: the window, the tools and the history were the "
                    "old model's (a Halo before 3.3.5.0, or a path that moved the model without /model)",
                    calls=bad, numbers={"calls": len(bad)}, switched_from=frm)]


RULES = [two_windows, too_small, too_large, spilled, switch_without_fit]  # one window for every halo first: it is why the others reload
