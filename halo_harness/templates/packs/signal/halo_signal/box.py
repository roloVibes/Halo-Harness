"""halo_signal.box -- signal-cli and Java on this machine (Setup's "Signal on this box" and `/signal status`).

The pack never installs signal-cli: pack.yaml's `requires:` names it with its install line per OS (Halo's rule for a
tool a pack wraps), and this module only looks.

    find(cfg) -> (argv | None, line)    signal.json's `binary` when it runs, else `signal-cli` on PATH
    version_of(argv) -> "0.14.9" | None
    java_major() -> 25 | None           `java -version` (the JVM build of signal-cli needs a JRE 25 or newer)
    native_host()                       Linux x86-64: the native build, no Java
    install_line(os_name=None)          the line for this OS (pack.yaml's requires entry says the same)
    report(cfg) -> [line]               what Setup's check prints

signal-cli (https://github.com/AsamK/signal-cli) is GPL-3.0: the pack calls the installed program and carries none of
its code. Every program here runs with the service's environment, which never holds Halo's provider keys.
"""

from __future__ import annotations

import re
import shutil
from halo_harness.ext import subprocess_safe as subprocess
import sys
from typing import Optional

MIN_JRE = 25
TESTED = "0.14.9"
INSTALL = {
    "windows": "winget install EclipseAdoptium.Temurin.25.JRE, then unpack signal-cli-<version>.tar.gz from "
               "https://github.com/AsamK/signal-cli/releases and add its bin folder to PATH",
    "linux": "unpack signal-cli-<version>-Linux-native.tar.gz from https://github.com/AsamK/signal-cli/releases into "
             "~/.local (no Java needed on x86-64) and put ~/.local/signal-cli-<version>/bin on PATH",
    "mac": "brew install signal-cli",
}


def os_name(platform: Optional[str] = None) -> str:
    p = platform if platform is not None else sys.platform
    return "windows" if p.startswith("win") else ("mac" if p == "darwin" else "linux")


def install_line(os_n: Optional[str] = None) -> str:
    return INSTALL[os_n or os_name()]


def native_host(platform: Optional[str] = None, machine: Optional[str] = None) -> bool:
    import platform as _p
    plat = platform if platform is not None else sys.platform
    arch = (machine if machine is not None else _p.machine()).lower()
    return plat.startswith("linux") and arch in ("x86_64", "amd64")


def java_major(runner=subprocess.run) -> Optional[int]:
    if shutil.which("java") is None:
        return None
    try:
        res = runner(["java", "-version"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r'version "(\d+)(?:\.(\d+))?', (res.stderr or "") + (res.stdout or ""))
    if not m:
        return None
    major = int(m.group(1))
    return int(m.group(2) or 0) if major == 1 else major


def version_of(argv, runner=subprocess.run) -> Optional[str]:
    words = [str(x) for x in argv] if isinstance(argv, (list, tuple)) else [str(argv)]
    try:
        res = runner(words + ["--version"], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r"signal-cli\s+(\d+\.\d+\.\d+(?:\.\d+)?)", (res.stdout or "") + (res.stderr or ""))
    return m.group(1) if m else None


def find(cfg: dict) -> "tuple[Optional[list], str]":
    from halo_signal.settings import binary_words
    words = binary_words(cfg)
    if words != ["signal-cli"]:
        return (words, f"signal.json names {' '.join(words)}") if version_of(words) else \
            (None, f"signal.json names {' '.join(words)}, and it does not answer --version")
    onpath = shutil.which("signal-cli")
    return ([onpath], f"found {onpath} on PATH") if onpath else (None, "signal-cli is not on PATH")


def report(cfg: dict) -> "tuple[bool, list]":
    argv, where = find(cfg)
    lines = [f"signal-cli: {where}"]
    if argv is None:
        lines += [f"install it: {install_line()}", "(Halo never installs it; signal-cli is GPL-3.0, "
                  "https://github.com/AsamK/signal-cli -- it is how this computer speaks Signal)"]
        return False, lines
    version = version_of(argv)
    lines.append(f"version: {version or 'unknown'}" + ("" if version in (None, TESTED) else f" (the pack is tested with {TESTED})"))
    if not native_host():
        major = java_major()
        ok = major is not None and major >= MIN_JRE
        lines.append(f"java: {major if major is not None else 'not found'}" + ("" if ok else
                     f" -- the JVM build of signal-cli needs Java {MIN_JRE} or newer ({install_line()})"))
        if not ok:
            return False, lines
    account = cfg.get("account")
    lines.append(f"account: {account} ({cfg.get('identity_model')})" if account else
                 "account: none yet -- link this computer to your phone (/signal link) or register a number "
                 "(/signal register +<number>)")
    return True, lines
