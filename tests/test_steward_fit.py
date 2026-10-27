"""tests.test_steward_fit -- Halo 3.3.4.0 R3: the fit planner
(ollama_steward/fit.py) on R1's worked cases: qwen3.8:27b and
qwen3-coder:30b on the measured 24 GB card, with nothing else on it and
with ComfyUI holding 6 GB; the Mac's unified memory; the server-side
options only as recommendations; what each plan loses; the plan from the
ledger (the Mac's lines included) through `halo ollama steward plan`.
Pure arithmetic on fixture cards and catalog rows: no server.
Run: python -m tests.test_steward_fit
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
ensure_default_provider_credentials()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.steward_seed import GIB, Home, card, line, rows  # noqa: E402

test, TESTS = new_registry()
BOTH = [{"model": "qwen3.8:27b", "window": 65536, "max_prompt": 30000, "calls": 10, "load_ms": 12000.0},
        {"model": "qwen3-coder:30b", "window": 65536, "max_prompt": 20000, "calls": 5, "load_ms": 11000.0}]


def _plan(c, asked=BOTH, other=None):
    from halo_harness.ollama_steward.fit import plan
    return plan(c, asked, rows(), host_name="pc", other_hosts=other)


def _kinds(p) -> list:
    return [o["kind"] for o in p["options"]]


@test
def test_one_model_alone_fits_and_says_so(ctx: Ctx):
    p = _plan(card(), asked=BOTH[:1])
    ctx.check(f"the 27B at 65,536 alone fits the card, got {p.get('says')}", p["fits_now"] is True and not p["options"])


@test
def test_the_27b_and_the_30b_on_one_24_gb_card(ctx: Ctx):
    """Weights alone are 32 GB: no pair of windows fits; one at a time
    does (each fits alone at 65,536), or the 30B asked on another host."""
    p = _plan(card(), other=lambda m: ["samus"])
    ctx.check(f"they do not fit together, got {p['says']}", p["fits_now"] is False)
    ctx.check(f"no 'windows' option (the weights alone overflow), got {_kinds(p)}", "windows" not in _kinds(p))
    chosen = p["options"][p["chosen"]]
    ctx.check(f"one at a time is chosen: keep_alive 0 on the less-called 30B, got {chosen}",
              chosen["kind"] == "one-at-a-time" and chosen["changes"] == [
                  {"key": "pc|qwen3-coder:30b", "field": "keep_alive", "to": "0"}])
    ctx.check(f"it says what you lose: a reload of about 11 s, got {chosen['lose']}", "about 11 s" in chosen["lose"])
    other = next(o for o in p["options"] if o["kind"] == "other-host")
    ctx.check(f"or the 30B on samus, got {other['changes']}", other["changes"][0]["to"] == "samus" and other["fits"])
    ctx.check("every option says what you lose", all(o.get("lose") for o in p["options"]))


@test
def test_with_comfyui_holding_6_gb(ctx: Ctx):
    """18 GB left: the 27B does not fit even alone (its weights, projector
    and recurrent state need 18.6 GB at the smallest window); the plan says
    so and keeps the server-side and quant lines as recommendations."""
    c = card(others=[{"name": "python (ComfyUI)", "bytes": 6 * GIB}])
    p = _plan(c, other=lambda m: ["samus"])
    ctx.check(f"18.0 GiB for models, got {p['budget']['budget'] / GIB:.1f}", round(p["budget"]["budget"] / GIB, 1) == 18.0)
    ctx.check(f"one at a time cannot help (the 27B alone overflows), got {_kinds(p)}", "one-at-a-time" not in _kinds(p))
    alone = next(o for o in p["options"] if o["kind"] == "window-alone")
    ctx.check(f"the 27B does not fit even at 8k beside ComfyUI, got {alone['says']}",
              not alone["fits"] and "does not fit" in alone["says"])
    other = next(o for o in p["options"] if o["kind"] == "other-host")
    ctx.check("moving the 30B alone is not enough, and it says so", not other["fits"] and "still needs" in other["lose"])
    quant = next(o for o in p["options"] if o["kind"] == "smaller-quant")
    ctx.check(f"the smaller quant is a pull line, never applied, got {quant}",
              quant["changes"] == [] and quant["server_hint"]["line"].startswith("ollama pull qwen3.8:27b"))
    ctx.check("nothing Halo-side fits: no chosen change", p["chosen"] is None)


@test
def test_a_server_at_f16_gets_the_q8_0_line_and_the_twin(ctx: Ctx):
    p = _plan(card(kv="f16"))
    kv = next(o for o in p["options"] if o["kind"] == "kv-q8_0")
    ctx.check(f"the exact env line and its cost, got {kv['server_hint']}",
              kv["server_hint"]["line"] == "OLLAMA_KV_CACHE_TYPE=q8_0" and "precision" in kv["server_hint"]["cost"]
              and kv["changes"] == [])
    twin = [o for o in p["options"] if o["kind"] == "twin"]
    ctx.check(f"a tuned twin where --fit spills but every layer fits, got {[o['says'] for o in twin]}",
              twin and twin[0]["server_hint"]["line"].startswith("halo ollama tune "))


@test
def test_the_macs_unified_memory(ctx: Ctx):
    """A Mac: the GPU's share of unified memory (27 GiB of 36) is the
    budget, Metal keeps 512 MiB; two models fit with a window each."""
    mac = card(total_mib=36864, available_mib=27648, unified=True, kv="f16")
    asked = [{"model": "qwen3.5:9b", "window": 32768, "max_prompt": 9000, "calls": 5},
             {"model": "qwen3-coder:30b", "window": 32768, "max_prompt": 9000, "calls": 2}]
    from halo_harness.ollama_steward.fit import plan
    p = plan(mac, asked, rows(), host_name="mac")
    ctx.check(f"the budget is the GPU's share, got {p['budget']['budget'] / GIB:.0f} GiB, metal {p['budget']['metal']}",
              p["budget"]["budget"] == 27 * GIB and p["budget"]["metal"])
    chosen = p["options"][p["chosen"]]
    ctx.check(f"a window per model, both over their largest prompt, got {chosen}",
              chosen["kind"] == "windows" and all(c["to"] >= 16384 for c in chosen["changes"]))
    from halo_harness.ollama_steward.fit import _together
    trial = [{**a, "row": rows()[a["model"]], "window": next((c["to"] for c in chosen["changes"]
                                                             if c["key"] == f"mac|{a['model']}"), a["window"])}
             for a in asked]
    ctx.check("and they do fit at those windows", _together(p["budget"], trial) <= p["budget"]["budget"])


@test
def test_the_plan_from_the_ledger_with_the_macs_lines(ctx: Ctx):
    """`halo ollama steward plan`: the models the halos ask for on the PC,
    the Mac's forwarded lines included, planned against the card."""
    from halo_harness.ollama_steward import cli_steward
    with Home():
        from halo_harness.ollama_steward.ledger import append_lines
        from halo_harness.config.paths import bridge_home
        append_lines(bridge_home(), [line(model="qwen3-coder:30b", num_ctx_sent=65536) for _ in range(3)]
                     + [line(num_ctx_sent=65536, session="m1", **{"from": "mac@book"}) for _ in range(5)])
        saved = cli_steward._readers
        cli_steward._readers = lambda: {"card_reader": lambda h: card(), "catalog_reader": lambda h: {"models": list(rows().values())}}
        try:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                cli_steward.cmd_ollama_steward(["plan", "--json"])
            plans = json.loads(out.getvalue())
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                cli_steward.cmd_ollama_steward(["plan"])
        finally:
            cli_steward._readers = saved
        models = [m["model"] for m in plans[0]["models"]]
        ctx.check(f"both models planned, the Mac's (more calls) first, got {models}",
                  models == ["qwen3.8:27b", "qwen3-coder:30b"])
        ctx.check(f"the lines say the plan, got {out.getvalue()!r}", "one-at-a-time" in out.getvalue()
                  and "you lose" in out.getvalue())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
