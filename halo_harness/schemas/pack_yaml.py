"""halo_harness.schemas.pack_yaml -- the shape of a pack's `pack.yaml` (Halo
3.2.0.0 R1, docs/EXTENSION_API.md "The manifest").

Strict at every level the manifest defines (a key nothing reads is
reported with the closest known key); `config.schema` / `config.defaults`
are mappings whose inside belongs to the pack. 3.2.0.0 R3: `contributes.studio`
is typed (`studio()`: sections, panels, palette, config_form, events,
attention; docs/EXTENSION_API.md "Studio contributions"). 3.2.0.0 R4:
`contributes.fleet` is typed (`fleet()`: capabilities, inspector, mission;
"Fleet capabilities"); a capability's `requires` takes unknown keys here so
packs/fleet_rules.py names them with their line. 3.2.0.0 R5: `contributes.events`
entries are a kind or `{kind, schema, description}`, `contributes.artifacts`
schema names (packs/typed.py; a workflow file's shape is schemas/workflow_yaml.py). What a value means (an id, a
semver, a range, a file that exists, a panel kind) is
`halo_harness.packs.manifest.validate_manifest`'s job (packs/studio_rules.py
for the Studio part, packs/fleet_rules.py for the fleet part). The machine-readable twin is
`halo_harness/packs/schema/pack.schema.json`; tests/test_packs_manifest.py and
tests/test_packs_studio_contract.py keep the two equal.
"""

from __future__ import annotations

from halo_harness.schemas.check import BOOL, INT, MAPPING, NUMBER, STRING, obj

_VERSION = {"type": ["string", "number"]}
_RANGE = obj({"min": _VERSION, "max": _VERSION})
_NAMES = {"type": "array", "items": STRING}

TOP_KEYS = ("id", "name", "version", "description", "author", "license", "halo_api", "halo", "capabilities",
            "requires", "contributes", "config", "permissions", "migrations")
CONTRIBUTION_KEYS = ("agents", "teams", "skills", "commands", "hooks", "mcp", "studio", "fleet", "artifacts",
                     "events", "workflows")  # 3.2.0.0 R2: workflows (names a lineup's workflows may use; R5 runs them)
# 3.2.0.0 R3: contributes.studio
STUDIO_KEYS = ("sections", "panels", "palette", "config_form", "events", "attention")
PANEL_KEYS = ("id", "title", "kind", "source", "schema", "w", "h", "help", "columns", "links")  # schema: 3.2.0.0 R5 (artifact)
SECTION_KEYS = ("id", "title", "blurb", "help", "panels")
ANSWER_KEYS = ("a", "r", "s", "o")
# 3.2.0.0 R4: contributes.fleet
FLEET_KEYS = ("capabilities", "inspector", "mission")
CAPABILITY_KEYS = ("name", "description", "requires", "capacity")
REQUIRES_KEYS = ("tools", "runtimes", "platform", "hardware", "models", "grants", "locality")
HARDWARE_KEYS = ("gpu", "ram_gb")


def panel(section: bool = False) -> dict:
    """One `<panel>`; `section=True` adds the core section it sits in (`contributes.studio.panels[]`)."""
    link = obj({"label": STRING, "route": STRING, "url": STRING})
    props = {"id": STRING, "title": STRING, "kind": STRING, "source": STRING, "schema": STRING, "w": INT, "h": INT, "help": STRING,
             "columns": _NAMES, "links": {"type": "array", "items": link}}
    assert tuple(props) == PANEL_KEYS
    return obj({"section": STRING, **props} if section else props)


def studio() -> dict:
    section = obj({"id": STRING, "title": STRING, "blurb": STRING, "help": STRING,
                   "panels": {"type": "array", "items": panel()}})
    entry = obj({"id": STRING, "label": STRING, "action": STRING})
    event = obj({"label": STRING, "line": STRING})
    attention = obj({"label": STRING, "keys": obj({k: STRING for k in ANSWER_KEYS})})
    props = {"sections": {"type": "array", "items": section}, "panels": {"type": "array", "items": panel(True)},
             "palette": {"type": "array", "items": entry}, "config_form": BOOL,
             "events": {"type": "object", "properties": {}, "additionalProperties": event},
             "attention": {"type": "object", "properties": {}, "additionalProperties": attention}}
    assert tuple(props) == STUDIO_KEYS and tuple(section["properties"]) == SECTION_KEYS
    return obj(props)


def fleet() -> dict:
    hardware = obj({"gpu": {"type": ["boolean", "string"]}, "ram_gb": NUMBER})
    requires = obj({"tools": _NAMES, "runtimes": _NAMES, "platform": _NAMES, "hardware": hardware, "models": _NAMES,
                    "grants": _NAMES, "locality": _NAMES}, strict=False)  # an unknown key: fleet_rules' line
    cap = obj({"name": STRING, "description": STRING, "requires": requires, "capacity": obj({"parallel": INT})})
    props = {"capabilities": {"type": "array", "items": cap},
             "inspector": {"type": "array", "items": obj({"label": STRING, "source": STRING})},
             "mission": obj({"metadata": MAPPING})}
    assert tuple(props) == FLEET_KEYS and tuple(cap["properties"]) == CAPABILITY_KEYS
    assert tuple(requires["properties"]) == REQUIRES_KEYS and tuple(hardware["properties"]) == HARDWARE_KEYS
    return obj(props)


def pack() -> dict:
    author = {"type": ["string", "object"], "properties": {"name": STRING, "email": STRING, "url": STRING},
              "additionalProperties": False}
    requires = {"type": "array", "items": obj({"pack": STRING, "version": {"type": ["string", "number", "object"]}})}
    mcp_entry = {"type": "object", "properties": {"name": STRING, "description": STRING},
                 "additionalProperties": True}
    # 3.2.0.0 R5: an event is a kind or {kind, schema, description}; artifacts are schema names (packs/typed.py)
    event = {"type": ["string", "object"], "properties": {"kind": STRING, "schema": STRING, "description": STRING},
             "additionalProperties": False}
    contributes = obj({"agents": _NAMES, "teams": _NAMES, "skills": STRING, "commands": STRING, "hooks": STRING,
                       "mcp": {"type": "array", "items": mcp_entry}, "studio": studio(), "fleet": fleet(),
                       "artifacts": _NAMES, "events": {"type": "array", "items": event}, "workflows": _NAMES})
    migration = obj({"from": _VERSION, "to": _VERSION, "note": STRING, "settings": MAPPING})  # settings: 3.2.0.0 R7 renames
    props = {"id": STRING, "name": STRING, "version": STRING, "description": STRING, "author": author,
             "license": STRING, "halo_api": _RANGE, "halo": _RANGE, "capabilities": _NAMES, "requires": requires,
             "contributes": contributes, "config": obj({"schema": MAPPING, "defaults": MAPPING}),
             "permissions": _NAMES, "migrations": {"type": "array", "items": migration}}
    assert tuple(props) == TOP_KEYS and tuple(contributes["properties"]) == CONTRIBUTION_KEYS
    return obj(props)
