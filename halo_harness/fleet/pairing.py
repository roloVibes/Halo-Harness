"""halo_harness.fleet.pairing -- the hub's side of pairing (Halo 3.0.5.0
"Fleet" round R2): one-time codes and the member list. The same idea as
remote/pairing.py (a short-lived single-use code kept only as a hash, state
files 0600 behind the shared locked read/modify/write of pairing_files.py),
for harnesses instead of phones.

Files under `<home>/fleet/hub/`:

    codes.json    {version, codes: [{key, created, expires, used}]}     key = hex SHA-256 of the code
    members.json  {version, members: {<harness id>: {id, name, host, user, version, os, key_hex,
                   paired_at, share, allow_control}}, kicked: {<harness id>: ts}}

`halo fleet pair` adds a code; the hub's join route takes it (one code
admits one harness, then it is spent); `halo fleet members` lists the
members and `halo fleet kick <name>` removes one (its pair key goes with
it; a running hub notices the file change and closes that member's links).
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Optional

from halo_harness.fleet import pair_kex
from halo_harness.remote.pairing_files import _edit, _read

CODE_TTL_S = 600
MAX_CODES = 16
MAX_TTL_S = 24 * 3600


def hub_dir(home) -> Path:
    return Path(home) / "fleet" / "hub"


def public(record: dict) -> dict:
    """A member as a listing shows it: never its key."""
    return {k: v for k, v in (record or {}).items() if k != "key_hex"}


class HubPairing:
    def __init__(self, home, clock: Callable[[], float] = time.time) -> None:
        self.dir = hub_dir(home)
        self.codes_path = self.dir / "codes.json"
        self.members_path = self.dir / "members.json"
        self.clock = clock

    # ---- codes -------------------------------------------------------------
    def _codes(self):
        return _edit(self.codes_path, {"version": 1, "codes": []})

    def new_code(self, ttl_s: float = CODE_TTL_S) -> "tuple[str, float]":
        ttl_s = max(30.0, min(float(ttl_s), MAX_TTL_S))
        code = pair_kex.new_code()
        now = self.clock()
        self.dir.mkdir(parents=True, exist_ok=True)
        with self._codes() as d:
            live = [c for c in d.get("codes", []) if not c.get("used") and c.get("expires", 0) > now]
            live.append({"key": pair_kex.code_key(code).hex(), "created": now, "expires": now + ttl_s, "used": False})
            d["codes"] = live[-MAX_CODES:]
        return code, now + ttl_s

    def active_codes(self) -> int:
        now = self.clock()
        return sum(1 for c in _read(self.codes_path, {}).get("codes", [])
                   if not c.get("used") and c.get("expires", 0) > now)

    def take_code(self, matches: Callable[[bytes], bool]) -> Optional[bytes]:
        """The key of the first live code `matches` accepts, now spent; None when none does."""
        if not self.codes_path.exists():
            return None
        now = self.clock()
        with self._codes() as d:
            for c in d.get("codes", []):
                if c.get("used") or c.get("expires", 0) <= now:
                    continue
                try:
                    key = bytes.fromhex(str(c.get("key") or ""))
                except ValueError:
                    continue
                if key and matches(key):
                    c["used"] = True
                    c["used_at"] = now
                    return key
        return None

    # ---- members -----------------------------------------------------------
    def _members(self):
        return _edit(self.members_path, {"version": 1, "members": {}, "kicked": {}})

    def mtime(self) -> float:
        try:
            return self.members_path.stat().st_mtime
        except OSError:
            return 0.0

    def members(self) -> dict:
        rows = _read(self.members_path, {}).get("members", {})
        return {k: v for k, v in rows.items() if isinstance(v, dict)} if isinstance(rows, dict) else {}

    def member(self, hid: str) -> Optional[dict]:
        return self.members().get(hid)

    def key_for(self, hid: str) -> Optional[bytes]:
        rec = self.member(hid)
        try:
            key = bytes.fromhex(str((rec or {}).get("key_hex") or ""))
        except ValueError:
            return None
        return key if len(key) == 32 else None

    def add_member(self, record: dict, key: bytes) -> dict:
        rec = {**record, "key_hex": key.hex(), "paired_at": self.clock()}
        self.dir.mkdir(parents=True, exist_ok=True)
        with self._members() as d:
            d.setdefault("members", {})[rec["id"]] = rec
            d.setdefault("kicked", {}).pop(rec["id"], None)
        return public(rec)

    def update_member(self, hid: str, **fields) -> None:
        if not self.members_path.exists():
            return
        with self._members() as d:
            rec = d.setdefault("members", {}).get(hid)
            if rec is not None and any(rec.get(k) != v for k, v in fields.items()):
                rec.update(fields)

    def find(self, name_or_id: str) -> list:
        """Members whose name is `name_or_id` (any case), else whose id starts with it."""
        want = (name_or_id or "").strip()
        rows = list(self.members().values())
        hits = [r for r in rows if str(r.get("name") or "").lower() == want.lower()]
        return hits or [r for r in rows if want and str(r.get("id") or "").startswith(want)]

    def remove(self, hid: str, *, kicked: bool = True) -> Optional[dict]:
        if not self.members_path.exists():
            return None
        with self._members() as d:
            rec = d.setdefault("members", {}).pop(hid, None)
            if rec is not None and kicked:
                d.setdefault("kicked", {})[hid] = self.clock()
        return public(rec) if rec else None

    def kicked(self) -> dict:
        rows = _read(self.members_path, {}).get("kicked", {})
        return rows if isinstance(rows, dict) else {}
