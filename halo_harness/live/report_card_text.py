"""halo_harness.live.report_card_text -- the report card as Markdown (Halo 3.4.1.0 R3 "Time"): what `halo report`
prints and Studio's Copy puts on the clipboard, from the same data the Studio page draws (live/report_card.card). No
model call; a cost Halo cannot price is "unknown" or the priced part with a "+", never $0.

    markdown(card) -> str
"""

from __future__ import annotations

from halo_harness.live.compare_text import bare, money, secs

KIND = {"session": "session", "run": "goal run", "file": "saved replay"}
CELL_ROWS = (("ended", "How it ended"), ("wall", "Wall time"), ("cost", "Cost"), ("tokens", "Tokens"), ("models", "Models used"),
             ("agents", "Agents spawned"), ("asks", "Asks to you"), ("failures", "Failures"), ("retries", "Retries"))


def pct(x) -> str:
    return "?" if x is None else f"{round(x * 100)} %"


def cost_of(usd, unknown: bool) -> str:
    if unknown:
        return f"{money(usd)}+" if usd else "unknown (no price)"
    return money(usd)


def _cell(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def head(c: dict) -> list:
    kind = KIND.get(c.get("kind") or "", c.get("kind") or "run")
    where = f"from the saved replay `{c['file']}`" if c.get("file") else f"from the {kind}'s own record"
    return [f"# Report card: {c.get('title') or c.get('id') or '(untitled)'}", "",
            f"{kind} `{c.get('id')}` · {c.get('when')} · {c.get('how')}" + (f" · saved by Halo {c['halo']}" if c.get("halo") else ""),
            f"Rendered {where}; no model call.", ""]


def time_lines(t: dict) -> list:
    out = [f"Wall time {secs(t.get('wall_s'))}."]
    if t.get("phases"):
        out.append("By phase: " + "; ".join(f"{p['words']} {secs(p['secs'])} ({pct(p['share'])})" for p in t["phases"]) + ".")
    else:
        out.append("By phase: not in this record.")
    for b in t.get("blocks") or []:
        out.append(f"- {b['block']}: {b['agents']} agent{'s' if b['agents'] != 1 else ''}, {secs(b['secs'])} of agent time "
                   f"({secs(b['busy'])} busy)")
    return out


def money_lines(m: dict) -> list:
    total = "unknown" if m.get("total") is None or (not m.get("known") and not m.get("total")) else money(m["total"]) + ("" if m.get("known") else "+")
    out = [f"Total {total}."]
    out += [f"- {bare(x['model'])}: {cost_of(x.get('cost_usd'), x.get('unknown'))}" + ("" if x.get("unknown") else f" ({pct(x.get('share'))})")
            for x in m.get("models") or []]
    if not m.get("models"):
        out.append("- by model: nothing priced in this record")
    if m.get("blocks"):
        out.append("\nBy block: " +"; ".join(f"{b['block']} {cost_of(b['cost_usd'], b['unknown'])}" for b in m["blocks"])
                   + (" (priced calls only: an unpriced call is in no block)." if not m.get("known") else "."))
    return out


def waited(c: dict) -> str:
    waits = c.get("waits") or []
    timed = [w for w in waits if w.get("secs") is not None]
    if not waits:
        return "Nothing waited on you."
    if not timed:
        return "How long these waited is not in the record."
    return f"In all {'at least ' if len(timed) < len(waits) else ''}{secs(c.get('waited_s'))} waiting on you."


def markdown(c: dict) -> str:
    out = head(c)
    out += ["## The figures", "", "| | |", "|---|---|"]
    out += [f"| {label} | {_cell(c['cells'][key]['text'])} |" for key, label in CELL_ROWS if key in c.get("cells", {})]
    out += ["", "## The story", ""]
    out += [f"{i}. `{s['at']}` {s['text']}" for i, s in enumerate(c.get("story") or [], 1)]
    if c.get("story_more"):
        out.append(f"\n...and {c['story_more']} more step{'s' if c['story_more'] != 1 else ''} (Replay shows every one).")
    out += ["", "## Where the time went", ""] + time_lines(c.get("time") or {})
    out += ["", "## Where the money went", ""] + money_lines(c.get("money") or {})
    out += ["", "## What failed and what happened next", ""]
    out += [f"- `{f['at']}` {f['who']} failed; next: {f['next']}" for f in c.get("failures") or []]
    if c.get("failed_calls"):
        out.append(f"- {c['failed_calls']} model call{'s' if c['failed_calls'] != 1 else ''} failed (the provider answered with an error)")
    if c.get("retries"):
        out.append(f"- {c['retries']} retr{'ies' if c['retries'] != 1 else 'y'}" + (" (pieces the gate sent back)" if c.get("kind") == "run" else " by the provider"))
    if not c.get("failures") and not c.get("failed_calls") and not c.get("retries"):
        out.append("Nothing failed.")
    out += ["", "## What waited on you", ""]
    waits = c.get("waits") or []
    out += [f"- `{w['at']}` {w['who']}: {w['text']}" + (f" -- {secs(w['secs'])}" if w.get("secs") is not None and "answered" not in w["text"] else "")
            for w in waits]
    out.append(("\n" if waits else "") + waited(c))
    out += ["", "## Which model did what", ""]
    for m in c.get("models") or []:
        who = "; ".join(f"{a['name']}" + (f" ({a['role']})" if a["role"] and a["role"] != a["name"] else "") + (f": {a['task']}" if a["task"] else "")
                        for a in m["agents"])
        share = f" -- {pct(m['cost_share'])} of cost, {pct(m['time_share'])} of time" if m.get("cost_share") is not None or m.get("time_share") is not None else ""
        out.append(f"- **{bare(m['model'])}**{share}: {who}")
    out += ["", "## Artefacts", ""]
    arts = c.get("artefacts")
    if arts is None:
        out.append("Not in this record (see below).")
    else:
        out += [f"- `{a['rel']}`" + (" (outside the project: its name only)" if a.get("outside") else "") + f" -- {', '.join(a.get('by') or [])}" for a in arts]
        out += [] if arts else ["No file was written."]
    out += ["", "## What this record cannot show", ""] + [f"- {line}" for line in c.get("cannot") or []]
    return "\n".join(out) + "\n"
