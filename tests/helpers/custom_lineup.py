"""tests.helpers.custom_lineup -- a custom lineup active for a block (Halo 3.3.15.0 R5): the guided first run is
offered only for one (halo_harness/start/auto_gate.py), so a test of the start, its check row or its Studio door sets
`team` in the scoped config.json for the block and puts the value of before back after it.

    with custom_lineup():            team: halo-dev-cycle (a shipped lineup that is not Auto)
    with custom_lineup(None):        team unset: the Auto lineup (roles on), the start not offered
"""
from __future__ import annotations

from contextlib import contextmanager

CUSTOM = "halo-dev-cycle"


@contextmanager
def custom_lineup(name=CUSTOM):
    from halo_harness.theme import get_config_value, set_config_value, unset_config_value
    before = get_config_value("team", None)
    if name:
        set_config_value("team", name)
    else:
        unset_config_value("team")
    try:
        yield name
    finally:
        if before is None:
            unset_config_value("team")
        else:
            set_config_value("team", before)
