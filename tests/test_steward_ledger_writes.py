"""tests.test_steward_ledger_writes -- Halo 3.3.4.0 R2: the ledger written
in-process (halo_harness/ollama_steward/ledger.py, ledger_call.py; the
real-Session half is tests/test_steward_ledger.py).

1. a timeout and a connect failure are their own status, the second is retry
   1 of the turn; a call to Ollama's cloud gets its stream back untouched;
2. rotation at the size limit, `read_calls` filters and `--since` spans, a
   calibration load's line;
3. `ollama.ledger: false` -> no file and the stream untouched.
A fresh home per test, never the real ~/.halo, never a server.
Run: python -m tests.test_steward_ledger_writes
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


class _Env:
    """A fresh home for the in-process tests (every touched variable restored)."""

    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "OLLAMA_HOST")}
        root = Path(tempfile.mkdtemp(prefix="l2_ledger-"))
        os.environ["BRIDGE_TEST_HOME"] = str(root)
        os.environ["BRIDGE_STATE_DIR"] = str(root / ".halo")
        os.environ["OLLAMA_HOST"] = "http://127.0.0.1:1"
        self.state = root / ".halo"
        self.state.mkdir(parents=True)
        return self

    def config(self, cfg: dict) -> None:
        (self.state / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    def __exit__(self, *exc):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class _Obj:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def _req(state, url="http://127.0.0.1:1", dialect="ollama", provider="ollama", model="m1"):
    from halo_harness.providers.routing import Route
    body = {"model": model, "messages": [{"role": "user", "content": "x" * 70}], "options": {"num_ctx": 8192}}
    return _Obj(route=Route(provider, model, dialect), creds=_Obj(base_url=url), prebuilt_ollama_body=body,
                prebuilt_oai_body=None, body=body, state_dir=state)


def _session(state):
    return _Obj(state_dir=state, turn_count=3, log=_Obj(session_id="s-l2"), model_ref=None, settings=None)


def _raising(exc):
    yield {"type": "message_start"}
    raise exc


@test
def test_a_timeout_and_a_connect_failure_are_their_own_status(ctx: Ctx):
    from halo_harness.ollama_steward.ledger import read_calls
    from halo_harness.ollama_steward.ledger_call import observe_call
    from halo_harness.providers.stream import UpstreamError
    with _Env() as env:
        sess = _session(env.state)
        for exc in (UpstreamError(504, "api_error", "upstream read timed out after 300s", True),
                    UpstreamError(502, "api_error", "cannot resolve/reach 127.0.0.1:1 -- connection refused", False)):
            try:
                list(observe_call(sess, _req(env.state), _raising(exc)))
            except UpstreamError:
                pass
        rows = read_calls(env.state)
        ctx.check(f"a timeout, then a connection failure, got {[r.get('status') for r in rows]}",
                  [r.get("status") for r in rows] == ["timeout", "connection"])
        ctx.check("each with the one line and the wall time", all(r.get("error") and isinstance(r.get("total_ms"), float)
                                                                   for r in rows))
        ctx.check(f"the second is retry 1 of turn 3, got {[r.get('retry') for r in rows]}",
                  [r.get("retry") for r in rows] == [0, 1] and rows[0].get("turn") == 3)
        cloud = _req(env.state, url="https://ollama.com")
        gen = iter([{"type": "message_stop"}])
        ctx.check("a call to Ollama's cloud gets its stream back untouched",
                  observe_call(sess, cloud, gen) is gen)


@test
def test_rotation_filters_and_a_calibration_line(ctx: Ctx):
    from halo_harness.ollama_steward import ledger
    from halo_harness.providers.ollama import JsonReply
    with _Env() as env:
        row = {"host": {"name": "pc", "url": "http://192.0.2.10:11434"}, "status": 200}
        ledger.record_call(env.state, {**row, "model": "b"})
        size = ledger.traffic_path(env.state).stat().st_size
        saved = ledger.ROTATE_BYTES
        ledger.ROTATE_BYTES = size * 10
        try:
            for i in range(1, 15):
                ledger.record_call(env.state, {**row, "model": "a" if i % 2 else "b"})
        finally:
            ledger.ROTATE_BYTES = saved
        d = env.state / "ollama"
        ctx.check("the file rotated into traffic.1.jsonl", (d / "traffic.1.jsonl").exists()
                  and (d / "traffic.jsonl").stat().st_size < size * 10)
        rows = ledger.read_calls(env.state)
        ctx.check(f"read_calls reads the rotated file too, got {len(rows)}", len(rows) == 15)
        ctx.check("filters by model and host", all(r["model"] == "a" for r in ledger.read_calls(env.state, model="a"))
                  and not ledger.read_calls(env.state, host="mac") and ledger.read_calls(env.state, host="pc"))
        ctx.check("--since: a span", ledger.parse_since("24h") == 86400 and ledger.parse_since("7d") == 7 * 86400
                  and len(ledger.read_calls(env.state, since="1h")) == len(rows))
        host = _Obj(name="pc", url="http://192.0.2.10:11434")
        ledger.record_probe(host, "m1", num_ctx=32768, reply=JsonReply(failure="timeout"), elapsed_s=20.0, state_dir=env.state)
        cal = ledger.read_calls(env.state, kind="calibrate")
        ctx.check(f"a calibration load that ran out is a calibrate line with status timeout, got {cal}",
                  len(cal) == 1 and cal[0]["status"] == "timeout" and cal[0]["num_ctx_sent"] == 32768
                  and cal[0]["total_ms"] == 20000.0)


@test
def test_ollama_ledger_false_writes_no_file(ctx: Ctx):
    from halo_harness.ollama_steward import ledger
    from halo_harness.ollama_steward.ledger_call import observe_call
    with _Env() as env:
        env.config({"ollama": {"ledger": False}})
        ctx.check("record_call answers None", ledger.record_call(env.state, {"model": "m"}) is None)
        gen = iter([])
        ctx.check("the observer hands the stream back untouched", observe_call(_session(env.state),
                                                                                 _req(env.state), gen) is gen)
        ctx.check("and no traffic file exists", not (env.state / "ollama" / "traffic.jsonl").exists())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
