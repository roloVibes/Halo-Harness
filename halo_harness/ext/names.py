"""halo_harness.ext.names -- the name rules a pack meets (extension API 1.0).

    is_valid_pack_id("doc-review")             # True: ^[a-z][a-z0-9-]*$, no "--", no trailing "-"
    is_valid_name("reviewer")                  # the bio and lineup name rule
    qualified_name("doc-review", "reviewer")   # "doc-review--reviewer": how Halo lists the pack's bio
    split_name("doc-review--reviewer")         # ("doc-review", "reviewer"); (None, name) for a bare name
"""

from __future__ import annotations

from halo_harness.packs.names import is_valid_name, is_valid_pack_id, qualify as qualified_name
from halo_harness.packs.names import unqualify as split_name

__all__ = ["is_valid_pack_id", "is_valid_name", "qualified_name", "split_name"]
