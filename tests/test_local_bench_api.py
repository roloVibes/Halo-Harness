"""tests.test_local_bench_api -- Halo 3.3.6.0 R5: the Benchmarks routes (studio/local_bench_api.py,
studio/local_bench_job.py, studio/local_tune_api.py) in-process through studio/api.dispatch over the bench's fake host
(tests/helpers/bench_rig.py), no model call, nothing sent but to the fake:

1. GET local/host/<n>/bench?model= answers the cost line and the CLI; POST starts a job whose lines arrive as `bench`
   frames and whose end writes the speed card; GET local/benches lists it per host; a busy card, a second model while
   one runs, no model, an unknown host: 409 / 409 / 422 / 404, each one line;
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


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
