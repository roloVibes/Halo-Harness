"""halo_harness.studio.setup_state -- what `GET setup/state` answers (Halo
3.3.0.0 R1, Studio's Setup section; docs/STUDIO-sections.md "Setup"): every
block's current value, read from the same places the terminal wizard reads
them, and the rows each block offers (the wizard's own lists).

    {model, permission_mode, theme, theme_default,
     themes: [{name, palette: {bg, surface, panel, text, muted, accent, ok, warn, bad, tool}}],
     permission_modes: [{id, label, note}],            init_cli._PERMISSION_MODE_ROWS
     team: {active, source, maps: [{name, label, scope, description, boxes, lines, active, default}]}  (the Map step),
     models: [{ref, provider, label, best_at, price, context}],   the Models panel's rows (studio/model.py), cached only
     model_notes: [lines],                            a configured Ollama host nothing read yet ("not read yet: Refresh")
     providers: {<name>: {label, set, source, tail, enabled, reachable, catalog_count, detail, host_hint, fields}},
     ollama, huggingface, local_models,               R2: studio/setup_providers_state.py
     checks, gym_models, card, last_check, linux_fixes, no_provider,   R3: studio/setup_check_state.py
     ollama_discover, home, done_at}                  R5; 3.3.1.0 R1 `home`: a 12-hex hash of the state dir;
                                                      3.3.3.0 R1 `done_at`: Setup's Done (studio/setup_done.py) or null
     packs: [{id, name, help, blocks}]                3.3.11.0 R3: the enabled packs' Setup blocks (setup_packs_api.py)

No key is ever in it: a provider is `set` or not, with its source and last four characters. `permission_mode`, `theme`
and `model` are "" when config.json has none (the strip then says "not set"). 3.3.0.0 R3: a read opens no
connection -- the model rows are the cached catalog (no Ollama host or local port probed: a host never read in this
process is a `model_notes` line instead), the costs and the card the same.
"""

from __future__ import annotations

PALETTE_KEYS = (("bg", "bridge-bg"), ("surface", "bridge-surface"), ("panel", "bridge-panel"), ("text", "bridge-text"),
                ("muted", "bridge-muted"), ("accent", "bridge-accent"), ("ok", "bridge-success"), ("warn", "bridge-warning"),
                ("bad", "bridge-error"), ("tool", "bridge-tool"))


def _config(key: str) -> str:
    from halo_harness.theme import get_config_value
    value = get_config_value(key, "")
    return value.strip() if isinstance(value, str) else ""


def permission_rows() -> list:
    """The wizard's four rows, each split into its label and its note at the first " -- "."""
    from halo_harness.init_cli import _PERMISSION_MODE_ROWS
    out = []
    for mode, text in _PERMISSION_MODE_ROWS:
        label, _, note = str(text).partition(" -- ")
        out.append({"id": mode, "label": label.strip(), "note": note.strip()})
    return out


def theme_rows() -> list:
    """3.3.12.0 R1: the eleven palettes of the registry, in its order, with the colours the terminal draws each in
    (tui/theme.py `variables_for`); the -daltonized / -ansi modifiers are Settings -> Themes' toggles. R2: then the
    enabled packs' palettes (`<pack-id>/<id>`)."""
    from halo_harness.themes.registry import all_ids
    from halo_harness.tui.theme import variables_for
    rows = []
    for name in all_ids():
        colours = variables_for(name)
        rows.append({"name": name, "palette": {short: colours.get(long, "") for short, long in PALETTE_KEYS}})
    return rows


def model_list(state_dir=None, cwd=None) -> list:
    """The Models panel's rows (the configured providers' catalog, the best-at line), the fields the block shows;
    3.3.0.0 R3: from what is cached, no host probed (`model_rows(cached=True)`)."""
    from halo_harness.studio import model as M
    try:
        rows = M.model_rows(state_dir, cwd, cached=True)
    except Exception:
        rows = []
    out = []
    for r in rows:
        if not isinstance(r, dict) or not r.get("ref"):
            continue
        best = r.get("best_at") if isinstance(r.get("best_at"), dict) else {}
        out.append({"ref": str(r["ref"]), "provider": str(r.get("provider") or ""), "label": str(r.get("detail") or r["ref"]),
                    "best_at": str(best.get("line") or ""), "price": str(r.get("price") or ""), "context": str(r.get("context") or ""),
                    "takes": list(r.get("takes") or ["?"]),  # 3.3.15.0 R2: what it takes (model_takes.py)
                    **({"effort": str(r["effort_word"])} if r.get("effort_word") else {}),  # 3.3.5.0 R0 (e): local rows only
                    **({k: r[k] for k in ("card", "fit") if isinstance(r.get(k), dict)})})  # 3.3.5.0 R0b
    return out


from halo_harness.crew.changes_map import ONE_MODEL  # noqa: E402  the Map step's "One model for everything" row


def map_rows(cwd=None, state_dir=None) -> list:
    """The Map step's rows (3.6.0.0 R5, the Team step before): One model for everything first, then every map, nearest
    first (yours, this project's, the starters); `active` marks the one new sessions run on, `default` the starter
    map while no `crew.map` is set."""
    from halo_harness.crew import store
    from halo_harness.crew.compile import DEFAULT_MAP, in_use
    used, source = in_use(None, cwd)
    # 3.6.0.0 R5 fix (M6): "One model for everything" (roles off, no map), the choice the Team step had
    rows, seen = [{"name": ONE_MODEL, "label": "One model for everything", "scope": "",
                   "description": "No map: main does every job on your model and hands nothing off (roles off).",
                   "boxes": 0, "lines": 0, "active": source == "none", "default": False}], set()
    for r in store.rows("map", cwd=cwd, state_dir=state_dir):
        if r["name"] in seen:
            continue
        seen.add(r["name"])
        rows.append({"name": r["name"], "label": r["name"], "scope": r["_scope"], "description": str(r.get("about") or ""),
                     "boxes": len(r.get("boxes") or []), "lines": len(r.get("lines") or []), "active": r["name"] == used,
                     "default": source == "default" and r["name"] == DEFAULT_MAP})
    return rows


def team_block(cwd=None, state_dir=None) -> dict:
    """The Map step (its block id stays `team`: `halo setup team`, `?block=team`): the map in use and every map."""
    from halo_harness.crew.compile import in_use
    name, source = in_use(None, cwd)
    return {"active": name or ONE_MODEL, "source": source, "maps": map_rows(cwd, state_dir)}


def setup_state(cwd=None, state_dir=None) -> dict:
    from halo_harness.studio.setup_check_state import check_blocks
    from halo_harness.studio.setup_providers_state import provider_blocks
    from halo_harness.theme import DEFAULT_THEME
    return {"model": _config("model"), "permission_mode": _config("permission_mode"), "theme": _config("theme"),
            "theme_default": DEFAULT_THEME, "themes": theme_rows(), "permission_modes": permission_rows(),
            "team": team_block(cwd, state_dir), "models": model_list(state_dir, cwd), **provider_blocks(cwd, state_dir),
            **check_blocks(cwd, state_dir)}


# 3.3.0.0 R5 (Ollama everywhere): `ollama_discover` {ports, subnets, scan, measure} rides in the state -- the ports Find
# asks, the subnets Scan adds and the latest scan / measure frames (studio/setup_discover_api.py discover_block).
_setup_state_before_r5 = setup_state


def setup_state(cwd=None, state_dir=None) -> dict:  # noqa: F811  (the state above plus the R5 block)
    from halo_harness.studio.setup_discover_api import discover_block
    from halo_harness.studio.setup_done import setup_done_at  # 3.3.3.0 R1: when the Summary's Done was last pressed
    from halo_harness.studio.setup_packs_api import pack_blocks  # 3.3.11.0 R3: the enabled packs' own Setup blocks
    from halo_harness.studio.init_waiting import waiting  # 3.3.15.0 R6: a `halo init` terminal waits for Done
    return {**_setup_state_before_r5(cwd, state_dir), "ollama_discover": discover_block(), "home": home_id(state_dir),
            "done_at": setup_done_at(state_dir), "packs": pack_blocks(cwd, state_dir), "init_waiting": bool(waiting(state_dir))}


def home_id(state_dir=None) -> str:
    """3.3.1.0 R1: a short hash of this home's state dir, the key Setup's page remembers its current step under
    (one browser can open Studios of several homes); never the path itself."""
    import hashlib
    from pathlib import Path

    from halo_harness.providers.config import default_state_dir
    where = Path(state_dir) if state_dir else Path(default_state_dir())
    return hashlib.sha256(str(where.resolve()).encode("utf-8", "replace")).hexdigest()[:12]
