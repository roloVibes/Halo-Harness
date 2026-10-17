"""halo_harness.model_probe -- Halo 3.0.7.0 round R1: "Test this model".

One one-token round trip on a model ref: the prompt "Reply with the single
word ok" through the same print-mode subprocess a bio's "Try it" smoke call
uses (`agents_doctor.print_mode_argv`: `halo -p ... --model <ref>
--max-turns 1`), so the probe exercises the route, the credentials and the
model id exactly as a real call would. 20 s timeout; never raises.

    probe_model(ref) -> {ok, latency_ms, error, cost_line, ref, reply}

Studio's `POST /api/models/test {ref}` (studio/models_api.py), `halo models
test <ref>` and the TUI lineup editor's `T` key all call it.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from typing import Optional

PROBE_PROMPT = "Reply with the single word ok"
PROBE_TIMEOUT_S = 20.0


def _last_line(text: str) -> str:
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    return lines[-1][:300] if lines else ""


def probe_model(ref: "Optional[str]", *, timeout: float = PROBE_TIMEOUT_S, state_dir=None) -> dict:
    """The probe result. `ok` is a non-empty reply from a clean exit;
    `error` says what went wrong otherwise (the call's own last stderr
    line, the exit code, the timeout); `cost_line` is the smoke cost
    estimate (`smoke_run.smoke_cost_line`) for the same ref."""
    from halo_harness.smoke_run import smoke_cost_line
    ref = str(ref or "").strip()
    try:
        cost = smoke_cost_line(ref, state_dir=state_dir)
    except Exception:
        cost = ""
    out = {"ok": False, "latency_ms": 0, "error": "", "cost_line": cost, "ref": ref, "reply": ""}
    if not ref:
        out["error"] = "no model ref given"
        return out
    from halo_harness.agents_doctor import print_mode_argv
    started = time.monotonic()
    try:
        proc = subprocess.run(print_mode_argv(ref, PROBE_PROMPT), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        out["latency_ms"] = int((time.monotonic() - started) * 1000)
        out["error"] = f"no reply within {timeout:g} s"
        return out
    except Exception as e:
        out["latency_ms"] = int((time.monotonic() - started) * 1000)
        out["error"] = f"the probe could not start: {type(e).__name__}: {e}"
        return out
    out["latency_ms"] = int((time.monotonic() - started) * 1000)
    reply = (proc.stdout or "").strip()
    out["reply"] = reply[:200]
    if proc.returncode == 0 and reply:
        out["ok"] = True
    elif proc.returncode != 0:
        out["error"] = _last_line(proc.stderr) or _last_line(proc.stdout) or f"exit code {proc.returncode}"
    else:
        out["error"] = _last_line(proc.stderr) or "the model sent back an empty reply"
    return out


def probe_line(result: dict) -> str:
    """One line: `<ref>: ok in 812 ms ("ok") -- <cost>` or `<ref>: failed
    after 20000 ms: <error> -- <cost>`."""
    ref = result.get("ref") or "(no ref)"
    cost = str(result.get("cost_line") or "")
    if cost.startswith(f"{ref}: "):
        cost = cost[len(ref) + 2:]
    tail = f" -- {cost}" if cost else ""
    if result.get("ok"):
        return f"{ref}: ok in {result.get('latency_ms', 0)} ms ({str(result.get('reply') or '')[:40]!r}){tail}"
    return f"{ref}: failed after {result.get('latency_ms', 0)} ms: {result.get('error') or 'no reply'}{tail}"


def cmd_models_test(argv: list) -> int:
    """`halo models test <ref> [--json] [--timeout S]`: exit 0 when the model answered, 1 when not."""
    p = argparse.ArgumentParser(prog="halo models test",
                                description="Send a one-token probe to a model ref and print ok or the error.")
    p.add_argument("ref", help="the model ref, e.g. or:vendor/model or ol:qwen3:8b")
    p.add_argument("--json", action="store_true", help="print the result as JSON")
    p.add_argument("--timeout", type=float, default=PROBE_TIMEOUT_S, help="seconds to wait (default 20)")
    a = p.parse_args(argv)
    result = probe_model(a.ref, timeout=a.timeout)
    print(json.dumps(result, indent=2) if a.json else probe_line(result))
    sys.stdout.flush()
    return 0 if result["ok"] else 1
