"""tests.test_steward_job -- Halo 3.3.4.0 R4: the steward's job
(ollama_steward/job.py, job_state.py, notes.py) on a fixture state dir with
a fake clock: it runs on the timer while calls flow, at once on a server
event that passed its quiet period, and is idle otherwise; one instance per
state dir (a second start names the holder, `--watch` too); the frames it
publishes to a fake bridge ({stage, say, data}: the shape R5's panel reads);
every `say` a note line; `halo ollama steward status`; the hub's note on a
member; the fleet attention row. No model is called (the agent has no model
here, or a fake one), no server is read (readers stubbed, the watch faked).
Run: python -m tests.test_steward_job
"""
from __future__ import annotations

import contextlib
import io
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
ensure_default_provider_credentials()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.steward_seed import Home, line  # noqa: E402

test, TESTS = new_registry()
NO_READS = {"card_reader": None, "catalog_reader": None}


def _job(h, frames=None, **kw):
    from halo_harness.ollama_steward.job import StewardJob
    kw.setdefault("model", (None, "no steward model: set ollama.steward.model"))
    return StewardJob(h.state, readers=NO_READS, watch=False, publish=(frames.append if frames is not None else None),
                      **kw)


def _small_window(h, ago: float = 120.0) -> None:
    h.cap("qwen3.8:27b", 65536)
    h.calls(*[line(prompt_eval_count=31000, ago=ago - i, session=None) for i in range(5)])


def _stages(frames) -> list:
    return [f["data"]["stage"] for f in frames]


@test
def test_runs_on_the_timer_while_calls_flow_and_idles_without_them(ctx: Ctx):
    with Home() as h:
        _small_window(h)
        frames: list = []
        job = _job(h, frames)
        t0 = time.time()
        ctx.check("the first tick runs (calls in the last 15 minutes)", job.tick(t0) is not None)
        ctx.check("a tick 10 s later does not", job.tick(t0 + 10) is None)
        ctx.check("a tick past every_s (300 s) runs again", job.tick(t0 + 301) is not None)
        n = len(frames)
        ctx.check("an hour on, no calls in the last 15 minutes: no run", job.tick(t0 + 3600) is None)
        ctx.check(f"one idle frame, got {_stages(frames[n:])}", _stages(frames[n:]) == ["idle"])
        job.tick(t0 + 4000)
        ctx.check("idle is said once until the job runs again", _stages(frames[n:]) == ["idle"])
        f = frames[0]
        ctx.check(f"a frame is the steward event on its own session id, got {sorted(f)}",
                  f["event"] == "steward" and f["session_id"] == "ollama:steward" and isinstance(f["ts"], float))
        ctx.check(f"its data is {{stage, say, data}}, got {sorted(f['data'])}",
                  sorted(f["data"]) == ["data", "say", "stage"] and f["data"]["stage"] in ("finding", "change", "note", "idle"))


@test
def test_a_notify_event_runs_it_at_once(ctx: Ctx):
    with Home() as h:
        h.calls(line(ago=7200))  # an old call: the timer alone would not run
        job = _job(h)
        t0 = time.time()
        ctx.check("no calls flow: no run", job.tick(t0) is None)
        job.on_event({"kind": "loaded", "severity": "info", "notify": True})
        ctx.check("an info event does not run it", job.tick(t0 + 1) is None)
        job.on_event({"kind": "cpu-spill", "severity": "warn", "notify": False})
        ctx.check("an event inside its quiet period does not", job.tick(t0 + 2) is None)
        job.on_event({"kind": "cpu-spill", "severity": "warn", "notify": True})
        ctx.check("a warn event that passed its quiet period runs it", job.tick(t0 + 3) is not None)
        ctx.check("and only once", job.tick(t0 + 4) is None)


@test
def test_findings_and_changes_become_frames_and_note_lines(ctx: Ctx):
    from halo_harness.ollama_steward import notes
    with Home() as h:
        _small_window(h)
        frames: list = []
        job = _job(h, frames)
        t0 = time.time()
        done = job.tick(t0)
        ctx.check(f"auto applied the window change, got {len(done['applied'])}", len(done["applied"]) == 1)
        ctx.check(f"a finding frame and a change frame, got {_stages(frames)}",
                  "finding" in _stages(frames) and "change" in _stages(frames))
        change = next(f for f in frames if f["data"]["stage"] == "change")
        ctx.check(f"the change frame says the profile line, got {change['data']['say']!r}",
                  change["data"]["say"].startswith("steward: num_ctx 65536"))
        rows = notes.read(h.state)
        ctx.check(f"every say is a note line, got {[r['stage'] for r in rows]}",
                  [r["say"] for r in rows] == [f["data"]["say"] for f in frames])
        ctx.check("a change raises the attention flag", any(r["attention"] for r in rows if r["stage"] == "change"))
        n = len(frames)
        job.tick(t0 + 301)
        ctx.check(f"the same finding is not said again, got {_stages(frames[n:])}", "finding" not in _stages(frames[n:]))


@test
def test_one_job_per_state_dir(ctx: Ctx):
    from halo_harness.ollama_steward import job_state
    from halo_harness.ollama_steward.cli_steward import cmd_ollama_steward
    with Home() as h:
        first = _job(h, where="studio")
        ok, why = first.start()
        try:
            ctx.check(f"the first start holds the lock, got {why!r}", ok)
            ctx.check("status says it runs", job_state.status(h.state)["running"])
            ok2, why2 = _job(h, where="hub").start()
            ctx.check(f"a second start is refused and names the holder, got {why2!r}",
                      not ok2 and "already runs" in why2 and "studio" in why2)
            err = io.StringIO()
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                rc = cmd_ollama_steward(["--watch"])
            ctx.check(f"`--watch` says who holds it and exits 1, got {rc} {err.getvalue()!r}",
                      rc == 1 and "already runs" in err.getvalue())
        finally:
            first.stop()
        ctx.check("after a stop status says it does not run", not job_state.status(h.state)["running"])
        again = _job(h)
        ok3, _ = again.start()
        again.stop()
        ctx.check("and a new job can start", ok3)


@test
def test_the_watch_thread_wakes_the_timer(ctx: Ctx):
    from halo_harness.ollama_steward.job import StewardJob, current

    def fake_watch(state_dir, host, stop, *, on_event=None):
        on_event({"kind": "http-500", "severity": "error", "notify": True})
        stop.wait(5)

    with Home() as h:
        frames: list = []
        job = StewardJob(h.state, host=object(), readers=NO_READS, watch=fake_watch, publish=frames.append,
                         model=(None, "none"))
        ok, _ = job.start()
        try:
            deadline = time.time() + 5
            while job.last_run is None and time.time() < deadline:
                time.sleep(0.05)
            ctx.check("the event from the tail ran the steward", ok and job.last_run is not None)
            ctx.check("current() is the page's catch-up view", (current(h.state) or {}).get("where") == "watch")
        finally:
            job.stop()
        ctx.check("a stopped job leaves current()", current(h.state) is None)


@test
def test_status_prints_where_since_the_last_run_and_the_last_note(ctx: Ctx):
    from halo_harness.ollama_steward.cli_steward import cmd_ollama_steward
    with Home() as h:
        _small_window(h)
        job = _job(h, where="hub", model=("ol:qwen3.5:9b", "ollama.steward.model"),
                   caller=lambda *a, **k: {"text": "The 27B on pc needed a larger window.\nIt now gets 65,536.",
                                           "local": True})
        job.run_once(time.time())  # before start(): the timer's own first tick then finds nothing due
        ok, _ = job.start()
        try:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                cmd_ollama_steward(["status"])
            text = out.getvalue()
        finally:
            job.stop()
        ctx.check(f"running in the hub since ..., got {text!r}", ok and "running in hub" in text and " since " in text)
        ctx.check("the last run's counts", "1 applied" in text and "findings" in text)
        ctx.check("the model", "model: ol:qwen3.5:9b" in text)
        ctx.check("the last note", "The 27B on pc needed a larger window." in text and "local, free" in text)


@test
def test_the_job_starts_only_when_on_and_background_reads_are_on(ctx: Ctx):
    import os
    from halo_harness.ollama_steward.job import start_for
    with Home() as h:
        ctx.check("background reads off (the test default): Studio and the hub start none",
                  start_for(h.state, where="studio") is None)
    with Home(extra={"ollama": {"steward": {"job": False}}}) as h:
        saved = os.environ.pop("BRIDGE_TEST_NO_BACKGROUND_NET", None)
        try:
            ctx.check("ollama.steward.job false: none", start_for(h.state, where="hub") is None)
        finally:
            if saved is not None:
                os.environ["BRIDGE_TEST_NO_BACKGROUND_NET"] = saved


@test
def test_a_note_raises_the_attention_row_and_travels_to_a_member(ctx: Ctx):
    from halo_harness.fleet import attention
    from halo_harness.fleet.steward_attention import latest_attention
    from halo_harness.ollama_steward import notes
    from halo_harness.studio.fleet_answer import SET_ASIDE, open_target
    with Home() as h:
        notes.append(h.state, "note", "all quiet", lines=["all quiet", "nothing changed"])
        ctx.check("a note without an error finding or a change raises nothing", latest_attention(h.state) is None)
        notes.append(h.state, "note", "the 30B on pc spilled 3 GiB to the CPU while ComfyUI held the card",
                     lines=["the 30B on pc spilled 3 GiB to the CPU while ComfyUI held the card", "the window went down"],
                     attention=True)
        rows = attention.build({"harnesses": []}, home=h.state)
        mine = [r for r in rows if r["kind"] == "ollama_steward"]
        ctx.check(f"one steward row with the first line, got {[r['what'] for r in mine]}",
                  len(mine) == 1 and mine[0]["what"].startswith("the 30B on pc spilled"))
        ctx.check("its keys: set aside and open", mine and mine[0]["keys"] == {"a": "set aside", "o": "open Ollama"})
        ctx.check("set aside hides it like the other set-aside kinds", "ollama_steward" in SET_ASIDE)
        ctx.check("open goes to the Ollama panel", mine and open_target(mine[0])["panel"] == "ollama")
        gone = attention.build({"harnesses": []}, home=h.state, acks={mine[0]["id"]})
        ctx.check("an acked row stays hidden", not [r for r in gone if r["kind"] == "ollama_steward"])
        payload = notes.share_payload(h.state, "pc-hub")
        ctx.check(f"the hub's share answer carries the note, got {payload}",
                  payload and payload["hub"] == "pc-hub" and payload["line"].startswith("the 30B") and payload["attention"])
    with Home() as m:
        ctx.check("a member keeps a new hub note", notes.take_hub_note(m.state, payload))
        ctx.check("and not twice", not notes.take_hub_note(m.state, payload))
        ctx.check(f"the member's line, got {notes.member_line(notes.hub_note(m.state))!r}",
                  notes.member_line(notes.hub_note(m.state)).startswith("steward on pc-hub: the 30B on pc spilled"))
        rows = [r for r in attention.build({"harnesses": []}, home=m.state) if r["kind"] == "ollama_steward"]
        ctx.check("the hub's attention note is a row on the member", len(rows) == 1 and "steward on pc-hub" in rows[0]["what"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
