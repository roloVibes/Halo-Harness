"""tests.test_engines_steward -- Halo 3.3.13.0 R1 deliverable 2: the steward reads every engine through its descriptor
(halo_harness/engines/steward.py; ollama_steward/server_rules_hf.classify and server_context_hf.Rules hand an engine's
lines there):

1. each descriptor's sample lines (tests/helpers/engine_lines.SAMPLES, the engines' own wording) -> the event kind and
   the steward's sentence the folded readers produced; a line under its threshold (a cache hit of 82 %, a 4 s warm-up)
   is no event; TensorFold's capacity line is a backend fallback only for an NVFP4 model;
2. the load: Halo's start line names the model, the load is timed from it (or the line's own seconds) and a load over
   three minutes adds slow-load; the steward's kinds per runtime come from the table;
3. the queue: TensorFold's /health `live` block and its /metrics (behind Halo's key) -> engine-waiting;
4. one rule: an engine group's events -> one finding per kind with the descriptor's sentence and fix, `server`,
   `runtime`, `not_asked`, `applied: False`; a loading line is quiet once the server has loaded, unless it crossed a
   threshold; a runtime that is not a descriptor id is untouched.
Run: python -m tests.test_engines_steward
"""
from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers import engine_lines as L  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
T0 = 1_000_000_000.0  # 2001-09-09: far from today, and from 1970 (Windows cannot stamp local times near it)


@test
def test_each_descriptors_lines_become_its_events(ctx: Ctx):
    from halo_harness.ollama_steward.server_rules_hf import classify
    for engine, line, kind, say in L.SAMPLES:
        ev = classify(line, runtime=engine)
        got = (ev["kind"], ev["say"]) if ev else (None, None)
        ctx.check(f"{engine}: {line[-60:]!r} -> {kind}, got {got}", got == (kind, say)
                  and (ev is None or ev["data"]["runtime"] == engine))
    from halo_harness.engines.steward import classify as engine_classify
    cap = L.tf_capacity()
    ev = engine_classify(cap, runtime="tensorfold", model="Qwen3.6-35B-A3B-NVFP4")
    ctx.check(f"an NVFP4 model on sm_89: the fallback, got {ev and ev['say']}", ev and ev["kind"] ==
              "engine-backend-fallback" and ev["severity"] == "warn" and ev["data"]["sm"] == 89)
    ev = engine_classify(L.ft("Decode batch, #running-req: 1, gen throughput (token/s): 21.50"), runtime="freetoken")
    ctx.check(f"a decode line carries the decode speed, got {ev and ev['data']}", ev["data"]["phase"] == "decode"
              and ev["data"]["eval_tok_s"] == 21.5 and ev["at"] is not None)


@test
def test_the_load_is_timed_and_named(ctx: Ctx):
    from halo_harness.ollama_steward.server_context_hf import Rules
    from halo_harness.ollama_steward.server_rules_hf import SAYS
    r = Rules("freetoken")
    r.feed("--- halo starts: ft serve --model /m/Qwen3.6-35B-A3B-NVFP4 --served-model-name Qwen3.6-35B-A3B-NVFP4 "
           "--host 127.0.0.1 --port 1919", at=T0)
    evs = [e for x in L.ft_load(1919, at=T0 + 300) for e in r.feed(x, at=T0 + 300)]
    load = next((e for e in evs if e["kind"] == "load-result"), {})
    ctx.check(f"the load from Halo's start line, named by it, got {load}", load.get("model") == "Qwen3.6-35B-A3B-NVFP4"
              and round(load["data"]["load_s"]) == 300 and any(e["kind"] == "slow-load" for e in evs))
    r = Rules("tensorfold")
    r.feed("--- halo starts: tensorfold-native serve TensorFold/Qwen3.8-27B-MLX-4bit --name Qwen3.8-27B-MLX-4bit", at=5.0)
    evs = r.feed(L.tf_serving("Qwen3.8-27B-MLX-4bit", 8080, 298.4))
    ctx.check(f"the line's own load seconds, got {[e['kind'] for e in evs]}", [e["kind"] for e in evs] ==
              ["load-result", "slow-load"] and evs[0]["data"]["load_s"] == 298.4 and evs[0]["data"]["window"] == 32768)
    ctx.check(f"the kinds per runtime from the table, got {SAYS['tensorfold']}", "engine-waiting" in SAYS["tensorfold"]
              and "slow-load" in SAYS["strata"] and SAYS["llama-server"][0] == "prompt-trimmed")


class _Health(BaseHTTPRequestHandler):
    def log_message(self, *_a):
        pass

    def do_GET(self):  # noqa: N802
        body = json.dumps({"status": "ok", "live": {"connections": 6, "waiting": 2}, "max_batch_size": 4}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@test
def test_the_queue_read(ctx: Ctx):
    from halo_harness.engines.steward import stats
    from halo_harness.ollama_steward.servers_hf import Server
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Health)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{srv.server_address[1]}/v1"
        got = stats(Server(name="mac", url=url, runtime="tensorfold", model="m"))
        ctx.check(f"/health's live block: 2 waiting, got {got}", len(got) == 1 and got[0]["kind"] == "engine-waiting"
                  and got[0]["data"]["waiting"] == 2 and got[0]["data"]["source"] == "/health")
        ctx.check("no stats on a descriptor without them", stats(Server(name="s", url=url, runtime="strata")) == [])
    finally:
        srv.shutdown()
    import os
    from tests.helpers.engine_home import EngineHome
    with EngineHome() as h:
        h.cached("TensorFold/Qwen3.8-27B-MLX-4bit")
        os.environ["FAKE_ENGINE_WAITING"] = "3"
        from halo_harness.engines.launch import serve
        code, _lines, row = serve("tensorfold", "TensorFold/Qwen3.8-27B-MLX-4bit", state_dir=h.state)
        got = stats(Server(name="tensorfold", url=row["base_url"], runtime="tensorfold")) if code == 0 else []
        ctx.check(f"/metrics behind Halo's key: 3 waiting on 4 lanes, got {got}", len(got) == 1
                  and got[0]["data"]["waiting"] == 3 and got[0]["data"]["lanes"] == 4 and got[0]["data"]["source"] == "/metrics")


def _group(runtime: str, lines: list, model: str = "m") -> dict:
    from halo_harness.engines.steward import classify
    evs = []
    for i, x in enumerate(lines):
        ev = classify(x, runtime=runtime, at=1000.0 + i)
        if ev:
            ev["at"] = f"2026-11-08T10:00:{i:02d}+00:00"
            evs.append(ev)
    return {"host": runtime, "server": runtime, "model": model, "key": f"{runtime}|{model}", "runtime": runtime,
            "events": evs, "lines": []}


@test
def test_one_rule_makes_the_findings(ctx: Ctx):
    from halo_harness.engines.steward import findings
    g = _group("strata", ["[strata] starting the engine: reading the model's weights ...", L.st_ready(8080),
                          "[strata] parallel requests: 4 asked, the engine runs 3 (its log says why)",
                          "[strata] parallel: a request has waited 12 s for a free slot",
                          "[strata] mapping the experts from the model files (about 43 GB)"])
    got = {f["rule"]: f for f in findings({"groups": [g]})}
    ctx.check(f"slots, waiting, disk-bound; the start line quiet once loaded, got {sorted(got)}", sorted(got) ==
              ["engine-disk-bound", "engine-slots", "engine-waiting"])
    f = got["engine-disk-bound"]
    ctx.check(f"the descriptor's sentence and fix, tagged, got {f}", f["finding"].startswith("m on strata: the experts are "
              "mapped from the model files") and "a smaller set" in f["finding"] and f["server"] == "strata"
              and f["runtime"] == "strata" and f["applied"] is False and f["verified"] is False and f["severity"] == "warn"
              and "a smaller set" in f["server_hint"]["line"] and isinstance(f["not_asked"], list))
    g = _group("freetoken", L.ft_load(1919, warmup_s=312.48))
    got = {f["rule"]: f for f in findings({"groups": [g]})}
    ctx.check(f"a kernel compile past its threshold is said after the load, got {sorted(got)}", sorted(got) ==
              ["engine-loading"] and "compiled its CUDA kernels" in got["engine-loading"]["finding"])
    plain = _group("llama-server", [L.st_ready(8080)])
    ctx.check("a runtime that is not a descriptor id is untouched", findings({"groups": [plain]}) == [] and not plain["events"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
