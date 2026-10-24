"""halo_harness.packs.workflow_stages -- the stage rules of a pack's workflow
file (Halo 3.2.0.0 R5, docs/WORKFLOWS.md "Stages"), one line each through
workflow_rules.Lines:

- an `id` (letters, digits, - and _), unique; a `brief` (what its worker does);
- `role`: a bio of the pack (by name, `<id>--<name>` or kind) or a bio Halo
  ships (`role_bio`); `needs`: capabilities the pack declares;
- `after` and `takes.from` name other stages and never go round in a circle;
  a `take` is all, summary or a name the upstream gives;
- `for_each` names a path input; `when` is on one input or one upstream
  output (`<stage>.<give>`), with one of exists, equals, not-empty;
- `gives` kinds are files, summary or artifact, each name once; `retries`
  0 or more, `timeout_s` 1 or more, `budget_usd` 0 or more; `gate` human or auto;
- `verify.evidence` names an output, a give of the stage or a path inside the
  repo; `after_event` is `<pack>:<kind>` (a kind of this pack's own events).

    stage_lines(L, data, manifest, root) -> {stage id: stage}   (the stages with a usable id)
    role_bio(manifest, root, role)       -> the bio a role runs as ('' when none)
"""

from __future__ import annotations

import re
from pathlib import Path

from halo_harness.packs import names as N

STAGE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,47}$")
GIVE_KINDS = ("files", "summary", "artifact")
BUILTIN_TAKES = ("all", "summary")
CONDITIONS = ("exists", "equals", "not-empty")
EVENT = re.compile(r"^([a-z][a-z0-9-]*):([a-z][a-z0-9_.-]*)$")


def pack_bios(manifest, root) -> "dict[str, str]":
    """`{bio name: kind}` for the pack's YAML bios (contributes.agents)."""
    from halo_harness.agents_yaml import _read_yaml_file
    out: "dict[str, str]" = {}
    items = ((manifest.get("contributes") or {}).get("agents") or []) if isinstance(manifest, dict) else []
    for rel in items if isinstance(items, list) else []:
        if isinstance(rel, str) and rel.endswith(".yaml") and root is not None:
            raw = _read_yaml_file(Path(root) / rel) or {}
            out[Path(rel).stem] = str(raw.get("kind") or "custom")
    return out


def shipped_bios() -> "list[str]":
    folder = Path(__file__).resolve().parent.parent / "templates" / "agents"
    return sorted(p.stem for p in folder.glob("*.yaml"))


def role_bio(manifest, root, role) -> str:
    """`<id>--<name>` for a pack bio (by name, qualified name or kind), the name of a shipped bio, else ''."""
    if not isinstance(role, str) or not role.strip():
        return ""
    role, pack_id = role.strip(), str((manifest or {}).get("id") or "")
    bios = pack_bios(manifest, root)
    own, name = N.unqualify(role)
    if own == pack_id and name in bios:
        return role
    if own is None and name in bios:
        return N.qualify(pack_id, name)
    kind = next((b for b, k in bios.items() if k == role), None)
    if kind:
        return N.qualify(pack_id, kind)
    return role if role in shipped_bios() else ""


def _deps(stages: dict) -> dict:
    return {sid: list(dict.fromkeys(_strs(s.get("after")) + [t.get("from") for t in s.get("takes") or []
                                                             if isinstance(t, dict) and t.get("from") in stages]))
            for sid, s in stages.items()}


def _strs(v) -> list:
    return [str(x) for x in v] if isinstance(v, list) else []


def _ids(L, data: dict) -> dict:
    stages: dict = {}
    for i, s in enumerate(data.get("stages") or [] if isinstance(data.get("stages"), list) else []):
        if not isinstance(s, dict):
            continue
        sid = s.get("id")
        if not isinstance(sid, str) or not STAGE_ID.match(sid):
            L.add(f"stages[{i}].id", f" {sid!r} is not a stage id (letters, digits, - and _)", "id", sid)
        elif sid in stages:
            L.add(f"stages[{i}].id", f" {sid!r} is used twice", "id", sid)
        else:
            stages[sid] = s
    if not stages and not isinstance(data.get("stages"), list):
        L.add("stages", ": required (one or more stages)", "stages")
    return stages


def _links(L, sid: str, s: dict, stages: dict, gives: dict) -> None:
    for a in _strs(s.get("after")):
        if a == sid:
            L.add(f"stages.{sid}.after", " names the stage itself", "after", a)
        elif a not in stages:
            L.add(f"stages.{sid}.after", f" {a!r} is not a stage of the workflow ({', '.join(stages)})", "after", a)
    for t in s.get("takes") or []:
        if not isinstance(t, dict):
            continue
        src, take = t.get("from"), str(t.get("take") or "")
        if src == sid or src not in stages:
            L.add(f"stages.{sid}.takes", f" from {src!r}: " + ("the stage itself" if src == sid else "not a stage"), "from", src)
        elif take not in BUILTIN_TAKES and take not in gives.get(src, {}):
            L.add(f"stages.{sid}.takes", f" {take!r} from {src}, which gives "
                  + (", ".join(gives.get(src) or ()) or "only its summary") + " (or use all / summary)", "take", take)


def _when(L, sid: str, s: dict, data: dict, stages: dict, ups: set, gives: dict) -> None:
    w = s.get("when")
    if not isinstance(w, dict):
        return
    key = f"stages.{sid}.when"
    if ("input" in w) == ("output" in w):
        L.add(key, ": a condition is on one input or one upstream output (input: or output:)", "when")
    elif "input" in w and w["input"] not in (data.get("inputs") or {}):
        L.add(f"{key}.input", f" {w['input']!r} is not an input of the workflow", "input", w["input"])
    elif "output" in w:
        stage, _, give = str(w["output"]).partition(".")
        if stage not in ups:
            L.add(f"{key}.output", f" {w['output']!r}: {stage!r} is not a stage {sid} runs after", "output", w["output"])
        elif give != "summary" and give not in gives.get(stage, {}):
            L.add(f"{key}.output", f" {w['output']!r}: {stage} does not give {give!r}", "output", w["output"])
    if sum(1 for c in CONDITIONS if c in w) != 1:
        L.add(key, f": say one of {', '.join(CONDITIONS)}", "when")


def _rest(L, sid: str, s: dict, data: dict, manifest, root, own_names: set) -> None:
    from halo_harness.orchestra.goal import _outside
    from halo_harness.packs.workflow_rules import capabilities
    if not str(s.get("brief") or "").strip():
        L.add(f"stages.{sid}.brief", ": required (what the stage's worker does)", "id", sid)
    if s.get("role") is not None and not role_bio(manifest, root, s.get("role")):
        L.add(f"stages.{sid}.role", f" {s.get('role')!r} is not a bio of the pack (by name or kind) "
              "nor a bio Halo ships", "role", s.get("role"))
    caps = set(capabilities(manifest))
    for c in _strs(s.get("needs")):
        if c not in caps:
            L.add(f"stages.{sid}.needs", f" {c!r} is not a capability the pack declares", "needs", c)
    each = s.get("for_each")
    name = each.get("input") if isinstance(each, dict) else each
    if each is not None and (data.get("inputs") or {}).get(name, {}).get("type") != "path":
        L.add(f"stages.{sid}.for_each", f" {name!r} is not a path input (one job per file under it)", "for_each")
    for k, lo in (("retries", 0), ("timeout_s", 1), ("budget_usd", 0)):
        v = s.get(k)
        if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float)) or v < lo):
            L.add(f"stages.{sid}.{k}", f" {v!r} is not a number {lo} or more", k, v)
    if s.get("gate") not in (None, "human", "auto"):
        L.add(f"stages.{sid}.gate", f" {s.get('gate')!r} is human or auto", "gate", s.get("gate"))
    verify = s.get("verify") if isinstance(s.get("verify"), dict) else {}
    for e in _strs(verify.get("evidence")):
        if e not in own_names and ("/" not in e and "." not in e or _outside(e)):
            L.add(f"stages.{sid}.verify.evidence", f" {e!r} is not an output, a give of {sid} or a path in the repo",
                  "evidence", e)
    if "test" in verify and not str(verify.get("test") or "").strip():
        L.add(f"stages.{sid}.verify.test", ": an empty command", "test")
    ev = s.get("after_event")
    m = EVENT.match(str(ev)) if ev is not None else None
    if ev is not None and not m:
        L.add(f"stages.{sid}.after_event", f" {ev!r} is not <pack>:<kind>", "after_event", ev)
    elif m and m.group(1) == (manifest or {}).get("id"):
        from halo_harness.packs.typed import event_kinds
        if m.group(2) not in event_kinds(manifest):
            L.add(f"stages.{sid}.after_event", f" {m.group(2)!r} is not one of the pack's contributes.events",
                  "after_event", ev)


def stage_lines(L, data: dict, manifest, root) -> dict:
    from halo_harness.orchestra.handoff_spec import reach
    stages = _ids(L, data)
    gives: "dict[str, dict]" = {}
    for sid, s in stages.items():
        gives[sid] = {}
        for g in s.get("gives") or []:
            if not isinstance(g, dict):
                continue
            if g.get("name") in gives[sid]:
                L.add(f"stages.{sid}.gives", f" {g.get('name')!r} twice", "name", g.get("name"))
            if g.get("kind") not in GIVE_KINDS:
                L.add(f"stages.{sid}.gives", f" {g.get('name')!r} has kind {g.get('kind')!r}; use files, summary or artifact",
                      "kind", g.get("kind"))
            gives[sid][g.get("name")] = g.get("kind")
    deps = _deps(stages)
    outputs = set((data.get("outputs") or {}).keys()) if isinstance(data.get("outputs"), dict) else set()
    for sid, s in stages.items():
        _links(L, sid, s, stages, gives)
        if sid in reach(deps, sid):
            L.add(f"stages.{sid}.after", f": {sid} waits for itself (its after and takes go round in a circle)", "id", sid)
        _when(L, sid, s, data, stages, reach(deps, sid), gives)
        _rest(L, sid, s, data, manifest, root, outputs | set(gives[sid]))
    return stages
