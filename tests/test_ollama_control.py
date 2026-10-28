"""tests.test_ollama_control -- Halo 3.3.5.0 R3: providers/ollama_control.py against the fake Ollama
(tests/helpers/mock_ollama.py + mock_ollama_pull.py, 127.0.0.1:0): the pull stream's lines in order with their
digest / total / completed, the model in /api/tags and /api/show after "success", a name the server cannot pull,
a cancel mid-stream (the fake sees the hang-up, nothing added, the answer says Ollama keeps its layers), an HF
GGUF through Ollama (`hf.co/<repo>:<quant>`), show's facts, copy, rename = copy + delete, delete and its 404,
`/api/ps`; and the test flag's guard: the made-up default host and a non-loopback address are never sent a call.
Run: python -m tests.test_ollama_control
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.control_env import Box  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _names(mock) -> list:
    return [t["model"] for t in mock.tags_response["models"]]


@test
def test_a_pull_streams_its_lines_and_the_model_arrives(ctx: Ctx):
    from halo_harness.providers.ollama_control import pull
    with Box() as b:
        seen = []
        got = pull(b.host, "qwen3.5:9b", on_status=seen.append)
        ctx.check(f"ok, the success said, got {got}", got["ok"] and got["say"] == "qwen3.5:9b pulled on box")
        statuses = [s["status"] for s in seen]
        ctx.check(f"the documented order, got {statuses}", statuses[0] == "pulling manifest" and statuses[-3:] ==
                  ["verifying sha256 digest", "writing manifest", "success"] and sum(s.startswith("pulling sha") is False
                  and s.startswith("pulling ") for s in statuses) == 6)
        layer = [s for s in seen if s.get("total")]
        ctx.check(f"each layer line has digest, total and completed rising to total, got {layer[-1]}",
                  layer and layer[-1]["completed"] == layer[-1]["total"] and layer[0]["completed"] < layer[0]["total"]
                  and layer[0]["digest"].startswith("sha256:") and got["total"] == layer[-1]["total"])
        ctx.check(f"the model is in /api/tags now, got {_names(b.mock)}", "qwen3.5:9b" in _names(b.mock))
        body = next(r["body"] for r in b.mock.requests if r["path"] == "/api/pull")
        ctx.check(f"the body is the documented one, got {body}", body == {"model": "qwen3.5:9b", "stream": True})


@test
def test_a_name_the_server_cannot_pull_says_its_error(ctx: Ctx):
    from halo_harness.providers.ollama_control import pull
    with Box() as b:
        got = pull(b.host, "no-such-model:1b")
        ctx.check(f"not ok, the server's error, got {got}", not got["ok"] and "file does not exist" in got["say"]
                  and got["error"] == "pull model manifest: file does not exist")


@test
def test_a_cancel_mid_stream_stops_it_and_says_what_ollama_keeps(ctx: Ctx):
    from halo_harness.providers.ollama_control import pull
    with Box(delay=0.3) as b:
        cancel = threading.Event()
        lines = []

        def on(s):
            lines.append(s)
            if s.get("completed"):
                cancel.set()
        t0 = time.monotonic()
        got = pull(b.host, "qwen3.5:9b", on_status=on, cancel=cancel)
        took = time.monotonic() - t0
        ctx.check(f"cancelled, not ok, quickly, got {got} in {took:.2f}s", got["cancelled"] and not got["ok"] and took < 2.0)
        ctx.check(f"it says Ollama keeps its layers, got {got['say']!r}", "keeps the layers" in got["say"])
        deadline = time.monotonic() + 5
        while not b.mock.pull_cancelled and time.monotonic() < deadline:
            time.sleep(0.05)
        ctx.check(f"the fake saw the hang-up and added nothing, got {b.mock.pull_cancelled} {_names(b.mock)}",
                  b.mock.pull_cancelled == ["qwen3.5:9b"] and "qwen3.5:9b" not in _names(b.mock))


@test
def test_an_hf_gguf_pulls_through_ollama(ctx: Ctx):
    from halo_harness.providers.ollama_control import pull, show
    with Box() as b:
        name = "hf.co/example-org/Some-8B-GGUF:Q4_K_M"
        got = pull(b.host, name)
        ctx.check(f"pulled, got {got['say']}", got["ok"] and name in b.mock.pulled)
        s = show(b.host, name)
        ctx.check(f"its show reads the GGUF's facts, got {s['facts']}", s["ok"] and s["facts"]["quant"] == "Q4_K_M"
                  and s["facts"]["context"] == 131072)


@test
def test_show_returns_the_facts(ctx: Ctx):
    from halo_harness.providers.ollama_control import pull, show
    with Box() as b:
        pull(b.host, "qwen3.5:9b")
        s = show(b.host, "qwen3.5:9b")
        v = s["show"]
        ctx.check(f"template, licence, capabilities, details, model_info, got {sorted(v)}", s["ok"] and
                  {"template", "license", "capabilities", "details", "model_info", "parameters"} <= set(v))
        ctx.check(f"parameters parsed, got {v['params']}", v["params"].get("temperature") == "0.7" and v["params"].get("stop") == "<|im_end|>")
        ctx.check(f"facts, got {s['facts']}", s["facts"] == {"family": "qwen35", "params": "9.0B", "quant": "Q4_K_M",
                                                             "format": "gguf", "parent": None, "context": 262144})
        miss = show(b.host, "nope:1b")
        ctx.check(f"a model it lacks: 404 said, got {miss}", not miss["ok"] and "HTTP 404" in miss["say"])


@test
def test_copy_rename_delete_and_the_404(ctx: Ctx):
    from halo_harness.providers.ollama_control import copy, delete, rename
    with Box() as b:
        got = copy(b.host, "qwen3:30b", "qwen3-mine:30b")
        ctx.check(f"copied, both names, got {got} {_names(b.mock)}", got["ok"] and {"qwen3:30b", "qwen3-mine:30b"} <= set(_names(b.mock)))
        got = rename(b.host, "qwen3-mine:30b", "qwen3-other:30b")
        ctx.check(f"renamed: the new one there, the old gone, got {got} {_names(b.mock)}", got["ok"]
                  and "qwen3-other:30b" in _names(b.mock) and "qwen3-mine:30b" not in _names(b.mock))
        body = next(r["body"] for r in b.mock.requests if r["path"] == "/api/copy")
        ctx.check(f"the documented copy body, got {body}", body == {"source": "qwen3:30b", "destination": "qwen3-mine:30b"})
        got = delete(b.host, "qwen3-other:30b")
        ctx.check(f"deleted, got {got}", got["ok"] and "qwen3-other:30b" not in _names(b.mock))
        got = delete(b.host, "qwen3-other:30b")
        ctx.check(f"a second delete: 404, said, got {got}", not got["ok"] and got["missing"] and got["status"] == 404)
        ctx.check(f"the delete went as DELETE /api/delete, got {b.paths('DELETE')}", b.paths("DELETE").count("/api/delete") == 3)
        ctx.check(f"a copy of a model it lacks: 404, got {copy(b.host, 'nope', 'x')}", copy(b.host, "nope", "x")["status"] == 404)


@test
def test_loaded_reads_api_ps(ctx: Ctx):
    from halo_harness.providers.ollama_control import loaded
    from tests.helpers.mock_ollama import partial_offload_ps_entry
    with Box() as b:
        b.mock.ps_response = {"models": [partial_offload_ps_entry("qwen3:30b", size=4 * 2 ** 30, size_vram=3 * 2 ** 30,
                                                                  context_length=32768)]}
        got = loaded(b.host)
        ctx.check(f"one row, its VRAM share and expiry, got {got}", got["ok"] and got["models"][0]["vram_pct"] == 75
                  and got["models"][0]["expires"] and got["models"][0]["context_length"] == 32768)


@test
def test_the_flag_keeps_every_call_off_the_default_host_and_real_addresses(ctx: Ctx):
    from halo_harness.providers.ollama import OllamaHost
    from halo_harness.providers import ollama_control as C
    with Box() as b:
        default = OllamaHost(name="default", url=b.mock.base_url, default=True, synthesized=True)
        lan = OllamaHost(name="lan", url="http://192.0.2.10:11434")
        here = OllamaHost(name="here", url="http://127.0.0.1:11434")
        for h in (default, lan, here):
            for got in (C.pull(h, "qwen3.5:9b"), C.delete(h, "x"), C.show(h, "x"), C.copy(h, "a", "b"), C.loaded(h)):
                ctx.check(f"{h.name}: not sent, the flag said, got {got}", not got["ok"] and got.get("blocked")
                          and "test flag" in got["say"])
        ctx.check(f"the fake behind the made-up default host saw nothing, got {b.mock.requests}", b.mock.requests == [])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
