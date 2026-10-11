"""tests.test_review2_round10c -- pins for the vibes/review.md fix pass,
round 10, gym results and shared state files (findings 90, 92):

  * f90  gym results with no digest all overwrote `nodigest.json`; the
         "never raises" promise was false; scratch directories leaked
  * f92  `state.json`, `update-check.json`, `history.jsonl`: no lock on
         the read-modify-write, group-readable creation, torn last line
"""
from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.test_review2_round10 import scoped_home

test, TESTS = new_registry()


def _run_threads(target, count: int) -> None:
    threads = [threading.Thread(target=target, args=(i,)) for i in range(count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)


# ---- f90 ----------------------------------------------------------------------

@test
def test_f90_results_without_a_digest_do_not_overwrite_each_other(ctx: Ctx):
    from halo_harness.gym import iter_results, result_path, save_result
    with scoped_home() as home:
        base = {"host_name": "default", "digest": None, "finished_at": 1.0}
        a = save_result(home, {**base, "model": "qwen3:8b"})
        b = save_result(home, {**base, "model": "llama3:70b"})
        ctx.check(f"two files, got {a.name} / {b.name}", a != b and a.exists() and b.exists())
        ctx.check("the file is named for the model", "qwen3-8b" in a.name)
        save_result(home, {**base, "model": "qwen3:8b", "finished_at": 2.0})
        rows = iter_results(home)
        ctx.check(f"same model again replaces its own file only, got {len(rows)}", len(rows) == 2)
        ctx.check("a real digest still keys by digest",
                  result_path(home, "default", "sha256:abc", "qwen3:8b").name == "abc.json")


@test
def test_f90_run_gym_for_model_never_raises(ctx: Ctx):
    from halo_harness import gym_run
    real = gym_run._dispatch_gym

    def boom(*a, **kw):
        raise RuntimeError("catalog exploded")
    gym_run._dispatch_gym = boom
    try:
        with scoped_home() as home:
            result = gym_run.run_gym_for_model("ol:some-model", state_dir=home)
    finally:
        gym_run._dispatch_gym = real
    ctx.check(f"an error result, got {result.get('errors')}",
              isinstance(result, dict) and any("catalog exploded" in e for e in result.get("errors", [])))
    with scoped_home() as home:
        result = gym_run.run_gym_for_model("", state_dir=home)
        ctx.check("an empty ref is a result too", isinstance(result, dict) and result.get("errors"))


@test
def test_f90_scratch_directory_made_by_the_run_is_removed(ctx: Ctx):
    from halo_harness.gym_run import _scratch_dir
    with _scratch_dir(None) as made:
        (made / "work.txt").write_text("x", encoding="utf-8")
        ctx.check("the scratch directory exists during the run", made.is_dir())
    ctx.check("and is gone afterwards", not made.exists())
    try:
        with _scratch_dir(None) as failed_run:
            raise ValueError("task blew up")
    except ValueError:
        pass
    ctx.check("also removed when the run fails", not failed_run.exists())
    with scoped_home() as home:
        mine = home / "mine"
        with _scratch_dir(mine) as given:
            (given / "keep.txt").write_text("x", encoding="utf-8")
        ctx.check("a directory the caller named is left alone", (mine / "keep.txt").is_file())


# ---- f92 ----------------------------------------------------------------------

@test
def test_f92_file_lock_excludes_a_second_holder(ctx: Ctx):
    from halo_harness.filelock import file_lock
    with scoped_home() as home:
        target = home / "shared.json"
        with file_lock(target) as first:
            ctx.check("first holder acquires", first is True)
            with file_lock(target, timeout=0.2) as second:
                ctx.check("a second holder times out and runs unlocked", second is False)
        with file_lock(target, timeout=0.2) as again:
            ctx.check("released lock can be taken again", again is True)


@test
def test_f92_concurrent_state_json_writers_keep_every_change(ctx: Ctx):
    from halo_harness import launch_state
    with scoped_home() as home:
        cwds = [home / f"proj{i}" for i in range(8)]

        def record(i):
            launch_state.record_last_model(f"or:vendor/m{i}", cwd=cwds[i])
        _run_threads(record, len(cwds))
        data = json.loads(launch_state.state_path().read_text(encoding="utf-8"))
        kept = data["last_model"]["by_cwd"]
        ctx.check(f"all {len(cwds)} writers are present, got {len(kept)}", len(kept) == len(cwds))
        if os.name != "nt":
            ctx.check("state.json is private", (launch_state.state_path().stat().st_mode & 0o077) == 0)


@test
def test_f92_update_cache_is_read_modify_written_under_the_lock(ctx: Ctx):
    from halo_harness import update
    with scoped_home() as home:
        def write(i):
            update._update_cache(home, lambda c: c.__setitem__(f"chan{i}", {"commit": str(i)}))
        _run_threads(write, 8)
        cache = update._load_cache(home)
        ctx.check(f"every channel kept, got {sorted(cache)}", all(f"chan{i}" in cache for i in range(8)))
        wins = []
        _run_threads(lambda i: wins.append(update.note_due_today(home)), 8)
        ctx.check(f"the daily note is claimed exactly once, got {wins.count(True)}", wins.count(True) == 1)
        ctx.check("and the earlier channels were not lost", "chan0" in update._load_cache(home))


@test
def test_f92_history_append_is_private_whole_lines_and_recovers_a_torn_line(ctx: Ctx):
    from halo_harness.history import _read_jsonl, append_history_entry, rolo_history_path
    with scoped_home() as home:
        _run_threads(lambda i: append_history_entry(f"prompt {i}", str(home), timestamp=float(i + 1)), 8)
        path = rolo_history_path()
        ctx.check(f"eight whole entries, got {len(_read_jsonl(path))}", len(_read_jsonl(path)) == 8)
        if os.name != "nt":
            ctx.check("the file is created 0600", (path.stat().st_mode & 0o077) == 0)
        with open(path, "ab") as f:
            f.write(b'{"display": "torn')          # a crash mid-write: no newline
        append_history_entry("after the crash", str(home), timestamp=99.0)
        shown = [e["display"] for e in _read_jsonl(path)]
        ctx.check(f"the new entry starts its own line, got {shown[-2:]}", shown[-1] == "after the crash"
                  and len(shown) == 9)


# ---- sweep: findings 26 and 31 were still open after round 9 ----------------

@test
def test_f31_a_lone_surrogate_in_a_tool_result_does_not_kill_the_bridge_write(ctx: Ctx):
    from halo_harness.ccbridge.server import ToolBridgeServer

    class _Wire:
        data = b""

        def write(self, chunk):
            self.data += chunk
    wire = _Wire()
    ToolBridgeServer._write(wire, {"id": 1, "result": {"text": "a\ud800b"}})
    reply = json.loads(wire.data.decode("utf-8"))
    ctx.check(f"the reply was written with a replacement character, got {reply}",
              reply["result"]["text"] == "a�b")


@test
def test_f26_fired_jobs_carry_the_marker_and_do_not_arm_schedules(ctx: Ctx):
    from halo_harness import agents_schedule
    from halo_harness.agent.loop import Session
    seen = {}

    class _Registry:
        def start_background(self, command, **kw):
            seen.update(kw)
            return SimpleRecord(), None

    class SimpleRecord:
        job_id = "j1"
    session = type("S", (), {"job_registry": _Registry(), "cwd": "."})()
    agents_schedule._default_fire(session, {"name": "n", "prompt": "p", "team": "t"})
    ctx.check(f"the fired job's environment is marked, got {seen.get('env')}",
              seen.get("env", {}).get("HALO_SCHEDULED_FIRE") == "1")

    armed = []
    real_arm = agents_schedule.arm_session
    agents_schedule.arm_session = lambda *a, **kw: armed.append(1)
    holder = type("H", (), {"_team_scheduler": None, "agent_depth": 0, "team_control": object()})()
    saved = os.environ.get("HALO_SCHEDULED_FIRE")
    try:
        os.environ["HALO_SCHEDULED_FIRE"] = "1"
        Session._arm_team_scheduler_once(holder)
        ctx.check("a fired job arms nothing", armed == [])
        os.environ.pop("HALO_SCHEDULED_FIRE")
        Session._arm_team_scheduler_once(holder)
        ctx.check("an ordinary session still arms", armed == [1])
    finally:
        agents_schedule.arm_session = real_arm
        if saved is not None:
            os.environ["HALO_SCHEDULED_FIRE"] = saved


@test
def test_f18_rejected_an_https_url_never_retries_as_http(ctx: Ctx):
    """Finding 18 describes an https->http downgrade. WebFetch only ever
    returns to plain http when the caller TYPED an http URL (it tries https
    first); an https URL that fails is reported, never retried as http."""
    from halo_harness.tools import webfetch
    from halo_harness.tools.base import ToolContext, ToolResult
    tried = []
    tool = webfetch.WebFetchTool()
    tool._fetch_once = lambda url: tried.append(url) or ToolResult("tls failure", is_error=True)
    webfetch._CACHE.clear()
    result = tool.run({"url": "https://example.test/page", "prompt": "x"}, ToolContext(cwd=Path(".")))
    ctx.check(f"one https attempt, no http retry, got {tried}", tried == ["https://example.test/page"]
              and result.is_error)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
