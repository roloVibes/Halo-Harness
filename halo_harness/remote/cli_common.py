"""halo_harness.remote.cli_common -- the small helpers the core's CLI verbs share (Halo 2.0.9 round 4, written for
`halo remote signal`; 3.3.13.0 R3: the Signal verbs and their signal.json helpers left with the signal pack, these
stay for `halo fleet`, `halo host`, `halo pool` and `halo remote`): argument parsing that returns an exit code
instead of exiting, `--json` output, a failure line, a prompt that falls back to its default when stdin is not a
terminal, and QR printing."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional


def make_parser(verb: str, description: str, *, json_flag: bool = True, prog: str = "halo remote") -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=f"{prog} {verb}", description=description)
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
