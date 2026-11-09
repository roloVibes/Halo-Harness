"""halo_signal.main -- `bin/signal.py`, the pack's one program:

    bin/signal.py service              the bridge (the supervisor runs it: pack.yaml contributes.services)
    bin/signal.py ctl [verb ...]       `/signal ...` (the entry command runs it with your words after it)
    bin/signal.py setup <block>        Setup's check blocks: box, link, test, pair, phones, service
    bin/signal.py link-helper <name>   the background half of `/signal link`

Exit codes: 0 done, 1 could not (the line says why), 2 usage, 3 the service has nothing to run yet.
"""

from __future__ import annotations

import sys


def _ctl(args: list) -> int:
    from halo_signal import ctl, ctl_account
    verb, rest = (args[0].lower(), args[1:]) if args else ("status", [])
    table = {"status": ctl.status, "pair": ctl.pair, "phones": ctl.phones, "sign": ctl.sign, "url": ctl.url,
             "notices": ctl.notices, "test": ctl.test, "link": ctl_account.link, "register": ctl_account.register,
             "on": lambda a: ctl.onoff("on"), "off": lambda a: ctl.onoff("off"),
             "unpair": lambda a: ctl._phone_verb("unpair", a), "reverify": lambda a: ctl._phone_verb("reverify", a),
             "home": lambda a: ctl._phone_verb("home", a), "help": ctl.status}
    fn = table.get(verb)
    if fn is None:
        print(f"/signal {verb}: not a verb of the signal pack. {ctl.ENTRY} pair | phones | unpair <n> | sign on|off <n> "
              "| home <n> <folder> | off | on | url | test | link | register | notices")
        return 2
    return fn(rest)


def _setup(args: list) -> int:
    from halo_signal import setup
    block = args[0] if args else ""
    fn = setup.BLOCKS.get(block)
    if fn is None:
        print(f"setup block {block!r}: one of {', '.join(setup.BLOCKS)}")
        return 2
    return fn()


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    cmd, rest = (args[0], args[1:]) if args else ("ctl", [])
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass
    if cmd == "service":
        from halo_signal.service import main as service
        return service(rest)
    if cmd == "ctl":
        return _ctl(rest)
    if cmd == "setup":
        return _setup(rest)
    if cmd == "link-helper":
        from halo_signal.ctl_account import link_helper
        return link_helper(rest)
    print(__doc__.split("\n\n")[1])
    return 2
