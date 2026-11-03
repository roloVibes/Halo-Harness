"""tests.test_local_serve_tensorfold -- Halo 3.3.9.3 deliverables 1 and 2: `halo local serve --runtime tensorfold --model
<hf repo | checkpoint dir>` (providers/local_runtime_tensorfold.py through local_hf_serve_cli.py) with the fake binary
(`huggingface.tensorfold_bin` = tests/helpers/fake_tensorfold_server.py, tests/helpers/tf_home.TfHome) on a free loopback
port:

1. a repo in the Hub cache: the command line (`tensorfold serve <repo> --name <model> --host 127.0.0.1 --port P --context
   N --api-key-file <file>`), the registry row and the entry `tensorfold` (url, log, runtime, model, pid, api_key_env);
   the key in the 0600 file and the env file, never on the command line, the output or config.json; a chat answers with
   the key, a call without it is refused; `halo local servers | log | stop` treat it like the others and the stop takes
   the entry and the key file out; a second serve says the running one, another model says stop it first;
2. a checkpoint folder and a repo Halo's download put in a model folder are served by their path; a repo nowhere on
   disk starts nothing: one line, `tensorfold pull` with the GB TensorFold states, exit 2; no binary: the per-OS line
   (brew on the Mac, the native build guide on Windows, the fetch on Linux), exit 2;
3. the load still going after the wait is said, exit 0; a driver refusal: exit 2 with its line;
4. `--lan` binds every address; the auto-detect names a hand-started server by `owned_by: tensorfold`, its window from
   `context_length`. No real TensorFold, no model, nothing downloads.
Run: python -m tests.test_local_serve_tensorfold
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.tf_home import FAKE_TF, REPO, TfHome  # noqa: E402

test, TESTS = new_registry()
NAME = "Qwen3.8-27B-MLX-4bit"


def _local(*argv) -> "tuple[int, str]":
    from halo_harness.local_cli import cmd_local
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = cmd_local(list(argv))
    return code, out.getvalue()


def _call(url: str, key: str = "", body=None) -> int:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json",
                                                          **({"Authorization": f"Bearer {key}"} if key else {})})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def _entry(h) -> dict:
    return next((e for e in h.config()["huggingface"].get("local_servers") or [] if e.get("name") == "tensorfold"), {})


@test
def test_serve_a_cached_repo(ctx: Ctx):
    with TfHome() as h:
        h.cached()
        code, out = _local("serve", "--runtime", "tensorfold", "--model", REPO)
        ctx.check(f"serving, got {code} {out!r}", code == 0 and f"serving {NAME} (TensorFold) on http://127.0.0.1:" in out
                  and f"use it as hf:local/{NAME}@tensorfold" in out and "window 32,768 (TensorFold's table)" in out)
        cmd = next(x for x in out.splitlines() if " serve " in x).split()
        kf = h.state / "local" / "servers" / "tensorfold.key"
        ctx.check(f"the command line, got {cmd[2:]}", cmd[2:4] == ["serve", REPO] and cmd[4:6] == ["--name", NAME]
                  and cmd[6:8] == ["--host", "127.0.0.1"] and cmd[8] == "--port" and cmd[10:12] == ["--context", "32768"]
                  and cmd[12:14] == ["--api-key-file", str(kf)])
        key = os.environ.get("HALO_SECRET_TENSORFOLD_API_KEY") or ""
        ctx.check("the key: in the key file and the env file, not in the output or config.json", key and key in
                  kf.read_text(encoding="utf-8") and key in (h.root / "env").read_text(encoding="utf-8")
                  and key not in out and key not in (h.state / "config.json").read_text(encoding="utf-8"))
        if os.name != "nt":
            ctx.check("the key file is owner-only", (kf.stat().st_mode & 0o777) == 0o600)
        rows = json.loads((h.state / "run" / "local-servers.json").read_text(encoding="utf-8"))
        row = next((r for r in rows if r.get("id") == "tensorfold"), {})
        e = _entry(h)
        ctx.check(f"the registry row and the entry, got {row} {e}", row.get("kind") == "tensorfold" and row.get("ready")
                  and e.get("url") == row.get("base_url") and e.get("model") == NAME and e.get("pid") == row.get("pid")
                  and e.get("runtime") == "tensorfold" and e.get("api_key_env") == "HALO_SECRET_TENSORFOLD_API_KEY"
                  and e.get("tensorfold") is True and e.get("lan") is False and str(e.get("log")).endswith("tensorfold.log"))
        chat = {"model": NAME, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 4}
        ctx.check("a chat answers with the key, is refused without it",
                  _call(e["url"] + "/chat/completions", key, chat) == 200 and _call(e["url"] + "/chat/completions", "",
                                                                                    chat) == 401)
        from halo_harness.providers.huggingface import resolve_huggingface_local_server
        ctx.check("Halo's own entry carries the key", resolve_huggingface_local_server("tensorfold").api_key == key)
        code, out = _local("servers")
        ctx.check(f"halo local servers, got {out!r}", code == 0 and "tensorfold  tensorfold  http://127.0.0.1:" in out
                  and f"hf:local/{NAME}@tensorfold  tensorfold serve --context 32768" in out)
        code, out = _local("log", "tensorfold", "-n", "40")
        ctx.check(f"halo local log, got {out[-300:]!r}", code == 0 and f"[tensorfold] serving {NAME} at http://127.0.0.1:"
                  in out and "streams at once" in out)
        code, out = _local("serve", "--runtime", "tensorfold", "--model", REPO)
        ctx.check(f"a second serve: already serving it, got {out!r}", code == 0 and "already serving it" in out)
        code, out = _local("serve", "--runtime", "tensorfold", "--model", str(h.checkpoint()))
        ctx.check(f"another model: stop it first, got {out!r}", code == 1 and "halo local stop tensorfold first" in out)
        code, out = _local("stop", "tensorfold")
        ctx.check(f"stopped: the entry and the key file gone, got {out!r}", code == 0 and "stopped tensorfold" in out
                  and _entry(h) == {} and not kf.exists())


@test
def test_folders_missing_checkpoints_and_the_binary_line(ctx: Ctx):
    from halo_harness.providers.local_runtime_tensorfold import serve
    from halo_harness.tensorfold import requirements as Q
    with TfHome() as h:
        ck = h.checkpoint()
        code, lines, row = serve(str(ck), state_dir=h.state, wait_s=10)
        ctx.check(f"a checkpoint folder is served by its path, got {code} {lines[:2]}", code == 0 and row["model"] ==
                  "qwen27-local" and row["cmdline"][3] == str(ck.resolve()))
        _local("stop", "tensorfold")
        snap = h.cached("LiquidAI/LFM2.5-24B-A2B-MLX-4bit", root=h.models)
        code, lines, row = serve("LiquidAI/LFM2.5-24B-A2B-MLX-4bit", state_dir=h.state, wait_s=10)
        ctx.check(f"Halo's download in a model folder: its snapshot path, got {code} {lines[:1]}", code == 0 and
                  row["cmdline"][3] == str(snap) and any("(Halo's download)" in x for x in lines))
        _local("stop", "tensorfold")
        code, out = _local("serve", "--runtime", "tensorfold", "--model", "nvidia/Qwen3.6-35B-A3B-NVFP4")
        line = out.strip()
        ctx.check(f"a repo nowhere on disk: one line with the GB, exit 2, got {code} {line!r}", code == 2 and "\n" not in
                  line and "(20.9 GiB, TensorFold's figure)" in line and "tensorfold pull nvidia/Qwen3.6-35B-A3B-NVFP4@" in
                  line and "halo local download nvidia/Qwen3.6-35B-A3B-NVFP4" in line)
        code, out = _local("serve", "--runtime", "tensorfold", "--model", str(h.root / "nowhere"))
        ctx.check(f"a folder that is not there: exit 1, got {code} {out!r}", code == 1 and "no checkpoint folder" in out)
        h.cached()
        h.set_hf(tensorfold_bin=None)
        for os_name, want in (("macos", "brew install ashhart/tensorfold/tensorfold"),
                              ("windows", "docs/WINDOWS.md"),
                              ("linux", "halo local serve --runtime tensorfold --yes fetches the linux-x86_64")):
            Q.SEAMS.update(os=lambda o=os_name: o, which=lambda name: None)
            code, out = _local("serve", "--runtime", "tensorfold", "--model", REPO)
            ctx.check(f"no binary on {os_name}: one line with its route, got {code} {out!r}", code == 2
                      and out.count("\n") == 1 and want in out)


@test
def test_still_loading_and_the_driver_refusal(ctx: Ctx):
    from halo_harness.providers.local_runtime_tensorfold import serve
    with TfHome() as h:
        h.cached()
        os.environ["FAKE_TF_LOAD_S"] = "5"
        code, lines, row = serve(REPO, wait_s=0.6, state_dir=h.state)
        ctx.check(f"still loading: said, exit 0, got {code} {lines}", code == 0 and row["ready"] is False
                  and any("is still loading: TensorFold opens its port once the checkpoint is in memory" in x for x in lines))
        _local("stop", "tensorfold")
    with TfHome() as h:
        h.cached()
        os.environ["FAKE_TF_EXIT"] = "driver"
        code, lines, row = serve(REPO, wait_s=10, state_dir=h.state)
        ctx.check(f"a driver refusal: exit 2 with its line, got {code} {lines[-2:]}", code == 2 and row is None
                  and any("driver R580 or newer" in x for x in lines))


@test
def test_lan_and_the_auto_detect(ctx: Ctx):
    from halo_harness.providers import huggingface_local_probe as P
    from halo_harness.providers.local_runtime import find_free_port
    from halo_harness.providers.local_server_cmd import get
    with TfHome() as h:
        h.cached()
        code, out = _local("serve", "--runtime", "tensorfold", "--model", REPO, "--lan")
        ctx.check(f"--lan: every address, the entry says so, got {code}", code == 0 and "--host 0.0.0.0" in out
                  and "bound to every address" in out and _entry(h).get("lan") is True)
        _local("stop", "tensorfold")
        port = find_free_port()
        proc = subprocess.Popen([sys.executable, str(FAKE_TF), "serve", REPO, "--name", "local-model", "--port", str(port)],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
        try:
            end, info = time.monotonic() + 15, None
            while time.monotonic() < end and info is None:
                info = P.probe_models_endpoint(f"http://127.0.0.1:{port}/v1", name=f"auto:{port}")
                time.sleep(0.1) if info is None else None
            ctx.check(f"owned_by tensorfold -> runtime tensorfold, got {info}", info and info.runtime_label == "tensorfold"
                      and info.model_ids == ("local-model",) and info.context_by_model.get("local-model") == 32768)
            code, body = get(f"http://127.0.0.1:{port}/health")
            ctx.check(f"a keyless server's /health has live.*, got {body}", code == 200 and body["live"]["waiting"] == 0
                      and body["backend"] == "cuda" and body["model_ids"] == ["local-model"])
        finally:
            proc.kill()
            proc.wait(timeout=10)
        P.reset_auto_detect_cache()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
