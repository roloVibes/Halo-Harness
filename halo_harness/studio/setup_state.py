"""halo_harness.studio.setup_state -- what `GET setup/state` answers (Halo
3.3.0.0 R1, Studio's Setup section; docs/STUDIO-sections.md "Setup"): every
block's current value, read from the same places the terminal wizard reads
them, and the rows each block offers (the wizard's own lists).

    {model, permission_mode, theme, theme_default,
     themes: [{name, palette: {bg, surface, panel, text, muted, accent, ok, warn, bad, tool}}],
     permission_modes: [{id, label, note}],            init_cli._PERMISSION_MODE_ROWS
     team: {active, source, roles_enabled, lineups: [{name, label, scope, description, active, default}]},
     models: [{ref, provider, label, best_at, price, context}],   the Models panel's rows (studio/model.py), cached only
     model_notes: [lines],                            a configured Ollama host nothing read yet ("not read yet: Refresh")
     providers: {<name>: {label, set, source, tail, enabled, reachable, catalog_count, detail, host_hint, fields}},
     ollama, huggingface, local_models,               R2: studio/setup_providers_state.py
     checks, gym_models, card, last_check, linux_fixes, no_provider,   R3: studio/setup_check_state.py
     ollama_discover, home, done_at}                  R5; 3.3.1.0 R1 `home`: a 12-hex hash of the state dir;
                                                      3.3.3.0 R1 `done_at`: Setup's Done (studio/setup_done.py) or null

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
    """Every TUI theme name in the wizard's order (each base, then its -daltonized and -ansi twins) with the
    colours the terminal draws it in (tui/theme.py `variables_for`)."""
    from halo_harness.theme import _BASE_THEMES, _SUFFIXES
    from halo_harness.tui.theme import variables_for
    rows = []
    for base in _BASE_THEMES:
        for suffix in _SUFFIXES:
            name = base + suffix
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
                    **({"effort": str(r["effort_word"])} if r.get("effort_word") else {})})  # 3.3.5.0 R0 (e): local rows only
    return out


def lineup_rows(cwd=None, state_dir=None) -> list:
    """The Team step's rows (tui/dialogs/team_step_actions.py `_rows`): One model for everything, then every
    lineup with its scope; `active` marks the one in use, `default` the auto lineup while no `team:` is set."""
    from halo_harness import teams_yaml as T
    from halo_harness.lineup_choice import ONE_MODEL_WORD
    from halo_harness.lineup_default import DEFAULT_LINEUP, configured_team
    from halo_harness.roles import roles_mode_enabled
    from halo_harness.tui.dialogs.team_preview import ONE_MODEL_LABEL
    T.ensure_builtin_team_templates(state_dir=state_dir)
    off = not roles_mode_enabled()
    team = configured_team()
    rows = []
    for name in T.list_team_templates(cwd=cwd, state_dir=state_dir):
        found = T.find_team_template_path(name, cwd=cwd, state_dir=state_dir)
        raw = T.load_team_template_raw(name, cwd=cwd, state_dir=state_dir) or {}
        default = not off and team is None and name == DEFAULT_LINEUP
        rows.append({"name": name, "label": name, "scope": found[1] if found else "?", "description": str(raw.get("description") or ""),
                     "active": not off and (name == team or default), "default": default})
    one = {"name": ONE_MODEL_WORD, "label": ONE_MODEL_LABEL, "scope": "", "description": "the default model runs every job",
           "active": off or not any(r["active"] for r in rows), "default": False}
    return [one, *rows]


def team_block(cwd=None, state_dir=None) -> dict:
    from halo_harness.lineup_choice import ONE_MODEL_WORD
    from halo_harness.lineup_default import lineup_in_use
    from halo_harness.roles import roles_mode_enabled
    name, source = lineup_in_use()
    return {"active": name or ONE_MODEL_WORD, "source": source, "roles_enabled": bool(roles_mode_enabled()),
            "lineups": lineup_rows(cwd, state_dir)}


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
    return {**_setup_state_before_r5(cwd, state_dir), "ollama_discover": discover_block(), "home": home_id(state_dir),
            "done_at": setup_done_at(state_dir)}


def home_id(state_dir=None) -> str:
    """3.3.1.0 R1: a short hash of this home's state dir, the key Setup's page remembers its current step under
    (one browser can open Studios of several homes); never the path itself."""
    import hashlib
    from pathlib import Path

    from halo_harness.providers.config import default_state_dir
    where = Path(state_dir) if state_dir else Path(default_state_dir())
    return hashlib.sha256(str(where.resolve()).encode("utf-8", "replace")).hexdigest()[:12]
