"""halo_harness.studio.model -- what Studio shows, built from the same
functions the wizard and the CLI use (Halo 2.1.0 round B3). Nothing here
re-implements a rule: lineups and bios come from `teams_yaml` /
`agents_yaml`, the model catalog from `providers.model_enumeration`, the
live session from the files a session writes under ~/.halo/sessions.

A lineup becomes a graph: one node per `agents:` entry (the assignment,
the bio behind it, the model that resolves, price/context from the
catalog, scope, problems), edges for delegation (main -> member, labelled
with the routing keys that reach it), org `reports_to` lines and pipeline
stage order.
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

def model_rows(state_dir=None) -> list:
    from halo_harness.capabilities import capability_profile
    from halo_harness.model_display import format_price_per_m, format_speed, format_token_count
    import os
    from halo_harness.providers.config import default_state_dir, load_provider_env_files, load_routes
    from halo_harness.providers.model_enumeration import build_model_rows
    state_dir = Path(state_dir or default_state_dir())
    load_provider_env_files()  # the shared env files (keys) the CLI and the TUI both read
    routes_path = state_dir / "routes.json" if state_dir.exists() else None
    rows = []
    for row in build_model_rows(state_dir, env=dict(os.environ), routes=load_routes(routes_path)):
        ref = row.get("ref")
        if not ref or row.get("provider") == "alias":
            continue
        rows.append({
            "ref": ref, "provider": row.get("provider", ""), "group": row.get("group", ""), "detail": row.get("detail", ""),
            "price_in": row.get("price_in_per_m"), "price_out": row.get("price_out_per_m"),
            "price": format_price_per_m(row.get("price_in_per_m")) or "?",
            "context": format_token_count(row.get("context_tokens")) or "?",
            "context_tokens": row.get("context_tokens"),
            "speed": format_speed(row.get("speed_ttft_s"), row.get("speed_tokens_per_second")) or "?",
            "local": row.get("provider") in ("ollama", "huggingface"),
            "chips": capability_profile(row)["chips"],  # 3.0.1.0 D1: vision / audio / video / files / image-out, or ? when unknown
            "modalities_in": row.get("modalities_in"), "image_output": bool(row.get("image_output")),
            "price_in_per_m": row.get("price_in_per_m"), "tools": row.get("tools"),  # the raw keys capabilities.best_for scores on
        })
    return rows


def _catalog_index(state_dir=None) -> dict:
    try:
        return {r["ref"]: r for r in model_rows(state_dir)}
    except Exception:
        return {}


# -- lineups ----------------------------------------------------------------------

def _effective_model(entry: dict, bio: Optional[dict]) -> tuple[str, str]:
    over = (entry.get("models") or {}) if isinstance(entry.get("models"), dict) else {}
    bm = (bio or {}).get("models") if isinstance((bio or {}).get("models"), dict) else {}
    pref = over.get("preference") or bm.get("preference") or bm.get("fallback") or ""
    return str(pref or ""), str(over.get("fallback") or bm.get("fallback") or "")


def _subscription_warnings(*refs) -> list:
    """3.0.2.0: a cc:/cx: pick while the subscription routes are not
    accepted falls through to the default model -- say so on the card."""
    from halo_harness.subscription_consent import is_accepted
    out = []
    if any(str(r or "").startswith(("cc:", "cx:")) for r in refs) and not is_accepted():
        out.append("names a subscription route (cc:/cx:) that is not accepted -- it falls through to the default model until `halo subscriptions accept`")
    return out


def _node_id(entry: dict, i: int) -> str:
    return str(entry.get("as") or entry.get("role") or entry.get("agent") or f"n{i}") + f"#{i}"


def graph_for(raw: dict, *, cwd=None, state_dir=None, catalog: Optional[dict] = None) -> dict:
    catalog = _catalog_index(state_dir) if catalog is None else catalog
    entries = [e for e in (raw.get("agents") or []) if isinstance(e, dict)]
    nodes, by_alias, by_role, by_agent = [], {}, {}, {}
    for i, e in enumerate(entries):
        bio = A.resolve_agent_bio(str(e.get("agent") or ""), cwd=cwd, state_dir=state_dir) if e.get("agent") else None
        model, fallback = _effective_model(e, bio)
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
            "id": _node_id(e, i), "index": i, "agent": str(e.get("agent") or ""), "role": str(e.get("role") or "subagent"),
            "alias": str(e.get("as") or ""), "instances": inst if good else 1,
            "use_for": list(e["use_for"]) if isinstance(e.get("use_for"), list) else [],
            "model": model, "fallback": fallback, "price": cat.get("price", ""), "context": cat.get("context", ""),
            "tools": (len(allow) if isinstance(allow, list) else 0) if bio else None,
            "scope": (bio or {}).get("_source", ""), "kind": (bio or {}).get("kind", ""),
            "description": (bio or {}).get("description", ""), "problems": problems, "warnings": _subscription_warnings(model, fallback),
            "overrides": {k: v for k, v in e.items() if k not in ("agent", "role", "as", "instances", "use_for")},
        }
        nodes.append(node)
        if node["alias"]:
            by_alias.setdefault(node["alias"], node["id"])
        by_role.setdefault(node["role"], node["id"])
        by_agent.setdefault(node["agent"], node["id"])
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
    # 3.0.2.0 (the owner: "connect a new agent and role to something other
    # than the starting box"): `org.positions[].reports_to` is the
    # connection. A title names an assignment by alias, else by role, else
    # by agent; a member that reports to another member hangs off THAT
    # card instead of main, so the tree re-forms as you connect boxes.
    org = raw.get("org") if isinstance(raw.get("org"), dict) else {}

    positions = [p for p in (org.get("positions") or []) if isinstance(p, dict)]
    titles: dict = {}
    for p in positions:   # a position's title names its assignment by alias, role, or the position's own agent
        t = str(p.get("title") or "")
        nid = by_alias.get(t) or by_role.get(t) or by_agent.get(str(p.get("agent") or "")) or by_agent.get(t)
        if t and nid:
            titles[t] = nid

    def _node_for_title(title) -> Optional[str]:
        t = str(title or "")
        return titles.get(t) or by_alias.get(t) or by_role.get(t) or by_agent.get(t)
    parent_of: dict = {}
    for p in positions:
        if p.get("reports_to"):
            child, parent = _node_for_title(p.get("title")), _node_for_title(p.get("reports_to"))
            if child and parent and child != parent:
                parent_of[child] = parent
    main_id = mains[0]["id"] if mains else None
    if mains:
        for n in nodes:   # a member that reports to another MEMBER hangs off that card, not main
            if n is not mains[0] and parent_of.get(n["id"], main_id) == main_id:
                edges.append({"from": mains[0]["id"], "to": n["id"], "kind": "delegation", "label": ", ".join(target_labels.get(n["id"], []))})
    for child, parent in parent_of.items():
        edges.append({"from": child, "to": parent, "kind": "reports", "label": "reports to"})
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
            "shipped_copy": _is_shipped_copy(name, raw)}


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


def lineup_payload(name: str, *, cwd=None, state_dir=None, active: str = "") -> Optional[dict]:
    raw = T.load_team_template_raw(name, cwd=cwd, state_dir=state_dir)
    if raw is None:
        return None
    resolved = T.resolve_team_template(name, cwd=cwd, state_dir=state_dir) or raw
    problems = T.validate_team_template(clean(raw), name=name, cwd=cwd, state_dir=state_dir)
    table, notes = T.resolve_role_table(resolved, cwd=cwd, state_dir=state_dir)
    return {
        "name": name, "scope": raw.get("_source", ""), "path": raw.get("_path", ""), "active": name == active,
        "raw": clean(raw), "yaml": to_yaml(raw), "graph": graph_for(resolved, cwd=cwd, state_dir=state_dir),
        "role_table": table, "notes": notes, "problems": problems,
        "sections": {s: resolved.get(s) for s in T.TOP_SECTIONS if resolved.get(s) is not None},
        "enforcement": {s: list(T.SECTION_ENFORCEMENT.get(s, ("", ""))) for s in T.TOP_SECTIONS},
    }


def bio_summary(name: str, *, cwd=None, state_dir=None) -> Optional[dict]:
    bio = A.resolve_agent_bio(name, cwd=cwd, state_dir=state_dir)
    if bio is None:
        return None
    return {"name": name, "scope": bio.get("_source", ""), "description": str(bio.get("description") or ""),
            "kind": str(bio.get("kind") or ""), "model": str(((bio.get("models") or {}).get("preference")) or ""),
            "tools": len(((bio.get("tools") or {}).get("allow") or []))}


def bio_payload(name: str, *, cwd=None, state_dir=None) -> Optional[dict]:
    raw = A.load_agent_bio_raw(name, cwd=cwd, state_dir=state_dir)
    if raw is None:
        return None
    resolved = A.resolve_agent_bio(name, cwd=cwd, state_dir=state_dir) or raw
    return {"name": name, "scope": raw.get("_source", ""), "path": raw.get("_path", ""), "raw": clean(raw),
            "resolved": clean(resolved), "yaml": to_yaml(raw),
            "problems": A.validate_agent_bio(clean(raw), name=name, cwd=cwd, state_dir=state_dir),
            "sections": list(A.BIO_SECTIONS), "kinds": list(A.KNOWN_KINDS)}


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
