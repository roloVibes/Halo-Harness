"""halo_harness.guest -- a Claude Code session shown in Studio, WATCH ONLY (Halo 3.6.0.25, package G).

How it fits together (docs/GUEST.md is the page for people):

* `halo guest install` writes a local Claude Code plugin folder under Halo's own folder (install.py); Halo runs no
  command of Claude Code's: it prints the ones that add and turn on the plugin.
* Claude Code starts the plugin's hooks: each is `note.py` (stdlib only), which appends one line, cut to size, to
  the spool of the bridge of ITS Claude Code process, and exits 0 printing nothing (no bridge up: it writes nothing).
* Claude Code starts the plugin's MCP server as its own child: the bridge (bridge.py, `halo guest serve`). It offers
  the model no tools, opens a control socket and a registry row (`kind: guest`) exactly as every Halo session does,
  turns the spool's lines into rows of an agent tree and frames of its feed (feed.py), and ends when its input closes.

The rules, in the code's own words (they bind every file of this package; tests/test_guest.py reads them):

* Halo reads, stores, forwards and uses NOTHING of the Claude login: no credential file, no login variable, no
  base address pointed at Halo. The hook keeps only the documented fields it names, cut to size.
* Halo starts nothing of Claude's: no Claude Code process, no turn, no prompt typed into it.
* Watch only changes nothing in his session: a hook returns no context, no decision, never stops Claude Code and
  never exits with a blocking code; the bridge answers every command that would send into a session "watch only".
* No new listening port beyond the loopback control socket every session opens, nothing off this machine, nothing
  kept after the session: the spool and the registry row live under Halo's run folder while the session lives.
"""

from __future__ import annotations

KIND = "guest"  # the registry row's `kind` (Studio draws it as a session, watch only)
TITLE = "Claude Code"  # the row's title, and main's role
PLUGIN = "halo-guest"  # the Claude Code plugin's name (no "claude" in it: Claude Code's rule for plugin names)
MARKETPLACE = "halo-local"  # the local marketplace the plugin folder is
WATCH_ONLY = "watch only"
WATCH_ONLY_LINE = "watch only: Halo shows this Claude Code session and sends nothing into it"
GOAL_NOT_KNOWN = "goal not known"
DESCRIPTION = "Halo: shows this session in Studio (watch only)"
# the commands the bridge serves; every other one answers WATCH_ONLY_LINE (remote/protocol.py)
WATCH_CMDS = ("ping", "status", "subscribe", "unsubscribe", "agents", "agent_tail", "agent_follow")


def guest_dir():
    """`<run>/guest`: the bridges' `.on` marks and spools (0700 on POSIX, under the owner's run folder)."""
    import os
    from halo_harness.remote.control_socket import run_dir
    d = run_dir() / "guest"
    d.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(d, 0o700)
    except OSError:
        pass
    return d
