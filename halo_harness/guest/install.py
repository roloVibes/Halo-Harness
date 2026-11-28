"""halo_harness.guest.install -- `halo guest install | uninstall | status | serve` (Halo 3.6.0.25 G).

`install` writes a local Claude Code plugin folder under Halo's own folder (`<halo home>/guest-plugin`): a local
marketplace holding one plugin, `halo-guest`, with its manifest (`defaultEnabled: false`: installed, it stays off
until he turns it on), its hooks file (every documented event this release reads, each an async exec-form command
of this Halo's own Python running the plugin's copy of note.py) and its MCP entry (the bridge, the same Python).
Halo runs no command of Claude Code's: `install` PRINTS the ones that add and turn on the plugin, `uninstall`
removes the folder and prints the ones that turn it off and remove it. `status` says whether a bridge is up.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Optional

from halo_harness.guest import KIND, MARKETPLACE, PLUGIN, guest_dir
from halo_harness.guest.note import EVENTS

USAGE = """usage: halo guest install | uninstall | status | serve

  install     write the Claude Code plugin that shows a Claude Code session in Studio (watch only), and print the
              Claude Code commands that add and turn it on (Halo runs none of them)
  uninstall   remove that plugin folder, and print the commands that turn it off and remove it
  status      whether a Claude Code session is shown now (a bridge is up)
  serve       the bridge itself: Claude Code starts it as the plugin's MCP server; not for a terminal"""
HOOK_TIMEOUT_S = 5  # async: Claude Code does not wait on it; note.py ends by itself within a second


def plugin_root(home: Optional[Path] = None) -> Path:
    from halo_harness.config.paths import bridge_home
    return Path(home) if home is not None else bridge_home() / "guest-plugin"


def _python() -> str:
    """This Halo's interpreter by the path it runs under, absolute and NEVER resolved: a venv's (or a uv tool's)
    bin/python is a link to the base interpreter, and the resolved path runs without the venv (no Halo, or another)."""
    return os.path.abspath(sys.executable)


def _bridge_env() -> dict:
    """The home this Halo uses, when it is not the default one (a test or a second home): the bridge must find it."""
    return {k: os.environ[k] for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR") if os.environ.get(k)}


def files(root: Path) -> dict:
    """{path: JSON object} of the plugin folder."""
    from halo_harness import __version__
    py, spool = _python(), str(guest_dir())
    plugin = root / PLUGIN
    hook = {"type": "command", "command": py, "args": ["-I", "${CLAUDE_PLUGIN_ROOT}/note.py", spool],
            "async": True, "timeout": HOOK_TIMEOUT_S}
    server = {"command": py, "args": ["-m", "halo_harness.guest", "serve", "--project", "${CLAUDE_PROJECT_DIR}"]}
    if _bridge_env():
        server["env"] = _bridge_env()
    words = "Shows this Claude Code session in Halo's Studio, watch only (nothing is sent into the session)"
    return {
        root / ".claude-plugin" / "marketplace.json": {
            "name": MARKETPLACE, "owner": {"name": "Halo"},
            "plugins": [{"name": PLUGIN, "source": f"./{PLUGIN}", "description": words}]},
        plugin / ".claude-plugin" / "plugin.json": {
            "name": PLUGIN, "version": __version__, "description": words, "defaultEnabled": False},
        plugin / "hooks" / "hooks.json": {"hooks": {event: [{"hooks": [dict(hook)]}] for event in EVENTS}},
        plugin / ".mcp.json": {"mcpServers": {PLUGIN: server}},
    }


def add_commands(root: Path) -> list:
    return [f'claude plugin marketplace add "{root}"', f"claude plugin install {PLUGIN}@{MARKETPLACE}",
            f"claude plugin enable {PLUGIN}"]


def remove_commands() -> list:
    return [f"claude plugin disable {PLUGIN}", f"claude plugin uninstall {PLUGIN}@{MARKETPLACE}",
            f"claude plugin marketplace remove {MARKETPLACE}"]


def install(root: Optional[Path] = None) -> Path:
    root = plugin_root(root)
    for path, data in files(root).items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    shutil.copyfile(Path(__file__).with_name("note.py"), root / PLUGIN / "note.py")
    return root


def uninstall(root: Optional[Path] = None) -> bool:
    root = plugin_root(root)
    if not root.is_dir():
        return False
    shutil.rmtree(root)
    return True


def bridges() -> list:
    """The registry's live guest rows."""
    from halo_harness.remote import registry
    return [r for r in registry.list_live() if isinstance(r, dict) and r.get("kind") == KIND]


def doctor_line() -> str:
    """`halo doctor`'s one row: the plugin folder, and how many Claude Code sessions are shown now."""
    from halo_harness.guest import sweep_dead
    sweep_dead()
    root = plugin_root()
    if not root.is_dir():
        return "Claude Code in Studio: off (`halo guest install` shows a Claude Code session, watch only)"
    up = len(bridges())
    return (f"Claude Code in Studio: the plugin folder is written ({root}); "
            + (f"{up} session{'' if up == 1 else 's'} shown now" if up else "no session shown now"))


def cmd_install(argv: list) -> int:
    root = install(Path(argv[argv.index("--to") + 1]) if "--to" in argv and argv.index("--to") + 1 < len(argv) else None)
    print(f"The plugin is written: {root}")
    print("Halo runs no command of Claude Code's. To show your Claude Code sessions in Studio, run these yourself:")
    for line in add_commands(root):
        print(f"  {line}")
    print("Watch only: Halo reads the hooks' lines (docs/GUEST.md says which), sends nothing into a session and "
          "touches nothing of your Claude login.")
    return 0


def cmd_uninstall(argv: list) -> int:
    root = plugin_root(Path(argv[argv.index("--to") + 1]) if "--to" in argv and argv.index("--to") + 1 < len(argv) else None)
    gone = uninstall(root)
    from halo_harness.guest import sweep_dead
    sweep_dead()
    print(f"The plugin folder is removed: {root}" if gone else f"No plugin folder here: {root}")
    print("To turn the plugin off in Claude Code and remove it there, run these yourself:")
    for line in remove_commands():
        print(f"  {line}")
    return 0


def dropped_of(row: dict):
    """The lines a bridge dropped (another folder, another session): one `status` call on its socket; None when
    it does not answer."""
    from halo_harness.remote.client import ControlClient, default_token_for
    client = None
    try:
        client = ControlClient(str(row.get("endpoint") or ""), default_token_for(row), timeout=2.0)
        n = ((client.call("status").get("result") or {}).get("guest") or {}).get("dropped")
        return n if isinstance(n, int) and not isinstance(n, bool) else None
    except Exception:
        return None
    finally:
        if client is not None:
            client.close()


def cmd_status(_argv: list) -> int:
    from halo_harness.guest import sweep_dead
    sweep_dead()
    rows = bridges()
    if not rows:
        print("No Claude Code session is shown in Studio now (no bridge is up).")
        return 0
    for r in rows:
        n = dropped_of(r)
        print(f"Claude Code session shown, watch only: {r.get('cwd')} ({r.get('parent')}); lines dropped (another "
              f"folder or another session): {'not known' if n is None else n}")
    return 0


def cmd_guest(argv: list) -> int:
    verb, rest = (argv[0], argv[1:]) if argv else ("", [])
    if verb == "serve":
        from halo_harness.guest.bridge import serve
        return serve(rest)
    if verb in ("install", "uninstall", "status"):
        return {"install": cmd_install, "uninstall": cmd_uninstall, "status": cmd_status}[verb](rest)
    print(USAGE, file=sys.stderr if verb not in ("-h", "--help") else sys.stdout)
    return 0 if verb in ("-h", "--help") else 2
