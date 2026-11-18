"""halo_harness.live.replay_cut -- 3.6.0.3: the rules for a text cut short moved to halo_harness/privacy_scrub.py with
no change of behaviour; re-exported here (the same objects) until the batch that deletes this module.
"""

from __future__ import annotations

from halo_harness.privacy_scrub import (COMMON_NAMES, cut_name_rule, cut_path_rule, _CUT_RUN, _CUT_WORD, _forms,
                                        _starts_a_path)  # noqa: F401
