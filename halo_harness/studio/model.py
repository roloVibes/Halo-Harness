"""halo_harness.studio.model -- what Studio shows, built from the same
functions the wizard and the CLI use (Halo 2.1.0 round B3): the model
catalog from `providers.model_enumeration`, a pack canvas's saved layout,
the live session from the files a session writes under ~/.halo/sessions.
(3.6.0.0 R5b: the lineup graph and the bio views went with lineups and bios.)
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

import yaml

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
    from halo_harness.model_takes import takes_words
    from halo_harness.providers.effort_on import row_word as effort_row_word
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
    from halo_harness.studio.model_card_api import row_view  # 3.3.5.0 R0b: the card's chips and the fit meter
    host_cards: dict = {}
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
            "takes": takes_words(row),  # 3.3.15.0 R2: the words the terminal picker's takes= column shows
            "learned": learned.get(ref) or {},  # {kind: {n, passed, rate, picked, weight, counted, dropped, days}}
            "effort_word": effort_row_word(ref, row),  # 3.3.5.0 R0 (e): think on/off, effort n/a, or "" (cloud)
            **row_view(ref, row, state_dir, read_hardware=not cached, host_cards=host_cards),  # card, fit
        })
        card = rows[-1].get("card") or {}  # 3.3.6.0 R6: the vision fact on the row itself (Settings' model row, the picker)
        rows[-1]["vision"] = {"value": card.get("vision"), "truth": card.get("vision_truth"),
                              "source": (card.get("sources") or {}).get("vision")}
    return rows


# -- node ids (a pack canvas's nodes, a ComfyUI graph's) --------------------------

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
