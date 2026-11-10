"""halo_harness.packs.lineup_run -- what a lineup says about the runs that
use it (Halo 3.2.0.0 R2, docs/PACKS.md "A pack's lineups").

A lineup's `acceptance` section already holds the smoke prompt `halo doctor
--teams` runs (`prompt`, `expect`). It also holds the Orchestra defaults a
run with this lineup starts with, under the Orchestra's own field names:

    acceptance:
      test: python -m pytest -q   # the goal's `test`: the command the gate runs
      review: true                # the goal's `plan: review`: pause after the split for the plan's review

`halo orchestra new --lineup L` takes them when you give no `--test` (and the
plan is still `auto`); what you type wins. `workflows: [<name>, ...]` names
the pack workflows the lineup runs (R5 runs them; in a pack's lineup each
name is one its pack.yaml declares, packs/bio_rules.py).

3.2.1.0 R2: an item is a `<pack>/<name>` ref, the way `halo workflow run`
names a workflow (`<pack>--<name>` reads the same), or a bare name, which
resolves inside its own pack: a pack's lineup's own, or the pack a clone of
yours came from (`from_pack: <id>@<version>`). The resolved lineup carries
`workflow_refs` beside `workflows` (which stays as written); in a lineup of
yours a ref no running pack holds is one line (`halo teams validate`).

    acceptance_problems(data, cwd=..., state_dir=...)  # one line per bad value (teams_yaml.validate_team_template)
    workflow_refs(raw)                      # ["<pack>/<name>", ...] (teams_yaml.resolve_team_template)
    resolved_workflows(pack, raw, cwd=, state_dir=)   # [{ref, found, line}]: inspect and the Pack Manager (3.3.10.0 R3)
    run_defaults(name, cwd=..., state_dir=...)  # {"test": "...", "review": True} (only what the lineup sets)
    goal_defaults(goal, cwd=..., explicit_test=False)  # fills an Orchestra Goal; the lines saying what it took
"""

from __future__ import annotations


def acceptance_problems(data, *, cwd=None, state_dir=None) -> "list[str]":
    if not isinstance(data, dict):
        return []
    out: "list[str]" = []
    flows = data.get("workflows")
    from halo_harness.workflows.when import item_ref, problems as when_problems  # 3.3.16.3: {ref, when} items
    if flows is not None and not (isinstance(flows, list) and all(item_ref(f) for f in flows)):
        out.append('"workflows" must be a list of workflow names (or {ref, when} mappings)')
    elif flows and not data.get("_pack"):  # 3.2.1.0 R2: a lineup of yours; a pack's is checked with its manifest
        out += _ref_problems([item_ref(f) for f in flows], cwd=cwd, state_dir=state_dir)
        out += [f'"workflows" {item_ref(f)!r}: {p}' for f in flows if isinstance(f, dict) for p in when_problems(f.get("when"))]
    acc = data.get("acceptance") if isinstance(data.get("acceptance"), dict) else {}
    if acc.get("test") is not None and not isinstance(acc.get("test"), str):
        out.append('"acceptance.test" must be a command (a string), the one the Orchestra gate runs')
    if acc.get("review") is not None and not isinstance(acc.get("review"), bool):
        out.append('"acceptance.review" must be true or false (pause for the plan\'s review)')
    return out


def _ref(item: str) -> tuple:
    from halo_harness.workflows.spec import split_ref
    return split_ref(item.strip())


def workflow_refs(raw) -> "list[str]":
    """A lineup file's `workflows` as `<pack>/<name>` refs; a bare name with no pack of its own has none."""
    flows = raw.get("workflows") if isinstance(raw, dict) else None
    if not isinstance(flows, list):
        return []
    own = str(raw.get("_pack") or "") or str(raw.get("from_pack") or "").partition("@")[0].strip()
    out = []
    from halo_harness.workflows.when import item_ref  # 3.3.16.3: an item may be {ref, when}
    for item in [item_ref(f) for f in flows]:
        if not item:
            continue
        pack_id, name = _ref(item)
        if pack_id or own:
            out.append(f"{pack_id or own}/{name if pack_id else item.strip()}")
    return list(dict.fromkeys(out))


def _own_workflow(pack, name: str) -> "dict | None":
    from halo_harness.packs.workflow_rules import read_workflow, workflow_files
    path = workflow_files(pack.manifest, pack.root).get(name)
    if path is None:
        return None
    data, _t = read_workflow(path)
    return data if isinstance(data, dict) else {}


def resolved_workflows(pack, raw, *, cwd=None, state_dir=None) -> "list[dict]":
    """3.3.10.0 R3: a pack lineup's `workflows`, each resolved through `workflow_refs`: `{ref, found, line}`, the line
    `<pack>/<name> -- <title>: <description>` (the title is the workflow's `name:`), or the item as written with
    "(not found)" when no pack knows it. The pack's own are read from its folder (inspect of a folder before it is
    installed resolves them too); another pack's must run here (workflows.spec.find)."""
    from halo_harness.workflows.spec import find
    flows = raw.get("workflows") if isinstance(raw, dict) else None
    out, seen = [], set()
    for item in [f for f in flows or [] if isinstance(f, str) and f.strip()] if isinstance(flows, list) else []:
        ref = workflow_refs({"workflows": [item], "_pack": pack.id})[0]
        if ref in seen:
            continue
        seen.add(ref)
        pack_id, _, name = ref.partition("/")
        if pack_id == pack.id:
            data = _own_workflow(pack, name)
        else:
            wf, _why = find(ref, cwd=cwd, state_dir=state_dir)
            data = wf.data if wf is not None else None
        if data is None:
            out.append({"ref": ref, "found": False, "line": f"{item.strip()} (not found)"})
            continue
        title, about = str(data.get("name") or name), str(data.get("description") or "").strip()
        out.append({"ref": ref, "found": True, "line": f"{ref} -- {title}" + (f": {about}" if about else "")})
    return out


def workflow_lines(lineup: dict) -> "list[str]":
    """`halo teams show`'s lines: the refs, and a bare name of a lineup with no pack of its own."""
    refs = list(lineup.get("workflow_refs") or []) if isinstance(lineup, dict) else []
    names = {r.partition("/")[2] for r in refs}
    from halo_harness.workflows.when import item_ref
    loose = [f for f in (item_ref(i) for i in lineup.get("workflows") or []) if f and not _ref(f)[0] and f not in names]
    out = [f"  workflows: {', '.join(refs)} (halo workflow run {refs[0]})"] if refs else []
    out += [f"  workflows: {f} names no pack: a lineup of yours names <pack>/{f}" for f in loose]
    from halo_harness.workflows.blocks_show import block_lines  # 3.3.16.3: each square block with its when line
    return out + block_lines(lineup)


def _ref_problems(flows: list, *, cwd=None, state_dir=None) -> "list[str]":
    """One line per `<pack>/<name>` item no running pack holds (spec.find's own words)."""
    from halo_harness.workflows.spec import find
    out = []
    for item in flows:
        if _ref(item)[0]:
            wf, why = find(item.strip(), cwd=cwd, state_dir=state_dir)
            if wf is None:
                out.append(f'"workflows" {item.strip()!r}: {why}')
    return out


def run_defaults(name: str, *, cwd=None, state_dir=None) -> dict:
    """The Orchestra defaults lineup `name` sets: `test` and `review`, each only when set."""
    from halo_harness.teams_yaml import resolve_team_template
    if not isinstance(name, str) or not name.strip():
        return {}
    lineup = resolve_team_template(name.strip(), cwd=cwd, state_dir=state_dir) or {}
    acc = lineup.get("acceptance") if isinstance(lineup.get("acceptance"), dict) else {}
    out: dict = {}
    if isinstance(acc.get("test"), str) and acc["test"].strip():
        out["test"] = acc["test"].strip()
    if isinstance(acc.get("review"), bool):
        out["review"] = acc["review"]
    return out


def goal_defaults(goal, *, cwd=None, state_dir=None, explicit_test: bool = False) -> "list[str]":
    """Fill an Orchestra `Goal` from its lineup's acceptance; what you gave wins. The lines say what was taken."""
    defaults = run_defaults(getattr(goal, "lineup", "") or "", cwd=cwd, state_dir=state_dir)
    lines: "list[str]" = []
    if defaults.get("test") and not explicit_test and not str(goal.test or "").strip():
        goal.test = defaults["test"]
        lines.append(f"test: {goal.test} (from lineup {goal.lineup}'s acceptance.test)")
    if defaults.get("review") and getattr(goal, "plan", "auto") == "auto":
        goal.plan = "review"
        lines.append(f"plan: review (lineup {goal.lineup}'s acceptance.review: the run pauses for the plan)")
    return lines
