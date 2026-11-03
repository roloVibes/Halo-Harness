"""tests.test_server_log_tensorfold -- Halo 3.3.9.3 deliverable 3: the steward reads a TensorFold server's log
(ollama_steward/server_log_tensorfold.py through server_rules_hf / server_context_hf / server_log_hf) and its queue from
`/health` and `/metrics` (server_stats_tensorfold.py), and says its three findings (rules_tensorfold.py), from fixture
logs in TensorFold's own wording (tests/helpers/tf_lines.py: from its source, unverified against a live run):

1. the lines: the CUDA and Metal capacity lines, the done line (its queued seconds), the live line, the ended line, the
   thinking cut, a fatal startup line, the UTC stamp; the start + capacity + serving lines -> one load-result;
2. the queue: a keyless server's `/health` live.waiting, Halo's keyed server's `/metrics` with the key (refused
   without), nothing when nothing waits;
3. tf-waiting from the queue and from the done lines' queued seconds, with `--parallel` said; a quiet server says nothing;
4. tf-backend-fallback: NVFP4 on sm_89 -> warn; on sm_120, or an MLX checkpoint on sm_89 -> nothing;
5. tf-load: a load still going a minute after Halo started it, and a 298 s load -> info, never a timeout;
6. `halo ollama steward findings` prints them; `halo ollama explain tf-waiting` answers from the knowledge.
Fixture logs and the fake server on 127.0.0.1 only; no model.
Run: python -m tests.test_server_log_tensorfold
"""
from __future__ import annotations

import contextlib
import io
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
ensure_default_provider_credentials()

from tests.helpers import tf_lines as L  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.tf_home import FAKE_TF, TfHome  # noqa: E402

test, TESTS = new_registry()
MODEL = "Qwen3.8-27B-MLX-4bit"
NVFP4 = "NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4"


def _seed(h, lines: list, model: str = MODEL, at=None) -> None:
    log = h.root / f"tf-box-{len(lines)}-{model[:6]}.log"
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    h.set_hf(local_servers=[{"name": "tf-box", "url": "http://127.0.0.1:9/v1", "runtime": "tensorfold", "log": str(log)}])
    from halo_harness.ollama_steward.server_log_hf import scan
    from halo_harness.ollama_steward.servers_hf import Server
    scan(h.state, Server(name="tf-box", url="http://127.0.0.1:9", runtime="tensorfold", log=str(log), model=model),
         from_start=True, at=at)


def _found(h) -> dict:
    from halo_harness.ollama_steward.rules import findings
    return {f["rule"]: f for f in findings(h.state, cards={}, catalogs={}, hosts=[]) if f["rule"].startswith("tf-")}


def _start(model: str) -> str:
    return f"--- halo starts: tensorfold serve x --name {model} --host 127.0.0.1 --port 8080 --context 32768"


@test
def test_each_line_is_its_event(ctx: Ctx):
    from halo_harness.ollama_steward.server_log_tensorfold import TfRules, classify, line_time
    lines = (L.cuda_capacity(), L.metal_capacity(), L.done(queued=2.5), L.live(6, 2), L.ended(), L.key_file_refused(),
             "[tensorfold] warning: a reply reached max_tokens while still thinking, so its content is empty", L.profile())
    kinds = [(classify(x) or {}).get("kind") for x in lines]
    ctx.check(f"the kinds, got {kinds}", kinds == ["capacity", "capacity", "timing", "queue", "gpu-memory",
                                                   "load-failed", "reply-cut", None])
    c = classify(L.cuda_capacity(sm=89, device="NVIDIA GB10, memory shared with the host", streams=4, window=40960))["data"]
    ctx.check(f"the CUDA capacity line, got {c}", c["backend"] == "cuda" and c["sm"] == 89 and c["streams"] == 4
              and c["window"] == 40960 and c["device"] == "NVIDIA GB10" and c["model_gib"] == 16.02)
    m = classify(L.metal_capacity(streams=8))["data"]
    ctx.check(f"the Metal capacity line, got {m}", m["backend"] == "metal" and m["sm"] is None and m["streams"] == 8
              and m["device"] == "Apple M3 Max")
    d = classify(L.stamp(L.done(prompt=900, tokens=64, tok_s=32.0, queued=2.5)))
    ctx.check(f"the done line and its stamp, got {d['data']} {d['at']}", d["data"]["tok_s"] == 32.0 and
              d["data"]["queued_s"] == 2.5 and d["data"]["prompt_tokens"] == 900 and d["data"]["tokens"] == 64
              and abs(d["at"] - line_time(L.stamp("x"))) < 1e-6 and line_time("no stamp") is None)
    r = TfRules()
    evs = [e for x in [_start(MODEL)] + L.load(MODEL, 8080, loaded_s=4.2) for e in r.feed(L.stamp(x) if x[0] == "[" else x)]
    kinds = [e["kind"] for e in evs]
    load = [e for e in evs if e["kind"] == "load-result"]
    ctx.check(f"start, capacity, one load-result, got {kinds}", kinds == ["load-start", "capacity", "load-result"]
              and load[0]["model"] == MODEL and load[0]["data"]["streams"] == 4 and load[0]["data"]["backend"] == "cuda"
              and load[0]["data"]["window"] == 32768 and load[0]["data"]["load_s"] == 4.2)


@test
def test_the_queue_from_health_and_metrics(ctx: Ctx):
    from halo_harness.ollama_steward.server_stats_tensorfold import parse_metrics, read
    from halo_harness.ollama_steward.servers_hf import Server
    from halo_harness.providers.local_runtime import find_free_port
    ctx.check("the scrape's samples", parse_metrics('# HELP x\ntensorfold:requests_waiting 3\nvllm:x{a="b"} 2\n') ==
              {"tensorfold:requests_waiting": 3.0, "vllm:x": 2.0})
    with TfHome() as h:
        kf = h.root / "keys"
        kf.write_text("halo: fixture-key-1\n", encoding="utf-8")
        for keyed in (False, True):
            port = find_free_port()
            env = {**os.environ, "FAKE_TF_WAITING": "3", "FAKE_TF_LOAD_S": "0"}
            argv = [sys.executable, str(FAKE_TF), "serve", "x/y", "--name", MODEL, "--port", str(port), "--parallel", "2"]
            proc = subprocess.Popen(argv + (["--api-key-file", str(kf)] if keyed else []), env=env, stdin=subprocess.DEVNULL,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                s = Server(name="tf-box", url=f"http://127.0.0.1:{port}", runtime="tensorfold", model=MODEL)
                end, got = time.monotonic() + 15, []
                while time.monotonic() < end and not got:
                    got = read(s, key="fixture-key-1" if keyed else None)
                    time.sleep(0.1) if not got else None
                d = got[0]["data"] if got else {}
                want = "/metrics" if keyed else "/health"
                ctx.check(f"{want}: 3 waiting on 2 streams, got {d}", got and got[0]["kind"] == "queue" and d["waiting"]
                          == 3 and d["lanes"] == 2 and d["source"] == want and "fixture-key-1" not in got[0]["evidence"])
                if keyed:
                    ctx.check("without the key /metrics says nothing", read(s, key="") == [])
            finally:
                proc.kill()
                proc.wait(timeout=10)


@test
def test_tf_waiting(ctx: Ctx):
    with TfHome() as h:
        _seed(h, [_start(MODEL)] + L.load(MODEL, 8080, streams=2) + [L.done(queued=2.5), L.done(queued=4.0),
                                                                    L.done(queued=0.0)])
        f = _found(h).get("tf-waiting")
        ctx.check(f"tf-waiting from the done lines, got {f and f['finding']}", f and f["severity"] == "warn"
                  and f["key"] == f"tf-box|{MODEL}" and f["server"] == "tf-box" and "past the 2 streams" in f["finding"]
                  and "--parallel 4" in f["server_hint"]["line"] and f["applied"] is False)
    with TfHome() as h:
        _seed(h, [_start(MODEL)] + L.load(MODEL, 8080) + [L.done(), L.done(), L.done()])
        ctx.check("a quiet server says nothing", "tf-waiting" not in _found(h))


@test
def test_tf_backend_fallback(ctx: Ctx):
    with TfHome() as h:
        _seed(h, [_start(NVFP4)] + L.load(NVFP4, 8080, sm=89), model=NVFP4)
        f = _found(h).get("tf-backend-fallback")
        ctx.check(f"NVFP4 on sm_89: warn, got {f and f['finding']}", f and f["severity"] == "warn" and "sm_89" in f["finding"]
                  and "fallback path" in f["finding"] and f["evidence"]["numbers"]["sm"] == 89)
    for model, sm in ((NVFP4, 120), (MODEL, 89)):
        with TfHome() as h:
            _seed(h, [_start(model)] + L.load(model, 8080, sm=sm), model=model)
            ctx.check(f"{model} on sm_{sm}: nothing", "tf-backend-fallback" not in _found(h))


@test
def test_tf_load_and_the_cli(ctx: Ctx):
    with TfHome() as h:
        _seed(h, [_start(MODEL)], at=time.time() - 120)
        f = _found(h).get("tf-load")
        ctx.check(f"a load still going: info, never a timeout, got {f and f['finding']}", f and f["severity"] == "info"
                  and "has been loading for" in f["finding"] and "not a timeout" in f["finding"])
    with TfHome() as h:
        _seed(h, [_start(MODEL)] + L.load(MODEL, 8080, loaded_s=298.4) + [L.done(queued=3.0), L.done(queued=3.0)])
        f = _found(h).get("tf-load")
        ctx.check(f"a 298 s load: info, got {f and f['finding']}", f and "the load took 298 s for 16.02 GiB" in f["finding"])
        from halo_harness.ollama_steward.cli_steward import cmd_ollama_steward
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cmd_ollama_steward(["findings"])
        ctx.check(f"halo ollama steward findings prints them, got {out.getvalue()[:300]!r}", "tf-waiting" in out.getvalue()
                  and "tf-load" in out.getvalue())
        from halo_harness.ollama_steward.explain import cmd_ollama_explain
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = cmd_ollama_explain(["tf-waiting"])
        ctx.check(f"halo ollama explain tf-waiting, got {rc} {out.getvalue()[:200]!r}", rc == 0 and "streams" in out.getvalue())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
