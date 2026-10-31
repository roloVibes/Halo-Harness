"""halo_harness.ollama_steward.rules_drift -- the drift and deletion guards as steward rules (Halo 3.3.7.0 R4;
plans/local-model-fit-brief.md G14). rules.run_rules adds them beside the others.

    drift_rules(ctx) -> [finding]
      tag-drift (warn)    an installed tag whose digest is not the one its records were measured on: the battery
                          profile, the speed card, the window truth, the crash fingerprints (tag_digests.stale_records)
                          -- "measured on an older build of this tag"; the speed card stops pricing a swap or Auto's
                          pick (local_sched/swap_cost.py) and the off-hours refresh queues the tag first (drifted)
      tag-deleted (error) a role, the active lineup's lane, a `warm:` entry or a placement (`host_for`) names a tag the
                          host's catalog no longer has: the one dead-tag line (dead_tag.py) with its nearest equivalent
                          and "point the role at it"; (info) a tag that left the catalog since the last read and that
                          nothing names
    refs(state_dir) -> [(where, ref)]     every place that names a local model, for the deletion guard
Each host's catalog comes from ctx["catalogs"] (gather's), else its `catalog_reader`; a catalog that does not answer
judges nothing. Each catalog read goes through tag_digests.observe (the digests are stored at that read).
"""

from __future__ import annotations

from halo_harness.ollama_steward.rules import finding


def refs(state_dir) -> list:
    out = []
    try:
        from halo_harness.roles import configured_role_table, role_value_parts
        for role, v in sorted(configured_role_table().items()):
            ref = role_value_parts(v)[0]
            if isinstance(ref, str) and ref.startswith("ol:"):
                out.append((f"role {role}", ref, role))
    except Exception:
        pass
    try:
        from halo_harness.local_sched.preview import lanes_for
        from halo_harness.teams_runtime import active_team_name
        name = active_team_name(None)
        if name:
            lanes, declared, _n = lanes_for(name, state_dir=state_dir)
            out += [(f"lineup {name} lane {ln['lane']}", f"ol:{ln['model']}@{ln['host']}", None) for ln in lanes
                    if ln["lane"] != "main"]
            out += [(f"lineup {name} warm:", f"ol:{m}", None) for m in declared if not any(m == ln["model"] for ln in lanes)]
    except Exception:
        pass
    try:
        from halo_harness.ollama_steward.profiles import all_profiles, split_role
        for key, p in sorted(all_profiles().items()):
            if isinstance(p, dict) and p.get("host_for"):
                _h, model, role = split_role(key)
                out.append((f"placement of {key} (host_for)", f"ol:{model}@{p['host_for']}", role))
    except Exception:
        pass
    return out


def _catalog(ctx, h) -> list:
    got = (ctx.get("catalogs") or {}).get(h.name)
    if got is None and ctx.get("catalog_reader") is not None:
        try:
            got = {str(r.get("model") or r.get("name")): r for r in (ctx["catalog_reader"](h) or {}).get("models") or []
                   if isinstance(r, dict)}
        except Exception:
            got = {}
    return [{**r, "model": r.get("model") or m} for m, r in (got or {}).items() if isinstance(r, dict)]


def _group(host: str, model: str) -> dict:
    from halo_harness.ollama_steward.profiles import key_for
    return {"host": host, "model": model, "key": key_for(host, model)}


def drift_rules(ctx: dict) -> list:
    from halo_harness.ollama_steward import dead_tag, tag_digests as D
    state, out = ctx.get("state_dir"), []
    if state is None:
        return out
    named = refs(state)
    for h in ctx.get("hosts") or []:
        rows = _catalog(ctx, h)
        if not rows:
            continue
        seen = D.observe(state, h.name, rows, now=ctx.get("now"))
        for r in rows:
            stale = D.stale_records(state, h.name, r["model"], r.get("digest"), host_url=h.url)
            if not stale:
                continue
            ch = D.changed(state, h.name, r["model"]) or {}
            was = f" ({str(ch.get('was') or '?')[:15]} -> {str(r.get('digest'))[:15]})" if ch else ""
            words = ", ".join(s["line"] for s in stale)
            out.append(finding("tag-drift", _group(h.name, r["model"]), "warn",
                               f"the tag's digest changed{was}: {words} {'was' if len(stale) == 1 else 'were'} "
                               f"{D.WORD}; its speed card no longer prices a swap or Auto's pick, and the off-hours "
                               "refresh measures it first (halo local refresh, or halo host refresh now)",
                               numbers={"digest": r.get("digest"), "was": ch.get("was"), "stale": [s["what"] for s in stale]}))
        names = set()
        for where, ref, role in named:
            got = dead_tag.check(ref, state_dir=state, catalog={"models": rows}, role=role)
            if got["dead"] and got["host"] == h.name:
                names.add(got["model"])
                out.append(finding("tag-deleted", _group(h.name, got["model"]), "error", f"{where}: {got['line']}",
                                   numbers={"near": got["near"], "where": where}, point=got["point"], near=got["near"],
                                   role=role))
        for g in seen["gone"]:
            if g["model"] not in names:
                out.append(finding("tag-deleted", _group(h.name, g["model"]), "info",
                                   f"{g['model']} left {h.name}'s catalog since the last read (deleted there); nothing "
                                   "Halo runs names it", numbers={"was": g.get("was")}))
    return out
