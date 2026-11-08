"""__NAME__'s PostToolUse hook (hooks/hooks.json; it runs once the owner grants `hooks`): after a Write or an Edit it
appends one line -- the time, the tool and the file -- to `writes.log` in the pack's data folder
(~/.halo/packs/.data/__ID__/). The event comes as JSON on stdin; exit 0 lets the session go on. A pack's code imports
halo_harness.ext and nothing else of Halo; with a Python that cannot import Halo the hook does nothing.
"""

import json
import sys
import time

try:
    from halo_harness.ext import data_dir
except ImportError:  # the `python` on PATH is not the one Halo runs in
    data_dir = None

PACK_ID = "__ID__"


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0
    if data_dir is None or not isinstance(event, dict):
        return 0
    tool = str(event.get("tool_name") or "")
    path = str((event.get("tool_input") or {}).get("file_path") or "")
    folder = data_dir(PACK_ID)
    folder.mkdir(parents=True, exist_ok=True)
    with open(folder / "writes.log", "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {tool} {path}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
