"""tests.test_engines_children -- what a managed server's child is given and how Halo knows it (Halo 3.3.14.0 R2;
engines/launch_env.py, engines/launch.py, engines/adapter.py, voice/launch.py, providers/local_server.py,
providers/local_runtime.py):

1. REVIEW #22 (LOCAL-2): every launcher (an engine, a speech server, llama-server through `halo local serve`, the
   session's managed server) starts its child with no ANTHROPIC_API_KEY / OPENROUTER_API_KEY / DATABRICKS_TOKEN /
   HF_TOKEN when the parent holds fake values; an engine's own key is still there;
2. REVIEW #21 (LOCAL-1): an engine row records `proc_start`; a row whose live pid has another start time is gone to
   `alive`, and the exit sweep signals nothing;
3. REVIEW #24 (LOCAL-4): `--lan` says "behind Halo's key" only when the engine refuses a request without it; an engine
   answering 200 unkeyed serves on 127.0.0.1 only and the row says why;
4. REVIEW #45 (LOCAL-11): `widen` gives the long wait to the first connection only;
5. REVIEW #43 (LOCAL-9): a program only the current folder holds is not run (the line says so).
Run: python -m tests.test_engines_children"""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.engine_home import EngineHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
KEYS = ("ANTHROPIC_API_KEY", "OPENROUTER_API_KEY", "DATABRICKS_TOKEN", "HF_TOKEN")
REPO = "TensorFold/Qwen3.8-27B-MLX-4bit"


def _local(*argv) -> "tuple[int, str]":
    from halo_harness.local_cli import cmd_local
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = cmd_local(list(argv))
    return code, out.getvalue()


def _row(h, rid: str) -> dict:
    rows = json.loads((h.state / "run" / "local-servers.json").read_text(encoding="utf-8"))
    return next((r for r in rows if r.get("id") == rid), {})


@contextlib.contextmanager
def _captured():
    """Every Popen records its argv and env and fails to start: the env a launcher hands its child, nothing run."""
    got, real = [], subprocess.Popen

    def fake(argv, *a, **kw):
        got.append((list(argv), kw.get("env")))
        raise OSError("captured by the test")
    saved = {k: os.environ.get(k) for k in KEYS}
    os.environ.update({k: f"fake-{k.lower()}" for k in KEYS})
    subprocess.Popen = fake
    try:
        yield got
    finally:
        subprocess.Popen = real
        for k, v in saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


@test
def test_every_launcher_hands_its_child_no_provider_key(ctx: Ctx):
    with EngineHome() as h:
        h.cached(REPO)
        model = h.root / "m.gguf"
        model.write_bytes(b"GGUF")
        from halo_harness.engines.launch import serve
        from halo_harness.providers.local_runtime import start_managed_server
        from halo_harness.providers.local_server import start
        from halo_harness.voice.launch import _start as voice_start
        with _captured() as got:
            serve("tensorfold", REPO, state_dir=h.state, wait_s=0)
            engine = got[-1]
            voice_start("stt", SimpleNamespace(name="m"), h.root, {"device": "cpu", "line": "cpu"}, ["prog"], port=0,
                        keep=False, state_dir=h.state, wait_s=0)
            voice = got[-1]
            start(model, runtime="llama-server", window=4096, ngl=0, prefix=["prog"], state_dir=h.state)
            llama = got[-1]
            start_managed_server(model="m", runtime="llama-server", binary_argv=["prog"], model_path=model,
                                 state_dir=h.state, startup_timeout=1)
            managed = got[-1]
        for name, (argv, env) in (("engine", engine), ("speech server", voice), ("llama-server", llama),
                                  ("managed server", managed)):
            ctx.check(f"the {name} child gets its own env, got {argv[:3]}", isinstance(env, dict) and "PATH" in
                      {k.upper() for k in env})
            ctx.check(f"the {name} child holds no provider key", isinstance(env, dict) and not set(KEYS) & set(env))
        ctx.check("the engine is the tensorfold serve", "serve" in engine[0])


@test
def test_a_reused_pid_is_not_the_engine(ctx: Ctx):
    from halo_harness.bg_run import pid_alive, process_start_time
    from halo_harness.engines.adapter import alive
    from halo_harness.providers import local_runtime as R
    from halo_harness.providers.local_server import exit_sweep
    with EngineHome() as h:
        h.cached(REPO)
        code, out = _local("serve", "--runtime", "tensorfold", "--model", REPO)
        row = _row(h, "tensorfold")
        ctx.check(f"served, got {code} {out!r}", code == 0)
        ctx.check(f"the row records proc_start, got {row.get('proc_start')}", row.get("proc_start")
                  and row["proc_start"] == process_start_time(row["pid"]))
        ctx.check("the live row is alive", alive(row))
        _local("stop", "tensorfold")
        other = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        try:
            ctx.check("this platform reads a start time", process_start_time(other.pid) is not None)
            stale = {**row, "pid": other.pid, "proc_start": "1", "owner_pid": 2 ** 22 + 7, "owner_start": "1",
                     "port": R.find_free_port(), "keep": False, "halo": True}
            R.save_registry(h.state, [stale])
            ctx.check("a live pid with another start time is gone to alive()", alive(stale) is False)
            swept = exit_sweep(h.state)
            ctx.check(f"the exit sweep signals nothing, got {swept}", any("nothing signalled" in str(s.get("say"))
                                                                         for s in swept) and other.poll() is None)
            ctx.check("the unrelated process still runs", pid_alive(other.pid))
        finally:
            other.kill()
            other.wait(10)


@test
def test_lan_is_announced_only_when_the_key_is_refused(ctx: Ctx):
    with EngineHome() as h:
        h.cached(REPO)
        code, out = _local("serve", "--runtime", "tensorfold", "--model", REPO, "--lan")
        ctx.check(f"a 401 unkeyed: announced, got {out!r}", code == 0 and "every address, behind Halo's key" in out
                  and "refused a request without the key (401)" in out)
        _local("stop", "tensorfold")
        os.environ["FAKE_ENGINE_NO_KEY"] = "1"
        code, out = _local("serve", "--runtime", "tensorfold", "--model", REPO, "--lan")
        ctx.check(f"a 200 unkeyed: not announced, got {code} {out!r}", code == 0 and "behind Halo's key" not in out
                  and "does not check Halo's key: it answered a request without Halo's key (200)" in out
                  and "127.0.0.1 only" in out)
        starts = [a for a in h.argv() if a[1:2] == ["serve"]]
        ctx.check("it was started again on loopback", starts and starts[-1][starts[-1].index("--host") + 1] == "127.0.0.1")
        row = _row(h, "tensorfold")
        ctx.check(f"the row says why, got {row.get('lan_off')}", "answered a request without Halo's key" in
                  str(row.get("lan_off")) and not (row.get("flags") or {}).get("lan"))
        entry = next((e for e in h.config()["huggingface"].get("local_servers") or [] if e.get("name") == "tensorfold"), {})
        ctx.check(f"the entry is not offered on the LAN, got {entry}", entry and entry.get("lan") is False)
        _local("stop", "tensorfold")


class _Sock:
    def __init__(self) -> None:
        self.waits = []

    def settimeout(self, t) -> None:
        self.waits.append(t)


@test
def test_widen_gives_the_first_connection_only_the_long_wait(ctx: Ctx):
    from halo_harness.engines import adapter as A
    from halo_harness.ollama_steward import servers_hf
    from halo_harness.ollama_steward.servers_hf import Server
    url, real = "http://127.0.0.1:1919/v1", servers_hf.for_url
    servers_hf.for_url = lambda u, state_dir=None: Server(name="freetoken", url=url, runtime="freetoken", pid=4242)
    A._WIDENED.clear()
    try:
        first, second = SimpleNamespace(sock=_Sock()), SimpleNamespace(sock=_Sock())
        A.widen(first, url)
        A.widen(second, url)
        ctx.check(f"the first connection waits the descriptor's time, got {first.sock.waits}",
                  len(first.sock.waits) == 1 and first.sock.waits[0] >= 600)
        ctx.check(f"the next keeps the normal budget, got {second.sock.waits}", second.sock.waits == [])
    finally:
        servers_hf.for_url = real
        A._WIDENED.clear()


@test
def test_a_program_in_the_current_folder_is_not_run(ctx: Ctx):
    from halo_harness.engines import adapter as A
    from halo_harness.engines.launch_env import on_path, vet
    with EngineHome() as h:
        h.set_hf(engine_bins={})
        A.SEAMS.pop("which", None)
        here, empty = Path(tempfile.mkdtemp(dir=h.root)), Path(tempfile.mkdtemp(dir=h.root))
        for name in ("strata.cmd", "llama-server.exe") if os.name == "nt" else ("strata", "llama-server"):
            (here / name).write_text("echo planted\n", encoding="utf-8")
            os.chmod(here / name, 0o755)
        old_cwd, old_path = os.getcwd(), os.environ.get("PATH", "")
        os.chdir(here)
        os.environ["PATH"] = str(empty)
        try:
            prefix, line = A.binary("strata")
            ctx.check(f"binary('strata') runs nothing, got {prefix} {line!r}", prefix is None
                      and "in the current folder is not run" in line)
            ctx.check("on_path finds nothing", on_path("llama-server")[0] is None)
            ctx.check("a which hit in the current folder is refused",
                      vet(str(here / ("llama-server.exe" if os.name == "nt" else "llama-server")), "llama-server")[0] is None)
            os.environ["PATH"] = str(here)
            ctx.check("the same folder named on PATH is a PATH folder", A.binary("strata")[0] is not None)
        finally:
            os.chdir(old_cwd)
            os.environ["PATH"] = old_path


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
