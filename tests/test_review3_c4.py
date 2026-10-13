"""tests.test_review3_c4 -- pins for the 3.0.2.0 review fix pass, round
C-studio-tools, part 4: the tools.

  * item 22   a foreground Bash call's capped-output spill file is removed at
              session teardown
  * item 23   the Python Grep engine skips hidden entries and .gitignore'd
              paths like ripgrep does
  * item 24   the 50 KB backstop is a byte budget
  * item 25   the http fallback body is cached under the http URL only
  * item 94   the read-only pool refuses mutating / program-running git forms
  * item 95   the read-only pool refuses tail -f and other flag-dependent forms
"""

from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


@test
def test_item22_foreground_spill_files_are_deleted_at_teardown(ctx: Ctx):
    from halo_harness.agent.jobs import JobRegistry
    from halo_harness.tools import _proc
    from halo_harness.tools.base import ToolContext
    from halo_harness.tools.bash import BashTool
    d = Path(tempfile.mkdtemp(prefix="bash-spill-"))
    cmd = {"command": "yes abcdefghij | head -c 400000"}
    reg = JobRegistry(object())
    res = BashTool().run(cmd, ToolContext(cwd=d, bash_state={"cwd": d}, job_registry=reg))
    m = re.search(r"saved to (.+?\.log)\]", res.content)
    spill = Path(m.group(1)) if m else None
    ctx.check(f"the result points at a spill file that exists, got {res.content[:80]!r}", spill is not None and spill.is_file())
    ctx.check("the session registry tracks it", spill in reg.spills)
    reg.kill_all()
    ctx.check("session teardown deletes it", spill is not None and not spill.exists() and not reg.spills)
    res = BashTool().run(cmd, ToolContext(cwd=d, bash_state={"cwd": d}))
    spill2 = Path(re.search(r"saved to (.+?\.log)\]", res.content).group(1))
    ctx.check("with no registry it is kept for the pointer and tracked for exit", spill2.is_file() and spill2 in _proc._ORPHAN_SPILLS)
    _proc._remove_orphan_spills()
    ctx.check("the exit hook deletes it", not spill2.exists())


@test
def test_item23_python_grep_follows_ripgreps_file_set(ctx: Ctx):
    from halo_harness.tools import grep_tool
    from halo_harness.tools.base import ToolContext
    root = Path(tempfile.mkdtemp(prefix="grep-ignore-"))

    def put(rel, text="NEEDLE\n"):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    for rel in (".env", ".github/workflows/ci.yml", "dist/bundle.js", "src.py", "a.log", "keep.log", "sub/inner.txt", "sub/ok.txt", "sub/dist/x.txt"):
        put(rel)
    put(".gitignore", "dist/\n*.log\n!keep.log\n")
    put("sub/.gitignore", "inner.txt\n")
    real = grep_tool.shutil.which
    grep_tool.shutil.which = lambda name, *a, **k: None  # force the Python engine
    try:
        def hits(base=root):
            out = grep_tool.GrepTool().run({"pattern": "NEEDLE", "path": str(base)}, ToolContext(cwd=root)).content
            return sorted(Path(x).relative_to(base).as_posix() for x in out.splitlines() if x.strip())

        ctx.check(f"outside a git checkout only hidden entries are skipped, got {hits()}", hits() == ["a.log", "dist/bundle.js", "keep.log", "src.py", "sub/dist/x.txt", "sub/inner.txt", "sub/ok.txt"])
        (root / ".git").mkdir()
        got = hits()
        ctx.check(f"inside one: hidden, dist/, *.log (but !keep.log) and sub/inner.txt are skipped, got {got}", got == ["keep.log", "src.py", "sub/ok.txt"])
        ctx.check("searching inside a hidden folder you name still works", hits(root / ".github") == ["workflows/ci.yml"])
        out = grep_tool.GrepTool().run({"pattern": "NEEDLE", "path": str(root / "a.log")}, ToolContext(cwd=root)).content
        ctx.check("a file named outright is searched even when ignored", "a.log" in out)
    finally:
        grep_tool.shutil.which = real


@test
def test_item24_the_backstop_is_a_byte_budget(ctx: Ctx):
    from halo_harness.tools.truncate import MAX_BYTES, spill_and_truncate
    cjk = "\n".join("中" * 601 for _ in range(100))
    out = spill_and_truncate(cjk, cap=100000, session_dir=None, tool_use_id=None)
    size = len(out.encode("utf-8"))
    ctx.check(f"CJK text stays under the 50 KB byte cap, got {size} bytes", size <= MAX_BYTES)
    ctx.check("the pointer names the cap and the text decodes cleanly", "2000-line/50KB cap" in out and "�" not in out)
    ascii_text = "x" * 200_000
    a = spill_and_truncate(ascii_text, cap=100000, session_dir=None, tool_use_id=None)
    ctx.check("ASCII keeps the old shape: 60% head, 30% tail of 50 KB", a.startswith("x" * 30720) and len(a) < MAX_BYTES and "2000-line/50KB cap" in a)
    small = spill_and_truncate("中" * 10000, cap=100000, session_dir=None, tool_use_id=None)
    ctx.check("30000 bytes of CJK is under the backstop and returned whole", small == "中" * 10000)
    capped = spill_and_truncate("y" * 6000, cap=5000, session_dir=None, tool_use_id=None)
    ctx.check("the per-tool cap keeps its own wording", "result truncated at 5000 characters" in capped)
    lines = "\n".join("中" * 4 for _ in range(3000))
    byl = spill_and_truncate(lines, cap=1_000_000, session_dir=None, tool_use_id=None)
    ctx.check("the line backstop is a byte budget too", len(byl.encode("utf-8")) < len("\n".join(["中" * 4] * 2000).encode("utf-8")) and "2000-line" in byl)


@test
def test_item25_the_http_fallback_is_cached_under_the_http_url(ctx: Ctx):
    from halo_harness.tools import webfetch as W
    from halo_harness.tools.base import ToolResult
    calls = []

    def fake(self, url):
        calls.append(url)
        if url.startswith("https://"):
            return ToolResult("HTTP error fetching: 404", is_error=True)
        return b"HTTP-ORIGIN BODY", "text/plain", url

    real = W.WebFetchTool._fetch_once
    W.WebFetchTool._fetch_once = fake
    W._CACHE.clear()
    try:
        tool = W.WebFetchTool()
        r = tool.run({"url": "http://host.example/page"}, None)
        ctx.check("the fallback still answers silently with the http body", not r.is_error and r.content == "HTTP-ORIGIN BODY")
        ctx.check(f"only the http URL is cached, got {list(W._CACHE)}", "https://host.example/page" not in W._CACHE and "http://host.example/page" in W._CACHE)
        again = tool.run({"url": "https://host.example/page"}, None)
        ctx.check("a later https fetch is not served the http origin's content", again.is_error and calls[-1] == "https://host.example/page")
    finally:
        W.WebFetchTool._fetch_once = real
        W._CACHE.clear()


@test
def test_item94_git_forms_that_mutate_or_run_programs_are_not_pooled(ctx: Ctx):
    from halo_harness.tools.bash import bash_command_is_read_only as ro
    for cmd in ("git remote add evil https://evil/x.git", "git remote set-url origin https://evil/x.git", "git remote remove origin",
                "git remote rename a b", "git diff --output=/tmp/pwned.txt", "git show --output=/tmp/x", "git log --output /tmp/x",
                "git log --ext-diff", "git diff --ext-diff", "git grep -Oless foo", "git grep --open-files-in-pager=less foo"):
        ctx.check(f"not pooled: {cmd}", ro(cmd) is False)
    for cmd in ("git remote", "git remote -v", "git remote show origin", "git status", "git log --oneline -5", "git diff HEAD", "git show HEAD:README.md",
                "git branch -a", "git stash list", "git config --get user.name", "git grep foo"):
        ctx.check(f"still pooled: {cmd}", ro(cmd) is True)


@test
def test_item95_flag_dependent_readers_are_screened(ctx: Ctx):
    from halo_harness.tools.bash import bash_command_is_read_only as ro
    for cmd in ("tail -f /var/log/syslog", "tail -F x.log", "tail --follow=name x", "tail -fn5 x", "tail -n 5 -f x", "head -f x",
                "date -s 2030-01-01", "date --set=2030-01-01", "hostname newname", "tree -o out.txt", "rg --pre=cat NEEDLE", "file -C", "xxd -r in out"):
        ctx.check(f"not pooled: {cmd}", ro(cmd) is False)
    for cmd in ("tail -n 20 x.log", "tail x", "head -n 5 x", "cat x", "ls -la", "date", "date -u", "hostname", "hostname -f", "tree -L 2", "rg NEEDLE src", "file x", "xxd x", "find . -name main.py"):
        ctx.check(f"still pooled: {cmd}", ro(cmd) is True)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="review3 c4 tests"))
