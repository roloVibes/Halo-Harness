"""halo_harness.packs.semver -- versions and ranges for packs (Halo 3.2.0.0 R1).

A pack's own `version` is semver (`1.2.3`, an optional `-pre` and `+build`).
`halo_api` and `halo` ranges and a `requires[].version` compare release
numbers of any length (`1.0`, `3.2.0.0`), so Halo's four-part version and
the two-part API version compare the same way: missing parts count as 0.

    parse_semver("1.2.3-rc.1")             # (1, 2, 3), "rc.1"; None when it is not semver
    compare("3.2.0.0", "3.2")              # 0
    in_range("1.0", {"min": "1.0", "max": "1.9"})   # True
    range_problem({"min": "2"})            # "" (well formed); a line for a bad range
"""

from __future__ import annotations

import re
from typing import Optional

SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
                       r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$")
RELEASE_RE = re.compile(r"^\d+(?:\.\d+){0,3}$")


def parse_semver(text) -> "Optional[tuple[tuple[int, int, int], str]]":
    m = SEMVER_RE.match(text) if isinstance(text, str) else None
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3))), m.group(4) or ""


def is_semver(text) -> bool:
    return parse_semver(text) is not None


def release(text) -> "Optional[tuple[int, ...]]":
    """The release numbers of `text` (`"3.2.0.0"` -> (3, 2, 0, 0)); a semver's pre-release is dropped."""
    if isinstance(text, (int, float)) and not isinstance(text, bool):
        text = str(text)
    if not isinstance(text, str):
        return None
    core = text.strip().split("+", 1)[0].split("-", 1)[0]
    if not RELEASE_RE.match(core):
        return None
    return tuple(int(p) for p in core.split("."))


def compare(a, b) -> int:
    """-1, 0 or 1 comparing two release numbers (missing parts are 0); a semver
    pre-release sorts before its release. Raises ValueError for a value that is no version."""
    ra, rb = release(a), release(b)
    if ra is None or rb is None:
        raise ValueError(f"not a version: {a!r} or {b!r}")
    n = max(len(ra), len(rb))
    ra, rb = ra + (0,) * (n - len(ra)), rb + (0,) * (n - len(rb))
    if ra != rb:
        return -1 if ra < rb else 1
    pa = parse_semver(a) if isinstance(a, str) else None
    pb = parse_semver(b) if isinstance(b, str) else None
    pre_a, pre_b = (pa[1] if pa else ""), (pb[1] if pb else "")
    if pre_a == pre_b:
        return 0
    if not pre_a or not pre_b:
        return 1 if not pre_a else -1
    return -1 if pre_a < pre_b else 1


def range_problem(rng, *, where: str = "range") -> str:
    """One line naming what is wrong with a `{min, max?}` range, or ''."""
    if rng is None:
        return ""
    if not isinstance(rng, dict):
        return f"{where} is a mapping {{min, max}}, got {rng!r}"
    for key in ("min", "max"):
        if key in rng and rng[key] is not None and release(rng[key]) is None:
            return f"{where}.{key} {rng[key]!r} is not a version (1.0, 3.2.0.0)"
    unknown = sorted(set(rng) - {"min", "max"})
    if unknown:
        return f"{where} has {', '.join(unknown)}; a range takes min and max"
    if rng.get("min") is not None and rng.get("max") is not None and compare(rng["min"], rng["max"]) > 0:
        return f"{where}.min {rng['min']} is above {where}.max {rng['max']}"
    return ""


def _max_matches(value, maximum) -> bool:
    """`max` is inclusive at its own precision: max 1.9 takes 1.9.4; max 1 takes 1.9."""
    rv, rm = release(value), release(maximum)
    head = rv[:len(rm)] + (0,) * max(0, len(rm) - len(rv))
    return head <= rm


def in_range(value, rng) -> bool:
    """True when `value` lies inside `{min?, max?}` (both inclusive; a missing bound is open)."""
    if not isinstance(rng, dict):
        return True
    if release(value) is None:
        return False
    if rng.get("min") is not None and compare(value, rng["min"]) < 0:
        return False
    if rng.get("max") is not None and not _max_matches(value, rng["max"]):
        return False
    return True


def describe(rng) -> str:
    """`">= 1.0"`, `"<= 1.9"`, `"1.0 to 1.9"` or `"any"`."""
    if not isinstance(rng, dict):
        return "any"
    lo, hi = rng.get("min"), rng.get("max")
    if lo is not None and hi is not None:
        return f"{lo} to {hi}"
    if lo is not None:
        return f">= {lo}"
    return f"<= {hi}" if hi is not None else "any"
