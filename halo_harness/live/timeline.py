"""halo_harness.live.timeline -- 3.6.0.3: one session as a time axis (marks, bands) moved to live/card_timeline.py
with no change of behaviour; every name of it is re-exported here (the same objects) until the batch that
deletes this module.
"""

from __future__ import annotations

from halo_harness.live.card_timeline import (bands, _line, MARK_KINDS, marks, MAX_BANDS, of, _phase, PHASE_CAP,
                                             PHASES, _question, _segments, TEXT_CAP, _ts)  # noqa: F401 (moved in 3.6.0.3)
