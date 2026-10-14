"""halo_harness.remote.signal_install -- find or fetch the pinned signal-cli
(Halo 2.0.9 round 4). Nothing is installed system-wide: the archive is
unpacked under `<remote>/signal-cli/dist/<version>/` (beside, never inside,
signal-cli's own `data/` and `attachments/`), and `signal.json` points at it.

Pin: signal-cli 0.14.9, released 2026-10-07 (docs/harness/SIGNAL-RESEARCH.md
section 1). Linux x86-64 gets the native tarball; every other host gets the
JVM tarball and needs a JRE 25. `download` is the only function here that
touches the network; tests replace it.

What setup verifies (2.0.10 review finding 21), in this order:

1. The SHA-256 of the downloaded archive against `SHA256` below, BEFORE
   anything is unpacked or run. A mismatch, or an asset with no pinned digest,
   stops the install and deletes the download. This is the gate.
2. The extraction itself: device, FIFO, link, absolute-path and `..` members
   are rejected, and `tarfile`'s `data` filter is applied when available.
3. The `.asc` beside the archive, when `gpg` is installed AND
   `RELEASE_KEY_FINGERPRINT` is filled in: the signature must be good AND made
   by that exact key (`gpg --status-fd` VALIDSIG), not "some key in your
   keyring". A good signature by any other key stops the install. While
   `RELEASE_KEY_FINGERPRINT` is empty gpg is not consulted and the result is
   reported as `digest-only`. No key is ever downloaded or imported by Halo.

The digests are the `digest` field GitHub publishes for each release asset
(fetched 2026-10-11 from the release API, cross-checked twice):
https://api.github.com/repos/AsamK/signal-cli/releases/tags/v0.14.9
(page: https://github.com/AsamK/signal-cli/releases/tag/v0.14.9). To re-pin a
new version, read `assets[].digest` from that URL shape for the two archives
and change `VERSION`, `RELEASED` and `SHA256` together.
"""

from __future__ import annotations

import calendar
import hashlib
import http.client
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Callable, Optional

from halo_harness.remote.cli_common import child_env  # no provider keys for signal-cli or java
from halo_harness.remote.signal_config import remote_dir

VERSION = "0.14.9"
RELEASED = "2026-10-07"
RELEASED_TS = float(calendar.timegm((2026, 10, 7, 0, 0, 0)))
STALE_AFTER_DAYS = 90
MIN_JRE = 25
SHA256 = {
    "signal-cli-0.14.9-Linux-native.tar.gz": "a8fab78b5e8053abf3db5725272957ad11d1745b9a16848ddb2ace4743dfa5d5",
    "signal-cli-0.14.9.tar.gz": "c32b87f587198cbd277c9d71228716ee6047ee2b63e8e88728e8280d9407d65a",
}
# The signal-cli release signing key's full 40-hex fingerprint, upper case, no spaces. EMPTY until the
# owner fills it in from a source they trust (Halo does not fetch keys): while empty, gpg is not consulted.
RELEASE_KEY_FINGERPRINT = ""
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
        res = runner(["java", "-version"], capture_output=True, text=True, timeout=10, env=child_env())
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
        res = runner(argv + ["--version"], capture_output=True, text=True, timeout=20, env=child_env())
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r"signal-cli\s+(\d+\.\d+\.\d+(?:\.\d+)?)", (res.stdout or "") + (res.stderr or ""))
    return m.group(1) if m else None


def _discard(path: Path) -> None:
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        pass


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
        _discard(dest)
        raise InstallError(f"network.offline is on; {e}") from None
    except (OSError, http.client.HTTPException) as e:  # IncompleteRead and friends are not OSErrors
        _discard(dest)  # never leave a partial archive behind
        raise InstallError(f"download failed: {type(e).__name__}: {e}") from None


def verify_digest(archive: Path, name: str) -> str:
    """The archive's SHA-256 must equal the pinned digest for `name`; returns the hex digest.
    A missing, empty or placeholder pin refuses (nothing is installed from an unpinned asset)."""
    want = str(SHA256.get(name) or "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", want):
        raise InstallError(f"no pinned SHA-256 for {name}; refusing to install an unverified archive")
    h = hashlib.sha256()
    with open(archive, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    got = h.hexdigest()
    if got != want:
        raise InstallError(f"SHA-256 mismatch for {name}: expected {want}, got {got}; the archive was not unpacked")
    return got


def verify_signature(archive: Path, sig: Optional[Path], runner: Callable = subprocess.run) -> tuple:
    """`(status, detail)`: verified | unverified | digest-only | no-gpg | no-signature | bad.
    `verified` means a good signature made by `RELEASE_KEY_FINGERPRINT`, not by any key."""
    want = RELEASE_KEY_FINGERPRINT.replace(" ", "").upper()
    if not want:
        return "digest-only", "no release key fingerprint is pinned, so gpg was not consulted"
    if sig is None or not sig.exists():
        return "no-signature", "no .asc file was downloaded"
    if shutil.which("gpg") is None:
        return "no-gpg", "gpg is not installed, so the .asc was not checked"
    from halo_harness.remote.cli_common import child_env  # provider keys never reach a third-party child
    try:
        res = runner(["gpg", "--status-fd", "1", "--verify", str(sig), str(archive)], capture_output=True, text=True,
                     timeout=60, env=child_env())
    except (OSError, subprocess.SubprocessError) as e:
        return "unverified", f"gpg could not run: {e}"
    out = (res.stderr or "") + (res.stdout or "")
    if "BADSIG" in out or "BAD signature" in out:
        return "bad", "gpg reports a BAD signature"
    valid = [ln.split() for ln in out.splitlines() if ln.startswith("[GNUPG:] VALIDSIG")]
    if res.returncode == 0 and valid:
        fprs = {t.upper() for parts in valid for t in (parts[2], parts[-1]) if len(t) == 40}
        if want in fprs:
            return "verified", f"gpg: good signature by {want}"
        return "bad", "gpg: good signature, but not by the pinned signal-cli release key"
    return "unverified", "the pinned signing key is not in your gpg keyring (import it, then run `gpg --verify` by hand)"


def _unsafe_member(m: "tarfile.TarInfo", base: Path, dest: Path) -> bool:
    name = m.name
    if m.isdev() or m.isfifo() or m.islnk() or m.issym() or not (m.isfile() or m.isdir()):
        return True
    if name.startswith(("/", chr(92))) or PureWindowsPath(name).is_absolute() or PurePosixPath(name).is_absolute():
        return True
    if ".." in PurePosixPath(name.replace(chr(92), "/")).parts:
        return True
    target = (dest / name).resolve()
    return not (target == base or base in target.parents)


def extract(archive: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    base = dest.resolve()
    with tarfile.open(archive, "r:*") as tar:
        members = []
        for m in tar.getmembers():
            if _unsafe_member(m, base, dest):
                raise InstallError(f"unsafe member in archive: {m.name}")
            members.append(m)
        if hasattr(tarfile, "data_filter"):
            tar.extractall(dest, members=members, filter="data")
        else:
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
        verify_digest(archive, name)
    except InstallError:
        archive.unlink(missing_ok=True)
        raise
    say("SHA-256 matches the pinned digest.")
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
