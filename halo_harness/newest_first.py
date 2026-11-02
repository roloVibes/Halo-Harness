"""halo_harness.newest_first -- rows newest first with a tie broken by their order (Halo 3.3.8.1; the flake rule
"a sort by a stamp alone" in docs/DEVELOPMENT.md, linted by tests/test_flake_rules.py).

    newest_first(rows, stamp) -> list     the rows by `stamp(row)` descending; rows with the same stamp (two writes in
                                          one millisecond, two jobs started together) in reverse file / insertion
                                          order, so the later one is first

A plain `sorted(rows, key=stamp, reverse=True)` keeps equal stamps in file order (Python's sort is stable either way),
so of two rows written in the same millisecond the OLDER came first -- GET local/changes on the Linux runner, 3.3.8.0
candidate 44617414.
"""

from __future__ import annotations

from typing import Callable, Iterable


def newest_first(rows: Iterable, stamp: Callable) -> list:
    order = sorted(enumerate(rows), key=lambda t: (stamp(t[1]), t[0]), reverse=True)
    return [r for _i, r in order]
