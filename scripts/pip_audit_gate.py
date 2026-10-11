"""scripts/pip_audit_gate.py -- CI step: `pip-audit` over requirements.lock.

    python scripts/pip_audit_gate.py [--lock requirements.lock] [--allowlist .github/pip-audit-allowlist.txt]

Fails (exit 1) when `pip-audit` reports a known vulnerability in any pinned
dependency, except the advisory ids listed in the allowlist file (one id per
line, `#` starts a comment; give every accepted id a reason in that comment).
`pip-audit` runs with `--disable-pip`, so it audits exactly the hashed pins in
the lock and resolves nothing on its own.

Regenerating the lock (uv; no hand edits):

    uv pip compile pyproject.toml --universal --generate-hashes -o requirements.lock

and installing from it, hashes enforced:

    pip install --require-hashes --no-deps -r requirements.lock

2.0.10 review finding 27.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read_allowlist(path: Path) -> list:
    """The advisory ids in `path` (a missing file means none)."""
    ids = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ids
    for line in text.splitlines():
        token = line.split("#", 1)[0].strip()
        if token:
            ids.append(token.split()[0])
    return ids


def audit_argv(lock: Path, allowlist: Path) -> list:
    argv = [sys.executable, "-m", "pip_audit", "--requirement", str(lock), "--disable-pip", "--strict"]
    for vuln_id in read_allowlist(allowlist):
        argv += ["--ignore-vuln", vuln_id]
    return argv


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--lock", default=str(ROOT / "requirements.lock"))
    ap.add_argument("--allowlist", default=str(ROOT / ".github" / "pip-audit-allowlist.txt"))
    args = ap.parse_args(argv)
    cmd = audit_argv(Path(args.lock), Path(args.allowlist))
    print("running: " + " ".join(cmd))
    return subprocess.run(cmd).returncode


if __name__ == "__main__":
    sys.exit(main())
