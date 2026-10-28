"""tests.helpers.ollama_panel_seed -- Halo 3.3.4.0 R5: one fixture for the steward's Studio routes
(tests/test_ollama_steward_api.py) and the Ollama panel's Chrome driver (tests/helpers/studio_ollama.py): two
configured hosts (`pc`, `samus`: 192.0.2.x placeholders), a Hugging Face local server on loopback, the ledger
(the 27B's trims and cut replies, a coder, a small model, the local server's OpenAI-dialect lines), a server event,
a hardware card per host with ComfyUI holding memory (so the fit plan has options and a server-side hint), the
catalog rows, a steward note, and `review` mode. The card and the catalog reach Studio through
studio/ollama_hosts_view.READERS; nothing is sent anywhere.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from tests.helpers.steward_seed import GIB, MIB, PC, SAMUS, at, event, line, rows

LOCAL = {"name": "llama-box", "url": "http://127.0.0.1:8080/v1"}
NOTE = "The 27B spills to the CPU on pc: ComfyUI holds 2.0 GiB of the card."
COST = "(steward model ol:qwen3.5:9b: local, free)"
BIG, CODER, SMALL, HF = "qwen3.8:27b", "qwen3-coder:30b", "qwen3.5:9b", "llama-3.1-8b"
# what the fixture's last hour holds per host and model (the panel's rows are held to these)
HOUR = {("pc", BIG): {"calls": 7, "trims": 1, "cuts": 1, "errors": 1}, ("pc", CODER): {"calls": 3, "trims": 0, "cuts": 0,
        "errors": 0}, ("samus", SMALL): {"calls": 2, "trims": 0, "cuts": 0, "errors": 0},
        ("llama-box", HF): {"calls": 3, "trims": 0, "cuts": 1, "errors": 0}}
CONFIG = {"ollama": {"hosts": [PC, SAMUS], "steward": {"apply": "review"}},
          "huggingface": {"local_servers": [LOCAL]}}


def cards() -> dict:
    """The hardware card per host name (ollama_steward/hardware.py's shape)."""
    expires = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 240))
    pc = {"gpus": [{"id": "0", "name": "a 24 GB card", "library": "CUDA", "total_bytes": 24564 * MIB,
                    "available_bytes": 1200 * MIB}],
          "unified": False, "ram_bytes": 64 * GIB, "other_users": [{"name": "ComfyUI", "bytes": 2 * GIB}],
          "server": {"version": "0.40.6", "kv_cache_type": "f16", "parallel": 1, "max_loaded": 3, "keep_alive": "5m",
                     "flash_attention": True, "source": "fixture"},
          "loaded": [{"model": BIG, "size": 20 * GIB, "size_vram": 18 * GIB, "expires": expires, "context_length": 32768}],
          "sources": [], "read_at": "fixture"}
    samus = {"gpus": [{"id": "0", "name": "a 10 GB card", "library": "CUDA", "total_bytes": 10240 * MIB,
                       "available_bytes": 3000 * MIB}],
             "unified": False, "ram_bytes": 64 * GIB, "other_users": [],
             "server": {"version": "0.40.6", "kv_cache_type": "q8_0", "parallel": 1, "max_loaded": 1},
             "loaded": [{"model": SMALL, "size": 7 * GIB, "size_vram": 7 * GIB, "expires": expires,
                         "context_length": 16384}], "sources": [], "read_at": "fixture"}
    return {"pc": pc, "samus": samus}


def catalogs() -> dict:
    r = rows()
    return {"pc": {"models": [r[BIG], r[CODER]]}, "samus": {"models": [r[SMALL]]}}


def readers() -> dict:
    """studio/ollama_hosts_view.READERS for this fixture."""
    c, k = cards(), catalogs()
    return {"card": lambda host: c.get(host.name), "catalog": lambda host: k.get(host.name, {"models": []})}


def ledger() -> list:
    out = [line(prompt_eval_count=p) for p in (30500, 31000, 29800, 30900)]
    out += [line(trimmed=True, prompt_eval_count=12000, ago=300), line(done_reason="length", prompt_eval_count=32000,
                                                                        ago=240),
            line(status=500, prompt_eval_count=None, error="HTTP 500", ago=180)]
    out += [line(model=CODER, prompt_eval_count=8000, ago=1200 + i * 60) for i in range(3)]
    out += [line(model=CODER, prompt_eval_count=9000, ago=3 * 3600 + i * 60) for i in range(2)]
    out += [line(host=SAMUS, model=SMALL, num_ctx_sent=16384, prompt_eval_count=4000, ago=900 + i * 60) for i in range(2)]
    hf = {"name": "127.0.0.1:8080", "url": LOCAL["url"]}
    out += [line(host=hf, model=HF, dialect="openai", num_ctx_sent=None, window_source="server default",
                 prompt_eval_count=3000, ago=700 + i * 60, **({"done_reason": "length"} if i == 0 else {}))
            for i in range(3)]
    return out


def seed(state: Path, *, config: bool = True) -> Path:
    """Write the fixture into `state` (a scratch home's state dir); returns it."""
    from halo_harness.ollama_steward import notes
    from halo_harness.ollama_steward.ledger import append_lines
    from halo_harness.ollama_steward.server_events import record_events
    from halo_harness.providers.ollama_calibrate import record_calibration
    state.mkdir(parents=True, exist_ok=True)
    if config:
        p = state / "config.json"
        cfg = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}
        for section, values in CONFIG.items():
            cfg.setdefault(section, {}).update(values)
        p.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    record_calibration(state, host_url=PC["url"], model=BIG, digest=None, max_full_gpu_ctx=65536, ollama_version=None)
    append_lines(state, ledger())
    record_events(state, [event("cpu-spill", model=BIG, ago=900, gpu_layers=58, layers=65)], host="pc")
    notes.append(state, "note", NOTE, lines=[NOTE, "Every reload since 10:40 waited on ComfyUI's memory.", COST],
                 cost="local, free", attention=True, model="ol:qwen3.5:9b", where="studio")
    return state


__all__ = ["BIG", "CODER", "SMALL", "HF", "HOUR", "LOCAL", "NOTE", "COST", "PC", "SAMUS", "at", "cards", "catalogs",
           "readers", "ledger", "seed"]
