"""The doc-review fixture pack's PostToolUse hook: notes the file a Write
touched in the pack's data folder. It imports halo_harness.ext only
(tests/test_ext_api.py checks every fixture pack for that)."""

import json
import sys

from halo_harness.ext import publish_event, write_private


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0
    path = str((event.get("tool_input") or {}).get("file_path") or "")
    write_private("doc-review", "last-write.txt", path + "\n")
    publish_event("doc-review", "review.done", {"file": path, "findings": 0})
    return 0


if __name__ == "__main__":
    sys.exit(main())
