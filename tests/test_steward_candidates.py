"""tests.test_steward_candidates -- Halo 3.3.7.0 R5: the steward candidates (ollama_steward/candidates.py) and
choose_model picking from them (ollama_steward/agent.py), over tests/helpers/sched_rig.SchedHome (the fixture card,
pc's four models on a 32 GB card, the main model qwen3-coder:30b at 32 k); no request beyond 127.0.0.1, no model:

1. ranked: tool calls verified first, then fits beside the main model, then the smaller; each with why ("fits beside
   qwen3-coder:30b, 6.4 GB, tool calls verified"); a model that crowds main out says so;
2. choose_model picks the first installed one that can call tools and fits beside main, and says why;
3. with nothing installed, the known-good small models that would fit, each a download with its size and minutes (never
   downloaded here);
4. `halo ollama steward candidates` prints the line, one row each, and what the steward runs on.
Run: python -m tests.test_steward_candidates
"""
from __future__ import annotations

import contextlib
import io
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.sched_rig import BIG, CODER, SMALL, TINY, SchedHome  # noqa: E402
from tests.helpers.steward_seed import card  # noqa: E402

test, TESTS = new_registry()


def _verified(h, model: str) -> None:
    from halo_harness.providers.ollama_capability import save_profile
    save_profile(h.state, {"model": model, "host": "pc", "digest": f"sha256:{model[:4]}", "ollama_version": "0.40.6",
                           "probe_set": "battery-3", "probed_at": time.time() - 60, "tools": "yes", "vision": "no",
                           "sits": "a small helper", "agentic_ready": False, "evidence": {}, "speed": {"tok_s": 95.0}})


@test
def test_ranked_with_why(ctx: Ctx):
    from halo_harness.ollama_steward.candidates import candidates, line
    with SchedHome(card=card(total_mib=32768, kv="q8_0")) as h:
        h.config(**{"model": f"ol:{CODER}@pc"})
        _verified(h, SMALL)
        got = candidates(h.state)
        names = [c["model"] for c in got]
        ctx.check(f"the verified 9B first, got {names}", names[0] == f"ol:{SMALL}@pc")
        top = got[0]
        ctx.check(f"its why, got {top['why']!r}", top["why"].startswith(f"fits beside {CODER}, ")
                  and "tool calls verified" in top["why"] and "95 tok/s" in top["why"] and top["fits_beside_main"] is True)
        big = next(c for c in got if c["model"] == f"ol:{BIG}@pc")
        ctx.check(f"the 27B crowds main out, said, got {big['why']!r}", big["fits_beside_main"] is False
                  and big["why"].startswith(f"does not fit beside {CODER} ("))
        ctx.check(f"the line, got {line(got)!r}", line(got).startswith(
            f"candidates to run the steward on this machine: {SMALL} (fits beside {CODER}, "))


@test
def test_choose_model_picks_from_them(ctx: Ctx):
    from halo_harness.ollama_steward.agent import choose_model
    with SchedHome(card=card(total_mib=32768, kv="q8_0")) as h:
        h.config(**{"model": f"ol:{CODER}@pc"})
        _verified(h, SMALL)
        local = [(f"ol:{m}@pc", 1) for m in (BIG, CODER, SMALL, TINY)]
        got = choose_model(configured="", compaction="", local=local, state_dir=h.state)
        ctx.check(f"the verified one that fits beside main, said why, got {got}", got[0] == f"ol:{SMALL}@pc"
                  and got[1].startswith(f"the best steward candidate here: fits beside {CODER}"))


@test
def test_known_good_downloads_when_nothing_is_installed(ctx: Ctx):
    from halo_harness.ollama_steward.candidates import best, candidates
    from halo_harness.studio import ollama_hosts_view as V
    with SchedHome() as h:
        V.READERS["catalog"] = lambda host: {"models": []}
        V.reset_cache()
        got = candidates(h.state)
        ctx.check(f"known-good small ones, each a download with its size and minutes, got {[c['why'] for c in got]}",
                  got and all(not c["installed"] and c["download_gb"] and "GB download, ~" in c["why"] for c in got)
                  and got[0]["model"] == f"ol:{SMALL}@pc")
        ctx.check("none is the steward's pick (it needs the download first)", best(got) is None)
        ctx.check(f"nothing pulled, got {h.mock.pulled}", h.mock.pulled == [])


@test
def test_the_cli(ctx: Ctx):
    from halo_harness.ollama_steward.cli_steward import cmd_ollama_steward
    with SchedHome(card=card(total_mib=32768, kv="q8_0")) as h:
        h.config(**{"model": f"ol:{CODER}@pc", "ollama.steward.model": f"ol:{SMALL}@pc"})
        _verified(h, SMALL)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = cmd_ollama_steward(["candidates"])
        lines = out.getvalue().splitlines()
        ctx.check(f"the line, the rows, the chosen marked, got {rc} {lines}", rc == 0
                  and lines[0].startswith("candidates to run the steward on this machine: ")
                  and lines[1].startswith(f"  * ol:{SMALL}@pc: fits beside")
                  and lines[-1] == f"the steward runs on: ol:{SMALL}@pc (ollama.steward.model)")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
