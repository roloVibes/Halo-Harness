"""halo_harness.schemas.yaml_files -- the shapes of the YAML files Halo reads:
a lineup (`~/.halo/teams/<name>.yaml`) and an agent bio (`~/.halo/agents/<name>.yaml`)
(3.4.0.0 B: the team file's shape left with it).

The key lists come from the loaders themselves (`teams_yaml.TOP_SECTIONS`,
`agents_yaml.IDENTITY_FIELDS` / `BIO_SECTIONS`), so a key a loader learns shows up here without a second edit. Each
schema checks the top level strictly (a key there that nothing reads is
reported) and the type of every section; what a value means is left to
`validate_team_template` and `validate_agent_bio`.
"""

from __future__ import annotations

from halo_harness.schemas.check import LIST, MAPPING, STRING, obj

_VERSION = {"type": ["string", "number"]}
_LIST_OF_MAPPINGS = {"type": "array", "items": MAPPING}
_WORD_OR_MAPPING = {"type": ["string", "object"]}  # 3.1.8.0 R5: `isolation: container` or its mapping


def lineup() -> dict:
    from halo_harness import teams_yaml as T
    props = {"name": STRING, "description": STRING, "version": _VERSION, "tags": LIST, "about": STRING,
             "extends": STRING, "agents": _LIST_OF_MAPPINGS, "roles": MAPPING,
             "workflows": LIST, "from_pack": STRING}  # 3.2.0.0 R2: a pack lineup's workflows; a clone's origin
    for section in T.TOP_SECTIONS:
        props[section] = LIST if section in T.LIST_SECTIONS else MAPPING
    props.update(isolation=_WORD_OR_MAPPING, secrets=MAPPING, tools=MAPPING)  # 3.1.8.0 R5 (T.OPT_IN_SECTIONS)
    return obj(props)


def bio() -> dict:
    from halo_harness import agents_yaml as A
    props = {"name": STRING, "description": STRING, "version": _VERSION, "tags": LIST, "kind": STRING,
             "extends": STRING, "from_pack": STRING}  # 3.2.0.0 R2: a clone's origin, `<id>@<version>`
    missing = [f for f in A.IDENTITY_FIELDS if f not in props]
    props.update({f: STRING for f in missing})
    for section in A.BIO_SECTIONS:
        props[section] = LIST if section == "triggers" else MAPPING
    props.update(isolation=_WORD_OR_MAPPING, secrets=MAPPING)  # 3.1.8.0 R5 (A.OPT_IN_SECTIONS)
    return obj(props)


def pack() -> dict:
    """A pack's pack.yaml (3.2.0.0 R1; the shape lives beside the manifest's own key lists)."""
    from halo_harness.schemas.pack_yaml import pack as shape
    return shape()


SCHEMAS = {"lineup": lineup, "bio": bio, "pack": pack}
