"""tests.test_fit_evidence -- Halo 3.3.6.0 R3 deliverable 6, "the fit badge cites the log" (providers/
fit_evidence.py), on fixture events (the server log's `load-result`, the steward's `/api/ps` reading) and ledger lines:

1. verified -- 41/41 layers, splits = 2, 258 tok/s; spilled -- 59/66 layers, 16 tok/s; unverified (no load seen);
   /api/ps alone: size_vram == size verified, under it spilled; the newer of the log and /api/ps wins;
2. the measured tok/s is the median of the newest answered calls that are not warming;
3. the card carries it (`fit_evidence`, the blocks' `fit` line, `halo models show`'s "fit:" line), the Models rows
   and the Library row of an installed model (studio/models_library_api.mark_installed);
4. ollama_twin_verify's line is the same line_of.
Run: python -m tests.test_fit_evidence
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.logs_rig import LogsHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
BOX = {"name": "box", "url": "http://127.0.0.1:9"}
GIB = 2 ** 30


def _load(model, layers, splits, at, cpu=None):
    return {"kind": "load-result", "severity": "info", "say": f"{model} loaded", "evidence": "llama-server started", "at": at,
            "model": model, "data": {"layers": layers, "splits": splits, "kv_gpu_mib": 1632.0, "kv_cpu_mib": cpu,
                                     "window": 32768}}


def _ps(model, size, vram, at):
    return {"kind": "loaded", "severity": "info", "say": f"{model} loaded", "evidence": "/api/ps", "at": at, "model": model,
            "data": {"size": size, "size_vram": vram, "context_length": 32768}}


def _speed(h, model, *toks, warming=False):
    for t in toks:
        h.call(BOX, model, time.time() - 60, eval_tok_s=t, warming=warming)


def _fresh():
    from halo_harness.providers import fit_evidence
    fit_evidence._CACHE.clear()


@test
def test_verified_spilled_unverified(ctx: Ctx):
    from halo_harness.providers.fit_evidence import evidence
    now = time.time()
    with LogsHome(hosts=[BOX]) as h:
        h.events(_load("coder:30b", [41, 41], 2, now - 300), _load("big:27b", [59, 66], 14, now - 300, cpu=272.0),
                 _ps("ps-full:8b", 8 * GIB, 8 * GIB, now - 200), _ps("ps-spill:8b", 10 * GIB, 8 * GIB, now - 200),
                 _load("newer:9b", [33, 33], 2, now - 500), _ps("newer:9b", 10 * GIB, 7 * GIB, now - 100))
        _speed(h, "coder:30b", 250.0, 258.0, 262.0, 900.0, warming=False)
        _speed(h, "coder:30b", 5.0, warming=True)
        _speed(h, "big:27b", 16.0)
        _fresh()
        got = {m: evidence(h.state, "box", m) for m in ("coder:30b", "big:27b", "ps-full:8b", "ps-spill:8b", "never:1b", "newer:9b")}
    ctx.check(f"verified with the log's numbers, got {got['coder:30b']['line']!r}",
              got["coder:30b"]["line"] == "verified -- 41/41 layers, splits = 2, 260 tok/s" and got["coder:30b"]["source"] == "the log")
    ctx.check(f"spilled, got {got['big:27b']['line']!r}", got["big:27b"]["line"] == "spilled -- 59/66 layers, 16 tok/s")
    ctx.check(f"/api/ps alone: every byte on the GPU, got {got['ps-full:8b']['line']!r}", got["ps-full:8b"]["state"] == "verified"
              and got["ps-full:8b"]["source"] == "/api/ps")
    ctx.check(f"/api/ps alone: under its size spilled, got {got['ps-spill:8b']['line']!r}",
              got["ps-spill:8b"]["line"] == "spilled -- 80% on the GPU")
    ctx.check(f"no load seen: unverified, got {got['never:1b']['line']!r}", got["never:1b"]["state"] == "unverified"
              and got["never:1b"]["line"].startswith("unverified"))
    ctx.check(f"the newer reading wins (/api/ps after the log), got {got['newer:9b']['line']!r}",
              got["newer:9b"]["state"] == "spilled" and got["newer:9b"]["source"] == "/api/ps")


@test
def test_the_card_the_rows_and_the_library(ctx: Ctx):
    from halo_harness.providers.model_card_blocks import block_lines
    from halo_harness.providers.model_card_quirks import with_quirks
    from halo_harness.studio import models_library_api as A
    now = time.time()
    with LogsHome(hosts=[BOX]) as h:
        h.events(_load("coder:30b", [41, 41], 2, now - 300))
        _speed(h, "coder:30b", 258.0)
        _fresh()
        card = with_quirks({"kind": "ollama", "name": "coder:30b", "host": "box", "how": [], "blocks": {"use_for": []}}, h.state)
        lines = block_lines(card["blocks"])
        from halo_harness.studio import ollama_hosts_view as V
        real = V.catalog_of
        V.catalog_of = lambda host: {"models": [{"model": "coder:30b", "name": "coder:30b"}]}
        try:
            answer = A.mark_installed({"rows": [{"source": "ollama", "id": "coder", "tag_or_file": "30b", "name": "coder:30b",
                                                 "model": "coder:30b", "pull_line": "ollama pull coder:30b"}]}, h.state)
        finally:
            V.catalog_of = real
    row = (answer.get("rows") or [{}])[0]
    ctx.check(f"the card carries it, got {card.get('fit_evidence')}", (card.get("fit_evidence") or {}).get("state") == "verified")
    ctx.check(f"the blocks' fit line (halo models show), got {lines}", lines and lines[0] == "  fit: verified -- 41/41 layers, "
              "splits = 2, 258 tok/s (the log)")
    ctx.check(f"a library row of an installed model, got {row.get('installed')} {row.get('fit_evidence')}",
              row.get("installed") == ["box"] and (row.get("fit_evidence") or {}).get("line", "").startswith("verified -- 41/41"))


@test
def test_twin_verify_says_the_same_line(ctx: Ctx):
    from halo_harness.providers.fit_evidence import line_of
    from halo_harness.providers.ollama_twin_verify import _line
    r = {"state": "verified", "layers": [49, 49], "splits": 2, "tok_s": 188.0, "window": 32768}
    ctx.check(f"the twin's line is line_of's, got {_line(r)!r}", _line(r) == line_of("verified", layers=[49, 49], splits=2,
                                                                                    tok_s=188.0, window=32768))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
