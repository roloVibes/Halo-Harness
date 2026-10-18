"""halo_harness.schemas.yaml_files -- the shapes of the YAML files Halo reads:
a lineup (`~/.halo/teams/<name>.yaml`), an agent bio (`~/.halo/agents/<name>.yaml`),
a team file (`.halo/team.yaml`, `~/.halo/teams/<project>.team.yaml`) and a flow
(`~/.halo/flows/<name>.flow.yaml`, `.halo/flow.yaml`).

The key lists come from the loaders themselves (`teams_yaml.TOP_SECTIONS`,
`agents_yaml.IDENTITY_FIELDS` / `BIO_SECTIONS`, the keys `team.spec.normalize`
keeps), so a key a loader learns shows up here without a second edit. Each
schema checks the top level strictly (a key there that nothing reads is
reported) and the type of every section; what a value means is left to
`validate_team_template`, `validate_agent_bio`, `validate_team` and
`validate_flow`.
"""

from __future__ import annotations

from halo_harness.schemas.check import LIST, MAPPING, NUMBER, STRING, obj

_VERSION = {"type": ["string", "number"]}
_LIST_OF_MAPPINGS = {"type": "array", "items": MAPPING}


def lineup() -> dict:
    from halo_harness import teams_yaml as T
    props = {"name": STRING, "description": STRING, "version": _VERSION, "tags": LIST, "about": STRING,
             "extends": STRING, "agents": _LIST_OF_MAPPINGS, "roles": MAPPING}
    for section in T.TOP_SECTIONS:
        props[section] = LIST if section in T.LIST_SECTIONS else MAPPING
    return obj(props)


def bio() -> dict:
    from halo_harness import agents_yaml as A
    props = {"name": STRING, "description": STRING, "version": _VERSION, "tags": LIST, "kind": STRING,
             "extends": STRING}
    missing = [f for f in A.IDENTITY_FIELDS if f not in props]
    props.update({f: STRING for f in missing})
    for section in A.BIO_SECTIONS:
        props[section] = LIST if section == "triggers" else MAPPING
    return obj(props)


def team() -> dict:
    member = obj({"name": STRING, "lineup": STRING, "role": STRING, "harness": STRING})
    block = obj({"id": STRING, "kind": STRING, "path": STRING, "claims": STRING})
    stage = obj({"id": STRING, "kind": STRING, "members": {"type": ["array", "string"]},
                 "reads": {"type": ["array", "string"]}, "writes": {"type": ["array", "string"]},
                 "trigger": STRING, "lead": STRING, "gate": STRING, "acceptance": MAPPING,
                 "settle_s": NUMBER, "goal": {"type": ["string", "object"]}, "flow": STRING,
                 "inputs": MAPPING, "prompt": STRING})
    return obj({"name": STRING, "brief": STRING,
                "members": {"type": ["array", "string"], "items": {"type": ["object", "string"], **_inner(member)}},
                "blocks": {"type": ["array", "string"], "items": {"type": ["object", "string"], **_inner(block)}},
                "workflow": obj({"stages": {"type": ["array", "string"], "items": {"type": ["object", "string"], **_inner(stage)}}})})


def _inner(schema: dict) -> dict:
    return {"properties": schema["properties"], "additionalProperties": schema["additionalProperties"]}


def flow() -> dict:
    step = {"type": "object"}
    return obj({"name": STRING, "description": STRING, "version": _VERSION, "project": STRING,
                "budget_usd": NUMBER, "steps": {"type": "array", "items": step}})


SCHEMAS = {"lineup": lineup, "bio": bio, "team": team, "flow": flow}
