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

    def why(self) -> str:
        """For a failure message: what the last external copy said, and whether the fallback file was written."""
        saved = self.state_dir / "clipboard.txt"
        found = self._cb.find_clipboard_tool()
        return (f"(last copy error {self._cb.last_copy_error()!r}; clipboard.txt written: {saved.exists()}; "
                f"find -> {found!r}; PATH={os.environ.get('PATH')!r})")

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
        self._saved_tools = cb._LINUX_CLIPBOARD_TOOLS
        if sys.platform == "win32":
            # a Windows build host runs the fake through its own interpreter, not a .bat through cmd.exe
            # (the GitHub Windows runner never delivered the text to the .bat launcher; a POSIX host keeps
            # the real shape: the tool's name found on PATH)
            fakes = {*self.tools, *self.failing}
            cb._LINUX_CLIPBOARD_TOOLS = tuple(
                (name, [sys.executable, str(self.bin_dir / f"_{name}_impl.py"), *argv[1:]]) if name in fakes else (name, argv)
                for name, argv in self._saved_tools)
        self._saved_find = cb.find_clipboard_tool
        if sys.platform == "win32" and (self.tools or self.failing):
            # On a Windows host the detector is answered from the table above, not from a PATH search:
            # the GitHub Windows runner found the fake on PATH when called directly but not from the TUI's
            # clipboard worker (why is still unknown); the PATH search itself is pinned by the detection
            # test, which uses no running tool. A POSIX host keeps the real detector.
            table, fakes, session = cb._LINUX_CLIPBOARD_TOOLS, {*self.tools, *self.failing}, cb.TOOL_SESSION_VAR

            def _find():
                found = [(name, list(argv)) for name, argv in table if name in fakes]
                for name, argv in found:
                    if os.environ.get(session.get(name, "")):
                        return name, argv
                return found[0] if found else None
            cb.find_clipboard_tool = _find
        self.probe_error = self._probe()
        return self

    def _probe(self) -> "Optional[str]":
        """Run the first fake tool once the way the detector would; '' lands -> None, else why (a host where
        the fake cannot run skips the tests that need it, with this reason in the SKIP line)."""
        if not self.tools:
            return None
        import subprocess
        found = self._cb.find_clipboard_tool()
        if found is None:
            return f"find_clipboard_tool() found nothing on PATH={os.environ.get('PATH')!r}"
        name, argv = found
        try:
            p = subprocess.run(argv, input=b"probe", capture_output=True, timeout=30)
        except (OSError, subprocess.SubprocessError) as exc:
            return f"{name} {argv[0]!r} did not run: {exc}"
        got = self.sink(name)
        sink = self.root / f"{name}.sink"
        if sink.exists():
            sink.unlink()
        if p.returncode != 0 or got != "probe":
            return (f"{name} {argv[0]!r} rc={p.returncode} stdout={p.stdout[:200]!r} stderr={p.stderr[:300]!r} "
                    f"sink={got!r}")
        return None

    def __exit__(self, *exc) -> bool:
        self._cb.find_clipboard_tool = self._saved_find
        self._cb._LINUX_CLIPBOARD_TOOLS = self._saved_tools
        self._cb._platform = self._saved_platform
        self._cb._TMUX_MODE_CACHE.clear()
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        return False
