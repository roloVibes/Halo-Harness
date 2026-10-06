"""halo_harness.balances_cli -- `halo balances` (Halo 2.0.4 round 3,
deliverable 2): the CLI half of the one shared balances surface
(`providers.balances`); `/balances` (`commands/builtins.py::_cmd_balances`)
renders the SAME table, so the two surfaces never drift apart.

Bare `halo balances` never touches the network (same "no network on a
bare listing" rule `halo models`/`halo providers` already follow) --
shows whatever `balances.json` already has cached, or "not fetched yet".
`--refresh` does the one bounded round of fetches, written back to that
same cache file.
"""

from __future__ import annotations

import argparse

from halo_harness.config.paths import bridge_home
from halo_harness.providers.config import load_provider_env_files


def cmd_balances(argv) -> int:
    parser = argparse.ArgumentParser(prog="halo balances", add_help=True)
    parser.add_argument("--refresh", action="store_true",
                         help="Fetch a fresh reading from every provider that offers one (bounded, "
                              "best-effort) instead of showing the cached figures")
    args = parser.parse_args(argv)

    load_provider_env_files()
    state_dir = bridge_home()

    from halo_harness.providers.balances import cached_balances, format_balances_table, refresh_all_balances
    if args.refresh:
        entries = refresh_all_balances(state_dir)
    else:
        entries = cached_balances(state_dir)
    for line in format_balances_table(entries):
        print(line)
    if not args.refresh and not entries:
        print("\n(nothing cached yet -- `halo balances --refresh` fetches a real reading)")
    return 0
