"""halo_harness.ollama_steward.chat_tools -- what the steward's chat can do (Halo 3.3.7.0 R5; ollama_steward/chat.py runs
them, one at a time, as the model asks).

    TOOLS = {name: (args help, what it does)}       the list the model reads in its guide
    run(env, name, args) -> {ok, text, button?, landed?}
    env = {state, ctx (rules.gather), found (the findings, a paired host's folded in), hosts, mode}

Reads: card, ledger, events, servers (3.3.8.0 R2: the local servers), profiles, speed, knowledge, findings, bundles, advice, busy (why the card is busy:
idle.idle_since), refresh (what the off-hours refresh does tonight). Acts, within the duty steward's bounds -- a
Halo-side profile field (profiles.CHANGEABLE), one change per answer, citing a finding -- `propose` lands through
agent_proposals (its bounds, steward.check, the mode; a host-served model through the host's guarded path). `apply`
takes an adviser suggestion by its id: point lands (the role write); retire and add, like `bench` and `battery`, become
the one button that does that one thing (Studio's route; the CLI prints the command) with what it costs said first.
"""

from __future__ import annotations

TOOLS = {
    "card": ("{host?}", "the host's hardware card: its GPUs, what holds memory, the server's settings"),
    "ledger": ("{host?, model?}", "the calls per model: count, tok/s, trims, cut replies, errors, machines"),
    "events": ("{host?}", "the newest server events"),
    "servers": ("{name?}", "the local servers (llama-server, LM Studio, mlx): runtime, model, window, log status"),
    "profiles": ("{host?}", "the Halo-side profiles and the battery profiles (tools, vision, where it sits)"),
    "speed": ("{host?, model?}", "the speed cards: tok/s and first-token time per window, the cold load"),
    "knowledge": ("{kind}", "what an alert kind or a topic means, from the steward's knowledge"),
    "findings": ("{host?}", "what the rules find here and on the paired hosts, each with its id"),
    "bundles": ("{}", "each bundle's verdict and what is reserved"),
    "advice": ("{}", "the roster adviser's suggestions, each with its id (adv-...)"),
    "busy": ("{host?}", "why the card is busy (or since when it is idle), the clients that are not a halo"),
    "refresh": ("{}", "what the off-hours refresh does tonight, and its last run"),
    "propose": ("{key, field, to, why, finding}", "one Halo-side profile change citing a finding's id"),
    "apply": ("{id}", "an adviser suggestion the user named: point lands; retire and add become a button"),
    "bench": ("{model, host?, quick?}", "a benchmark of a model: becomes a button (it runs the model for minutes)"),
    "battery": ("{model, host?}", "the capability battery on a model: becomes a button"),
}
MAX_LINES = 14


def _host(env: dict, args: dict):
    name = str(args.get("host") or "").strip()
    hs = env.get("hosts") or []
    return next((h for h in hs if h.name.lower() == name.lower()), None) if name else (hs[0] if hs else None)


def _say(lines: list, empty: str) -> dict:
    lines = [str(x) for x in lines if str(x).strip()][:MAX_LINES]
    return {"ok": True, "text": "\n".join(lines) or empty}


def _card(env, a):
    from halo_harness.ollama_steward.hardware import format_card
    h = _host(env, a)
    if h is None:
        return {"ok": False, "text": "no Ollama host is configured here"}
    card = (env["ctx"].get("cards") or {}).get(h.name)
    if not card:
        from halo_harness.local_sched.facts import card as card_of  # the cached view, the test flag's guard
        card = card_of(h)
    from halo_harness.local_sched.reserve import budget_line
    return _say((format_card(card, host_name=h.name) if card else [f"'{h.name}': no card read"]) +
                [budget_line(h, state_dir=env["state"])], "no card")


def _ledger(env, a):
    from halo_harness.ollama_steward.traffic import format_row, rollup
    rows = [r for r in rollup(env["ctx"].get("lines") or [], env.get("hosts") or [])
            if (not a.get("host") or r["host"] == a["host"]) and (not a.get("model") or r.get("model") == a["model"])]
    return _say([f"{r['host']} {format_row(r).strip()}" for r in rows], "no calls in the ledger's window")


def _events(env, a):
    from halo_harness.ollama_steward.server_events import format_event
    evs = [e for e in env["ctx"].get("events") or [] if not a.get("host") or e.get("host") == a["host"]][-10:]
    return _say([format_event(e) for e in evs], "no server events")


def _servers(env, a):
    """3.3.8.0 R2: the local servers beside the hosts: each one's line, its newest events, what its log never says."""
    from halo_harness.ollama_steward.hardware_servers import lines, rows
    from halo_harness.ollama_steward.server_events import format_event
    from halo_harness.ollama_steward.server_rules_hf import not_asked
    want = str(a.get("name") or a.get("host") or "").lower()
    out = []
    for r in rows(env["state"], env["ctx"].get("servers")):
        if want and r["name"].lower() != want:
            continue
        out += lines([r]) + [f"  its log never says: {', '.join(not_asked(r.get('runtime'))) or 'nothing it is asked'}"]
        out += [f"  {format_event(e)}" for e in env["ctx"].get("events") or [] if e.get("host") == r["name"]][-3:]
    return _say(out, "no local server on this machine")


def _profiles(env, a):
    from halo_harness.ollama_steward.profiles import all_profiles
    from halo_harness.providers.ollama_capability import all_profiles as battery
    host = str(a.get("host") or "").lower()
    out = [f"profile {k}: " + ", ".join(f"{f} {v}" for f, v in p.items() if f not in ("note", "at", "by"))
           for k, p in sorted(all_profiles().items()) if not host or k.lower().startswith(host + "|")]
    out += [f"battery {p.get('model')}@{p.get('host')}: tools {p.get('tools')}, vision {p.get('vision')}, "
            f"{p.get('sits') or ''}".rstrip(", ") for p in battery(env["state"]) or []
            if not host or str(p.get("host") or "").lower() == host]
    return _say(out, "no profiles yet")


def _speed(env, a):
    from halo_harness.providers.local_bench_runs import all_cards, lines
    out = []
    for c in all_cards(env["state"], a.get("host") or None):
        if not a.get("model") or c.get("model") == a["model"]:
            out += [f"{c.get('model')}@{c.get('host')}: {x}" for x in lines(c)[:3]]
    return _say(out, "no speed cards yet (halo local bench <model>)")


def _knowledge(env, a):
    from halo_harness.ollama_steward.explain import explain
    got, _ok = explain(str(a.get("kind") or a.get("topic") or "").strip() or None)
    return _say(got, "nothing in the knowledge for that")


def _findings(env, a):
    from halo_harness.ollama_steward.rules import format_finding
    found = [f for f in env.get("found") or [] if not a.get("host") or f.get("host") == a["host"]]
    return _say([x for f in found for x in format_finding(f)[:2]], "no findings: the calls and the server's lines look right")


def _bundles(env, a):
    from halo_harness.local_sched.bundle_fit import verdict
    from halo_harness.local_sched.reserve import all_lines
    from halo_harness.packs.bundles import listing
    out = [f"{e['id']}: {verdict(e['block'], None, state_dir=env['state'])['says']}" for e in listing(state_dir=env["state"])
           if e["block"]]
    return _say([x["host"] + ": " + x["line"] for x in all_lines(env["state"])] + out, "no bundles")


def _advice(env, a):
    from halo_harness.models_library.advise import advise
    got = advise(env["state"])
    env["advice"] = got["suggestions"]
    return _say([f"[{s['id']}] {s['line']}" for s in got["suggestions"]] or [got["head"]], got["head"])


def _busy(env, a):
    from halo_harness.ollama_steward.idle import idle_since
    h = _host(env, a)
    if h is None:
        return {"ok": False, "text": "no Ollama host is configured here"}
    got = idle_since(env["state"], h)
    return _say([got.get("line") or "", got.get("foreign_line") or ""], f"{h.name}: nothing says it is busy")


def _refresh(env, a):
    from halo_harness.host.refresh import status
    st = status(env["state"])
    return _say([st["line"], st["last_line"]], "no refresh planned")


def run(env: dict, name: str, args) -> dict:
    from halo_harness.ollama_steward import chat_acts
    args = args if isinstance(args, dict) else {}
    reads = {"card": _card, "ledger": _ledger, "events": _events, "servers": _servers, "profiles": _profiles, "speed": _speed,
             "knowledge": _knowledge, "findings": _findings, "bundles": _bundles, "advice": _advice, "busy": _busy,
             "refresh": _refresh}
    acts = {"propose": chat_acts.propose, "apply": chat_acts.apply, "bench": chat_acts.bench, "battery": chat_acts.battery}
    fn = reads.get(name) or acts.get(name)
    if fn is None:
        return {"ok": False, "text": f"no tool {name!r}; the tools: {', '.join(TOOLS)}"}
    try:
        return fn(env, args)
    except Exception as e:  # one tool that cannot read its source never ends the conversation
        return {"ok": False, "text": f"{name}: {type(e).__name__}: {str(e)[:200]}"}
