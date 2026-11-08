"""__NAME__'s TODO hook (hooks/hooks.json, PostToolUse on Write; it runs once the owner grants `hooks`): it asks rg
(ripgrep) how many TODO lines the written file holds and appends `<file>: <n> TODO` to `todos.log` in the pack's data
folder. It reads rg's output, an argument list with `--`, and a time limit. Without rg, or with a Python that cannot
import Halo, it does nothing and exits 0.
"""

import json
import shutil
import subprocess
import sys

try:
    from halo_harness.ext import data_dir
except ImportError:
    data_dir = None

PACK_ID = "__ID__"


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0
    rg = shutil.which("rg")
    path = str(((event or {}).get("tool_input") or {}).get("file_path") or "") if isinstance(event, dict) else ""
    if rg is None or data_dir is None or not path:
        return 0
    try:
        done = subprocess.run([rg, "--count", "--", "TODO", path], capture_output=True, text=True, timeout=10)
    except subprocess.TimeoutExpired:
        return 0
    count = done.stdout.strip() or "0"
    folder = data_dir(PACK_ID)
    folder.mkdir(parents=True, exist_ok=True)
    with open(folder / "todos.log", "a", encoding="utf-8") as f:
        f.write(f"{path}: {count} TODO\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
