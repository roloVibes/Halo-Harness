"""tests.test_local_ollama_verbs -- Halo 3.6.0.0 R8: `halo local ps | warm | unload | pull | measure`
(halo_harness/local_ollama_cli.py) against two fake Ollama servers on loopback that count loads
(tests/helpers/mock_ollama_loads.LoadCountingOllama) and a third entry nobody answers. Nothing runs on the "far"
server but Ollama's API; never a real Ollama, never a real model.

Pinned: each verb's own --help, its --json form, one plain line on a failure (unreachable, unknown model), the exit
codes (0 done, 1 the server said no, 2 usage, 3 unreachable); `halo --help` names local and host; `halo local
--help` names the verbs; measure never steps above the host's max_ctx, the cold first load is one load, a slow step
above a safe window keeps the safe window, and it never runs twice for the same digest and server version.
Run: python -m tests.test_local_ollama_verbs
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
from tests.helpers.mock_ollama_loads import GB, LoadCountingOllama  # noqa: E402
from tests.helpers.mock_openai import free_port  # noqa: E402

REPO_DIR = Path(__file__).resolve().parent.parent
test, TESTS = new_registry()
TINY, BIG = "tiny:1b", "big:27b"


class Rig:
    """Two fakes (`gpu-box` with max_ctx 65,536, `laptop`) and `gone` (a loopback port nothing listens on), in a
    state dir of their own."""

    def __enter__(self):
        self.box = LoadCountingOllama({TINY: {"size_gb": 1.0}, BIG: {"size_gb": 16.6, "params": "27B"}}).start()
        self.lap = LoadCountingOllama({TINY: {"size_gb": 1.0}}).start()
        self.saved = os.environ.get("BRIDGE_STATE_DIR")
        self.state = tempfile.mkdtemp(prefix="r8-verbs-")
        os.environ["BRIDGE_STATE_DIR"] = self.state
        from halo_harness.providers.ollama import reset_catalog_cache, reset_ollama_version_cache
        reset_catalog_cache()
        reset_ollama_version_cache()
        Path(self.state, "config.json").write_text(json.dumps({"ollama": {"hosts": [
            {"name": "gpu-box", "url": self.box.base_url, "max_ctx": 65536, "default": True},
            {"name": "laptop", "url": self.lap.base_url},
            {"name": "gone", "url": f"http://127.0.0.1:{free_port()}"}]}}), encoding="utf-8")
        return self

    def __exit__(self, *exc):
        self.box.stop()
        self.lap.stop()
        if self.saved is None:
            os.environ.pop("BRIDGE_STATE_DIR", None)
        else:
            os.environ["BRIDGE_STATE_DIR"] = self.saved


def _cli(argv: list) -> "tuple[int, str, str]":
    from halo_harness.local_cli import cmd_local
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            rc = cmd_local(argv)
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 2
    return rc, out.getvalue(), err.getvalue()


@test
def test_every_verb_has_its_own_help_and_halo_help_names_local_and_host(ctx: Ctx):
    for verb in ("ps", "warm", "unload", "pull", "measure"):
        rc, out, _err = _cli([verb, "--help"])
        ctx.check(f"`halo local {verb} --help` is its own, got {rc} {out[:120]!r}",
                  rc == 0 and out.startswith(f"usage: halo local {verb}") and "exit codes" in out.lower())
    rc, out, _err = _cli(["--help"])
    ctx.check(f"`halo local --help` names the verbs, got {out[-600:]!r}",
              all(f"  {v} " in out for v in ("ps", "warm", "unload", "pull", "measure")))
    env = {**os.environ, "BRIDGE_TEST_HOME": tempfile.mkdtemp(prefix="r8-help-"), "BRIDGE_TEST_NO_BACKGROUND_NET": "1",
           "PYTHONPATH": str(REPO_DIR)}
    got = subprocess.run([sys.executable, "-m", "halo_harness", "--help"], env=env, cwd=str(REPO_DIR),
                         capture_output=True, text=True, timeout=120, encoding="utf-8", errors="replace")
    # 3.6.0.0 R16: the commands block is built from cli_commands' registry -- one `    <name>  <purpose>` row each
    block = got.stdout.split("Commands:", 1)[-1].splitlines()
    rows = {ln.split(None, 1)[0]: ln.split(None, 1)[1] for ln in block
            if ln.startswith("    ") and len(ln.split(None, 1)) == 2}
    ctx.check(f"`halo --help` exits 0 and has a row for local and one for host, got {got.returncode} {sorted(rows)}",
              got.returncode == 0 and "local" in rows and "host" in rows)
    ctx.check(f"the local row names its verbs, got {rows.get('local')!r}",
              all(v in rows.get("local", "") for v in ("ps", "warm", "unload", "pull", "measure")))


@test
def test_ps_lists_both_servers_and_says_which_one_did_not_answer(ctx: Ctx):
    with Rig() as r:
        r.box.preload(BIG, 32768)
        r.box.vram[BIG] = lambda n: (int(17.4 * GB), int(16.0 * GB))  # part of it on the CPU
        rc, out, _ = _cli(["ps"])
        ctx.check(f"exit 3: one server did not answer, got {rc}", rc == 3)
        ctx.check(f"gpu-box's model, its window, the card and how long it stays, got {out!r}",
                  "gpu-box (" in out and f"{BIG}  window 32,768" in out and "on the CPU" in out and "for ever" in out)
        ctx.check("laptop: nothing loaded", "laptop (" in out and "nothing loaded" in out)
        ctx.check("gone: one plain line", "gone (" in out and "did not answer" in out)
        rc, out, _ = _cli(["ps", "--host", "gpu-box", "--json"])
        got = json.loads(out)
        ctx.check(f"--json for one host, exit 0, got {rc}", rc == 0 and got["ok"]
                  and got["hosts"][0]["models"][0]["window"] == 32768)
        rc, _out, err = _cli(["ps", "--host", "nowhere"])
        ctx.check(f"an unknown host is a usage error (2) with one line, got {rc} {err!r}",
                  rc == 2 and "no Ollama host named 'nowhere'" in err)
        ctx.check("ps loads nothing", not r.box.loads and not r.lap.loads)


@test
def test_warm_loads_once_at_the_window_and_keeps_what_was_asked(ctx: Ctx):
    with Rig() as r:
        rc, out, _ = _cli(["warm", TINY, "--host", "gpu-box", "--window", "32768", "--keep", "forever"])
        ctx.check(f"warmed, exit 0, got {rc} {out!r}", rc == 0 and f"{TINY} loaded on gpu-box at 32,768" in out)
        ctx.check(f"one load at 32,768, kept for ever, got {r.box.loads} {r.box.keep_alives}",
                  [x["num_ctx"] for x in r.box.loads] == [32768] and [k["keep_alive"] for k in r.box.keep_alives] == [-1])
        rc, out, _ = _cli(["warm", TINY, "--host", "gpu-box"])
        ctx.check(f"warm again: already loaded, nothing sent, got {rc} {out!r}",
                  rc == 0 and "already loaded" in out and len(r.box.loads) == 1)
        rc, out, _ = _cli(["warm", TINY, "--host", "laptop", "--json"])
        got = json.loads(out)
        ctx.check(f"--json, the first-call window, no keep_alive sent, got {got}",
                  rc == 0 and got["models"][0]["window"] == 16384 and not r.lap.keep_alives)
        rc, _out, err = _cli(["warm", "nope:7b", "--host", "gpu-box"])
        ctx.check(f"a model the server lacks: exit 1, one line, got {rc} {err!r}",
                  rc == 1 and "gpu-box does not have nope:7b" in err)
        rc, _out, err = _cli(["warm", TINY, "--host", "gone"])
        ctx.check(f"an unreachable server: exit 3, one line, got {rc} {err!r}", rc == 3 and "did not answer" in err)


@test
def test_unload_takes_it_off_the_card_and_all_takes_everything(ctx: Ctx):
    with Rig() as r:
        r.box.preload(TINY, 16384)
        r.box.preload(BIG, 32768)
        rc, out, _ = _cli(["unload", TINY, "--host", "gpu-box"])
        ctx.check(f"unloaded, got {rc} {out!r}", rc == 0 and f"{TINY} unloaded on gpu-box" in out
                  and TINY not in r.box.resident)
        rc, out, _ = _cli(["unload", TINY, "--host", "gpu-box"])
        ctx.check(f"not loaded: nothing to do, exit 0, got {rc} {out!r}", rc == 0 and "not loaded" in out)
        rc, out, _ = _cli(["unload", "--all", "--json"])  # the default host
        got = json.loads(out)
        ctx.check(f"--all on the default host, got {got}", rc == 0 and not r.box.resident
                  and [m["model"] for m in got["models"]] == [BIG])
        rc, _out, err = _cli(["unload", "--host", "gpu-box"])
        ctx.check(f"no model and no --all: usage (2), got {rc} {err!r}", rc == 2)
        rc, _out, err = _cli(["unload", TINY, "--host", "gone"])
        ctx.check(f"unreachable: exit 3, got {rc} {err!r}", rc == 3 and "did not answer" in err)


@test
def test_pull_says_the_size_and_its_progress(ctx: Ctx):
    with Rig() as r:
        r.lap.pullable["new:8b"] = {"capabilities": ["completion"], "details": {"family": "qwen3"},
                                    "model_info": {"qwen3.context_length": 40960}}
        rc, out, _ = _cli(["pull", "new:8b", "--host", "laptop"])
        ctx.check(f"pulled, the size said first, got {rc} {out!r}",
                  rc == 0 and "5.0 GB to download" in out and "new:8b pulled on laptop" in out
                  and out.index("to download") < out.index("pulled on"))
        rc, _out, err = _cli(["pull", "nothing:1b", "--host", "laptop"])
        ctx.check(f"a name the registry lacks: exit 1, one line, got {rc} {err!r}",
                  rc == 1 and "could not pull nothing:1b" in err)
        rc, _out, err = _cli(["pull", "new:8b", "--host", "gone"])
        ctx.check(f"unreachable: exit 3, got {rc} {err!r}", rc == 3 and "did not answer" in err)


@test
def test_measure_stays_under_the_cap_keeps_what_it_learned_and_runs_once(ctx: Ctx):
    from halo_harness.providers import ollama_calibrate as C
    real_budget = C.load_budget_s
    C.load_budget_s = lambda size_gb, remote: 0.4  # a short step budget; the cold first load gets its own allowance
    try:
        with Rig() as r:
            # wholly on the card up to 32,768, part on the CPU above (a 24 GB card)
            r.box.vram[BIG] = lambda n: (int(16.6 * GB) + n * 100_000, int(16.6 * GB) + min(n, 32768) * 100_000)
            r.box.first_load_s = 1.0  # the cold load: longer than a step's budget, still a load
            rc, out, _ = _cli(["measure", BIG, "--host", "gpu-box"])
            asked = [c["num_ctx"] for c in r.box.calibrates]
            ctx.check(f"measured, exit 0, got {rc} {out!r}", rc == 0 and "32k fits" in out)
            ctx.check(f"never above the host's max_ctx (65,536), got {asked}", asked and max(asked) <= 65536)
            ctx.check(f"the cold first load is one load (no timeout and retry), got {asked}",
                      asked.count(asked[0]) == 1)
            before = len(r.box.calibrates)
            rc, out, _ = _cli(["measure", BIG, "--host", "gpu-box"])
            ctx.check(f"the same digest and server version: not again, got {rc} {out!r}",
                      rc == 0 and "measured already" in out and len(r.box.calibrates) == before)
            rc, out, _ = _cli(["measure", BIG, "--host", "gpu-box", "--again", "--json"])
            ctx.check(f"--again measures again, got {rc}", rc == 0 and len(r.box.calibrates) > before
                      and json.loads(out)["max_full_gpu_ctx"] == 32768)
        with Rig() as r:
            r.box.slow_at[65536] = 3.0  # a step above the safe window that never answers in its time
            rc, out, _ = _cli(["measure", TINY, "--host", "gpu-box", "--json"])
            got = json.loads(out)
            ctx.check(f"a slow step above a safe window keeps the safe window, got {rc} {got}",
                      rc == 0 and got.get("max_full_gpu_ctx") == 32768)
            rc, _out, err = _cli(["measure", "nope:7b", "--host", "gpu-box"])
            ctx.check(f"a model the server lacks: exit 1, got {rc} {err!r}", rc == 1 and "does not have" in err)
            rc, _out, err = _cli(["measure", TINY, "--host", "gone"])
            ctx.check(f"unreachable: exit 3, got {rc} {err!r}", rc == 3 and "did not answer" in err)
    finally:
        C.load_budget_s = real_budget


@test
def test_studio_cards_control_the_far_server_through_ollamas_api(ctx: Ctx):
    import time
    from halo_harness.studio.api import Request, dispatch
    from halo_harness.providers import ollama_calibrate as C
    real_budget = C.load_budget_s
    C.load_budget_s = lambda size_gb, remote: 0.4
    try:
        with Rig() as r:
            ask = lambda m, p, q=None, b=None: dispatch(Request(method=m, path=p, query=q or {}, body=b or {},  # noqa: E731
                                                                cwd=Path(r.state), state_dir=Path(r.state), server=None))
            code, got = ask("GET", "local/hosts", {"fresh": "1"})
            box = next((h for h in got.get("hosts") or [] if h["name"] == "gpu-box"), {})
            # (a loopback fake reads as served here; tests/test_local_api.py pins "Ollama's API" for another machine's)
            ctx.check(f"gpu-box's card: control from here, got {code} {box.get('controls')}",
                      code == 200 and (box.get("controls") or {}).get("ok") is True)
            code, got = ask("POST", "local/host/gpu-box/load", b={"model": TINY})
            ctx.check(f"Warm: one load at the first-call window (not max_ctx), got {code} {got.get('say')!r} {r.box.loads}",
                      code == 200 and [x["num_ctx"] for x in r.box.loads] == [16384] and not r.box.keep_alives)
            code, got = ask("POST", "local/host/gpu-box/measure", b={"model": TINY})
            ctx.check(f"Measure starts, got {code} {got}", code == 200 and got.get("running") is True)
            end, view = time.monotonic() + 30, {}
            while time.monotonic() < end:
                view = ask("GET", "local/host/gpu-box/measure", {"model": TINY})[1]
                if not view.get("running"):
                    break
                time.sleep(0.2)
            ctx.check(f"Measure ends with its line and its steps, got {view}",
                      view.get("ok") is True and "fits" in view.get("line", "") and view.get("lines"))
            ctx.check(f"never above max_ctx, got {[c['num_ctx'] for c in r.box.calibrates]}",
                      r.box.calibrates and max(c["num_ctx"] for c in r.box.calibrates) <= 65536)
            code, got = ask("POST", "local/host/gpu-box/unload", b={"model": TINY})
            ctx.check(f"Unload through Ollama's API, got {code} {r.box.unloads}", code == 200 and r.box.unloads)
    finally:
        C.load_budget_s = real_budget


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
