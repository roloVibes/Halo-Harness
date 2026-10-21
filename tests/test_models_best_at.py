"""tests.test_models_best_at -- the "best at" cache and `halo models analyze`
(Halo 3.1.9.0 R1, "what each model is good at"):

1. `models_best_at.index` builds `<state>/models/best-at.json` once, answers
   from it while every source cache's mtime is unchanged, and rebuilds when
   one moves (models.json, a new gym result) or when it is forced;
2. a session start (`stale_ok`) gets the stale cache at once and the rebuild
   runs in the background for the next reader;
3. `halo models analyze --json` prints the cache: every model's kinds and
   line, the cheapest and the strongest per kind, sources by file name (no
   path, no key); the text form prints one line per model and the per-kind
   picks; `--best-for code` ranks with the new kinds.
Fixture caches only. Run: python -m tests.test_models_best_at
"""
from __future__ import annotations

import io
import json
import os
import sys
import time
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers import catalog_facts_seed as S  # noqa: E402

test, TESTS = new_registry()


def _bump(path: Path, by: float = 5.0) -> None:
    st = path.stat()
    os.utime(path, (st.st_atime + by, st.st_mtime + by))


@test
def test_the_cache_is_built_once_and_rebuilt_when_a_source_moves(ctx: Ctx):
    from halo_harness import models_best_at as B
    with S.home() as (_root, state):
        S.seed(state)
        calls = {"n": 0}
        real = B.rebuild

        def counting(state_dir, rows):
            calls["n"] += 1
            return real(state_dir, rows)
        B.rebuild = counting
        try:
            first = B.index(state)
            ctx.check("the first read builds the cache file", calls["n"] == 1 and B.cache_path(state).exists())
            ctx.check(f"it holds the catalog's models with kinds and a line, got {sorted(first['rows'])[:4]}",
                      "or:v/eyes" in first["rows"] and first["rows"]["or:v/eyes"]["line"] and first["rows"]["or:v/eyes"]["kinds"])
            again = B.index(state)
            ctx.check("an unchanged source set answers from the file (no rebuild)", calls["n"] == 1 and again["built"] == first["built"])
            _bump(state / "models.json")
            B.index(state)
            ctx.check("a moved models.json mtime rebuilds it", calls["n"] == 2)
            from halo_harness.gym import save_result
            save_result(state, {"model": "v/cheap", "model_ref": "or:v/cheap", "host_name": "cloud", "digest": None,
                                "tool_call_accuracy": {"score": 1.0}, "finished_at": time.time()})
            rebuilt = B.index(state)
            ctx.check("a new gym result rebuilds it, and the row shows the measure",
                      calls["n"] == 3 and "gym 1.00" in rebuilt["rows"]["or:v/cheap"]["line"])
            B.index(state, force=True)
            ctx.check("force rebuilds", calls["n"] == 4)
            ctx.check("a ref the cache lacks is scored for the call, not written",
                      "or:extra" in B.index(state, [{"ref": "or:extra", "provider": "openrouter"}])["rows"]
                      and "or:extra" not in (B.load(state) or {}).get("rows", {}) and calls["n"] == 4)
        finally:
            B.rebuild = real


@test
def test_a_session_start_reads_the_stale_cache_and_rebuilds_behind(ctx: Ctx):
    from halo_harness import models_best_at as B
    with S.home() as (_root, state):
        S.seed(state)
        saved, B.FIRST_BUILD_WAIT_S = B.FIRST_BUILD_WAIT_S, 0.0
        try:
            t0 = time.monotonic()
            none_yet = B.index(state, stale_ok=True)
            ctx.check("with no cache yet a session start does not wait past FIRST_BUILD_WAIT_S",
                      none_yet.get("rows") == {} and time.monotonic() - t0 < 2.0)
        finally:
            B.FIRST_BUILD_WAIT_S = saved
        B.wait_for_rebuild(state, 30)
        ctx.check("the first build lands behind it", bool((B.load(state) or {}).get("rows")))
        first = B.index(state)
        _bump(state / "models.json")
        stale = B.index(state, stale_ok=True)
        ctx.check("stale_ok answers with the cache it has", stale["built"] == first["built"])
        B.wait_for_rebuild(state, 30)
        ctx.check("the background rebuild left a fresh cache for the next reader", B.is_fresh(B.load(state), state)
                  and B.load(state)["built"] > first["built"])


@test
def test_halo_models_analyze_prints_the_cache(ctx: Ctx):
    from halo_harness.catalog_cli import cmd_models
    with S.home() as (root, state):
        env = S.seed(state)
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cmd_models(["analyze", "--json"])
        out = buf.getvalue()
        data = json.loads(out)
        eyes = data["rows"].get("or:v/eyes") or {}
        ctx.check(f"--json: every model's kinds and line, got {eyes.get('kinds')} {eyes.get('line')!r}",
                  rc == 0 and "visual" in eyes.get("kinds", []) and eyes.get("line", "").startswith("vision+pdf in"))
        ctx.check(f"--json: the strongest and the cheapest per kind, got {data['best'].get('audio')}",
                  data["best"]["audio"]["strongest"] in ("or:v/ears", "dbx:databricks-gemini-x-pro")
                  and data["best"]["bulk"]["strongest"] in ("or:v/cheap", "dbx:databricks-gemini-9-flash"))
        ctx.check("--json: sources by file name, never a path", "models.json" in data["sources"]
                  and str(root) not in out and str(root).replace("\\", "\\\\") not in out)
        ctx.check("--json: no provider key anywhere", not any(v in out for v in env.values() if v.startswith(("sk-", "dapi", "hf_", "xp-"))))
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cmd_models(["analyze"])
        text = buf.getvalue()
        ctx.check(f"the text form: one line per model, then the per-kind picks, got {text[:200]!r}",
                  rc == 0 and "or:v/painter" in text and "makes images" in text and "Cheapest and strongest per kind" in text)
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cmd_models(["--best-for", "code"])
        ctx.check(f"--best-for code ranks with the new kinds, got {buf.getvalue()[:200]!r}",
                  rc == 0 and "Best for code" in buf.getvalue() and "tool calls" in buf.getvalue())


@test
def test_an_empty_catalog_says_how_to_fill_it(ctx: Ctx):
    from halo_harness.catalog_cli import cmd_models
    with S.home() as (_root, state):
        S.seed(state, providers=False)
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cmd_models(["analyze"])
        ctx.check(f"exit 1 and the refresh hint, got {buf.getvalue()!r}", rc == 1 and "halo models --refresh" in buf.getvalue())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="models best-at tests"))
