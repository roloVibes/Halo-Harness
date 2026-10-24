"""tests.test_command_body_shell -- Halo 3.2.1.0 round R5: a skill's or a
command's `` !`cmd` `` naming `${CLAUDE_SKILL_DIR}` / `${CLAUDE_PROJECT_DIR}`
runs on Windows (R4's candidate, found failing: Git Bash ate the pasted
path's backslashes, `sh: C:Users...my-skill/x.sh: No such file or
directory`, exit 127).

1. `fill_claude_vars_in_commands`: inside a span the value is the shell's
   (`shell_path`, `shlex`-quoted bare, escaped inside "..." and '...'), the
   prose around it is untouched; a body with no span is returned as it is.
2. A real run on this platform (Git Bash on Windows, bash on POSIX) through
   `expand_command_body` with an auto-mode permission engine: a script in a
   skill folder, a plain one and one with a space, bare / "..." / '...';
   the prose keeps the path as it is.
3. The model-invoked Skill tool and the `/skill` slash path both run it.
No model call. Run: python -m tests.test_command_body_shell
"""
from __future__ import annotations

import os
import shlex
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()

SCRIPT = 'echo "ran $(basename "$(dirname "$0")") $1"\n'
BODIES = {
    "bare": "!`sh ${CLAUDE_SKILL_DIR}/x.sh bare`",
    "in double quotes": '!`sh "${CLAUDE_SKILL_DIR}/x.sh" dq`',
    "in single quotes": "!`sh '${CLAUDE_SKILL_DIR}/x.sh' sq`",
}


def _skill_dir(parent: str) -> Path:
    d = Path(tempfile.mkdtemp(prefix="r5-body-")) / parent / "my-skill"
    d.mkdir(parents=True)
    (d / "x.sh").write_text(SCRIPT, encoding="utf-8", newline="\n")
    return d.resolve()


def _engine(cwd: Path):
    from halo_harness.permissions import PermissionEngine
    return PermissionEngine(mode="auto", cwd=cwd)


@test
def test_a_span_gets_the_shells_form_and_the_prose_the_plain_value(ctx: Ctx):
    from halo_harness.commands.registry import fill_claude_vars_in_commands
    from halo_harness.packs.interpreter import shell_path
    plain = "C:\\Tools\\my-skill" if os.name == "nt" else "/opt/skills/my-skill"
    spaced = "C:\\My Tools\\my-skill" if os.name == "nt" else "/opt/my skills/my-skill"
    for d in (plain, spaced):
        fwd = shell_path(d)
        text = "dir: ${CLAUDE_SKILL_DIR}\n" + "\n".join(BODIES.values())
        got = fill_claude_vars_in_commands(text, {"CLAUDE_SKILL_DIR": d, "CLAUDE_SESSION_ID": None})
        ctx.check(f"the prose is left for substitute_claude_vars, got {got!r}", got.startswith("dir: ${CLAUDE_SKILL_DIR}\n"))
        ctx.check(f"bare: shlex-quoted shell path ({d}), got {got!r}", f"!`sh {shlex.quote(fwd)}/x.sh bare`" in got)
        ctx.check(f"inside \"...\": the shell path as it is, got {got!r}", f'!`sh "{fwd}/x.sh" dq`' in got)
        ctx.check(f"inside '...': the shell path as it is, got {got!r}", f"!`sh '{fwd}/x.sh' sq`" in got)
        ctx.check("no backslash reaches a span on Windows",
                  os.name != "nt" or all("\\" not in line for line in got.splitlines()[1:]))
    ctx.check("a value with a space is quoted bare", shlex.quote(shell_path(spaced)) != shell_path(spaced))
    ctx.check("a plain value stays bare", shlex.quote(shell_path(plain)) == shell_path(plain))
    q = fill_claude_vars_in_commands("!`echo \"${CLAUDE_SKILL_DIR}\"`", {"CLAUDE_SKILL_DIR": 'a"b$c'})
    ctx.check(f"a quote or $ in the value is escaped inside \"...\", got {q!r}", q == '!`echo "a\\"b\\$c"`')
    ctx.check("no span: returned as it is", fill_claude_vars_in_commands("x ${CLAUDE_SKILL_DIR}", {"CLAUDE_SKILL_DIR": plain})
              == "x ${CLAUDE_SKILL_DIR}")
    ctx.check("no vars: returned as it is", fill_claude_vars_in_commands(BODIES["bare"], None) == BODIES["bare"])


@test
def test_a_span_naming_the_skill_dir_runs_on_this_platform(ctx: Ctx):
    from halo_harness.commands.registry import expand_command_body
    from halo_harness.config.paths import git_bash
    if git_bash() is None:
        ctx.check("no POSIX shell here (the span cannot run)", True)
        return
    for parent in ("plain", "with space"):
        d = _skill_dir(parent)
        for label, body in BODIES.items():
            r = expand_command_body("dir: ${CLAUDE_SKILL_DIR}\n" + body, "", cwd=d, permission_engine=_engine(d),
                                    env=dict(os.environ), claude_vars={"CLAUDE_SKILL_DIR": str(d), "CLAUDE_PROJECT_DIR": str(d)})
            tag = {"bare": "bare", "in double quotes": "dq", "in single quotes": "sq"}[label]
            ctx.check(f"[{parent}] {label}: the script ran, got {r.error!r} {r.text!r}",
                      r.error is None and f"ran my-skill {tag}" in r.text)
            ctx.check(f"[{parent}] {label}: the prose keeps the path as it is", r.text.startswith(f"dir: {d}\n"))
        r = expand_command_body("!`ls ${CLAUDE_PROJECT_DIR}`", "", cwd=d, permission_engine=_engine(d), env=dict(os.environ),
                                claude_vars={"CLAUDE_PROJECT_DIR": str(d)})
        ctx.check(f"[{parent}] ${{CLAUDE_PROJECT_DIR}} too, got {r.error!r} {r.text!r}", r.error is None and "x.sh" in r.text)


@test
def test_the_skill_tool_and_the_slash_skill_both_run_it(ctx: Ctx):
    from halo_harness.commands.skills import discover_all_skills
    from halo_harness.config.paths import git_bash
    from halo_harness.tools.base import ToolContext
    from halo_harness.tools.skill import SkillTool
    from tests.helpers.fake_home import add_fake_skill
    if git_bash() is None:
        ctx.check("no POSIX shell here (the span cannot run)", True)
        return
    root = Path(tempfile.mkdtemp(prefix="r5-body-skill-")) / "a folder"
    proj, home = root / "proj", root / "home"
    (home / ".claude").mkdir(parents=True)
    add_fake_skill(proj / ".claude" / "skills", name="shellskill", body="Out: " + BODIES["bare"] + "\n",
                   frontmatter_extra={"allowed-tools": "Bash(sh:*)"})
    skill = (proj / ".claude" / "skills" / "shellskill").resolve()
    (skill / "x.sh").write_text(SCRIPT, encoding="utf-8", newline="\n")
    saved = os.environ.get("BRIDGE_TEST_HOME")
    os.environ["BRIDGE_TEST_HOME"] = str(home)
    try:
        result = SkillTool().run({"skill": "shellskill"}, ToolContext(cwd=proj, permission_engine=_engine(proj),
                                                                       env=dict(os.environ)))
    finally:
        if saved is None:
            os.environ.pop("BRIDGE_TEST_HOME", None)
        else:
            os.environ["BRIDGE_TEST_HOME"] = saved
    ctx.check(f"the Skill tool: the script ran, got {result.content!r}",
              not result.is_error and "Out: ran shellskill bare" in result.content)

    class _Log:
        session_id = "r5session"

    class _Session:
        log, effort, permission_engine, tool_env = _Log(), "high", _engine(proj), dict(os.environ)

    class _Facade:
        cwd, session = proj, _Session()

    cmd = discover_all_skills(proj, home=home).get("shellskill")
    text = cmd.run("", _Facade()) if cmd is not None else "(not discovered)"
    ctx.check(f"/shellskill: the script ran, got {text!r}", "Out: ran shellskill bare" in text)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
