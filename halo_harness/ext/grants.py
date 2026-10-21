"""halo_harness.ext.grants -- what you granted a pack (extension API 1.0).

    is_granted("doc-review", "network")       # True once you ran halo pack enable doc-review --grant network
    is_granted("doc-review", "mcp:search")

A permission is a name the pack requests in pack.yaml (`mcp:<server>`,
`hooks`, `bash`, `network`, `home-write`) and you grant when you enable it;
the grants live in `~/.halo/packs/state.json`. A disabled pack holds none.
"""

from __future__ import annotations


def is_granted(pack_id: str, permission: str) -> bool:
    from halo_harness.packs import state as S
    data = S.load()
    rec = S.entry(pack_id, data=data) or {}
    return bool(rec.get("enabled")) and permission in S.granted(pack_id, data)


__all__ = ["is_granted"]
