"""tests.test_review3_g2b -- pins for the 3.0.2.0 review fix pass, round G2
(local catalog), second half:

  * item 63   a 400 that echoes the rejected value or the model id never
              produces a clamp to that same text
  * item 64   `halo local warm --keep-alive -1` sends a number; resident
              models are matched through the :latest-aware comparison
  * item 133  empty-model refs are refused; a non-string alias is an
              InvalidModelError
  * item 134  a non-numeric total_usage no longer breaks the balances path
  * item 135  the VRAM-aware role check budgets an Apple GPU by its usable
              share, not by all unified RAM
"""
from __future__ import annotations

import contextlib
import io
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once
from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.test_review3_g2 import env_patch, _tmp

ensure_scoped_state_dir_once()
ensure_default_provider_credentials()
test, TESTS = new_registry()
_GIB = 1024 ** 3


# ---- item 63 ---------------------------------------------------------------

@test
def test_g2_63_echoed_rejected_value_is_not_an_allowed_value(ctx: Ctx):
    from halo_harness.providers.learned_params import detect_param_rejection
    fix = detect_param_rejection(
        400, "Invalid value for 'reasoning_effort': 'xhigh'. Supported values: 'low', 'medium', 'high'",
        {"reasoning_effort": "xhigh"})
    ctx.check(f"clamps to the nearest listed effort, got {fix}", fix is not None and fix.action == "clamp"
              and fix.value == "high")
    fix = detect_param_rejection(400, "Invalid value for 'reasoning_effort': 'xhigh'.", {"reasoning_effort": "xhigh"})
    ctx.check(f"only the rejected value quoted -> drop, got {fix}", fix is not None and fix.action == "drop")


@test
def test_g2_63_model_id_in_quotes_is_not_a_replacement(ctx: Ctx):
    from halo_harness.providers.learned_params import detect_param_rejection
    fix = detect_param_rejection(
        400, "Invalid parameter 'temperature' for model 'databricks-gpt-5-mini'", {"temperature": 0.7})
    ctx.check(f"drops instead of clamping to the model name, got {fix}", fix is not None and fix.action == "drop")
    fix = detect_param_rejection(
        400, "temperature must be one of '0' or '1' for model 'databricks-gpt-5-mini'", {"temperature": 0.7})
    ctx.check(f"numbers are offered only numeric tokens, got {fix}", fix is not None and fix.action == "clamp"
              and fix.value == "1")


# ---- item 64 ---------------------------------------------------------------

def _warm(argv, **mock_kw):
    from halo_harness.local_cli import _cmd_warm
    from tests.helpers.mock_ollama import MockUpstream, send_json

    def one_shot(h, body):
        send_json(h, 200, {"message": {"role": "assistant", "content": "hi"}, "done": True})
    mock = MockUpstream(scenarios={"qwen3:30b": one_shot, "qwen3": one_shot}, **mock_kw).start()
    out = io.StringIO()
    try:
        with env_patch(OLLAMA_HOST=mock.base_url), contextlib.redirect_stdout(out):
            rc = _cmd_warm(argv)
        return rc, out.getvalue(), [r for r in mock.requests if r["path"].rstrip("/") == "/api/chat"]
    finally:
        mock.stop()


@test
def test_g2_64_keep_alive_minus_one_goes_out_as_a_number(ctx: Ctx):
    rc, text, chats = _warm(["qwen3:30b", "--keep-alive", "-1"], ps_response={"models": []})
    ctx.check(f"warmed, rc={rc} {text!r}", rc == 0 and len(chats) == 1)
    ka = chats[0]["body"].get("keep_alive")
    ctx.check(f"the wire value is the number -1, got {ka!r}", ka == -1 and isinstance(ka, int))
    _rc, _text, chats = _warm(["qwen3:30b", "--keep-alive", "24h"], ps_response={"models": []})
    ctx.check(f"a duration with a unit stays a string, got {chats[0]['body'].get('keep_alive')!r}",
              chats[0]["body"].get("keep_alive") == "24h")
    _rc, _text, chats = _warm(["qwen3:30b", "--keep-alive", "3600"], ps_response={"models": []})
    ctx.check("a bare integer string is a number", chats[0]["body"].get("keep_alive") == 3600)


@test
def test_g2_64_untagged_name_matches_its_latest_row_in_ps(ctx: Ctx):
    rc, text, chats = _warm(["qwen3"], ps_response={"models": [{"name": "qwen3:latest", "model": "qwen3:latest"}]})
    ctx.check(f"reported resident, got {text!r}", "already resident" in text and rc == 0)
    ctx.check(f"no load request was sent, got {len(chats)}", not chats)


# ---- item 133 --------------------------------------------------------------

@test
def test_g2_133_empty_model_refs_are_refused(ctx: Ctx):
    from halo_harness.model import InvalidModelError, parse_model_ref
    for raw in ("ol:", "or:", "ant:", "dbx:", "cc:", "ol:@lan"):
        try:
            parse_model_ref(raw)
            kind = "accepted"
        except InvalidModelError:
            kind = "refused"
        except Exception as e:  # noqa: BLE001
            kind = type(e).__name__
        ctx.check(f"{raw!r} is an InvalidModelError, got {kind}", kind == "refused")
    ctx.check("a real ref still parses", parse_model_ref("ol:qwen3:30b@lan").model == "qwen3:30b")


@test
def test_g2_133_malformed_alias_tables_do_not_crash(ctx: Ctx):
    from halo_harness.model import InvalidModelError, parse_model_ref
    try:
        parse_model_ref("fast", {"aliases": {"fast": {"model": "or:x"}}})
        kind = "accepted"
    except InvalidModelError:
        kind = "refused"
    except Exception as e:  # noqa: BLE001
        kind = type(e).__name__
    ctx.check(f"a dict alias target is an InvalidModelError, got {kind}", kind == "refused")
    ref = parse_model_ref("or:vendor/m", {"aliases": ["fast"]})
    ctx.check("a list-valued alias table is ignored", ref.model == "vendor/m")


# ---- item 134 --------------------------------------------------------------

@test
def test_g2_134_string_total_usage_does_not_break_the_refresh(ctx: Ctx):
    from halo_harness.providers import balances, experiential_account
    real = experiential_account.fetch_experiential_credits
    experiential_account.fetch_experiential_credits = lambda env=None: {"total_credits": 100, "total_usage": "12.5"}
    try:
        out = balances.refresh_all_balances(_tmp("g2-134-"), env={"EXPLABS_API_KEY": "k"})
    finally:
        experiential_account.fetch_experiential_credits = real
    ent = out["experiential"]
    ctx.check(f"ok with the numeric-string usage subtracted, got {ent}",
              ent["status"] == "ok" and abs(ent["amount"] - 87.5) < 1e-9)
    line = balances.format_balance_entry(
        "OpenRouter", {"status": "ok", "amount": 5.0, "kind": "credits", "total_credits": 10, "total_usage": ["x"]})
    ctx.check(f"a list total_usage formats as $0.00 used, got {line!r}", "$0.00 used" in line)


# ---- item 135 --------------------------------------------------------------

def _apple_card(wired_mb=None):
    from halo_harness.providers.ollama_hw import probe_apple_unified_memory

    def runner(argv, timeout):
        return str(32 * _GIB) if argv[-1] == "hw.memsize" else (str(wired_mb) if wired_mb else "0")
    return probe_apple_unified_memory(runner=runner)


def _fits(card, main_gib, cand_gib):
    from halo_harness.providers import ollama_hw
    from halo_harness.providers.ollama import OllamaHost
    from tests.helpers.mock_ollama import MockUpstream
    mock = MockUpstream(ps_response={"models": [
        {"model": "main", "name": "main", "size": main_gib * _GIB, "size_vram": main_gib * _GIB}]}).start()
    real = ollama_hw.get_local_gpu_memories
    ollama_hw.get_local_gpu_memories = lambda runner=None: [card]
    try:
        catalog = {"models": [{"model": "small", "name": "small", "size": cand_gib * _GIB}]}
        return ollama_hw._fits_beside_main_uncached(OllamaHost(name="m", url=mock.base_url), main_model="main",
                                                    candidate_model="small", catalog=catalog)
    finally:
        ollama_hw.get_local_gpu_memories = real
        mock.stop()


@test
def test_g2_135_apple_budget_is_the_usable_share_not_total_ram(ctx: Ctx):
    from halo_harness.providers.ollama_hw import GpuMemory, gpu_budget_bytes
    card = _apple_card()
    ctx.check(f"fake 32 GiB Mac, share ~22.4 GiB, got {card}", card.total_bytes == 32 * _GIB
              and abs(card.free_bytes - 0.7 * 32 * _GIB) < 1024)
    ctx.check("14 + 9 GiB exceeds the 22.4 GiB GPU share, so it does not fit", _fits(card, 14, 9) is False)
    ctx.check("14 + 6 GiB fits", _fits(card, 14, 6) is True)
    wired = _apple_card(wired_mb=28 * 1024)
    ctx.check("an explicit 28 GiB wired limit raises the budget, 23 GiB fits", _fits(wired, 14, 9) is True)
    nv = GpuMemory(vendor="nvidia", name="x", total_bytes=24 * _GIB, free_bytes=3 * _GIB)
    ctx.check("a discrete card is still budgeted by its total (live free is not the budget)",
              gpu_budget_bytes(nv) == 24 * _GIB and _fits(nv, 14, 9) is True)
    ctx.check("an Apple row with no usable share falls back to its total",
              gpu_budget_bytes(GpuMemory(vendor="apple", name=None, total_bytes=8 * _GIB, free_bytes=None)) == 8 * _GIB)
    ctx.check("nothing readable -> None",
              gpu_budget_bytes(GpuMemory(vendor="unknown", name=None, total_bytes=None, free_bytes=None)) is None)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
