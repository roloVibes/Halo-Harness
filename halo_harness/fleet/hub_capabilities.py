"""halo_harness.fleet.hub_capabilities -- the hub's copy of every harness's
capability catalog (Halo 3.0.6.0 "Fleet Missions" round R6).

A member's announce carries `capabilities_summary` and `capabilities_hash`
(fleet/capabilities.py `announce_fields`). When the hash is one the hub has
no catalog for, the hub asks that member once, on its own thread, with the
read-only `capabilities` fleet command through one of its live sessions; a
failed ask is retried after RETRY_S, never on every announce. A catalog that
arrives with a new hash is kept (`catalogs[harness]`) and a `fleet` frame
`{action: "capabilities", harness, name, hash}` goes to every sink. The hub's
own harness is in `entries()` too, from its cached catalog
(`capabilities.current`, gathered on a background thread when stale).

    entries() -> [{harness, name, local, online, hash, summary, chips, at, received, catalog | None, note?}]
"""

from __future__ import annotations

import threading
import time
from typing import Optional

from halo_harness.fleet import capabilities as caps

RETRY_S = 60.0
FETCH_WAIT_S = 30.0
MAX_TOOLS = 4000


def _trim(cat: dict) -> dict:
    """A member's catalog as the hub keeps it: scrubbed again (paths), at most MAX_TOOLS tools."""
    cat = caps.scrub(dict(cat))
    left, mcp = MAX_TOOLS, []
    for s in cat.get("mcp") or []:
        if isinstance(s, dict):
            tools = s.get("tools") if isinstance(s.get("tools"), list) else None
            if tools is not None:
                tools, left = tools[:max(0, left)], left - len(tools)
            mcp.append({**s, "tools": tools})
    cat["mcp"] = mcp
    return cat


class HubCaps:
    def __init__(self, state) -> None:
        self.state = state
        self.catalogs: dict = {}
        self.announced: dict = {}
        self.asked: dict = {}  # harness -> (hash, pending | failed | done, at)
        self.fetches: list = []  # (harness, hash): every ask sent, for the tests and the log
        self._lock = threading.Lock()

    # ---- members ------------------------------------------------------------------
    def seen(self, m, body: dict) -> None:
        """An announce: note its summary and hash; ask for the catalog once per new hash."""
        h = body.get("capabilities_hash")
        if not isinstance(h, str) or not h.strip():
            return
        h = h.strip()[:64]
        with self._lock:
            self.announced[m.id] = {"hash": h, "summary": str(body.get("capabilities_summary") or "")[:400]}
            m.caps = dict(self.announced[m.id])
            if (self.catalogs.get(m.id) or {}).get("hash") == h:
                return
            prev = self.asked.get(m.id)
            if prev and prev[0] == h and (prev[1] in ("pending", "done") or time.time() - prev[2] < RETRY_S):
                return
            self.asked[m.id] = (h, "pending", time.time())
        threading.Thread(target=self._fetch, args=(m.id, h), daemon=True, name="halo-hub-caps").start()

    def _fetch(self, hid: str, h: str, refresh: bool = False) -> "tuple[int, dict]":
        m = self.state.members.get(hid)
        sids = [s.get("session_id") for s in (m.sessions() if m is not None else []) if s.get("session_id")]
        if not sids:
            with self._lock:
                self.asked[hid] = (h, "failed", time.time())
            return 409, {"error": f"{m.name if m else hid} has no live session to ask"}
        with self._lock:
            self.fetches.append((hid, h))
        status, body = self.state.commands.send(hid, sids[0], "capabilities", {"refresh": True} if refresh else {},
                                                by=self.state.name, wait_s=FETCH_WAIT_S)
        cat = (body or {}).get("result") if status == 200 else None
        if isinstance(cat, dict) and cat.get("hash"):
            self.put(hid, cat)
            return 200, cat
        with self._lock:
            self.asked[hid] = (h, "failed", time.time())
        return status, body or {}

    def fetch_now(self, hid: str, refresh: bool = True) -> "tuple[int, dict]":
        """A member's catalog asked for now (Studio's Refresh): `(status, catalog | error)`."""
        h = (self.announced.get(hid) or {}).get("hash") or ""
        return self._fetch(hid, h, refresh)

    def put(self, hid: str, cat: dict) -> None:
        cat = {**_trim(cat), "received": time.time()}
        with self._lock:
            old = (self.catalogs.get(hid) or {}).get("hash")
            self.catalogs[hid] = cat
            self.asked[hid] = (cat["hash"], "done", time.time())
        if old != cat["hash"]:
            self.publish(hid, cat)

    def publish(self, hid: str, cat: dict) -> None:
        name = (cat.get("harness") or {}).get("name")
        self.state.publish({"session_id": None, "harness": hid, "event": "fleet", "turn": None, "agent_id": None,
                            "ts": time.time(), "data": {"action": "capabilities", "harness": hid, "name": name,
                                                        "hash": cat.get("hash")}})

    # ---- this harness -------------------------------------------------------------
    def local(self) -> Optional[dict]:
        hid = str(self.state.identity.get("id"))
        return local_catalog(self.state.home, lambda c: self.publish(hid, c))

    def entries(self, view: Optional[dict] = None) -> list:
        view = view if view is not None else self.state.view()
        out = []
        for h in view.get("harnesses") or []:
            hid = str(h.get("id"))
            cat = self.local() if h.get("local") else self.catalogs.get(hid)
            out.append(entry(h, cat, self.announced.get(hid), self.asked.get(hid)))
        return out


def local_catalog(home, on_change=None) -> Optional[dict]:
    """This harness's catalog: the cache; gathered now when there is none, on a background thread
    when it is stale (`on_change(catalog)` when that moved the hash)."""
    cat = caps.load(home)
    if cat is None:
        try:
            cat, _changed = caps.refresh(home)
        except Exception:
            return None
    elif caps.stale(cat):
        caps.refresh_in_background(home, (lambda c, changed: on_change(c) if changed else None) if on_change else None)
    return cat


def entry(h: dict, cat: Optional[dict], announced: Optional[dict] = None, asked=None) -> dict:
    """One harness's row in `GET /api/fleet/capabilities` (and the hub's local/capabilities route)."""
    row = {"harness": h.get("id"), "name": h.get("name"), "local": bool(h.get("local")), "online": bool(h.get("online")),
           "hash": (cat or {}).get("hash") or (announced or {}).get("hash"),
           "summary": caps.summary(cat) if cat else (announced or {}).get("summary") or "",
           "chips": caps.chips(cat) if cat else [], "at": (cat or {}).get("at"), "received": (cat or {}).get("received"),
           "catalog": cat}
    if cat is None:
        if asked and asked[1] == "pending":
            row["note"] = "asking it for its catalog"
        elif asked and asked[1] == "failed":
            row["note"] = "it did not answer `capabilities` (an older Halo, or no live session); asked again within a minute"
        elif not h.get("local"):
            row["note"] = "no catalog yet: it sends one with its next announce (a live session is needed)"
    elif announced and announced.get("hash") and announced["hash"] != cat.get("hash"):
        row["note"] = "a newer catalog is on its way"
    return row
