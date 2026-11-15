"""tests.test_windows_long_state_paths -- 3.6.0.0 fx windows-shell batch 2.

On Windows without long-path support (LongPathsEnabled = 0, the default) a file whose full path is 260 characters
or more cannot be opened. The session log is `<home>/.halo/sessions/<slug>/<32 hex>.jsonl` and a sub-agent's files
sit one level deeper (`<session>/subagents/agent-<8>.evidence.json`). The slug for a project folder of about 200
characters was 207 characters (Claude Code's 200 + hash), so the log of such a project was 261 characters and its
sub-agent files up to 294: the session was not saved. Halo's own state folders now use `state_slug`, which on Windows
cuts the slug so those files stay under 260 (the hash of the whole folder keeps it unique). Claude Code's own folders
(`~/.claude/projects/<slug>/memory`) keep `project_slug` unchanged, and POSIX is unchanged.
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from halo_harness.config import paths as p

test, TESTS = new_registry()

HOME = r"C:\Users\someone\.halo"
# A project folder 218 characters long (the auditor's measured case).
LONG = "C:\\" + "\\".join(["project-folder-with-a-long-name-%02d" % i for i in range(7)])[:215]
def chk(ctx, desc, cond, got=None):
    ctx.check(desc if got is None else f"{desc} (got {got!r})", bool(cond))


SID = "0123456789abcdef0123456789abcdef"


def _files(home: str, slug: str) -> list:
    base = home + "\\sessions\\" + slug
    sub = base + "\\" + SID + "\\subagents\\agent-0123abcd"
    # A large tool output is spilled to `<session dir>\tool-results\<tool id>.txt` (tools/truncate.py,
    # tools/mcp_tool.py); a sub-agent's session dir is `<sid>\subagents\agent-<8>`.
    spill = "\\tool-results\\toolu_01XFDUDYJgAACzvnptvVoYEL.txt"
    return [base + "\\" + SID + ".jsonl", sub + ".jsonl", sub + ".meta.json", sub + ".evidence.json",
            base + "\\" + SID + spill, sub + spill]


@test
def test_long_project_state_files_stay_under_max_path_on_windows(ctx: Ctx):
    chk(ctx, "the case is the auditor's (218 characters)", len(LONG) == 218, len(LONG))
    old = p.project_slug(LONG)
    chk(ctx, "before: Claude Code's slug puts the session log at 260 or more",
              len(_files(HOME, old)[0]) >= 260, len(_files(HOME, old)[0]))
    slug = p.state_slug(LONG, base=HOME + "\\sessions", windows=True)
    longest = max(len(f) for f in _files(HOME, slug))
    chk(ctx, "every session and sub-agent file is under 260 characters", longest < 260, longest)
    chk(ctx, "the slug ends with the hash of the whole folder",
              slug.endswith("-" + p._base36(abs(p._java_string_hash(LONG)))), slug)
    chk(ctx, "the same folder gives the same slug", slug == p.state_slug(LONG, base=HOME + "\\sessions",
                                                                         windows=True))
    other = LONG[:-1] + "X"
    chk(ctx, "a folder that differs only past the cut gets another slug",
              p.state_slug(other, base=HOME + "\\sessions", windows=True) != slug)
    deep_home = "C:\\Users\\" + "u" * 60 + "\\.halo"
    deep = p.state_slug(LONG, base=deep_home + "\\sessions", windows=True)
    chk(ctx, "a long home cuts the slug further", max(len(f) for f in _files(deep_home, deep)) < 260,
              max(len(f) for f in _files(deep_home, deep)))


@test
def test_state_slug_is_project_slug_when_it_fits_or_off_windows(ctx: Ctx):
    short = r"C:\work\app"
    chk(ctx, "a short folder keeps Claude Code's slug on Windows",
              p.state_slug(short, base=HOME + "\\sessions", windows=True) == p.project_slug(short))
    chk(ctx, "POSIX keeps Claude Code's slug however long",
              p.state_slug(LONG, base="/home/someone/.halo/sessions", windows=False) == p.project_slug(LONG))


@test
def test_an_existing_long_folder_keeps_its_sessions(ctx: Ctx):
    # A Windows with long paths ON saved sessions under the full slug before this fix; they are not orphaned.
    with tempfile.TemporaryDirectory() as td:
        base = Path(td) / "sessions"
        full = p.project_slug(LONG)
        try:
            (base / full).mkdir(parents=True)
        except OSError:
            chk(ctx, "skipped: this machine cannot make the long folder", True)
            return
        chk(ctx, "the folder already there is used",
                  p.state_slug(LONG, base=str(base), windows=True) == full)


@test
def test_halo_state_writers_and_readers_agree_on_the_folder(ctx: Ctx):
    # The real calls (os.name decides): the log is written where every reader looks.
    with tempfile.TemporaryDirectory() as td:
        old = os.environ.get("BRIDGE_TEST_HOME")
        os.environ["BRIDGE_TEST_HOME"] = td
        try:
            from halo_harness.agent.log import SessionLog
            from halo_harness.agent.session_store import SessionStore
            from halo_harness.agent.sessions import sessions_dir
            want = p.state_slug(LONG)
            log = SessionLog(LONG)
            chk(ctx, "SessionLog uses state_slug", log.dir.name == want, log.dir.name)
            chk(ctx, "SessionStore uses state_slug", SessionStore(LONG).dir.name == want)
            chk(ctx, "sessions_dir uses state_slug", sessions_dir(LONG).name == want)
            if os.name == "nt":
                chk(ctx, "on Windows the session log path is under 260", len(str(log.path)) < 260,
                          len(str(log.path)))
            log._append({"type": "user", "content": "hi"})
            found = SessionLog.latest_for_cwd(LONG)
            chk(ctx, "latest_for_cwd finds the log just written",
                      found is not None and found.path.name == log.path.name)
        finally:
            if old is None:
                os.environ.pop("BRIDGE_TEST_HOME", None)
            else:
                os.environ["BRIDGE_TEST_HOME"] = old


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
