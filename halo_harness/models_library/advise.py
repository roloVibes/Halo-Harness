"""halo_harness.models_library.advise -- the roster adviser (Halo 3.3.7.0 R4; plans/local-model-fit-brief.md Part J:
"Halo reviews the installed roster against the roles, the host budget and the capability profiles, then tells the user
what is missing, what overlaps and what to add or retire -- in plain language, with the numbers, and with a one-click
add"). Deterministic: no model is asked anything.

    inputs(state_dir, host=None, lineup=None) -> {hosts [{name, budget_gb, version, rows}], profiles, lanes, gaps,
                                                  preview, crashes}
        the installed models per host (the Ollama panel's cached catalog), the battery profiles, the host budget
        (fit.card_budget), the lineup's lanes and its roles with no model (role_gaps.gaps), the swap preview
        (local_sched/preview.preview: pivots, swaps), the crash fingerprints (the host log)
    advise(state_dir, host=None, *, inp=None, lineup=None) -> {suggestions, lines, fingerprint, at, kinds}
        the four kinds (advise_rules.py), ranked by value per gigabyte (then value), one line each (advise_lines.say);
        3.3.8.0 R4: a fifth, `placement` (local_sched/place_advice.py: a lane's placement score and loading tax against
        the cheaper candidate across the fleet and the pool)
    fingerprint(inp) -> the roster (every tag's digest), each host's Ollama version and the hosts: what re-runs it
    due(state_dir, inp=None) -> (due, why)      the roster, the Ollama version or the host changed since the last run
    remember(state_dir, result)                 <state>/ollama/advise.json (the last run, for `due`)
Nothing downloads, deletes or retires here: each suggestion names the one button (or command) that does its one thing.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Optional

FILE = "advise.json"


def _hosts(host: Optional[str]) -> list:
    from halo_harness.providers.ollama import resolve_ollama_hosts
    from halo_harness.providers.ollama_guard import skip_default
    try:
        hs = [h for h in resolve_ollama_hosts() if not skip_default(h)]
    except Exception:
        hs = []
    return [h for h in hs if not host or h.name.lower() == host.lower()]


def inputs(state_dir, host: Optional[str] = None, lineup: Optional[str] = None) -> dict:
    from halo_harness.ollama_steward.fit import card_budget
    from halo_harness.providers.ollama_capability import all_profiles
    from halo_harness.studio import ollama_hosts_view as V
    hosts = []
    for h in _hosts(host):
        card = V.card_of(h) or {}
        b = card_budget(card, h.name) if card else {}
        hosts.append({"name": h.name, "budget_gb": round(b["budget"] / 1e9, 1) if b.get("budget") else None,
                      "version": (card.get("server") or {}).get("version"),
                      "rows": [r for r in (V.catalog_of(h) or {}).get("models") or [] if isinstance(r, dict)]})
    lanes, gaps, pv = [], [], None
    try:
        from halo_harness.local_sched.preview import lanes_for, preview
        from halo_harness.teams_runtime import active_team_name
        name = lineup or active_team_name(None)
        if name:
            lanes = lanes_for(name, state_dir=state_dir)[0]
            pv = preview(name, state_dir=state_dir)
            from halo_harness.models_library.role_gaps import gaps as role_gaps
            from halo_harness.teams_yaml import resolve_role_table, resolve_team_template
            t = resolve_team_template(name, state_dir=state_dir)
            if t:
                table, _n = resolve_role_table(t, state_dir=state_dir)
                gaps = role_gaps(table, state_dir, roles=[e.get("as") or e.get("role") for e in t.get("agents") or []
                                                           if isinstance(e, dict)])
    except Exception:
        pass
    from halo_harness.ollama_steward.fingerprints import read as fps
    crashes = [f for h in hosts for f in fps(state_dir, host=h["name"]) if not f.get("from")] if state_dir else []
    return {"hosts": hosts, "profiles": all_profiles(state_dir) if state_dir else [], "lanes": lanes, "gaps": gaps,
            "preview": pv, "crashes": crashes}


def fingerprint(inp: dict) -> str:
    parts = sorted(f"{h['name']}|{h.get('version')}|" + ",".join(sorted(f"{r.get('model') or r.get('name')}@"
                                                                         f"{r.get('digest')}" for r in h.get("rows") or []))
                   for h in inp.get("hosts") or [])
    return hashlib.sha1("\n".join(parts).encode("utf-8")).hexdigest()[:12]


def advise(state_dir, host: Optional[str] = None, *, inp: Optional[dict] = None, lineup: Optional[str] = None) -> dict:
    from halo_harness.models_library import advise_rules as R
    from halo_harness.models_library.advise_lines import say
    inp = inp if inp is not None else inputs(state_dir, host, lineup)
    out = []
    inp.setdefault("state_dir", state_dir)  # 3.3.8.0 R4: the placement rule reads the fleet's cards and the pool
    for rule in (R.gap, R.overlap, R.mismatch, R.freshness, R.placement):
        try:
            out.extend(rule(inp))
        except Exception:  # one rule that cannot read its inputs never hides the others
            continue
    out.sort(key=lambda s: (-s["value_per_gb"], -s["value"], s["kind"], s["says"]))
    for i, s in enumerate(out, 1):
        s["id"] = f"adv-{hashlib.sha1((s['kind'] + s['says']).encode('utf-8')).hexdigest()[:8]}"
        s["rank"], s["line"] = i, say(s)
    kinds = {k: sum(1 for s in out if s["kind"] == k) for k in ("gap", "overlap", "mismatch", "freshness", "placement")}
    have = sum(len(h.get("rows") or []) for h in inp.get("hosts") or [])
    head = (f"roster: {have} model{'s' * (have != 1)} on {len(inp.get('hosts') or [])} host"
            f"{'s' * (len(inp.get('hosts') or []) != 1)}; " + (", ".join(f"{n} {k}" for k, n in kinds.items() if n)
                                                             or "nothing to add or retire"))
    return {"suggestions": out, "lines": [head] + [s["line"] for s in out], "fingerprint": fingerprint(inp),
            "at": time.time(), "kinds": kinds, "head": head,
            "placement": {"lines": (inp.get("placement") or {}).get("lines") or []}}  # 3.3.8.0 R4: the scores


def _path(state_dir) -> Path:
    from halo_harness.ollama_steward.ledger import ledger_dir
    return ledger_dir(state_dir) / FILE


def remember(state_dir, result: dict) -> None:
    try:
        p = _path(state_dir)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({k: result.get(k) for k in ("fingerprint", "at", "lines", "kinds")}), encoding="utf-8")
    except OSError:
        pass


def last(state_dir) -> Optional[dict]:
    try:
        got = json.loads(_path(state_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return got if isinstance(got, dict) else None


def due(state_dir, inp: Optional[dict] = None) -> "tuple[bool, str]":
    prev = last(state_dir)
    fp = fingerprint(inp if inp is not None else inputs(state_dir))
    if prev is None:
        return True, "never reviewed"
    if prev.get("fingerprint") != fp:
        return True, "the roster, an Ollama version or the hosts changed since the last review"
    return False, "nothing changed since the last review"
