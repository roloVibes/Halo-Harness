"""tests.test_security_round4b -- 2.0.10 round 4, security fix pass 2,
findings 14-16 of docs/harness/SECURITY-REVIEW-2.0.10.md.

14  a malformed deny/ask rule is surfaced (load notice, /permissions,
    doctor) instead of being silently inert; it is never rewritten
15  a Read deny/ask path rule reaches `cat ~/...`, the Bash searchers and
    copiers (grep/sed/awk/cp/...), `< file`, and Grep/Glob over a directory
16  a path rule whose own text contains a symlink matches after resolving
    both sides the same way; Windows trailing dots/spaces are judged as
    the OS opens them
"""
from __future__ import annotations

import inspect
import io
import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all

test, TESTS = new_registry()

os.environ.setdefault("BRIDGE_TEST_HOME", tempfile.mkdtemp(prefix="halo-sec4b-home-"))

import halo_harness.permissions as P
from halo_harness.tools.base import ToolContext
from halo_harness.tools.glob_tool import GlobTool
from halo_harness.tools.grep_tool import GrepTool


def _tmp() -> Path:
    return Path(tempfile.mkdtemp(prefix="halo-sec4b-")).resolve()


def _engine(tmp: Path, *, deny=(), ask=(), mode: str = "auto"):
    return P.PermissionEngine(
        mode=mode, cwd=tmp,
        deny_rules=[P.parse_rule(r, source="user", base_dir=tmp, action="deny") for r in deny],
        ask_rules=[P.parse_rule(r, source="user", base_dir=tmp, action="ask") for r in ask])


# ---- 14: malformed rules are surfaced -------------------------------------------------


@test
def test_f14_invalid_rules_are_collected_and_named(ctx: Ctx):
    bad = P.parse_rule("Bash(rm:* -rf)", source="settings", action="deny")
    good = P.parse_rule("Bash(rm:*)", source="settings", action="deny")
    ctx.check("the rule parses as invalid", bad.kind == "invalid")
    found = P.invalid_rules([bad, good], [], [])
    ctx.check("exactly the malformed rule is reported", len(found) == 1 and found[0][1] == "Bash(rm:* -rf)")
    text = P.describe_invalid_rules([bad, good], [])
    ctx.check("the line names the rule and the reason",
              "Bash(rm:* -rf)" in text and "must be at the end" in text and text.count("\n") == 0)
    ctx.check("nothing to say when every rule parses", P.describe_invalid_rules([good], []) == "")
    ctx.check("the inert rule is not rewritten into a different one", bad.value is None)


@test
def test_f14_load_notice_prints_once(ctx: Ctx):
    P._INVALID_NOTICED.clear()
    bad = [P.parse_rule("Bash(rm:* -rf)", source="settings", action="deny")]
    out = io.StringIO()
    P.notice_invalid_rules(bad, [], file=out)
    P.notice_invalid_rules(bad, [], file=out)
    ctx.check("one line, printed once", out.getvalue().count("Bash(rm:* -rf)") == 1)
    from halo_harness import headless
    ctx.check("build_session calls the notice", "notice_invalid_rules" in inspect.getsource(headless.build_session))


@test
def test_f14_permissions_views_and_doctor_name_the_inactive_rule(ctx: Ctx):
    tmp = _tmp()
    from halo_harness.commands.builtins import _cmd_permissions
    settings = SimpleNamespace(permissions_allow=[], permissions_ask=[], permissions_deny=["Bash(rm:* -rf)"])
    text = _cmd_permissions("", SimpleNamespace(settings=settings, permission_mode="auto"))
    ctx.check("/permissions (headless) names the inactive rule",
              "Inactive deny rule 'Bash(rm:* -rf)'" in text)
    from halo_harness.controller import Controller
    engine = _engine(tmp, deny=["Bash(rm:* -rf)", "Bash(ls:*)"])
    rows = Controller.list_permission_rules(SimpleNamespace(session=SimpleNamespace(permission_engine=engine)))
    marked = [r for r in rows if "INACTIVE" in r["rule"]]
    ctx.check("the TUI list marks only the inactive rule", len(marked) == 1 and "Bash(rm:* -rf)" in marked[0]["rule"])
    (tmp / ".claude").mkdir()
    (tmp / ".claude" / "settings.json").write_text(
        json.dumps({"permissions": {"deny": ["Bash(rm:* -rf)"]}}), encoding="utf-8")
    from halo_harness import doctor
    line = doctor._check_permission_rules(tmp)
    ctx.check("doctor warns and names it", line is not None and line.startswith(doctor.WARN)
              and "Bash(rm:* -rf)" in line)
    ctx.check("doctor omits the rule when a project has none",
              "Bash(rm:* -rf)" not in (doctor._check_permission_rules(_tmp()) or ""))

# ---- 15: Read rules reach the readers --------------------------------------------------


@test
def test_f15_read_deny_reaches_home_paths_and_more_readers(ctx: Ctx):
    tmp = _tmp()
    (tmp / ".env").write_text("K=1\n", encoding="utf-8")
    home = os.path.expanduser("~").replace(chr(92), "/")
    eng_home = _engine(tmp, deny=["Read(~/.ssh/**)"])
    for cmd in ("cat ~/.ssh/id_rsa", "head -1 ~/.ssh/id_rsa", "grep K ~/.ssh/id_rsa",
                "cat $HOME/.ssh/id_rsa", "cat ${HOME}/.ssh/id_rsa", f"cat {home}/.ssh/id_rsa",
                "echo $(cat ~/.ssh/id_rsa)", "(cat ~/.ssh/id_rsa)"):
        ctx.check(f"denied: {cmd}", eng_home.decide("Bash", {"command": cmd}).action == "deny")
    eng = _engine(tmp, deny=["Read(./.env)"])
    for cmd in ("grep K .env", "egrep K .env", "sed -n p .env", "awk 1 .env", "cp .env /tmp/o",
                "cat < .env", "cat .e*", "/bin/cat .env", "if true; then cat .env; fi", "tar cf o.tar .env",
                "grep -f .env other", "sort .env", "diff .env other", "grep --file=.env other",
                "find . -exec cat .env ;"):
        ctx.check(f"denied: {cmd}", eng.decide("Bash", {"command": cmd}).action == "deny")
    for cmd in ("grep .env README.md", "cp a .env", "cat other.txt", "sed -n p other.txt", "grep K other"):
        ctx.check(f"not denied: {cmd}", eng.decide("Bash", {"command": cmd}).action == "allow")
    free = P.PermissionEngine(mode="auto", cwd=tmp)
    ctx.check("auto with no rules allows grep K .env", free.decide("Bash", {"command": "grep K .env"}).action == "allow")
    eng_ask = _engine(tmp, ask=["Read(./.env)"])
    ctx.check("an ask rule holds for sed", eng_ask.decide("Bash", {"command": "sed -n p .env"}).action == "ask")


@test
def test_f15_grep_and_glob_over_a_directory_skip_denied_files(ctx: Ctx):
    tmp = _tmp()
    (tmp / ".env").write_text("SECRET_KEY=1\n", encoding="utf-8")
    (tmp / "ok.txt").write_text("SECRET_KEY=2\n", encoding="utf-8")
    (tmp / "sub").mkdir()
    (tmp / "sub" / ".env").write_text("SECRET_KEY=3\n", encoding="utf-8")
    engine = _engine(tmp, deny=["Read(./.env)"])
    tctx = ToolContext(cwd=tmp, permission_engine=engine)
    grep = GrepTool().run({"pattern": "SECRET_KEY", "path": str(tmp), "output_mode": "content"}, tctx)
    ctx.check("Grep finds the allowed file", "ok.txt" in grep.content and "SECRET_KEY=2" in grep.content)
    ctx.check("Grep never returns the denied file", ".env" not in grep.content and "SECRET_KEY=1" not in grep.content
              and "SECRET_KEY=3" not in grep.content)
    nopath = GrepTool().run({"pattern": "SECRET_KEY"}, tctx)
    ctx.check("Grep with no path (cwd) is filtered too", ".env" not in nopath.content and "ok.txt" in nopath.content)
    glob = GlobTool().run({"pattern": "**/*", "path": str(tmp)}, tctx)
    ctx.check("Glob lists the allowed file and skips the denied ones",
              "ok.txt" in glob.content and ".env" not in glob.content)
    plain = ToolContext(cwd=tmp)
    ctx.check("without an engine nothing is filtered (auto, no rules)",
              ".env" in GrepTool().run({"pattern": "SECRET_KEY", "path": str(tmp)}, plain).content)
    ctx.check("engine.read_denied answers per path",
              engine.read_denied(tmp / ".env") and not engine.read_denied(tmp / "ok.txt"))


@test
def test_f15_read_ask_rule_asks_for_a_directory_search(ctx: Ctx):
    tmp = _tmp()
    (tmp / ".env").write_text("K=1\n", encoding="utf-8")
    (tmp / "ok.txt").write_text("K=2\n", encoding="utf-8")
    engine = _engine(tmp, ask=["Read(./.env)"])
    got = engine.decide("Grep", {"pattern": "K", "path": str(tmp)}, GrepTool())
    ctx.check("Grep over a directory holding an ask-ruled file asks", got.action == "ask")
    got = engine.decide("Glob", {"pattern": "*", "path": str(tmp)}, GlobTool())
    ctx.check("Glob over the same directory asks", got.action == "ask")
    (tmp / "clean").mkdir()
    (tmp / "clean" / "a.txt").write_text("K\n", encoding="utf-8")
    got = engine.decide("Grep", {"pattern": "K", "path": str(tmp / "clean")}, GrepTool())
    ctx.check("a directory without such a file does not ask", got.action == "allow")
    free = P.PermissionEngine(mode="auto", cwd=tmp)
    ctx.check("auto with no rules allows the search",
              free.decide("Grep", {"pattern": "K", "path": str(tmp)}, GrepTool()).action == "allow")

# ---- 16: symlinks and Windows names -------------------------------------------------------


@test
def test_f16_rule_text_with_a_symlink_matches_the_resolved_target(ctx: Ctx):
    real_abs = P._abs_posix

    def fake(path):
        s = str(path).replace("\\", "/")
        if s.startswith("/data/link"):
            return "/data/real" + s[len("/data/link"):]
        return real_abs(path)

    P._abs_posix = fake
    try:
        base = Path(tempfile.gettempdir())
        regex, _ = P.path_rule_regex("//data/link/**", base, any_depth=True)
        ctx.check("a rule spelled through the link hits the resolved path", bool(regex.match("/data/real/secret.txt")))
        ctx.check("and still the spelled path", bool(regex.match("/data/link/secret.txt")))
        ctx.check("an unrelated sibling is untouched", not regex.match("/data/other/secret.txt"))
        reg2, _ = P.path_rule_regex("//data/link/one.txt", base, any_depth=True)
        ctx.check("a fully literal rule resolves too", bool(reg2.match("/data/real/one.txt")))
    finally:
        P._abs_posix = real_abs


@test
def test_f16_real_symlink_deny_rule(ctx: Ctx):
    tmp = _tmp()
    real = tmp / "real"
    real.mkdir()
    (real / "secret.txt").write_text("s\n", encoding="utf-8")
    try:
        os.symlink(str(real), str(tmp / "link"), target_is_directory=True)
    except (OSError, NotImplementedError):
        raise SkipTest("symlinks unavailable on this host")
    link_rule = "Read(//" + str(tmp / "link").replace("\\", "/").lstrip("/") + "/**)"
    engine = _engine(tmp, deny=[link_rule])
    got = engine.decide("Read", {"file_path": str(tmp / "link" / "secret.txt")})
    ctx.check("reading through the link is denied", got.action == "deny")
    got = engine.decide("Read", {"file_path": str(real / "secret.txt")})
    ctx.check("reading the real path is denied too", got.action == "deny")
    rel = _engine(tmp, deny=["Read(link/**)"])
    ctx.check("a relative rule through the link also holds",
              rel.decide("Read", {"file_path": str(real / "secret.txt")}).action == "deny")


@test
def test_f16_windows_trailing_dot_and_space_are_judged_as_opened(ctx: Ctx):
    ctx.check("normalizer drops trailing dots, spaces and stream suffixes",
              P._win_normalize_posix("C:/proj/.env.") == "C:/proj/.env"
              and P._win_normalize_posix("C:/proj/.env ") == "C:/proj/.env"
              and P._win_normalize_posix("C:/proj/.env::$DATA") == "C:/proj/.env"
              and P._win_normalize_posix("C:/proj/../a/b") == "C:/proj/../a/b")
    tmp = _tmp()
    saved = P._IS_WINDOWS
    P._IS_WINDOWS = True
    try:
        engine = P.PermissionEngine(mode="auto", cwd=tmp, deny_rules=[
            P.parse_rule("Edit(.env)", source="user", base_dir=tmp, action="deny")])
        for name in (".env.", ".env ", ".env::$DATA", ".env"):
            got = engine.decide("Write", {"file_path": str(tmp / name)})
            ctx.check(f"Write {name!r} is denied", got.action == "deny")
        got = engine.decide("Write", {"file_path": str(tmp / "other.txt")})
        ctx.check("another file is not", got.action == "allow")
    finally:
        P._IS_WINDOWS = saved
    allow_engine = P.PermissionEngine(mode="default", cwd=tmp, allow_rules=[
        P.parse_rule("Edit(.env)", source="user", base_dir=tmp, action="allow")])
    P._IS_WINDOWS = True
    try:
        got = allow_engine.decide("Write", {"file_path": str(tmp / ".env.")})
        ctx.check("the allow side is not widened by the normalization", got.action != "allow")
    finally:
        P._IS_WINDOWS = saved


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
