"""halo_harness.where.halo_files -- Halo's own files for `halo config where`:
`~/.halo/config.json` (and a repo `.halo/config.json`, which nothing reads),
`routes.json`, the env file (names only), a repo `.env`, and the Databricks
team preset (`.halo/team.json` / `~/.halo/team.json`).

Precedence is read off the resolvers: the start model through
`doctor._effective_default_model`, the theme through `theme.resolve_theme`,
an env file name through `load_env_file`'s setdefault (a variable already in
the process environment keeps its value), the preset through
`team_config.team_config_path`.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from halo_harness.where.rows import display, json_keys, lose, make


def _config_rows(cwd: Path, state_dir: Path) -> list:
    path = state_dir / "config.json"
    keys, problem = json_keys(path) if path.is_file() else ([], "")
    rows = [make("config", path, "home", cwd=cwd, sets=sorted(keys),
                 note=problem or "Halo's own settings (halo config get / set)")]
    repo_cfg = cwd / ".halo" / "config.json"
    if repo_cfg.is_file():
        keys2, problem2 = json_keys(repo_cfg)
        rows.append(make("config", repo_cfg, "repo", cwd=cwd, sets=sorted(keys2), read=False, rank=2,
                         note=problem2 or "Halo reads only ~/.halo/config.json; these keys do nothing here"))
    routes = state_dir / "routes.json"
    if routes.is_file():
        keys3, problem3 = json_keys(routes)
        rows.append(make("config", routes, "home", cwd=cwd, sets=sorted(keys3), rank=3,
                         note=problem3 or "per-box model defaults (aliases, default, small, profiles)"))
    _model_and_theme(rows[0], cwd)
    return rows


def _load(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _model_and_theme(cfg_row: dict, cwd: Path) -> None:
    data = _load(Path(cfg_row["path"]))
    if isinstance(data.get("model"), str) and data["model"]:
        try:
            from halo_harness.doctor import _effective_default_model
            _model, origin = _effective_default_model(cwd, None)
        except Exception:
            origin = ""
        if origin and origin != "config.json's model":
            lose(cfg_row, "model", origin)
    theme = data.get("theme")
    if isinstance(theme, str):
        from halo_harness import theme as T
        chosen = T.resolve_theme(persisted_theme=theme, settings_theme=_settings_theme(cwd))
        if chosen != theme:
            var = next((v for v in T._ENV_VARS if T.is_valid_theme(os.environ.get(v))), "")
            lose(cfg_row, "theme", var or "settings.json theme")


def _settings_theme(cwd: Path):
    try:
        from halo_harness.config.settings import resolve_settings
        value = resolve_settings(cwd).raw.get("theme")
    except Exception:
        return None
    return value if isinstance(value, str) else None


def _env_names(path: Path) -> list:
    from halo_harness.providers.config import _parse_env_file
    return sorted(_parse_env_file(path))


def _env_rows(cwd: Path) -> list:
    from halo_harness.config.paths import env_compat, env_file_path, legacy_env_file_path
    from halo_harness.providers.config import _parse_env_file
    path = env_file_path()
    override = env_compat("ENV_FILE")
    row = make("env", path, "env", cwd=cwd, sets=_env_names(path) if path.is_file() else [],
               note=("HALO_ENV_FILE points here" if override else "provider keys, KEY=value; names shown, never values"))
    for name, value in _parse_env_file(path).items() if path.is_file() else ():
        if name in os.environ and os.environ[name] != value:
            lose(row, name, "the process environment")
    rows = [row]
    legacy = legacy_env_file_path()
    if not override and legacy.is_file():
        rows.append(make("env", legacy, "env", cwd=cwd, sets=_env_names(legacy), read=False, rank=2,
                         note="the pre-2.0.0 env file; halo init copied it forward once, Halo no longer reads it"))
    dot_env = cwd / ".env"
    if dot_env.is_file():
        rows.append(make("env", dot_env, "repo", cwd=cwd, sets=_env_names(dot_env), read=False, rank=3,
                         note="Halo does not read .env; a tool or server you start in this repo may"))
    return rows


def _preset_rows(cwd: Path, state_dir: Path) -> list:
    from halo_harness.team_config import team_config_path
    import contextlib
    import io
    with contextlib.redirect_stderr(io.StringIO()):
        chosen = team_config_path(cwd)
    rows = []
    for rank, (path, scope) in enumerate(((cwd / ".halo" / "team.json", "repo"),
                                          (cwd / ".rolo-claude" / "team.json", "repo"),
                                          (state_dir / "team.json", "home")), start=1):
        if rank == 2 and not path.is_file():
            continue
        keys, problem = json_keys(path) if path.is_file() else ([], "")
        row = make("team-preset", path, scope, cwd=cwd, sets=sorted(keys), rank=rank,
                   note=problem or "the shared Databricks preset (docs/DATABRICKS.md)")
        if path.is_file() and chosen and Path(chosen).resolve() != path.resolve():
            for key in row["sets"]:
                lose(row, key, display(chosen, cwd=cwd), str(chosen))
        rows.append(row)
    return rows


def halo_rows(cwd: Path, state_dir: Path) -> list:
    return _config_rows(cwd, state_dir) + _env_rows(cwd) + _preset_rows(cwd, state_dir)
