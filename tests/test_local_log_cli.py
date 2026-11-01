"""tests.test_local_log_cli -- Halo 3.3.8.0 R2: a local server's log from the terminal (halo_harness/local_log_cli.py):
`halo local log <server> [-n] [--kind] [--follow]` by name, id, port or model, `halo local events <server>` with the
kinds its runtime never prints, `halo ollama crashes` across runtimes, and `halo doctor --local`'s line per server
(doctor_local_servers.py). Fixture logs under a scratch home (tests/helpers/servers_seed.py); no server runs.
Run: python -m tests.test_local_log_cli
"""
from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
ensure_default_provider_credentials()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.servers_seed import LLAMA_CRASH, Home  # noqa: E402

test, TESTS = new_registry()


def _run(fn, argv) -> "tuple[int, str, str]":
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = fn(argv)
    return rc, out.getvalue(), err.getvalue()


def _local(argv):
    from halo_harness.local_cli import cmd_local
    return _run(cmd_local, argv)


@test
def test_the_log_by_name_id_port_and_model(ctx: Ctx):
    with Home(lms=False) as h:
        for key in ("llama-8080", "8080", "qwen3-8b"):
            rc, out, _e = _local(["log", key, "-n", "5"])
            ctx.check(f"{key}: the header names the path, the server and its state, got {out!r}", rc == 0
                      and out.splitlines()[0].startswith(f"# {h.llama_log} -- 'llama-8080' (llama-server):")
                      and out.count("\n") == 6)
        rc, out, _e = _local(["log", "llama-8080", "-n", "400", "--kind", "truncation"])
        ctx.check(f"--kind truncation: the cut lines only, got {out!r}", rc == 0 and "input truncated" in out
                  and "load_tensors" not in out and all(x.startswith(("#", "[truncation")) for x in out.splitlines()))
        rc, out, _e = _local(["log", "mac-mlx", "-n", "3"])
        ctx.check(f"a manual entry's log path, got {out!r}", rc == 0 and str(h.mlx_log) in out and "(mlx)" in out)
        rc, _out, err = _local(["log", "nobody"])
        ctx.check(f"an unknown server, said, got {err!r}", rc == 1 and "no local server named 'nobody'" in err)


@test
def test_follow_prints_what_arrives(ctx: Ctx):
    from halo_harness import local_log_cli as L
    with Home(lms=False, mlx=False) as h:
        L.SEAMS.update(rounds=1, sleep=lambda _s: h.append(h.llama_log, "slot update_slots: id  0 | task 9 | context "
                                                                        "shift, n_keep = 0, n_left = 8190, n_discard = 4095\n"))
        try:
            rc, out, _e = _local(["log", "llama-8080", "-n", "3", "--follow"])
        finally:
            L.SEAMS.clear()
        ctx.check(f"the appended line, once, got {out!r}", rc == 0 and out.count("context shift") == 1
                  and out.rstrip().endswith("n_discard = 4095"))


@test
def test_a_hand_started_server_says_why_its_log_is_not_read(ctx: Ctx):
    extra = {"huggingface": {"local_servers": [{"name": "hand", "url": "http://127.0.0.1:8090/v1"}]}}
    with Home(llama=False, lms=False, mlx=False, extra=extra):
        rc, out, _e = _local(["log", "hand"])
        ctx.check(f"the status line and the why, got {out!r}", rc == 1 and "unreadable" in out
                  and "start it with `halo local serve` or set `log`" in out)


@test
def test_events_and_the_kinds_never_printed(ctx: Ctx):
    with Home(llama=False, lms=False) as h:
        rc, out, _e = _local(["events", "mac-mlx", "--from-start"])
        ctx.check(f"mlx's events, got {out!r}", rc == 0 and "gpu-memory" in out and "http-500" in out)
        ctx.check("the kinds its log never says", "its log never says: prompt-trimmed" in out and "cpu-spill" in out)
        rc, out, _e = _local(["events", "mac-mlx", "--kind", "http-500", "--json"])
        ctx.check(f"--kind --json, got {out!r}", rc == 0 and out.strip() and all('"http-500"' in x for x in out.splitlines()))


@test
def test_crashes_across_runtimes_and_the_doctor_lines(ctx: Ctx):
    from halo_harness.doctor_local_servers import server_steps
    from halo_harness.ollama_cli import cmd_ollama
    from halo_harness.ollama_steward.server_log_hf import scan
    extra = {"huggingface": {"local_servers": [{"name": "hand", "url": "http://127.0.0.1:8090/v1"}]}}
    with Home(lms=False, mlx=False, pid=None, extra={}) as h:
        s = h.server("llama-8080")
        scan(h.state, s, from_start=True)
        h.append(h.llama_log, LLAMA_CRASH)
        scan(h.state, s)
        rc, out, _e = _run(cmd_ollama, ["crashes"])
        ctx.check(f"a llama-server crash with its runtime, got {out!r}", rc == 0 and out.startswith("llama-8080 [llama-server] qwen3-8b: crashed here"))
        rc, out, _e = _run(cmd_ollama, ["crashes", "--why"])
        ctx.check(f"--why: Halo's launch command, got {out!r}", "the load command: /opt/llama/llama-server" in out)
    with Home(lms=False, mlx=False, pid=None, extra=extra) as h:
        steps = {s["step"]: s for s in server_steps(h.state)}
        ctx.check(f"one line per server, got {sorted(steps)}", sorted(steps) == ["server log hand", "server log llama-8080"])
        ctx.check(f"a readable one is OK with its state, got {steps['server log llama-8080']}", steps["server log llama-8080"]
                  .get("tag") is None and "server log" in steps["server log llama-8080"]["reason"])
        hand = steps["server log hand"]
        ctx.check(f"an unreadable one is a WARN with how, got {hand}", hand["tag"] == "WARN" and hand["ok"]
                  and "set `log`" in hand["reason"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
