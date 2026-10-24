"""halo_harness.ext.compat -- the compatibility policy of the extension API
(Halo 3.2.0.0 R7; docs/EXTENSION_API.md "Compatibility and migration").

The policy, as this module applies it:

- The API version is MAJOR.MINOR (`API_VERSION`, "1.0"). A minor version only
  adds names: every name keeps its meaning for every later minor of the same
  major. A major version may remove a name, and only one `deprecations()` has
  listed for at least one minor version before it.
- A pack states `halo_api: {min, max}`. `min` is required; `max` is inclusive
  at its own precision (`max: "1.9"` takes 1.9.4). Without `max` a pack runs on
  its `min`'s major only: `{min: "1.0"}` runs on every 1.x and not on 2.0.
- A Halo whose API is outside the range does not run the pack, and says so in
  one line (`halo_harness.packs.resolve.compat_lines`):
  "pack doc-review needs extension API 1.2 to 1.9; this Halo has 1.0".

    api_version()                           "1.0"
    compatible({"min": "1.0", "max": "1.9"})   True on this Halo
    compatible({"min": "1.0"}, "2.0")       False: a new major
    range_words({"min": "1.2"})             "1.2 or a later 1.x"
    deprecations()                          [{name, since, removed_in, use}]; empty in 1.0
"""

from __future__ import annotations

from typing import Optional

#: The names announced for removal: `{name: {"since": "1.x", "removed_in": "2.0", "use": "<the name to use>"}}`.
#: A name is listed here for at least one minor version before the major that removes it. Empty in 1.0.
DEPRECATED: "dict[str, dict]" = {}


def api_version() -> str:
    """This Halo's extension API version (`API_VERSION`)."""
    from halo_harness.ext import API_VERSION
    return API_VERSION


def _major(version) -> Optional[int]:
    from halo_harness.packs.semver import release
    parts = release(version)
    return parts[0] if parts else None


def compatible(rng, version=None) -> bool:
    """True when the API `version` (default this Halo's) is inside a pack's `halo_api` range under the policy:
    `min <= version <= max`, and with no `max`, the same major as `min`."""
    from halo_harness.packs import semver as V
    version = str(version if version is not None else api_version())
    if not isinstance(rng, dict) or V.range_problem(rng) or V.release(version) is None:
        return False
    if not V.in_range(version, rng):
        return False
    if rng.get("max") is None and rng.get("min") is not None:
        return _major(version) == _major(rng["min"])
    return True


def range_words(rng) -> str:
    """A `halo_api` range in the policy's words: "1.0 to 1.9", "1.2 or a later 1.x", "<= 1.9"."""
    from halo_harness.packs import semver as V
    if isinstance(rng, dict) and rng.get("max") is None and rng.get("min") is not None:
        return f"{rng['min']} or a later {_major(rng['min'])}.x"
    return V.describe(rng)


def deprecations() -> "list[dict]":
    """Every name announced for removal, by name: `[{name, since, removed_in, use}]` (`use` may be '')."""
    return [{"name": name, "since": str(info.get("since") or ""), "removed_in": str(info.get("removed_in") or ""),
             "use": str(info.get("use") or "")} for name, info in sorted(DEPRECATED.items())]


__all__ = ["DEPRECATED", "api_version", "compatible", "range_words", "deprecations"]
