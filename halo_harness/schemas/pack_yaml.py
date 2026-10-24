"""halo_harness.schemas.pack_yaml -- the shape of a pack's `pack.yaml` (Halo
3.2.0.0 R1, docs/EXTENSION_API.md "The manifest").

Strict at every level the manifest defines (a key nothing reads is
reported with the closest known key); `contributes.fleet` and
`config.schema` / `config.defaults` are mappings whose inside belongs to a
later round or to the pack. 3.2.0.0 R3: `contributes.studio` is typed
(`studio()`: sections, panels, palette, config_form, events, attention;
docs/EXTENSION_API.md "Studio contributions"). What a value means (an id, a
semver, a range, a file that exists, a panel kind) is
`halo_harness.packs.manifest.validate_manifest`'s job (packs/studio_rules.py
for the Studio part). The machine-readable twin is
`halo_harness/packs/schema/pack.schema.json`; tests/test_packs_manifest.py and
tests/test_packs_studio_contract.py keep the two equal.
"""

from __future__ import annotations

from halo_harness.schemas.check import BOOL, INT, LIST, MAPPING, STRING, obj

_VERSION = {"type": ["string", "number"]}
_RANGE = obj({"min": _VERSION, "max": _VERSION})
_NAMES = {"type": "array", "items": STRING}

TOP_KEYS = ("id", "name", "version", "description", "author", "license", "halo_api", "halo", "capabilities",
            "requires", "contributes", "config", "permissions", "migrations")
CONTRIBUTION_KEYS = ("agents", "teams", "skills", "commands", "hooks", "mcp", "studio", "fleet", "artifacts",
                     "events", "workflows")  # 3.2.0.0 R2: workflows (names a lineup's workflows may use; R5 runs them)
# 3.2.0.0 R3: contributes.studio
STUDIO_KEYS = ("sections", "panels", "palette", "config_form", "events", "attention")
PANEL_KEYS = ("id", "title", "kind", "source", "w", "h", "help", "columns", "links")
SECTION_KEYS = ("id", "title", "blurb", "help", "panels")
ANSWER_KEYS = ("a", "r", "s", "o")


def panel(section: bool = False) -> dict:
    """One `<panel>`; `section=True` adds the core section it sits in (`contributes.studio.panels[]`)."""
    link = obj({"label": STRING, "route": STRING, "url": STRING})
    props = {"id": STRING, "title": STRING, "kind": STRING, "source": STRING, "w": INT, "h": INT, "help": STRING,
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


def pack() -> dict:
    author = {"type": ["string", "object"], "properties": {"name": STRING, "email": STRING, "url": STRING},
              "additionalProperties": False}
    requires = {"type": "array", "items": obj({"pack": STRING, "version": {"type": ["string", "number", "object"]}})}
    mcp_entry = {"type": "object", "properties": {"name": STRING, "description": STRING},
                 "additionalProperties": True}
    contributes = obj({"agents": _NAMES, "teams": _NAMES, "skills": STRING, "commands": STRING, "hooks": STRING,
                       "mcp": {"type": "array", "items": mcp_entry}, "studio": studio(), "fleet": MAPPING,
                       "artifacts": LIST, "events": _NAMES, "workflows": _NAMES})
    migration = obj({"from": _VERSION, "to": _VERSION, "note": STRING})
    props = {"id": STRING, "name": STRING, "version": STRING, "description": STRING, "author": author,
             "license": STRING, "halo_api": _RANGE, "halo": _RANGE, "capabilities": _NAMES, "requires": requires,
             "contributes": contributes, "config": obj({"schema": MAPPING, "defaults": MAPPING}),
             "permissions": _NAMES, "migrations": {"type": "array", "items": migration}}
    assert tuple(props) == TOP_KEYS and tuple(contributes["properties"]) == CONTRIBUTION_KEYS
    return obj(props)
