"""tests.helpers.local_seed -- Halo 3.3.5.0 R1: one fixture for the Local tab
(tests/test_local_api.py in-process, tests/helpers/studio_local.py in headless
Chrome, tools/capture_local.py's picture). On top of the Ollama panel's seed
(tests/helpers/ollama_panel_seed.py: hosts `pc` and `samus` on 192.0.2.x
placeholders, the local server `llama-box`, the ledger, an event, the cards
and catalogs, a steward note) it adds `box`, a fake Ollama on 127.0.0.1:0
(tests/helpers/mock_ollama.py with /api/generate: Load and Unload land there),
the ledger's bytes, a fleet member's samples for its own host `mac` (the hub's
5-minute store), and the sampler's seams: nvidia-smi and /proc answers that move
every second (a fake clock is not needed: the page only reads the frames).
Nothing is sent anywhere but the fake.
"""
from __future__ import annotations

import time
from pathlib import Path

from tests.helpers import ollama_panel_seed as P
from tests.helpers.steward_seed import GIB, MIB, rows

BOX_MODELS = ("qwen3.5:9b", "qwen3-coder:30b", "nomic-embed-text")
EMBED = {"model": "nomic-embed-text", "size": 274_302_450, "capabilities": ["embedding"],
         "model_info": {"nomic-bert.block_count": 12, "nomic-bert.context_length": 2048},
         "details": {"quantization_level": "F16", "parameter_size": "137M", "family": "nomic-bert"}}
MEMBER = "mac@studio"


def box_rows() -> list:
    """box's catalog: the 9B (it can orchestrate), the coder (it cannot: the lane offer), an embedding model."""
    r = rows()
    small, coder = dict(r["qwen3.5:9b"]), dict(r["qwen3-coder:30b"])
    small["model_info"] = {**small["model_info"], "qwen35.context_length": 262144}
    coder["model_info"] = {**coder["model_info"], "qwen3moe.context_length": 262144}
    return [small, coder, dict(EMBED)]


def start_box():
    """The fake Ollama `box` serves: the three models in /api/tags and /api/show, nothing loaded."""
    from tests.helpers.mock_ollama import MockUpstream
    tags = {"models": [{"name": x["model"], "model": x["model"], "size": x["size"], "digest": f"sha256:b0{i}",
                        "modified_at": "2026-10-01T00:00:00Z", "details": x["details"]} for i, x in enumerate(box_rows())]}
    show = {x["model"]: {"capabilities": x["capabilities"], "model_info": x["model_info"], "details": x["details"],
                         "template": "", "parameters": "", "modelfile": ""} for x in box_rows()}
    return MockUpstream(tags_response=tags, show_responses=show, ps_response={"models": []}).start()


def box_card(mock) -> dict:
    """box's hardware card: a 24 GB card, what the fake has loaded now (its /api/ps)."""
    from halo_harness.ollama_steward.hardware_sources import parse_ps
    return {"gpus": [{"id": "0", "name": "a 24 GB card", "library": "CUDA", "total_bytes": 24564 * MIB,
                      "available_bytes": 20000 * MIB}], "unified": False, "ram_bytes": 64 * GIB, "other_users": [],
            "server": {"version": "0.40.6", "kv_cache_type": "f16", "parallel": 1, "max_loaded": 2, "source": "fixture"},
            "loaded": parse_ps(mock.ps_snapshot()), "sources": [], "read_at": "fixture"}


def readers(mock) -> dict:
    """studio/ollama_hosts_view.READERS: the panel seed's cards and catalogs, and box's from the fake."""
    c, k = P.cards(), P.catalogs()
    return {"card": lambda host: box_card(mock) if host.name == "box" else c.get(host.name),
            "catalog": lambda host: {"models": box_rows()} if host.name == "box" else k.get(host.name, {"models": []})}


def seed(state: Path, mock) -> Path:
    """The panel seed, then `box` added to ollama.hosts and the ledger lines given their bytes."""
    import json
    from halo_harness.ollama_steward.ledger import append_lines
    from tests.helpers.steward_seed import line
    P.seed(state)
    cfg_path = state / "config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    cfg["ollama"]["hosts"] = [P.PC, P.SAMUS, {"name": "box", "url": mock.base_url, "max_ctx": 65536}]
    cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    box = {"name": "box", "url": mock.base_url}
    append_lines(state, [line(host=box, model="qwen3.5:9b", num_ctx_sent=32768, prompt_eval_count=2000, eval_count=120,
                              bytes_in=8192, bytes_out=600, ago=120 + 30 * i) for i in range(3)])
    return state


class Seams:
    """The sampler's seams on a Linux-shaped machine: the GPU's use and memory move each read."""

    def __init__(self) -> None:
        self.n = 0

    def runner(self, argv, timeout):
        from halo_harness.ollama_steward.resources_readers import NVIDIA_APPS, NVIDIA_QUERY
        if argv == NVIDIA_QUERY:
            self.n += 1
            return f"{(self.n * 7) % 100}, {18000 + (self.n % 5) * 100}, 24564, {50 + self.n % 3}\n"
        if argv == NVIDIA_APPS:
            return "4242, /usr/bin/ollama, [N/A]\n"
        return None

    def read_file(self, path):
        if path == "/proc/meminfo":
            return "MemTotal:       67108864 kB\nMemAvailable:   33554432 kB\n"
        if path == "/proc/stat":
            self.n += 1
            return f"cpu  {1000 + self.n * 40} 0 {500 + self.n * 10} {8000 + self.n * 50} 0 0 0 0 0 0\n"
        return None

    def as_seams(self):
        from halo_harness.ollama_steward.resources_readers import Seams as S
        return S(runner=self.runner, read_file=self.read_file, platform="linux", injected=True)


def sampler_seams(mock) -> dict:
    """resources.SAMPLER_SEAMS: the fake machine, its hosts `pc` (the card fixture's loaded model) and `box` (the fake)."""
    from halo_harness.providers.ollama import resolve_ollama_host
    big = {"models": [{"name": P.BIG, "model": P.BIG, "size": 20 * GIB, "size_vram": 18 * GIB, "context_length": 32768}]}
    return {"seams": Seams().as_seams(), "hosts": lambda: [h for h in (resolve_ollama_host("pc"), resolve_ollama_host("box")) if h],
            "ps": lambda host: big if host.name == "pc" else mock.ps_snapshot()}


def member_samples(now: float = None) -> list:
    """A member's samples for its own host (what its ledger push carries), the last 20 s."""
    now = time.time() if now is None else now
    return [{"host": "local", "url": "http://127.0.0.1:11434", "lan_url": "http://192.0.2.30:11434", "t": now - 20 + i,
             "gpu": 30 + i, "vram_used": 9 * GIB, "vram_total": 32 * GIB, "holder": "qwen3.5:9b",
             "holders": [{"name": "qwen3.5:9b", "bytes": 7 * GIB, "kind": "model"}], "ram_used": 20 * GIB,
             "ram_total": 32 * GIB, "cpu": 12.5, "temp": None, "others": 2 * GIB, "unified": True,
             "sources": {"gpu": "ioreg IOAccelerator over sysctl hw.memsize (unified memory)"}} for i in range(20)]


__all__ = ["BOX_MODELS", "MEMBER", "box_rows", "start_box", "readers", "seed", "Seams", "sampler_seams", "member_samples"]
