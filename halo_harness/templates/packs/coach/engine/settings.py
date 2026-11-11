"""The coach pack's settings (`contributes.settings`, Halo 3.4.0.0 B2): its rows in Studio's Settings ("From packs")
and `halo config get/set packs.settings.coach.<key>`; this reads them through the extension API (`ext.get_config`).
Until 3.4.0.0 they were the core keys `coach.*` and `improve.*`; a value left there is ignored (`halo doctor --config`
says so in one line).
"""

from __future__ import annotations


def get(key: str, default=None):
    """`packs.settings.coach.<key>` (a dotted key reaches inside), else `default`."""
    from halo_harness.ext import get_config
    try:
        value = get_config("coach", key, None)
    except Exception:
        value = None
    return default if value is None else value
