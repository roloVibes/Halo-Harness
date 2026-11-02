"""tests.test_local_serve_freetoken -- Halo 3.3.9.1 deliverables 1 and 2: `halo local serve --runtime freetoken --model
<checkpoint dir>` (halo_harness/freetoken/launch.py through local_hf_serve_cli.py) with the fake `ft`
(`huggingface.freetoken_bin` = tests/helpers/fake_ft_server.py, tests/helpers/ft_home.FtHome) on a free loopback port:

1. served: the command line (`ft serve --model <dir> --served-model-name <name> --host 127.0.0.1 --port P
   --moe-collect-stats`), the registry row `freetoken` (kind and runtime freetoken, its log) and the entry `freetoken`
   (url, log, runtime, model, pid); a chat answers; `halo local servers | log | stop` treat it like the others and the
   stop takes the entry out;
2. a second serve says the running one; a folder that is not a checkpoint starts nothing;
3. a missing requirement (no `huggingface.freetoken_bin`): one line, the three requirements and the install command for
   each one missing, exit 2; all there: check() says ok;
4. the load that is still going after the wait: said with its progress, exit 0; nvcc against CUDA 13: exit 2 with the
   toolkit line;
5. `--lan`: bound to every address, Halo's key in FREETOKEN_API_KEY (never on the command line), the entry's
   api_key_env; the server refuses a call without it;
6. the auto-detect names a FreeToken server by its runtime (`owned_by: FreeToken`), and the session's wait for it is
   widened (freetoken/waits.py). No real FreeToken, no model, nothing downloads.
Run: python -m tests.test_local_serve_freetoken
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

from tests.helpers.ft_home import FtHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
NAME = "Qwen3.6-35B-A3B-NVFP4"


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
    return next((e for e in h.config()["huggingface"].get("local_servers") or [] if e.get("name") == "freetoken"), {})


@test
def test_serve_registers_the_server_and_the_entry(ctx: Ctx):
    with FtHome() as h:
        ck = h.checkpoint()
        code, out = _local("serve", "--runtime", "freetoken", "--model", str(ck))
        ctx.check(f"serving, got {code} {out!r}", code == 0 and f"serving {NAME} (FreeToken) on http://127.0.0.1:" in out
                  and f"use it as hf:local/{NAME}@freetoken" in out and "compiles FreeToken's CUDA kernels" in out)
        cmd = out.splitlines()[1].split()
        ctx.check(f"the command line, got {cmd[2:]}", cmd[2:5] == ["serve", "--model", str(ck)]
                  and cmd[5:7] == ["--served-model-name", NAME] and cmd[7:9] == ["--host", "127.0.0.1"]
                  and cmd[9] == "--port" and cmd[-1] == "--moe-collect-stats")
        rows = json.loads((h.state / "run" / "local-servers.json").read_text(encoding="utf-8"))
        row = next((r for r in rows if r.get("id") == "freetoken"), {})
        ctx.check(f"the registry row, got {row}", row.get("kind") == "freetoken" and row.get("runtime") == "freetoken"
                  and row.get("ready") is True and str(row.get("log", "")).endswith("freetoken.log"))
        e = _entry(h)
        ctx.check(f"the huggingface.local_servers entry, got {e}", e.get("runtime") == "freetoken" and e.get("url") ==
                  row.get("base_url") and e.get("model") == NAME and e.get("pid") == row.get("pid")
                  and e.get("freetoken") is True and e.get("lan") is False and "api_key_env" not in e)
        from halo_harness.freetoken.bench import sender
        from types import SimpleNamespace
        got = sender(SimpleNamespace(url=e["url"], model=NAME, api_key=None))([{"role": "user", "content": "hi"}],
                                                                             max_tokens=4)
        ctx.check(f"a chat answers with usage, got {got}", got.get("error") is None and got["completion_tokens"] == 4)
        code, out = _local("servers")
        ctx.check(f"halo local servers, got {out!r}", code == 0 and "freetoken  freetoken  http://127.0.0.1:" in out
                  and f"hf:local/{NAME}@freetoken  ft serve" in out)
        code, out = _local("log", "freetoken", "-n", "60")
        ctx.check(f"halo local log freetoken, got {code} {out[-300:]!r}", code == 0 and "API server is ready to serve" in out)
        code, out = _local("serve", "--runtime", "freetoken", "--model", str(ck))
        ctx.check(f"a second serve: already serving it, got {out!r}", code == 0 and "already serving it" in out)
        code, out = _local("serve", "--runtime", "freetoken", "--model", str(h.checkpoint("Gemma-4-26B-A4B-NVFP4")))
        ctx.check(f"another checkpoint: stop it first, got {out!r}", code == 1 and "halo local stop freetoken first" in out)
        code, out = _local("stop", "freetoken")
        ctx.check(f"stopped, the entry gone, got {out!r}", code == 0 and "stopped freetoken" in out and _entry(h) == {})


@test
def test_no_checkpoint_and_the_requirements_line(ctx: Ctx):
    from halo_harness.freetoken import requirements as R
    with FtHome() as h:
        code, out = _local("serve", "--runtime", "freetoken", "--model", str(h.root / "nowhere"))
        ctx.check(f"no checkpoint folder, got {code} {out!r}", code == 1 and "no checkpoint folder" in out
                  and not (h.state / "run" / "local-servers.json").is_file())
        h.set_hf(freetoken_bin=None)
        R.SEAMS.update(platform=lambda: {"os": "windows", "arch": "amd64", "linux": False, "x86": True, "wsl": False},
                       which=lambda name: None, run=lambda argv: (127, "not found"))
        code, out = _local("serve", "--runtime", "freetoken", "--model", str(h.checkpoint()))
        line = out.strip()
        ctx.check(f"one line, exit 2, got {code} {line!r}", code == 2 and "\n" not in line and line.startswith(
            "FreeToken needs Linux x86_64, an NVIDIA driver r580+ (CUDA 13) and nvcc on PATH; missing here: Linux x86_64 "
            "(this machine: windows amd64; on Windows, WSL2 with Ubuntu)") and "nvidia-driver-580" in line
                  and "cuda-toolkit-13-0" in line and 'uv pip install "freetoken[accel]"' in line)
        answers = {"nvidia-smi": (0, "580.65.06\n"), "nvcc": (0, "Cuda compilation tools, release 13.0, V13.0.48"),
                   "/opt/ft/bin/ft": (0, "freetoken version 0.4.1\n")}
        R.SEAMS.update(platform=lambda: {"os": "linux", "arch": "x86_64", "linux": True, "x86": True, "wsl": True},
                       which=lambda name: {"ft": "/opt/ft/bin/ft", "nvcc": "/usr/local/cuda/bin/nvcc"}.get(name),
                       run=lambda argv: answers.get(argv[0], (1, "")))
        c = R.check()
        ctx.check(f"all there under WSL2: ok, the caveat said, got {c['line']!r}", c["ok"] and c["driver"] == "580.65"
                  and c["nvcc"] == "13.0" and c["ft_version"] == "0.4.1" and c["line"].startswith("WSL2: under WSL2 CUDA "
                                                                                                   "pinned memory is capped"))


@test
def test_still_loading_and_the_nvcc_failure(ctx: Ctx):
    from halo_harness.freetoken.launch import serve
    with FtHome() as h:
        os.environ["FAKE_FT_LOAD_S"] = "5"
        code, lines, row = serve(str(h.checkpoint()), wait_s=0.6, state_dir=h.state)
        ctx.check(f"still loading, said with its progress, got {code} {lines}", code == 0 and row["ready"] is False
                  and any("is still loading (2.0 of 18.0 GiB): it goes on in the background" in x for x in lines))
        _local("stop", "freetoken")
    with FtHome() as h:
        os.environ["FAKE_FT_EXIT"] = "nvcc"
        code, lines, row = serve(str(h.checkpoint()), wait_s=10, state_dir=h.state)
        ctx.check(f"nvcc against CUDA 13: exit 2, the toolkit line, got {code} {lines[-2:]}", code == 2 and row is None
                  and any("would build kernels" in x for x in lines) and lines[-1].startswith("  needs the CUDA 13 toolkit"))


@test
def test_lan_binds_every_address_behind_a_key(ctx: Ctx):
    with FtHome() as h:
        code, out = _local("serve", "--runtime", "freetoken", "--model", str(h.checkpoint()), "--lan")
        e = _entry(h)
        key = os.environ.get("HALO_SECRET_FREETOKEN_API_KEY") or ""
        ctx.check(f"served on the LAN, got {code} {out.splitlines()[:2]}", code == 0 and "--host 0.0.0.0" in out
                  and "behind Halo's key (FREETOKEN_API_KEY)" in out and key and key not in out)
        ctx.check(f"the entry names the key's env var, got {e}", e.get("lan") is True
                  and e.get("api_key_env") == "HALO_SECRET_FREETOKEN_API_KEY")
        ctx.check("the key is in the scratch env file", key in (h.root / "env").read_text(encoding="utf-8"))
        ctx.check("a call without the key is refused, with it answered",
                  _get(e["url"] + "/models") == 401 and _get(e["url"] + "/models", key) == 200)
        from halo_harness.providers.huggingface import resolve_huggingface_local_server
        ctx.check("Halo's own entry carries the key", resolve_huggingface_local_server("freetoken").api_key == key)


@test
def test_auto_detect_names_it_and_the_wait_is_widened(ctx: Ctx):
    import time
    from halo_harness.freetoken.waits import FIRST_WAIT_S, widen
    from halo_harness.providers import huggingface_local_probe as P
    from halo_harness.ollama_steward import servers_hf
    with FtHome() as h:
        code, out = _local("serve", "--runtime", "freetoken", "--model", str(h.checkpoint()))
        e = _entry(h)
        from halo_harness.providers import local_runtime as R
        rows = R.load_registry(h.state)
        R.save_registry(h.state, [])  # a server started by hand: no row, no entry, only the probe sees it
        h.set_hf(local_servers=[])
        info = P.probe_models_endpoint(e["url"], name="auto:x")
        ctx.check(f"owned_by FreeToken -> runtime freetoken, got {info}", info and info.runtime_label == "freetoken"
                  and info.model_ids == (NAME,) and info.context_by_model.get(NAME) == 32768)
        port = servers_hf.port_of(e["url"])
        P._auto_detect_cache = (time.monotonic(), (port,), (info,))
        servers_hf.reset()
        got = next((s for s in servers_hf.roster(h.state) if s.url.endswith(f":{port}")), None)
        ctx.check(f"the roster names it by its runtime, got {got}", got and got.runtime == "freetoken"
                  and got.source == "auto" and got.name == f"auto:{port}" and got.model == NAME)
        R.save_registry(h.state, rows)  # the rig's exit stops it

        class Sock:
            t = None

            def settimeout(self, v):
                self.t = v
        a, b = type("C", (), {"sock": Sock()})(), type("C", (), {"sock": Sock()})()
        widen(a, e["url"])
        widen(b, "http://127.0.0.1:9/v1")
        ctx.check(f"the session's wait: {FIRST_WAIT_S:g} s for FreeToken, untouched otherwise, got {a.sock.t} {b.sock.t}",
                  a.sock.t == FIRST_WAIT_S and b.sock.t is None)
        P.reset_auto_detect_cache()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
