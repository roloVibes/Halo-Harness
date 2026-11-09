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
            "requires", "contributes", "config", "permissions", "migrations", "bundle")  # bundle: 3.3.7.0 R5
CONTRIBUTION_KEYS = ("agents", "teams", "skills", "commands", "hooks", "mcp", "studio", "fleet", "artifacts",
                     "events", "workflows",  # 3.2.0.0 R2: workflows (names a lineup's workflows may use; R5 runs them)
                     "policy", "modes",  # 3.3.10.0 R1: policy hooks and the pack's runtime modes (packs/manifest_policy.py)
                     "setup",  # 3.3.11.0 R3: the pack's own Setup blocks (packs/manifest_setup.py)
                     "themes",  # 3.3.12.0 R2: the pack's own palettes (packs/manifest_themes.py)
                     "services")  # 3.3.13.0 R3: programs the supervisor keeps running (packs/manifest_services.py)
SERVICE_KEYS = ("name", "description", "run", "autostart", "restart", "health", "log")  # 3.3.13.0 R3
POLICY_KEYS = ("id", "run", "when", "impact", "on_error", "redact", "after")
SETUP_KEYS = ("id", "title", "kind", "after", "help", "fields", "run", "what", "cost", "time", "writes", "text")
MODE_KEYS = ("id", "label", "theme")
THEME_KEYS = ("id", "label", "posture", "palette")  # 3.3.12.0 R2
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
# 3.3.7.0 R5: `bundle` (packs/manifest_bundle.py: a pack with a resource claim)
BUNDLE_KEYS = ("needs", "reservation", "routing", "latency_budget_ms",
               "reservations", "schedule", "priority", "min_free_gb")  # 3.3.8.0 R4: several claims, hours, a floor
NEED_KEYS = ("any_of", "window", "device", "vision", "tools", "runtime")
RESERVATION_KEYS = ("model", "vram_gb", "keep_alive", "priority", "window", "host", "min_free_gb")  # 3.3.8.0 R4
SCHEDULE_KEYS = ("hours",)
OSES = ("windows", "linux", "mac")  # 3.3.12.0 R4: a tool requirement's install lines
ROUTING_KEYS = ("task_work", "never_evict", "escalation")


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


def bundle() -> dict:
    """3.3.7.0 R5: `bundle:` -- needs (role -> {any_of, window, device, ...}), reservation, routing, latency_budget_ms;
    3.3.8.0 R4: reservations (each with host? and min_free_gb?), schedule {hours}, priority, min_free_gb."""
    need = obj({"any_of": _NAMES, "window": INT, "device": STRING, "vision": BOOL, "tools": BOOL, "runtime": STRING})
    res = obj({"model": STRING, "vram_gb": NUMBER, "keep_alive": {"type": ["integer", "string"]}, "priority": STRING,
               "window": INT, "host": STRING, "min_free_gb": NUMBER})
    routing = obj({"task_work": STRING, "never_evict": STRING, "escalation": {"type": ["string", "boolean"]}})
    schedule = obj({"hours": STRING})
    props = {"needs": {"type": "object", "properties": {}, "additionalProperties": need}, "reservation": res,
             "routing": routing, "latency_budget_ms": INT, "reservations": {"type": "array", "items": res},
             "schedule": schedule, "priority": STRING, "min_free_gb": NUMBER}
    assert tuple(props) == BUNDLE_KEYS and tuple(need["properties"]) == NEED_KEYS
    assert tuple(res["properties"]) == RESERVATION_KEYS and tuple(routing["properties"]) == ROUTING_KEYS
    assert tuple(schedule["properties"]) == SCHEDULE_KEYS
    return obj(props)


def pack() -> dict:
    author = {"type": ["string", "object"], "properties": {"name": STRING, "email": STRING, "url": STRING},
              "additionalProperties": False}
    # 3.3.12.0 R4: an entry is a pack {pack, version} or a tool {kind, name, version, install, ...} (packs/manifest_requires.py)
    requires = {"type": "array", "items": obj({"pack": STRING, "version": {"type": ["string", "number", "object"]},
                                               "kind": STRING, "name": STRING, "install": obj({o: STRING for o in OSES}),
                                               "url": STRING, "license": STRING, "why": STRING, "used_by": _NAMES})}
    mcp_entry = {"type": "object", "properties": {"name": STRING, "description": STRING},
                 "additionalProperties": True}
    # 3.2.0.0 R5: an event is a kind or {kind, schema, description}; artifacts are schema names (packs/typed.py)
    event = {"type": ["string", "object"], "properties": {"kind": STRING, "schema": STRING, "description": STRING},
             "additionalProperties": False}
    # 3.3.10.0 R1: a policy hook and a mode (packs/manifest_policy.py names each problem with its entry)
    policy = obj({"id": STRING, "run": {"type": ["string", "array"]}, "when": obj({"tools": _NAMES, "modes": _NAMES}),
                  "impact": STRING, "on_error": STRING, "redact": _NAMES, "after": BOOL})
    mode = obj({"id": STRING, "label": STRING, "theme": STRING})
    assert tuple(policy["properties"]) == POLICY_KEYS and tuple(mode["properties"]) == MODE_KEYS
    # 3.3.11.0 R3: a Setup block (packs/manifest_setup.py names each problem with its entry)
    setup = obj({"id": STRING, "title": STRING, "kind": STRING, "after": STRING, "help": STRING, "fields": _NAMES,
                 "run": {"type": ["string", "array"]}, "what": STRING, "cost": STRING, "time": STRING, "writes": STRING,
                 "text": STRING})
    assert tuple(setup["properties"]) == SETUP_KEYS
    theme = obj({"id": STRING, "label": STRING, "posture": STRING, "palette": MAPPING})  # 3.3.12.0 R2: packs/manifest_themes.py
    assert tuple(theme["properties"]) == THEME_KEYS
    service = obj({"name": STRING, "description": STRING, "run": {"type": ["string", "array"]}, "autostart": BOOL,
                   "restart": STRING, "health": obj({"file": STRING, "url": STRING, "max_age_s": NUMBER}, strict=False),
                   "log": STRING})  # 3.3.13.0 R3: packs/manifest_services.py names each problem with its entry
    assert tuple(service["properties"]) == SERVICE_KEYS
    contributes = obj({"agents": _NAMES, "teams": _NAMES, "skills": STRING, "commands": STRING, "hooks": STRING,
                       "mcp": {"type": "array", "items": mcp_entry}, "studio": studio(), "fleet": fleet(),
                       "artifacts": _NAMES, "events": {"type": "array", "items": event}, "workflows": _NAMES,
                       "policy": {"type": "array", "items": policy}, "modes": {"type": "array", "items": mode},
                       "setup": {"type": "array", "items": setup}, "themes": {"type": "array", "items": theme},
                       "services": {"type": "array", "items": service}})
    migration = obj({"from": _VERSION, "to": _VERSION, "note": STRING, "settings": MAPPING})  # settings: 3.2.0.0 R7 renames
    props = {"id": STRING, "name": STRING, "version": STRING, "description": STRING, "author": author,
             "license": STRING, "halo_api": _RANGE, "halo": _RANGE, "capabilities": _NAMES, "requires": requires,
             "contributes": contributes, "config": obj({"schema": MAPPING, "defaults": MAPPING}),
             "permissions": _NAMES, "migrations": {"type": "array", "items": migration}, "bundle": bundle()}
    assert tuple(props) == TOP_KEYS and tuple(contributes["properties"]) == CONTRIBUTION_KEYS
    return obj(props)
