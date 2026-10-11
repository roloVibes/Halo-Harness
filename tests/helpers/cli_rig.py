"""tests.helpers.cli_rig -- shared pieces for the `halo remote signal` CLI
tests (Halo 2.0.9 round 4): run a verb in-process with captured output and a
non-terminal stdin, write a signal.json that points at the fake one-shot
signal-cli, and build the .tar.gz a mocked download hands back."""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tarfile
import tempfile
from pathlib import Path

ADMIN = Path(__file__).resolve().parent / "fake_signal_admin.py"
FAKE_VARS = ("FAKE_SIGNAL_MODE", "FAKE_SIGNAL_LOG", "FAKE_SIGNAL_VERSION", "HALO_OFFLINE")


class Env:
    """Scoped state home plus fake-signal-cli variables, restored on exit."""

    def __init__(self, mode: str = "ok") -> None:
        keys = ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR") + FAKE_VARS
        self._saved = {k: os.environ.get(k) for k in keys}
        os.environ.pop("BRIDGE_STATE_DIR", None)
        os.environ.pop("HALO_OFFLINE", None)
        self.home = tempfile.mkdtemp(prefix="cli-home-")
        os.environ["BRIDGE_TEST_HOME"] = self.home
        os.environ["FAKE_SIGNAL_MODE"] = mode
        self.log = Path(self.home) / "fake-signal.log"
        os.environ["FAKE_SIGNAL_LOG"] = str(self.log)

    def __enter__(self) -> "Env":
        return self

    def __exit__(self, *exc) -> bool:
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        return False

    def calls(self) -> list:
        try:
            return [json.loads(x) for x in self.log.read_text(encoding="utf-8").splitlines() if x.strip()]
        except OSError:
            return []

    def write_signal_json(self, **kw) -> dict:
        from halo_harness.remote.signal_config import signal_json_path
        data = {"binary": [sys.executable, str(ADMIN)], **kw}
        signal_json_path().write_text(json.dumps(data), encoding="utf-8")
        return data


def run(argv: list, *, top: bool = True, stdin_text: str = "") -> tuple:
    """`(exit code, stdout, stderr)` of `halo remote signal <argv>` run in-process."""
    from halo_harness.remote.cli import cmd_remote
    out, err, saved_in = io.StringIO(), io.StringIO(), sys.stdin
    sys.stdin = io.StringIO(stdin_text)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = cmd_remote((["signal"] if top else []) + list(argv))
    finally:
        sys.stdin = saved_in
    return rc, out.getvalue(), err.getvalue()


def make_archive(dest: Path, native: bool = False) -> None:
    """A tiny stand-in for the signal-cli release tarball (prints a version)."""
    bat = os.name == "nt"
    body = '@echo off\r\necho signal-cli 0.14.9\r\n' if bat else '#!/bin/sh\necho "signal-cli 0.14.9"\n'
    name = "signal-cli.bat" if bat else "signal-cli"
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / name
        f.write_bytes(body.encode("ascii"))
        with tarfile.open(dest, "w:gz") as tar:
            tar.add(f, arcname=name if native and not bat else f"signal-cli-0.14.9/bin/{name}")
