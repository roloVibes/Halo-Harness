"""tests.test_team_spec -- Halo 3.0.8.0 round R1: the team file
(halo_harness/team/spec.py, validate.py, validate_stages.py, resolve.py): where it is found
(the repo's `.halo/team.yaml` wins over `~/.halo/teams/<project>.team.yaml`),
the normalised shape with its defaults, the shipped template validating
clean, each problem's exact line, members by name / alias / tier, the
trigger-cycle check, the preflight's blocking findings per member, and a
team file beside the lineups never listing as a lineup. No model is called.

Run: python -m tests.test_team_spec
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers import team_rig as R  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _doc(**over) -> dict:
    doc = yaml.safe_load(R.TEAM)
    doc.update(over)
    return doc


@test
def test_find_load_and_the_normalised_shape(ctx: Ctx):
    from halo_harness.team import spec as S
    root, state = R.repo()
    team = S.load_team(root, state)
    ctx.check("the repo file is found", team["source"] == "repo" and Path(team["path"]) == root / ".halo" / "team.yaml"
              and Path(team["root"]) == root)
    ctx.check("members keep name/lineup/role/harness", team["members"][2] == {"name": "remote", "lineup": "standard",
                                                                             "role": "coder", "harness": "kali"}
              and team["members"][0]["harness"] is None)
    draft = S.stage_by_id(team, "draft")
    ctx.check(f"a stage's keys and defaults, got {sorted(draft)}", set(draft) == {
        "id", "kind", "members", "reads", "writes", "trigger", "lead", "gate", "acceptance", "settle_s", "goal", "flow",
        "inputs", "prompt"} and draft["settle_s"] == 20 and draft["goal"] is None and draft["flow"] is None)
    ctx.check("the lead defaults to the first member", S.stage_lead(team, draft, S.stage_members(team, draft)) == "writer")
    bare = S.normalize({"blocks": [{"id": "a", "kind": "git", "path": "."}, {"id": "b", "path": "x/"}],
                        "workflow": {"stages": [{"id": "s"}]}, "members": [{"name": "m", "lineup": "l", "harness": "here"}]})
    ctx.check("claims default to file for git, section for a folder",
              [b["claims"] for b in bare["blocks"]] == ["file", "section"] and bare["blocks"][1]["kind"] == "folder")
    ctx.check("a stage defaults to agent, manual, gate none; harness 'here' is null",
              bare["workflow"]["stages"][0]["kind"] == "agent" and bare["workflow"]["stages"][0]["trigger"] == "manual"
              and bare["workflow"]["stages"][0]["gate"] == "none" and bare["members"][0]["harness"] is None
              and bare["members"][0]["role"] == "main")
    (root / ".halo" / "team.yaml").unlink()
    ctx.check("no repo file and no user file: None", S.load_team(root, state) is None)
    user = S.user_team_path(root, state)
    user.parent.mkdir(parents=True, exist_ok=True)
    user.write_text(R.TEAM, encoding="utf-8")
    team = S.load_team(root, state)
    ctx.check(f"the user file <project>.team.yaml is next, got {team and team['path']}",
              team is not None and team["source"] == "user" and user.name == f"{root.name}.team.yaml")
    (root / ".halo" / "team.yaml").write_text("name: [", encoding="utf-8")
    try:
        S.load_team(root, state)
        ctx.check("a broken file raises", False)
    except ValueError as e:
        ctx.check(f"a broken repo file wins and raises a plain line, got {e}", "is not valid YAML" in str(e))


@test
def test_the_rig_and_the_shipped_template_validate_clean(ctx: Ctx):
    from halo_harness.team import spec as S
    root, state = R.repo()
    ctx.check("the rig's team has no problem", S.validate_team(S.load_team(root, state), cwd=root, state_dir=state) == [])
    root2, state2 = R.repo(S.template_text())
    problems = S.validate_team(S.load_team(root2, state2), cwd=root2, state_dir=state2)
    ctx.check(f"the shipped template validates clean, got {problems}", problems == [])


@test
def test_each_problem_has_its_line(ctx: Ctx):
    from halo_harness.team import spec as S
    root, state = R.repo()
    (root / "afile").write_text("x", encoding="utf-8")
    doc = _doc(brief="docs/NOPE.md", members=[
        {"name": "writer", "lineup": "standard"}, {"name": "writer", "lineup": "standard"},
        {"name": "ghost", "lineup": "no-such-lineup"}, {"name": "odd", "lineup": "standard", "role": "nobody"}],
        blocks=[{"id": "copy", "kind": "folder", "path": "content/"}, {"id": "copy", "kind": "folder", "path": "c2/"},
                {"id": "brief", "path": "b/"}, {"id": "bad", "kind": "disk", "path": "d/", "claims": "rows"},
                {"id": "out", "path": "../elsewhere"}, {"id": "f", "kind": "file", "path": "content"},
                {"id": "g", "kind": "folder", "path": "afile"}],
        workflow={"stages": [
            {"id": "a", "members": ["stranger"], "writes": ["copy"], "reads": ["nothing"], "gate": "maybe",
             "trigger": "block_change:copy", "lead": "editor"},
            {"id": "b", "trigger": "stage_done:c", "writes": ["missing"]},
            {"id": "c", "trigger": "stage_done:c"},
            {"id": "d", "trigger": "whenever"},
            {"id": "e", "trigger": "block_change:nope"},
            {"id": "o", "kind": "orchestra"},
            {"id": "o2", "kind": "orchestra", "goal": {"what": "x", "done_when": "y", "workers": 99}},
            {"id": "fl", "kind": "flow", "flow": "no-such-flow"},
            {"id": "k", "kind": "robot"}]})
    doc["root"] = str(root)
    lines = S.validate_team(doc, cwd=root, state_dir=state)
    want = ["brief docs/NOPE.md does not exist yet", "member `writer` is listed twice",
            "member `ghost`: lineup `no-such-lineup` does not exist", "member `odd`: lineup `standard` has no alias `nobody`",
            "block `copy` is declared twice", "block id `brief` is taken", "block `bad`: kind is file, folder or git",
            "block `bad`: claims is section, file or none", "block `out`: path '../elsewhere' must be relative",
            "block `f`: content is a folder", "block `g`: afile is a file",
            "stage `a`: `stranger` is no member, alias or tier", "stage `a`: lead `editor` is not one of its members",
            "stage `a`: reads `nothing`, which is no declared block", "stage `b`: writes `missing`, which is no declared block",
            "stage `a`: gate is required, optional or none", "stage `b`: trigger `stage_done:c` names a later stage",
            "stage `c`: trigger `stage_done:c` names the stage itself", "stage `d`: trigger is manual, block_change",
            "stage `e`: trigger `block_change:nope` names no declared block",
            "stage `o`: an orchestra stage needs a goal", "stage `o2`: goal: \"workers\" must be a whole number",
            "stage `fl`: no flow `no-such-flow`", "stage `k`: kind is agent, orchestra or flow",
            "triggers loop: `a` -> `a`"]
    for w in want:
        ctx.check(f"a line starts with {w!r}", any(line.startswith(w) for line in lines), )
    ctx.check(f"nothing else, got {len(lines)} lines for {len(want)} wanted: {lines}", len(lines) == len(want))
    ctx.check("not a mapping", S.validate_team([1], cwd=root) == [
        "the team file is a mapping with name, brief, members, blocks and workflow"])


@test
def test_a_cycle_through_two_blocks_and_the_graph(ctx: Ctx):
    from halo_harness.team import spec as S
    from halo_harness.team.validate_stages import edges, find_cycle
    root, state = R.repo()
    doc = _doc(workflow={"stages": [
        {"id": "a", "writes": ["copy"], "trigger": "block_change:site"},
        {"id": "b", "writes": ["site"], "trigger": "block_change:copy"},
        {"id": "c", "trigger": "stage_done:a"}]})
    doc["root"] = str(root)
    team = S.normalize(doc)
    ctx.check(f"the edges, got {edges(team)}", edges(team) == {"a": {"b", "c"}, "b": {"a"}, "c": set()})
    ctx.check("the cycle is a -> b -> a", find_cycle(edges(team)) == ["a", "b", "a"])
    lines = S.validate_team(doc, cwd=root, state_dir=state)
    ctx.check(f"one loop line, got {lines}", lines == ["triggers loop: `a` -> `b` -> `a` (each start would start the "
                                                        "next again); break the loop with a manual trigger"])


@test
def test_members_by_name_alias_and_tier(ctx: Ctx):
    from halo_harness.team import spec as S
    root, state = R.repo()
    teams = state / "teams"
    teams.mkdir(parents=True, exist_ok=True)
    (teams / "stacked.yaml").write_text(yaml.safe_dump({"name": "stacked", "agents": [
        {"agent": "default-model", "role": "main"}, {"agent": "default-model", "role": "planner"},
        {"agent": "default-model", "role": "coder"}],
        "tiers": [{"name": "top", "members": ["main"]}, {"name": "leads", "members": ["planner"]},
                  {"name": "workers", "members": ["coder"]}]}), encoding="utf-8")
    doc = _doc(members=[{"name": "boss", "lineup": "stacked", "role": "main"},
                        {"name": "p1", "lineup": "stacked", "role": "planner"},
                        {"name": "c1", "lineup": "stacked", "role": "coder"},
                        {"name": "c2", "lineup": "stacked", "role": "coder"}],
               workflow={"stages": [{"id": "s1", "members": ["leads", "coder"], "writes": ["copy"]},
                                    {"id": "s2", "members": ["boss"]}]})
    doc["root"] = str(root)
    team = S.normalize(doc)
    team["root"] = str(root)
    got = S.stage_members(team, team["workflow"]["stages"][0], cwd=root, state_dir=state)
    ctx.check(f"a tier and an alias expand to members, got {got}", got == ["p1", "c1", "c2"])
    ctx.check("valid", S.validate_team(doc, cwd=root, state_dir=state) == [])


@test
def test_the_preflight_lines_per_member(ctx: Ctx):
    from halo_harness.team import spec as S
    from halo_harness.team.validate import preflight_findings
    from tests.helpers.preflight_seed import Home
    with Home() as h:
        root, _state = R.repo()
        doc = _doc(members=[{"name": "bad", "lineup": "pf-bad", "role": "main"},
                            {"name": "far", "lineup": "pf-bad", "role": "main", "harness": "kali"},
                            {"name": "good", "lineup": "pf-good", "role": "main"}],
                   workflow={"stages": [{"id": "s", "members": ["bad"], "writes": ["copy"]}]})
        doc["root"] = str(root)
        team = S.normalize(doc)
        team["root"] = str(root)
        found = preflight_findings(team, cwd=root, state_dir=h.state_dir)
        ids = {f["id"] for f in found}
        ctx.check(f"the bad lineup's findings, prefixed by the member, got {sorted(ids)}",
                  "bad/dead-model:worker" in ids and "bad/missing-bio:ghost" in ids and not any(i.startswith("far/") for i in ids))
        lines = S.validate_team(doc, cwd=root, state_dir=h.state_dir)
        pre = [l for l in lines if l.startswith("preflight: ")]
        ctx.check(f"validate_team lists each blocking finding with its fix, got {pre}",
                  pre and all("member `bad` (lineup `pf-bad`)" in l and " -- fix: " in l for l in pre)
                  and not any("dead-fallback" in l or "in no tier" in l for l in pre))
        ctx.check("preflight=False leaves them out",
                  not any(l.startswith("preflight: ") for l in S.validate_team(doc, cwd=root, state_dir=h.state_dir,
                                                                               preflight=False)))


@test
def test_a_team_file_beside_the_lineups_is_not_a_lineup(ctx: Ctx):
    from halo_harness.teams_yaml import list_team_templates
    _root, state = R.repo()
    teams = state / "teams"
    teams.mkdir(parents=True, exist_ok=True)
    (teams / "myproj.team.yaml").write_text(R.TEAM, encoding="utf-8")
    (teams / "mine.yaml").write_text("name: mine\nroles: {main: general}\n", encoding="utf-8")
    names = list_team_templates(state_dir=state)
    ctx.check(f"mine is a lineup, myproj.team is not, got {names}", "mine" in names and "myproj.team" not in names)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="team spec tests"))
