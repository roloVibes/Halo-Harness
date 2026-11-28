"""`python -m halo_harness.guest serve ...`: the plugin's MCP entry runs the bridge this way, straight, without the
`halo` command's start-up (the bridge starts nothing and is Claude Code's child; guest/bridge.py)."""

import sys

from halo_harness.guest.install import cmd_guest

if __name__ == "__main__":
    sys.exit(cmd_guest(sys.argv[1:]))
