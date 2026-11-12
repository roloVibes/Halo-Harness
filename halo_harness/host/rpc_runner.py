"""halo_harness.host.rpc_runner -- finding and running llama.cpp's `rpc-server` on a pool worker (Halo 3.3.8.0 R3;
host/ops_rpc.py is the op; docs/HOST.md "rpc_server").

    binary(home=None) -> (argv prefix | None, source line)
        `pool.rpc_server_bin` (a path, or a list: the program and its first arguments), else `rpc-server` on PATH,
        else the rpc-server beside the llama-server Halo would run (`huggingface.llama_server_bin`, PATH, or a runtime
        `halo local serve` fetched: llama.cpp's release archives carry both). Under BRIDGE_TEST_NO_BACKGROUND_NET only a
        configured pool.rpc_server_bin or the SEAMS runner is used: a real rpc-server never starts in a test.
    argv(prefix, *, bind, port, mem_mib) -> [... "-H", bind, "-p", port, "--mem", mem_mib]
    start(argv, log) -> pid       stop(pid) -> how it ended       alive(pid) -> bool
    proto_from_log(log) -> "3.0.0" | None   rpc-server's "Starting RPC server v3.0.0" line

SEAMS (the tests' runner): "start": fn(argv, log_path) -> pid, "stop": fn(pid) -> str, "alive": fn(pid) -> bool. The
real runner is a detached Popen with its output in the log, its environment from providers/config.tool_child_env.
"""

from __future__ import annotations

import os
import shutil
from halo_harness import subprocess_safe as subprocess
import sys
from pathlib import Path
from typing import Optional

SEAMS: dict = {}
EXE = "rpc-server.exe" if sys.platform == "win32" else "rpc-server"


def _beside(prefix: Optional[list]) -> Optional[list]:
    if not prefix:
        return None
    exe = Path(str(prefix[-1]))
    cand = exe.with_name(EXE)
    return [str(cand)] if exe.name.lower().startswith("llama-server") and cand.is_file() else None


def binary(home=None) -> "tuple[Optional[list], str]":
    from halo_harness.config.paths import background_net_disabled
    from halo_harness.theme import get_config_value
    conf = get_config_value("pool.rpc_server_bin", default=None)
    if isinstance(conf, list) and conf and all(isinstance(x, str) for x in conf):
        return list(conf), "pool.rpc_server_bin"
    if isinstance(conf, str) and conf.strip():
        p = Path(conf).expanduser()
        return ([str(p)], "pool.rpc_server_bin") if p.exists() else (None, f"pool.rpc_server_bin names {p}, which is not there")
    if background_net_disabled():
        return None, "under the test flag (BRIDGE_TEST_NO_BACKGROUND_NET) only a configured pool.rpc_server_bin runs"
    found = shutil.which("rpc-server")
    if found:
        return [found], f"rpc-server on PATH ({found})"
    from halo_harness.providers.local_server_cmd import binary as llama
    prefix, why = llama("llama-server", state_dir=home)
    got = _beside(prefix)
    if got:
        return got, f"the rpc-server beside {why}"
    return None, ("rpc-server is not on PATH, pool.rpc_server_bin is not set and no llama.cpp runtime here carries one: "
                  "install llama.cpp (its release archive has rpc-server) or set pool.rpc_server_bin")


def argv(prefix: list, *, bind: str, port: int, mem_mib: Optional[int]) -> list:
    out = list(prefix) + ["-H", str(bind), "-p", str(int(port))]
    return out + ["--mem", str(int(mem_mib))] if isinstance(mem_mib, int) and mem_mib > 0 else out


def start(cmd: list, log: Path) -> int:
    if "start" in SEAMS:
        return int(SEAMS["start"](list(cmd), Path(log)))
    from halo_harness.providers.config import tool_child_env
    Path(log).parent.mkdir(parents=True, exist_ok=True)
    flags = {}
    if os.name == "nt":
        flags["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
    else:
        flags["start_new_session"] = True
    with open(log, "ab") as out:
        out.write(f"--- halo host starts: {' '.join(cmd)}\n".encode("utf-8"))
        out.flush()
        proc = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                env=tool_child_env(dict(os.environ)), **flags)
    return proc.pid


def alive(pid) -> bool:
    if "alive" in SEAMS:
        return bool(SEAMS["alive"](pid))
    from halo_harness.bg_run import pid_alive
    return isinstance(pid, int) and bool(pid_alive(pid))


def stop(pid) -> str:
    if "stop" in SEAMS:
        return str(SEAMS["stop"](pid))
    if not alive(pid):
        return "already gone"
    from halo_harness.providers.local_server_cmd import halt
    return halt(int(pid), grace=5.0)


def proto_from_log(log) -> Optional[str]:
    from halo_harness.local_pool.versions import parse
    try:
        data = Path(log).read_bytes()[-65536:].decode("utf-8", "replace")
    except OSError:
        return None
    return parse(data).get("rpc_proto")
