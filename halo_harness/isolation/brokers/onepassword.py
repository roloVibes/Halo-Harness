"""halo_harness.isolation.brokers.onepassword -- the 1Password CLI (`op read <ref>`).

`secrets: {broker: 1password, account: <optional>}`; a ref is the one
`op read` takes (`op://<vault>/<item>/<field>`). `account` becomes
`--account <account>`. The value is `op`'s stdout less its last newline;
it is returned to the caller only, never printed or written.
"""

from __future__ import annotations

import shutil
import subprocess

from halo_harness.isolation.brokers import BrokerError

NAME, CLI = "1password", "op"
READ_TIMEOUT_S = 60


def present(which=shutil.which) -> bool:
    return bool(which(CLI))


def read(ref: str, *, account: str = "", runner=subprocess.run, which=shutil.which, environ=None) -> str:
    exe = which(CLI)
    if not exe:
        raise BrokerError("secrets: 1password asked, no `op` on PATH")
    if not str(ref).startswith("op://"):
        raise BrokerError(f"secrets: {ref} is not an op:// reference")
    argv = [exe, "read", str(ref)] + (["--account", account] if account else [])
    try:
        proc = runner(argv, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=READ_TIMEOUT_S,
                      stdin=subprocess.DEVNULL, env=environ)
    except (OSError, subprocess.SubprocessError) as e:
        raise BrokerError(f"secrets: could not read {ref} ({type(e).__name__})") from None
    if proc.returncode != 0:
        raise BrokerError(f"secrets: could not read {ref} (op exited {proc.returncode})")
    value = str(proc.stdout or "")
    value = value[:-2] if value.endswith("\r\n") else value[:-1] if value.endswith("\n") else value
    if not value:
        raise BrokerError(f"secrets: {ref} read back empty")
    return value
