"""tests.test_steward_rules -- Halo 3.3.4.0 R3: every rule of the steward
(ollama_steward/rules*.py) on fixture ledgers, events and cards: the
finding, its evidence, its proposal and the cap guard; the PC's case (a log
and no ledger); one proposal per profile field; `halo ollama steward
findings`. In-process, a fresh home, background reads off: no server.
Run: python -m tests.test_steward_rules
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
from tests.helpers.steward_seed import Home, card, event, line, rows  # noqa: E402

test, TESTS = new_registry()


def _found(home, **kw) -> list:
    from halo_harness.ollama_steward.rules import findings
    return findings(home.state, **kw)


def _one(found, rule) -> dict:
    hits = [f for f in found if f["rule"] == rule]
    return hits[0] if hits else {}


@test
def test_a_window_too_small_is_raised_toward_the_learned_cap(ctx: Ctx):
    with Home() as h:
        h.cap("qwen3.8:27b", 65536)
        h.calls(*[line(prompt_eval_count=p) for p in (30500, 31000, 29800, 30900, 31200)],
                line(trimmed=True, prompt_eval_count=12000), line(done_reason="length", prompt_eval_count=32000))
        f = _one(_found(h), "window-small")
        ctx.check(f"a finding with the numbers, got {f.get('finding')}", f.get("evidence", {}).get("numbers", {})
                  .get("trims") == 1 and f["evidence"]["numbers"]["cuts"] == 1)
        ctx.check(f"the calls named by their at, got {f['evidence']['calls']}", len(f["evidence"]["calls"]) == 2)
        p = f.get("proposal") or {}
        ctx.check(f"num_ctx raised to the learned cap 65,536, got {p}", p.get("field") == "num_ctx" and p.get("to") == 65536)
        ctx.check("the key names the host here and the model", f["key"] == "pc|qwen3.8:27b")


@test
def test_the_cap_guard_and_the_tuned_twin(ctx: Ctx):
    with Home() as h:
        h.cap("qwen3.8:27b", 49152)
        h.calls(*[line(prompt_eval_count=31000) for _ in range(5)])
        f = _one(_found(h), "window-small")
        ctx.check(f"never above the measured cap: 49,152, got {f.get('proposal')}", (f.get("proposal") or {}).get("to") == 49152)
    with Home() as h:
        h.cap("qwen3.8:27b", 32768)
        h.calls(*[line(prompt_eval_count=31000) for _ in range(5)])
        f = _one(_found(h), "window-small")
        hint = f.get("server_hint") or {}
        ctx.check(f"at the cap: no profile change, the tuned twin offered, got {f.get('proposal')}, {hint}",
                  f.get("proposal") is None and hint.get("line") == "halo ollama tune qwen3.8:27b --host pc")
    with Home() as h:
        h.calls(*[line(prompt_eval_count=31000) for _ in range(5)])
        f = _one(_found(h), "window-small")
        ctx.check("no cap measured: calibrate is the line", (f.get("server_hint") or {}).get("line", "")
                  .startswith("halo ollama calibrate qwen3.8:27b"))


@test
def test_a_small_window_asked_for_names_the_kind_and_the_source(ctx: Ctx):
    with Home() as h:
        h.calls(line(num_ctx_sent=4096, trimmed=True, prompt_eval_count=2050, window_source="learned cap"),
                line(num_ctx_sent=8192, trimmed=True, kind="compaction", prompt_eval_count=4098,
                     window_source="remote default"))
        h.events(event("prompt-trimmed", window_sent=8192, limit=4098, prompt=11000))
        f = _one(_found(h), "window-asked-small")
        ctx.check(f"its own finding, error, got {f.get('severity')} {f.get('finding')}",
                  f.get("severity") == "error" and "a small window was asked for" in f.get("finding", ""))
        ctx.check(f"the kinds and the sources, got {f.get('kinds')} {f.get('sources')}",
                  f.get("kinds") == ["compaction", "turn"] and f.get("sources") == ["learned cap", "remote default"])
        ctx.check(f"the server's line is evidence too, got {f['evidence']['events']}", len(f["evidence"]["events"]) == 1)


@test
def test_the_pcs_case_a_log_and_no_ledger(ctx: Ctx):
    """What the PC has today: events from its server log, no ledger line."""
    with Home(hosts=[{"name": "default", "url": "http://127.0.0.1:11434"}]) as h:
        h.events(event("prompt-trimmed", window_sent=4096, limit=2050, prompt=9000),
                 event("reply-cut", n_tokens=65535), event("cpu-spill", model="qwen3-coder:30b"), host="default")
        found = _found(h)
        rules = sorted(f["rule"] for f in found)
        ctx.check(f"the small window asked, the cut replies, the spill, got {rules}",
                  rules == ["cpu-spill", "reply-cut", "window-asked-small"])
        spill = _one(found, "cpu-spill")
        ctx.check(f"the spill: the tuned twin's line, no smaller window, got {spill.get('server_hint')}",
                  spill.get("proposal") is None and spill["server_hint"]["line"].startswith("halo ollama tune qwen3-coder:30b"))
        ctx.check("a cut known only from the server's lines says so",
                  "the server's own lines" in _one(found, "reply-cut").get("finding", ""))


@test
def test_a_window_too_large_is_lowered_never_under_the_largest_prompt(ctx: Ctx):
    with Home() as h:
        h.calls(*[line(num_ctx_sent=131072, prompt_eval_count=p, load_ms=9000.0) for p in (3000, 3500, 2800, 4200, 3900)])
        h.events(event("cpu-spill", size=24 * 2 ** 30, size_vram=20 * 2 ** 30))
        f = _one(_found(h), "window-large")
        p = f.get("proposal") or {}
        ctx.check(f"lowered to 16,384 (4,200 x 1.25 + the reply, a power of two), got {p}", p.get("to") == 16384)
        ctx.check("the spill is evidence", f["evidence"]["numbers"]["spills"] == 1)


@test
def test_cut_replies_get_a_reply_reserve(ctx: Ctx):
    with Home() as h:
        h.calls(line(done_reason="length", prompt_eval_count=31800, eval_count=900),
                line(session="s2"), line(kind="calibrate", done_reason="length", eval_count=1))
        f = _one(_found(h), "reply-cut")
        p = f.get("proposal") or {}
        ctx.check(f"num_predict 4,096 (a calibration load is not a cut), got {p} {f.get('finding')}",
                  p.get("field") == "num_predict" and p.get("to") == 4096 and f["evidence"]["numbers"]["cuts"] == 1)
        ctx.check("one at the window's end", f["evidence"]["numbers"]["at_window_end"] == 1)


@test
def test_a_session_past_80_percent_without_compacting(ctx: Ctx):
    with Home() as h:
        h.calls(*[line(prompt_eval_count=p, ago=900 - i) for i, p in enumerate((20000, 27000, 29000, 31500))])
        f = _one(_found(h), "no-compaction")
        ctx.check(f"error, the session, compact earlier, got {f.get('finding')} {f.get('proposal')}",
                  f.get("severity") == "error" and (f.get("proposal") or {}).get("to") == 0.7
                  and f["evidence"]["numbers"]["calls_past"] == 3)
    with Home() as h:
        h.calls(line(prompt_eval_count=29000, ago=900), line(kind="compaction", status=500, ago=800))
        found = _found(h)
        ctx.check(f"a compaction that ran and failed is said apart, got {[f['rule'] for f in found]}",
                  _one(found, "compaction-failed") and not _one(found, "no-compaction"))
    with Home() as h:
        h.calls(line(prompt_eval_count=29000, ago=900), line(kind="compaction", ago=800), line(prompt_eval_count=9000))
        ctx.check("compacted: nothing to say", not _one(_found(h), "no-compaction"))


@test
def test_a_truncated_reply_resent_is_flagged(ctx: Ctx):
    """The Mac's 00:10 case: 64,829 + the cut reply, then the same prompt
    sent again and cut again."""
    with Home() as h:
        h.calls(line(num_ctx_sent=65536, prompt_eval_count=64829, eval_count=706, done_reason="length", ago=700),
                line(num_ctx_sent=65536, prompt_eval_count=64829, eval_count=706, done_reason="length", ago=690,
                     retry=1))
        found = _found(h)
        f = _one(found, "cut-resent")
        ctx.check(f"error: sent again unchanged and cut again, got {f.get('finding')}",
                  f.get("severity") == "error" and "sent again unchanged" in f.get("finding", ""))
        props = [x for x in found if (x.get("proposal") or {}).get("field") == "num_predict"]
        ctx.check(f"one num_predict proposal between the cut and the resend, got {[x['rule'] for x in props]}",
                  len(props) == 1 and props[0]["rule"] == "cut-resent")
    with Home() as h:
        h.calls(line(prompt_eval_count=20000, eval_count=3000, done_reason="length", ago=700),
                line(prompt_eval_count=23100, ago=690))
        ctx.check("the next call carrying the cut text", "carried" in _one(_found(h), "cut-resent").get("finding", ""))


@test
def test_a_slow_box(ctx: Ctx):
    with Home() as h:
        h.calls(*[line(eval_tok_s=2.0, load_ms=8000.0) for _ in range(4)])
        f = _one(_found(h, catalogs={"pc": rows()}), "slow-box")
        ctx.check(f"slow under 6 tok/s for a 27B, keep_alive longer, got {f.get('finding')} {f.get('proposal')}",
                  f.get("slow") is True and f["evidence"]["numbers"]["threshold"] == 6.0
                  and (f.get("proposal") or {}).get("to") == "30m")
        h.calls(*[line(model="qwen3.5:9b", eval_tok_s=40.0) for _ in range(4)])
        ctx.check("a fast one is not", not [x for x in _found(h) if x["rule"] == "slow-box" and x["model"] == "qwen3.5:9b"])


@test
def test_two_models_thrashing_one_card_get_the_fit_plan(ctx: Ctx):
    with Home() as h:
        h.calls(*[line(model="qwen3.8:27b", num_ctx_sent=65536, load_ms=12000.0, ago=900 - i) for i in range(4)],
                *[line(model="qwen3-coder:30b", num_ctx_sent=65536, load_ms=11000.0, ago=800 - i, session="s2")
                  for i in range(3)])
        h.events(*[event("loaded", model=m, ago=900 - 10 * i)
                   for i, m in enumerate(["qwen3.8:27b", "qwen3-coder:30b"] * 3)])
        f = _one(_found(h, cards={"pc": card()}, catalogs={"pc": rows()}), "thrash")
        ctx.check(f"a thrash finding with the plan, got {f.get('finding')}", f.get("plan") and f["severity"] == "error")
        kinds = [o["kind"] for o in f["plan"]["options"]]
        ctx.check(f"one at a time is the Halo-side answer (both cannot fit), got {kinds} {f.get('proposal')}",
                  "one-at-a-time" in kinds and (f.get("proposal") or {}).get("field") == "keep_alive")
        ctx.check(f"what you lose is said, got {f['proposal']['why']}", "you lose" in f["proposal"]["why"])


@test
def test_two_windows_for_one_model_become_one(ctx: Ctx):
    with Home() as h:
        h.calls(*[line(num_ctx_sent=65536, prompt_eval_count=20000) for _ in range(3)],
                *[line(num_ctx_sent=8192, prompt_eval_count=6000, session="m1", **{"from": "mac@book"})
                  for _ in range(3)])
        h.events(event("reloaded", context_length=8192, previous_context_length=65536))
        f = _one(_found(h), "two-windows")
        ctx.check(f"one window for both: 65,536, got {f.get('proposal')} {f.get('finding')}",
                  (f.get("proposal") or {}).get("to") == 65536 and "mac@book" in f.get("finding", ""))


@test
def test_halo_ollama_steward_findings(ctx: Ctx):
    from halo_harness.ollama_steward.cli_steward import cmd_ollama_steward
    with Home() as h:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cmd_ollama_steward(["findings"])
        ctx.check(f"nothing yet: one line, got {out.getvalue()!r}", code == 0 and "no findings" in out.getvalue())
        h.cap("qwen3.8:27b", 65536)
        h.calls(*[line(prompt_eval_count=31000) for _ in range(5)])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cmd_ollama_steward(["findings", "--host", "pc"])
        text = out.getvalue()
        ctx.check(f"the finding, the change, the evidence, got {text!r}",
                  "window-small" in text and "change: num_ctx None -> 65536" in text and "evidence:" in text)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cmd_ollama_steward(["findings", "--json"])
        data = json.loads(out.getvalue())
        ctx.check("--json: the findings' shape", data and {"id", "rule", "host", "model", "severity", "finding",
                                                          "evidence", "proposal", "server_hint"} <= set(data[0]))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
