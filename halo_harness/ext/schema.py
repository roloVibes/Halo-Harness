"""halo_harness.ext.schema -- shape checks (extension API 1.0).

`check_schema(doc, schema)` walks a parsed document against a
JSON-schema-like dict (`type`, `properties`, `additionalProperties`,
`items`, `enum`) and answers one finding per problem:
`{"check": "unknown-key" | "wrong-type" | "bad-value", "key", "text", "closest"}`.
It is the checker `halo doctor --config` uses for Halo's own files and the
one a pack's `config.schema` is read with.
"""

from __future__ import annotations


def check_schema(doc, schema: dict) -> list:
    from halo_harness.schemas.check import check
    return check(doc, schema if isinstance(schema, dict) else {})


__all__ = ["check_schema"]
