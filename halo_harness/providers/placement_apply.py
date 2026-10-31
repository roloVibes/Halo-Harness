"""halo_harness.providers.placement_apply -- Halo 3.3.6.0 R1: the placement
rules that change how Halo calls a model (plans/local-model-fit-brief.md
E3, G1's dialect record), applied after a battery run and before a call.

    apply_profile(profile, state_dir) -> [lines]
        thinking -> the steward profile's `num_predict` (ollama.profiles["<host>|<model>"])
        raised to at least REASONING_RESERVE and the window class's default; a reserve
        you set (`by: "user"`) stays
    reserve_for(profile) -> the reply reserve a thinking model needs at its window
    prompt_card(session) -> {system_role, tools, from, probed} | {} for agent/prompt_wire.py
        (`session._prompt_card`: a weak system role puts the instruction in the user turn)
    lineup_pivots(role_table, state_dir) -> [{models, host, line}]
        two models named by one lineup that cannot co-reside on one card: a pivot schedule
"""

from __future__ import annotations

from typing import Optional

REASONING_RESERVE = 300
PIVOT_LINE = ("{a} and {b} cannot co-reside on {host}: every switch is a 20-55 s pivot (a pivot schedule); "
              "make one resident and pivot explicitly")


def reserve_for(profile: dict) -> int:
    from halo_harness.agent.model_switch import class_reserve
    used = ((profile or {}).get("window") or {}).get("used")
    return max(REASONING_RESERVE, class_reserve(used if isinstance(used, int) else None))


def apply_profile(profile: dict, state_dir=None) -> list:
    """See the module docstring. Never raises."""
    out: list = []
    if not isinstance(profile, dict) or profile.get("reasoning") != "thinking":
        return out
    try:
        from halo_harness.ollama_steward.profiles import all_profiles, key_for, set_field
        key = key_for(profile.get("host"), profile.get("model"))
        mine = all_profiles().get(key) or {}
        want = reserve_for(profile)
        have = mine.get("num_predict")
        if mine.get("by") == "user" or (isinstance(have, int) and have >= want):
            return out
        set_field(key, "num_predict", want, by="steward",
                  note=f"answers in thinking (the battery): a reply reserve of {want:,} so content is not empty")
        out.append(f"{profile.get('model')} answers in thinking: its reply reserve on {profile.get('host')} is now "
                   f"{want:,} tokens (ollama.profiles)")
    except Exception:
        pass
    return out


def prompt_card(session) -> dict:
    """The dialect facts a call to this session's model reads (cached on the session per ref and turn). 3.3.6.0 R4:
    the dialect record (providers/dialect.py) decides the placement and a tools_max of 0 (`from: "dialect"` when no
    probe stands behind it)."""
    ref = getattr(session, "model_ref", None)
    raw = getattr(ref, "raw", None)
    if getattr(ref, "provider", "") != "ollama":
        return {}
    key = (raw, getattr(session, "turn_count", None))
    hit = getattr(session, "_placement_card", None)
    if isinstance(hit, tuple) and hit[0] == key:
        return hit[1]
    card: dict = {}
    try:
        from halo_harness.providers.battery_profile import date_of
        from halo_harness.providers.placement import profile_for_ref
        p = profile_for_ref(ref, getattr(session, "state_dir", None))
        if p:
            card = {"system_role": "weak" if p.get("system_role") == "weak" else "ok",
                    "tools": "none" if p.get("tools") == "no" else "probed", "from": "probe", "probed": date_of(p),
                    "output": p.get("output"), "identifiers": p.get("identifiers"), "reasoning": p.get("reasoning")}
        from halo_harness.providers.dialect_apply import record_for
        rec = record_for(session)
        if rec:
            frm = rec.get("from") or {}
            if frm.get("instruction_placement") in ("user", "ledger", "hub") or (card and rec.get("instruction_placement")):
                card = {**card, "system_role": "weak" if rec["instruction_placement"] == "user-turn" else "ok",
                        "from": card.get("from") or "dialect", "probed": card.get("probed") or "your dialect record"}
            if rec.get("tools_max") == 0:
                card = {**card, "tools": "none", "from": card.get("from") or "dialect"}
    except Exception:
        card = card or {}
    session._placement_card = (key, card)
    return card


def _host_of(raw: str) -> "tuple[str, Optional[str]]":
    from halo_harness.providers.model_card_purpose import parse_ref
    r = parse_ref(raw)
    return r.model, r.host


def lineup_pivots(role_table: dict, state_dir) -> list:
    """See the module docstring. Only `ol:` models with a profile that says where they sit are judged."""
    from halo_harness.providers.ollama import ollama_names_match, resolve_ollama_host
    from halo_harness.providers.placement import profile_for_ref
    from halo_harness.roles import role_value_parts
    if state_dir is None:
        from halo_harness.config.paths import bridge_home
        state_dir = bridge_home()
    seen: dict = {}
    for _role, value in sorted((role_table or {}).items()):
        model, _e = role_value_parts(value)
        if isinstance(model, str) and model.startswith("ol:"):
            seen.setdefault(model, None)
    refs = list(seen)
    out, done = [], set()
    for i, a in enumerate(refs):
        for b in refs[i + 1:]:
            (ma, ha), (mb, hb) = _host_of(a), _host_of(b)
            host_a = ha or getattr(resolve_ollama_host(None), "name", None)
            host_b = hb or getattr(resolve_ollama_host(None), "name", None)
            if host_a != host_b or ollama_names_match(ma, mb):
                continue
            pa, pb = profile_for_ref(a, state_dir), profile_for_ref(b, state_dir)
            apart = False
            for p, other in ((pa, mb), (pb, ma)):
                res = (p or {}).get("resident") or {}
                if res.get("pivot_only") is None:
                    continue
                if not any(ollama_names_match(n, other) for n in res.get("co_resides_with") or []):
                    apart = True
            if apart and (a, b) not in done:
                done.add((a, b))
                out.append({"models": [a, b], "host": host_a, "line": PIVOT_LINE.format(a=a, b=b, host=host_a)})
    return out
