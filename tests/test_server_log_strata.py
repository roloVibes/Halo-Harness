"""tests.test_server_log_strata -- Halo 3.3.9.2 deliverable 3: the steward reads a Strata server's log
(ollama_steward/server_log_strata.py through server_rules_hf / server_context_hf / server_log_hf) and says its three
findings (ollama_steward/rules_strata.py), from fixture logs in Strata's own wording (tests/helpers/st_lines.py: from its
source, unverified against a live run):

1. the lines: each kind (timing from a `done:` line and from the engine's request line, slots, ram-tight, download,
   load-failed, gpu-memory), the load block -> one load-result {strategy, window, experts, load_s};
2. strata-disk-bound: the experts mapped from the model files and the replies at 5 tok/s -> warn, keyed
   `<server>|<model>`, the next set down said (qwen/IQ2_XS, 35.5 GB of experts); a healthy box says nothing; the RAM
   budget warning alone says it;
3. strata-slots: 4 asked, the engine runs 2 -> warn with `--parallel 2`; a request that waited for a slot -> warn;
4. strata-download: the first launch's "Downloading 31.0 of 76.0 GB" -> info with the GB and the share, never a
   timeout; quiet once the server is ready;
5. `halo ollama steward findings` prints them; `halo ollama explain strata-disk-bound` answers from the knowledge.
Fixture logs only: no server runs, nothing is sent.
Run: python -m tests.test_server_log_strata
"""
from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
ensure_default_provider_credentials()

from tests.helpers import st_lines as L  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.st_home import StHome  # noqa: E402

test, TESTS = new_registry()
MODEL = "qwen3.8-flash-next-iq3_xxs"


def _seed(h, lines: list) -> None:
    log = h.root / "st-box.log"
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    h.set_hf(local_servers=[{"name": "st-box", "url": "http://127.0.0.1:9/v1", "runtime": "strata", "log": str(log)}])
    from halo_harness.ollama_steward.server_log_hf import scan
    from halo_harness.ollama_steward.servers_hf import Server
    scan(h.state, Server(name="st-box", url="http://127.0.0.1:9", runtime="strata", log=str(log), model=MODEL),
         from_start=True)


def _found(h) -> dict:
    from halo_harness.ollama_steward.rules import findings
    return {f["rule"]: f for f in findings(h.state, cards={}, catalogs={}, hosts=[]) if f["rule"].startswith("strata-")}


def _load(mode: str = "ram") -> list:
    return [L.starting(), L.experts(mode), L.loaded(31), L.ready(8080)]


@test
def test_each_line_is_its_event(ctx: Ctx):
    from halo_harness.ollama_steward.server_log_strata import StRules, classify
    lines = (L.done(120, 3, 41.5), L.engine_request(4000, 1000, 900.0, 120, 41.5), L.parallel(4, 2), L.waited(41),
             L.ram_tight(), L.download(31.0, 76.0), L.engine_download(40), L.no_engine(),
             "[strata] the GPU reported a fatal error (CUDA error 700); the engine ended", L.starting(), "idle")
    kinds = [(classify(x) or {}).get("kind") for x in lines]
    ctx.check(f"the kinds, got {kinds}", kinds == ["timing", "timing", "slots", "slots", "ram-tight", "download",
                                                   "download", "load-failed", "gpu-memory", None, None])
    d = classify(L.done(120, 3, 41.5, hit=62.0, pcie=3.5))["data"]
    ctx.check(f"the done line's numbers, got {d}", d["tok_s"] == 41.5 and d["hit"] == 0.62 and d["pcie"] == 0.035
              and d["phase"] == "decode" and d["finish"] == "stop")
    d = classify(L.download(31.0, 76.0))["data"]
    ctx.check(f"the download's GB and share, got {d}", d["done_gb"] == 31.0 and d["total_gb"] == 76.0 and d["pct"] == 41)
    r = StRules()
    evs = [e for x in _load("mapped") for e in r.feed(x)]
    load = [e for e in evs if e["kind"] == "load-result"]
    ctx.check(f"one load-result from the load block, got {[e['data'] for e in load]}", len(load) == 1
              and load[0]["data"]["strategy"] == "mapped" and load[0]["data"]["window"] == 32768
              and load[0]["data"]["experts"] == "about 43 GB" and load[0]["data"]["load_s"] == 31)


@test
def test_strata_disk_bound(ctx: Ctx):
    with StHome() as h:
        _seed(h, _load("mapped") + [L.done(120, 24, 5.1, hit=22.0) for _ in range(3)])
        f = _found(h).get("strata-disk-bound")
        ctx.check(f"a warn keyed st-box|{MODEL}, got {f and (f['severity'], f['key'])}", f is not None
                  and f["severity"] == "warn" and f["key"] == f"st-box|{MODEL}" and f["runtime"] == "strata"
                  and f["server"] == "st-box" and f["applied"] is False)
        ctx.check(f"the SSD dominates, the next set down said, got {f and f['finding']!r}", f and
                  "the experts are mapped from the model files, so the expert reads from the SSD dominate" in f["finding"]
                  and "decode at 5.1 tok/s" in f["finding"] and "qwen/IQ2_XS (35.5 GB of experts, IQ3_XXS holds 43)"
                  in f["finding"] and "or more RAM" in f["finding"])
        ctx.check(f"the stated fix, never applied, got {f and f['server_hint']}", f and f["server_hint"]["line"] ==
                  "halo local stop st-box, then halo local serve --runtime strata --model qwen/IQ2_XS"
                  and f["evidence"]["numbers"]["strategy"] == "mapped" and f["evidence"]["numbers"]["hit"] == 0.22)
    with StHome() as h:
        _seed(h, _load("ram") + [L.done(120, 3, 41.5) for _ in range(3)])
        ctx.check("a healthy box says nothing", "strata-disk-bound" not in _found(h))
    with StHome() as h:
        _seed(h, [L.starting(), L.experts("budget"), "[strata] WARNING: the RAM budget for experts is 40 GiB "
                  "(--resident-budget-gib), but this PC has 22 GiB free of 64 GiB: what does not fit goes to swap or is "
                  "read from disk, which can make decoding very slow.", L.ready(8080)])
        f = _found(h).get("strata-disk-bound")
        ctx.check(f"the RAM budget warning alone says it, got {f and f['finding']!r}", f is not None
                  and "under a RAM budget" in f["finding"])


@test
def test_strata_slots(ctx: Ctx):
    with StHome() as h:
        _seed(h, _load() + [L.parallel(4, 2)])
        f = _found(h).get("strata-slots")
        ctx.check(f"4 asked, 2 run: warn, got {f and (f['severity'], f['finding'])}", f is not None
                  and f["severity"] == "warn" and "4 parallel requests asked, the engine runs 2" in f["finding"]
                  and "12 GB runs 1, 20 GB 2, 24 GB 3, 32 GB and more 4" in f["finding"]
                  and "at most 2 of Halo's lanes on this server at once" in f["finding"]
                  and f["server_hint"]["line"].startswith("strata launch ... --parallel 2 on st-box"))
    with StHome() as h:
        _seed(h, _load() + [L.waited(41), L.waited(12)])
        f = _found(h).get("strata-slots")
        ctx.check(f"requests waited for a slot: warn, got {f and f['evidence']['numbers']}", f is not None
                  and f["evidence"]["numbers"]["waits"] == 2 and f["evidence"]["numbers"]["longest_wait_s"] == 41
                  and "2 requests waited for a free slot (up to 41 s)" in f["finding"])


@test
def test_strata_download(ctx: Ctx):
    with StHome() as h:
        _seed(h, ["--- halo starts: strata launch --family qwen --model IQ3_XXS --yes --no-tui", L.download(7.6, 76.0),
                  L.download(31.0, 76.0)])
        f = _found(h).get("strata-download")
        ctx.check(f"downloading: info with the GB and the share, never a timeout, got {f and f['finding']!r}",
                  f is not None and f["severity"] == "info" and "the first launch is downloading the model: 31 of 76 GB "
                  "(41 %) -- Strata's own download, not a timeout" in f["finding"])
    with StHome() as h:
        _seed(h, [L.engine_download(40), L.engine_download(100)] + _load())
        ctx.check("quiet once the server is ready", "strata-download" not in _found(h))


@test
def test_the_cli_prints_them_and_explain_answers(ctx: Ctx):
    with StHome() as h:
        _seed(h, _load("mapped") + [L.parallel(4, 2)] + [L.done(100, 20, 5.0) for _ in range(2)])
        from halo_harness.ollama_steward.cli_steward import cmd_ollama_steward
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cmd_ollama_steward(["findings"])
        text = out.getvalue()
        ctx.check(f"halo ollama steward findings, got {code} {text[:300]!r}", code == 0 and "strata-disk-bound" in text
                  and "strata-slots" in text and f"st-box {MODEL}" in text)
        from halo_harness.ollama_steward.explain import explain
        lines, ok = explain("strata-disk-bound")
        ctx.check(f"explain answers from local-servers.md, got {lines[:2]}", ok and lines[0] == "strata-disk-bound"
                  and any("a smaller set" in x for x in lines))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
