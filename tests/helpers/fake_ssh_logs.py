"""tests.helpers.fake_ssh_logs -- Halo 3.3.6.0 R3: a fake `ssh` runner for the remote server-log reads
(halo_harness/ollama_steward/server_log_remote.py). It answers the read command the way the real `sh -c` / PowerShell
script does on that machine, over a fixture folder that stands for it -- never a real ssh, never a network call.

    FakeRemote(folder, platform="posix" | "windows", journal=None)   folder holds server.log, server-1.log, ...
    runner = fake.runner          runner(argv, timeout) -> stdout text | None (the platform that does not answer)
    fake.calls                    every argv it was given; fake.bytes the stdout sizes
    fake.write(name, data, mtime_s=None)   a file of the set (bytes), with its mtime set when given

On "posix" a `powershell` argv gets None (cmd.exe has no PowerShell answer here); on "windows" an `sh -c` argv gets
None (cmd.exe has no sh). `journal` (a list of lines) makes it a systemd Linux with no ~/.ollama/logs file.
"""

from __future__ import annotations

import base64
import os
import re
from pathlib import Path

_POSIX = re.compile(r"o0=(-?\d+); o1=(-?\d+); t=(\d+)")
_WIN = re.compile(r"\$o = @\((-?\d+), (-?\d+)\); \$t = (\d+)")
_CURSOR = re.compile(r"--after-cursor '([^']*)'")
_N = re.compile(r"-n (\d+)")


class FakeRemote:
    def __init__(self, folder, platform: str = "posix", journal=None) -> None:
        self.folder, self.platform, self.journal = Path(folder), platform, journal
        self.folder.mkdir(parents=True, exist_ok=True)
        self.calls: list = []
        self.bytes: list = []

    def write(self, name: str, data: bytes, mtime_s=None) -> Path:
        p = self.folder / name
        p.write_bytes(data)
        if mtime_s is not None:
            os.utime(p, (mtime_s, mtime_s))
        return p

    def append(self, name: str, data: bytes) -> None:
        with open(self.folder / name, "ab") as f:
            f.write(data)

    def _files(self) -> list:
        return sorted(self.folder.glob("server*.log"), key=lambda p: -p.stat().st_mtime)[:2]

    def _journal(self, script: str) -> str:
        lines = list(self.journal or [])
        m = _CURSOR.search(script)
        if m:
            start = int(m.group(1).split("=")[-1]) + 1
        else:
            n = int((_N.search(script) or [None, "1"])[1])
            start = max(0, len(lines) - n)
        out = ["@@HALO-JOURNAL"] + lines[start:] + [f"-- cursor: s=fake;i={len(lines) - 1}"]
        return "\n".join(out) + "\n"

    def _files_out(self, o: list, t: int, where: str) -> str:
        files = self._files()
        if not files:
            return "@@HALO-NONE\n"
        out = []
        for i, f in enumerate(files):
            data = f.read_bytes()
            out.append(f"@@HALO-FILE {i} {len(data)} {where}{f.name}")
            out.append(base64.b64encode(data[:200]).decode("ascii"))
            out.append("@@HALO-DATA")
            if t > 0:
                out.append(base64.b64encode(data[-t:]).decode("ascii"))
            elif 0 <= o[i] < len(data):
                out.append(base64.b64encode(data[o[i]:o[i] + 1024 * 1024]).decode("ascii"))
        return "\n".join(out) + "\n"

    def runner(self, argv, timeout):
        self.calls.append(list(argv))
        if argv[:2] == ["sh", "-c"]:
            if self.platform != "posix":
                return None
            script = argv[2]
            if self.journal is not None:
                out = self._journal(script)
            else:
                m = _POSIX.search(script)
                out = self._files_out([int(m.group(1)), int(m.group(2))], int(m.group(3)), "/home/example/.ollama/logs/")
        elif argv and argv[0] == "powershell":
            if self.platform != "windows":
                return None
            script = base64.b64decode(argv[-1]).decode("utf-16-le")
            m = _WIN.search(script)
            out = self._files_out([int(m.group(1)), int(m.group(2))], int(m.group(3)),
                                  "C:\\Users\\example\\AppData\\Local\\Ollama\\")
        else:
            return None
        self.bytes.append(len(out))
        return out
