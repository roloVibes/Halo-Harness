"""tests.test_fit_meter -- Halo 3.3.5.0 R0b: the fit meter
(`providers/fit_meter.py`), the first of "Local"'s five ideas. Pure arithmetic
on fixture cards (tests/helpers/model_card_fixtures.py) and host cards (one
24 GB GPU, another program holding part of it, a small RAM):

1. fits / tight / spill / no from the window the card runs at;
2. cloud and unknown (no hardware card, no size, a local server);
3. the host card comes from the Ollama panel's cache and is never read under
   BRIDGE_TEST_NO_BACKGROUND_NET; a picker row (studio/model_card_api.row_view)
   carries the card's chips and the meter from what is cached.
No server, no model call.
Run: python -m tests.test_fit_meter
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
ensure_default_provider_credentials()

from tests.helpers.model_card_fixtures import ROWS, host_card  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.steward_seed import Home  # noqa: E402

test, TESTS = new_registry()


def _meter(name: str, window: int, hc):
    from halo_harness.providers.fit_meter import fit_meter
    card = {"kind": "ollama", "host": "pc", "ref": f"ol:{name}@pc", "window": {"tokens": window, "source": "test"}}
    return fit_meter(card, hc, row=ROWS[name])


@test
def test_fits_and_tight(ctx: Ctx):
    m = _meter("qwen3.5:9b", 32768, host_card())
    ctx.check(f"the 9B at 32,768 on a 24 GB card fits with room, got {m}",
              m["level"] == "fits" and m["at_window"] == 32768 and "room to spare" in m["why"])
    t = _meter("qwen3-coder:30b", 65536, host_card())
    ctx.check(f"the 30B at 65,536 (f16 cache) holds only with every layer forced on: tight, got {t}",
              t["level"] == "tight" and t["gpu_window"] >= 65536 and "forced" in t["why"])
    f = _meter("qwen3-coder:30b", 32768, host_card())
    ctx.check(f"... and fits at 32,768, got {f['level']}", f["level"] == "fits")


@test
def test_spill_and_no(ctx: Ctx):
    s = _meter("qwen3.8:27b", 32768, host_card(others_gib=8, ram_gib=64))
    ctx.check(f"with 8 GB held by another program the 27B's weights pass the card: spill, got {s}",
              s["level"] == "spill" and "CPU" in s["why"] and "held by other programs" in s["why"])
    n = _meter("qwen3.8:27b", 32768, host_card(others_gib=12, ram_gib=2))
    ctx.check(f"with 12 GB held and 2 GB of RAM it does not fit this machine: no, got {n}",
              n["level"] == "no" and "RAM" in n["why"])


@test
def test_cloud_and_unknown(ctx: Ctx):
    from halo_harness.providers.fit_meter import fit_meter
    ctx.check("a cloud model's meter says cloud",
              fit_meter({"kind": "cloud", "window": {"tokens": 200000}}, None)["level"] == "cloud")
    no_card = _meter("qwen3.5:9b", 32768, None)
    ctx.check(f"no hardware card read: unknown, and it says so, got {no_card}",
              no_card["level"] == "unknown" and "no hardware card" in no_card["why"])
    bare = fit_meter({"kind": "ollama", "host": "pc", "ref": "ol:x@pc", "window": {"tokens": 8192}}, host_card(),
                     row={"model": "x"})
    ctx.check(f"a row with no size: unknown, got {bare['level']}", bare["level"] == "unknown")
    hf = fit_meter({"kind": "llama-server", "window": {"tokens": None, "source": "unknown"}}, None)
    served = fit_meter({"kind": "llama-server", "window": {"tokens": 16384, "source": "loaded window"}}, None)
    ctx.check(f"a local server without sizes: unknown; one that runs it now: fits, got {hf['level']} {served['level']}",
              hf["level"] == "unknown" and served["level"] == "fits" and "16,384" in served["why"])


@test
def test_the_host_card_comes_from_the_panels_cache(ctx: Ctx):
    from halo_harness.providers import ollama as O
    from halo_harness.providers.fit_meter import host_card_of
    from halo_harness.studio import ollama_hosts_view as V
    from halo_harness.studio.model_card_api import row_view
    with Home() as h:
        host = O.resolve_ollama_host("pc")
        V.reset_cache()
        calls = []
        V.READERS["card"] = lambda hh: calls.append(hh) or host_card()
        try:
            ctx.check("nothing cached and the test flag set: no read", host_card_of(host, read=True) is None and not calls)
            with V._LOCK:
                V._CACHE[("card", host.url)] = (time.monotonic(), host_card())
            ctx.check("the panel's cached card is used", host_card_of(host)["gpus"][0]["total_bytes"] == 24 * 2 ** 30)
            with O._CATALOG_LOCK:
                O._CATALOG_CACHE[host.url] = (time.monotonic(), {"models": [dict(ROWS["qwen3.5:9b"])]})
            got = row_view("ol:qwen3.5:9b@pc", None, h.state)
        finally:
            V.READERS.pop("card", None)
            V.reset_cache()
            O.reset_catalog_cache()
    ctx.check(f"a picker row carries the chips and the meter, got {got}",
              got["card"]["chips"]["tools"] == "tools" and got["card"]["chips"]["purpose"] == "instruct"
              and got["fit"]["level"] == "fits" and got["card"]["fit_for"]["small"])


if __name__ == "__main__":
    results, passed, failed, skipped = run_all(TESTS, Ctx())
    sys.exit(print_results(results, passed, failed, skipped))
