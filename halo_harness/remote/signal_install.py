"""halo_harness.remote.signal_install -- find or fetch the pinned signal-cli
(Halo 2.0.9 round 4). Nothing is installed system-wide: the archive is
unpacked under `<remote>/signal-cli/dist/<version>/` (beside, never inside,
signal-cli's own `data/` and `attachments/`), and `signal.json` points at it.

Pin: signal-cli 0.14.9, released 2026-10-07 (docs/harness/SIGNAL-RESEARCH.md
section 1). Linux x86-64 gets the native tarball; every other host gets the
JVM tarball and needs a JRE 25. The `.asc` beside each archive is checked
with `gpg` when it is installed. `download` is the only function here that
touches the network; tests replace it.
"""

from __future__ import annotations

import calendar
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path
from typing import Callable, Optional

from halo_harness.remote.signal_config import remote_dir

VERSION = "0.14.9"
RELEASED = "2026-10-07"
RELEASED_TS = float(calendar.timegm((2026, 10, 7, 0, 0, 0)))
STALE_AFTER_DAYS = 90
MIN_JRE = 25
BASE_URL = "https://github.com/AsamK/signal-cli/releases/download/v{v}/{name}"
HOSTS = ("chat.signal.org", "cdn.signal.org", "cdn2.signal.org", "cdn3.signal.org", "storage.signal.org",
         "cdsi.signal.org", "svr2.signal.org")


class InstallError(Exception):
    pass


def native_host(platform: Optional[str] = None, machine: Optional[str] = None) -> bool:
    import platform as _p
    plat = platform if platform is not None else sys.platform
    arch = (machine if machine is not None else _p.machine()).lower()
    return plat.startswith("linux") and arch in ("x86_64", "amd64")


def asset_name(platform: Optional[str] = None, machine: Optional[str] = None, jvm: bool = False) -> str:
    if native_host(platform, machine) and not jvm:
        return f"signal-cli-{VERSION}-Linux-native.tar.gz"
    return f"signal-cli-{VERSION}.tar.gz"


def asset_url(name: str) -> str:
    return BASE_URL.format(v=VERSION, name=name)


def install_dir(jvm: bool = False) -> Path:
    """`dist/0.14.9` (the build this host gets by default) or `dist/0.14.9-jvm` (`setup --jvm`)."""
    return remote_dir() / "signal-cli" / "dist" / (VERSION + ("-jvm" if jvm else ""))


def find_binary(root: Path) -> Optional[Path]:
    names = ("signal-cli.bat",) if os.name == "nt" else ("signal-cli",)
    for pat in (f"bin/{names[0]}", f"*/bin/{names[0]}", names[0]):
        for hit in sorted(root.glob(pat)):
            if hit.is_file():
                return hit
    return None


def find_installed(jvm: bool = False) -> Optional[Path]:
    root = install_dir(jvm)
    return find_binary(root) if root.is_dir() else None


def age_days(now: Optional[float] = None) -> float:
    return ((time.time() if now is None else now) - RELEASED_TS) / 86400.0


def java_major(runner: Callable = subprocess.run) -> Optional[int]:
    """The major version of `java` on PATH (25 for "25.0.1"; 1.8 style -> 8), or None."""
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


def version_of(binary, runner: Callable = subprocess.run) -> Optional[str]:
    """`0.14.9` from `signal-cli --version`, or None."""
    argv = [str(x) for x in binary] if isinstance(binary, (list, tuple)) else [str(binary)]
    try:
        res = runner(argv + ["--version"], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r"signal-cli\s+(\d+\.\d+\.\d+(?:\.\d+)?)", (res.stdout or "") + (res.stderr or ""))
    return m.group(1) if m else None


def download(url: str, dest: Path, progress: Optional[Callable[[int], None]] = None) -> None:
    """Fetch `url` into `dest` (the one network call in this module)."""
    from halo_harness.providers.http import OfflineBlocked, urlopen_tls  # the shared TLS + offline choke point
    done = 0
    try:
        with urlopen_tls(url, timeout=60) as resp, open(dest, "wb") as out:
            while True:
                chunk = resp.read(1 << 20)
                if not chunk:
                    break
                out.write(chunk)
                done += len(chunk)
                if progress:
                    progress(done)
    except OfflineBlocked as e:
        raise InstallError(f"network.offline is on; {e}") from None
    except OSError as e:
        raise InstallError(f"download failed: {e}") from None


def verify_signature(archive: Path, sig: Optional[Path], runner: Callable = subprocess.run) -> tuple:
    """`(status, detail)`: verified | unverified | no-gpg | no-signature | bad."""
    if sig is None or not sig.exists():
        return "no-signature", "no .asc file was downloaded"
    if shutil.which("gpg") is None:
        return "no-gpg", "gpg is not installed, so the .asc was not checked"
    try:
        res = runner(["gpg", "--verify", str(sig), str(archive)], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as e:
        return "unverified", f"gpg could not run: {e}"
    out = (res.stderr or "") + (res.stdout or "")
    if res.returncode == 0:
        return "verified", "gpg: good signature"
    if "BAD signature" in out:
        return "bad", "gpg reports a BAD signature"
    return "unverified", "the signing key is not in your gpg keyring (import it, then run `gpg --verify` by hand)"


def extract(archive: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    base = dest.resolve()
    with tarfile.open(archive, "r:*") as tar:
        members = []
        for m in tar.getmembers():
            target = (dest / m.name).resolve()
            if m.islnk() or m.issym() or not (target == base or base in target.parents):
                raise InstallError(f"unsafe path in archive: {m.name}")
            members.append(m)
        tar.extractall(dest, members=members)


def install(say: Callable[[str], None], work: Optional[Path] = None, runner: Callable = subprocess.run,
            jvm: bool = False) -> tuple:
    """Download, check and unpack the pinned build. Returns `(binary, signature_status)`.
    The caller has already asked for confirmation."""
    name = asset_name(jvm=jvm)
    work = Path(work) if work else remote_dir() / "signal-cli" / "dl"
    work.mkdir(parents=True, exist_ok=True)
    archive, sig = work / name, work / (name + ".asc")
    say(f"Downloading {asset_url(name)}")
    download(asset_url(name), archive)
    try:
        download(asset_url(name + ".asc"), sig)
    except InstallError:
        sig = None
    status, detail = verify_signature(archive, sig, runner)
    say(f"Signature: {status} ({detail})")
    if status == "bad":
        raise InstallError("the signature check failed; the archive was not unpacked")
    root = install_dir(jvm)
    extract(archive, root)
    binary = find_binary(root)
    if binary is None:
        raise InstallError(f"no signal-cli launcher found under {root}")
    if os.name != "nt":
        os.chmod(binary, 0o755)
    for leftover in (archive, sig):
        try:
            if leftover is not None:
                leftover.unlink()
        except OSError:
            pass
    return binary, status
