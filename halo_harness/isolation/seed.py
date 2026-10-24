"""halo_harness.isolation.seed -- the scoped state dir an isolated worker runs on.

An isolated worker never sees the host's `~/.halo`: it gets
`<run>/state-<n>/` (mounted at `/root/.halo` in a container; named by
BRIDGE_STATE_DIR for a scoped user), seeded with what its `halo -p` needs:

- `config.json`: the host config's `CONFIG_KEYS` only, with every key whose
  name looks like a credential (key, token, secret, password, headers,
  authorization, cookie) dropped at any depth;
- `routes.json` the same way, and the model catalogs (`CATALOGS`) as they are;
- `teams/<lineup>.yaml` and `agents/<bio>.yaml`: the run's lineup and every
  bio it assigns plus the lane's own, resolved (`extends` folded in).

A credential reaches the worker only through its environment: a name in
the isolation's `env`, or a ref the secret broker reads at spawn.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Optional

CONFIG_KEYS = ("model", "team", "effort", "roles", "routing", "models", "ollama", "providers", "network", "agents",
               "local", "huggingface", "databricks", "openai")
CATALOGS = ("models.json", "models-dev.json", "anthropic-models.json", "huggingface-models.json", "openai-models.json")
_CREDENTIAL = re.compile(r"(?:^|[_-])(?:api[_-]?key|apikey|token|secret|passw(?:or)?d|authorization|cookie|headers|key"
                         r"|bearer|credentials?)(?:$|[_-])", re.IGNORECASE)


def state_dir_for(run_dir, lane_n: int) -> Path:
    return Path(run_dir) / f"state-{int(lane_n)}"


def without_credentials(value):
    """`value` with every mapping key that names a credential dropped, at any depth."""
    if isinstance(value, dict):
        return {k: without_credentials(v) for k, v in value.items() if not _CREDENTIAL.search(str(k))}
    if isinstance(value, list):
        return [without_credentials(v) for v in value]
    return value


def _json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write(path: Path, text: str) -> None:
    from halo_harness.privateio import write_private_atomic
    path.parent.mkdir(parents=True, exist_ok=True)
    write_private_atomic(path, text)


def _yaml(data: dict) -> str:
    import yaml
    clean = {k: v for k, v in data.items() if not str(k).startswith("_") and v is not None}
    clean.pop("extends", None)
    return yaml.safe_dump(clean, sort_keys=False, default_flow_style=False, allow_unicode=True)


def seed(run_dir, lane_n: int, *, lineup: str = "", bio: str = "", cwd=None, source: Optional[Path] = None) -> Path:
    """Write `<run>/state-<n>/` and answer its path. `source` is the host state dir (default: bridge_home())."""
    from halo_harness.config.paths import bridge_home
    src = Path(source) if source is not None else bridge_home()
    out = state_dir_for(run_dir, lane_n)
    out.mkdir(parents=True, exist_ok=True)
    host = _json(src / "config.json")
    _write(out / "config.json", json.dumps(without_credentials({k: host[k] for k in CONFIG_KEYS if k in host}), indent=2))
    if (src / "routes.json").is_file():
        _write(out / "routes.json", json.dumps(without_credentials(_json(src / "routes.json")), indent=2))
    for name in CATALOGS:
        if (src / name).is_file():
            shutil.copyfile(src / name, out / name)
    bios = {bio} if bio else set()
    if lineup:
        from halo_harness.teams_yaml import resolve_team_template
        tpl = resolve_team_template(lineup, cwd=cwd) or {}
        if tpl:
            _write(out / "teams" / f"{lineup}.yaml", _yaml(tpl))
            bios |= {e["agent"] for e in tpl.get("agents") or [] if isinstance(e, dict) and e.get("agent")}
    from halo_harness.agents_yaml import resolve_agent_bio
    for name in sorted(bios):
        data = resolve_agent_bio(name, cwd=cwd)
        if data:
            _write(out / "agents" / f"{name}.yaml", _yaml(data))
    return out
