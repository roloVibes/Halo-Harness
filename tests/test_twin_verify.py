"""tests.test_twin_verify -- Halo 3.3.6.0 R1: a fitted twin verified
(providers/ollama_twin_verify.py; plans/local-model-fit-brief.md Part A):

1. the fake Ollama answers `/api/ps` with `size_vram == size`: verified, the
   line with the layers and splits from the log lines and the warm tok/s (the
   first call after the load never timed); `size_vram < size`: spilled; the
   log saying 59/66 layers: spilled; no `/api/ps` row: unverified;
2. the result kept in the tune store (`verify`), the Models rows' chips: the
   twin's state and line, the raw tag with "delete the raw tag, keep the twin"
   only once its twin is verified;
3. the Library's pull-time warning when the weights alone exceed the card;
4. never a real host under the flag.
Run: python -m tests.test_twin_verify
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
ensure_default_provider_credentials()

from tests.helpers import mock_ollama_battery as MB  # noqa: E402
from tests.helpers.battery_rig import BatteryRig  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
TWIN = "bt-coder-halo:30b"
LOG = ["load_tensors: offloaded 49/49 layers to GPU", "llama_kv_cache: CUDA0 KV buffer size = 1632.00 MiB",
       "llama_context: graph splits = 2"]


def _rig():
    rig = BatteryRig(["bt-coder:30b"])
    return rig


def _twin_scenario(rig):
    rig.mock.scenarios[TWIN] = MB.scenario("bt-coder:30b")


@test
def test_verified_spilled_unverified(ctx: Ctx):
    from halo_harness.providers.ollama_twin_verify import verify
    with _rig() as rig:
        _twin_scenario(rig)
        MB.ps_full(rig.mock, TWIN, 32768)
        r = verify(rig.host, TWIN, 32768, state_dir=rig.state, log_lines=LOG)
        ctx.check(f"size_vram == size and 49/49: verified, got {r['state']} {r['line']!r}", r["state"] == "verified"
                  and r["line"] == "verified: 49/49 layers, splits = 2, 188 tok/s at 32,768")
        chats = rig.chats()
        ctx.check(f"a warm-up then one timed call, got {len(chats)}", len(chats) == 2)
        MB.ps_spill(rig.mock, TWIN, 32768, share=0.8)
        r = verify(rig.host, TWIN, 32768, state_dir=rig.state, log_lines=[])
        ctx.check(f"size_vram < size: spilled, got {r['line']!r}", r["state"] == "spilled" and "80% on the GPU" in r["line"])
        MB.ps_full(rig.mock, TWIN, 32768)
        r = verify(rig.host, TWIN, 32768, state_dir=rig.state, log_lines=["offloaded 59/66 layers to GPU"])
        ctx.check(f"the log's 59/66: spilled, got {r['line']!r}", r["line"].startswith("spilled: 59/66 layers"))
        rig.mock.ps_response = {"models": []}
        r = verify(rig.host, TWIN, 32768, state_dir=rig.state, log_lines=[])
        ctx.check(f"no /api/ps row: unverified, got {r['line']!r}", r["state"] == "unverified" and r["line"].startswith("unverified:"))


@test
def test_the_chips_and_the_raw_tag_offer(ctx: Ctx):
    from halo_harness.providers.ollama_twin_verify import verify
    from halo_harness.studio.local_twin_verify import raw_and_twins
    with _rig() as rig:
        _twin_scenario(rig)
        rows = [{"model": "bt-coder:30b", "twin_of": None}, {"model": TWIN, "twin_of": "bt-coder:30b"}]
        raw_and_twins(rig.host, rows, rig.state)
        ctx.check(f"a twin never checked: unverified, got {rows[1]['twin']}", rows[1]["twin"]["state"] == "unverified")
        ctx.check(f"the raw tag: no offer before the twin is verified, got {rows[0]['raw']}",
                  rows[0]["raw"]["twins"] == [TWIN] and rows[0]["raw"]["offer"] == "")
        MB.ps_full(rig.mock, TWIN, 32768)
        verify(rig.host, TWIN, 32768, state_dir=rig.state, log_lines=LOG)
        rows = [{"model": "bt-coder:30b", "twin_of": None}, {"model": TWIN, "twin_of": "bt-coder:30b"}]
        raw_and_twins(rig.host, rows, rig.state)
        ctx.check(f"the twin's chip: verified with its line, got {rows[1]['twin']}", rows[1]["twin"]["state"] == "verified"
                  and rows[1]["twin"]["line"].startswith("verified: 49/49"))
        ctx.check(f"the raw tag offers its delete, got {rows[0]['raw']['offer']!r}",
                  rows[0]["raw"]["offer"].startswith("delete the raw tag, keep the twin " + TWIN))
        from halo_harness.providers.ollama_tune_store import twin_verify
        ctx.check("kept in the tune store", (twin_verify(rig.state, host_url=rig.host.url, twin=TWIN) or {}).get("state")
                  == "verified")
        from halo_harness.providers.model_card import card_of
        card = card_of(f"ol:{TWIN}@fake", state_dir=rig.state, catalog={**MB.row("bt-coder:30b"), "model": TWIN, "name": TWIN},
                       host=rig.host)
        ctx.check(f"the twin's card says it, got {card.get('twin_verify')} {card['how'][-1]!r}",
                  (card.get("twin_verify") or {}).get("state") == "verified" and card["how"][-1].startswith("fitted twin, verified:"))


@test
def test_the_pull_time_warning(ctx: Ctx):
    from halo_harness.providers.ollama_twin_verify import pull_warning
    ctx.check(f"23 GB on a 23 GB card, got {pull_warning(23.4e9, 23.0e9)!r}",
              pull_warning(23.4e9, 23.0e9) == "23 GB on a 23 GB card: it will always spill")
    ctx.check("weights under the card: no warning", pull_warning(17e9, 23e9) == "")
    from halo_harness.models_library.rows import fit_for_row
    from tests.helpers.battery_rig import gpu_card
    from tests.helpers.steward_seed import CODER30
    row = {"source": "ollama", "id": "big", "tag_or_file": "big:70b", "params": 70.0, "weights_bytes": int(40e9),
           "size_bytes": int(40e9), "shape": {**CODER30, "qwen3moe.context_length": 32768}, "capabilities": []}
    fit = fit_for_row(row, gpu_card(24.0), 8192, host_name="fake")
    ctx.check(f"the Library row carries it, got {fit.get('pull_warning')!r}",
              (fit.get("pull_warning") or "").endswith("card: it will always spill"))


@test
def test_never_a_real_host_under_the_flag(ctx: Ctx):
    from halo_harness.providers.ollama import OllamaHost
    from halo_harness.providers.ollama_twin_verify import verify
    with _rig() as rig:
        r = verify(OllamaHost(name="lan", url="http://192.0.2.10:11434"), TWIN, 32768, state_dir=rig.state)
        ctx.check(f"unverified with the reason, nothing sent, got {r['line']!r}", r["state"] == "unverified"
                  and "test flag" in r["line"] and not rig.mock.requests)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
