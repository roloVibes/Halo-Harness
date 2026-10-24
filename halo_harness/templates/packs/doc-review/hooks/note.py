"""The Documentation Review pack's PostToolUse hook (hooks/hooks.json, runs
once you grant `hooks`): after a Write it notes the file in the pack's data
folder and publishes a review.done event. A pack's code imports
halo_harness.ext and nothing else of Halo (docs/EXTENSION_API.md); with a
Python that cannot import Halo the hook does nothing."""

import json
import sys

try:
    from halo_harness.ext import publish_event, write_private
except ImportError:  # the `python` on PATH is not the one Halo runs in
    publish_event = write_private = None


def main() -> int:
    if write_private is None:
        return 0
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0
    path = str((event.get("tool_input") or {}).get("file_path") or "")
    write_private("doc-review", "last-write.txt", path + "\n")
    try:
        publish_event("doc-review", "review.done", {"file": path, "findings": 0})
    except ValueError:  # the pack is disabled here: its events are not published
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
