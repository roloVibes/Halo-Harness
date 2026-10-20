"""tests.test_review3_s2 -- pins for the 3.0.1.0 review fix pass, round
S-subagents-teams (part 2): review items 54, 123, 125 (item 124 pinned the
cc:/cx: scrub, removed in 3.1.5.0).

  * 54   a team bundle's bios are validated before anything is written, a
         bio named like a shipped one is reported as shadowing it, and a
         hand-edited bio with a non-mapping section never crashes a lineup
  * 123  a failed task_id resume leaves the original run's outcome alone
  * 125  a role-table value no spawn can resolve runs on the session model
         (the same answer /roles gives) and assign_role refuses to write it
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.test_review3_s import patched, scoped_home

test, TESTS = new_registry()


def _bundle(root: Path, team: dict, bios: dict) -> Path:
    import yaml
    d = root / "bundle"
    (d / "bios").mkdir(parents=True)
    (d / "bundle.json").write_text(json.dumps({"bundle": "halo-team", "version": 1, "name": team["name"],
                                               "bios": sorted(bios)}), encoding="utf-8")
    (d / "team.yaml").write_text(yaml.safe_dump(team, sort_keys=False), encoding="utf-8")
    for name, body in bios.items():
        text = body if isinstance(body, str) else yaml.safe_dump(body, sort_keys=False)
        (d / "bios" / f"{name}.yaml").write_text(text, encoding="utf-8")
    return d


# ---- 54: bundle_import validates bios and reports shadowed shipped ones --------


@test
def test_54_an_invalid_bio_refuses_the_whole_import(ctx: Ctx):
    from halo_harness.teams_bundle import bundle_import
    with scoped_home() as home:
        team = {"name": "bt", "agents": [{"agent": "reviewer", "role": "reviewer"}]}
        d = _bundle(home / "src", team, {
            "reviewer": {"name": "reviewer", "models": "not-a-mapping", "hooks": {"bogus_event": []}},
            "bad-bio": {"name": "bad-bio", "kind": "nonsense"},
            "stray": "- just\n- a list\n",
            "orphan": {"name": "orphan", "extends": "does-not-exist"},
        })
        ok, lines = bundle_import(d)
        text = "\n".join(lines)
        ctx.check(f"the import is refused, got {lines}", ok is False)
        for needle in ("bio reviewer", "bio bad-bio", "bio stray", "bio orphan"):
            ctx.check(f"the problems name {needle!r}", needle in text)
        agents = home / ".halo" / "agents"
        ctx.check("nothing was written to user scope", not agents.exists() or not list(agents.glob("*.yaml")))
        ctx.check("the team was not saved", not (home / ".halo" / "teams" / "bt.yaml").exists())


@test
def test_54_a_bundle_bio_named_like_a_shipped_one_is_reported(ctx: Ctx):
    from halo_harness.agents_yaml import find_agent_bio_path
    from halo_harness.teams_bundle import bundle_import
    with scoped_home() as home:
        team = {"name": "bt2", "agents": [{"agent": "orchestrator", "role": "main"},
                                          {"agent": "reviewer", "role": "reviewer"},
                                          {"agent": "child-bio", "role": "subagent"}]}
        d = _bundle(home / "src", team, {
            "reviewer": {"name": "reviewer", "description": "the bundle's reviewer", "kind": "reviewer",
                         "models": {"preference": "or:vendor/r"}, "_source": "x"},
            "child-bio": {"name": "child-bio", "extends": "parent-bio"},
            "parent-bio": {"name": "parent-bio", "models": {"preference": "or:vendor/p"}},
        })
        ok, lines = bundle_import(d)
        ctx.check(f"the import succeeds (bios that extend each other are fine), got {lines}", ok is True)
        ctx.check(f"a shadows-shipped line names reviewer, got {lines}",
                  any("shadows shipped" in l and "reviewer" in l for l in lines))
        found = find_agent_bio_path("reviewer")
        ctx.check(f"the bundle's reviewer is the one that resolves now, got {found}",
                  found is not None and found[1] == "user")
        import yaml
        written = yaml.safe_load(found[0].read_text(encoding="utf-8"))
        ctx.check(f"internal _ keys are dropped, got {sorted(written)}", "_source" not in written)


@test
def test_54_a_failed_team_save_restores_a_bio_force_overwrote(ctx: Ctx):
    from halo_harness.teams_bundle import bundle_import
    with scoped_home() as home:
        agents = home / ".halo" / "agents"
        agents.mkdir(parents=True)
        (agents / "mine.yaml").write_bytes(b"name: mine\ndescription: the LOCAL one\n")
        team = {"name": "bt3", "agents": "not-a-list"}
        d = _bundle(home / "src", team, {"mine": {"name": "mine", "description": "bundle one"}})
        ok, lines = bundle_import(d, force=True)
        ctx.check(f"a bad team refuses the import, got {lines}", ok is False)
        ctx.check("the overwritten bio got its previous bytes back",
                  (agents / "mine.yaml").read_bytes() == b"name: mine\ndescription: the LOCAL one\n")


@test
def test_54_a_hand_edited_bio_never_crashes_a_lineup(ctx: Ctx):
    from halo_harness.teams_yaml import member_system_context_addition, resolve_role_table
    with scoped_home() as home:
        agents = home / ".halo" / "agents"
        agents.mkdir(parents=True)
        (agents / "odd.yaml").write_text("name: odd\nmodels: just-a-string\ncontext: also-a-string\n",
                                         encoding="utf-8")
        template = {"name": "t", "agents": [{"agent": "odd", "role": "reviewer"}]}
        table, notes = resolve_role_table(template)
        ctx.check(f"the role table resolves with a note, got {table} {notes}",
                  "reviewer" not in table and any("not a mapping" in n for n in notes))
        ctx.check("member context is empty, not a crash", member_system_context_addition("odd") == "")


# ---- 123: a failed task_id resume keeps the original outcome ------------------


@test
def test_123_a_failed_resume_does_not_rewrite_the_original_meta(ctx: Ctx):
    from halo_harness.agent import subagent
    with scoped_home() as home:
        cwd = Path(tempfile.mkdtemp(prefix="r3s-cwd-"))
        parent = SimpleNamespace(log=SimpleNamespace(dir=home / "sessions", session_id="parent"), cwd=cwd,
                                 cost_meter=SimpleNamespace(total_usd=0.0), state_dir=home / ".halo")
        spec = SimpleNamespace(name="worker", role=None, dock_label=None)
        runtime = subagent.AgentRuntime(parent=parent, agents={"worker": spec})
        runtime.tasks["t1"] = {"spec_name": "worker", "child_session_id": "agent-abc"}
        _log, meta_path = subagent._child_log_paths(parent, "abc")
        meta_path.write_text(json.dumps({"status": "completed", "is_error": False, "finished": 1.0}),
                             encoding="utf-8")

        def boom(**_kw):
            raise ValueError("no such model")

        with patched(subagent, _build_child_session=boom):
            _evs, result = subagent._resume_task_claimed(runtime, "t1", {"model": "nosuch:zzz"}, "tool-1")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        ctx.check(f"the resume reports its failure, got {result.content!r}",
                  result.is_error and "Could not resume" in str(result.content))
        ctx.check(f"the original outcome is untouched, got {meta}",
                  meta.get("is_error") is False and meta.get("finished") == 1.0)
        ctx.check(f"the failed attempt is recorded beside it, got {meta}",
                  "no such model" in str(meta.get("last_resume_error")) and meta.get("last_resume_at"))


# ---- 125: an unresolvable role-table value -----------------------------------


@test
def test_125_spawn_and_roles_agree_on_an_unresolvable_table_value(ctx: Ctx):
    from halo_harness.config.agents_md import resolve_agent_model
    from halo_harness.model import ModelRef
    from halo_harness.roles import assign_role, configured_role_table, resolve_role_ref
    with scoped_home() as home:
        parent_ref = ModelRef(raw="or:vendor/main", provider="openrouter", model="vendor/main", dialect="openai-chat")
        parent_profile = object()
        table = {"coder": "nosuch:zzz", "subagent_default": "nosuch:yyy"}
        common = dict(role_table=table, parent_ref=parent_ref, parent_profile=parent_profile,
                      state_dir=home / ".halo")
        ref, prof = resolve_agent_model(role_name="coder", **common)
        ctx.check("a spawn on that role runs on the session model", ref is parent_ref and prof is parent_profile)
        ref2, _p = resolve_agent_model(role_name=None, **common)
        ctx.check("an unresolvable subagent_default does the same", ref2 is parent_ref)
        shown = resolve_role_ref("coder", role_table=table, parent_ref=parent_ref, parent_profile=parent_profile,
                                 state_dir=home / ".halo")
        ctx.check(f"/roles shows the same answer, got {shown[3]}", shown[0] is parent_ref and "session model" in shown[3])
        try:
            resolve_agent_model(role_name="coder", invocation_model="nosuch:zzz", **common)
            raised = False
        except Exception:
            raised = True
        ctx.check("an explicit model= on the call still fails loudly", raised)
        ok, problems = assign_role("coder", "nosuch:zzz")
        ctx.check(f"assign_role refuses a value that cannot resolve, got {(ok, problems)}", ok is False and problems)
        ctx.check("nothing was written", "coder" not in configured_role_table())
        ok2, problems2 = assign_role("coder", "inherit")
        ctx.check(f"inherit is still accepted, got {problems2}", ok2 is True)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
