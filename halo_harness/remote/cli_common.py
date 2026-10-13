"""halo_harness.remote.cli_common -- the small helpers every `halo remote
signal ...` verb shares (Halo 2.0.9 round 4): argument parsing that returns
an exit code instead of exiting, `--json` output, `signal.json` updates, a
prompt that falls back to its default when stdin is not a terminal, prefix
lookup, running the signal-cli binary, and QR printing."""

from __future__ import annotations

import argparse
import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

from halo_harness.privateio import write_private_atomic
from halo_harness.remote.signal_config import load_signal_config, signal_json_path


def make_parser(verb: str, description: str, *, json_flag: bool = True) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=f"halo remote signal {verb}", description=description)
    if json_flag:
        p.add_argument("--json", action="store_true", help="print the result as JSON")
    return p


def parse(p: argparse.ArgumentParser, argv: list) -> "tuple[Optional[argparse.Namespace], int]":
    """`(namespace, 0)`; or `(None, code)` when `-h` was given (0) or the
    arguments were wrong (2, after argparse printed why)."""
    try:
        return p.parse_args(argv), 0
    except SystemExit as e:
        return None, (0 if e.code in (0, None) else 2)


def emit_json(obj) -> None:
    print(json.dumps(obj, indent=2, sort_keys=True))


def fail(as_json: bool, error: str, message: str, **extra) -> int:
    if as_json:
        emit_json({"ok": False, "error": error, "message": message, **extra})
    else:
        print(message, file=sys.stderr)
    return 1


def save_signal_config(**updates) -> dict:
    """Merge `updates` into signal.json (unknown keys kept); returns the file's content."""
    path = signal_json_path()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        data = raw if isinstance(raw, dict) else {}
    except (OSError, ValueError):
        data = {}
    data.update(updates)
    write_private_atomic(path, json.dumps(data, indent=2, sort_keys=True) + "\n")
    return data


def ask(prompt: str, default: str = "") -> str:
    """One line from the user; `default` when stdin is not a terminal or is closed."""
    if not sys.stdin or not sys.stdin.isatty():
        return default
    try:
        return input(prompt).strip() or default
    except EOFError:
        return default


def interactive() -> bool:
    return bool(sys.stdin and sys.stdin.isatty())


def resolve_prefix(keys: list, prefix: str, what: str = "sender") -> tuple:
    """`(key, "")` for the one key starting with `prefix`, else `(None, message)`."""
    hits = [k for k in keys if k.startswith(prefix.strip())] if prefix.strip() else []
    if len(hits) == 1:
        return hits[0], ""
    if not hits:
        return None, f"No {what} matches {prefix!r}."
    return None, f"{prefix!r} matches {len(hits)} {what}s; use more characters."


def binary_words(cfg: dict) -> list:
    b = cfg.get("binary") or "signal-cli"
    return [str(x) for x in b] if isinstance(b, (list, tuple)) else [str(b)]


def cli_argv(cfg: dict, *args: str, account: Optional[str] = None, json_out: bool = False) -> list:
    argv = binary_words(cfg)
    if account:
        argv += ["-a", account]
    if json_out:
        argv += ["-o", "json"]
    return argv + ["-d", str(cfg["data_dir"])] + [str(a) for a in args]


def child_env() -> dict:
    """The environment for signal-cli, java and the other third-party binaries the remote verbs
    run: this process's environment minus every provider key (2.0.7 finding 19)."""
    from halo_harness.providers.config import tool_child_env
    return tool_child_env(dict(os.environ))


def run_cli(cfg: dict, *args: str, account: Optional[str] = None, timeout: float = 120.0,
            json_out: bool = False) -> subprocess.CompletedProcess:
    """Run one signal-cli command to completion (stdin closed, output captured)."""
    Path(cfg["data_dir"]).mkdir(parents=True, exist_ok=True)
    return subprocess.run(cli_argv(cfg, *args, account=account, json_out=json_out), capture_output=True, text=True,
                          timeout=timeout, stdin=subprocess.DEVNULL, encoding="utf-8", errors="replace",
                          env=child_env())


class RpcResult:
    """`ok`, the JSON-RPC `result`, or the `code`/`message` of the error (code None: no answer at all)."""

    def __init__(self, ok: bool, result=None, code=None, message: str = "") -> None:
        self.ok, self.result, self.code, self.message = ok, result, code, message

    @property
    def unsupported(self) -> bool:
        return self.code == -32601  # method not found: the caller may choose another route


def rpc_once(cfg: dict, method: str, params: dict, *, account: Optional[str] = None,
             timeout: float = 120.0) -> RpcResult:
    """One JSON-RPC call through a short-lived `signal-cli jsonRpc` child (2.0.10 review finding 23).
    The parameters travel on the child's stdin, so a PIN or code never appears in `ps`. The child
    is closed as soon as its answer arrives."""
    Path(cfg["data_dir"]).mkdir(parents=True, exist_ok=True)
    argv = binary_words(cfg) + (["-a", account] if account else []) + ["-d", str(cfg["data_dir"]),
                                                                       "jsonRpc", "--receive-mode", "manual"]
    try:
        proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                text=True, encoding="utf-8", errors="replace", env=child_env())
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


def configured(as_json: bool = False) -> "tuple[Optional[dict], int]":
    """`(cfg, 0)` when signal.json names a binary, else `(None, 1)` after saying what to run."""
    cfg = load_signal_config()
    if not signal_json_path().exists() or not cfg.get("binary"):
        return None, fail(as_json, "not_set_up", "signal-cli is not set up yet. Run `halo remote signal setup`.")
    return cfg, 0


def print_qr(text: str, ascii_only: bool = False) -> None:
    """The QR of `text` as half-blocks (ASCII `##` when asked, or when the
    terminal's encoding cannot draw blocks); the text is printed by the caller."""
    from halo_harness.remote import qr
    try:
        matrix = qr.encode(text)
    except qr.QrTooLong as e:
        print(f"(no QR code: {e})")
        return
    art = qr.render_ascii(matrix) if ascii_only else qr.render(matrix)
    enc = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        art.encode(enc)
    except (UnicodeEncodeError, LookupError):
        art = qr.render_ascii(matrix)
    print(art)
