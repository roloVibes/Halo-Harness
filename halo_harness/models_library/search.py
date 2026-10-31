"""halo_harness.models_library.search -- Halo 3.3.6.0 R2: the capability-filtered search (plans/local-model-fit-
brief.md F2-F5): what the user needs and what the host has in, a short, ranked, explained list out.

    search(rows, *, host="", window=None, needs=None, fit=None, supply=None, intent="", q="", role="",
           host_card=None, state_dir=None, profiles=None, crashes=None, exclude_crashed=False) -> [row]

`rows` are browse.py's views (a LibraryRow with its card view, fit at the window, intent). `needs` {cap: floor}
keeps a row when the fact holds at that truth or stronger ("verified" > "declared" > "expected"; "any" also keeps
a verified-only fact that needs a probe); `fit` and `supply` are search_filters.py's. Each row gains

    facts      {cap: {value, truth, why}} (truths.py)       chips   the capability chips with their truth
    cost       {download_gb, download_eta_s, vram_at_window, cold_load_s, tok_s_expected, evicts, text} (search_cost.py)
    verdicts   {fits: {ok, word, why}, role_ready: {ok, why}}   only verified may make a role ready
    crashed    {line, at, signature} | None: the host's fingerprint (ollama_steward/fingerprints.py)
    gate_tier  3 verified, 2 declared, 1 expected, 0 needs a probe     why_this_rank   one line

The order: passes the gates (verified first, declared second, expected last) -> the intent's band -> fits at the
window -> measured speed -> download size -> licence; `exclude_crashed` greys a crashed row and puts it last.
"""

from __future__ import annotations

from typing import Optional

from halo_harness.models_library.truths import RANK, VERIFIED, at_least, chips, facts_for_row

FIT_RANK = {"fits": 4, "tight": 3, "unknown": 2, "spill": 1, "cloud": 0, "no": 0}
LIC_RANK = {"permissive": 0, "restricted": 1, "other": 2, "research": 3, "unknown": 4}


def norm_needs(needs) -> dict:
    """{cap: floor} from a dict, "tools=verified,coder" or ["tools", "coder=declared"] (a bare cap: expected)."""
    if isinstance(needs, dict):
        return {str(k): str(v or "expected") for k, v in needs.items() if k}
    items = needs.split(",") if isinstance(needs, str) else list(needs or [])
    out = {}
    for it in items:
        cap, _, floor = str(it).strip().partition("=")
        if cap.strip():
            out[cap.strip()] = floor.strip() or "expected"
    return out


def target_of(row: dict) -> str:
    line = str(row.get("pull_line") or "")
    return row.get("pull_target") or (line[len("ollama pull "):].strip() if line.startswith("ollama pull ") else "")


def profile_of_row(row: dict, profiles: list, host: str) -> Optional[dict]:
    from halo_harness.providers.ollama import ollama_names_match
    name = target_of(row) or row.get("name")
    if not name:
        return None
    return next((p for p in profiles or [] if ollama_names_match(p.get("model"), name)
                 and (not host or p.get("host") == host or p.get("from_host") == host)), None)


def gate(facts: dict, needs: dict) -> "tuple[bool, int, list]":
    """(passes, tier, the lines): each need held at its floor; the tier is the weakest truth among them."""
    tier, lines = (3 if facts else 0), []
    for cap, floor in needs.items():
        f = facts.get(cap)
        if not f:
            return False, 0, [f"{cap}: nothing says"]
        if f.get("probe"):
            if floor != "any":
                return False, 0, [f"{cap}: {f['why']}"]
            tier = 0
            lines.append(f"{cap} needs a probe")
            continue
        if f.get("value") is not True or not at_least(f.get("truth"), floor):
            return False, 0, [f"{cap}: {f.get('why')}"]
        tier = min(tier, RANK.get(f.get("truth"), 0))
        lines.append(f"{cap} {f.get('truth')}")
    return True, (tier if needs else 0), lines


def verdicts(row: dict, facts: dict, needs: dict, p: Optional[dict], role: str) -> dict:
    fit = row.get("fit") or {}
    level = fit.get("level") or "unknown"
    fits = {"ok": True if level in ("fits", "tight") else None if level == "unknown" else False,
            "word": {"fits": "yes", "tight": "yes (tight)", "spill": "no (spills to the CPU)", "no": "no"}.get(level, "?"),
            "why": fit.get("word") or fit.get("why") or ""}
    if not p:
        after = "halo models probe " + (target_of(row) or row.get("name") or "") if row.get("installed") else "download and verify"
        return {"fits": fits, "role_ready": {"ok": None, "why": f"not probed ({after})"}}
    from halo_harness.providers.battery_profile import date_of
    if role:
        from halo_harness.providers.placement import verdict
        v = verdict(p, role)
        if v["ok"] is False:
            return {"fits": fits, "role_ready": {"ok": False, "why": v["why"]}}
    for cap in needs:
        f = facts.get(cap) or {}
        if f.get("truth") == VERIFIED and f.get("value") is False:
            return {"fits": fits, "role_ready": {"ok": False, "why": f.get("why") or cap}}
    if facts.get("tools", {}).get("truth") == VERIFIED and facts["tools"]["value"] is False and not needs:
        return {"fits": fits, "role_ready": {"ok": False, "why": "no tool calls"}}
    return {"fits": fits, "role_ready": {"ok": True, "why": f"{p.get('sits') or 'probed'} (probed {date_of(p)})"}}


def crash_for(row: dict, crashes: list) -> Optional[dict]:
    from halo_harness.providers.ollama import ollama_names_match
    name = target_of(row) or row.get("name")
    hits = [c for c in crashes or [] if name and ollama_names_match(c.get("model"), name)]
    return max(hits, key=lambda c: str(c.get("at") or "")) if hits else None


def _why(r: dict, intent: str) -> str:
    bits = [", ".join(r["gate_lines"]) or "no capability asked"]
    v, c = r["verdicts"], r["cost"]
    nums = (r.get("fit") or {}).get("numbers") or {}
    free = (nums.get("budget") or 0) - (nums.get("total") or 0)
    if v["fits"]["ok"]:
        bits.append(f"fits at {int(nums.get('window') or 0):,} with {free / 2 ** 30:.1f} GB free" if nums else "fits")
    else:
        bits.append(f"fit: {v['fits']['word']}")
    if c.get("tok_s_expected"):
        bits.append(f"{c['tok_s_expected']:.0f} tok/s {'measured' if (r.get('profile') or {}).get('speed') else 'expected'}")
    if c.get("download_gb") is not None:
        bits.append("installed" if c.get("installed") else f"{c['download_gb']:g} GB")
    from halo_harness.models_library.search_filters import licence_class
    bits.append(f"licence {r.get('license') or 'unknown'} ({licence_class(r.get('license'))})")
    if r.get("crashed"):
        bits.insert(0, r["crashed"]["line"])
    return " · ".join(bits)


def search(rows: list, *, host: str = "", window: Optional[int] = None, needs=None, fit: Optional[dict] = None,
           supply: Optional[dict] = None, intent: str = "", q: str = "", role: str = "", host_card: Optional[dict] = None,
           state_dir=None, profiles: Optional[list] = None, crashes: Optional[list] = None,
           exclude_crashed: bool = False, keep_order: bool = False) -> list:
    from halo_harness.models_library.search_cost import cost, speeds
    from halo_harness.models_library.search_filters import keep_fit, keep_supply, licence_class, ollama_supports, runs_here
    needs = norm_needs(needs)
    exclude_crashed = exclude_crashed or bool((supply or {}).get("exclude_crashed"))  # the brief's supply key too
    if profiles is None:
        from halo_harness.providers.ollama_capability import all_profiles
        profiles = all_profiles(state_dir) if state_dir is not None else []
    if crashes is None:
        from halo_harness.ollama_steward.fingerprints import read
        crashes = read(state_dir, host=host or None) if state_dir is not None else []
    budget = 0
    if host_card:
        from halo_harness.ollama_steward.fit import card_budget
        budget = card_budget(host_card, host)["budget"]
    version = ((host_card or {}).get("server") or {}).get("version")
    sp = speeds(state_dir, host, profiles)
    ctx = {"host_card": host_card, "budget": budget, "window": window, "version": version}
    words = [w for w in str(q or "").lower().split() if w]
    out = []
    for r in rows:
        if words and not all(w in f"{r.get('name')} {r.get('description') or ''}".lower() for w in words):
            continue
        if intent and (r.get("intent") or {}).get(intent) is None:
            continue
        p = profile_of_row(r, profiles, host)
        card = r.get("card") or {}
        facts = facts_for_row({**r, "installed": bool(r.get("installed"))}, card, p)
        ok, tier, lines = gate(facts, needs)
        if not ok:
            continue
        rr = {**r, "facts": facts, "chips": chips(facts), "gate_tier": tier, "gate_lines": lines,
              "profile": {k: p.get(k) for k in ("sits", "speed", "window", "probed_at", "agentic_ready", "tools")} if p else None}
        rr["cost"] = cost(rr, r.get("fit"), p, host_card, budget=budget, speeds=sp)
        if not keep_fit(rr, fit or {}, ctx)[0] or not keep_supply(rr, supply or {}, ctx)[0]:
            continue
        crash = crash_for(r, crashes)
        rr["crashed"] = {k: crash.get(k) for k in ("line", "at", "signature", "count")} if crash else None
        rr["greyed"] = bool(crash) and exclude_crashed
        rr["verdicts"] = verdicts(rr, facts, needs, p, role)
        rr["runs"] = runs_here(r, host_card)[1]
        rr["supports"] = ollama_supports(r, version)[1]
        out.append(rr)

    def key(r):
        band = ((r.get("intent") or {}).get(intent) or 0) // 10 if intent else 0
        tok = ((r.get("profile") or {}).get("speed") or {}).get("tok_s") or 0
        size = r.get("size_bytes") if isinstance(r.get("size_bytes"), int) else 10 ** 13
        return (r["greyed"], -r["gate_tier"], -band, -FIT_RANK.get((r.get("fit") or {}).get("level") or "unknown", 2),
                -float(tok), size, LIC_RANK.get(licence_class(r.get("license")), 4), str(r.get("name")))
    if not keep_order:
        out.sort(key=key)
    for r in out:
        r["why_this_rank"] = _why(r, intent)
    return out
