"""halo_harness.tensorfold.requirements -- the TensorFold binary and what it says about itself, read without changing
anything (Halo 3.3.9.3; docs/MODELS-tensorfold.md "Install").

Where the binary comes from, in order: `huggingface.tensorfold_bin` (a path, or the program and its first arguments:
the tests' seam, tests/helpers/fake_tensorfold_server.py), then `tensorfold` or `tensorfold-native` on PATH (Homebrew
links both on the Mac: packaging/homebrew/tensorfold.rb.in), then the Linux release archive Halo fetched
(`~/.halo/runtimes/tensorfold-<tag>/tensorfold-<v>-<platform>/bin/tensorfold-native`, newest tag first; never on PATH).
From the source, unverified against a live run: `tensorfold-native --version` prints "tensorfold-native <version>" (the
formula's test), `tensorfold capabilities --json` prints {"schema": 1, "engine": "zig", "version", "chip", "backends":
[...], "families": {...}, "serve": {"flags": {...}}, "env": [...], ...} (zig/src/server/cli_capabilities.zig).

    binary(state_dir=None) -> (argv prefix | None, where from)
    os_word() -> "macos" | "linux" | "windows" | ...     machine() -> "x86_64" | "arm64" | ...
    version(prefix) -> "1.2.1" | None                  capabilities(prefix) -> dict | None
    check(state_dir=None) -> {ok, tensorfold, tensorfold_from, version, backends, os, machine, line}
        `line`: one line with the install route for THIS OS when the binary is missing or silent; "" when it answered
    SEAMS: {"run": fn(argv) -> (rc, text), "which": fn(name) -> path | None, "os": fn() -> word, "machine": fn()}
Each probe is one short local command, never a model, never the network.
"""

from __future__ import annotations

import json
import platform as _platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

from halo_harness.tensorfold import install_line

SEAMS: dict = {}
_VERSION = re.compile(r"^tensorfold(?:-native)? v?(\S+)", re.M)


def _run(argv: list, timeout: float = 20.0) -> "tuple[int, str]":
    if "run" in SEAMS:
        return SEAMS["run"](list(argv))
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError) as e:
        return 127, str(e)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def os_word() -> str:
    if "os" in SEAMS:
        return SEAMS["os"]()
    p = sys.platform
    return "linux" if p.startswith("linux") else "macos" if p == "darwin" else "windows" if p.startswith("win") else p


def machine() -> str:
    return SEAMS["machine"]() if "machine" in SEAMS else (_platform.machine() or "").lower()


def _state(state_dir):
    if state_dir is not None:
        return state_dir
    from halo_harness.config.paths import bridge_home
    return bridge_home()


def fetched(state_dir=None) -> Optional[Path]:
    """The newest fetched archive's binary under `~/.halo/runtimes/tensorfold-<tag>/`, or None."""
    from halo_harness.providers.local_runtime import runtimes_dir
    root = runtimes_dir(_state(state_dir))
    try:
        dirs = sorted((p for p in root.iterdir() if p.is_dir() and p.name.startswith("tensorfold-")), reverse=True)
    except OSError:
        return None
    for d in dirs:
        for cand in sorted(d.rglob("tensorfold-native*")):  # the Linux archive's bin/tensorfold-native (.exe: a build)
            if cand.is_file() and cand.name in ("tensorfold-native", "tensorfold-native.exe"):
                return cand
    return None


def binary(state_dir=None) -> "tuple[Optional[list], str]":
    from halo_harness.theme import get_config_value
    raw = get_config_value("huggingface.tensorfold_bin", default=None)
    if isinstance(raw, list) and raw and all(isinstance(x, str) for x in raw):
        return list(raw), "huggingface.tensorfold_bin"
    if isinstance(raw, str) and raw.strip():
        return [raw.strip()], "huggingface.tensorfold_bin"
    which = SEAMS.get("which") or shutil.which
    for name in ("tensorfold", "tensorfold-native"):
        found = which(name)
        if found:
            return [found], f"{name} on PATH"
    got = fetched(state_dir)
    return ([str(got)], f"the release Halo fetched ({got.parent.parent.parent.name})") if got else (None, "")


def version(prefix: Optional[list]) -> Optional[str]:
    if not prefix:
        return None
    rc, out = _run(list(prefix) + ["--version"])
    m = _VERSION.search(out) if rc == 0 else None
    return m.group(1) if m else None


def capabilities(prefix: Optional[list]) -> Optional[dict]:
    """`tensorfold capabilities --json` parsed, or None (an older binary, or no answer)."""
    if not prefix:
        return None
    rc, out = _run(list(prefix) + ["capabilities", "--json"])
    if rc != 0:
        return None
    start = out.find("{")
    try:
        got = json.loads(out[start:]) if start >= 0 else None
    except ValueError:
        return None
    return got if isinstance(got, dict) else None


def missing_line(os_name: str, arch: str, *, found: bool) -> str:
    head = "tensorfold did not answer --version" if found else "no tensorfold binary (huggingface.tensorfold_bin, PATH)"
    return f"{head}: {install_line(os_name, arch)}"


def check(state_dir=None) -> dict:
    os_name, arch = os_word(), machine()
    prefix, src = binary(state_dir)
    v = version(prefix) if prefix else None
    caps = capabilities(prefix) if v else None
    backends = [str(b) for b in (caps or {}).get("backends") or []]
    line = "" if v else missing_line(os_name, arch, found=prefix is not None)
    return {"ok": bool(v), "tensorfold": prefix, "tensorfold_from": src, "version": v, "backends": backends,
            "capabilities": caps, "os": os_name, "machine": arch, "line": line}
