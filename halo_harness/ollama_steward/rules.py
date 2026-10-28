"""halo_harness.ollama_steward.rules -- Halo 3.3.4.0 R3: the steward
judges. Each rule reads a window of the ledger (`ledger.read_calls`, the
last 24 h by default; on a hub every member's lines too), joined with the
server's events (`server_events.read_events`), the hardware card and the
learned caps, per host and model, and says what is wrong.

A finding (the shape R4's note-writer and R5's panel read):

    {id, rule, host, model, key ("<host>|<model>"), severity ("info" |
     "warn" | "error"), finding (one line), evidence {calls: [the ledger
     lines' `at`], events: ["<at> <kind>"], numbers: {...}},
     proposal {field, from, to, why} | None   -- a profile change
     server_hint {env, line, cost} | None     -- only ever recommended}

`id` is stable for the same rule, host, model and proposal, so `halo
ollama steward apply <id>` names what `findings` printed. The rules live
in rules_window.py (a, b, h), rules_reply.py (c, d, e), rules_host.py
(f, g) and rules_card.py (3.3.5.0 R0b: `called-wrong`); knowledge/symptoms.md
is their spec.
"""

from __future__ import annotations

import hashlib
import time
from collections import Counter
from typing import Callable, Optional

SINCE = "24h"
SEVERITY_ORDER = {"error": 0, "warn": 1, "info": 2}


def proposal(field: str, frm, to, why: str) -> dict:
    return {"field": field, "from": frm, "to": to, "why": why}


def hint(env: Optional[str], line: str, cost: str) -> dict:
    return {"env": env, "line": line, "cost": cost}


def finding(rule: str, group: dict, severity: str, text: str, *, calls=(), events=(), numbers=None,
            proposal=None, server_hint=None, **extra) -> dict:
    to = (proposal or {}).get("to")
    raw = f"{rule}|{group['key']}|{(proposal or {}).get('field')}|{to}"
    out = {"id": f"{rule}-{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:6]}", "rule": rule,
           "host": group["host"], "model": group["model"], "key": group["key"], "severity": severity,
           "finding": text, "evidence": {"calls": [c.get("at") for c in calls][:8],
                                         "events": [f"{e.get('at')} {e.get('kind')}" for e in events][:8],
                                         "numbers": numbers or {}},
           "proposal": proposal, "server_hint": server_hint}
    out.update(extra)
    return out


def _model_eq(a, b) -> bool:
    from halo_harness.ollama_steward.profiles import short_model
    return short_model(a) == short_model(b) or short_model(a).split(":")[0] == str(b or "")


def window_stats(lines: list) -> dict:
    """The numbers every rule reads, over the native-dialect lines (the OpenAI
    dialect carries no window to compare with)."""
    from halo_harness.ollama_steward.traffic import RELOAD_MS, percentile
    lines = [x for x in lines if x.get("kind") != "calibrate"]  # a calibration load is cut at num_predict 1 by design
    native = [x for x in lines if x.get("dialect") in (None, "ollama")]
    ok = [x for x in native if x.get("status") == 200 and isinstance(x.get("prompt_eval_count"), int)]
    windows = Counter(x.get("num_ctx_sent") for x in native if isinstance(x.get("num_ctx_sent"), int))
    return {"calls": len(lines), "native": native, "ok": ok,
            "window": windows.most_common(1)[0][0] if windows else None, "windows": windows,
            "p50": percentile([x["prompt_eval_count"] for x in ok], 50),
            "p95": percentile([x["prompt_eval_count"] for x in ok], 95),
            "max_prompt": max([x["prompt_eval_count"] for x in ok], default=None),
            "trims": [x for x in native if x.get("trimmed")],
            "cuts": [x for x in lines if x.get("done_reason") == "length"],
            "reloads": [x for x in lines if isinstance(x.get("load_ms"), (int, float)) and x["load_ms"] > RELOAD_MS],
            "eval_p50": percentile([x.get("eval_tok_s") for x in lines], 50)}


def _cap(state_dir, group: dict, ctx: dict) -> "tuple[Optional[int], str]":
    """The most the window may be raised to: the learned cap, else what the
    card fits (every layer on), else the host's max_ctx."""
    host = group.get("host_obj")
    if host is None:
        return None, "unknown"
    try:
        from halo_harness.providers.ollama_calibrate import lookup_learned_cap
        cap = lookup_learned_cap(state_dir, host_url=host.url, model=group["model"])
    except Exception:
        cap = None
    if cap:
        return cap, "learned cap"
    fit = card_fit(group, ctx)
    if fit:
        return fit, "the card"
    return (host.max_ctx, "max_ctx") if getattr(host, "max_ctx", None) else (None, "unknown")


def card_fit(group: dict, ctx: dict) -> Optional[int]:
    from halo_harness.ollama_steward.fit import model_window_on_card
    card, row = ctx["cards"].get(group["host"]), (ctx["catalogs"].get(group["host"]) or {}).get(group["model"])
    if not card or not row:
        return None
    return model_window_on_card(card, row, alone=True)


def gather(state_dir, *, since=SINCE, host: Optional[str] = None, cards: Optional[dict] = None,
           catalogs: Optional[dict] = None, card_reader: Optional[Callable] = None,
           catalog_reader: Optional[Callable] = None, hosts: Optional[list] = None, now: Optional[float] = None) -> dict:
    """Everything the rules read. `cards` / `catalogs` ({host name: card} /
    {host name: {model: catalog row}}) or the readers that fetch them are
    the seams tests use; without either, the rules that need them say less."""
    from halo_harness.ollama_steward.ledger import read_calls
    from halo_harness.ollama_steward.profiles import all_profiles, key_for
    from halo_harness.ollama_steward.server_events import read_events
    from halo_harness.ollama_steward.traffic import canonical_host
    if hosts is None:
        from halo_harness.providers.ollama import resolve_ollama_hosts
        hosts = resolve_ollama_hosts()
    lines, events = read_calls(state_dir, since=since), read_events(state_dir, since=since)
    groups: dict = {}
    for line in lines:
        name, h = canonical_host(line.get("host") or {}, hosts)
        if host and name.lower() != host.lower():
            continue
        model = str(line.get("model") or "?")
        g = groups.setdefault((name, model), {"host": name, "host_obj": h, "model": model,
                                              "key": key_for(name, model), "lines": [], "events": []})
        g["lines"].append(line)
    for ev in events:
        mine = [g for g in groups.values()
                if str(ev.get("host") or "").lower() == g["host"].lower() and _model_eq(g["model"], ev.get("model"))]
        if not mine and ev.get("model") and ev.get("host") and (not host or str(ev["host"]).lower() == host.lower()):
            # a model the server log names with no ledger line (calls from clients that are not halos, or
            # before 3.3.4.0): its events still count
            h = next((x for x in hosts if x.name.lower() == str(ev["host"]).lower()), None)
            name, model = (h.name if h else str(ev["host"])), str(ev["model"])
            mine = [groups.setdefault((name, model), {"host": name, "host_obj": h, "model": model,
                                                      "key": key_for(name, model), "lines": [], "events": []})]
        for g in mine:
            g["events"].append(ev)
    cards, catalogs = dict(cards or {}), dict(catalogs or {})
    for g in groups.values():
        if g["host_obj"] is None:
            continue
        if g["host"] not in cards and card_reader is not None:
            try:
                cards[g["host"]] = card_reader(g["host_obj"])
            except Exception:
                cards[g["host"]] = None
        if g["host"] not in catalogs and catalog_reader is not None:
            try:
                rows = (catalog_reader(g["host_obj"]) or {}).get("models") or []
                catalogs[g["host"]] = {str(r.get("model") or r.get("name")): r for r in rows if isinstance(r, dict)}
            except Exception:
                catalogs[g["host"]] = {}
    profiles = all_profiles()
    ctx = {"state_dir": state_dir, "lines": lines, "events": events, "hosts": hosts, "cards": cards,
           "catalogs": catalogs, "profiles": profiles, "now": now or time.time(), "groups": list(groups.values())}
    for g in ctx["groups"]:
        g["stats"] = window_stats(g["lines"])
        g["profile"] = profiles.get(g["key"]) or {}
        g["cap"], g["cap_source"] = _cap(state_dir, g, ctx)
    return ctx


def run_rules(ctx: dict) -> list:
    """Every rule over every group; one proposal per profile field (the most severe finding keeps it)."""
    from halo_harness.ollama_steward import rules_card, rules_host, rules_reply, rules_window
    out: list = []
    for g in ctx["groups"]:
        for rule in rules_window.RULES + rules_reply.RULES + rules_card.RULES:  # 3.3.5.0 R0b: called-wrong
            out.extend(rule(g, ctx) or [])
    out.extend(rules_host.host_rules(ctx))
    from halo_harness.ollama_steward.steward import dismissed  # 3.3.4.0 R5: Studio's Dismiss, quiet for 24 hours
    quiet = dismissed(ctx["state_dir"], now=ctx.get("now")) if ctx.get("state_dir") else set()
    out = [f for f in out if f["id"] not in quiet]
    out.sort(key=lambda f: SEVERITY_ORDER.get(f["severity"], 3))
    seen = set()
    for f in out:
        p = f.get("proposal")
        if p is None:
            continue
        slot = (f["key"], p["field"])
        if slot in seen:
            f["proposal"] = None
            f["finding"] += " (the change is proposed by another finding)"
        seen.add(slot)
    return out


def findings(state_dir, **kw) -> list:
    return run_rules(gather(state_dir, **kw))


def format_finding(f: dict) -> "list[str]":
    out = [f"[{f['id']}] {f['severity']} {f['host']} {f['model']}: {f['finding']}"]
    p = f.get("proposal")
    if p:
        out.append(f"    change: {p['field']} {p['from']} -> {p['to']} ({p['why']})")
    s = f.get("server_hint")
    if s:
        out.append(f"    on the server: {s['line']} (costs: {s['cost']})")
    nums = ", ".join(f"{k} {v}" for k, v in (f["evidence"].get("numbers") or {}).items())
    if nums:
        out.append(f"    evidence: {nums}")
    return out
