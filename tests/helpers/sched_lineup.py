"""tests.helpers.sched_lineup -- Halo 3.3.7.0 R3: a lineup file with local lanes for the scheduler's tests.

    write(state, name, lanes, warm=None) -> Path    <state>/teams/<name>.yaml: `roles:` main on the `general` bio,
        each lane `{agent: general, models: {preference: <ref>}}`; `warm:` when given
"""
from __future__ import annotations

from pathlib import Path


def write(state, name: str, lanes: dict, warm=None) -> Path:
    import yaml
    roles: dict = {"main": "general"}
    for lane, ref in lanes.items():
        roles[lane] = {"agent": "general", "models": {"preference": ref}}
    data = {"name": name, "description": f"{name}: a test lineup with local lanes", "version": 1, "roles": roles}
    if warm is not None:
        data["warm"] = warm
    d = Path(state) / "teams"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{name}.yaml"
    p.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return p
