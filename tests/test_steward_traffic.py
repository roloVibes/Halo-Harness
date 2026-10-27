"""tests.test_steward_traffic -- Halo 3.3.4.0 R2: the two commands.

1. `rollup` per host and model: calls, compaction calls, p50 / p95 prompt
   against the window sent and its share, trims, cuts, 499 / 500 /
   timeouts, reloads inferred from `load_ms`, the eval rate, calls per
   machine; a member's line naming this machine by its LAN address joins
   the local host's row;
2. `halo ollama traffic`: the empty answer, the lines (the host's card line
   above its models), `--model`, `--json`, a bad `--since`;
3. `halo ollama events`: the first read starts at the end (the empty
   answer), `--from-start` reads a fixture log from its top, `--kind`, an
   unknown `--host`. The fixture log is written only inside the test's own
   temporary home (checked before the write), never at a real log path.
In-process, a fresh home, background reads off: no server, no subprocess.
Run: python -m tests.test_steward_traffic
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
FIX = Path(__file__).resolve().parent / "fixtures" / "ollama_steward"
PC = {"name": "pc", "url": "http://192.0.2.10:11434"}


class _Env:
    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "OLLAMA_HOST",
                                                      "BRIDGE_TEST_NO_BACKGROUND_NET")}
        self.root = Path(tempfile.mkdtemp(prefix="l2_cli-")).resolve()
        os.environ.update(BRIDGE_TEST_HOME=str(self.root), BRIDGE_STATE_DIR=str(self.root / ".halo"),
                          OLLAMA_HOST="http://127.0.0.1:11434", BRIDGE_TEST_NO_BACKGROUND_NET="1")
        self.state = self.root / ".halo"
        self.state.mkdir(parents=True)
        return self

    def __exit__(self, *exc):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _cli(fn, *argv) -> "tuple[int, str]":
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = fn(list(argv))
    return code, out.getvalue()


def _line(**kw) -> dict:
    from halo_harness.ollama_steward.ledger import blank_line
    base = {"host": PC, "model": "qwen3.8:27b", "status": 200, "num_ctx_sent": 32768, "prompt_eval_count": 10000,
            "eval_tok_s": 60.0, "load_ms": 50.0, "from": None}
    return blank_line(**{**base, **kw})


@test
def test_the_rollup_per_host_and_model(ctx: Ctx):
    from halo_harness.fleet import ollama_share
    from halo_harness.ollama_steward.traffic import format_rollups, rollup
    from halo_harness.providers.ollama import OllamaHost
    lines = [_line(prompt_eval_count=n) for n in (8000, 10000, 12000, 30000)]
    lines += [_line(kind="compaction", prompt_eval_count=4000, eval_tok_s=40.0),
              _line(trimmed=True, status=500, prompt_eval_count=None, error="no user query found in messages"),
              _line(done_reason="length", prompt_eval_count=31000, load_ms=14000.0),
              _line(status=499, prompt_eval_count=None), _line(status="timeout", prompt_eval_count=None),
              _line(host={"name": "lan", "url": "http://192.0.2.10:11434"}, **{"from": "mac@book"})]
    lines.append(_line(model="small:1b", host={"name": "default", "url": "http://127.0.0.1:11434"}))
    saved = dict(ollama_share._OWN)
    ollama_share._OWN.update(at=1e18, set={"127.0.0.1", "localhost", "192.0.2.10"})
    try:
        hosts = [OllamaHost(name="default", url="http://127.0.0.1:11434")]
        rows = rollup(lines, hosts)
    finally:
        ollama_share._OWN.clear()
        ollama_share._OWN.update(saved)
    ctx.check(f"one row per host and model, every call to this machine under 'default', got "
              f"{[(r['host'], r['model'], r['calls']) for r in rows]}",
              [(r["host"], r["model"], r["calls"]) for r in rows] == [("default", "qwen3.8:27b", 10),
                                                                      ("default", "small:1b", 1)])
    r = rows[0]
    ctx.check(f"p50 / p95 of the answered prompts against the window, got {r['p50_prompt']} {r['p95_prompt']} "
              f"{r['p95_pct']}", r["p50_prompt"] == 10000 and r["window"] == 32768 and r["p95_pct"] is not None
              and 90 < r["p95_pct"] < 100)
    ctx.check("trims, cuts, 499, 500, timeouts, reloads, compaction",
              (r["trims"], r["cuts"], r["s499"], r["s500"], r["timeouts"], r["reloads"], r["compaction"])
              == (1, 1, 1, 1, 1, 1, 1))
    ctx.check(f"the eval rate's p50 and the calls per machine, got {r['eval_tok_s']} {r['machines']}",
              r["eval_tok_s"] == 60.0 and r["machines"] == {"this machine": 9, "mac@book": 1})
    text = format_rollups(rows, card=lambda h: "GPU 0: a card")
    ctx.check(f"the host's card line above its models, got {text}", text[0] == "'default': GPU 0: a card"
              and text[1].startswith("  qwen3.8:27b: 10 calls (1 compaction); prompt p50 10.0k / p95")
              and "of 32.8k" in text[1] and "from this machine 9, mac@book 1" in text[1])


@test
def test_halo_ollama_traffic(ctx: Ctx):
    from halo_harness.ollama_steward import ledger
    from halo_harness.ollama_steward.cli import cmd_ollama_traffic
    with _Env() as env:
        code, out = _cli(cmd_ollama_traffic)
        ctx.check(f"empty: the one line, got {out!r}", code == 0
                  and out.strip() == "no ledger yet: calls to default are recorded from 3.3.4.0 on")
        for n in (1000, 2000):
            ledger.record_call(env.state, _line(prompt_eval_count=n))
        ledger.record_call(env.state, _line(model="other:7b"))
        code, out = _cli(cmd_ollama_traffic, "--since", "1h")
        ctx.check(f"the host line, then one line per model, got {out!r}", code == 0
                  and out.splitlines()[0].startswith("'pc': ") and "qwen3.8:27b: 2 calls" in out
                  and "other:7b: 1 calls" in out)
        code, out = _cli(cmd_ollama_traffic, "--model", "other:7b", "--json")
        rows = json.loads(out)
        ctx.check(f"--model and --json, got {rows}", code == 0 and len(rows) == 1 and rows[0]["model"] == "other:7b"
                  and rows[0]["calls"] == 1)
        code, out = _cli(cmd_ollama_traffic, "--host", "elsewhere")
        ctx.check(f"--host with no calls: the empty line names it, got {out!r}",
                  "calls to elsewhere are recorded from 3.3.4.0 on" in out)
        code, out = _cli(cmd_ollama_traffic, "--since", "soon")
        ctx.check(f"a bad --since is exit 2 with the reason, got {code} {out!r}", code == 2 and "--since" in out)


def _fixture_log(env) -> Path:
    """The fixture at the path the CLI reads, which must be inside the test's own home."""
    from halo_harness.ollama_steward.hardware_readers import server_log_path
    target = server_log_path().resolve()
    if env.root not in target.parents:
        raise AssertionError(f"the server log path {target} is not inside the test home {env.root}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes((FIX / "every-rule.txt").read_bytes())
    return target


@test
def test_halo_ollama_events(ctx: Ctx):
    from halo_harness.ollama_steward.cli import cmd_ollama_events
    with _Env() as env:
        _fixture_log(env)
        code, out = _cli(cmd_ollama_events)
        ctx.check(f"the first read starts at the end: the empty answer, got {out!r}", code == 0
                  and "no events yet: default's server log is read from 3.3.4.0 on" in out)
        code, out = _cli(cmd_ollama_events, "--from-start", "--since", "3650d")
        ctx.check(f"--from-start: the fixture's events, newest last, got {out.splitlines()[:3]}", code == 0
                  and "prompt-trimmed [qwen3.8:27b]" in out and "cancel-task" in out
                  and out.strip().splitlines()[-1].split()[3] == "http-500")
        code, out = _cli(cmd_ollama_events, "--since", "3650d", "--kind", "client-gave-up", "--json")
        rows = [json.loads(x) for x in out.splitlines() if x.startswith("{")]
        ctx.check(f"--kind and --json, got {[r['kind'] for r in rows]}", code == 0 and [r["kind"] for r in rows]
                  == ["client-gave-up"] and rows[0]["host"] == "default" and rows[0]["notify"] is True)
        code, out = _cli(cmd_ollama_events, "--host", "nowhere")
        ctx.check(f"an unknown --host is exit 1, got {code}", code == 1 and "no configured host named" in out)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
