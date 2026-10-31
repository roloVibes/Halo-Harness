"""halo_harness.ollama_steward.server_log_remote -- Halo 3.3.6.0 R3: the server log of a host this machine does not
serve, read through its `ssh:` entry (plans/local-model-fit-brief.md D3 item 13; server_log.read_new's seam).

    read_new_remote(state_dir, host, *, runner=None, from_start=False, timeout=5.0) -> (lines, why)
    host_state(state_dir, name) -> {...}         what the last read of that host left
    argv_for(platform, ...) / parse(out) / runner_for(host)   the command, its output, the runner (log_tail.py's too)

One command per read over providers/ollama_hw.run_via_ssh (`ssh -o BatchMode=yes`):
- macOS, a Linux user install: `sh -c` over `~/.ollama/logs/server*.log` (the rotation set by mtime, the newest two):
  each file's size, its first 200 bytes and the bytes from the saved offset (at most MAX_BYTES), as base64, so an
  invalid UTF-8 byte is decoded here with errors="replace" and the offsets stay exact; with no such file and
  journalctl there (a systemd Linux): `journalctl -u ollama -o cat --show-cursor`, `--after-cursor` the saved cursor;
- Windows: `powershell -NoProfile -EncodedCommand` over `%LOCALAPPDATA%\\Ollama\\server*.log` the same way.
The platform that answered is kept. Per host (`<state>/ollama/server-log-remote.json`): {platform, offset, head,
cursor, ok_at, why, last_line_at, bytes, read_at, path, quiet}. A rotation (the newest file's head changed) reads the
old file (now the second newest) from the saved offset and the new one from its top, in a second command. Nothing
here writes on that machine or changes a setting.
"""

from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from typing import Callable, Optional

STATE_FILE = "server-log-remote.json"
MAX_BYTES = 1024 * 1024
TAIL_BYTES = 256 * 1024
REMOTE_S = 30.0
SEAMS: dict = {}  # "ssh": fn(host) -> runner(argv, timeout) (the tests' seam: never a real ssh in a test)

_POSIX = """d="$HOME/.ollama/logs"; o0=__O0__; o1=__O1__; t=__T__; i=0
if ls "$d"/server*.log >/dev/null 2>&1; then
  for f in $(ls -t "$d"/server*.log | head -n 2); do
    s=$(wc -c < "$f" | tr -d ' ')
    echo "@@HALO-FILE $i $s $f"
    head -c 200 "$f" | base64
    echo "@@HALO-DATA"
    if [ $i -eq 0 ]; then o=$o0; else o=$o1; fi
    if [ "$t" -gt 0 ]; then tail -c "$t" "$f" | base64
    elif [ "$o" -ge 0 ] && [ "$o" -lt "$s" ]; then tail -c +$((o+1)) "$f" | head -c __MAX__ | base64; fi
    i=$((i+1))
  done
elif command -v journalctl >/dev/null 2>&1; then
  echo "@@HALO-JOURNAL"
  journalctl -u ollama -o cat --no-pager --show-cursor __J__
else
  echo "@@HALO-NONE"
fi"""

_WINDOWS = """$ErrorActionPreference = 'SilentlyContinue'
$d = Join-Path $env:LOCALAPPDATA 'Ollama'
$fs = @(Get-ChildItem -Path $d -Filter 'server*.log' | Sort-Object LastWriteTime -Descending | Select-Object -First 2)
if ($fs.Count -eq 0) { '@@HALO-NONE'; exit 0 }
$o = @(__O0__, __O1__); $t = __T__; $i = 0
foreach ($f in $fs) {
  $s = [IO.File]::Open($f.FullName, 'Open', 'Read', 'ReadWrite'); $n = $s.Length
  '@@HALO-FILE ' + $i + ' ' + $n + ' ' + $f.FullName
  $h = New-Object byte[] ([Math]::Min(200, $n)); [void]$s.Read($h, 0, $h.Length); [Convert]::ToBase64String($h)
  '@@HALO-DATA'
  $from = -1
  if ($t -gt 0) { $from = [Math]::Max(0, $n - $t) } elseif ($o[$i] -ge 0 -and $o[$i] -lt $n) { $from = $o[$i] }
  if ($from -ge 0) { $k = [Math]::Min(__MAX__, $n - $from); $b = New-Object byte[] $k; [void]$s.Seek($from, 0)
    [void]$s.Read($b, 0, $k); [Convert]::ToBase64String($b) }
  $s.Close(); $i++
}"""


def argv_for(platform: str, o0: int = -1, o1: int = -1, tail: int = 0, jargs: str = "-n 1") -> list:
    fill = {"__O0__": str(int(o0)), "__O1__": str(int(o1)), "__T__": str(int(tail)), "__MAX__": str(MAX_BYTES), "__J__": jargs}
    text = _WINDOWS if platform == "windows" else _POSIX
    for k, v in fill.items():
        text = text.replace(k, v)
    if platform == "windows":
        return ["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand",
                base64.b64encode(text.encode("utf-16-le")).decode("ascii")]
    return ["sh", "-c", text]


def parse(out) -> dict:
    """The command's output -> {kind: files | journal | none, files: [{size, path, head, data (bytes)}], lines}."""
    text = out.decode("utf-8", "replace") if isinstance(out, (bytes, bytearray)) else str(out or "")
    if "@@HALO-NONE" in text:
        return {"kind": "none", "files": [], "lines": []}
    if "@@HALO-JOURNAL" in text:
        return {"kind": "journal", "files": [], "lines": text.split("@@HALO-JOURNAL", 1)[1].splitlines()}
    files, cur, part = [], None, "head"
    for line in text.splitlines():
        if line.startswith("@@HALO-FILE "):
            bits = line.split(" ", 3)
            cur = {"size": int(bits[2]) if len(bits) > 2 and bits[2].isdigit() else 0,
                   "path": bits[3] if len(bits) > 3 else "", "head": [], "data": []}
            files.append(cur)
            part = "head"
        elif line.startswith("@@HALO-DATA"):
            part = "data"
        elif cur is not None and line.strip():
            cur[part].append(line.strip())
    for f in files:
        for k in ("head", "data"):
            try:
                f[k] = base64.b64decode("".join(f[k]))
            except ValueError:
                f[k] = b""
        f["head"] = f["head"].decode("utf-8", "replace")
    return {"kind": "files" if files else "none", "files": files, "lines": []}


def _whole(data: bytes) -> "tuple[list, int]":
    end = data.rfind(b"\n")
    if end < 0:
        return [], 0
    return [x.rstrip("\r") for x in data[:end].decode("utf-8", "replace").split("\n")], end + 1


def runner_for(host, runner: Optional[Callable] = None, timeout: float = 5.0) -> "tuple[Optional[Callable], Optional[str]]":
    if runner is not None:
        return runner, None
    if not getattr(host, "ssh", None):
        return None, "no ssh entry for this host"
    if "ssh" in SEAMS:
        return SEAMS["ssh"](host), None
    from halo_harness.config.paths import background_net_disabled
    if background_net_disabled():
        return None, "background reads are off"
    from halo_harness.providers.ollama_hw import run_via_ssh
    return run_via_ssh(host.ssh, timeout=timeout), None


def _call(run, st: dict, timeout: float, **kw) -> Optional[dict]:
    """One command on the platform that answered last (the first time: POSIX, then Windows)."""
    for platform in ([st["platform"]] if st.get("platform") else ["posix", "windows"]):
        out = run(argv_for(platform, **kw), timeout)
        if out is not None:
            st["platform"], st["bytes"] = platform, len(out)
            return parse(out)
    return None


def _path(state_dir) -> Path:
    from halo_harness.ollama_steward.ledger import ledger_dir
    return ledger_dir(state_dir) / STATE_FILE


def _load(state_dir) -> dict:
    try:
        d = json.loads(_path(state_dir).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def host_state(state_dir, name: str) -> dict:
    return dict(_load(state_dir).get(name) or {})


def _save(state_dir, name: str, st: dict) -> None:
    try:
        p = _path(state_dir)
        p.parent.mkdir(parents=True, exist_ok=True)
        all_ = _load(state_dir)
        all_[name] = st
        p.write_text(json.dumps(all_), encoding="utf-8")
    except OSError:
        pass


def _newest_time(lines: list, before: Optional[float]) -> Optional[float]:
    from halo_harness.ollama_steward.server_rules import line_time, strip_prefix
    times = [t for t in (line_time(strip_prefix(x)) for x in lines[-400:]) if t is not None]
    return max(times + ([before] if isinstance(before, (int, float)) else [])) if times or before else None


def _read(run, st: dict, from_start: bool, timeout: float) -> "tuple[list, Optional[str]]":
    first = "offset" not in st and "cursor" not in st
    jargs = f"--after-cursor '{st['cursor']}'" if st.get("cursor") else ("-n 5000" if from_start else "-n 1")
    got = _call(run, st, timeout, o0=(0 if from_start else (-1 if first else int(st.get("offset") or 0))), jargs=jargs)
    if got is None:
        return [], "the ssh read did not answer"
    if got["kind"] == "none":
        return [], "no server log on that machine (no ~/.ollama/logs/server*.log, no journal, no %LOCALAPPDATA%\\Ollama)"
    if got["kind"] == "journal":
        lines = []
        for line in got["lines"]:
            if line.startswith("-- cursor: "):
                st["cursor"] = line[len("-- cursor: "):].strip()
            elif line.strip() and not line.startswith("-- No entries --"):
                lines.append(line)
        st["path"] = "journalctl -u ollama"
        return ([] if first and not from_start else lines), None
    newest = got["files"][0]
    st["path"] = newest["path"]
    if first and not from_start:
        st.update(offset=newest["size"], head=newest["head"])
        return [], None
    from halo_harness.ollama_steward.ledger import same_file
    off = 0 if from_start else int(st.get("offset") or 0)
    if (st.get("head") and not same_file(st["head"], newest["head"])) or newest["size"] < off:
        again = _call(run, st, timeout, o0=0, o1=off) or {"files": []}  # a rotation: the old file is the second now
        files = again.get("files") or []
        old = files[1]["data"] if len(files) > 1 and same_file(st.get("head") or "", files[1]["head"]) else b""
        newest = files[0] if files else newest
        lines_old, _ = _whole(old)
        lines_new, used = _whole(newest["data"])
        st.update(offset=used, head=newest["head"])
        return lines_old + lines_new, None
    lines, used = _whole(newest["data"])
    st.update(offset=off + used, head=st.get("head") or newest["head"])
    return lines, None


def read_new_remote(state_dir, host, *, runner: Optional[Callable] = None, from_start: bool = False,
                    timeout: float = 5.0) -> "tuple[list, Optional[str]]":
    """The new lines of `host`'s server log since the last read (the first read starts at its end)."""
    run, why = runner_for(host, runner, timeout)
    st = host_state(state_dir, host.name)
    if run is None:
        return [], f"the server log of '{host.name}' is on that machine ({why})"
    from halo_harness.filelock import file_lock
    with file_lock(_path(state_dir), timeout=timeout) as held:
        if not held:
            return [], "another read of that log is running"
        st = host_state(state_dir, host.name)
        if from_start:
            st = {"platform": st.get("platform"), "quiet": st.get("quiet") or {}}
        lines, why = _read(run, st, from_start, timeout)
        now = time.time()
        st.update(read_at=now, why=why, **({"ok_at": now} if why is None else {}))
        st["last_line_at"] = _newest_time(lines, st.get("last_line_at"))
        st["debug"] = any("level=DEBUG" in x for x in lines[-400:]) or (bool(st.get("debug")) and not lines)
        _save(state_dir, host.name, st)
    return lines, (None if why is None else f"{host.name}: {why}")
