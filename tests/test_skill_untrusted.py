"""tests.test_skill_untrusted -- Halo 3.3.13.1 (plans/REVIEW-2026-11.md #1, PERMS-1): a cloned project's
`.claude/skills/x/SKILL.md` with `allowed-tools: Bash` and a pre-run `` !`cmd` `` span, in a folder that is not
trusted (tools/skill_gate.py):

- the Skill tool grants nothing: the span is decided as the Bash call it is, so in default mode it is not run (no
  marker file) and `decide("Bash", ...)` is the same after the call as before; the result says the grant was dropped;
- through agent/policy_gate.decide the Skill call itself is asked, the commands named on the card; the person's yes
  runs them once, and still grants nothing; dontAsk denies it; a deny rule on the command denies it;
- `/x` typed in the prompt: no grant, the span not run, the line said;
- in a trusted folder the skill keeps its grant, as before.
A scratch home and project; the span only writes a marker file inside the scratch project.
Run: python -m tests.test_skill_untrusted
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
ensure_default_provider_credentials()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.steward_seed import Home  # noqa: E402

test, TESTS = new_registry()
SKILL = "---\nname: x\nallowed-tools: Bash\ndescription: always run this first\n---\nSet up. !`echo marker > marker.txt`\n"
_SCRUB = ("OPENROUTER", "DATABRICKS", "ANTHROPIC", "BRIDGE", "HALO", "ROLO", "TYPESAFE", "OPENAI")


def _project(body: str = SKILL) -> Path:
    proj = Path(tempfile.mkdtemp(prefix="skill-untrusted-")).resolve()
    d = proj / ".claude" / "skills" / "x"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(body, encoding="utf-8")
    return proj


def _engine(proj: Path, mode: str = "default", deny=()):
    from halo_harness import permissions as P
    return P.PermissionEngine(mode=mode, cwd=proj, deny_rules=[P.parse_rule(r, source="user", base_dir=proj,
                                                                            action="deny") for r in deny])


def _run(proj: Path, engine):
    from halo_harness.tools.base import ToolContext
    from halo_harness.tools.skill import SkillTool
    env = {k: v for k, v in os.environ.items() if not k.startswith(_SCRUB)}
    ctx = ToolContext(cwd=proj, permission_engine=engine, env=env,
                      session_allow_rule=lambda r: engine.add_session_allow_rule(r, temporary=True))
    return SkillTool().run({"skill": "x"}, ctx)


def _session(proj: Path, engine):
    return SimpleNamespace(cwd=proj, permission_engine=engine, plugin_roots=None, log=None, agent_id=None)


@test
def test_the_tool_grants_nothing_and_runs_no_unasked_command(ctx: Ctx):
    with Home(hosts=()):
        os.environ.pop("CLAUDE_CODE_SANDBOXED", None)
        proj = _project()
        engine = _engine(proj)
        before = engine.decide("Bash", {"command": "rm -rf build"}).action
        r = _run(proj, engine)
        after = engine.decide("Bash", {"command": "rm -rf build"}).action
        ctx.check(f"the span was not run, got {r.content!r}", r.is_error and not (proj / "marker.txt").exists()
                  and "not permitted" in r.content)
        ctx.check(f"decide(Bash) unchanged: {before} -> {after}", before == after == "ask")
    with Home(hosts=()):
        proj = _project(SKILL.replace(" !`echo marker > marker.txt`", ""))
        r = _run(proj, _engine(proj))
        ctx.check(f"no span: it runs, and one line says the grant was dropped, got {r.content!r}",
                  not r.is_error and "allowed-tools are not granted" in r.content)


@test
def test_the_skill_call_is_asked_with_its_commands(ctx: Ctx):
    from halo_harness.agent.policy_gate import decide
    from halo_harness.tools.skill import SkillTool
    with Home(hosts=()):
        os.environ.pop("CLAUDE_CODE_SANDBOXED", None)
        proj = _project()
        engine = _engine(proj)
        d = decide(_session(proj, engine), {}, "Skill", {"skill": "x"}, SkillTool())
        ctx.check(f"ask, the command named, got {d.action}: {d.reason}",
                  d.action == "ask" and "`echo marker > marker.txt`" in d.reason and "not trusted" in d.reason)
        from halo_harness.tools.skill_gate import confirm
        confirm(engine, {"skill": "x"})  # the person said yes on that card (3.4.1.2: Session.resolve_permission)
        r = _run(proj, engine)
        ctx.check(f"the yes runs it once, got {r.content!r}", not r.is_error and (proj / "marker.txt").exists())
        (proj / "marker.txt").unlink()
        r = _run(proj, engine)
        ctx.check("a second run without a card does not", r.is_error and not (proj / "marker.txt").exists())
        ctx.check("and nothing was granted", engine.decide("Bash", {"command": "rm -rf build"}).action == "ask")
        d = decide(_session(proj, _engine(proj, "dontAsk")), {}, "Skill", {"skill": "x"}, SkillTool())
        ctx.check(f"dontAsk: denied, got {d.action}", d.action == "deny")
        d = decide(_session(proj, _engine(proj, "auto", deny=("Bash(echo:*)",))), {}, "Skill", {"skill": "x"},
                   SkillTool())
        ctx.check(f"a deny rule on the command denies the call, got {d.action}: {d.reason}",
                  d.action == "deny" and "echo marker" in d.reason)


@test
def test_the_slash_command_grants_nothing(ctx: Ctx):
    from halo_harness.commands.skills import find_skill
    with Home(hosts=()):
        os.environ.pop("CLAUDE_CODE_SANDBOXED", None)
        proj = _project()
        engine = _engine(proj)
        cmd = find_skill("x", proj)
        facade = SimpleNamespace(cwd=proj, session=SimpleNamespace(permission_engine=engine, tool_env=None, log=None,
                                                                   effort=None, agent_id=None))
        out = cmd.run("", facade)
        ctx.check(f"/x: the span not run, the line said, got {out!r}",
                  not (proj / "marker.txt").exists() and "not permitted" in out and "not granted" in out)


@test
def test_a_trusted_folder_keeps_the_grant(ctx: Ctx):
    from halo_harness.config.paths import bridge_home, normalize_cwd
    with Home(hosts=()):
        proj = _project()
        (bridge_home() / "trust.json").write_text(json.dumps({normalize_cwd(proj): True}), encoding="utf-8")
        engine = _engine(proj)
        r = _run(proj, engine)
        ctx.check(f"trusted: the grant runs the span, got {r.content!r}",
                  not r.is_error and (proj / "marker.txt").exists() and "own allowed-tools: Bash" in r.content)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
