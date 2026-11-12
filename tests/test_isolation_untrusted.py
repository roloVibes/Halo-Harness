"""tests.test_isolation_untrusted -- an untrusted project's bio or lineup does not pick the owner's secrets or the
host (Halo 3.3.14.0 R2, REVIEW #10 PERMS-4; isolation/spec.py `untrusted_split` / `for_lane`, isolation/lines.py):

1. a project bio (repo/.halo/agents) asking for `secrets: {broker: env}`, an `environment.secrets` ref to a provider
   key, `pass_to_tools`, and `isolation: {image, mounts, user}` in a folder that is not trusted runs without them,
   and the lane's opt-in lines say what was not applied and why;
2. the same bio once the folder is trusted keeps them all;
3. a project lineup's `secrets` and isolation mounts are dropped the same way; a user-level bio keeps its keys.
The values are made up. No model is called; no container or broker runs (for_lane only reads the files).
Run: python -m tests.test_isolation_untrusted"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.isolation_rig import IsoEnv, run_with_lane  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
BIO = {"name": "coder", "description": "coder", "secrets": {"broker": "env"},
       "environment": {"secrets": [{"env": "BUILD_TOKEN", "ref": "ENV:OPENROUTER_API_KEY"}],
                       "pass_to_tools": ["BUILD_TOKEN"]},
       "isolation": {"mode": "container", "image": "example.invalid/img:1", "mounts": ["/:/host"]}}


def _project_file(repo: Path, kind: str, name: str, data: dict) -> None:
    d = repo / ".halo" / kind
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.yaml").write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _trust(e, repo: Path) -> None:
    from halo_harness.config.paths import normalize_cwd
    (e.state / "trust.json").write_text(json.dumps({normalize_cwd(repo): True}), encoding="utf-8")


@test
def test_an_untrusted_projects_bio_loses_the_keys_and_says_so(ctx: Ctx):
    from halo_harness.isolation import spec as S
    with IsoEnv() as e:
        e.lineup("crew", {"agents": [{"agent": "coder", "role": "subagent"}]})
        repo, run_dir, lane = run_with_lane(lineup="crew", bio="coder")
        _project_file(repo, "agents", "coder", BIO)
        opt = S.for_lane(run_dir, lane.job)
        ctx.check(f"no secrets, got {opt.secrets}", opt.secrets is None)
        iso = opt.isolation or {}
        ctx.check(f"no mounts and the default image, got {iso}", not iso.get("mounts")
                  and iso.get("image") != "example.invalid/img:1")
        # 3.4.1.2 (ENGINE-1): in an untrusted folder the project's bio is not read at all (project_gate.py); the split
        # it used to go through still holds for a project-sourced layer that reaches it
        bio = dict(BIO, _source="project")
        lines = [S.untrusted_split(bio, "bio coder")[1]]
        said = [ln for ln in lines if "not trusted yet" in ln]
        ctx.check(f"one line says what was not applied, got {lines}", len(said) == 1 and said[0].startswith("bio coder: ")
                  and all(k in said[0] for k in ("secrets", "environment.secrets", "environment.pass_to_tools",
                                                 "isolation.image", "isolation.mounts")))
        _trust(e, repo)
        opt = S.for_lane(run_dir, lane.job)
        ctx.check(f"trusted: the bio keeps its secrets, got {opt.secrets}", opt.secrets and opt.secrets["broker"] == "env"
                  and opt.secrets["refs"] == [("BUILD_TOKEN", "ENV:OPENROUTER_API_KEY")]
                  and opt.secrets["pass"] == ["BUILD_TOKEN"])
        ctx.check("and its mounts and image", (opt.isolation or {}).get("mounts") == ["/:/host"]
                  and opt.isolation.get("image") == "example.invalid/img:1" and not opt.dropped)


@test
def test_a_project_lineup_too_and_a_user_bio_keeps_its_keys(ctx: Ctx):
    from halo_harness.isolation import spec as S
    with IsoEnv() as e:
        e.bio("coder", {"secrets": {"broker": "env"},
                        "environment": {"secrets": [{"env": "SERVICE_TOKEN", "ref": "ENV:SERVICE_TOKEN"}]}})
        repo, run_dir, lane = run_with_lane(lineup="crew", bio="coder")
        _project_file(repo, "teams", "crew", {"name": "crew", "agents": [{"agent": "coder", "role": "subagent"}],
                                              "isolation": {"mode": "container", "mounts": ["/:/host"]},
                                              "secrets": {"broker": "1password", "account": "theirs"}})
        opt = S.for_lane(run_dir, lane.job)
        ctx.check(f"the user's bio keeps its broker, got {opt.secrets}", opt.secrets and opt.secrets["broker"] == "env"
                  and opt.secrets["by"] == "bio coder")
        ctx.check(f"the project lineup's mounts are not applied, got {opt.isolation}",
                  not (opt.isolation or {}).get("mounts"))
        from halo_harness.project_gate import note  # 3.4.1.2 (ENGINE-1): the untrusted lineup is not read at all
        ctx.check(f"the lineup is not used, and one line says why, got {opt.dropped} {note('teams', 'crew', repo)!r}",
                  not opt.dropped and "not trusted" in note("teams", "crew", repo))
        layer = {"name": "crew", "_source": "project", "isolation": {"mode": "container", "mounts": ["/:/host"]},
                 "secrets": {"broker": "1password", "account": "theirs"}}
        ctx.check("a project-sourced lineup layer still loses them", S.untrusted_split(layer, "lineup crew")[1]
                  .startswith("lineup crew: secrets, isolation.mounts not applied"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
