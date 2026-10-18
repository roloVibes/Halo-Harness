"""halo_harness.fleet.mission_claims -- a mission part's claims as paths
(Halo 3.0.6.0 "Fleet Missions" round R7; 3.1.0.0 R2 cut it out of
mission_plan_rules.py). A claim is a repo-relative path or glob (`*`, `?`,
`**`); a path with no wildcard also covers what is under it.

* `bad_claim(c)`: why a claim is not repo-relative (absolute, `..`), or None.
* `overlap(a, b)`: two claims can name one file (mission_plan_check.sequence
  then runs the later part after the earlier).
* `covers(claims, rel)`: a repo-relative path is inside one of the claims
  (mission_guard.py lets a part's worker edit only those).
"""

from __future__ import annotations

import fnmatch
import re
from typing import Optional

_WILD = re.compile(r"[*?\[]")


def norm_claim(c) -> str:
    p = str(c or "").replace("\\", "/").strip()
    while p.startswith("./"):
        p = p[2:]
    return p.rstrip("/")


def bad_claim(c: str) -> Optional[str]:
    p = norm_claim(c)
    if not p:
        return "an empty claim"
    if p.startswith("/") or (len(p) > 1 and p[1] == ":") or ".." in p.split("/"):
        return f"{c!r} is not repo-relative (no absolute path, no `..`)"
    return None


def _seg(a: str, b: str) -> bool:
    wa, wb = bool(_WILD.search(a)), bool(_WILD.search(b))
    if not wa or not wb:
        return fnmatch.fnmatchcase(a, b) if not wa else fnmatch.fnmatchcase(b, a)
    pa, pb = _WILD.split(a)[0], _WILD.split(b)[0]
    sa, sb = _WILD.split(a)[-1], _WILD.split(b)[-1]
    return (pa.startswith(pb) or pb.startswith(pa)) and (sa.endswith(sb) or sb.endswith(sa))


def _segs(a: list, b: list) -> bool:
    if not a and not b:
        return True
    if a and a[0] == "**":
        return _segs(a[1:], b) or (bool(b) and _segs(a, b[1:]))
    if b and b[0] == "**":
        return _segs(a, b[1:]) or (bool(a) and _segs(a[1:], b))
    if not a or not b:
        return False
    return _seg(a[0], b[0]) and _segs(a[1:], b[1:])


def _forms(c: str) -> list:
    p = norm_claim(c)
    return [p.split("/")] + ([] if _WILD.search(p) else [p.split("/") + ["**"]])


def overlap(a: str, b: str) -> bool:
    """True when some file could match both claims."""
    return any(_segs(x, y) for x in _forms(a) for y in _forms(b))


def covers(claims: list, rel: str) -> bool:
    """True when the repo-relative path `rel` is inside one of `claims`."""
    path = norm_claim(rel).split("/")
    return any(_segs(path, form) for c in claims for form in _forms(c))
