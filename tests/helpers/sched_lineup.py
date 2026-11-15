"""tests.helpers.sched_lineup -- Halo 3.3.7.0 R3: a map with local models for the scheduler's tests (3.6.0.0 R5b: a
map and its agents, where it was a lineup file).

    write(state, name, lanes) -> Path    <state>/crew/maps/<name>.yaml: main, and a box per lane with a line from main;
        each lane an agent file <state>/crew/agents/<lane>.yaml whose `model` is the lane's ref
"""
from __future__ import annotations

from pathlib import Path


def write(state, name: str, lanes: dict) -> Path:
    import yaml
    crew = Path(state) / "crew"
    (crew / "agents").mkdir(parents=True, exist_ok=True)
    (crew / "maps").mkdir(parents=True, exist_ok=True)
    for lane, ref in lanes.items():
        agent = {"format": "agent/1", "name": lane, "does": f"The {lane} lane of a test map.", "model": ref,
                 "uses": ["read"], "careful": "ask-changes"}
        (crew / "agents" / f"{lane}.yaml").write_text(yaml.safe_dump(agent, sort_keys=False), encoding="utf-8")
    data = {"format": "map/1", "name": name, "boxes": [{"id": lane, "agent": lane} for lane in lanes],
            "lines": [{"from": "main", "to": lane} for lane in lanes], "main": {"agent": "main"}}
    p = crew / "maps" / f"{name}.yaml"
    p.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return p
