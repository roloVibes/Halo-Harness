"""tests.test_model_rank -- the one order a model pick breaks a tie by (Halo 3.3.16.2, "from a session's own
review": `best_per_kind` broke an equal score by the model's name, so `...-4-1` beat `...-4-6`):

1. each rung decides in turn: the score, measured success here (3+ checked tasks), the newer version in a
   family, the larger context, the lower price, the provider with a key, the name;
2. versions: 4.6 over 4.1, a successor over its predecessor across separators (`-`, `.`, `v`), a date suffix,
   ids that do not parse fall through; measured outcomes outrank the version;
3. cheapest: price first, no price never wins it; the order is deterministic whatever the input order;
4. best_per_kind's `*_why`, a leader's line, the roster line, `best_for`'s `tie`, the auto pick's tie words;
   the index's schema is 2, so a schema-1 file is rebuilt once.
No model call. Run: python -m tests.test_model_rank
"""
from __future__ import annotations

import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _item(ref, score=0.9, price=1.0, context=200_000, provider="openrouter", measured=None):
    return {"ref": ref, "score": score, "price": price, "context": context, "provider": provider, "measured": measured}


def _top(items, keyed=None):
    from halo_harness import model_rank as R
    key = R.strongest_key(items)
    out = R.ranked(items, key, keyed=keyed)
    return out[0]["ref"], R.why(out[0], out[1] if len(out) > 1 else None, key, R.STRONGEST, keyed=keyed)


def _entry(score, price_in=1.0, ctx=200_000, provider="openrouter", outcomes=None, kind="code"):
    return {"kinds": [kind], "line": "a line", "scores": {kind: score},
            "facts": {"provider": provider, "price_in_per_m": price_in, "price_out_per_m": price_in,
                      "context_tokens": ctx, "measured": {"outcomes": outcomes} if outcomes else {}}}


@test
def test_each_rung_decides_in_turn(ctx: Ctx):
    ctx.check("the score first", _top([_item("a/x", 0.8), _item("z/y", 0.9)])[0] == "z/y")
    top, why = _top([_item("a/x"), _item("z/y", measured=(4, 5))])
    ctx.check(f"then measured here (4/5 beats unmeasured), got {top} {why!r}",
              top == "z/y" and why == "same score as a/x: measured 4/5 here")
    top, why = _top([_item("v/m-4.1"), _item("v/m-4.6")])
    ctx.check(f"then the newer version, got {top} {why!r}", top == "v/m-4.6" and why == "same score as v/m-4.1: newer")
    top, why = _top([_item("a/x", context=128_000), _item("z/y", context=1_000_000)])
    ctx.check(f"then the larger context, got {top} {why!r}", top == "z/y" and why == "same score as a/x: larger context")
    top, why = _top([_item("a/x", price=9.0), _item("z/y", price=2.0)])
    ctx.check(f"then the lower price, got {top} {why!r}", top == "z/y" and why == "same score as a/x: cheaper")
    top, why = _top([_item("a/x", provider="openai"), _item("z/y", provider="openrouter")],
                    keyed={"openai": False, "openrouter": True})
    ctx.check(f"then the provider with a key, got {top} {why!r}",
              top == "z/y" and why == "same score as a/x: you have its provider's key")
    top, why = _top([_item("z/y"), _item("a/x")])
    ctx.check(f"then the name, so it is deterministic, got {top} {why!r}", top == "a/x" and why == "same score as z/y: by name")
    ctx.check("a lower measured rate loses to an unmeasured one (neither proven nor failed)",
              _top([_item("a/x", measured=(1, 4)), _item("z/y")])[0] == "z/y")
    ctx.check("fewer than 3 checked tasks count as unmeasured", _top([_item("z/y", measured=(2, 2)), _item("a/x", price=0.5)])[0] == "a/x")


@test
def test_versions_parse_across_separators(ctx: Ctx):
    from halo_harness.model_rank import family_ranks, version_of
    for older, newer in (("dbx:databricks-claude-opus-4-1", "dbx:databricks-claude-opus-4-6"),
                         ("or:anthropic/claude-opus-4.1", "or:anthropic/claude-opus-4.6"),
                         ("or:deepseek/deepseek-v4-flash", "or:deepseek/deepseek-v4.1-flash"),
                         ("or:openai/gpt-5", "or:openai/gpt-5.3"), ("or:z/glm-4.9", "or:z/glm-4.10"),
                         ("ant:claude-sonnet-4-20250514", "ant:claude-sonnet-4-5-20250929"),
                         ("ant:claude-x-3-5-2024-06-20", "ant:claude-x-3-5-2024-10-22"),
                         ("ol:qwen3:8b", "ol:qwen3.5:8b"), ("or:openai/o3-mini", "or:openai/o4-mini")):
        ranks = family_ranks([older, newer])
        ctx.check(f"{newer} is newer than {older}: {version_of(older)} vs {version_of(newer)}",
                  ranks == {older: 1, newer: 0})
    ctx.check("different families never compare", family_ranks(["or:a/x-4.1", "or:a/y-4.6"]) == {"or:a/x-4.1": 0, "or:a/y-4.6": 0})
    ctx.check("a size is not a version", version_of("ol:qwen3:8b")[0] != version_of("ol:qwen3:30b")[0])
    ctx.check("an id with no version does not parse", version_of("dbx:databricks-gpt-oss-120b") is None
              and version_of("weird") is None)
    top, why = _top([_item("or:x/zeta", context=500_000), _item("or:x/alpha")])
    ctx.check(f"unparseable ids fall through to the next rung, got {top} {why!r}",
              top == "or:x/zeta" and why == "same score as or:x/alpha: larger context")
    top, why = _top([_item("v/m-4.6"), _item("v/m-4.1", measured=(5, 5))])
    ctx.check(f"measured outcomes outrank the version, got {top} {why!r}",
              top == "v/m-4.1" and why == "same score as v/m-4.6: measured 5/5 here")


@test
def test_cheapest_and_determinism(ctx: Ctx):
    from halo_harness import model_rank as R
    from halo_harness.models_best_at import best_per_kind
    entries = {"or:v/free-none": _entry(0.9, price_in=None), "or:v/m-4.1": _entry(0.5, price_in=0.5),
               "or:v/m-4.6": _entry(0.5, price_in=0.5), "or:v/big": _entry(0.95, price_in=3.0)}
    best = best_per_kind(entries, keyed={})["code"]
    ctx.check(f"no price never wins cheapest; the same price goes newer, got {best}",
              best["cheapest"] == "or:v/m-4.6" and best["cheapest_why"] == "same price as or:v/m-4.1: newer"
              and best["strongest"] == "or:v/big" and best["strongest_why"] == "")
    items = [_item(f"v/m-{v}", score=s, price=p) for v, s, p in (("4.1", 0.9, 1), ("4.6", 0.9, 1), ("5", 0.7, 1),
                                                                  ("3", 0.9, 0.5))]
    first = [it["ref"] for it in R.ranked(items, R.strongest_key(items), keyed={})]
    for seed in range(5):
        random.Random(seed).shuffle(items)
        ctx.check(f"shuffle {seed}: the same order", [it["ref"] for it in R.ranked(items, R.strongest_key(items), keyed={})] == first)
    ctx.check(f"the order: score, then the newest of the family, got {first}", first[:2] == ["v/m-4.6", "v/m-4.1"])
    cheap = [_item("a/c", score=0.5, price=1.0), _item("b/c", score=0.9, price=1.0), _item("c/c", score=0.1, price=0.2)]
    order = [it["ref"] for it in R.ranked(cheap, R.cheapest_key(cheap))]
    ctx.check(f"cheapest: the price first, then the higher score, got {order}", order == ["c/c", "b/c", "a/c"])


@test
def test_the_reasons_name_the_deciding_term(ctx: Ctx):
    from halo_harness.models_best_at import best_per_kind, lead_words
    entries = {"dbx:databricks-claude-opus-4-1": _entry(0.9, provider="databricks"),
               "dbx:databricks-claude-opus-4-6": _entry(0.9, provider="databricks")}
    best = best_per_kind(entries, keyed={})
    ctx.check(f"the owner's case: 4-6 over 4-1, got {best['code']}",
              best["code"]["strongest"] == "dbx:databricks-claude-opus-4-6"
              and best["code"]["strongest_why"] == "same score as dbx:databricks-claude-opus-4-1: newer")
    ctx.check("a leader's line carries it", lead_words(best) == {
        "dbx:databricks-claude-opus-4-6": "strongest for code: same score as dbx:databricks-claude-opus-4-1: newer; "
                                          "cheapest for code: same price as dbx:databricks-claude-opus-4-1: newer"})
    from halo_harness.capabilities import best_for
    rows = [{"ref": r, "provider": "openrouter", "tools": True, "context_tokens": 200_000, "price_in_per_m": 3.0,
             "price_out_per_m": 15.0, "modalities_in": ["text"], "modalities_out": ["text"]}
            for r in ("or:v/m-4.1", "or:v/m-4.6")]
    ranked = best_for(rows, "code")
    ctx.check(f"`halo models --best-for` ranks the newer first and says why, got {[(r['ref'], r.get('tie')) for r in ranked]}",
              ranked[0]["ref"] == "or:v/m-4.6" and ranked[0]["tie"] == "same score as or:v/m-4.1: newer")
    from halo_harness.models_auto import pick
    rows_idx = {r: {"kinds": ["code"], "scores": {"code": 0.9, "bulk": 0.5}, "facts": {
        "provider": "openrouter", "price_in_per_m": 1.0, "price_out_per_m": 1.0, "context_tokens": 200_000,
        "tools": True, "modalities_in": ["text"], "modalities_out": ["text"]}} for r in ("or:v/m-4.1", "or:v/m-4.6")}
    p = pick(None, needs=["tools"], band="high", main_ref="or:v/main", rows=rows_idx, kind="code", stats={},
             learn={"enabled": False, "min_tasks": 3, "window_days": 0, "drop_below": 0.34}, local_state={})
    ctx.check(f"the auto pick: the newer, and the tie says so, got {p.line()!r}",
              p.ref == "or:v/m-4.6" and "same score as or:v/m-4.1: newer" in p.reason)


@test
def test_the_index_schema_is_bumped(ctx: Ctx):
    from halo_harness import models_best_at as B
    import os
    import tempfile
    root = Path(tempfile.mkdtemp(prefix="rank-schema-", dir=os.environ.get("BRIDGE_TEST_HOME") or None))
    path = B.cache_path(root)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"schema": 1, "built": time.time(), "sources": {}, "rows": {}, "best": {}}), encoding="utf-8")
    ctx.check("schema is 2", B.SCHEMA == 2)
    ctx.check("a schema-1 index is not read, so every box rebuilds it once", B.load(root) is None)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
