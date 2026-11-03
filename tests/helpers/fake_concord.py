"""tests.helpers.fake_concord -- a stand-in for Concord's `concord` CLI (Halo 3.3.10.0 R3, tests/test_pack_concord.py):
never the real one. `install(bin_dir)` writes a `concord` launcher into a scratch bin dir (`concord.cmd` on Windows)
that runs this file with Halo's Python; the test puts that dir first on PATH.

    concord check [--task <id>] <file>...   exit 1 with Concord's overlap lines when a file is FAKE_CONCORD_CLAIMED
                                            (default `claimed.txt`, claimed by task FAKE_CONCORD_TASK, default t-42)
                                            and is not that task's own (`--task`); else exit 0 with its OK line
    anything else                           exit 0, nothing printed

Every call appends `{"argv": [...], "telemetry_off": bool, "cwd": "..."}` to FAKE_CONCORD_LOG when it is set.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def install(bin_dir: Path) -> Path:
    bin_dir.mkdir(parents=True, exist_ok=True)
    me = Path(__file__).resolve()
    if os.name == "nt":
        launcher = bin_dir / "concord.cmd"
        launcher.write_text(f'@"{sys.executable}" "{me}" %*\r\n', encoding="utf-8")
    else:
        launcher = bin_dir / "concord"
        launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{me}" "$@"\n', encoding="utf-8")
        launcher.chmod(0o755)
    return launcher


def main(argv: list) -> int:
    log = os.environ.get("FAKE_CONCORD_LOG")
    if log:
        with open(log, "a", encoding="utf-8") as f:
            f.write(json.dumps({"argv": argv, "telemetry_off": os.environ.get("CONCORD_TELEMETRY_DISABLED") == "1",
                                "cwd": os.getcwd()}) + "\n")
    if not argv or argv[0] != "check":
        return 0
    rest, own = list(argv[1:]), ""
    if "--task" in rest:
        i = rest.index("--task")
        own = rest[i + 1] if i + 1 < len(rest) else ""
        del rest[i:i + 2]
    claimed = os.environ.get("FAKE_CONCORD_CLAIMED", "claimed.txt")
    task = os.environ.get("FAKE_CONCORD_TASK", "t-42")
    hit = [f for f in rest if f == claimed and own != task]
    if not hit:
        print(f"OK: none of the {len(rest)} file(s) overlap another active task.")
        return 0
    print("Overlap: files you are about to edit collide with 1 active task(s):")
    print(f"  - {task} (the auth work): same file(s): {', '.join(hit)}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
