"""halo_signal.signalcli -- one-shot signal-cli runs for the account verbs (link, register, verify, listAccounts):

    cli_argv(cfg, *args, account=None, json_out=False) -> argv
    run_cli(cfg, *args, account=None, timeout=120, json_out=False) -> CompletedProcess   stdin closed, output captured
    rpc_once(cfg, method, params, account=None, timeout=120) -> RpcResult   one JSON-RPC call through a short-lived
        `signal-cli jsonRpc` child: the parameters travel on its stdin, so a PIN or a code never shows in `ps`

Every run gets this process's environment, which never holds Halo's provider keys (a pack command or a service
runs with them taken out). Not used while the bridge runs: signal-cli keeps one process per data folder.
"""

from __future__ import annotations

import json
import queue
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

from halo_signal.settings import binary_words


def cli_argv(cfg: dict, *args: str, account: Optional[str] = None, json_out: bool = False) -> list:
    argv = binary_words(cfg)
    if account:
        argv += ["-a", account]
    if json_out:
        argv += ["-o", "json"]
    return argv + ["-d", str(cfg["data_dir"])] + [str(a) for a in args]


def run_cli(cfg: dict, *args: str, account: Optional[str] = None, timeout: float = 120.0,
            json_out: bool = False) -> subprocess.CompletedProcess:
    Path(cfg["data_dir"]).mkdir(parents=True, exist_ok=True)
    return subprocess.run(cli_argv(cfg, *args, account=account, json_out=json_out), capture_output=True, text=True,
                          timeout=timeout, stdin=subprocess.DEVNULL, encoding="utf-8", errors="replace")


class RpcResult:
    def __init__(self, ok: bool, result=None, code=None, message: str = "") -> None:
        self.ok, self.result, self.code, self.message = ok, result, code, message

    @property
    def unsupported(self) -> bool:
        return self.code == -32601


def rpc_once(cfg: dict, method: str, params: dict, *, account: Optional[str] = None,
             timeout: float = 120.0) -> RpcResult:
    Path(cfg["data_dir"]).mkdir(parents=True, exist_ok=True)
    argv = binary_words(cfg) + (["-a", account] if account else []) + ["-d", str(cfg["data_dir"]), "jsonRpc",
                                                                       "--receive-mode", "manual"]
    try:
        proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                text=True, encoding="utf-8", errors="replace")
    except OSError as e:
        return RpcResult(False, message=str(e))
    lines: "queue.Queue" = queue.Queue()
    threading.Thread(target=lambda: ([lines.put(x) for x in proc.stdout], lines.put(None)), daemon=True).start()
    rid = "halo-1"
    try:
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": rid, "method": method, "params": params}) + "\n")
        proc.stdin.flush()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                line = lines.get(timeout=0.2)
            except queue.Empty:
                continue
            if line is None:
                break
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if isinstance(msg, dict) and msg.get("id") == rid:
                err = msg.get("error")
                if isinstance(err, dict):
                    return RpcResult(False, code=err.get("code"), message=str(err.get("message") or ""))
                return RpcResult(True, result=msg.get("result"))
        return RpcResult(False, message="signal-cli did not answer")
    except OSError as e:
        return RpcResult(False, message=str(e))
    finally:
        for fn in (proc.stdin.close, proc.terminate):
            try:
                fn()
            except OSError:
                pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
