"""tests.test_security_round4 -- 2.0.10 round 4, security fix pass 2 (permission
engine), findings 11-13 of docs/harness/SECURITY-REVIEW-2.0.10.md.

11  REJECTED by the standing contract (allow side): an explicit allow rule
    keeps matching exactly as before; the deny side is finding 12
12  a deny/ask rule holds through if/then, for/do, while, `!`, `exec`, case
    arms, more wrappers, `-c` payloads, `find -exec`, and PowerShell's
    script blocks, call operator and nested interpreters
13  tool-global options between the binary and the verb (git -C x push,
    docker --context x run, kubectl -n x delete, npm --prefix x publish)

Siblings: test_security_round4b (14-16), test_security_round4c (24-25).
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()

os.environ.setdefault("BRIDGE_TEST_HOME", tempfile.mkdtemp(prefix="halo-sec4-home-"))

import halo_harness.permissions as P


def _engine(rule: str, *, mode: str = "auto", action: str = "deny", tool: str = "Bash"):
    tmp = Path(tempfile.mkdtemp(prefix="halo-sec4-"))
    parsed = P.parse_rule(rule, source="user", base_dir=tmp)
    kwargs = {"deny_rules": [parsed]} if action == "deny" else {"ask_rules": [parsed]}
    return P.PermissionEngine(mode=mode, cwd=tmp, **kwargs)


def _decide(engine, command: str, tool: str = "Bash") -> str:
    return engine.decide(tool, {"command": command}).action


# ---- 11: rejected (allow side) ---------------------------------------------------


@test
def test_f11_rejected_allow_side_is_unchanged(ctx: Ctx):
    tmp = Path(tempfile.mkdtemp(prefix="halo-sec4-"))
    allow = [P.parse_rule("Bash(ls:*)", source="user", base_dir=tmp, action="allow")]
    engine = P.PermissionEngine(mode="default", cwd=tmp, allow_rules=allow)
    ctx.check("an explicit allow still matches ls with a substitution",
              _decide(engine, "ls $(touch x)") == "allow")
    ctx.check("auto mode with no rules still allows it",
              _decide(P.PermissionEngine(mode="auto", cwd=tmp), "ls $(touch x)") == "allow")
    # the deny side of the same shape is covered by finding 12
    deny = _engine("Bash(touch:*)")
    ctx.check("a deny rule still sees the body of the substitution",
              _decide(deny, "ls $(touch x)") == "deny")


# ---- 12: compound keywords ---------------------------------------------------------

_COMPOUND = [
    "if true; then rm x; fi",
    "for f in a b; do rm $f; done",
    "while true; do rm x; done",
    "until false; do rm x; done",
    "if false; then echo a; else rm x; fi",
    "if false; then echo a; elif true; then rm x; fi",
    "! rm x",
    "exec rm x",
    "case a in a) rm x;; esac",
    "case a in b) echo;; a) rm x;; esac",
    "if ! rm x; then echo; fi",
    "time rm x",
]


@test
def test_f12_deny_holds_through_compound_keywords(ctx: Ctx):
    engine = _engine("Bash(rm:*)")
    for cmd in _COMPOUND:
        ctx.check(f"denied: {cmd}", _decide(engine, cmd) == "deny")
    ctx.check("a harmless loop is not denied",
              _decide(engine, "for f in a b; do echo $f; done") == "allow")
    free = P.PermissionEngine(mode="auto", cwd=Path(tempfile.mkdtemp(prefix="halo-sec4-")))
    for cmd in _COMPOUND:
        ctx.check(f"auto with no rules allows: {cmd}", _decide(free, cmd) == "allow")


@test
def test_f12_ask_holds_through_compound_keywords(ctx: Ctx):
    engine = _engine("Bash(git push:*)", action="ask")
    for cmd in ("for r in a b; do git push $r; done", "if true; then git push; fi", "! git push",
                "exec git push", "while true; do git push; done"):
        ctx.check(f"asks: {cmd}", _decide(engine, cmd) == "ask")


_WRAPPED = [
    "watch -n 2 rm x", "watch rm x", "flock /tmp/l rm x", "flock -n /tmp/l rm x",
    "flock -w 5 /tmp/l rm x", "unshare -m rm x", "unshare --fork --pid rm x",
    "chroot /srv/root rm x", "strace -o out rm x", "strace -f -e trace=open rm x",
    "ltrace rm x", "fakeroot rm x", "nsenter -t 1 -m rm x", "taskset 0x1 rm x",
    "taskset -c 0,1 rm x", "chrt -f 10 rm x", "setarch x86_64 rm x", "runuser -u bob rm x",
    "pkexec rm x", "unbuffer rm x", "eatmydata rm x", "busybox rm x", "sudo -E watch rm x",
    "flock f -c 'rm x'", "runuser bob -c 'rm x'", "find . -name a -exec rm {} \\;",
    "find . -execdir rm {} +",
]


@test
def test_f12_deny_holds_through_wrappers_and_payloads(ctx: Ctx):
    engine = _engine("Bash(rm:*)")
    for cmd in _WRAPPED:
        ctx.check(f"denied: {cmd}", _decide(engine, cmd) == "deny")
    for cmd in ("watch -n 2 date", "flock /tmp/l ls", "strace ls", "find . -name a -exec ls {} \\;"):
        ctx.check(f"not denied: {cmd}", _decide(engine, cmd) == "allow")


@test
def test_f12_opaque_shell_forms_are_asked_when_a_rule_exists(ctx: Ctx):
    engine = _engine("Bash(rm:*)")
    for cmd in ("bash -lc 'rm x'", "sh <<EOF\nrm x\nEOF", "echo rm x | sh", "bash <<< 'rm x'"):
        ctx.check(f"asked about: {cmd!r}", _decide(engine, cmd) in ("ask", "deny"))
    free = P.PermissionEngine(mode="auto", cwd=Path(tempfile.mkdtemp(prefix="halo-sec4-")))
    ctx.check("auto with no rules allows bash -lc", _decide(free, "bash -lc 'rm x'") == "allow")
    ctx.check("auto with no rules allows a heredoc into sh", _decide(free, "sh <<EOF\nrm x\nEOF") == "allow")


_PS_FORMS = [
    "if ($true) { Remove-Item x }", "if ($true) { rm x; echo done }",
    "Get-ChildItem | ForEach-Object { Remove-Item $_ }", "ls | % { rm $_ }",
    "& rm x", "& 'Remove-Item' x", ". rm x", "foreach ($f in 1,2) { del $f }",
    "powershell -Command \"rm x\"", "pwsh -NoProfile -c \"Remove-Item x\"",
    "cmd /c \"del x\"", "try { rm x } catch { }", "$(Remove-Item x)",
]


@test
def test_f12_powershell_forms_reach_the_deny_rule(ctx: Ctx):
    engine = _engine("PowerShell(Remove-Item:*)")
    for cmd in _PS_FORMS:
        ctx.check(f"denied: {cmd}", _decide(engine, cmd, "PowerShell") == "deny")
    ctx.check("a harmless block is not denied",
              _decide(engine, "if ($true) { Write-Output hi }", "PowerShell") == "allow")
    free = P.PermissionEngine(mode="auto", cwd=Path(tempfile.mkdtemp(prefix="halo-sec4-")))
    for cmd in _PS_FORMS:
        ctx.check(f"auto with no rules allows: {cmd}", _decide(free, cmd, "PowerShell") == "allow")


@test
def test_f12_powershell_opaque_forms_are_asked_when_a_rule_exists(ctx: Ctx):
    engine = _engine("PowerShell(Remove-Item:*)")
    for cmd in ("iex $payload", "Invoke-Expression $payload", "powershell -EncodedCommand AAAA",
                "pwsh -enc AAAA"):
        ctx.check(f"asked about: {cmd}", _decide(engine, cmd, "PowerShell") == "ask")
    free = P.PermissionEngine(mode="auto", cwd=Path(tempfile.mkdtemp(prefix="halo-sec4-")))
    ctx.check("auto with no rules allows iex", _decide(free, "iex $payload", "PowerShell") == "allow")


# ---- 13: tool-global options --------------------------------------------------------


@test
def test_f13_tool_global_options_do_not_defeat_a_prefix_rule(ctx: Ctx):
    cases = [
        ("Bash(git push:*)", ["git -C /x push", "git --no-pager push", "git --git-dir=.git push --force",
                              "git -c core.x=1 push origin", "/usr/bin/git -C x push",
                              "sudo git -C x push", "FOO=1 git -C x push", "for r in a; do git -C x push; done"]),
        ("Bash(docker run:*)", ["docker --context x run img", "docker -H tcp://h run img", "docker --config d run img"]),
        ("Bash(docker compose up:*)", ["docker -H h compose -f f.yml up", "docker compose --profile p up"]),
        ("Bash(kubectl delete:*)", ["kubectl -n x delete pod p", "kubectl --context c --namespace n delete pod p"]),
        ("Bash(npm publish:*)", ["npm --prefix x publish", "npm --registry r publish"]),
        ("Bash(cargo publish:*)", ["cargo +nightly publish"]),
        ("Bash(terraform apply:*)", ["terraform -chdir=infra apply"]),
        ("Bash(make deploy:*)", ["make -C sub deploy"]),
    ]
    for rule, commands in cases:
        engine = _engine(rule)
        for cmd in commands:
            ctx.check(f"{rule} denies: {cmd}", _decide(engine, cmd) == "deny")
    git = _engine("Bash(git push:*)")
    for cmd in ("git -C x status", "git --no-pager log", "git -C x commit -m push"):
        ctx.check(f"not denied: {cmd}", _decide(git, cmd) == "allow")
    ask = _engine("Bash(git push:*)", action="ask")
    ctx.check("an ask rule holds through -C", _decide(ask, "git -C x push") == "ask")
    free = P.PermissionEngine(mode="auto", cwd=Path(tempfile.mkdtemp(prefix="halo-sec4-")))
    ctx.check("auto with no rules allows git -C x push", _decide(free, "git -C x push") == "allow")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
