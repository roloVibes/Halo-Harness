"""halo_harness.schemas.pack_yaml -- the shape of a pack's `pack.yaml` (Halo
3.2.0.0 R1, docs/EXTENSION_API.md "The manifest").

Strict at every level the manifest defines (a key nothing reads is
reported with the closest known key); `contributes.studio`,
`contributes.fleet` and `config.schema` / `config.defaults` are mappings
whose inside belongs to a later round or to the pack. What a value means
(an id, a semver, a range, a file that exists) is
`halo_harness.packs.manifest.validate_manifest`'s job. The machine-readable
twin is `halo_harness/packs/schema/pack.schema.json`; tests/test_packs_manifest.py
keeps the two equal.
"""

from __future__ import annotations

from halo_harness.schemas.check import LIST, MAPPING, STRING, obj

_VERSION = {"type": ["string", "number"]}
_RANGE = obj({"min": _VERSION, "max": _VERSION})
_NAMES = {"type": "array", "items": STRING}

TOP_KEYS = ("id", "name", "version", "description", "author", "license", "halo_api", "halo", "capabilities",
            "requires", "contributes", "config", "permissions", "migrations")
CONTRIBUTION_KEYS = ("agents", "teams", "skills", "commands", "hooks", "mcp", "studio", "fleet", "artifacts",
                     "events", "workflows")  # 3.2.0.0 R2: workflows (names a lineup's workflows may use; R5 runs them)


def pack() -> dict:
    author = {"type": ["string", "object"], "properties": {"name": STRING, "email": STRING, "url": STRING},
              "additionalProperties": False}
    requires = {"type": "array", "items": obj({"pack": STRING, "version": {"type": ["string", "number", "object"]}})}
    mcp_entry = {"type": "object", "properties": {"name": STRING, "description": STRING},
                 "additionalProperties": True}
    contributes = obj({"agents": _NAMES, "teams": _NAMES, "skills": STRING, "commands": STRING, "hooks": STRING,
                       "mcp": {"type": "array", "items": mcp_entry}, "studio": MAPPING, "fleet": MAPPING,
                       "artifacts": LIST, "events": _NAMES, "workflows": _NAMES})
    migration = obj({"from": _VERSION, "to": _VERSION, "note": STRING})
    props = {"id": STRING, "name": STRING, "version": STRING, "description": STRING, "author": author,
             "license": STRING, "halo_api": _RANGE, "halo": _RANGE, "capabilities": _NAMES, "requires": requires,
             "contributes": contributes, "config": obj({"schema": MAPPING, "defaults": MAPPING}),
             "permissions": _NAMES, "migrations": {"type": "array", "items": migration}}
    assert tuple(props) == TOP_KEYS and tuple(contributes["properties"]) == CONTRIBUTION_KEYS
    return obj(props)
