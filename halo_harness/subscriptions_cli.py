"""halo_harness.subscriptions_cli -- `halo subscriptions status|accept|
revoke` (Halo 2.0.7 round 7b). `accept` prints the notice and reads the
typed acceptance from stdin; a non-interactive stdin (nothing to read)
never accepts -- see `subscription_consent.read_typed_acceptance`.
"""

from __future__ import annotations

import sys

from halo_harness.subscription_consent import (
    ACCEPT_PHRASE, notice_text, read_typed_acceptance, record_acceptance, revoke, status_line,
)


def cmd_subscriptions(argv: list) -> int:
    action = argv[0] if argv else "status"
    if action in ("-h", "--help"):
        print("Usage: halo subscriptions [status|accept|revoke]")
        return 0
    if action == "status":
        print(status_line())
        return 0
    if action == "accept":
        print(notice_text())
        print()
        if read_typed_acceptance():
            state = record_acceptance()
            print(f"Accepted (v{state['accepted_version']}, {state['accepted_at']}). "
                  "cc:/cx: are now available.")
            return 0
        print(f'Not accepted (needs the exact phrase "{ACCEPT_PHRASE}") -- cc:/cx: remain off.',
              file=sys.stderr)
        return 1
    if action == "revoke":
        revoke()
        print("Revoked. cc:/cx: are off again until accepted.")
        return 0
    print(f"halo subscriptions: unrecognized argument: {action!r} "
          f"(expected status|accept|revoke)", file=sys.stderr)
    return 2
