"""tests.test_models_test_probe -- Halo 3.0.7.0 round R1: the model probe
("Test this model"): model_probe.probe_model through the print-mode
subprocess seam (`subprocess.run`, stubbed -- no network, no `halo -p`
child), its result shape, the failure lines (exit code, stderr, timeout,
empty reply, no ref), the cost line from a seeded catalog, `halo models
test <ref>` (exit 0 / 1) and Studio's `POST /api/models/test`.

Run: python -m tests.test_models_test_probe
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402

ensure_default_provider_credentials()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


class _Stub:
    """Scratch home with a seeded models.json, and `subprocess.run` replaced."""

    def __init__(self, behaviour):
        self.behaviour, self.calls = behaviour, []

    def __enter__(self):
        self._saved_env = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
        home = Path(tempfile.mkdtemp(prefix="probe-"))
        os.environ["BRIDGE_TEST_HOME"] = str(home)
        os.environ["BRIDGE_STATE_DIR"] = str(home / ".halo")
        self.state_dir = home / ".halo"
        self.state_dir.mkdir(parents=True)
        (self.state_dir / "models.json").write_text(json.dumps(
            {"vendor/priced": {"price_in_per_m": 0.60, "price_out_per_m": 2.40}}), encoding="utf-8")
        self._real_run = subprocess.run

        def fake_run(argv, **kw):
            self.calls.append((list(argv), kw))
            return self.behaviour(argv, kw)
        subprocess.run = fake_run
        return self

    def __exit__(self, *exc):
        subprocess.run = self._real_run
        for k, v in self._saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _done(rc=0, out="", err=""):
    return lambda argv, kw: subprocess.CompletedProcess(argv, rc, out, err)


@test
def test_an_answer_is_ok_with_latency_and_the_cost_line(ctx: Ctx):
    from halo_harness.model_probe import PROBE_PROMPT, probe_model
    with _Stub(_done(0, "ok\n")) as s:
        r = probe_model("or:vendor/priced", state_dir=s.state_dir)
        ctx.check(f"the result shape, got {r}", set(r) == {"ok", "latency_ms", "error", "cost_line", "ref", "reply"})
        ctx.check("ok, no error, the ref echoed", r["ok"] is True and r["error"] == "" and r["ref"] == "or:vendor/priced"
                  and r["reply"] == "ok" and isinstance(r["latency_ms"], int) and r["latency_ms"] >= 0)
        ctx.check(f"the cost line comes from the catalog's prices, got {r['cost_line']!r}",
                  "~$0.0011" in r["cost_line"] and "600 in / 300 out" in r["cost_line"])
        argv, kw = s.calls[0]
        ctx.check(f"the print-mode path with the one-word prompt, got {argv}",
                  argv[1:] == ["-m", "halo_harness", "-p", PROBE_PROMPT, "--model", "or:vendor/priced", "--max-turns", "1"]
                  and PROBE_PROMPT == "Reply with the single word ok")
        ctx.check(f"20 s timeout, utf-8 decoding, got {kw}", kw.get("timeout") == 20.0 and kw.get("encoding") == "utf-8"
                  and kw.get("capture_output") is True)


@test
def test_each_failure_names_its_error_and_never_raises(ctx: Ctx):
    from halo_harness.model_probe import probe_model
    with _Stub(_done(1, "", "starting...\nerror: 404 No endpoints found for vendor/gone\n")):
        r = probe_model("or:vendor/gone")
        ctx.check(f"a failed call's last stderr line, got {r}", r["ok"] is False and r["error"] == "error: 404 No endpoints found for vendor/gone")
        ctx.check("an unpriced ref says cost unknown", "cost unknown" in r["cost_line"])
    with _Stub(_done(3, "", "")):
        ctx.check("a silent failure names the exit code", probe_model("or:vendor/x")["error"] == "exit code 3")
    with _Stub(_done(0, "   \n", "")):
        r = probe_model("or:vendor/x")
        ctx.check(f"an empty reply is not ok, got {r}", r["ok"] is False and "empty reply" in r["error"])

    def slow(argv, kw):
        raise subprocess.TimeoutExpired(argv, kw.get("timeout"))
    with _Stub(slow):
        r = probe_model("or:vendor/slow")
        ctx.check(f"a timeout says so, got {r['error']!r}", r["ok"] is False and r["error"] == "no reply within 20 s")

    def boom(argv, kw):
        raise OSError("no such interpreter")
    with _Stub(boom):
        r = probe_model("or:vendor/x")
        ctx.check(f"a launch failure is an error, not a raise, got {r['error']!r}",
                  r["ok"] is False and "could not start" in r["error"])
    with _Stub(_done(0, "ok")) as s:
        r = probe_model("  ")
        ctx.check("no ref is an error and spawns nothing", r["ok"] is False and r["error"] == "no model ref given" and not s.calls)


@test
def test_the_line_and_halo_models_test(ctx: Ctx):
    from halo_harness.catalog_cli import cmd_models
    from halo_harness.model_probe import probe_line
    ok = probe_line({"ok": True, "latency_ms": 812, "ref": "or:v/m", "reply": "ok", "cost_line": "or:v/m: ~$0.0011 estimated"})
    ctx.check(f"the ok line, got {ok!r}", ok == "or:v/m: ok in 812 ms ('ok') -- ~$0.0011 estimated")
    bad = probe_line({"ok": False, "latency_ms": 20000, "ref": "or:v/m", "error": "no reply within 20 s", "cost_line": ""})
    ctx.check(f"the failure line, got {bad!r}", bad == "or:v/m: failed after 20000 ms: no reply within 20 s")
    with _Stub(_done(0, "ok")):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = cmd_models(["test", "or:vendor/priced"])
        ctx.check(f"halo models test exits 0 and prints the line, got {rc} {buf.getvalue()!r}",
                  rc == 0 and buf.getvalue().startswith("or:vendor/priced: ok in "))
    with _Stub(_done(1, "", "error: 401 bad key")):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = cmd_models(["test", "or:vendor/priced", "--json"])
        data = json.loads(buf.getvalue())
        ctx.check(f"a failure exits 1, --json carries the result, got {rc} {data}",
                  rc == 1 and data["ok"] is False and data["error"] == "error: 401 bad key")


@test
def test_studio_post_models_test(ctx: Ctx):
    from halo_harness.studio.api import Request, dispatch
    with _Stub(_done(0, "ok")) as s:
        req = Request(method="POST", path="models/test", query={}, body={"ref": "or:vendor/priced"}, cwd=s.state_dir.parent,
                      state_dir=s.state_dir)
        status, body = dispatch(req)
        ctx.check(f"200 with the probe result, got {status} {body}", status == 200 and body["ok"] is True
                  and body["ref"] == "or:vendor/priced" and "~$0.0011" in body["cost_line"])
        req = Request(method="POST", path="models/test", query={}, body={}, cwd=s.state_dir.parent, state_dir=s.state_dir)
        status, body = dispatch(req)
        ctx.check(f"no ref is a 422, got {status} {body}", status == 422 and "ref" in body["error"])
        ctx.check("only the one probe spawned", len(s.calls) == 1)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="model probe tests"))
