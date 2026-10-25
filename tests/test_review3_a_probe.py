"""tests.test_review3_a_probe -- the scripted probe for round A of the
3.0.2.0 review fix pass: every command string named in review items 1, 2,
3, 16, 17, 19, 20, 21, 91, 92 and 93 goes through `PermissionEngine.decide`
in all six permission modes, and each (command, rules, mode) has one
expected decision. One table row per call; one check per row and mode.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.test_review3_a import ALL_ALLOW, ALL_DENY, MODES, OTHER, engine, sandbox

test, TESTS = new_registry()

EDIT = {**OTHER, "acceptEdits": "allow"}  # an in-project edit
OPAQUE = {"default": "ask", "acceptEdits": "ask", "plan": "ask", "dontAsk": "deny",
          "auto": "ask", "bypassPermissions": "allow"}
ALLOW_EXCEPT_PLAN = {**ALL_ALLOW, "plan": "deny"}
ASKED = {"default": "ask", "acceptEdits": "ask", "plan": "ask", "dontAsk": "deny",
         "auto": "ask", "bypassPermissions": "allow"}

RM = ("Bash(rm:*)",)
ENV = ("Read(.env)",)
SSH = ("Read(~/.ssh/**)",)
PS_RM = ("PowerShell(Remove-Item:*)",)


def _b(cmd, expected, deny=(), ask=(), allow=()):
    return ("Bash", {"command": cmd}, deny, ask, allow, expected)


def _ps(cmd, expected, deny=(), ask=(), allow=()):
    return ("PowerShell", {"command": cmd}, deny, ask, allow, expected)


PROBE = [
    # item 1: the heredoc opener line
    _b("cat <<EOF; rm -rf /\nhello\nEOF", ALL_DENY, RM),
    _b("cat <<'EOF'; rm -rf /\nhello\nEOF", ALL_DENY, RM),
    _b('cat <<"EOF" && rm -rf /\nhello\nEOF', ALL_DENY, RM),
    _b("cat <<-EOF; rm -rf /\n\thello\n\tEOF", ALL_DENY, RM),
    _b("cat <<EOF; rm x\nhi\nEOF", ALL_DENY, RM),
    _b("cat <<EOF | sh\nhi\nEOF", ALLOW_EXCEPT_PLAN, allow=("Bash(cat:*)",)),
    _b("cat <<EOF; rm -rf x\nhi\nEOF", OTHER),
    # item 2: the live-cwd tracker
    _b("cd; rm -rf .ssh", OTHER), _b("cd && rm -rf .ssh", OTHER),
    _b("cd -- ~ && rm -rf .ssh", OTHER), _b("cd -P ~ && rm -rf .ssh", OTHER),
    _b("cd -- /etc && touch x", OTHER), _b("rm -rf build", EDIT),
    _b("cat .env; cd /tmp", ALL_DENY, ENV),
    _b("cd $HOME && cat .ssh/id_rsa", ALL_DENY, SSH), _b("cd; cat .ssh/id_rsa", ALL_DENY, SSH),
    _b("cd -- ~; cat .ssh/id_rsa", ALL_DENY, SSH), _b("pushd ~; cat .ssh/id_rsa", ALL_DENY, SSH),
    _b("(cd ~; cat .ssh/id_rsa)", ALL_DENY, SSH),
    _b("cd $X; cat .env", ALL_ALLOW, ENV),
    # item 3: deny-side wrapper tables
    *[_b(c, ALL_DENY, RM) for c in (
        "timeout 5s rm -rf x", "timeout 1m rm -rf x", "xargs -n 1 rm", "xargs -L 1 rm", "xargs -o rm x",
        "time -p rm -rf x", "env -C /tmp rm -rf x", "env --chdir /tmp rm -rf x", "sudo -r role rm -rf x",
        "sudo -h host rm -rf x", "sudo -C 3 rm -rf x")],
    # item 16: shell -c / eval payloads
    *[_b(c, ALL_DENY, RM) for c in (
        "sh -c 'rm -rf x'", 'bash -c "rm -rf x"', "eval rm -rf x", "sudo sh -c 'rm -rf x'",
        "find . -exec sh -c 'rm -rf {}' \\;")],
    _b("sh -c 'rm -rf x'", OTHER),
    # item 17: only a shell's -c is opaque
    *[_b(c, ALL_ALLOW, RM) for c in (
        "wc -c f", "grep -c foo f", "head -c 10 f", "cut -c 1-5 f", "tail -c 5 f", "ls -c", "du -c .")],
    *[_b(c, OTHER, RM) for c in (
        "gcc -c main.c", "uniq -c f", "sort -c f", "git -c user.name=x commit -m hi",
        "curl -c jar https://example.com")],
    _b("bash -c 'echo hi'", OPAQUE, RM),
    # item 19: Read-deny Bash gating
    *[_b(c, ALL_DENY, ENV) for c in (
        "grep -eSECRET .env", "grep --regexp=SECRET .env", "grep -fpats .env", "sed -nep .env",
        "sed --expression=p .env", "awk -fprog.awk .env", "grep -r SECRET .", "cat $PWD/.env",
        "cat .{env,bak}")],
    _b("grep -r SECRET .", ASKED, ask=ENV),
    # item 20: quoted / commented parentheses are text
    _b('git commit -m "cleanup (rm build dir)"', OTHER, RM), _b('echo "(rm x)"', ALL_ALLOW, RM),
    _b("echo hi # (rm x)", ALL_ALLOW, RM), _b("echo '$(rm x)'", OTHER, RM),
    _b('git commit -m "chore: { rm old; }"', OTHER, RM),
    _b('git commit -m "docs (git push flow)"', OTHER, ("Bash(git push:*)",)),
    _b("( rm x )", ALL_DENY, RM), _b('echo "$(rm x)"', ALL_DENY, RM),
    # item 21: non-string tool_input fields
    _b(None, OTHER), _b(["ls"], OTHER), _b(5, OTHER, RM), _ps(None, OTHER),
    ("Read", {"file_path": 123}, ENV, (), (), ALL_ALLOW),
    ("Edit", {"file_path": 5}, (), (), (), OTHER),
    ("Glob", {"path": 5}, ENV, (), (), ALL_ALLOW),
    # (3.2.2.0 R4: WebFetch is a web read -- plan mode runs it; the other modes keep their decision)
    ("WebFetch", {"url": 5}, ("WebFetch(domain:x.com)",), (), (), {**OTHER, "plan": "allow"}),
    # item 91: PowerShell plan-mode ban before allow rules
    _ps("Remove-Item x", ALLOW_EXCEPT_PLAN, allow=PS_RM), _ps("rm x", ALLOW_EXCEPT_PLAN, allow=PS_RM),
    _ps("Remove-Item x", OTHER),
    # item 92: Task / Agent canonicalisation
    ("Agent", {"subagent_type": "x"}, ("Task",), (), (), ALL_DENY),
    ("Task", {"subagent_type": "x"}, ("Task",), (), (), ALL_DENY),
    ("Agent", {"subagent_type": "evil"}, ("Task(evil)",), (), (), ALL_DENY),
    ("Task", {"subagent_type": "evil"}, ("Task(evil)",), (), (), ALL_DENY),
    ("Agent", {"subagent_type": "good"}, ("Task(evil)",), (), (), ALL_ALLOW),
    # item 93: PowerShell separators and wrappers
    _ps('cmd /c "echo hi & del x"', ALL_DENY, PS_RM), _ps('@"\nfoo " bar\n"@; rm x', ALL_DENY, PS_RM),
    _ps("Start-Process rm -ArgumentList x", ALL_DENY, PS_RM),
    _ps('cmd /c "echo hi & echo there"', OTHER, PS_RM),
    # the standing contract: auto/bypassPermissions with no rules allow all
    *[_b(c, OTHER) for c in ("timeout 5s rm -rf x", "eval rm -rf x", "cd; rm -rf .ssh")],
]


@test
def test_probe_table_well_formed(ctx: Ctx):
    ctx.check(f"{len(PROBE)} rows", len(PROBE) >= 90)
    for row in PROBE:
        ctx.check(f"row covers all six modes: {row[1]!r}", set(row[5]) == set(MODES))


@test
def test_probe_every_row_in_every_mode(ctx: Ctx):
    with sandbox() as (_home, proj):
        (proj / ".env").write_text("SECRET=1\n", encoding="utf-8")
        for tool, tool_input, deny, ask, allow, expected in PROBE:
            for mode in MODES:
                e = engine(mode, proj, deny, ask, allow)
                try:
                    got = e.decide(tool, dict(tool_input)).action
                except Exception as exc:  # noqa: BLE001 -- a raise is a probe failure too
                    got = f"raised {type(exc).__name__}"
                ctx.check(f"{tool} {tool_input!r} deny={deny} ask={ask} allow={allow} [{mode}]: "
                          f"want {expected[mode]}, got {got}", got == expected[mode])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
