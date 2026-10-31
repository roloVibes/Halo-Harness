"""halo_harness.fleet.protocol -- the fleet wire, version 1 (Halo 3.0.5.0 R2).

Every message is one JSON document (UTF-8) carrying `"v": 1`. The hub port
serves only these routes (docs/FLEET.md has the full shapes):

    POST /fleet/v1/join         {v, harness, share, allow_control, a, ts, nonce, mac}   the code authenticates it
    POST /fleet/v1/announce     {v, link, harness, share, allow_control, allow_answers, sessions: [...],
                                 capabilities_summary?, capabilities_hash?}   (3.0.6.0 R6)
    POST /fleet/v1/frames       {v, link, frames: [frame, ...]}
    GET  /fleet/v1/stream?link= SSE to the member: `hello`, `command`, `kicked`; `: ping` every PING_S
    POST /fleet/v1/reply        {v, link, cid, state: asked|done|refused|error, result?, error?}
    GET  /fleet/v1/ping         -> {v, hub, you: {online, sessions, version_mismatch}}
    POST /fleet/v1/leave        {v}
    POST /fleet/v1/mission_files {v, op: list|get|put, mission, path?, data_b64?}   3.0.6.0 R7 (fleet/mission_files.py)
    POST /fleet/v1/recall       {v, query, k}   3.1.2.0 R3: a member's recall across the fleet (fleet/hub_recall.py)
    POST /fleet/v1/local/recall the same from this machine (admin token): `halo recall --fleet`
    POST /fleet/v1/local/coach-library {v, harness, entry}   3.1.6.0 R3 (admin token): one member's library entry,
                                through its `coach_library` command (`halo coach library fetch`)
    POST /fleet/v1/local/knowledge {v, harness, id | kind, all}   3.1.8.0 R4 (admin token): a member's findings or
                                decisions, through its `knowledge` command (`halo knowledge fetch`)
    GET  /fleet/v1/local/state  loopback peer + the hub's own admin token only: the merged view
    POST /fleet/v1/local/command  the same: {harness, session_id, cmd, fields} (the terminal table)

Up (member -> hub, every route but join and local/state) is signed with the
pair key: headers `X-Halo-Fleet-Member` (harness id), `-Ts` (unix seconds),
`-Nonce` (32 hex characters) and `-Sig` = hex HMAC-SHA256(key, canonical),
canonical = "halo-fleet-v1\\n<METHOD>\\n<path?query>\\n<member>\\n<ts>\\n<nonce>\\n
<sha256 hex of the body>". The hub refuses a request whose ts is more than
WINDOW_S away or whose nonce it has seen (a replay). Down (hub -> member):
each SSE doc carries `seq` (strictly increasing per stream), `ts` and `sig` =
hex HMAC-SHA256(key, "halo-fleet-v1-down\\n<member>\\n<link>\\n" + the doc's
canonical JSON without `sig`), so a command is the hub's or nobody's.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from typing import Callable, Optional

VERSION = 1
PREFIX = "/fleet/v1"
WINDOW_S = 120.0
PING_S = 10.0
H_MEMBER, H_TS, H_NONCE, H_SIG = "X-Halo-Fleet-Member", "X-Halo-Fleet-Ts", "X-Halo-Fleet-Nonce", "X-Halo-Fleet-Sig"
H_ADMIN = "X-Halo-Fleet-Admin"

READ_CMDS = ("status", "agents", "doctor", "capabilities")  # R4 `doctor`: fleet/health.py; 3.0.6.0 R6 `capabilities`
FULL_CMDS = ("agent_tail", "agent_follow", "tail")  # share: full only
ACTING_CMDS = ("agent_steer", "agent_stop", "pause", "resume", "shutdown", "steer", "interrupt")
TASK_CMDS = ("run_task",)  # 3.0.6.0 R7: a mission part, gated by fleet.allow_control like steer (fleet/mission_worker.py)
RECALL_CMDS = ("recall",  # 3.1.2.0 R3: {query, k}, answered from the member's own index unless fleet.recall.share: false
               "coach_library",  # 3.1.6.0 R3: {entry}, one entry of its coach library (orchestra/coach_library_share.py)
               "knowledge")  # 3.1.8.0 R4: {id} | {kind, all}, its findings / decisions (knowledge/share.py)
MODEL_CMDS = ("ollama_load", "ollama_unload",  # 3.3.5.0 R1: the Local tab's Load / Unload on a member's host
              "ollama_pull", "ollama_delete", "ollama_copy", "ollama_twin",  # R3; fleet/control_models.py, gated like steer
              "ollama_probe")  # 3.3.6.0 R1: the battery on a member's host
FLEET_CMDS = READ_CMDS + FULL_CMDS + ACTING_CMDS + ("answer", "note") + TASK_CMDS + RECALL_CMDS + MODEL_CMDS  # note: a person's message (R4)

TEXT_KINDS = frozenset({"text_chunk", "text_delta", "thinking_delta", "thinking_chunk"})
FULL_KINDS = TEXT_KINDS | {"agent_event"}  # a followed agent's entries carry its text
STATUS_KINDS = frozenset({"agent_state", "fleet"})


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _hmac(key: bytes, data: str) -> str:
    return hmac.new(key, data.encode("utf-8"), hashlib.sha256).hexdigest()


def canonical(method: str, path: str, member: str, ts: str, nonce: str, body: bytes) -> str:
    return "\n".join(("halo-fleet-v1", method.upper(), path, member, ts, nonce, hashlib.sha256(body or b"").hexdigest()))


def sign_headers(key: bytes, method: str, path: str, member: str, body: bytes = b"",
                 now: Optional[float] = None, nonce: Optional[str] = None) -> dict:
    ts = f"{(time.time() if now is None else now):.3f}"
    nonce = nonce or secrets.token_hex(16)
    return {H_MEMBER: member, H_TS: ts, H_NONCE: nonce, H_SIG: _hmac(key, canonical(method, path, member, ts, nonce, body))}


class ReplayGuard:
    """The nonces seen inside the window, per member."""

    def __init__(self, window_s: float = WINDOW_S) -> None:
        self.window_s = window_s
        self._seen: dict = {}
        self._lock = threading.Lock()

    def first_use(self, member: str, nonce: str, now: float) -> bool:
        with self._lock:
            if len(self._seen) > 4096:
                self._seen = {k: t for k, t in self._seen.items() if t > now}
            key = (member, nonce)
            if self._seen.get(key, 0) > now:
                return False
            self._seen[key] = now + 2 * self.window_s
            return True


def check_headers(headers, method: str, path: str, body: bytes, key_for: Callable[[str], Optional[bytes]],
                  guard: ReplayGuard, now: Optional[float] = None) -> "tuple[Optional[str], str]":
    """`(member id, "")` for a good signature, else `(None, reason)`:
    unsigned | unknown member | stale | bad signature | replayed."""
    member, ts, nonce, sig = (str(headers.get(h) or "") for h in (H_MEMBER, H_TS, H_NONCE, H_SIG))
    if not (member and ts and nonce and sig):
        return None, "unsigned"
    key = key_for(member)
    if not key:
        return None, "unknown member"
    now = time.time() if now is None else now
    try:
        stale = abs(now - float(ts)) > guard.window_s
    except ValueError:
        stale = True
    if stale:
        return None, "stale"
    if not hmac.compare_digest(sig.lower(), _hmac(key, canonical(method, path, member, ts, nonce, body))):
        return None, "bad signature"
    if not guard.first_use(member, nonce, now):
        return None, "replayed"
    return member, ""


def sign_down(key: bytes, member: str, link: str, doc: dict) -> dict:
    body = {k: v for k, v in doc.items() if k != "sig"}
    return {**body, "sig": _hmac(key, f"halo-fleet-v1-down\n{member}\n{link}\n" + canonical_json(body))}


def verify_down(key: bytes, member: str, link: str, doc: dict, last_seq: int,
                now: Optional[float] = None) -> str:
    """"" when `doc` is the hub's, in order and fresh; else the reason."""
    if not isinstance(doc, dict) or not isinstance(doc.get("sig"), str):
        return "unsigned"
    want = sign_down(key, member, link, doc)["sig"]
    if not hmac.compare_digest(doc["sig"].lower(), want):
        return "bad signature"
    seq = doc.get("seq")
    if not isinstance(seq, int) or seq <= last_seq:
        return "replayed"
    try:
        if abs((time.time() if now is None else now) - float(doc.get("ts"))) > WINDOW_S:
            return "stale"
    except (TypeError, ValueError):
        return "stale"
    return ""


# ---- what a share level lets through -------------------------------------------------

def frame_allowed(level: str, kind: str) -> bool:
    if level == "full":
        return True
    if level == "events":
        return kind not in FULL_KINDS
    return kind in STATUS_KINDS


def _base(path) -> Optional[str]:
    """The last component of a local path: full paths never leave a machine."""
    if not path:
        return None
    return os.path.basename(str(path).rstrip("/\\")) or str(path)


def scrub_agent(row: dict, level: str) -> dict:
    out = {k: v for k, v in (row or {}).items() if k != "transcript"}
    if level == "status":
        out.pop("last_text", None)
    return out


def scrub_session(row: dict) -> dict:
    out = {k: v for k, v in (row or {}).items() if k not in ("endpoint", "token", "token_env")}
    if "cwd" in out:
        out["cwd"] = _base(out["cwd"])
    if isinstance(out.get("project"), dict):
        out["project"] = {**out["project"], "root": _base(out["project"].get("root"))}
    return out


def scrub_frame(frame: dict, level: str) -> Optional[dict]:
    """The frame as `level` shares it, or None when it is not shared at all."""
    kind = str(frame.get("event") or "")
    if not frame_allowed(level, kind):
        return None
    data = frame.get("data")
    if kind == "agent_state" and isinstance(data, dict):
        return {**frame, "data": scrub_agent(data, level)}
    if kind == "fleet" and isinstance(data, dict):
        return {**frame, "data": scrub_session(data)}
    return dict(frame)


def doc(**fields) -> dict:
    return {"v": VERSION, **fields}


def encode(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8")


def decode(raw: bytes) -> dict:
    data = json.loads((raw or b"{}").decode("utf-8") or "{}")
    if not isinstance(data, dict):
        raise ValueError("a fleet message is one JSON object")
    if data.get("v", VERSION) != VERSION:
        raise ValueError(f"fleet protocol version {data.get('v')!r}; this harness speaks {VERSION}")
    return data
