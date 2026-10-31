"""halo_harness.fleet.ollama_share -- Halo 3.3.4.0 R2: the hub sees every
halo's calls to the model servers.

A member's relay (fleet/relay_hub.py) calls `Forwarder.tick(link, link_id)`
on every pass of its loop: the new lines of this machine's ledger
(`<state>/ollama/traffic.jsonl`, ollama_steward/ledger.py) go to the hub in
one signed `POST /fleet/v1/ollama {link, lines}` every FLUSH_S seconds or as
soon as BATCH_LINES are waiting, and when the last session closes. A cursor
per hub (`<state>/ollama/share-<hub>.json`: the byte offset and the file's
first line; a first run starts at the top) survives restarts and a rotation; several processes on one
machine take turns through its lock, so a line is sent once.

`fleet.ollama.share` (docs/CONFIG.md):

    auto   (default) the calls to a host this machine does not serve itself
           (the host url is not a loopback name or one of this machine's own
           addresses): the Mac's calls to the PC's Ollama reach the PC's hub,
           calls to the Mac's own local server stay on the Mac
    all    every line, this machine's own server's too (`true` reads the same)
    off    none (`false` too); the cursor still moves, so a line recorded
           while it is off is never sent later

The hub (`serve`, from fleet/hub_http.py) appends what a member sends to ITS
ledger with `from` set to the member's name, so `read_calls` on the serving
machine returns the Mac's lines beside its own. 3.3.4.0 R3: the hub's
answer carries its steward profiles (`ollama.profiles`) keyed by the
member's own host names, and the member keeps them (`take_profiles`, never
over its own `by: "user"` entry); while sharing is not `off` the member asks
every FLUSH_S even with no line to send, so a profile reaches it within half
a minute. 3.3.4.0 R4: and the hub's newest steward note (`steward_note`,
notes.py), kept in `<state>/ollama/hub-note.json` for the member's TUI.
3.3.5.0 R1: each push also carries the member's newest resources samples
(`resources`, ollama_steward/resources_share.py); the hub keeps 5 minutes.
"""

from __future__ import annotations

import json
import socket
import time
import urllib.parse
from pathlib import Path
from typing import Optional

from halo_harness.fleet import identity, protocol

FLUSH_S = 30.0
BATCH_LINES = 50
MAX_LINES = 500  # one request carries at most this many; the hub reads at most this many
CHECK_S = 2.0
_HEAD_BYTES = 200
_OWN: dict = {}


def mode() -> str:
    """`fleet.ollama.share` -> "auto" | "all" | "off" (`true` / `false` read as all / off)."""
    raw = identity.config_value("fleet.ollama.share", "auto")
    if raw is True or str(raw).strip().lower() in ("true", "all", "on"):
        return "all"
    if raw is False or str(raw).strip().lower() in ("false", "off", "none"):
        return "off"
    return "auto"


def own_addresses() -> set:
    """Loopback names, this machine's host name and its LAN address (cached a minute)."""
    if _OWN.get("at", 0) > time.monotonic() - 60:
        return _OWN["set"]
    names = {"127.0.0.1", "::1", "localhost", "0.0.0.0"}
    try:
        host = socket.gethostname().lower()
        names |= {host, host.split(".")[0], host + ".local"}
        from halo_harness.fleet.hub import lan_address
        names.add(lan_address())
    except Exception:
        pass
    _OWN.update(at=time.monotonic(), set=names)
    return names


def served_here(url: str) -> bool:
    try:
        hostname = (urllib.parse.urlparse(str(url or "")).hostname or "").lower()
    except ValueError:
        return False
    return hostname.startswith("127.") or hostname in own_addresses()


def wanted(line: dict, how: str) -> bool:
    """Is this ledger line sent to a hub under `how` ("auto" | "all" | "off")?"""
    if how == "off" or not isinstance(line, dict):
        return False
    if line.get("from") not in (None, identity.fleet_name()):
        return False  # a line this machine took in as a hub is never sent on
    return how == "all" or not served_here((line.get("host") or {}).get("url"))


class Forwarder:
    def __init__(self, entry: dict, home: Optional[Path] = None) -> None:
        self.hub = str(entry.get("hub_id") or entry.get("url") or "hub")
        self.home = Path(home) if home is not None else identity.home()
        self.last_flush = time.monotonic()
        self.last_check, self.sent_t = 0.0, 0.0

    def _paths(self) -> "tuple[Path, Path, Path]":
        d = self.home / "ollama"
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in self.hub)[:64]
        return d / "traffic.jsonl", d / "traffic.1.jsonl", d / f"share-{safe}.json"

    @staticmethod
    def _head(path: Path) -> str:
        try:
            with open(path, "rb") as f:
                return f.read(_HEAD_BYTES).decode("utf-8", "replace")
        except OSError:
            return ""

    def _cursor(self, cpath: Path, current: Path) -> dict:
        try:
            cur = json.loads(cpath.read_text(encoding="utf-8"))
            if isinstance(cur, dict) and isinstance(cur.get("offset"), int):
                return cur
        except (OSError, ValueError):
            pass
        return {"offset": 0, "head": self._head(current)}  # first run: the whole ledger

    @staticmethod
    def _read(path: Path, offset: int, head: str) -> list:
        """Whole lines from `offset` -> [(line, the cursor just after it)]."""
        try:
            with open(path, "rb") as f:
                f.seek(offset)
                data = f.read(8 * 2 ** 20)
        except OSError:
            return []
        out, pos = [], offset
        for raw in data.split(b"\n")[:-1]:  # the last piece is a partial line (or empty)
            pos += len(raw) + 1
            try:
                obj = json.loads(raw.decode("utf-8", "replace"))
            except ValueError:
                continue
            if isinstance(obj, dict):
                out.append((obj, {"offset": pos, "head": head}))
        return out

    def pending(self) -> "tuple[list, dict]":
        """[(line, cursor after it)] since the saved cursor, and the cursor after all of them."""
        current, rotated, cpath = self._paths()
        cur = self._cursor(cpath, current)
        now_head = self._head(current)
        rows: list = []
        from halo_harness.ollama_steward.ledger import same_file
        if cur.get("head") and not same_file(cur["head"], now_head):
            if same_file(cur["head"], self._head(rotated)):  # rotated since: finish the old file first
                rows = self._read(rotated, cur["offset"], cur["head"])
            cur = {"offset": 0, "head": now_head}
        rows += self._read(current, cur["offset"], now_head)
        return rows, (rows[-1][1] if rows else {"offset": cur["offset"], "head": cur.get("head") or now_head})

    def tick(self, link, link_id: str, force: bool = False) -> int:
        """Send what is due; returns how many lines went. Never raises."""
        try:
            how = mode()
            current, _rotated, cpath = self._paths()
            now = time.monotonic()
            due = force or now - self.last_flush >= FLUSH_S
            if (not due and now - self.last_check < CHECK_S) or not current.exists():
                return 0
            self.last_check = now
            from halo_harness.filelock import file_lock
            with file_lock(cpath, timeout=0) as held:
                if not held:
                    return 0
                rows, cursor = self.pending()
                send = [(x, c) for x, c in rows if wanted(x, how)]
                if not due and len(send) < BATCH_LINES:
                    return 0
                if len(send) > MAX_LINES:
                    send, cursor = send[:MAX_LINES], send[MAX_LINES - 1][1]
                if send or how != "off":  # 3.3.4.0 R3: the answer carries the hub's profiles
                    from halo_harness.ollama_steward.resources_share import read_recent  # 3.3.5.0 R1
                    samples = read_recent(self.home, self.sent_t) if how != "off" else []
                    from halo_harness.fleet.control_pulls import read_pulls  # 3.3.5.0 R3: the pull jobs a hub asked for
                    from halo_harness.fleet.control_probes import read_crashes, read_events, read_probes  # 3.3.6.0 R1-R3
                    reply = link.request("POST", protocol.PREFIX + "/ollama", protocol.doc(
                        link=link_id, lines=[x for x, _c in send], resources=samples, pulls=read_pulls(self.home),
                        probes=read_probes(self.home), crashes=read_crashes(self.home), events=read_events(self.home)))
                    self.sent_t = max([self.sent_t] + [float(x.get("t") or 0) for x in samples])
                    take_profiles(reply)
                    take_note(reply, self.home)
                cpath.parent.mkdir(parents=True, exist_ok=True)
                cpath.write_text(json.dumps(cursor), encoding="utf-8")
                self.last_flush = now
                return len(send)
        except Exception:
            self.last_flush = time.monotonic()  # a hub that cannot take them now is tried again next period
            return 0


from halo_harness.fleet.ollama_share_take import take_note, take_profiles  # noqa: E402  (the member's side of an answer)


def accept(home, member_name: str, lines: list) -> int:
    """The hub's side: append a member's lines to this machine's ledger with `from` = the member's name."""
    from halo_harness.ollama_steward import ledger
    clean = []
    for x in (lines or [])[:MAX_LINES]:
        if isinstance(x, dict):
            row = {k: x.get(k) for k in ledger.FIELDS}
            row["from"] = member_name
            clean.append(row)
    return ledger.append_lines(home, clean)


def serve(handler):
    """`POST /fleet/v1/ollama {link, lines}` on the hub port (a member's signed request)."""
    try:
        raw = handler._raw_body()
    except ValueError as e:
        return handler._json(413, {"error": str(e)})
    hid = handler._signed(raw)
    if not hid:
        return None
    try:
        body = protocol.decode(raw)
    except ValueError as e:
        return handler._json(400, {"error": f"bad request: {e}"})
    member = handler.hub.state.members.get(hid)
    if member is None:
        return handler._json(403, {"error": "not a member of this hub"})
    lines = body.get("lines") if isinstance(body.get("lines"), list) else []
    n = accept(handler.hub.home, member.name, lines)
    from halo_harness.ollama_steward.resources_share import take_remote  # 3.3.5.0 R1: the member's samples
    take_remote(handler.hub.home, member.name, body.get("resources"))
    from halo_harness.fleet.control_pulls import take_pulls  # 3.3.5.0 R3
    take_pulls(member.name, body.get("pulls"))
    from halo_harness.fleet.control_probes import take_crashes, take_events, take_probes  # 3.3.6.0 R1-R3
    take_probes(handler.hub.home, member.name, body.get("probes"))
    take_crashes(handler.hub.home, member.name, body.get("crashes"))
    take_events(handler.hub.home, member.name, body.get("events"))  # R3: the member's server events (log_status.ladder)
    try:  # 3.3.4.0 R3: the hub's profiles, keyed by the member's own host names
        from halo_harness.ollama_steward.profiles import payload_for_member
        profiles = payload_for_member(handler.hub.home, member.name)
    except Exception:
        profiles = {}
    from halo_harness.ollama_steward.notes import share_payload  # 3.3.4.0 R4: the hub's newest steward note
    note = share_payload(handler.hub.home, handler.hub.name)
    return handler._json(200, protocol.doc(ok=True, accepted=n, profiles=profiles, steward_note=note))
