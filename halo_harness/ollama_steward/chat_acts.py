"""halo_harness.ollama_steward.chat_acts -- the chat's acting tools (Halo 3.3.7.0 R5; chat_tools.run calls them).

    propose(env, {key, field, to, why, finding})   one Halo-side profile change per answer, citing a finding the rules
        made (env["found"]): agent_proposals.land -- the field is one of profiles.CHANGEABLE, the value within the
        measured cap and the card's fit, steward.check's ten minutes per model, the mode (auto / review / off); a model a
        paired halo host serves lands through the host (its guards and its verify). Kept: the user asked for it.
    apply(env, {id})      an adviser suggestion by its id (adv-...): point lands now (the role write, dead_tag.point);
        retire and add become the one button that does it, what it frees or costs said first
    bench(env, {model, host?, quick?}) / battery(env, {model, host?})   the one button (Studio's bench / probe route,
        through the halo host when one serves the card); the CLI prints the command
A button is {verb, label, route, body, cli}: nothing runs until it is pressed.
"""

from __future__ import annotations


def _host_name(env: dict, args: dict) -> str:
    name = str(args.get("host") or "").strip()
    if name:
        return name
    hs = env.get("hosts") or []
    return hs[0].name if hs else ""


def propose(env: dict, a: dict) -> dict:
    from halo_harness.ollama_steward.agent_proposals import land
    from halo_harness.ollama_steward.profiles import CHANGEABLE
    if env.get("landed"):
        return {"ok": False, "text": "one change at a time: this answer already made one; ask again for the next"}
    field, finding = str(a.get("field") or ""), str(a.get("finding") or "")
    if field not in CHANGEABLE:
        return {"ok": False, "text": f"{field or '(no field)'} is not a Halo-side profile field ({', '.join(CHANGEABLE)})"}
    ids = [f["id"] for f in env.get("found") or []]
    if finding not in ids:
        return {"ok": False, "text": "a change names the finding it acts on: " + (", ".join(ids[:8]) if ids else
                                                                                "there is no finding now")}
    said: list = []
    out = land(env["state"], [{k: a.get(k) for k in ("key", "field", "to", "why")}], env["ctx"],
               mode_name=env.get("mode") or "auto", say=said.append, scope="keep")
    o = out[0] if out else {"landed": False, "kind": "dropped", "reason": "nothing to land"}
    env["landed"] = bool(o.get("landed"))
    text = "; ".join(said) or (f"{o.get('kind')}: {o.get('reason') or ''}").strip()
    return {"ok": o.get("kind") in ("apply", "proposal", "host-apply", "host-pending") or bool(o.get("landed")),
            "text": text, "landed": bool(o.get("landed")), "outcome": o}


def _suggestion(env: dict, sid: str):
    rows = env.get("advice")
    if rows is None:
        from halo_harness.models_library.advise import advise
        rows = env["advice"] = advise(env["state"])["suggestions"]
    return next((s for s in rows if s.get("id") == sid), None)


def apply(env: dict, a: dict) -> dict:
    sid = str(a.get("id") or "").strip()
    s = _suggestion(env, sid)
    if s is None:
        return {"ok": False, "text": f"no adviser suggestion {sid or '(no id)'} now (the advice tool lists them)"}
    act, host = s.get("action") or {}, s.get("host") or _host_name(env, a)
    if act.get("verb") == "point":
        from halo_harness.ollama_steward.dead_tag import point
        got = point(str(act.get("role") or ""), str(act.get("model") or ""))
        env["landed"] = got["ok"]
        return {"ok": got["ok"], "text": got["line"], "landed": got["ok"]}
    if act.get("verb") == "retire":
        from halo_harness.studio.local_uses import uses_of
        model = str(act.get("model") or "")
        uses = uses_of(f"ol:{model}@{host}", state_dir=env["state"])
        return {"ok": True, "text": f"{s['line']}; uses: {uses.get('line') or 'none'}; it waits for your Retire",
                "button": {"verb": "retire", "label": f"Retire {model} from {host}", "route": f"local/host/{host}/retire",
                           "body": {"name": model, "why": str(s.get("says") or "")[:120]}, "cli": act.get("cli") or ""}}
    if act.get("verb") == "add":
        c = s.get("cost") or {}
        model = str(act.get("model") or "")
        size = f"{c.get('download_gb') or '?'} GB, ~{c.get('minutes') or '?'} min"
        return {"ok": True, "text": f"{s['line']}; it waits for your Download and verify ({size})",
                "button": {"verb": "add", "label": f"Download and verify {model} ({size})", "route": "local/library/verify",
                           "body": {"host": host, "name": model, **({"role": act["role"]} if act.get("role") else {})},
                           "cli": act.get("cli") or f"halo models pull {model} --host {host}"}}
    return {"ok": True, "text": s.get("line") or "", "landed": False}


def bench(env: dict, a: dict) -> dict:
    model, host = str(a.get("model") or "").strip(), _host_name(env, a)
    if not model or not host:
        return {"ok": False, "text": "bench takes {model, host?}"}
    quick = a.get("quick") is True
    return {"ok": True, "text": f"a {'quick ' if quick else ''}bench of {model} on {host} runs the model for a few minutes "
                                "(local: the card's time; no tokens leave the LAN); it waits for your Bench",
            "button": {"verb": "bench", "label": f"Bench {model} on {host}", "route": f"local/host/{host}/bench",
                       "body": {"model": model, "quick": quick},
                       "cli": f"halo local bench --host {host} --model {model}" + (" --quick" if quick else "")}}


def battery(env: dict, a: dict) -> dict:
    model, host = str(a.get("model") or "").strip(), _host_name(env, a)
    if not model or not host:
        return {"ok": False, "text": "battery takes {model, host?}"}
    return {"ok": True, "text": f"the capability battery on {model} on {host} asks it a few short probes (local: about a "
                                "minute); it waits for your Probe",
            "button": {"verb": "battery", "label": f"Probe {model} on {host}", "route": f"local/host/{host}/probe",
                       "body": {"model": model}, "cli": f"halo models probe {model} --host {host}"}}
