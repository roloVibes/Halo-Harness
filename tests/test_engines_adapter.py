"""tests.test_engines_adapter -- Halo 3.3.13.0 R1 deliverable 1: one adapter for every engine of the descriptor table
(halo_harness/engines/adapter.py, launch.py) through the fake engine (tests/helpers/fake_engine.py, engine_home.EngineHome)
on free loopback ports:

1. detect: a server on a probed port is named by its rows' owned_by or by its /health keys (asked only when a row has
   the engine's shape); a llama-server stays llama-server;
2. the managed start per descriptor: FreeToken's `serve --model <dir> --served-model-name N --host 127.0.0.1 --port P
   --moe-collect-stats`, the registry row and the entry `engine: freetoken`; `halo local servers | stop` treat it like
   the others and the stop takes the entry out; TensorFold's `serve <repo> --name ... --context N --parallel N` behind a
   0600 key file with `--lan` (the key never on the command line), a repo not in the Hugging Face cache starts nothing;
3. Strata's supervised start: its plan says a download -> nothing starts, the GB said; nothing to fetch -> `launch` runs
   and returns, the settle reads its server log and serving state, the stop is `launch --stop --preset <its launch>`;
4. an engine with no `start` is detect-only; no program -> the owner's install line, exit 2; an entry Halo wrote before
   3.3.13.0 (`freetoken: true`) and the old `huggingface.freetoken_bin` word still work.
Run: python -m tests.test_engines_adapter
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.engine_home import EngineHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _local(*argv) -> "tuple[int, str]":
    from halo_harness.local_cli import cmd_local
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = cmd_local(list(argv))
    return code, out.getvalue()


def _status(url: str) -> int:
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def _entry(h, name: str) -> dict:
    return next((e for e in h.config()["huggingface"].get("local_servers") or [] if e.get("name") == name), {})


def _row(h, rid: str) -> dict:
    rows = json.loads((h.state / "run" / "local-servers.json").read_text(encoding="utf-8"))
    return next((r for r in rows if r.get("id") == rid), {})


@test
def test_detect_by_owned_by_or_health(ctx: Ctx):
    from halo_harness.engines.adapter import identify
    with EngineHome() as h:
        ck = h.checkpoint()
        code, _out = _local("serve", "--runtime", "freetoken", "--model", str(ck))
        url = _row(h, "freetoken").get("base_url")
        from halo_harness.providers.huggingface_local_probe import probe_models_endpoint
        got = probe_models_endpoint(url, name="auto")
        ctx.check(f"owned_by FreeToken names it, got {got}", code == 0 and got and got.runtime_label == "freetoken")
        rows = [{"id": "qwen", "object": "model", "meta": {"n_ctx": 32768}, "architecture": "qwen"}]
        ctx.check("a Strata-shaped row with no Strata behind it: nobody", identify(url, rows) == (None, {}))
        ctx.check("llama-server rows stay llama-server's", identify(url, [{"id": "m", "owned_by": "llamacpp"}])[0] is None)


@test
def test_freetokens_managed_start_and_stop(ctx: Ctx):
    with EngineHome() as h:
        ck = h.checkpoint()
        code, out = _local("serve", "--runtime", "freetoken", "--model", str(ck))
        ctx.check(f"serving, got {code} {out!r}", code == 0 and "serving Qwen3.6-35B-A3B-NVFP4 (FreeToken) on "
                  "http://127.0.0.1:" in out and "use it as hf:local/Qwen3.6-35B-A3B-NVFP4@freetoken" in out)
        start = next(a for a in h.argv() if a[1:2] == ["serve"])
        ctx.check(f"the descriptor's command line, got {start}", start[2:6] == ["--model", str(ck.resolve()),
                  "--served-model-name", "Qwen3.6-35B-A3B-NVFP4"] and start[6:8] == ["--host", "127.0.0.1"]
                  and start[-1] == "--moe-collect-stats")
        row, e = _row(h, "freetoken"), _entry(h, "freetoken")
        ctx.check(f"the registry row and the entry, got {row} {e}", row.get("kind") == "freetoken" and row.get("ready")
                  and e.get("engine") == "freetoken" and e.get("runtime") == "freetoken" and e.get("url") == row["base_url"]
                  and e.get("lan") is False)
        code, out = _local("serve", "--runtime", "freetoken", "--model", str(ck))
        ctx.check(f"a second serve says it runs, got {out!r}", code == 0 and "already serving it" in out)
        code, out = _local("servers")
        ctx.check(f"halo local servers lists it, got {out!r}", "hf:local/Qwen3.6-35B-A3B-NVFP4@freetoken  FreeToken" in out)
        code, out = _local("stop", "freetoken")
        ctx.check(f"stopped and the entry gone, got {out!r}", code == 0 and "stopped freetoken" in out
                  and not _entry(h, "freetoken"))
        code, out = _local("serve", "--runtime", "freetoken", "--model", str(h.root / "nothing-here"))
        ctx.check(f"no checkpoint folder: nothing starts, got {code} {out!r}", code == 1 and "no checkpoint folder" in out)


@test
def test_tensorfold_behind_a_key_file(ctx: Ctx):
    with EngineHome() as h:
        repo = "TensorFold/Qwen3.8-27B-MLX-4bit"
        code, out = _local("serve", "--runtime", "tensorfold", "--model", repo)
        ctx.check(f"not in the cache: nothing starts, the pull said, got {code} {out!r}", code == 2
                  and "tensorfold pull TensorFold/Qwen3.8-27B-MLX-4bit" in out)
        h.cached(repo)
        code, out = _local("serve", "--runtime", "tensorfold", "--model", repo, "--window", "16384", "--parallel", "2",
                           "--lan")
        start = next(a for a in h.argv() if a[1:2] == ["serve"])
        kf = h.state / "local" / "servers" / "tensorfold.key"
        ctx.check(f"served with the window, the streams and the key file, got {code} {start}", code == 0
                  and start[2] == repo and start[start.index("--context") + 1] == "16384"
                  and start[start.index("--parallel") + 1] == "2" and start[start.index("--host") + 1] == "0.0.0.0"
                  and start[start.index("--api-key-file") + 1] == str(kf))
        key = kf.read_text(encoding="utf-8").split(":", 1)[1].strip()
        ctx.check("the key is in the file and the env file, never on the command line", key and key not in " ".join(start)
                  and os.environ.get("HALO_SECRET_TENSORFOLD_API_KEY") == key)
        if os.name != "nt":
            ctx.check("the key file is owner-only", (kf.stat().st_mode & 0o777) == 0o600)
        e = _entry(h, "tensorfold")
        ctx.check(f"the entry: lan, its key's name, got {e}", e.get("lan") is True
                  and e.get("api_key_env") == "HALO_SECRET_TENSORFOLD_API_KEY")
        ctx.check("a call without the key is refused", _status(e["url"] + "/models") == 401)
        _local("stop", "tensorfold")
        ctx.check("the stop takes the entry and the key file", not _entry(h, "tensorfold") and not kf.exists())


@test
def test_stratas_supervised_start(ctx: Ctx):
    with EngineHome() as h:
        os.environ["FAKE_ENGINE_DOWNLOAD_GB"] = "76"
        code, out = _local("serve", "--runtime", "strata", "--model", "qwen/IQ3_XXS")
        ran = [a[1:3] for a in h.argv()]
        ctx.check(f"its plan downloads: nothing starts, the GB said, got {code} {out!r}", code == 2
                  and "downloads about 76.0 GB" in out and "strata launch --family qwen --model IQ3_XXS" in out
                  and all("--plan" in a or a[0] == "--version" for a in [x[1:] for x in h.argv()]) and ran)
        os.environ["FAKE_ENGINE_DOWNLOAD_GB"] = "0"
        code, out = _local("serve", "--runtime", "strata", "--model", "qwen/IQ3_XXS")
        start = next(a for a in h.argv() if a[1:2] == ["launch"] and "--no-tui" in a)
        ctx.check(f"started, its supervisor runs it, got {code} {out!r}", code == 0 and "its own supervisor runs it" in out
                  and start[start.index("--access") + 1] == "local" and "HALO_SECRET_STRATA_API_KEY" in start)
        row = _row(h, "strata")
        ctx.check(f"settled: the server's own log, no pid, got {row}", row.get("settled") and row.get("pid") is None
                  and str(row.get("log", "")).endswith(f"launch-{row.get('port')}.server.log"))
        from halo_harness.providers.huggingface_local_probe import probe_models_endpoint
        got = probe_models_endpoint(row["base_url"], name="auto", api_key=os.environ.get("HALO_SECRET_STRATA_API_KEY"))
        ctx.check(f"its /health names it Strata, its window from the rows' meta, got {got}", got is not None
                  and got.runtime_label == "strata" and set(got.context_by_model.values()) == {32768})
        code, out = _local("stop", "strata")
        stop = next((a for a in h.argv() if "--stop" in a), [])
        ctx.check(f"the stop is Strata's own, got {out!r} {stop}", code == 0 and stop[-2:] == ["--preset",
                  f"launch-{row.get('port')}"] and not _entry(h, "strata"))


@test
def test_detect_only_missing_program_and_old_words(ctx: Ctx):
    from halo_harness.engines import adapter
    from halo_harness.engines.descriptors import TABLE
    with EngineHome() as h:
        saved = TABLE["tensorfold"]["start"]
        TABLE["tensorfold"]["start"] = None
        try:
            code, out = _local("serve", "--runtime", "tensorfold", "--model", "a/b")
        finally:
            TABLE["tensorfold"]["start"] = saved
        ctx.check(f"no start: detect-only, got {code} {out!r}", code == 1 and "detect-only" in out)
        h.set_hf(engine_bins={})
        adapter.SEAMS["which"] = lambda name: None
        code, out = _local("serve", "--runtime", "freetoken", "--model", str(h.checkpoint()))
        ctx.check(f"no program: the owner's install line, got {code} {out!r}", code == 2
                  and 'uv pip install "freetoken[accel]"' in out)
        h.set_hf(freetoken_bin=["ft-old"])
        ctx.check("the old word is still read", adapter.binary("freetoken") == (["ft-old"], "huggingface.freetoken_bin"))
        old = {"name": "freetoken", "url": "http://127.0.0.1:9/v1", "runtime": "freetoken", "freetoken": True}
        h.set_hf(local_servers=[old])
        ctx.check("an entry Halo wrote before is ours, and forget takes it", adapter.ours(old, "freetoken")
                  and adapter.forget("freetoken") and not _entry(h, "freetoken"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
