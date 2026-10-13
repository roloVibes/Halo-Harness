"""tests.test_review3_a -- permission-engine integrity pins for the 3.0.2.0
review fix pass, round A (review items 1, 2, 3, 16, 17).

  * 1   a command after a heredoc opener on the same line is its own segment
  * 2   one cd walker: bare `cd`, `cd -- ~`, `cd -P ~`, pushd/popd, per-segment
        cwd, a subshell's own cd, unknown cwd never guessed
  * 3   deny-side wrapper tables (`timeout 5s`, `xargs -n 1`, `time -p`, ...)
  * 16  a `sh -c` / `bash -c` / `eval` payload is matched against deny rules
  * 17  only a SHELL's `-c` is an opaque re-exec (`wc -c f` is not)

Standing contract, written as tests: deny/ask rules hold in every mode;
auto/bypassPermissions with no rules allow everything; allow-rule matching
is unchanged. The helpers here are shared by tests/test_review3_a2.py,
_a3.py and _a_probe.py.
"""
from __future__ import annotations

import contextlib
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

import halo_harness.permissions as P

test, TESTS = new_registry()

MODES = ("default", "acceptEdits", "plan", "dontAsk", "auto", "bypassPermissions")


@contextlib.contextmanager
def sandbox():
    """(home, project): a throwaway `~` (HOME and USERPROFILE point at it, so
    `cd ~` / `~/.ssh` never name the real machine home) and a project dir
    beside it. Both variables are restored afterwards."""
    root = Path(tempfile.mkdtemp(prefix="review3a-"))
    home, proj = root / "home", root / "proj"
    home.mkdir()
    proj.mkdir()
    saved = {k: os.environ.get(k) for k in ("HOME", "USERPROFILE")}
    os.environ["HOME"] = os.environ["USERPROFILE"] = str(home)
    try:
        yield home, proj
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def engine(mode: str, proj: Path, deny=(), ask=(), allow=()) -> "P.PermissionEngine":
    def _rules(texts, action):
        return [P.parse_rule(t, source="user", base_dir=proj, action=action) for t in texts]
    return P.PermissionEngine(mode=mode, cwd=proj, deny_rules=_rules(deny, "deny"),
                              ask_rules=_rules(ask, "ask"), allow_rules=_rules(allow, "allow"))


def decisions(proj: Path, tool: str, tool_input: dict, deny=(), ask=(), allow=()) -> dict:
    """{mode: action} for one call across all six permission modes."""
    return {m: engine(m, proj, deny, ask, allow).decide(tool, dict(tool_input)).action for m in MODES}


ALL_DENY = {m: "deny" for m in MODES}
ALL_ALLOW = {m: "allow" for m in MODES}
# the mode table's "other" row (no rule matched, not read-only)
OTHER = {"default": "ask", "acceptEdits": "ask", "plan": "deny", "dontAsk": "deny",
         "auto": "allow", "bypassPermissions": "allow"}


def check_all_deny(ctx: Ctx, proj: Path, commands, deny) -> None:
    for cmd in commands:
        got = decisions(proj, "Bash", {"command": cmd}, deny=deny)
        ctx.check(f"denied in every mode: {cmd!r} -> {got}", got == ALL_DENY)


# ---- item 1 -------------------------------------------------------------------

@test
def test_i1_heredoc_opener_line_splits(ctx: Ctx):
    segs = P.split_bash_segments("cat <<EOF; rm x\nhi\nEOF", opener_scan=True)
    ctx.check(f"two segments, got {segs!r}", len(segs) == 2 and segs[0] == "cat <<EOF"
              and segs[1].startswith("rm x"))
    ctx.check("the body stays with the opener line, never its own command",
              not any(s.strip() == "hi" for s in segs))
    two = P.split_bash_segments("cat <<A <<B; rm y\na\nA\nb\nB\necho done", opener_scan=True)
    ctx.check(f"two heredocs on one line, then the next command, got {two!r}",
              two[-1] == "echo done" and two[1].startswith("rm y"))
    ctx.check("allow-side split unchanged (one segment)",
              len(P.split_bash_segments("cat <<EOF; rm x\nhi\nEOF")) == 1)


@test
def test_i1_heredoc_opener_denied_in_every_mode(ctx: Ctx):
    with sandbox() as (_home, proj):
        check_all_deny(ctx, proj, [
            "cat <<EOF; rm x\nhi\nEOF",
            "cat <<EOF; rm -rf /\nhello\nEOF",
            "cat <<'EOF'; rm -rf /\nhello\nEOF",
            "cat <<-EOF && rm -rf /\n\thello\n\tEOF",
            "cat <<EOF\nhello\nEOF\nrm -rf /",
        ], ["Bash(rm:*)"])


@test
def test_i1_allow_rule_still_covers_the_whole_command(ctx: Ctx):
    with sandbox() as (_home, proj):
        got = decisions(proj, "Bash", {"command": "cat <<EOF | sh\nhi\nEOF"}, allow=["Bash(cat:*)"])
        ctx.check(f"allow Bash(cat:*) still allows it (plan mode excepted), got {got}",
                  got == {**ALL_ALLOW, "plan": "deny"})
        got = decisions(proj, "Bash", {"command": "cat <<EOF; rm -rf x\nhi\nEOF"})
        ctx.check(f"no rules: auto/bypass allow, plan no longer sees it as read-only, got {got}", got == OTHER)


# ---- item 2 -------------------------------------------------------------------

@test
def test_i2_cd_walker_destinations(ctx: Ctx):
    with sandbox() as (home, proj):
        e = engine("acceptEdits", proj)

        def final(cmd):
            return e._bash_cwd_walk(cmd, proj)[1]
        for cmd in ("cd", "cd -- ~", "cd -P ~", "cd -L -- ~", "cd $HOME", "cd ${HOME}", "pushd ~"):
            ctx.check(f"{cmd!r} -> home", final(cmd) == home)
        ctx.check("cd -- sub -> project/sub", final("cd -- sub") == proj / "sub")
        for cmd in ("cd -", "cd $X", "popd", "pushd", "pushd +1", "cd ~other", "cd -Q x"):
            ctx.check(f"{cmd!r} -> unknown", final(cmd) is None)
        ctx.check("a subshell's cd stays inside it", final("(cd ~); true") == proj)
        ctx.check("a brace group's cd carries out", final("{ cd ~; }; true") == home)
        pairs = e._bash_cwd_walk("cat .env; cd /tmp", proj)[0]
        ctx.check(f"per-segment cwd: the cat runs in the project, got {pairs}", pairs[0][1] == proj)


@test
def test_i2_accept_edits_follows_the_real_cwd(ctx: Ctx):
    with sandbox() as (_home, proj):
        for cmd in ("cd; rm -rf .ssh", "cd && rm -rf .ssh", "cd -- ~ && rm -rf .ssh",
                    "cd -P ~ && rm -rf .ssh", "cd -- /etc && touch x", "popd; rm -rf x"):
            got = decisions(proj, "Bash", {"command": cmd})
            ctx.check(f"not an in-project edit: {cmd!r} -> {got}", got == OTHER)
        got = decisions(proj, "Bash", {"command": "cd sub && rm -rf build"})
        ctx.check(f"a cd inside the project still auto-allows in acceptEdits, got {got}",
                  got["acceptEdits"] == "allow")


@test
def test_i2_read_deny_uses_the_cwd_at_each_segment(ctx: Ctx):
    with sandbox() as (_home, proj):
        check_all_deny(ctx, proj, ["cat .env; cd /tmp", "cat .env && cd .."], ["Read(.env)"])
        check_all_deny(ctx, proj, [
            "cd $HOME && cat .ssh/id_rsa", "cd; cat .ssh/id_rsa", "cd -- ~; cat .ssh/id_rsa",
            "pushd ~; cat .ssh/id_rsa", "(cd ~; cat .ssh/id_rsa)", "{ cd ~; }; cat .ssh/id_rsa",
        ], ["Read(~/.ssh/**)"])
        got = decisions(proj, "Bash", {"command": "cd $X; cat .env"}, deny=["Read(.env)"])
        ctx.check(f"unknown cwd: the relative word is not guessed at, got {got}", got == ALL_ALLOW)
        got = decisions(proj, "Bash", {"command": "(cd ~; true); cat .ssh/id_rsa"}, deny=["Read(~/.ssh/**)"])
        ctx.check(f"after the subshell the project cwd is back (no deny, plain mode table), got {got}",
                  got == OTHER)


# ---- item 3 -------------------------------------------------------------------

@test
def test_i3_wrapper_forms_denied_in_every_mode(ctx: Ctx):
    cmds = ["timeout 5s rm -rf x", "timeout 1m rm -rf x", "timeout 0.5 rm x", "xargs -n 1 rm",
            "xargs -L 1 rm", "xargs -o rm x", "xargs -n1 rm", "time -p rm -rf x", "env -C /tmp rm -rf x",
            "env --chdir /tmp rm -rf x", "sudo -r role rm -rf x", "sudo -h host rm -rf x",
            "sudo -C 3 rm -rf x", "sudo -t type -T 5 -U bob rm x"]
    with sandbox() as (_home, proj):
        check_all_deny(ctx, proj, cmds, ["Bash(rm:*)"])
    ctx.check("strip result for timeout 5s",
              P.strip_wrappers_and_env_for_deny("timeout 5s rm -rf x") == "rm -rf x")
    ctx.check("env --default-signal stays valueless (no command eaten)",
              P.strip_wrappers_and_env_for_deny("env --default-signal rm x") == "rm x")


# ---- items 16 / 17 ------------------------------------------------------------

@test
def test_i16_shell_payloads_denied_in_every_mode(ctx: Ctx):
    with sandbox() as (_home, proj):
        check_all_deny(ctx, proj, [
            "sh -c 'rm -rf x'", 'bash -c "rm -rf x"', "eval rm -rf x", "sudo sh -c 'rm -rf x'",
            "bash -lc 'rm x'", "zsh -ec 'true; rm x'", "find . -exec sh -c 'rm -rf {}' \\;",
        ], ["Bash(rm:*)"])
        got = decisions(proj, "Bash", {"command": "sh -c 'rm -rf x'"})
        ctx.check(f"no rules: unchanged mode table (auto/bypass allow), got {got}", got == OTHER)
        got = decisions(proj, "Bash", {"command": "echo bash -c 'rm x'"}, deny=["Bash(rm:*)"])
        ctx.check(f"a shell word that is only an argument carries no payload, got {got}",
                  got == ALL_ALLOW)


@test
def test_i17_only_a_shell_dash_c_is_opaque(ctx: Ctx):
    with sandbox() as (_home, proj):
        for cmd in ("wc -c f", "grep -c x f", "head -c 10 f", "du -c ."):
            got = decisions(proj, "Bash", {"command": cmd}, deny=["Bash(rm:*)"])
            ctx.check(f"read-only, allowed everywhere: {cmd!r} -> {got}", got == ALL_ALLOW)
        for cmd in ("gcc -c main.c", "git -c user.name=x commit -m hi", "curl -c jar https://example.com"):
            got = decisions(proj, "Bash", {"command": cmd}, deny=["Bash(rm:*)"])
            ctx.check(f"plain mode-table row: {cmd!r} -> {got}", got == OTHER)
        got = decisions(proj, "Bash", {"command": "bash -c 'echo hi'"}, deny=["Bash(rm:*)"])
        ctx.check(f"a real shell -c is still asked about, got {got}",
                  got == {"default": "ask", "acceptEdits": "ask", "plan": "ask", "dontAsk": "deny",
                          "auto": "ask", "bypassPermissions": "allow"})


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
