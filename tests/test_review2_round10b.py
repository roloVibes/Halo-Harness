"""tests.test_review2_round10b -- pins for the vibes/review.md fix pass,
round 10, background runs and recall (findings 87, 88, 91):

  * f87  the bg PID-reuse guard was a no-op where there is no /proc
  * f88  recall's fixed temp file, cross-project prune, full-log reads
  * f91  `halo --bg -p` lost piped stdin
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.test_review2_round10 import scoped_home

test, TESTS = new_registry()


class _FakeOs:
    """The `os` module as seen by bg_run on a box with no /proc."""

    def __init__(self):
        self.name = "posix"
        self.path = SimpleNamespace(exists=lambda p: False)

    def __getattr__(self, item):
        return getattr(os, item)


def _ps_result(stdout, code=0):
    return lambda *a, **kw: SimpleNamespace(stdout=stdout, returncode=code)


# ---- f87 ----------------------------------------------------------------------

@test
def test_f87_start_time_comes_from_ps_when_there_is_no_proc(ctx: Ctx):
    from halo_harness import bg_run
    real_os, real_run, real_alive = bg_run.os, bg_run.subprocess.run, bg_run.pid_alive
    bg_run.os = _FakeOs()
    try:
        bg_run.subprocess.run = _ps_result("Mon Oct  5 10:00:00 2026\n")
        first = bg_run.process_start_time(4242)
        ctx.check(f"a ps-based fingerprint, got {first!r}", first == "ps:Mon Oct 5 10:00:00 2026")
        bg_run.subprocess.run = _ps_result("", code=1)
        ctx.check("a pid ps cannot find has no fingerprint", bg_run.process_start_time(4242) is None)

        def boom(*a, **kw):
            raise OSError("no ps")
        bg_run.subprocess.run = boom
        ctx.check("a missing ps is None, not a crash", bg_run.process_start_time(4242) is None)
        # the guard now refuses a pid that started at a different time
        bg_run.subprocess.run = _ps_result("Tue Oct  6 11:11:11 2026\n")
        bg_run.pid_alive = lambda pid: True
        meta = {"pid": 4242, "start_time": "ps:Mon Oct 5 10:00:00 2026"}
        ctx.check("a reused pid is not our process", bg_run.is_our_process(meta) is False)
        meta["start_time"] = "ps:Tue Oct 6 11:11:11 2026"
        ctx.check("the same start time is ours", bg_run.is_our_process(meta) is True)
    finally:
        bg_run.os, bg_run.subprocess.run, bg_run.pid_alive = real_os, real_run, real_alive


@test
def test_f87_a_finished_run_is_never_ours_even_without_a_start_time(ctx: Ctx):
    from halo_harness.bg_run import is_our_process
    with scoped_home() as home:
        status = home / "status.json"
        meta = {"pid": os.getpid(), "status_path": str(status)}
        ctx.check("no status file, no start time: pid-only answer (alive)", is_our_process(meta) is True)
        status.write_text("{}", encoding="utf-8")
        ctx.check("status.json written by the wrapper means the run is over", is_our_process(meta) is False)


# ---- f91 ----------------------------------------------------------------------

@test
def test_f91_piped_stdin_is_spooled_and_handed_to_the_child(ctx: Ctx):
    from halo_harness.bg_run import start_background_run
    seen = {}

    def fake_popen(command, **kw):
        stdin = kw["stdin"]
        seen["stdin"] = stdin
        seen["data"] = stdin.read() if hasattr(stdin, "read") else None
        return SimpleNamespace(pid=999991)

    with scoped_home():
        info = start_background_run(["-p"], popen=fake_popen, stdin_data="fix the bug   now".encode("utf-8"))
        ctx.check(f"the child's stdin held the piped bytes, got {seen['data']!r}",
                  seen["data"] == "fix the bug   now".encode("utf-8"))
        ctx.check("the spool file sits in the run directory", (Path(info["log_path"]).parent / "stdin.bin").is_file())
        ctx.check("our handle was closed after the spawn", seen["stdin"].closed)
        start_background_run(["-p", "task"], popen=fake_popen)
        ctx.check("no piped input -> the null device as before", seen["stdin"] == subprocess.DEVNULL)


class _PipedStdin:
    def __init__(self, data: bytes):
        self.buffer = io.BytesIO(data)

    def isatty(self):
        return False

    def read(self, *a):
        return self.buffer.read(*a).decode("utf-8")


@test
def test_f91_cli_reads_piped_stdin_for_a_bg_run_without_a_prompt(ctx: Ctx):
    from halo_harness import bg_run, cli
    captured = []
    real_start, real_stdin = bg_run.start_background_run, sys.stdin
    bg_run.start_background_run = lambda argv, **kw: captured.append((argv, kw)) or {
        "id": "x", "log_path": "x.log", "pid": 1, "meta_path": "m"}
    try:
        with scoped_home():
            sys.stdin = _PipedStdin(b"summarize the repo")
            code = cli.main(["--bg", "-p"])
            ctx.check(f"exit 0, got {code}", code == 0)
            ctx.check(f"argv lost --bg only, got {captured[0][0]}", "--bg" not in captured[0][0])
            ctx.check(f"the piped text rode along, got {captured[0][1]}",
                      captured[0][1].get("stdin_data") == b"summarize the repo")
            captured.clear()
            sys.stdin = _PipedStdin(b"unused")
            cli.main(["--bg", "-p", "inline prompt"])
            ctx.check("an inline prompt reads no stdin", captured[0][1].get("stdin_data") is None)
    finally:
        bg_run.start_background_run, sys.stdin = real_start, real_stdin


# ---- f88 ----------------------------------------------------------------------

def _enable_fake_embeddings(recall):
    from halo_harness.providers import embeddings
    saved = (embeddings.embeddings_enabled, embeddings.embed_texts, recall._memory_sources)
    calls = []
    embeddings.embeddings_enabled = lambda: True
    embeddings.embed_texts = lambda texts: calls.append(list(texts)) or [[1.0, 0.0] for _ in texts]
    recall._memory_sources = lambda cwd: []

    def restore():
        embeddings.embeddings_enabled, embeddings.embed_texts, recall._memory_sources = saved
    return calls, restore


@test
def test_f88_recall_prune_keeps_other_projects_and_never_reads_unchanged_logs(ctx: Ctx):
    from halo_harness import recall
    calls, restore = _enable_fake_embeddings(recall)
    try:
        with scoped_home() as home:
            state = home / ".halo"
            sdir = state / "sessions" / "proj"
            sdir.mkdir(parents=True)
            log = sdir / "s1.jsonl"
            log.write_text(json.dumps({"type": "user", "content": [{"type": "text", "text": "hello there"}]}) + "\n",
                           encoding="utf-8")
            other_memory = home / "other-project-topic.md"   # another project's memory topic, still on disk
            other_memory.write_text("notes", encoding="utf-8")
            index = recall._index_path(state)
            recall._save_index(index, {
                str(other_memory): {"id": str(other_memory), "kind": "memory", "title": "o", "mtime": 1.0, "vec": [1.0]},
                str(home / "deleted.md"): {"id": str(home / "deleted.md"), "kind": "memory", "title": "d",
                                           "mtime": 1.0, "vec": [1.0]}})
            report = recall.build_index(state)
            ids = set(recall._load_index(index))
            ctx.check(f"the other project's vector is kept, got {sorted(ids)}", str(other_memory) in ids)
            ctx.check("the vector whose file is gone is pruned", str(home / "deleted.md") not in ids
                      and report["pruned"] == 1)
            ctx.check("the session was embedded once", str(log) in ids and len(calls) == 1)
            # unchanged log: not read, not embedded again
            known = recall._load_index(index)
            rows = recall._session_sources(state, known)
            ctx.check(f"unchanged log returns no text to read, got {rows}", rows[0][2] is None)
            recall.build_index(state)
            ctx.check("a second build embeds nothing", len(calls) == 1)
    finally:
        restore()


@test
def test_f88_recall_save_uses_a_temp_file_of_its_own(ctx: Ctx):
    from halo_harness import recall
    with scoped_home() as home:
        path = home / "embeddings.jsonl"
        (home / "embeddings.jsonl.tmp").mkdir()      # the old fixed name, taken by something else
        recall._save_index(path, {"a": {"id": "a", "kind": "session", "title": "t", "mtime": 1.0, "vec": [1.0]}})
        ctx.check("the write succeeded despite the old fixed name being taken", "a" in recall._load_index(path))
        leftovers = [p.name for p in home.iterdir() if p.name.startswith(".embeddings.")]
        ctx.check(f"no temp file left behind, got {leftovers}", leftovers == [])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
