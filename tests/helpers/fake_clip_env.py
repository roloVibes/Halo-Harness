"""tests.helpers.fake_clip_env -- a Linux clipboard environment on any build
host (3.1.6.0 R5): `sys.platform` reads "linux" for tui/clipboard.py (its
`_platform()` seam), PATH is one fresh bin directory (empty, or holding fake
`xclip` / `wl-copy` / `xsel` tools that write stdin to a sink file), the
display/terminal/SSH/tmux variables are scrubbed and set only as asked, and
the state dir is a fresh scratch folder. Everything is restored on exit.

Usage:
    with LinuxClipEnv(tools=("xclip",), env={"DISPLAY": ":0"}) as clip:
        ... copy ...
        clip.sink("xclip")        # what the fake xclip received ('' if never run)
        clip.state_dir            # where clipboard.txt lands
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

SCRUBBED = ("SSH_CONNECTION", "SSH_CLIENT", "SSH_TTY", "TMUX", "TERM_PROGRAM", "TERMINAL",
            "COLORTERM", "KONSOLE_VERSION", "VTE_VERSION", "WAYLAND_DISPLAY", "DISPLAY",
            "BRIDGE_STATE_DIR", "BRIDGE_TEST_HOME")

_TOOL_SCRIPT = """import sys
data = sys.stdin.buffer.read()
with open({sink!r}, "wb") as f:
    f.write(data)
if {fail!r}:
    sys.stderr.write("Error: Can't open display: (null)\\n")
    sys.exit(1)
"""


def _write_tool(bin_dir: Path, name: str, sink: Path, *, fail: bool) -> None:
    script = bin_dir / f"_{name}_impl.py"
    script.write_text(_TOOL_SCRIPT.format(sink=str(sink), fail=fail), encoding="utf-8")
    if sys.platform == "win32":
        launcher = bin_dir / f"{name}.bat"
        launcher.write_text(f'@"{sys.executable}" "{script}" %*\r\n', encoding="utf-8")
    else:
        launcher = bin_dir / name
        launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding="utf-8")
        launcher.chmod(0o755)


class LinuxClipEnv:
    def __init__(self, *, tools=(), failing=(), env=None) -> None:
        self.tools = tuple(tools)
        self.failing = tuple(failing)
        self.env = dict(env or {})
        self.root = Path(tempfile.mkdtemp(prefix="halo-clipenv-"))
        self.bin_dir = self.root / "bin"
        self.state_dir = self.root / "state"

    def sink(self, name: str) -> str:
        path = self.root / f"{name}.sink"
        return path.read_bytes().decode("utf-8") if path.exists() else ""

    def __enter__(self) -> "LinuxClipEnv":
        import halo_harness.tui.clipboard as cb
        self._cb = cb
        self._saved_env = {k: os.environ.get(k) for k in (*SCRUBBED, "PATH", *self.env)}
        self._saved_platform = cb._platform
        for key in SCRUBBED:
            os.environ.pop(key, None)
        self.bin_dir.mkdir(parents=True)
        self.state_dir.mkdir(parents=True)
        for name in (*self.tools, *self.failing):
            _write_tool(self.bin_dir, name, self.root / f"{name}.sink", fail=name in self.failing)
        os.environ["PATH"] = str(self.bin_dir)
        os.environ["BRIDGE_TEST_HOME"] = str(self.root)
        os.environ["BRIDGE_STATE_DIR"] = str(self.state_dir)
        os.environ.update(self.env)
        cb._platform = lambda: "linux"
        cb._TMUX_MODE_CACHE.clear()
        return self

    def __exit__(self, *exc) -> bool:
        self._cb._platform = self._saved_platform
        self._cb._TMUX_MODE_CACHE.clear()
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        return False
