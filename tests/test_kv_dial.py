"""tests.test_kv_dial -- Halo 3.3.6.0 R4 deliverable 3, the KV-quantisation dial (providers/kv_dial.py) on fixture
hardware cards, catalog rows and crash fingerprints (no server):

1. the window at f16 vs q8_0 (and q4_0 only when it buys more) on this card, the line "f16 KV -> 32k, q8_0 KV -> 64k
   on this card (q8_0 KV: a small quality cost)", the window in force follows the card's KV type (the Halo-side half:
   fit.card_budget already reads it);
2. the crash note when this host's fingerprints count crashes with FA + q8_0 KV, and the host-side half as a stated
   action (the env vars, "restart Ollama on <host>"), never set by Halo;
3. no card or no model shape: no dial; the card carries it (blocks.kv_dial, `halo models show`'s "kv:" line) and the
   Models rows' window title reads it (studio/model_card_api.view's kv_dial).
Run: python -m tests.test_kv_dial
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.battery_rig import gpu_card  # noqa: E402
from tests.helpers.logs_rig import LogsHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.steward_seed import QWEN27  # noqa: E402

test, TESTS = new_registry()
BOX = {"name": "box", "url": "http://127.0.0.1:9"}
ROW = {"model": "qwen3.8:27b", "size": 17 * 10 ** 9, "model_info": {**QWEN27, "qwen35.context_length": 262144}}


def _fp(state, n: int, kv="q8_0", fa=True, host="box") -> None:
    p = Path(state) / "ollama" / "fingerprints.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    row = {"host": host, "model": "qwen3.8:27b", "signature": "cuda-ima", "kv_cache_type": kv, "flash_attention": fa,
           "spill": True, "window_used": 65536, "count": n, "at": "2026-10-29T10:00:00Z"}
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


@test
def test_the_windows_per_kv_type_and_the_line(ctx: Ctx):
    from halo_harness.ollama_steward.fit import model_window_on_card
    from halo_harness.providers.kv_dial import dial_for
    with LogsHome(hosts=[BOX]) as h:
        card = gpu_card(24.0, kv="f16")
        d = dial_for("box", "qwen3.8:27b", state_dir=h.state, card=card, row=ROW)
        by = {r["kv"]: r["window"] for r in d["rows"]}
        ctx.check(f"q8_0 holds a larger window than f16 on the same card, got {by}", by["q8_0"] > by["f16"] > 0)
        ctx.check(f"the line, got {d['text']!r}", d["text"].startswith(f"f16 KV -> {by['f16'] // 1024}k, q8_0 KV -> "
                                                                       f"{by['q8_0'] // 1024}k") and "on this card" in d["text"]
                  and "(q8_0 KV: a small quality cost" in d["text"])
        ctx.check(f"q4_0 shown only when it buys more than q8_0, got {list(by)}",
                  ("q4_0" not in by) or by["q4_0"] > by["q8_0"])
        ctx.check(f"the window in force is the f16 one (the card's type), got {d['window_in_force']}",
                  d["in_force"] == "f16" and d["window_in_force"] == model_window_on_card(card, ROW, step=4096) == by["f16"])
        ctx.check(f"f16 in force, q8_0 bigger: the host-side half stated, got {d['action']!r}",
                  d["action"].startswith("OLLAMA_KV_CACHE_TYPE=q8_0 with OLLAMA_FLASH_ATTENTION=1")
                  and "restart Ollama on box: Halo never sets them" in d["action"] and d["crash"] == "")
        q8 = dial_for("box", "qwen3.8:27b", state_dir=h.state, card=gpu_card(24.0, kv="q8_0"), row=ROW)
        ctx.check(f"a q8_0 card: the window in force is the q8_0 one, got {q8['window_in_force']}",
                  q8["in_force"] == "q8_0" and q8["window_in_force"] == by["q8_0"] and q8["action"] == "")


@test
def test_the_crash_note(ctx: Ctx):
    from halo_harness.providers.kv_dial import crashes_with_fa_q8, dial_for
    with LogsHome(hosts=[BOX]) as h:
        _fp(h.state, 3)
        _fp(h.state, 1)
        _fp(h.state, 2, kv="f16")
        _fp(h.state, 5, host="other")
        ctx.check("4 crashes here with FA + q8_0 (f16 and another host left out)", crashes_with_fa_q8(h.state, "box") == 4)
        card = gpu_card(24.0, kv="q8_0")
        card["server"]["flash_attention"] = True
        d = dial_for("box", "qwen3.8:27b", state_dir=h.state, card=card, row=ROW)
        ctx.check(f"the crash note, got {d['crash']!r}", d["crash"] == "4 crashes here with FA + q8_0 KV -- see "
                                                                       "`halo ollama crashes --why`")
        ctx.check(f"q8_0 in force with crashes: f16 (or FA off) stated, got {d['action']!r}",
                  d["action"].startswith("OLLAMA_KV_CACHE_TYPE=f16 (or OLLAMA_FLASH_ATTENTION=0), then restart Ollama on box"))
        ctx.check("no card: no dial", dial_for("box", "qwen3.8:27b", state_dir=h.state, card={}, row=ROW) is None)
        ctx.check("no model shape: no dial", dial_for("box", "x", state_dir=h.state, card=card, row={"size": 1}) is None)


@test
def test_the_card_carries_it(ctx: Ctx):
    from halo_harness.providers.model_card_blocks import block_lines
    from halo_harness.providers.model_card_measured import with_measured
    from halo_harness.studio import ollama_hosts_view as V
    from halo_harness.studio.model_card_api import view
    from halo_harness.providers import ollama as O
    import time
    with LogsHome(hosts=[BOX]) as h:
        _fp(h.state, 4)
        card = gpu_card(24.0, kv="q8_0")
        card["server"]["flash_attention"] = True
        with V._LOCK:
            V._CACHE[("card", BOX["url"])] = (time.time() + 1e9, card)
        with O._CATALOG_LOCK:
            O._CATALOG_CACHE[BOX["url"]] = (time.time() + 1e9, {"models": [ROW]})
        try:
            c = with_measured({"kind": "ollama", "host": "box", "name": "qwen3.8:27b", "blocks": {}}, h.state)
            ctx.check(f"blocks.kv_dial, got {c['blocks'].get('kv_dial')}", (c["blocks"].get("kv_dial") or {}).get("crash", "")
                      .startswith("4 crashes here"))
            out = block_lines(c["blocks"])
            ctx.check(f"halo models show prints 'kv:' and the crash note, got {out}", any(x.startswith("  kv: f16 KV -> ") for x in out)
                      and any("4 crashes here" in x for x in out))
            v = view(c, None)["card"]
            ctx.check("the Models rows' view carries the dial", (v.get("kv_dial") or {}).get("text", "").startswith("f16 KV"))
        finally:
            with V._LOCK:
                V._CACHE.pop(("card", BOX["url"]), None)
            with O._CATALOG_LOCK:
                O._CATALOG_CACHE.pop(BOX["url"], None)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
