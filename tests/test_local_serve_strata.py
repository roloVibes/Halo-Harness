"""tests.test_local_serve_strata -- Halo 3.3.9.2 deliverables 1 and 2: `halo local serve --runtime strata --model
<family>/<set>` (halo_harness/strata/launch.py and control.py through local_hf_serve_cli.py) with the fake `strata`
(`huggingface.strata_bin` = tests/helpers/fake_strata.py, tests/helpers/st_home.StHome) on a free loopback port:

1. served: `strata launch --family qwen --model IQ3_XXS --yes --no-tui --access local --port P --api-key-env
   HALO_SECRET_STRATA_API_KEY`, the registry row `strata` (kind strata, keep: Strata's supervisor runs it, the server's
   own log once the launch returned) and the entry `strata` (url, log, runtime, the served model, api_key_env); the key
   in the scratch env file, never in config.json or the output; a chat answers with it; `halo local servers | log |
   stop` treat it like the others and the stop is `strata launch --stop` for its launch;
2. a second serve says the running one; a set Strata does not name starts nothing; strata missing: one line, the
   install route for this OS (install.ps1 on Windows, install.sh elsewhere) and the set's download GB, exit 2;
3. the plan says a download (the set's GB, or the engine): exit 2, the GB and the command the user runs, nothing
   started; `--plan`: Strata's own plan and the fit here, nothing started;
4. a launch still loading after the wait: said, exit 0, settled once it returns; no engine for this computer: exit 1;
5. the auto-detect names a Strata server by its runtime (`/health` says "service": "strata"), its window from
   `meta.n_ctx`. No real Strata, no model, nothing downloads.
Run: python -m tests.test_local_serve_strata
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.st_home import StHome  # noqa: E402

test, TESTS = new_registry()
KEY_ENV = "HALO_SECRET_STRATA_API_KEY"


def _local(*argv) -> "tuple[int, str]":
    from halo_harness.local_cli import cmd_local
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = cmd_local(list(argv))
    return code, out.getvalue()


def _get(url: str, key: str = "") -> int:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"} if key else {})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def _entry(h) -> dict:
    return next((e for e in h.config()["huggingface"].get("local_servers") or [] if e.get("name") == "strata"), {})


def _row(h) -> dict:
    p = h.state / "run" / "local-servers.json"
    rows = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else []
    return next((r for r in rows if r.get("id") == "strata"), {})


@test
def test_serve_registers_the_server_and_the_entry(ctx: Ctx):
    with StHome() as h:
        code, out = _local("serve", "--runtime", "strata", "--model", "qwen/IQ3_XXS")
        ctx.check(f"serving, got {code} {out!r}", code == 0 and "serving qwen3.8-flash-next (Strata) on http://127.0.0.1:"
                  in out and "use it as hf:local/qwen3.8-flash-next@strata" in out and "Strata keeps serving" in out)
        cmd = out.splitlines()[1].split()
        ctx.check(f"the command line, got {cmd[2:]}", cmd[2:7] == ["launch", "--family", "qwen", "--model", "IQ3_XXS"]
                  and cmd[7:11] == ["--yes", "--no-tui", "--access", "local"] and cmd[11] == "--port"
                  and cmd[13:] == ["--api-key-env", KEY_ENV])
        row, e = _row(h), _entry(h)
        ctx.check(f"the registry row, got {row}", row.get("kind") == "strata" and row.get("keep") is True
                  and row.get("settled") is True and row.get("pid") is None and row.get("ready") is True
                  and row["log"].endswith("launch-iq3-xxs-32k.server.log") and row["launch_log"].endswith("strata.log"))
        ctx.check(f"the entry, got {e}", e.get("runtime") == "strata" and e.get("url") == row.get("base_url")
                  and e.get("model") == "qwen3.8-flash-next" and e.get("strata") is True and e.get("lan") is False
                  and e.get("api_key_env") == KEY_ENV and e.get("log") == row["log"])
        key = os.environ.get(KEY_ENV) or ""
        ctx.check("the key: in the scratch env file, never in config.json or the output",
                  key and key in (h.root / "env").read_text(encoding="utf-8") and key not in out
                  and key not in (h.state / "config.json").read_text(encoding="utf-8"))
        ctx.check("a call without the key is refused, with it answered",
                  _get(e["url"] + "/models") == 401 and _get(e["url"] + "/models", key) == 200)
        from types import SimpleNamespace
        from halo_harness.freetoken.bench import sender
        got = sender(SimpleNamespace(url=e["url"], model=e["model"], api_key=key))([{"role": "user", "content": "hi"}],
                                                                                 max_tokens=4)
        ctx.check(f"a chat answers with usage, got {got}", got.get("error") is None and got["completion_tokens"] == 4)
        code, out = _local("servers")
        ctx.check(f"halo local servers, got {out!r}", code == 0 and "strata  strata  http://127.0.0.1:" in out
                  and "ready  hf:local/qwen3.8-flash-next@strata  strata launch qwen/IQ3_XXS" in out)
        code, out = _local("log", "strata", "-n", "20")
        ctx.check(f"halo local log strata: the server's own log, got {code} {out[-300:]!r}", code == 0
                  and "ready: http://127.0.0.1:" in out and "[strata] done: 4 tokens" in out)
        code, out = _local("serve", "--runtime", "strata", "--model", "qwen/IQ3_XXS")
        ctx.check(f"a second serve: already serving it, got {out!r}", code == 0 and "already serving it" in out)
        code, out = _local("serve", "--runtime", "strata", "--model", "qwen/Q2_0")
        ctx.check(f"another set: stop it first, got {out!r}", code == 1 and "halo local stop strata first" in out)
        code, out = _local("stop", "strata")
        ctx.check(f"stopped through strata launch --stop, the entry gone, got {out!r}", code == 0
                  and "Stopped iq3-xxs-32k." in out and _entry(h) == {} and _row(h) == {} and h.fake_runs() == {})


@test
def test_no_such_set_and_the_install_line(ctx: Ctx):
    from halo_harness.strata import requirements as R
    with StHome() as h:
        code, out = _local("serve", "--runtime", "strata", "--model", "qwen/IQ9_ZZ")
        ctx.check(f"no such set, got {code} {out!r}", code == 1 and "no Strata set named 'qwen/IQ9_ZZ'" in out
                  and _row(h) == {})
        h.set_hf(strata_bin=None)
        R.SEAMS.update(which=lambda name: None, os=lambda: "windows")
        code, out = _local("serve", "--runtime", "strata", "--model", "qwen/IQ3_XXS")
        line = out.strip()
        ctx.check(f"Windows: one line, install.ps1, the GB, exit 2, got {code} {line!r}", code == 2 and "\n" not in line
                  and line.startswith("strata is not on PATH: install it in PowerShell: irm https://github.com/Niko1221/"
                                      "Strata/releases/latest/download/install.ps1 | iex")
                  and "about 76 GB (Strata's table), yours to run" in line)
        R.SEAMS["os"] = lambda: "linux"
        code, out = _local("serve", "--runtime", "strata", "--model", "deepseek41/ist-das-2.00bpw")
        ctx.check(f"Linux: install.sh, the 257 GB, got {out.strip()!r}", code == 2 and "sh install.sh" in out
                  and "about 257 GB" in out)


@test
def test_the_plan_says_the_download_and_starts_nothing(ctx: Ctx):
    with StHome() as h:
        os.environ["FAKE_STRATA_DOWNLOAD_GB"] = "76"
        code, out = _local("serve", "--runtime", "strata", "--model", "qwen/IQ3_XXS")
        ctx.check(f"a download: exit 2, the GB and the command, got {code} {out!r}", code == 2 and out.startswith(
            "the first launch downloads about 76.0 GB (About 76.0 GB to download") and "Strata's download, yours to run: "
                  "strata launch --family qwen --model IQ3_XXS --yes --no-tui --access local" in out
                  and _row(h) == {} and _entry(h) == {} and h.fake_runs() == {})
        os.environ["FAKE_STRATA_DOWNLOAD_GB"] = "0"
        os.environ["FAKE_STRATA_ENGINE_MISSING"] = "1"
        code, out = _local("serve", "--runtime", "strata", "--model", "qwen/IQ3_XXS")
        ctx.check(f"the engine missing: exit 2, said, got {out!r}", code == 2 and "the engine for this card comes with it"
                  in out and "about 76 GB (Strata's table for IQ3_XXS)" in out and h.fake_runs() == {})
        code, out = _local("serve", "--runtime", "strata", "--model", "qwen/IQ3_XXS", "--plan")
        ctx.check(f"--plan: Strata's own answer and the fit here, nothing started, got {code} {out!r}", code == 0
                  and "Strata's own answer:" in out and "  Plan for 'iq3-xxs-32k':" in out and "Nothing was changed." in out
                  and "fit here: " in out and h.fake_runs() == {})


@test
def test_still_loading_then_settled_and_no_engine(ctx: Ctx):
    from halo_harness.strata.launch import serve
    with StHome() as h:
        os.environ["FAKE_STRATA_LAUNCH_S"] = "3"
        code, lines, row = serve("qwen/Q2_0", wait_s=0.3, state_dir=h.state)
        ctx.check(f"still starting, said, exit 0, got {code} {lines[-1:]}", code == 0 and row["ready"] is False
                  and "is still starting" in lines[-1] and "goes on in the background" in lines[-1])
        end = time.monotonic() + 20
        while time.monotonic() < end and not _row(h).get("settled"):
            _local("servers")
            time.sleep(0.2)
        r = _row(h)
        ctx.check(f"settled once the launch returned, got {r}", r.get("settled") and r.get("ready") is True
                  and r["log"].endswith("launch-q2-0-32k.server.log"))
        _local("stop", "strata")
    with StHome() as h:
        os.environ["FAKE_STRATA_NO_ENGINE"] = "1"
        code, lines, row = serve("qwen/IQ3_XXS", wait_s=20, state_dir=h.state)
        ctx.check(f"no engine: exit 1, Strata's line, nothing kept, got {code} {lines[-2:]}", code == 1 and row is None
                  and any("couldn't find an engine for this computer" in x for x in lines) and _row(h) == {}
                  and _entry(h) == {})


@test
def test_auto_detect_names_it_by_its_runtime(ctx: Ctx):
    from halo_harness.ollama_steward import servers_hf
    from halo_harness.providers import huggingface_local_probe as P
    from halo_harness.providers import local_runtime as R
    with StHome() as h:
        _local("serve", "--runtime", "strata", "--model", "qwen/IQ3_XXS")
        e, key = _entry(h), os.environ.get(KEY_ENV)
        rows = R.load_registry(h.state)
        R.save_registry(h.state, [])  # a server started by hand: no row, no entry, only the probe sees it
        h.set_hf(local_servers=[])
        info = P.probe_models_endpoint(e["url"], name="auto:x", api_key=key)
        ctx.check(f"/health says strata -> runtime strata, the window from meta.n_ctx, got {info}", info
                  and info.runtime_label == "strata" and info.model_ids == ("qwen3.8-flash-next",)
                  and info.context_by_model.get("qwen3.8-flash-next") == 32768)
        port = servers_hf.port_of(e["url"])
        P._auto_detect_cache = (time.monotonic(), (port,), (info,))
        servers_hf.reset()
        got = next((s for s in servers_hf.roster(h.state) if s.url.endswith(f":{port}")), None)
        ctx.check(f"the roster names it by its runtime, got {got}", got and got.runtime == "strata"
                  and got.source == "auto" and got.name == f"auto:{port}")
        R.save_registry(h.state, rows)  # the rig's exit stops it
        P.reset_auto_detect_cache()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
