"""halo_harness.update_install -- the reinstall step of `halo update`, made to survive a network that uv's own TLS
does not trust (Halo 3.3.16.0; the owner's Kali, 2026-11-10: `uv tool install --reinstall --constraints https://raw.
githubusercontent.com/.../requirements.lock git+https://github.com/...` stopped at "invalid peer certificate:
UnknownIssuer" on the lock file -- git trusted the box's CA store, uv's bundled roots did not -- and halo stayed on the
old version).

    pin_locally(cmd)         -> (cmd, note): a `--constraints <https url>` is fetched by halo itself (providers/http's
                                TLS policy: the system's store and any configured CA bundle) into a temp file and the
                                command points at that file; when the fetch fails the pin is dropped for this run and
                                the note says so (an update you asked for is not blocked by the lock's download).
    run_install(cmd, cwd, run_fn) -> (returncode, output): runs it, prints its output, and when it failed on a
                                certificate runs it once more with uv's `--native-tls` (the system's certificates).
    certificate_failure(text) -> bool    with_native_tls(cmd) -> str    last_line(text) -> str
"""
from __future__ import annotations

import re
import tempfile
from pathlib import Path
from typing import Callable, Optional

_CERT_RE = re.compile(r"invalid peer certificate|UnknownIssuer|CERTIFICATE_VERIFY_FAILED|certificate verify failed"
                      r"|self[- ]signed certificate|unable to get local issuer certificate", re.IGNORECASE)
_CONSTRAINTS_RE = re.compile(r'(?P<flag>\s--constraints\s+)(?P<q>["\']?)(?P<url>https://[^\s"\']+)(?P=q)')


def _fetch_lock(url: str) -> bytes:
    from halo_harness.providers.http import urlopen_tls
    with urlopen_tls(url, timeout=20) as r:
        return r.read()


def pin_locally(cmd: str, fetch: Optional[Callable[[str], bytes]] = None) -> "tuple[str, str]":
    """The command with its https `--constraints` replaced by a local copy, and a note ("" when nothing changed)."""
    m = _CONSTRAINTS_RE.search(cmd or "")
    if not m:
        return cmd, ""
    url = m.group("url")
    try:
        data = (fetch or _fetch_lock)(url)
        if not data or b"==" not in data:
            raise ValueError("not a requirements lock")
        tmp = Path(tempfile.mkdtemp(prefix="halo-lock-")) / "requirements.lock"
        tmp.write_bytes(data)
        return cmd[:m.start()] + f'{m.group("flag")}"{tmp}"' + cmd[m.end():], ""
    except Exception as e:  # noqa: BLE001 -- any failure means "install without the pin", said once
        reason = str(e).strip().splitlines()[0] if str(e).strip() else type(e).__name__
        return cmd[:m.start()] + cmd[m.end():], (f"halo update: the dependency lock could not be fetched from "
                                                   f"{url} ({reason}); installing without the pin this once")


def certificate_failure(text: str) -> bool:
    return bool(_CERT_RE.search(text or ""))


def with_native_tls(cmd: str) -> str:
    """`uv tool install ...` -> `uv tool install --native-tls ...` (uv only; other installers are returned as is)."""
    if not (cmd or "").lstrip().startswith("uv ") or "--native-tls" in cmd:
        return cmd
    return cmd.replace("uv tool install", "uv tool install --native-tls", 1)


def last_line(text: str) -> str:
    """`halo --version` prints the banner first; the version is its last non-empty line."""
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    return lines[-1] if lines else ""


def run_install(cmd: str, *, cwd: Optional[str], run_fn, out=print) -> "tuple[int, str]":
    """Run `cmd`, print what it printed, and on a certificate failure run it once more with `--native-tls`."""
    import subprocess

    def once(c: str) -> "tuple[int, str]":
        try:
            r = run_fn(c, shell=True, cwd=cwd, capture_output=True, text=True, timeout=600)
        except (OSError, subprocess.SubprocessError) as e:
            out(f"halo update: the reinstall command failed to run: {e}")
            return 1, str(e)
        text = "\n".join(t for t in ((r.stdout or "").rstrip(), (getattr(r, "stderr", "") or "").rstrip()) if t)
        if text:
            out(text)
        return r.returncode, text

    code, text = once(cmd)
    if code != 0 and certificate_failure(text):
        retry = with_native_tls(cmd)
        if retry != cmd:
            out("halo update: the installer did not trust a certificate on this network (a proxy or TLS inspection "
                "between this box and GitHub or PyPI); trying once more with the system's certificate store")
            out(f"halo update: running: {retry}")
            code, text = once(retry)
        if code != 0:
            out("halo update: still refused. Check `env | grep -i proxy` on this box (an intercepting proxy such as Burp "
                "needs its CA in the system store), then run the command above by hand")
    return code, text
