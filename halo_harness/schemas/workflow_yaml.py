"""halo_harness.schemas.workflow_yaml -- the shape of a pack's workflow file,
`<pack>/workflows/<name>.yaml` (Halo 3.2.0.0 R5, docs/WORKFLOWS.md).

Strict at every level (a key nothing reads is reported with the closest
known key). What a value means (a stage a stage runs after, a role that is a
bio, an output some stage gives, an input's default of its type, a cycle) is
`halo_harness.packs.workflow_rules`' job, one manifest line each naming the
key and its line. The machine-readable twin is
`halo_harness/packs/schema/workflow.schema.json`; tests/test_workflow_schema.py
keeps the two equal.

    name, description, stop_when, done_when, budget_usd, checkpoint
    prerequisites: {tools, grants, capabilities, files}
    inputs:  {<name>: {type: text | path | json | artifact:<schema>, required, default, description}}
    outputs: {<name>: {type: artifact:<schema> | files | summary, from: <stage id>, description}}
    stages:  [{id, title, brief, role, needs, after, for_each, when, gives, takes, retries,
               timeout_s, budget_usd, gate: human | auto, verify: {test, evidence}, after_event}]
"""

from __future__ import annotations

from halo_harness.schemas.check import BOOL, INT, NUMBER, STRING, obj

_NAMES = {"type": "array", "items": STRING}
ANY = {}  # a value of any type (an input's default, a condition's `equals`)

TOP_KEYS = ("name", "description", "prerequisites", "inputs", "outputs", "stages", "done_when", "stop_when",
            "budget_usd", "checkpoint")
PREREQ_KEYS = ("tools", "grants", "capabilities", "files")
INPUT_KEYS = ("type", "required", "default", "description")
OUTPUT_KEYS = ("type", "from", "description")
STAGE_KEYS = ("id", "title", "brief", "role", "needs", "after", "for_each", "when", "gives", "takes", "retries",
              "timeout_s", "budget_usd", "gate", "verify", "after_event")
WHEN_KEYS = ("input", "output", "key", "exists", "equals", "not-empty")
GIVE_KEYS = ("name", "kind", "paths", "description")
TAKE_KEYS = ("from", "take")
VERIFY_KEYS = ("test", "evidence")
EACH_KEYS = ("input", "match")


def stage() -> dict:
    give = obj({"name": STRING, "kind": STRING, "paths": _NAMES, "description": STRING})
    take = obj({"from": STRING, "take": STRING})
    when = obj({"input": STRING, "output": STRING, "key": STRING, "exists": BOOL, "equals": ANY, "not-empty": BOOL})
    each = {"type": ["string", "object"], "properties": {"input": STRING, "match": STRING}, "additionalProperties": False}
    props = {"id": STRING, "title": STRING, "brief": STRING, "role": STRING, "needs": _NAMES, "after": _NAMES,
             "for_each": each, "when": when, "gives": {"type": "array", "items": give},
             "takes": {"type": "array", "items": take}, "retries": INT, "timeout_s": INT, "budget_usd": NUMBER,
             "gate": STRING, "verify": obj({"test": STRING, "evidence": _NAMES}), "after_event": STRING}
    assert tuple(props) == STAGE_KEYS and tuple(when["properties"]) == WHEN_KEYS
    assert tuple(give["properties"]) == GIVE_KEYS and tuple(take["properties"]) == TAKE_KEYS
    return obj(props)


def workflow() -> dict:
    inp = obj({"type": STRING, "required": BOOL, "default": ANY, "description": STRING})
    out = obj({"type": STRING, "from": STRING, "description": STRING})
    props = {"name": STRING, "description": STRING,
             "prerequisites": obj({"tools": _NAMES, "grants": _NAMES, "capabilities": _NAMES, "files": _NAMES}),
             "inputs": {"type": "object", "properties": {}, "additionalProperties": inp},
             "outputs": {"type": "object", "properties": {}, "additionalProperties": out},
             "stages": {"type": "array", "items": stage()}, "done_when": STRING, "stop_when": STRING,
             "budget_usd": NUMBER, "checkpoint": BOOL}
    assert tuple(props) == TOP_KEYS and tuple(props["prerequisites"]["properties"]) == PREREQ_KEYS
    assert tuple(inp["properties"]) == INPUT_KEYS and tuple(out["properties"]) == OUTPUT_KEYS
    return obj(props)
