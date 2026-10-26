"""halo_harness.studio.model -- what Studio shows, built from the same
functions the wizard and the CLI use (Halo 2.1.0 round B3). Nothing here
re-implements a rule: lineups and bios come from `teams_yaml` /
`agents_yaml`, the model catalog from `providers.model_enumeration`, the
live session from the files a session writes under ~/.halo/sessions.

A lineup becomes a graph: one node per `agents:` entry (the assignment,
the bio behind it, the model that resolves, price/context from the
catalog, scope, problems), edges for delegation (main -> member, labelled
with the routing keys that reach it) and pipeline stage order.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

import yaml

from halo_harness import agents_yaml as A
from halo_harness import teams_yaml as T

_PRIVATE = ("_source", "_path")


def clean(data: dict) -> dict:
    return {k: v for k, v in (data or {}).items() if not str(k).startswith("_")}


def to_yaml(data) -> str:
    # 3.0.7.0 R1: a section body may be a list (`tiers`), dumped as it is
    body = data if isinstance(data, list) else clean(data)
    return yaml.safe_dump(body, sort_keys=False, allow_unicode=True, width=100)


def from_yaml(text: str) -> dict:
    data = yaml.safe_load(text or "") or {}
    if not isinstance(data, dict):
        raise ValueError("the YAML must be a mapping at the top level")
    return data


# -- the model catalog --------------------------------------------------------

def catalog_rows(state_dir=None, cwd=None, *, cached: bool = False) -> list:
    """The catalog rows (`build_model_rows`, aliases and hints left out) the
    way a session in `cwd` resolves its providers -- `model_rows` and the
    best-at rebuild (`POST models/analyze`) both read these. 3.3.0.0 R3
    `cached`: no Ollama host or local port probed (Setup's state read)."""
    from halo_harness.providers.config import default_state_dir, load_routes
    from halo_harness.providers.model_enumeration import build_model_rows
    from halo_harness.studio.catalog_env import catalog_env
    state_dir = Path(state_dir or default_state_dir())
    routes_path = state_dir / "routes.json" if state_dir.exists() else None
    return [row for row in build_model_rows(state_dir, env=catalog_env(cwd), routes=load_routes(routes_path), cached=cached)
            if row.get("ref") and row.get("provider") != "alias"]


def model_rows(state_dir=None, cwd=None, *, cached: bool = False) -> list:
    """3.1.4.0 R4: the providers resolve through `catalog_env(cwd)`, the env a
    session resolves with (the env file, the shell, the settings.json `env`
    chain), not a bare copy of os.environ (which skipped the settings chain).
    3.1.9.0 R1: each row also carries the catalog's own keys (modalities,
    tools, reasoning, open weights, local, measured) and `best_at` -- `{line,
    kinds}` from the best-at cache (models_best_at), the same answer `halo
    models analyze` prints. 3.3.0.0 R3 `cached`: the local rows from what is
    already known (catalog_rows), so a read opens no connection."""
    from halo_harness.capabilities import capability_profile
    from halo_harness.model_display import format_price_per_m, format_speed, format_token_count
    from halo_harness.models_best_at import index as best_at_index
    from halo_harness.providers.config import default_state_dir
    state_dir = Path(state_dir or default_state_dir())
    raw = catalog_rows(state_dir, cwd, cached=cached)
    try:
        best = best_at_index(state_dir, raw).get("rows") or {}
    except Exception:
        best = {}
    try:  # 3.1.9.0 R3: what Auto learned per task kind (outcomes/learn.py): the picker's chips and strikes
        from halo_harness.outcomes.learn import by_model as learned_by_model
        learned = learned_by_model(state_dir)
    except Exception:
        learned = {}
    rows = []
    for row in raw:
        ref = row["ref"]
        at = best.get(ref) or {}
        rows.append({
            "ref": ref, "provider": row.get("provider", ""), "group": row.get("group", ""), "detail": row.get("detail", ""),
            "price_in": row.get("price_in_per_m"), "price_out": row.get("price_out_per_m"),
            "price": format_price_per_m(row.get("price_in_per_m")) or "?",
            "context": format_token_count(row.get("context_tokens")) or "?",
            "context_tokens": row.get("context_tokens"),
            "speed": format_speed(row.get("speed_ttft_s"), row.get("speed_tokens_per_second")) or "?",
            "local": bool(row.get("local")),  # 3.1.9.0 R1: is_local_model_ref (a Hugging Face router row is remote)
            "chips": capability_profile(row)["chips"],  # 3.0.1.0 D1: vision / audio / video / files / image-out, or ? when unknown
            "modalities_in": row.get("modalities_in"), "image_output": bool(row.get("image_output")),
            "price_in_per_m": row.get("price_in_per_m"), "tools": row.get("tools"),  # the raw keys capabilities.best_for scores on
            "price_out_per_m": row.get("price_out_per_m"), "max_output_tokens": row.get("max_output_tokens"),
            "speed_ttft_s": row.get("speed_ttft_s"), "speed_tokens_per_second": row.get("speed_tokens_per_second"),
            "modalities_out": row.get("modalities_out"), "reasoning": row.get("reasoning"),
            "open_weights": row.get("open_weights"), "measured": row.get("measured"),
            "best_at": {"line": at.get("line") or "", "kinds": list(at.get("kinds") or [])},
            "learned": learned.get(ref) or {},  # {kind: {n, passed, rate, picked, weight, counted, dropped, days}}
        })
    return rows


def _catalog_index(state_dir=None) -> dict:
    try:
        return {r["ref"]: r for r in model_rows(state_dir)}
    except Exception:
        return {}


# -- lineups ----------------------------------------------------------------------

def _effective_model(raw: dict, entry: dict, bio: Optional[dict], *, cwd=None, state_dir=None) -> tuple[str, str, str]:
    """3.1.6.0 R1: (model, fallback, source) in `teams_yaml.member_model`'s
    order -- the card's own, a pinning bio, its tier's model, the session's
    (a `default` bio), the fallbacks; `source` says which ("card", "bio",
    "tier:<name>", "session", "fallback")."""
    return T.member_model(raw, entry, cwd=cwd, state_dir=state_dir, bio=bio)


def _removed_route_warnings(*refs) -> list:
    """3.1.5.0 R1: a card still naming a cc:/cx: model (routes removed in
    3.1.5.0) falls through to the session model -- say so on the card."""
    if any(str(r or "").startswith(("cc:", "cx:")) for r in refs):
        return ["names a cc:/cx: model (removed in 3.1.5.0) -- it falls through to the session model; "
                "pick an API route, e.g. ant:sonnet"]
    return []


def _bio_warnings(bio, source: str, state_dir) -> list:
    """3.2.0.0 R2: no catalog model has the bio's capabilities; a pack bio's need not granted (packs/roles.py)."""
    from halo_harness.packs.roles import card_warnings
    return card_warnings(bio, source, state_dir=state_dir) if bio else []


def _node_base(entry: dict, i: int) -> str:
    return str(entry.get("as") or entry.get("role") or entry.get("agent") or f"n{i}")


def node_ids(entries: list) -> list:
    """3.2.2.0 R5: a card's id is its alias (else its role, else its agent)
    plus an ordinal only among the cards with that same name (two `reviewer`
    cards are `reviewer#0` and `reviewer#1`), so removing a card keeps every
    other card's id and its saved spot on the canvas."""
    seen: dict = {}
    out = []
    for i, e in enumerate(entries):
        base = _node_base(e, i)
        out.append(f"{base}#{seen.get(base, 0)}")
        seen[base] = seen.get(base, 0) + 1
    return out


def legacy_node_ids(entries: list) -> list:
    """The ids before 3.2.2.0: the name plus the card's index in the lineup."""
    return [f"{_node_base(e, i)}#{i}" for i, e in enumerate(entries)]


def migrate_layout_ids(layout: dict, raw: dict) -> dict:
    """A layout saved with the index ids (before 3.2.2.0) reads with today's
    ids when its cards are this lineup's cards under the old ids: all of
    them, or some of them when one of those ids can only be an old one (a
    layout keeps only the cards that were moved). Anything else -- a layout
    already in today's ids, cards that are not this lineup's -- is left as
    it is."""
    layout = normalize_layout(layout)
    entries = [e for e in (raw.get("agents") or []) if isinstance(e, dict)]
    old, new = legacy_node_ids(entries), node_ids(entries)
    saved = set(layout["nodes"])
    if old == new or not saved or not saved <= set(old) or saved == set(new):
        return layout
    if saved <= set(new) and saved != set(old):
        return layout  # every id reads either way: today's
    to_new = dict(zip(old, new))
    return {**layout, "nodes": {to_new[k]: v for k, v in layout["nodes"].items()}}


def graph_for(raw: dict, *, cwd=None, state_dir=None, catalog: Optional[dict] = None) -> dict:
    catalog = _catalog_index(state_dir) if catalog is None else catalog
    entries = [e for e in (raw.get("agents") or []) if isinstance(e, dict)]
    nodes, by_alias, by_role = [], {}, {}
    ids = node_ids(entries)
    for i, e in enumerate(entries):
        bio = A.resolve_agent_bio(str(e.get("agent") or ""), cwd=cwd, state_dir=state_dir) if e.get("agent") else None
        model, fallback, source = _effective_model(raw, e, bio, cwd=cwd, state_dir=state_dir)
        inherit, _fb, inherit_source = _effective_model(raw, {k: v for k, v in e.items() if k != "models"}, bio,
                                                        cwd=cwd, state_dir=state_dir)
        cat = catalog.get(model) or {}
        problems = []
        if not e.get("agent"):
            problems.append("no agent named")
        elif bio is None:
            problems.append(f"agent bio '{e.get('agent')}' not found")
        if not model:
            problems.append("no model resolves for this assignment")
        inst = e.get("instances")  # a hand-edited value must not stop the lineup from opening: the validator words the problem
        good = isinstance(inst, int) and not isinstance(inst, bool) and inst >= 1
        if inst is not None and not good:
            problems.append('"instances" must be a positive integer')
        allow = ((bio or {}).get("tools") or {}).get("allow") if isinstance((bio or {}).get("tools"), dict) else None
        node = {
            "id": ids[i], "index": i, "agent": str(e.get("agent") or ""), "role": str(e.get("role") or "subagent"),
            "alias": str(e.get("as") or ""), "instances": inst if good else 1,
            "use_for": list(e["use_for"]) if isinstance(e.get("use_for"), list) else [],
            "model": model, "fallback": fallback, "price": cat.get("price", ""), "context": cat.get("context", ""),
            # 3.1.4.0 R4: what the card runs on without its own model; 3.1.6.0 R1: where each comes from
            "bio_model": inherit, "model_source": source, "inherit_source": inherit_source,
            "tools": (len(allow) if isinstance(allow, list) else 0) if bio else None,
            "scope": (bio or {}).get("_source", ""), "kind": (bio or {}).get("kind", ""),
            "description": (bio or {}).get("description", ""), "problems": problems,
            "warnings": _removed_route_warnings(model, fallback) + _bio_warnings(bio, source, state_dir),
            "overrides": {k: v for k, v in e.items() if k not in ("agent", "role", "as", "instances", "use_for")},
        }
        nodes.append(node)
        if node["alias"]:
            by_alias.setdefault(node["alias"], node["id"])
        by_role.setdefault(node["role"], node["id"])
    mains = [n for n in nodes if n["role"] == "main"]
    if len(mains) != 1:
        for n in nodes:
            n["warnings"].append(f"{len(mains)} assignments have role main (exactly one is expected)")
    seen_alias = {}
    for n in nodes:
        if n["alias"]:
            if n["alias"] in seen_alias:
                n["warnings"].append(f"alias '{n['alias']}' is used twice")
            seen_alias[n["alias"]] = True
    edges = []
    routing = raw.get("routing") if isinstance(raw.get("routing"), dict) else {}
    target_labels: dict = {}
    for key, target in routing.items():
        nid = by_alias.get(str(target)) or by_role.get(str(target))
        if nid:
            target_labels.setdefault(nid, []).append(str(key))
    if mains:
        for n in nodes:   # every member hangs off main by its delegation edge
            if n is not mains[0]:
                edges.append({"from": mains[0]["id"], "to": n["id"], "kind": "delegation", "label": ", ".join(target_labels.get(n["id"], []))})
    stages = ((raw.get("pipeline") or {}).get("stages") or []) if isinstance(raw.get("pipeline"), dict) else []
    prev = None
    for st in stages:
        if not isinstance(st, dict):
            continue
        nid = by_alias.get(str(st.get("role"))) or by_role.get(str(st.get("role")))
        if prev and nid and prev != nid:
            edges.append({"from": prev, "to": nid, "kind": "pipeline", "label": f"then {st.get('name') or ''}".strip()})
        prev = nid or prev
    # 3.0.7.0 R1: the lineup's tiers (declared, plus the implicit last tier;
    # one implicit tier `all` when none are declared) -- `members` are the
    # assignment aliases, `node_ids` the cards that sit in each tier.
    from halo_harness.teams_tiers import effective_tiers
    by_key = {}
    for n in nodes:
        by_key.setdefault(n["alias"] or n["role"], []).append(n["id"])
    tiers = [{**t, "node_ids": [i for m in t["members"] for i in by_key.get(m, [])]} for t in effective_tiers(raw)]
    return {"nodes": nodes, "edges": edges, "tiers": tiers}


def lineup_summary(name: str, *, cwd=None, state_dir=None, active: str = "") -> Optional[dict]:
    raw = T.load_team_template_raw(name, cwd=cwd, state_dir=state_dir)
    if raw is None:
        return None
    entries = [e for e in (raw.get("agents") or []) if isinstance(e, dict)]
    return {"name": name, "scope": raw.get("_source", ""), "description": str(raw.get("description") or ""),
            "about": str(raw.get("about") or ""), "active": name == active, "agents": len(entries),
            "roles": sorted({str(e.get("as") or e.get("role") or "") for e in entries} - {""}),
            "shipped_copy": _is_shipped_copy(name, raw), **_pack_fields("lineups", name, raw, cwd, state_dir)}


def _pack_fields(kind: str, name: str, data: dict, cwd, state_dir) -> dict:
    """3.2.0.0 R2: a row's shadow, its clone origin and (bios) its capabilities (studio/packs_roles_api.py)."""
    from halo_harness.studio.packs_roles_api import row_fields
    return row_fields(kind, name, data, cwd=cwd, state_dir=state_dir)


def _is_shipped_copy(name: str, raw: dict) -> bool:
    """3.0.7.0 R2: a user-scope file that is still the byte-identical copy
    `ensure_builtin_team_templates` made of a shipped lineup (Studio's Roles
    Start view counts those as shipped, not as a lineup of your own)."""
    shipped = T.bundled_team_templates_dir() / f"{name}.yaml"
    try:
        if not raw.get("_path") or not shipped.is_file():
            return False
        # the copy is written in text mode, so on Windows a shipped file checked out with LF comes back CRLF:
        # compare the lines, not the line endings
        same = Path(raw["_path"]).read_bytes().replace(b"\r\n", b"\n") == shipped.read_bytes().replace(b"\r\n", b"\n")
        return same
    except OSError:
        return False


def lineup_payload(name: str, *, cwd=None, state_dir=None, active: str = "", layout: Optional[dict] = None) -> Optional[dict]:
    raw = T.load_team_template_raw(name, cwd=cwd, state_dir=state_dir)
    if raw is None:
        return None
    resolved = T.resolve_team_template(name, cwd=cwd, state_dir=state_dir) or raw
    problems = T.validate_team_template(clean(raw), name=name, cwd=cwd, state_dir=state_dir)
    table, notes = T.resolve_role_table(resolved, cwd=cwd, state_dir=state_dir)
    out = {
        "name": name, "scope": raw.get("_source", ""), "path": raw.get("_path", ""), "active": name == active,
        "pack": str(raw.get("_pack") or ""),  # 3.2.0.0 R2: a pack's lineup opens read-only
        "raw": clean(raw), "yaml": to_yaml(raw), "graph": graph_for(resolved, cwd=cwd, state_dir=state_dir),
        "role_table": table, "notes": notes, "problems": problems,
        "sections": {s: resolved.get(s) for s in T.TOP_SECTIONS if resolved.get(s) is not None},
        "enforcement": {s: list(T.SECTION_ENFORCEMENT.get(s, ("", ""))) for s in T.TOP_SECTIONS},
    }
    if layout is not None:  # 3.2.2.0 R5: the canvas layout, old card ids read as today's
        out["layout"] = legacy_layout_view(migrate_layout_ids(layout, resolved))
    return out


def bio_summary(name: str, *, cwd=None, state_dir=None) -> Optional[dict]:
    bio = A.resolve_agent_bio(name, cwd=cwd, state_dir=state_dir)
    if bio is None:
        return None
    return {"name": name, "scope": bio.get("_source", ""), "description": str(bio.get("description") or ""),
            "kind": str(bio.get("kind") or ""), "model": str(((bio.get("models") or {}).get("preference")) or ""),
            "tools": len(((bio.get("tools") or {}).get("allow") or [])), **_pack_fields("bios", name, bio, cwd, state_dir)}


def bio_payload(name: str, *, cwd=None, state_dir=None) -> Optional[dict]:
    raw = A.load_agent_bio_raw(name, cwd=cwd, state_dir=state_dir)
    if raw is None:
        return None
    resolved = A.resolve_agent_bio(name, cwd=cwd, state_dir=state_dir) or raw
    return {"name": name, "scope": raw.get("_source", ""), "path": raw.get("_path", ""), "raw": clean(raw),
            "resolved": clean(resolved), "yaml": to_yaml(raw),
            "problems": A.validate_agent_bio(clean(raw), name=name, cwd=cwd, state_dir=state_dir),
            "sections": list(A.BIO_SECTIONS), "kinds": list(A.KNOWN_KINDS),
            "pack": str(raw.get("_pack") or ""), "model_info": resolved.get("_model") or None}  # 3.2.0.0 R2


# -- layouts and the live session ------------------------------------------------

def layouts_dir(state_dir: Path) -> Path:
    return Path(state_dir) / "studio" / "layouts"


def layout_file_name(name: str) -> str:
    """The file a layout lives in. An Org layout is named `pc:<company id>`,
    and a colon in a file name makes an NTFS alternate data stream on
    Windows, so `pc:<id>` is stored as `_pc-<id>.json`. The leading
    underscore keeps it apart from every lineup layout (a valid layout name
    starts with a letter or digit, so `pc-<id>` stays a lineup's own file)."""
    return f"_{name.replace(':', '-')}.json" if ":" in name else f"{name}.json"


def _read_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None
    except (OSError, ValueError):
        return None


def read_layout(state_dir: Path, name: str) -> dict:
    d = layouts_dir(state_dir)
    got = _read_json(d / layout_file_name(name))
    if got is None and ":" in name and os.name != "nt":
        # one-time fallback: a layout written as `pc:<id>.json` before the
        # rename moves to the new file the first time it is read
        old = d / f"{name}.json"
        got = _read_json(old)
        if isinstance(got, dict):
            try:
                write_layout(state_dir, name, got)
                old.unlink()
            except OSError:
                pass
    return normalize_layout(got)


def normalize_layout(got) -> dict:
    """3.0.7.0 R1: a layout is `{nodes: {id: {x, y}}, tiers: {name:
    {collapsed: bool}}}`. The old flat shape `{id: {x, y}}` (every layout
    written before 3.0.7.0) reads as `{nodes: <it>, tiers: {}}`."""
    if not isinstance(got, dict):
        return {"nodes": {}, "tiers": {}}
    if isinstance(got.get("nodes"), dict) and all(isinstance(v, dict) for v in got["nodes"].values()) \
            and ("tiers" in got or set(got) == {"nodes"}):
        tiers = got.get("tiers") if isinstance(got.get("tiers"), dict) else {}
        return {"nodes": dict(got["nodes"]),
                "tiers": {str(k): {"collapsed": bool((v or {}).get("collapsed"))} for k, v in tiers.items()
                          if isinstance(v, dict) or v is None}}
    return {"nodes": {k: v for k, v in got.items() if isinstance(v, dict)}, "tiers": {}}


def legacy_layout_view(layout: dict) -> dict:
    """What `GET layout/<name>` answers: the new shape's `nodes` and `tiers`
    plus every node position at the top level too, because the legacy page
    (`app.js` setGraph, `org.js` draw) reads the flat `{id: {x, y}}` map.
    An empty layout answers `{}` (both readers treat that as "no layout")."""
    layout = normalize_layout(layout)
    if not layout["nodes"] and not layout["tiers"]:
        return {}
    return {**layout["nodes"], "nodes": layout["nodes"], "tiers": layout["tiers"]}


def write_layout(state_dir: Path, name: str, positions: dict, tiers: Optional[dict] = None) -> None:
    """Writes the new shape. `positions` is either the flat `{id: {x, y}}`
    map or a whole `{nodes, tiers}` layout; `tiers` (when given) replaces
    the tier state, else the saved tier state is kept."""
    layout = normalize_layout(positions)
    if tiers is not None:
        layout["tiers"] = normalize_layout({"nodes": {}, "tiers": tiers})["tiers"]
    elif not layout["tiers"]:
        d0 = layouts_dir(state_dir) / layout_file_name(name)
        layout["tiers"] = normalize_layout(_read_json(d0))["tiers"] if d0.is_file() else {}
    d = layouts_dir(state_dir)
    d.mkdir(parents=True, exist_ok=True)
    (d / layout_file_name(name)).write_text(json.dumps(layout, indent=1), encoding="utf-8")


def _newest_session(state_dir: Path):
    root = Path(state_dir) / "sessions"
    best = None
    for p in root.glob("*/*.jsonl") if root.is_dir() else []:
        try:
            m = p.stat().st_mtime
        except OSError:
            continue
        if best is None or m > best[0]:
            best = (m, p)
    return best


def _agent_metas(session_dir: Path, depth: int = 0) -> list:
    out = []
    sub = session_dir / "subagents"
    for meta in sorted(sub.glob("agent-*.meta.json")) if sub.is_dir() else []:
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        data["depth"] = depth
        out.append(data)
        out.extend(_agent_metas(sub / meta.name.replace(".meta.json", ""), depth + 1))
    return out


def session_payload(state_dir: Path) -> dict:
    found = _newest_session(state_dir)
    if not found:
        return {"running": False, "agents": [], "roles": {}}
    mtime, log = found
    cost_by_agent: dict = {}
    cost_by_role: dict = {}
    try:
        for line in log.read_text(encoding="utf-8").splitlines():
            try:
                node = json.loads(line)
            except ValueError:
                continue
            if node.get("type") != "usage":
                continue
            c = float(node.get("cost_usd") or 0)
            cost_by_agent[node.get("agent_id") or "main"] = cost_by_agent.get(node.get("agent_id") or "main", 0.0) + c
            role = node.get("role") or "main"
            cost_by_role[role] = cost_by_role.get(role, 0.0) + c
    except OSError:
        pass
    agents = _agent_metas(log.with_suffix(""))
    live_states = {"queued", "running", "background"}
    running = (time.time() - mtime) < 180 or any(a.get("status") in live_states for a in agents)
    for a in agents:
        a["cost_usd"] = round(cost_by_agent.get(a.get("agent_id"), 0.0), 4)
    return {"running": bool(running), "session_id": log.stem, "updated": mtime, "agents": agents,
            "roles": {k: round(v, 4) for k, v in cost_by_role.items()}}
