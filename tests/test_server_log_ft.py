"""tests.test_server_log_ft -- Halo 3.3.9.1 deliverable 3: the steward reads a FreeToken server's log
(ollama_steward/server_log_ft.py through server_rules_hf / server_context_hf) and says its three findings
(ollama_steward/rules_ft.py), from fixture logs in FreeToken's own wording (tests/helpers/ft_lines.py: from its
source, unverified against a live run):

1. the lines: the ANSI colours stripped, FreeToken's stamp read, each kind (timing prefill / decode, expert-cache,
   pin-cap, load-failed pinned / toolchain, kernel-jit over JIT_S, other-error), Halo's start line naming the model;
   the load block -> one load-result {strategy, experts, cache_slots, num_pages, warmup_s};
2. ft-expert-thrash: the expert cache hits 31 % over the newest decode stats -> warn, keyed `<server>|<model>`, the
   link said, `ft ctl cache --moe 3072` stated; a healthy 85 % says nothing;
3. ft-pinned-cap: WSL locked 22 layers -> warn; the load stopped on the pin budget -> error;
4. ft-kernel-jit: a 312 s startup warmup -> info, nothing to change; the first call after a load running four minutes
   (the traffic ledger) -> info; nvcc against CUDA 13 -> error with the toolkit line;
5. `halo ollama steward findings` prints them; `halo ollama explain ft-expert-thrash` answers from the knowledge.
Fixture logs only: no server runs, nothing is sent.
Run: python -m tests.test_server_log_ft
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

from tests.helpers import ft_lines as L  # noqa: E402
from tests.helpers.ft_home import FtHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
MODEL = "qwen3.6-35b-a3b"
START = (f"--- halo starts: /usr/bin/ft serve --model /models/Qwen3.6-35B-A3B-NVFP4 --served-model-name {MODEL} "
         "--host 127.0.0.1 --port 1919 --moe-collect-stats")


def _seed(h, lines: list) -> None:
    log = h.root / "ft-box.log"
    log.write_text("\n".join([START] + lines) + "\n", encoding="utf-8")
    h.set_hf(local_servers=[{"name": "ft-box", "url": "http://127.0.0.1:9/v1", "runtime": "freetoken", "log": str(log)}])
    from halo_harness.ollama_steward.server_log_hf import scan
    from halo_harness.ollama_steward.servers_hf import by_name
    scan(h.state, by_name("ft-box", h.state), from_start=True)


def _found(h) -> dict:
    from halo_harness.ollama_steward.rules import findings
    return {f["rule"]: f for f in findings(h.state, cards={}, catalogs={}, hosts=[]) if f["rule"].startswith("ft-")}


@test
def test_each_line_is_its_event(ctx: Ctx):
    from halo_harness.ollama_steward.server_log_ft import FtRules, classify, line_time, strip
    at = time.time() - 120
    raw = L.decode(21.5, at=at)
    ctx.check("the colours stripped, the stamp read", "\x1b" not in strip(raw) and abs(line_time(raw) - int(at)) < 1.5)
    kinds = [(classify(x) or {}).get("kind") for x in (L.prefill(), L.decode(), L.moe(0.4), L.pin_lock(), L.pin_stop(),
                                                       L.nvcc_mismatch(), L.warmup(300), L.warmup(4),
                                                       L.stamp("boom", level="ERROR"), L.stamp("idle"))]
    ctx.check(f"the kinds, got {kinds}", kinds == ["timing", "timing", "expert-cache", "pin-cap", "load-failed",
                                                   "load-failed", "kernel-jit", None, "other-error", None])
    ev = classify(L.moe(0.4))
    ctx.check(f"the expert cache's numbers, got {ev['data']}", ev["data"]["hit"] == 0.4 and ev["data"]["layers"] == 40)
    r = FtRules()
    evs = [e for x in [START] + L.load(1919, at=at) for e in r.feed(x, at=at)]
    load = [e for e in evs if e["kind"] == "load-result"]
    ctx.check(f"one load-result from the load block, got {[e['data'] for e in load]}", len(load) == 1
              and load[0]["model"] == MODEL and load[0]["data"]["strategy"] == "offload"
              and load[0]["data"]["experts"] == "nvfp4" and load[0]["data"]["cache_slots"] == 1536
              and load[0]["data"]["num_pages"] == 40000 and load[0]["data"]["warmup_s"] == 4.2)


@test
def test_ft_expert_thrash(ctx: Ctx):
    at = time.time() - 600
    with FtHome() as h:
        _seed(h, L.load(1919, at=at) + [y for i in range(8) for y in (L.decode(6.0, at=at + 10 + i), L.moe(0.31, 5.5, at=at + 10 + i))])
        f = _found(h).get("ft-expert-thrash")
        ctx.check(f"a warn keyed ft-box|{MODEL}, got {f and (f['severity'], f['key'])}", f is not None
                  and f["severity"] == "warn" and f["key"] == f"ft-box|{MODEL}" and f["runtime"] == "freetoken"
                  and f["server"] == "ft-box" and f["applied"] is False)
        ctx.check(f"the link is the limit, said, got {f and f['finding']!r}", f and "hits 31%" in f["finding"]
                  and "the link is the limit" in f["finding"] and "extrapolated" in f["finding"]
                  and "decoding at 6 tok/s" in f["finding"] and "NVLink-class hardware" in f["finding"])
        ctx.check(f"the stated fix, never applied, got {f and f['server_hint']}", f and f["server_hint"]["line"] ==
                  "ft ctl cache --moe 3072 on ft-box" and f["evidence"]["numbers"]["hit"] == 0.31)
    with FtHome() as h:
        _seed(h, L.load(1919, at=at) + [L.moe(0.85, at=at + 20 + i) for i in range(8)])
        ctx.check("a healthy cache says nothing", "ft-expert-thrash" not in _found(h))


@test
def test_ft_pinned_cap(ctx: Ctx):
    at = time.time() - 600
    with FtHome() as h:
        _seed(h, [L.pin_lock(at=at)] + L.load(1919, at=at + 5))
        f = _found(h).get("ft-pinned-cap")
        ctx.check(f"WSL locked layers: warn, got {f and (f['severity'], f['finding'])}", f is not None
                  and f["severity"] == "warn" and "under WSL the pinned bank did not fit (60 GiB of expert banks over a "
                  "25.6 GiB pin budget): 22 layers decode on the CPU, slower -- run it on Linux, or a smaller checkpoint"
                  in f["finding"] and "native Linux" in f["server_hint"]["line"])
    with FtHome() as h:
        _seed(h, [L.stamp("Free memory before loading model: 9.50 GiB", at=at), L.pin_stop()])
        f = _found(h).get("ft-pinned-cap")
        ctx.check(f"the load stopped: error, got {f and (f['severity'], f['evidence']['numbers'])}", f is not None
                  and f["severity"] == "error" and f["evidence"]["numbers"]["stopped"] is True)


@test
def test_ft_kernel_jit(ctx: Ctx):
    at = time.time() - 600
    with FtHome() as h:
        _seed(h, L.load(1919, warmup_s=312.48, at=at))
        f = _found(h).get("ft-kernel-jit")
        ctx.check(f"a 312 s warmup: info, nothing to change, got {f and (f['severity'], f['finding'])}", f is not None
                  and f["severity"] == "info" and "the startup warmup took 312 s" in f["finding"]
                  and "nothing to change" in f["finding"] and f["server_hint"] is None)
    with FtHome() as h:
        _seed(h, L.load(1919, at=at))
        from halo_harness.ollama_steward.ledger import append_lines
        from tests.helpers.steward_seed import line
        append_lines(h.state, [line(host={"name": "ft-box"}, model=MODEL, dialect="openai", total_ms=240000.0, ago=300),
                               line(host={"name": "ft-box"}, model=MODEL, dialect="openai", total_ms=3000.0, ago=200)])
        f = _found(h).get("ft-kernel-jit")
        ctx.check(f"the first call after the load: 240 s, got {f and f['finding']!r}", f is not None
                  and "the first call after the load took 240 s" in f["finding"])
    with FtHome() as h:
        _seed(h, [L.stamp("Free memory before loading model: 9.50 GiB", at=at), L.nvcc_mismatch()])
        f = _found(h).get("ft-kernel-jit")
        ctx.check(f"nvcc against CUDA 13: error, the toolkit line, got {f and (f['severity'], f['server_hint'])}",
                  f is not None and f["severity"] == "error" and "CUDA 13 toolkit with nvcc on PATH" in f["server_hint"]["line"])


@test
def test_the_cli_prints_them_and_explain_answers(ctx: Ctx):
    at = time.time() - 600
    with FtHome() as h:
        _seed(h, L.load(1919, warmup_s=312.48, at=at) + [L.moe(0.2, at=at + 30 + i) for i in range(4)])
        from halo_harness.ollama_steward.cli_steward import cmd_ollama_steward
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cmd_ollama_steward(["findings"])
        text = out.getvalue()
        ctx.check(f"halo ollama steward findings, got {code} {text[:300]!r}", code == 0 and "ft-expert-thrash" in text
                  and "ft-kernel-jit" in text and f"ft-box {MODEL}" in text)
        from halo_harness.ollama_steward.explain import explain
        lines, ok = explain("ft-pinned-cap")
        ctx.check(f"explain answers from local-servers.md, got {lines[:2]}", ok and lines[0] == "ft-pinned-cap"
                  and any("native Linux" in x for x in lines))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
