"""tests.test_review3_a3 -- permission-engine integrity pins for the 3.0.2.0
review fix pass, round A (review items 91, 92, 93).

  * 91  PowerShell: the plan-mode ban runs before allow rules
  * 92  `Task` and `Agent` name one tool in rules too, both directions
  * 93  PowerShell deny matching sees cmd.exe `&` separators, here-strings
        as one span, and the command Start-Process launches
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.test_review3_a import ALL_ALLOW, ALL_DENY, OTHER, P, decisions, engine, sandbox

test, TESTS = new_registry()

ALLOW_EXCEPT_PLAN = {**ALL_ALLOW, "plan": "deny"}


# ---- item 91 ------------------------------------------------------------------

@test
def test_i91_powershell_plan_ban_before_allow_rules(ctx: Ctx):
    with sandbox() as (_home, proj):
        for cmd in ("Remove-Item x", "rm x", "Get-ChildItem"):
            got = decisions(proj, "PowerShell", {"command": cmd}, allow=["PowerShell(Remove-Item:*)", "PowerShell"])
            ctx.check(f"plan denies even with an allow rule: {cmd!r} -> {got}", got == ALLOW_EXCEPT_PLAN)
        e = engine("plan", proj)
        ctx.check("plan with no rule: the mode table already denied",
                  e.decide("PowerShell", {"command": "Remove-Item x"}).action == "deny")


# ---- item 92 ------------------------------------------------------------------

@test
def test_i92_task_rules_canonicalise_to_agent(ctx: Ctx):
    rule = P.parse_rule("Task(evil)", source="user", action="deny")
    ctx.check(f"Task(x) is an agent rule, got {rule}", rule.tool == "Agent" and rule.kind == "agent"
              and rule.value == "evil" and rule.raw == "Task(evil)")
    bare = P.parse_rule("Task", source="user", action="deny")
    ctx.check("bare Task names the Agent tool", bare.tool == "Agent" and bare.kind == "bare")
    names = P.bare_deny_tool_names([bare])
    ctx.check(f"catalog removal covers both names, got {names}", {"Agent", "Task"} <= names)
    ctx.check("nothing reported invalid", P.describe_invalid_rules([rule, bare]) == "")
    with sandbox() as (_home, proj):
        for tool in ("Agent", "Task"):
            got = decisions(proj, tool, {"subagent_type": "x", "prompt": "p"}, deny=["Task"])
            ctx.check(f"deny Task blocks a {tool} call in every mode, got {got}", got == ALL_DENY)
            got = decisions(proj, tool, {"subagent_type": "evil", "prompt": "p"}, deny=["Task(evil)"])
            ctx.check(f"deny Task(evil) blocks a {tool} call in every mode, got {got}", got == ALL_DENY)
            got = decisions(proj, tool, {"subagent_type": "good", "prompt": "p"}, deny=["Task(evil)"])
            ctx.check(f"another subagent type is untouched, got {got}", got == ALL_ALLOW)
        got = decisions(proj, "Agent", {"subagent_type": "evil"}, ask=["Task(evil)"])
        ctx.check(f"ask Task(evil) asks for Agent, got {got}", got["default"] == "ask" and got["auto"] == "ask")


@test
def test_i92_freeze_registry_both_directions(ctx: Ctx):
    class _Reg:
        def __init__(self, names):
            self._names = set(names)

        def names(self):
            return set(self._names)

        def without(self, drop):
            return _Reg(self._names - set(drop))

        def filtered(self, keep):
            return _Reg(self._names & set(keep))
    reg = _Reg({"Agent", "Task", "Bash"})
    out = P.freeze_tool_registry(reg, disallowed_tools=["Task"])
    ctx.check(f"--disallowedTools Task removes Agent too, left {out.names()}", out.names() == {"Bash"})
    out = P.freeze_tool_registry(reg, disallowed_tools=["Agent"])
    ctx.check(f"--disallowedTools Agent removes Task too, left {out.names()}", out.names() == {"Bash"})
    out = P.freeze_tool_registry(reg, deny_rules=[P.parse_rule("Task", source="user", action="deny")])
    ctx.check(f"a bare Task deny rule removes both, left {out.names()}", out.names() == {"Bash"})


@test
def test_i92_hook_if_rule_spelled_either_way(ctx: Ctx):
    from halo_harness.hooks import if_rule_matches
    with sandbox() as (_home, proj):
        for rule in ("Task", "Agent", "Task(evil)", "Agent(evil)"):
            for tool in ("Task", "Agent"):
                ok = if_rule_matches(rule, tool, {"subagent_type": "evil"}, None, cwd=proj)
                ctx.check(f"hook if {rule!r} matches a {tool} call", ok is True)


# ---- item 93 ------------------------------------------------------------------

@test
def test_i93_powershell_separators_and_wrappers(ctx: Ctx):
    with sandbox() as (_home, proj):
        for cmd in ('cmd /c "echo hi & del x"', 'cmd /c "echo hi && del x"', "cmd /c echo hi | del x",
                    '@"\nfoo " bar\n"@; rm x', "@'\nit's\n'@; Remove-Item x",
                    "Start-Process rm -ArgumentList x", "saps -FilePath Remove-Item -ArgumentList x",
                    "start -Wait del x"):
            got = decisions(proj, "PowerShell", {"command": cmd}, deny=["PowerShell(Remove-Item:*)"])
            ctx.check(f"denied in every mode: {cmd!r} -> {got}", got == ALL_DENY)
        for cmd in ('cmd /c "echo a & echo b"', '@"\nrm x ; del y\n"@ | Out-File n.txt',
                    "Start-Process notepad -ArgumentList x"):
            got = decisions(proj, "PowerShell", {"command": cmd}, deny=["PowerShell(Remove-Item:*)"])
            ctx.check(f"not denied: {cmd!r} -> {got}", got == OTHER)
    from halo_harness import perm_ps
    ctx.check("cmd_split", perm_ps.cmd_split('a & "b & c" && d ^& e || f | g')
              == ["a", '"b & c"', "d ^& e", "f", "g"])
    ctx.check("here-string kept whole",
              P.split_powershell_segments('$x = @"\na; b\n"@; rm y') == ['$x = @"\na; b\n"@', "rm y"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
