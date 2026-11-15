"""tests.test_models_refresh_local_view -- fx studio batch 1 (3): Studio's model Refresh and R14's shared local
models view (providers/local_view_cache.py). A model pulled in a terminal must be in the picker after ONE Refresh:
the Refresh reads every Ollama host again (studio/models_refresh.py `_ollama`), so the shared view built from the
old catalog is dropped and the next read (POST models/refresh's own `rows`, the page's GET models) builds from the
catalog just read. A fake Ollama on 127.0.0.1:0 (tests/helpers/mock_ollama.py), a scratch state dir, no model call.
Run: python -m tests.test_models_refresh_local_view
"""
from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _tag(name: str) -> dict:
    return {"name": name, "model": name, "modified_at": "2026-01-01T00:00:00Z", "size": 1000, "digest": "sha256:" + name,
            "details": {"family": "qwen3", "families": ["qwen3"], "parameter_size": "1B", "quantization_level": "Q4_0",
                        "format": "gguf"}}


def _show() -> dict:
    return {"modelfile": "", "parameters": "", "template": "", "capabilities": ["tools"],
            "details": {"family": "qwen3"}, "model_info": {"qwen3.context_length": 8192}}


@test
def test_one_refresh_shows_a_model_pulled_in_a_terminal(ctx: Ctx):
    from tests.helpers.mock_ollama import MockUpstream
    from halo_harness.providers import local_models as LM, local_view_cache as V, ollama as O
    from halo_harness.studio import models_refresh as MR
    state = Path(tempfile.mkdtemp(prefix="halo-refresh-view-")) / ".halo"
    state.mkdir(parents=True)
    saved = (MR.jobs_for, LM.build_local_view)
    with MockUpstream(tags_response={"models": [_tag("alpha:latest")]},
                      show_responses={"alpha:latest": _show(), "beta:latest": _show()}) as mock:
        url = f"http://127.0.0.1:{mock._server.server_address[1]}"
        host = O.OllamaHost(name="gpu-box", url=url)
        env = {"OLLAMA_HOST": url}

        def built(**_k) -> list:  # the view's rows from the host's catalog as the cache holds it (the real build does)
            return [m.get("name") for m in O.get_catalog(host).get("models") or []]
        try:
            LM.build_local_view = built
            MR.jobs_for = lambda s, e, local=True: [("Ollama (gpu-box)", "ollama", MR._ollama(host))] if local else []
            V.forget()
            first = V.view(env, state)
            ctx.check(f"page load: the picker's local rows, got {first}", first == ["alpha:latest"])
            mock.tags_response = {"models": [_tag("alpha:latest"), _tag("beta:latest")]}  # `ollama pull beta`
            record = MR.refresh(state, env, box_s=5)
            line = [o["line"] for o in record["outcomes"]]
            after = V.view(env, state)
            ctx.check(f"Refresh says ok, 2 models AND the next read lists beta, got {line} {after}",
                      line == ["ok, 2 models"] and after == ["alpha:latest", "beta:latest"])
        finally:
            MR.jobs_for, LM.build_local_view = saved
            V.forget()
            O.reset_catalog_cache()


@test
def test_a_forget_while_a_build_runs_keeps_no_old_rows(ctx: Ctx):
    """A build that started before `forget()` (a stale read's background build, a picker read in flight) must not
    put the old rows back after the forget: the next read builds again."""
    from halo_harness.providers import local_models as LM, local_view_cache as V
    state = Path(tempfile.mkdtemp(prefix="halo-refresh-race-")) / ".halo"
    state.mkdir(parents=True)
    gate, started = threading.Event(), threading.Event()
    answers = {"n": 0}

    def built(**_k) -> list:
        answers["n"] += 1
        n = answers["n"]
        if n == 1:
            started.set()
            gate.wait(10)
        return [f"build-{n}"]
    saved = LM.build_local_view
    try:
        LM.build_local_view = built
        V.forget()
        got: list = []
        t = threading.Thread(target=lambda: got.append(V.view({}, state)), daemon=True)
        t.start()
        started.wait(10)
        V.forget()  # a Refresh read the hosts again while the first build was still out
        gate.set()
        t.join(10)
        time.sleep(0.05)
        again = V.view({}, state)
        ctx.check(f"after the forget the next read is a new build, got first {got} then {again}", again == ["build-2"])
    finally:
        LM.build_local_view = saved
        V.forget()


@test
def test_the_local_tab_seeing_a_new_model_list_drops_the_pickers_view(ctx: Ctx):
    """The sibling door: the Local tab (studio/local_catalog.py) reads /api/tags and, when its signature changed (a
    pull in a terminal), builds the host's catalog again; the picker's shared view goes with it."""
    from types import SimpleNamespace
    from halo_harness.providers import local_models as LM, local_view_cache as V
    from halo_harness.studio import local_catalog as LC
    state = Path(tempfile.mkdtemp(prefix="halo-refresh-tab-")) / ".halo"
    state.mkdir(parents=True)
    models = {"now": [_tag("alpha:latest")]}
    host = SimpleNamespace(name="gpu-box", url="http://gpu-box.invalid:11434", api_key=None, dialect=None)
    saved = (LM.build_local_view, LC.TAGS_TTL_S)
    try:
        LM.build_local_view = lambda **_k: [m["name"] for m in models["now"]]
        LC.TAGS_TTL_S = 0.0
        LC.reset()
        V.forget()
        tags, build = (lambda h: {"models": list(models["now"])}), (lambda h: {"models": list(models["now"])})
        LC.catalog_for(host, tags=tags, build=build)
        first = V.view({}, state)
        models["now"] = [_tag("alpha:latest"), _tag("beta:latest")]
        LC.catalog_for(host, tags=tags, build=build)
        after = V.view({}, state)
        ctx.check(f"the tab saw beta; the picker's next read lists it, got {first} then {after}",
                  first == ["alpha:latest"] and after == ["alpha:latest", "beta:latest"])
    finally:
        LM.build_local_view, LC.TAGS_TTL_S = saved
        LC.reset()
        V.forget()


if __name__ == "__main__":
    os.environ.setdefault("OLLAMA_HOST", "http://127.0.0.1:9")
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
