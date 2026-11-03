"""halo_harness.local_sched.place_advice -- placement across the fleet, its scores and its loading tax, for the
adviser and `halo local place` (Halo 3.3.8.0 R4; docs/COMMANDS-local.md "advise: placement scores").

    candidates(state_dir=None) -> [host]   fleet-wide: every configured Ollama host, each paired halo host's served
        Ollama host this machine has no entry for (named by the host's own name for it), the pool, and (3.3.9.1) each
        FreeToken server (freetoken/route.ft_hosts), (3.3.9.2) each Strata server (strata/route.st_hosts), and
        (3.3.9.3) each TensorFold server (tensorfold/route.tf_hosts)
    tax(row) -> "25 s to load, evicts qwen3.8:27b"   what the chosen placement costs: the load seconds,
        the switch (what it evicts or pivots beside), the pool's decode penalty
    scored(lanes, *, state_dir=None, hosts=None, answers=None) -> {rows, line}   place.solve with each row's
        `options` (every candidate's score and why), its `tax` and `cheaper` {host, score, gain} when a candidate
        scores at least GAIN more than the lane's own host
    suggestions(inp, state_dir=None) -> [adviser suggestion of kind `placement`]   one per lane with a cheaper place;
        inp["placement"] = {rows, lines}: every lane's scores (score_line), what `halo local advise` and the Adviser
        block show under "placement scores"
    recheck(state_dir, *, now=None, lanes=None, hosts=None, answers=None, residency=None) -> [{id, key, say}]
        a far card's residency changed (a model loaded or unloaded on a paired host since the last look, its `GET
        residency`): place.solve runs again for the lanes that host carries; each lane whose best host moved is one
        stated line ("pc's card changed ...: worker would go to samus now (95 against 60) -- halo local place --apply
        moves it"). Nothing moves: --apply (the user's) writes host_for. At most every RECHECK_S.
Reads only.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

GAIN = 10.0
RECHECK_S = 60.0
FILE = "place-recheck.json"
_LAST: dict = {}


def candidates(state_dir=None) -> list:
    from halo_harness.local_pool.route import pool_host
    from halo_harness.providers.ollama import OllamaHost, resolve_ollama_hosts
    try:
        hosts = list(resolve_ollama_hosts())
    except Exception:
        hosts = []
    urls = {str(h.url).rstrip("/").lower() for h in hosts}
    names = {h.name.lower() for h in hosts}
    try:
        from halo_harness.fleet import store
        entries = [e for e in store.hosts() if e.get("state", "joined") == "joined"]
    except Exception:
        entries = []
    for e in entries:
        for r in e.get("serves") or []:
            if not isinstance(r, dict) or not r.get("addr") or not r.get("port"):
                continue
            url = f"http://{r['addr']}:{int(r['port'])}"
            if url.lower() in urls:
                continue
            name = str(r.get("name") or e.get("name") or url)
            name = name if name.lower() not in names else f"{e.get('name') or 'host'}/{name}"
            hosts.append(OllamaHost(name=name, url=url))
            urls.add(url.lower())
            names.add(name.lower())
    from halo_harness.freetoken.route import ft_hosts  # 3.3.9.1: this machine's and each paired host's FreeToken server
    from halo_harness.strata.route import st_hosts  # 3.3.9.2: and each Strata server
    from halo_harness.tensorfold.route import tf_hosts  # 3.3.9.3: and each TensorFold server
    return (hosts + [h for h in (pool_host(state_dir),) if h is not None] + ft_hosts(state_dir) + st_hosts(state_dir)
            + tf_hosts(state_dir))


def tax(r: dict) -> str:
    from halo_harness.local_sched.swap_cost import secs
    parts = []
    if r.get("warm"):
        parts.append("warm: no load")
    elif isinstance(r.get("load_s"), (int, float)):
        parts.append(f"{secs(r['load_s'])} to load")
    if r.get("installed") is False:
        parts.append("not pulled there")
    if r.get("evicts"):
        parts.append(f"evicts {', '.join(r['evicts'])}")
    seg = next((p.strip() for p in str(r.get("why") or "").split(", ") if p.startswith("pivots beside")), None)
    if seg:
        parts.append(seg)
    if r.get("penalty_pct"):
        parts.append(f"pooled -{float(r['penalty_pct']):g} % decode")
    own = r.get("ft_tax") or r.get("st_tax") or r.get("tf_tax")  # 3.3.9.1 FreeToken's; 3.3.9.2 Strata's; 3.3.9.3
    if own and not r.get("warm"):
        parts = [p for p in parts if not (p.startswith("evicts") or p.endswith("to load"))] + [own]
    return ", ".join(parts) or "no load tax"


def scored(lanes: list, *, state_dir=None, hosts=None, answers=None) -> dict:
    from halo_harness.local_sched.place import solve
    plan = solve(lanes, hosts=hosts if hosts is not None else candidates(state_dir), answers=answers,
                 state_dir=state_dir, detail=True)
    for r in plan["rows"]:
        opts = sorted(r.get("options") or [], key=lambda o: (o["score"] is None, -(o["score"] or 0), o["host"]))
        r["options"] = opts
        r["tax"] = tax({**next((o for o in opts if o["host"] == r.get("host")), {}), "why": r.get("why")})
        own = next((o for o in opts if o["host"] == r.get("from_host")), None)
        best = opts[0] if opts and opts[0]["score"] is not None else None
        r["cheaper"] = ({"host": best["host"], "score": best["score"], "own": own["score"],
                         "gain": round(best["score"] - own["score"], 1)}
                        if best and own and own["score"] is not None and best["host"] != own["host"]
                        and best["score"] - own["score"] >= GAIN else None)
    return plan


def _words(r: dict) -> str:
    c = r["cheaper"]
    own = next((o for o in r["options"] if o["host"] == r.get("from_host")), {})
    return (f"{r['lane']} ({r['model']}) on {r.get('from_host')} scores {c['own']:g} ({tax(own)}); {c['host']} scores "
            f"{c['score']:g} ({tax(next((o for o in r['options'] if o['host'] == c['host']), {}))})")


def score_line(r: dict) -> str:
    """"worker (qwen3.5:9b): pc 60 (25 s to load, pivots beside qwen3.8:27b) | samus 95 (warm: no load) | pool --
    (does not fit)" -- every candidate's score and its loading tax, the chosen one first."""
    opts = r.get("options") or []
    return f"{r['lane']} ({r['model']}): " + " | ".join(
        f"{o['host']} {o['score']:g} ({tax({**o, 'why': o.get('why')})})" if o["score"] is not None else
        f"{o['host']} -- ({str(o.get('why') or 'not placed')[:90]})" for o in opts)


def suggestions(inp: dict, state_dir=None) -> list:
    lanes = [ln for ln in inp.get("lanes") or [] if ln.get("lane") != "main"]
    if not lanes:
        return []
    out, plan = [], scored(lanes, state_dir=state_dir)
    inp["placement"] = {"rows": plan.get("rows") or [], "lines": [score_line(r) for r in plan.get("rows") or []]}
    for r in plan.get("rows") or []:
        if not r.get("cheaper"):
            continue
        c = r["cheaper"]
        out.append({"kind": "placement", "host": r.get("from_host"), "says": _words(r),
                    "frees": f"{c['gain']:g} points of placement (the load and the switch it no longer pays)",
                    "cost": {"download_gb": 0.0, "vram_gb": None, "window": None, "beside": None, "minutes": 0},
                    "value": round(c["gain"] / 10.0, 1), "value_per_gb": round(c["gain"] / 10.0, 1),
                    "lane": r["lane"], "scores": r["options"],
                    "action": {"verb": "place", "what": f"host_for {r['lane']} -> {c['host']}", "host": c["host"],
                               "role": r["lane"], "model": r["model"], "cli": "halo local place --apply"}})
    return out


def _file(state_dir) -> Path:
    from halo_harness.ollama_steward.ledger import ledger_dir
    return ledger_dir(state_dir) / FILE


def _residency() -> dict:
    """{host name here: {model: at}} from every paired host's GET residency."""
    from halo_harness.fleet import identity, store
    from halo_harness.ollama_steward.host_client import HostClient, HostError
    out: dict = {}
    for e in store.hosts():
        key = store.key_for(e) if e.get("state", "joined") == "joined" else None
        if key is None:
            continue
        try:
            rows = HostClient(e, key, identity.harness()["id"]).get("residency").get("residency") or []
        except (HostError, OSError):
            continue
        names = {str(r.get("name") or "").lower(): str(r.get("name")) for r in e.get("serves") or [] if isinstance(r, dict)}
        for r in rows:
            name = names.get(str(r.get("host") or "").lower(), str(r.get("host") or ""))
            out.setdefault(name, {})[str(r.get("model"))] = r.get("at")
    return out


def recheck(state_dir, *, now: Optional[float] = None, lanes=None, hosts=None, answers=None,
            residency: Optional[dict] = None) -> list:
    now = time.time() if now is None else now
    if residency is None and now - _LAST.get(str(state_dir), 0.0) < RECHECK_S:
        return []
    _LAST[str(state_dir)] = now
    seen = residency if residency is not None else _residency()
    try:
        prev = json.loads(_file(state_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        prev = {}
    changed = {h: sorted(set(m) ^ set((prev.get("residency") or {}).get(h) or {})) for h, m in seen.items()}
    changed = {h: ms for h, ms in changed.items() if ms}
    if lanes is None:
        from halo_harness.local_sched.preview import lanes_for
        from halo_harness.teams_runtime import active_team_name
        name = active_team_name(None)
        lanes = lanes_for(name, state_dir=state_dir)[0] if name else []
    placed = prev.get("placed") or {}
    if not prev:  # the first look: where each lane goes now, remembered; nothing to compare yet
        placed = {r["lane"]: r.get("host") for r in scored([ln for ln in lanes if ln.get("lane") != "main"],
                                                           state_dir=state_dir, hosts=hosts, answers=answers)["rows"]}
    mine = [ln for ln in lanes if ln.get("lane") != "main" and (ln.get("host") in changed or placed.get(ln["lane"])
                                                                in changed)]
    out, now_placed = [], dict(placed)
    if changed and mine and prev:
        for r in scored(mine, state_dir=state_dir, hosts=hosts, answers=answers)["rows"]:
            was = placed.get(r["lane"]) or r.get("from_host")
            now_placed[r["lane"]] = r.get("host")
            if r.get("host") and r["host"] != was:
                why = next(f"{h}'s card changed ({', '.join(ms)} loaded or unloaded there)" for h, ms in changed.items())
                out.append({"id": f"place-{r['lane']}-{int(now)}", "key": f"{r['host']}|{r['model']}", "kind": "placement",
                            "say": f"{why}: {r['lane']} would go to {r['host']} now (score {r['score']:g}) -- halo local "
                                   "place --apply moves it; nothing moved"})
    try:
        _file(state_dir).parent.mkdir(parents=True, exist_ok=True)
        _file(state_dir).write_text(json.dumps({"residency": seen, "placed": now_placed, "at": now}), encoding="utf-8")
    except OSError:
        pass
    return out
