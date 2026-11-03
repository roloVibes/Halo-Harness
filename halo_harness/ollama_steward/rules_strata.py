"""halo_harness.ollama_steward.rules_strata -- the steward watches a Strata server (Halo 3.3.9.2; docs/MODELS-steward-
servers.md "Strata"; knowledge/local-servers.md "## Strata"). The events are Strata's own log lines (server_log_strata.py,
from the source, unverified against a live run); one finding per rule and group, keyed `<server>|<model>`, each with
`server`, `runtime` (strata) and a stated fix line -- never applied by itself.

    strata-disk-bound  the experts are mapped from the model files or held under a RAM budget (the load's words, or a
                       RAM-tight warning) and the newest replies decode under DISK_TOK_S: the expert reads from the SSD
                       dominate -- a smaller set (the next one down, its experts' GB said) or more RAM
    strata-slots       more parallel requests than the card holds: the engine runs fewer slots than asked, or a request
                       waited for a free slot -- the VRAM guide (12 GB runs 1, 20 GB 2, 24 GB 3, 32 GB and more 4), the
                       rest queue; at most that many of Halo's lanes on this server at once
    strata-download    the first launch is downloading (the set, the engine, a drafter): said with the GB and the share,
                       never a timeout; quiet once the server says it is ready

    strata_rules(ctx) -> [finding]
"""

from __future__ import annotations

from statistics import median

from halo_harness.ollama_steward.rules import finding, hint

DISK_TOK_S = 8.0
RECENT = 8
GUIDE = "12 GB runs 1, 20 GB 2, 24 GB 3, 32 GB and more 4"


def _tag(f: dict, g: dict) -> dict:
    from halo_harness.ollama_steward.server_rules_hf import not_asked
    f.update(server=g.get("server") or g["host"], runtime="strata", not_asked=not_asked("strata"), applied=False)
    return f


def _of(g: dict, kind: str) -> list:
    return [e for e in g["events"] if e.get("kind") == kind]


def _d(e: dict) -> dict:
    return e.get("data") or {}


def _smaller(model: str) -> str:
    from halo_harness.strata.catalog import ROWS, match
    row = match(model)
    if row is None or not row.get("experts_gb"):
        return "a smaller set (halo models search strata lists them with their experts' GB)"
    down = [r for r in ROWS if r["family"] == row["family"] and r.get("experts_gb") and r["experts_gb"] < row["experts_gb"]]
    if not down:
        return f"a smaller family (the Coder holds 23 GB of experts; {row['set']} is the smallest {row['family']} set)"
    pick = max(down, key=lambda r: r["experts_gb"])
    return f"{pick['family']}/{pick['set']} ({pick['experts_gb']:g} GB of experts, {row['set']} holds {row['experts_gb']:g})"


def disk_bound(g: dict, ctx: dict) -> list:
    loads = _of(g, "load-result")
    strategy = _d(loads[-1]).get("strategy") if loads else None
    tight = _of(g, "ram-tight")
    budget = [e for e in tight if _d(e).get("budget_gib") is not None]
    rates = [float(_d(e)["tok_s"]) for e in _of(g, "timing") if _d(e).get("phase") == "decode"
             and isinstance(_d(e).get("tok_s"), (int, float))][-RECENT:]
    slow = len(rates) >= 2 and median(rates) < DISK_TOK_S
    if not ((strategy in ("mapped", "budget") or tight) and slow) and not budget:
        return []
    who = g.get("server") or g["host"]
    hits = [float(_d(e)["hit"]) for e in _of(g, "timing") if isinstance(_d(e).get("hit"), (int, float))][-RECENT:]
    why = ("the experts are mapped from the model files" if strategy == "mapped" else
           "the experts sit under a RAM budget" if strategy == "budget" or budget else "RAM is tight beside the experts")
    smaller = _smaller(g["model"])
    text = (f"{g['model']} on {who}: {why}, so the expert reads from the SSD dominate"
            + (f" (the newest {len(rates)} replies decode at {median(rates):g} tok/s)" if rates else "")
            + f" -- {smaller}, or more RAM")
    nums = {"strategy": strategy, "decode_tok_s": round(median(rates), 1) if rates else None, "replies": len(rates),
            "hit": round(median(hits), 3) if hits else None,
            "ram_gb": _d(tight[-1]).get("ram_gb") if tight else None}
    line = f"halo local stop {who}, then halo local serve --runtime strata --model {smaller.split(' ', 1)[0]}"
    return [_tag(finding("strata-disk-bound", g, "warn", text, events=(tight + loads[-1:])[-8:], numbers=nums,
                         server_hint=hint(None, line if "/" in line else f"{smaller} on {who}",
                                          "a smaller set's quality, its download's GB, or a RAM upgrade")), g)]


def slots(g: dict, ctx: dict) -> list:
    evs = _of(g, "slots")
    short = [e for e in evs if isinstance(_d(e).get("asked"), int) and _d(e).get("runs", 0) < _d(e)["asked"]]
    waits = [e for e in evs if isinstance(_d(e).get("waited_s"), int)]
    if not (short or waits):
        return []
    who = g.get("server") or g["host"]
    runs = _d(short[-1]).get("runs") if short else None
    asked = _d(short[-1]).get("asked") if short else None
    text = (f"{g['model']} on {who}: " + (f"{asked} parallel requests asked, the engine runs {runs}" if short else
                                          f"{len(waits)} requests waited for a free slot (up to "
                                          f"{max(_d(e)['waited_s'] for e in waits)} s)")
            + f" -- past the VRAM guide ({GUIDE}) the rest queue; at most "
            + (f"{runs} of Halo's lanes" if runs else "the guide's count of Halo's lanes") + " on this server at once")
    nums = {"asked": asked, "runs": runs, "waits": len(waits),
            "longest_wait_s": max((_d(e)["waited_s"] for e in waits), default=None)}
    line = (f"strata launch ... --parallel {runs} on {who} (halo local stop {who}, then serve it again)" if runs else
            f"fewer lanes on {who} at once, or a bigger card ({GUIDE})")
    return [_tag(finding("strata-slots", g, "warn", text, events=(short + waits)[-8:], numbers=nums,
                         server_hint=hint(None, line, "lanes wait for each other, or a card with more VRAM")), g)]


def download(g: dict, ctx: dict) -> list:
    from halo_harness.ollama_steward.ledger import parse_at
    dl = _of(g, "download")
    if not dl:
        return []
    last = dl[-1]
    host = str(g["host"]).lower()  # any model's load on this server: the served id replaces the set's name once it runs
    after = [e for e in ctx.get("events") or [] if e.get("kind") == "load-result" and str(e.get("host")).lower() == host
             and (parse_at(e.get("at")) or 0) >= (parse_at(last.get("at")) or 0)]
    if after:
        return []
    d = _d(last)
    who = g.get("server") or g["host"]
    size = (f"{d['done_gb']:g} of {d['total_gb']:g} GB" if d.get("done_gb") is not None and d.get("total_gb") else
            f"{d['total_gb']:g} GB" if d.get("total_gb") else "")
    share = f" ({d['pct']} %)" if d.get("pct") is not None else ""
    text = (f"{g['model']} on {who}: the first launch is downloading {d.get('what') or 'the set'}"
            + (f": {size}" if size else "") + share + " -- Strata's own download, not a timeout: the server starts when "
            "it ends (halo local log " + str(who) + " shows it)")
    return [_tag(finding("strata-download", g, "info", text, events=dl[-4:],
                         numbers={"what": d.get("what"), "done_gb": d.get("done_gb"), "total_gb": d.get("total_gb"),
                                  "pct": d.get("pct")}), g)]


def strata_rules(ctx: dict) -> list:
    out: list = []
    for g in ctx.get("groups") or []:
        if g.get("runtime") == "strata":
            out += disk_bound(g, ctx) + slots(g, ctx) + download(g, ctx)
    return out
