"""tests.test_review3_a2 -- permission-engine integrity pins for the 3.0.2.0
review fix pass, round A (review items 19, 20, 21).

  * 19  Read-deny gating of Bash readers: glued/`=` pattern options, other
        readers' own options never eat the file word, `$PWD`, `{a,b}` braces,
        recursive readers' directory operands
  * 20  `( )`, `{ }`, `$( )` inside quotes or a `#` comment are text
  * 21  a non-string tool_input field returns a Decision, never raises
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.test_review3_a import ALL_ALLOW, OTHER, P, check_all_deny, decisions, engine, sandbox

test, TESTS = new_registry()


def _project_with_env(proj: Path) -> None:
    (proj / ".env").write_text("SECRET=1\n", encoding="utf-8")
    (proj / "src").mkdir()
    (proj / "src" / "app.py").write_text("print(1)\n", encoding="utf-8")


# ---- item 19 ------------------------------------------------------------------

@test
def test_i19_glued_and_long_pattern_options(ctx: Ctx):
    with sandbox() as (_home, proj):
        _project_with_env(proj)
        check_all_deny(ctx, proj, [
            "grep -eSECRET .env", "grep --regexp=SECRET .env", "grep -fpats .env", "grep -e SECRET .env",
            "sed -nep .env", "sed --expression=p .env", "awk -fprog.awk .env", "grep -ie x .env",
            "cat -e .env", "tail -f .env", "cat $PWD/.env", "cat ${PWD}/.env", "cat .{env,bak}",
        ], ["Read(.env)"])
        e = engine("default", proj)
        ctx.check("the pattern itself is not a path",
                  e._bash_reader_paths("grep", ["SECRET", "f.txt"]) == ["f.txt"])
        ctx.check("--file=X names a file that is read",
                  e._bash_reader_paths("grep", ["--file=pats", "f.txt"]) == ["pats", "f.txt"])
        ctx.check("cat's own -e never eats the file word",
                  e._bash_reader_paths("cat", ["-e", ".env"]) == [".env"])


@test
def test_i19_recursive_readers_walk_directory_operands(ctx: Ctx):
    with sandbox() as (_home, proj):
        _project_with_env(proj)
        check_all_deny(ctx, proj, [
            "grep -r SECRET .", "grep -rn SECRET", "grep --recursive SECRET .", "rg --hidden SECRET .",
            "cp -r . /tmp/out", "tar czf out.tgz .",
        ], ["Read(.env)"])
        got = decisions(proj, "Bash", {"command": "grep -r SECRET src"}, deny=["Read(.env)"])
        ctx.check(f"a directory without the denied file is fine, got {got}", got == ALL_ALLOW)
        got = decisions(proj, "Bash", {"command": "rg SECRET ."}, deny=["Read(.env)"])
        ctx.check(f"rg skips hidden files unless asked, so no hit, got {got}", got == OTHER)
        got = decisions(proj, "Bash", {"command": "stat ."}, deny=["Read(.env)"])
        ctx.check(f"a non-recursive reader of a directory is not walked, got {got}", got == ALL_ALLOW)
        got = decisions(proj, "Bash", {"command": "grep -r SECRET ."}, ask=["Read(.env)"])
        ctx.check(f"a Read ASK rule asks for the walk too, got {got}",
                  got["default"] == "ask" and got["dontAsk"] == "deny" and got["bypassPermissions"] == "allow")


@test
def test_i19_brace_expansion_helper(ctx: Ctx):
    from halo_harness import perm_words
    ctx.check("simple", perm_words.brace_expand(".{env,bak}") == [".env", ".bak"])
    ctx.check("nested", perm_words.brace_expand("a{b,c{d,e}}") == ["ab", "acd", "ace"])
    ctx.check("no comma group unchanged", perm_words.brace_expand("{}") == ["{}"])
    ctx.check("bounded", len(perm_words.brace_expand("{a,b}" * 10)) == 64)


# ---- item 20 ------------------------------------------------------------------

@test
def test_i20_quoted_and_commented_parens_are_text(ctx: Ctx):
    with sandbox() as (_home, proj):
        for cmd, want in (('git commit -m "cleanup (rm build dir)"', OTHER),
                          ('git commit -m "chore: { rm old; }"', OTHER),
                          ('echo "(rm x)"', ALL_ALLOW), ("echo hi # (rm x)", ALL_ALLOW),
                          ("echo '$(rm x)'", OTHER), ("echo 'a `rm x` b'", OTHER)):
            got = decisions(proj, "Bash", {"command": cmd}, deny=["Bash(rm:*)"])
            ctx.check(f"not denied: {cmd!r} -> {got}", got == want)
        got = decisions(proj, "Bash", {"command": 'git commit -m "docs (git push flow)"'}, deny=["Bash(git push:*)"])
        ctx.check(f"a git push deny does not block a commit message, got {got}", got == OTHER)
        check_all_deny(ctx, proj, ["( rm x )", 'echo "$(rm x)"', "echo $(rm x)", "{ rm x; }",
                                   "echo `rm x`", "( ( rm x ) )", 'echo "$(echo ")"; rm x)"',
                                   "diff <(rm x) f", "tee >(rm x)"], ["Bash(rm:*)"])


@test
def test_i20_span_scanner(ctx: Ctx):
    subs = P.extract_subshell_bodies("a '$(no)' \"$(yes)\" # $(no2)\n$(also)")
    ctx.check(f"subs {subs!r}", subs == ["yes", "also"])
    groups = P._extract_group_bodies('x "(no)" ( yes ) # ( no2 )')
    ctx.check(f"groups {groups!r}", groups == [" yes "])


# ---- item 21 ------------------------------------------------------------------

@test
def test_i21_non_string_fields_return_a_decision(ctx: Ctx):
    calls = [("Bash", {"command": None}), ("Bash", {"command": ["ls"]}), ("Bash", {"command": 5}),
             ("Read", {"file_path": 123}), ("Edit", {"file_path": 5}), ("Glob", {"path": 5}),
             ("Grep", {"path": ["x"]}), ("WebFetch", {"url": 5}), ("PowerShell", {"command": None}),
             ("Skill", {"skill": 5}), ("Write", ["not", "a", "dict"])]
    with sandbox() as (_home, proj):
        for mode in ("default", "acceptEdits", "auto", "bypassPermissions"):
            e = engine(mode, proj, deny=["Bash(rm:*)", "Read(.env)", "WebFetch(domain:x.com)"],
                       ask=["Skill(s *)"])
            for tool, ti in calls:
                try:
                    d = e.decide(tool, ti)
                    ok = isinstance(d, P.Decision) and d.action in ("allow", "ask", "deny")
                except Exception as exc:  # noqa: BLE001 -- the pin is "never raises"
                    ok, d = False, exc
                ctx.check(f"{mode} {tool} {ti!r} -> {d!r}", ok)
        e = engine("auto", proj)
        ctx.check("a null Bash command is left to the tool to report",
                  e.decide("Bash", {"command": None}).action == "allow")


@test
def test_i21_hook_if_rule_never_raises(ctx: Ctx):
    from halo_harness.hooks import if_rule_matches
    with sandbox() as (_home, proj):
        for rule, tool, ti in (("Bash(rm:*)", "Bash", {"command": None}), ("Read(.env)", "Read", {"file_path": 5}),
                               ("WebFetch(domain:x.com)", "WebFetch", {"url": 5}),
                               ("PowerShell(rm:*)", "PowerShell", {"command": ["x"]})):
            try:
                ok = if_rule_matches(rule, tool, ti, None, cwd=proj) is False
            except Exception:  # noqa: BLE001
                ok = False
            ctx.check(f"{rule} on {ti!r} is simply no match", ok)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
