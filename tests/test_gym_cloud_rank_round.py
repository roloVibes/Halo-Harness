"""tests.test_gym_cloud_rank_round -- Halo 2.0.6 round 11: the gym's
cloud-model ranking.

`halo gym propose --candidates local|cloud|all`: the ranking pool was
local-only by construction; the gym already RUNS against any reachable
ref (`halo gym --model or:...`), so the proposal now ranks cloud models
too. The default stays "local" -- byte-for-byte the old behavior for
every existing caller. The tokens/s normalization is computed within
the CHOSEN pool (a cloud model's tok/s never normalizes against a local
GPU's ceiling, and vice versa).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()


def _result(ref, **kw):
    base = {"model_ref": ref}
    for key in ("tool_call_accuracy", "edit_success", "context_recall", "instruction_adherence"):
        base[key] = {"score": kw.pop(key, 0.8)}
    base["tokens_per_second"] = kw.pop("tokens_per_second", None)
    return base


@test
def test_local_default_is_byte_for_byte_the_old_behavior(ctx: Ctx):
    from halo_harness.gym_propose import best_candidate_for_role
    results = [_result("ol:qwen3-coder:30b@lan", edit_success=0.9),
               _result("or:deepseek/deepseek-v4-pro", edit_success=0.99)]
    chosen, none_sentence = best_candidate_for_role(results, "researcher")
    ctx.check(f"the default pool ignores the cloud model, got {chosen}",
              chosen is not None and chosen["value"] == "ol:qwen3-coder:30b@lan")
    ctx.check("no no-candidate sentence on a hit", none_sentence is None)


@test
def test_cloud_pool_ranks_only_cloud_refs(ctx: Ctx):
    from halo_harness.gym_propose import best_candidate_for_role
    results = [_result("ol:qwen3-coder:30b@lan", edit_success=0.95),
               _result("or:deepseek/deepseek-v4-pro", edit_success=0.90),
               _result("dbx:databricks-glm-5-3", edit_success=0.85)]
    chosen, _ = best_candidate_for_role(results, "researcher", candidates="cloud")
    ctx.check(f"the cloud pool picks the best CLOUD ref, got {chosen}",
              chosen is not None and chosen["value"] == "or:deepseek/deepseek-v4-pro")
    # a pool with no cloud results says so in plain English
    chosen2, sentence = best_candidate_for_role([results[0]], "researcher", candidates="cloud")
    ctx.check(f"an empty cloud pool gets the plain-English sentence, got {sentence!r}",
              chosen2 is None and "no cloud model" in sentence)


@test
def test_all_pool_ranks_everything_together(ctx: Ctx):
    from halo_harness.gym_propose import best_candidate_for_role
    results = [_result("ol:qwen3-coder:30b@lan", edit_success=0.70),
               _result("or:deepseek/deepseek-v4-pro", edit_success=0.95)]
    chosen, _ = best_candidate_for_role(results, "researcher", candidates="all")
    ctx.check(f"'all' lets the cloud model win on merit, got {chosen}",
              chosen is not None and chosen["value"] == "or:deepseek/deepseek-v4-pro")


@test
def test_tps_normalizes_within_the_chosen_pool(ctx: Ctx):
    """A cloud model's tok/s must normalize against the CLOUD pool's own
    max (e.g. an API's 40 tok/s against a 60-tok/s API peer), never
    against a local GPU's 200-tok/s ceiling -- a pool-relative metric,
    not a global one."""
    from halo_harness.gym_propose import composite_score, best_candidate_for_role
    local_fast = _result("ol:qwen3.8:27b@lan", instruction_adherence=0.5, tokens_per_second=200.0)
    cloud_a = _result("or:a/model", instruction_adherence=0.5, tokens_per_second=40.0)
    cloud_b = _result("or:b/model", instruction_adherence=0.5, tokens_per_second=60.0)
    # same edit score; only tps differs -> the faster cloud model wins
    # within its own pool (40/60 vs 60/60), and the local one never
    # enters the cloud ranking at all
    chosen, _ = best_candidate_for_role([local_fast, cloud_a, cloud_b], "small",
                                        candidates="cloud")
    ctx.check(f"the cloud ranking prefers the faster cloud peer, got {chosen}",
              chosen is not None and chosen["value"] == "or:b/model")
    # and in the 'all' pool the 200-tok/s local model's tps term dominates
    chosen_all, _ = best_candidate_for_role([local_fast, cloud_a, cloud_b], "small",
                                            candidates="all")
    ctx.check(f"'all' sees the local tps ceiling, got {chosen_all}",
              chosen_all is not None and chosen_all["value"] == "ol:qwen3.8:27b@lan")


@test
def test_propose_role_table_threads_the_scope(ctx: Ctx):
    from halo_harness.gym_propose import propose_role_table
    results = [_result("ol:qwen3-coder:30b@lan", edit_success=0.70),
               _result("or:deepseek/deepseek-v4-pro", edit_success=0.95)]
    local_dict, _ = propose_role_table(results, roles=["researcher"], main_ref_raw=None)
    all_dict, _ = propose_role_table(results, roles=["researcher"], main_ref_raw=None, candidates="all")
    ctx.check(f"the default proposes the local pick, got {local_dict}",
              local_dict.get("researcher") == "ol:qwen3-coder:30b@lan")
    ctx.check(f"'all' proposes the cloud pick, got {all_dict}",
              all_dict.get("researcher") == "or:deepseek/deepseek-v4-pro")


@test
def test_the_cli_flag_reaches_the_ranking(ctx: Ctx):
    """Structural pin: the flag exists, has the three choices, and is
    threaded into propose_role_table at the one call site."""
    src = (Path(__file__).resolve().parent.parent / "halo_harness" / "gym_cli.py") \
        .read_text(encoding="utf-8")
    ctx.check("the --candidates flag is declared with all three choices",
              '"--candidates", choices=["local", "cloud", "all"]' in src)
    ctx.check("the call site threads it",
              "candidates=args.candidates" in src)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
