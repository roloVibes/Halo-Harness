"""halo_harness.crew.changes_steps -- a workflow's step changes, applied (Halo 3.6.0.0 R2; crew/changes.py).

    {op: step_add,    step: {...}, index: <1-based place> | None (the end)}
    {op: step_set,    index, fields: {name?, agents?, gets?, hands?, when?, repeat?}}   a field set to null goes
    {op: step_move,   index, to}
    {op: step_remove, index}
    {op: step_wf,     field: for | own_copy | max_usd, value}     (the workflow's own fields)

Indexes are 1-based, as the person reads them ("step 2"). A row whose index is not there leaves the file as it was;
crew/changes.py plan() then checks the whole file with workflow_problems before anything is written.
"""

from __future__ import annotations

import copy

from halo_harness.crew.store import step_clean


def _ok(steps: list, i) -> bool:
    return isinstance(i, int) and not isinstance(i, bool) and 1 <= i <= len(steps)


def apply_step(body: dict, op: dict) -> dict:
    body = copy.deepcopy(body)
    steps = list(body.get("steps") or [])
    o = op.get("op")
    if o == "step_add":
        at = op.get("index")
        s = step_clean(dict(op.get("step") or {}))
        if isinstance(at, int) and not isinstance(at, bool) and 1 <= at <= len(steps) + 1:
            steps.insert(at - 1, s)
        else:
            steps.append(s)
    elif o == "step_set" and _ok(steps, op.get("index")):
        s = dict(steps[op["index"] - 1])
        for k, v in (op.get("fields") or {}).items():
            if v in (None, "", [], {}):
                s.pop(k, None)
            else:
                s[k] = v
        steps[op["index"] - 1] = step_clean(s)
    elif o == "step_move" and _ok(steps, op.get("index")) and _ok(steps, op.get("to")):
        s = steps.pop(op["index"] - 1)
        steps.insert(op["to"] - 1, s)
    elif o == "step_remove" and _ok(steps, op.get("index")):
        steps.pop(op["index"] - 1)
    elif o == "step_wf":
        if op.get("value") in (None, "", []):
            body.pop(op["field"], None)
        else:
            body[op["field"]] = op["value"]
    body["steps"] = steps
    return body
