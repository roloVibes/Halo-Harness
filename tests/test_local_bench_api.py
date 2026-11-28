"""tests.test_local_bench_api -- Halo 3.3.6.0 R5: the Benchmarks routes (studio/local_bench_api.py,
studio/local_bench_job.py, studio/local_tune_api.py) in-process through studio/api.dispatch over the bench's fake host
(tests/helpers/bench_rig.py), no model call, nothing sent but to the fake:

1. GET local/host/<n>/bench?model= answers the cost line and the CLI; POST starts a job whose lines arrive as `bench`
   frames and whose end writes the speed card; GET local/benches lists it per host; a busy card, a second model while
   one runs, no model, an unknown host: 409 / 409 / 422 / 404, each one line;
1b. 3.3.8.1: a host another machine serves and no halo host takes: no 409 -- the confirm carries the link's tail, the
   `via` and the `offer` (`halo host serve` there, `halo host join` here); the job runs over the LAN and its card,
   in GET local/benches too, opens with the label;
2. GET local/host/<n>/tune; POST .../tune/apply {id, scope} lands with that scope (session with no live session says
   so); POST local/changes/apply (the KV dial's Apply); GET local/changes; POST local/changes/scope; POST
   local/changes/revert says what it put back.
Run: python -m tests.test_local_bench_api
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
ensure_default_provider_credentials()

from tests.helpers.bench_rig import BenchRig  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.steward_seed import line  # noqa: E402

test, TESTS = new_registry()


class _Bridge:
    def __init__(self):
        self.frames: list = []

    def publish_local(self, frame: dict) -> None:
        self.frames.append(frame)


def _api(rig, method, path, body=None, query=None, server=None):
    from halo_harness.studio.api import Request, dispatch
    return dispatch(Request(method=method, path=path, query=query or {}, body=body or {}, cwd=rig.home.root,
                            state_dir=rig.state, server=server))


def _wait(job_id: str, timeout: float = 30.0) -> dict:
    from halo_harness.studio.local_bench_job import current
    end = time.time() + timeout
    while time.time() < end:
        j = next((x for x in current()["jobs"] if x["job"] == job_id), None)
        if j and j["done"]:
            return j
        time.sleep(0.05)
    return {}


@test
def test_the_bench_routes(ctx: Ctx):
    from halo_harness.studio import events
    with BenchRig(["bn-small:9b", "bn-coder:30b"]) as rig:
        st, body = _api(rig, "GET", "local/host/fake/bench", query={"model": "bn-small:9b"})
        ctx.check(f"the cost line and the CLI before the run, got {st} {body}", st == 200
                  and body["cost"].startswith("local: ~") and body["cli"] == "halo local bench --host fake --model bn-small:9b")
        bridge = _Bridge()
        server = SimpleNamespace()
        saved = events.bridge_for
        events.bridge_for = lambda _s: bridge
        try:
            st, job = _api(rig, "POST", "local/host/fake/bench", {"model": "bn-small:9b", "quick": True}, server=server)
            ctx.check(f"a job started, got {st} {job.get('job')}", st == 200 and job["job"].startswith("bench-") and not job["joined"])
            st2, other = _api(rig, "POST", "local/host/fake/bench", {"model": "bn-coder:30b"}, server=server)
            done = _wait(job["job"])
        finally:
            events.bridge_for = saved
        ctx.check(f"a second model while one runs: 409 one line, got {st2} {other}", st2 in (409, 200)
                  and (st2 == 200 or other["error"].startswith("a bench of bn-small:9b runs on fake now")))
        if st2 == 200:
            _wait(other["job"])
        ctx.check(f"it ended well with its card, got {done.get('line')!r}", done.get("ok") and done["card"]["quick"]
                  and done["line"].startswith("benched: up to"))
        kinds = {f["event"] for f in bridge.frames}
        ctx.check(f"`bench` frames with its lines, got {kinds} {len(bridge.frames)}", kinds == {"bench"}
                  and any("warming" in (f["data"]["line"] or "") for f in bridge.frames))
        st, b = _api(rig, "GET", "local/benches")
        fake = next(h for h in b["hosts"] if h["name"] == "fake")
        small = next(m for m in fake["models"] if m["model"] == "bn-small:9b")
        ctx.check(f"local/benches lists the card per host, fresh, got {small['card'] and small['card']['stale']!r}",
                  st == 200 and small["card"] and small["card"]["stale"] == "" and small["card"]["lines"][0].startswith("speed card"))
        rig.home.calls(line(host={"name": "fake", "url": rig.mock.base_url}, model="bn-small:9b", ago=5))
        st, busy = _api(rig, "POST", "local/host/fake/bench", {"model": "bn-small:9b"})
        ctx.check(f"a busy card: 409 with one line, got {st} {busy}", st == 409 and "answered a call" in busy["error"])
        ctx.check("no model: 422", _api(rig, "POST", "local/host/fake/bench", {})[0] == 422)
        ctx.check("an unknown host: 404", _api(rig, "POST", "local/host/nope/bench", {"model": "x"})[0] == 404)


@test
def test_a_host_another_machine_serves_is_benched_over_the_lan(ctx: Ctx):
    from tests.helpers.bench_rig import over_the_lan
    label = "measured over the LAN from mac: includes the link (RTT 1.8 ms, wired)"
    with BenchRig(["bn-small:9b"]) as rig, over_the_lan():
        st, ask = _api(rig, "GET", "local/host/fake/bench", query={"model": "bn-small:9b"})
        ctx.check(f"the confirm: the cost line with the link's tail, the via, the offer, got {st} {ask}", st == 200
                  and ask["cost"].endswith("no tokens leave the LAN; " + label) and ask["via"] == "over the LAN from mac"
                  and ask["offer"].startswith("a card without the link: `halo host serve` on 127.0.0.1")
                  and "`halo host join 127.0.0.1` here" in ask["offer"])
        st, job = _api(rig, "POST", "local/host/fake/bench", {"model": "bn-small:9b", "quick": True})
        ctx.check(f"no 409: the job starts with the label, got {st} {job.get('error') or job.get('cost')!r}", st == 200
                  and job["job"].startswith("bench-") and job["cost"].endswith(label) and job["via"] == "over the LAN from mac"
                  and job["offer"] == ask["offer"])
        done = _wait(job["job"])
        ctx.check(f"it ran over the LAN, the card labelled, got {done.get('line')!r}", done.get("ok")
                  and done["card"]["over_lan"] and done["card"]["measured_from"] == "mac" and label in done["lines"])
        st, b = _api(rig, "GET", "local/benches")
        small = next(m for m in next(h for h in b["hosts"] if h["name"] == "fake")["models"] if m["model"] == "bn-small:9b")
        ctx.check(f"the Benchmarks row: the card's first line is the label, got {small['card'] and small['card']['lines'][:1]}",
                  st == 200 and small["card"]["over_lan"] and small["card"]["lines"][0] == label
                  and small["card"]["link"]["rtt_ms"] == 1.8)
    with BenchRig(["bn-small:9b"]) as rig:
        st, ask = _api(rig, "GET", "local/host/fake/bench", query={"model": "bn-small:9b"})
        ctx.check(f"a host this machine serves: no via, no offer, got {sorted(ask)}", st == 200 and "via" not in ask
                  and "offer" not in ask and ask["cost"].endswith("no tokens leave this machine"))


@test
def test_the_tune_and_changes_routes(ctx: Ctx):
    with BenchRig(["bn-coder:30b", "bn-small:9b"], kv="f16") as rig:
        rig.bench("bn-coder:30b")
        st, r = _api(rig, "GET", "local/host/fake/tune")
        ctx.check(f"the report with its cli, got {st} {r.get('says')!r}", st == 200 and r["cli"] == "halo local tune --host fake"
                  and r["options"])
        halo = next(o for o in r["options"] if o["kind"] == "halo")
        st, no = _api(rig, "POST", "local/host/fake/tune/apply", {"id": halo["id"], "scope": "session"})
        ctx.check(f"session with no live session: 409 that says so, got {st} {no.get('error')!r}", st == 409 and "session" in no["error"])
        st, ok = _api(rig, "POST", "local/host/fake/tune/apply", {"id": halo["id"], "scope": "until-restart"})
        ctx.check(f"applied with its scope, got {st} {ok.get('lines')}", st == 200 and ok["lines"][0].endswith("(undone when this halo exits)"))
        st, kv = _api(rig, "POST", "local/changes/apply", {"key": "fake|bn-small:9b", "field": "num_ctx", "to": 16384,
                                                          "why": "the KV dial"})
        ctx.check(f"the KV dial's Apply: one change of yours, keep, got {st} {kv}", st == 200 and kv["line"].endswith("(kept)"))
        st, bad = _api(rig, "POST", "local/changes/apply", {"key": "fake|bn-small:9b", "field": "colour", "to": 1})
        ctx.check(f"not a profile field: 422, got {st}", st == 422 and "not a profile change" in bad["error"])
        st, ch = _api(rig, "GET", "local/changes")
        ctx.check(f"the changes, newest first, with lines, got {[c['line'][:40] for c in ch['changes']]}", st == 200
                  and len(ch["changes"]) == 2 and ch["changes"][0]["field"] == "num_ctx" and ch["scopes"][0]["id"] == "session")
        cid = ch["changes"][0]["id"]
        st, sc = _api(rig, "POST", "local/changes/scope", {"id": cid, "scope": "until-restart"})
        ctx.check(f"a new scope, got {st} {sc}", st == 200 and sc["line"].endswith("undone when this halo exits"))
        st, rv = _api(rig, "POST", "local/changes/revert", {"id": cid})
        ctx.check(f"revert says what it put back, got {st} {rv}", st == 200
                  and rv["lines"] == ["took num_ctx on fake|bn-small:9b away: it had none before (reverted from Studio)"])
        st, rv = _api(rig, "POST", "local/changes/revert", {"id": "all"})
        ctx.check(f"revert all, got {rv['lines']}", st == 200 and len(rv["lines"]) == 1 and _api(rig, "GET", "local/changes")[1]["changes"] == [])
        ctx.check("revert with no id: 422", _api(rig, "POST", "local/changes/revert", {})[0] == 422)


@test
def test_the_sweep_routes_offer_stop_and_use_in_halo(ctx: Ctx):
    """3.6.0.25 T rulings 5 and 7: the offer says what it does before a start; the job runs with a Stop; the table and
    the pick; "Use in Halo" lands the pick as the profile's window through Changes (revertable), nothing else."""
    import os
    saved = os.environ.get("BRIDGE_TEST_NO_BACKGROUND_NET")
    os.environ["BRIDGE_TEST_NO_BACKGROUND_NET"] = "1"  # the card's memory: unknown here, never this PC's card
    try:
        with BenchRig(["sw-short:8b", "sw-up:8b"]) as rig:
            st, got = _api(rig, "GET", "local/host/fake/sweep", query={"model": "sw-short:8b"})
            ctx.check(f"before a start: no sweep, the offer, the cli, got {st} {got}", st == 200 and got["sweep"] is None
                      and "at most 6 loads of sw-short:8b" in got["offer"] and "unloads what is loaded and puts it back"
                      in got["offer"] and "nothing to the Ollama store" in got["offer"]
                      and got["cli"] == "halo local bench --host fake --sweep sw-short:8b" and got["use"] is None)
            st, job = _api(rig, "POST", "local/host/fake/sweep", body={"model": "sw-short:8b"})
            done = _wait(job.get("job", ""))
            ctx.check(f"the job ends with the pick's line, got {st} {done.get('line')!r}", st == 200 and done.get("ok")
                      and done.get("kind") == "sweep" and str(done.get("line")).startswith("the pick: 40,960"))
            st, got = _api(rig, "GET", "local/host/fake/sweep", query={"model": "sw-short:8b"})
            sw = got["sweep"] or {}
            ctx.check(f"the table and the pick, free unknown said, got {sw}", sw.get("pick") == 40960
                      and sw["why"] == "40,960: the model's own limit" and all("free unknown" in r["line"] for r in sw["windows"])
                      and sw.get("safe") is None and sw.get("safe_line") == ""  # free unknown: no safe window
                      and got["use"].startswith("sets the profile's window of sw-short:8b on fake to 40,960"))
            st, used = _api(rig, "POST", "local/host/fake/sweep/use", body={"model": "sw-short:8b"})
            from halo_harness.ollama_steward import changes as C
            rows = [r for r in C.read(rig.state) if not r.get("reverted_at")]
            ctx.check(f"Use in Halo: one change in Changes, revertable, got {st} {used} {rows}", st == 200 and used["ok"]
                      and any(r.get("field") == "num_ctx" and r.get("after") == 40960 for r in rows))
            st, job = _api(rig, "POST", "local/host/fake/sweep", body={"model": "sw-up:8b"})
            st2, stopped = _api(rig, "POST", "local/host/fake/sweep/stop", body={"model": "sw-up:8b"})
            done = _wait(job.get("job", ""))
            from halo_harness.providers import local_sweep as S
            kept = S.load(rig.state, rig.host.url, "sw-up:8b") or {"windows": []}
            ctx.check(f"Stop: it ends after the running load, what landed kept, got {stopped} {done.get('line')!r} "
                      f"{[r['window'] for r in kept['windows']]}", st2 == 200 and stopped["ok"] and done.get("ok")
                      and "stopped" in str(done.get("line")) and len(kept["windows"]) <= 1)
    finally:
        if saved is None:
            os.environ.pop("BRIDGE_TEST_NO_BACKGROUND_NET", None)
        else:
            os.environ["BRIDGE_TEST_NO_BACKGROUND_NET"] = saved


@test
def test_the_tuner_routes_off_by_default_then_a_job_with_its_texts(ctx: Ctx):
    """3.6.0.25 T rulings 8-10 through the routes: no tuner set -> the one closed line, POST refused, nothing sent; set
    -> the offer (which model, what is sent, the cost, what it writes), a job with its cost when done, the texts with
    who wrote them, Remove. The tuner is a scripted stand-in for agent.live_call: no request leaves this machine."""
    import json
    from halo_harness.ollama_steward import agent as A
    from halo_harness.theme import set_config_value
    with BenchRig(["sw-up:8b"]) as rig:
        st, got = _api(rig, "GET", "local/host/fake/sweep", query={"model": "sw-up:8b"})
        ctx.check(f"no tuner: one closed line, got {got.get('tuner')}", st == 200 and got["tuner"]["tuner"] is None
                  and "pick one in Settings (Tuner model)" in got["tuner"]["line"] and got["notes"] == {})
        st, refused = _api(rig, "POST", "local/host/fake/sweep/tuner", body={"model": "sw-up:8b"})
        ctx.check(f"no tuner: a start is refused, nothing sent, got {st} {refused}", st == 409
                  and "nothing was sent" in refused["error"])
        set_config_value("ollama.tuner.model", "ant:tuner-test")
        seen: list = []
        saved = A.live_call

        def fake(model, system, user, *, state_dir=None, timeout_s=120.0):
            seen.append(user)
            r = {"tool": "write", "args": {"kind": "guide", "best_at": ["quick edits"], "text": "small and fast"}}                 if len(seen) == 1 else {"done": "ok"}
            return {"text": json.dumps(r), "input_tokens": 800, "output_tokens": 40, "cost_usd": 0.002, "local": False}
        A.live_call = fake
        try:
            st, got = _api(rig, "GET", "local/host/fake/sweep", query={"model": "sw-up:8b"})
            t = got["tuner"]
            ctx.check(f"the offer before a start, got {t}", t["tuner"] == "ant:tuner-test" and "no user name" in t["sends"]
                      and "(at most 8 rounds)" in t["cost"] and t["writes"].startswith("nothing to the Ollama store"))
            st, job = _api(rig, "POST", "local/host/fake/sweep/tuner", body={"model": "sw-up:8b"})
            done = _wait(job.get("job", ""))
        finally:
            A.live_call = saved
        ctx.check(f"the job ends with its cost and counts, got {done.get('line')!r}", st == 200 and done.get("ok")
                  and "cost $0.0040" in str(done.get("line")) and "wrote: guide" in str(done.get("line")) and len(seen) == 2)
        st, got = _api(rig, "GET", "local/host/fake/sweep", query={"model": "sw-up:8b"})
        g = (got["notes"] or {}).get("guide") or {}
        ctx.check(f"the text, written by the tuner, got {g}", g.get("by") == "ant:tuner-test"
                  and g.get("by_line", "").startswith("written by ant:tuner-test, ") and g.get("best_at") == ["quick edits"])
        st, gone = _api(rig, "POST", "local/host/fake/sweep/notes/remove", body={"model": "sw-up:8b", "kind": "guide"})
        st, got = _api(rig, "GET", "local/host/fake/sweep", query={"model": "sw-up:8b"})
        ctx.check(f"Remove, got {gone}", gone["ok"] and got["notes"] == {})
        rig.home.calls(line(host={"name": "fake", "url": rig.mock.base_url}, model="other:1b", ago=5))
        st, busy = _api(rig, "POST", "local/host/fake/sweep/tuner", body={"model": "sw-up:8b"})
        ctx.check(f"after the check: a busy card refuses a tuner start, got {st} {busy}", st == 409
                  and "answered a call" in busy["error"])


@test
def test_the_sweep_table_cells_in_node(ctx: Ctx):
    """3.6.0.25 T ruling 7 (routes/local/sweepRows.ts): a row's cells -- window, on the card, free, prompt and reply speed,
    the pick's mark; "unknown" where the host did not tell, "not measured" for a window that did not load."""
    import json
    from tests.helpers import node_ts
    src = (Path(__file__).resolve().parent.parent / "halo_harness/studio/ui/src/routes/local/sweepRows.ts").resolve().as_uri()
    rows = [{"window": 65536, "state": "on the card", "free_mib": 1200, "prompt_tok_s": 2400.5, "tok_s": 90, "line": ""},
            {"window": 81920, "state": "on the card, but slow", "free_mib": None, "prompt_tok_s": 800, "tok_s": 28,
             "slow": True, "timed": 2, "line": ""},
            {"window": 98304, "state": "did not load", "free_mib": None, "prompt_tok_s": None, "tok_s": None,
             "error": "x", "line": ""}]
    got = node_ts.run(f"const M = await import({json.dumps(src)});\nconst D = {json.dumps(rows)};\n"
                      "console.log(JSON.stringify(D.map((r) => M.cells(r, 65536))));")
    ctx.check(f"the cells, got {got}", got == [
        ["65,536", "on the card", "1,200 MiB", "2,400.5 tok/s", "90 tok/s", "the pick"],
        ["81,920", "on the card, but slow", "unknown", "800 tok/s", "28 tok/s (timed twice)", "past the cliff"],
        ["98,304", "did not load", "not measured", "not measured", "not measured", ""]])


@test
def test_the_start_button_says_what_it_does_by_state(ctx: Ctx):
    """After the check (routes/local/sweepRows.ts startButton): "go on" only while the sweep is not done and loads are
    left; a done sweep, or one whose loads were used, offers "Sweep again" (again: true) whose title says it starts
    over; no sweep: "Find the best window"."""
    import json
    from tests.helpers import node_ts
    src = (Path(__file__).resolve().parent.parent / "halo_harness/studio/ui/src/routes/local/sweepRows.ts").resolve().as_uri()
    sws = [None, {"windows": [{}], "done": False, "loads": 2, "loads_cap": 6},
           {"windows": [{}], "done": True, "loads": 3, "loads_cap": 6},
           {"windows": [{}] * 6, "done": False, "loads": 6, "loads_cap": 6}]
    got = node_ts.run(f"const M = await import({json.dumps(src)});\nconst D = {json.dumps(sws)};\n"
                      "console.log(JSON.stringify(D.map((s) => M.startButton(s))));")
    labels = [(g or {}).get("label") for g in got or []]
    agains = [(g or {}).get("again") for g in got or []]
    ctx.check(f"the labels by state, got {got}", labels == ["Find the best window", "Find the best window (go on)",
                                                             "Sweep again", "Sweep again"]
              and agains == [False, False, True, True] and "starts over" in got[2]["title"])
    from halo_harness.providers import local_sweep as S
    from halo_harness.studio.local_sweep_api import _view
    v = _view({"windows": [{"window": 8192, "state": "on the card"}], "pick": 8192, "why": "x", "done": True})
    ctx.check(f"the view says the loads' cap, got {v}", v["loads_cap"] == S.MAX_LOADS)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
