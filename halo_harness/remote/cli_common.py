"""halo_harness.remote.cli_common -- the small helpers every `halo remote
signal ...` verb shares (Halo 2.0.9 round 4): argument parsing that returns
an exit code instead of exiting, `--json` output, `signal.json` updates, a
prompt that falls back to its default when stdin is not a terminal, prefix
lookup, running the signal-cli binary, and QR printing."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
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


def run_cli(cfg: dict, *args: str, account: Optional[str] = None, timeout: float = 120.0,
            json_out: bool = False) -> subprocess.CompletedProcess:
    """Run one signal-cli command to completion (stdin closed, output captured)."""
    Path(cfg["data_dir"]).mkdir(parents=True, exist_ok=True)
    return subprocess.run(cli_argv(cfg, *args, account=account, json_out=json_out), capture_output=True, text=True,
                          timeout=timeout, stdin=subprocess.DEVNULL, encoding="utf-8", errors="replace")


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
