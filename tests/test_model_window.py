"""tests.test_model_window -- Halo 3.3.5.0 R0: `agent/model_window.window_of`,
the window of a model with its source, every source from a fixture (every
reader injected: no server, no network, no model call):

1. Ollama: the steward profile, then the learned cap, the loaded window (the
   card's `/api/ps` row), the trained context (`/api/show`'s model_info), the
   host's max_ctx, the server default -- the first that knows wins and is
   named; a smaller bound (the learned cap, max_ctx, the card's fit, the hard
   cap) holds it and is named instead; `ceiling` is the learned cap, else the
   card's fit;
2. a Hugging Face local server: llama-server's `/props`, then LM Studio's
   model API, then the `/v1/models` row; the HF `config.json`; a
   `local.servers` entry's context; mlx with nothing known says unknown;
3. a cloud route: the cloud catalog's context;
4. `window_on_host` (the steward's panel and `halo ollama traffic`) fetches no
   catalog.
Run: python -m tests.test_model_window
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("BRIDGE_TEST_HOME", tempfile.mkdtemp(prefix="m0-window-"))
os.environ.setdefault("BRIDGE_TEST_NO_BACKGROUND_NET", "1")

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()

HOST = SimpleNamespace(name="lan", url="http://192.0.2.10:11434", max_ctx=None)
ROW = {"model": "qwen3.5:9b", "details": {"family": "qwen35"}, "model_info": {"qwen35.context_length": 262144},
       "capabilities": ["completion", "tools", "thinking"]}


def _ol(model="qwen3.5:9b"):
    return SimpleNamespace(provider="ollama", model=model, host="lan", raw=f"ol:{model}@lan", dialect="ollama")


def _w(ref, *, host=HOST, catalog=None, card=None, **readers):
    from halo_harness.agent.model_window import window_of
    base = {"profile": lambda h, m: None, "learned_cap": lambda h, m, *_: None, "catalog": lambda h: None}
    base.update(readers)
    return window_of(ref, state_dir=Path(os.environ["BRIDGE_TEST_HOME"]), host=host, catalog=catalog, card=card,
                     readers=base)


@test
def test_ollama_sources_in_order(ctx: Ctx):
    card = {"loaded": [{"model": "qwen3.5:9b", "context_length": 24576}]}
    w = _w(_ol(), catalog=ROW, card=card, profile=lambda h, m: 20480, learned_cap=lambda h, m, *_: 49152)
    ctx.check(f"the profile wins first, got {w}", w["tokens"] == 20480 and w["source"] == "steward profile")
    ctx.check("the ceiling is the learned cap", w["ceiling"] == 49152 and w["ceiling_source"] == "learned cap")
    w = _w(_ol(), catalog=ROW, card=card, learned_cap=lambda h, m, *_: 49152)
    ctx.check(f"no profile: the learned cap, got {w}", w["tokens"] == 49152 and w["source"] == "learned cap")
    w = _w(_ol(), catalog=ROW, card=card)
    ctx.check(f"no cap: the server's loaded window (/api/ps), got {w}", w["tokens"] == 24576 and w["source"] == "loaded window")
    w = _w(_ol(), catalog=ROW)
    ctx.check(f"not loaded: the trained context, held by the hard cap, got {w}",
              w["tokens"] == 131072 and w["source"] == "hard cap" and w["ceiling"] is None)
    small_row = dict(ROW, model_info={"qwen35.context_length": 32768})
    w = _w(_ol(), catalog=small_row)
    ctx.check(f"a trained context under the hard cap is named, got {w}", w["tokens"] == 32768 and w["source"] == "trained context")
    w = _w(_ol(), catalog={}, host=SimpleNamespace(name="lan", url=HOST.url, max_ctx=40960))
    ctx.check(f"nothing about the model: the host's max_ctx, got {w}", w["tokens"] == 40960 and w["source"] == "host max_ctx")
    w = _w(_ol(), catalog={})
    ctx.check(f"nothing at all: Ollama's server default, got {w}", w["tokens"] == 4096 and w["source"] == "server default")


@test
def test_a_smaller_bound_holds_the_window_and_is_named(ctx: Ctx):
    host = SimpleNamespace(name="lan", url=HOST.url, max_ctx=16384)
    w = _w(_ol(), host=host, catalog=ROW, profile=lambda h, m: 65536)
    ctx.check(f"a profile above the host's max_ctx is held there, got {w}", w["tokens"] == 16384 and w["source"] == "host max_ctx")
    w = _w(_ol(), catalog=ROW, profile=lambda h, m: 65536, learned_cap=lambda h, m, *_: 32768)
    ctx.check(f"and under the learned cap, got {w}", w["tokens"] == 32768 and w["source"] == "learned cap")
    card = {"gpus": [{"total_bytes": 1, "available_bytes": 1}], "loaded": []}
    ctx.check("a card with no room fits nothing (no bound from it)", _w(_ol(), catalog=ROW, card=card)["ceiling"] is None)


@test
def test_hugging_face_local_and_mlx(ctx: Ctx):
    ref = SimpleNamespace(provider="huggingface", model="Qwen/Qwen3-8B", host=None, local=True, mlx=False, raw="hf:local/Qwen/Qwen3-8B")
    w = _w(ref, props=lambda r: 8192, lmstudio=lambda r: 4096, loaded=lambda r: 2048, trained=lambda r: 40960)
    ctx.check(f"llama-server's /props n_ctx first, got {w}", w["tokens"] == 8192 and w["source"] == "loaded window" and w["kind"] == "hf-local")
    w = _w(ref, lmstudio=lambda r: 4096, loaded=lambda r: 2048)
    ctx.check(f"then LM Studio's model API, got {w}", w["tokens"] == 4096 and w["source"] == "loaded window")
    w = _w(ref, loaded=lambda r: None, trained=lambda r: 40960)
    ctx.check(f"nothing loaded: the HF config's max_position_embeddings, got {w}", w["tokens"] == 40960 and w["source"] == "trained context")
    w = _w(ref, loaded=lambda r: None, trained=lambda r: None, server_kind=lambda r: "lmstudio")
    ctx.check(f"nothing known on LM Studio: its default, got {w}", w["tokens"] == 4096 and w["source"] == "server default")
    mlx = SimpleNamespace(provider="huggingface", model="mlx-community/x", host=None, local=True, mlx=True, raw="hf:mlx/mlx-community/x")
    w = _w(mlx, loaded=lambda r: None, trained=lambda r: None)
    ctx.check(f"mlx with nothing known: unknown (it uses the trained context), got {w}", w["tokens"] is None and w["source"] == "unknown")
    local = SimpleNamespace(provider="local", model="m", host="box", local=False, mlx=False, raw="local:m@box")
    w = _w(local, host_max=lambda r: 12288)
    ctx.check(f"a local.servers entry's context, got {w}", w["tokens"] == 12288 and w["source"] == "host max_ctx" and w["kind"] == "local")


@test
def test_cloud_route_and_the_panel_helper(ctx: Ctx):
    from halo_harness.agent.model_window import window_on_host, window_words
    ref = SimpleNamespace(provider="openrouter", model="vendor/model", host=None, raw="or:vendor/model", dialect="openai-chat")
    w = _w(ref, cloud=lambda r: 200000)
    ctx.check(f"a cloud route: the catalog's context, got {w}", w["tokens"] == 200000 and w["source"] == "cloud catalog" and w["kind"] == "cloud")
    ctx.check("the words", window_words(w) == "200,000 (cloud catalog)" and window_words({}) == "unknown")
    import halo_harness.providers.ollama as O
    real = O.get_catalog
    O.get_catalog = lambda *a, **k: (_ for _ in ()).throw(AssertionError("no catalog read"))
    try:
        w = window_on_host("qwen3.5:9b", HOST, catalog_row=dict(ROW, model_info={"qwen35.context_length": 32768}))
    finally:
        O.get_catalog = real
    ctx.check(f"window_on_host reads the row in hand, never a catalog, got {w}", w["tokens"] == 32768 and w["source"] == "trained context")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
