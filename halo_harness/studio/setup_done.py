"""halo_harness.studio.setup_done -- Setup's Done (Halo 3.3.3.0 R1, "Setup hands
off to halo"; docs/STUDIO-sections.md "Setup"). The Summary's "Done: start
halo" posts `setup/done`; the terminal that ran `halo init` is waiting for it
(halo_harness/init_wait.py) and starts halo there.

    POST setup/done      writes `<state dir>/setup-done.json` {"at": <iso utc>, "home": <home_id>} (over any
                         earlier one), publishes a `setup` frame {stage: "done", at} on the live feed (another
                         open Studio tab on Setup leaves it too) -> 200 {ok: true, done_at}
    GET  setup/state     carries `done_at`: the marker's `at`, or null (studio/setup_state.py)

`setup_done_at(state_dir)` is the one reader: the state, the served page's boot attributes and the waiting
`halo init` all use it. The marker is not agent/loop.py's `.setup_done` (the Setup HOOK's marker): a different
file with a different job. Nothing secret is in either answer.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

MARKER = "setup-done.json"


def _dir(state_dir) -> Path:
    if state_dir:
        return Path(state_dir)
    from halo_harness.providers.config import default_state_dir
    return Path(default_state_dir())


def marker_path(state_dir=None) -> Path:
    return _dir(state_dir) / MARKER


def now_iso() -> str:
    """UTC, to the microsecond (a marker written in the same second as a wait began still reads as later)."""
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def parse_at(text) -> Optional[datetime]:
    if not isinstance(text, str) or not text.strip():
        return None
    try:
        at = datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return at if at.tzinfo is not None else at.replace(tzinfo=timezone.utc)


def setup_done_at(state_dir=None) -> Optional[str]:
    """The marker's `at` (an ISO UTC time), or None: no marker, or one that does not parse."""
    try:
        data = json.loads(marker_path(state_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    at = data.get("at") if isinstance(data, dict) else None
    return at if parse_at(at) is not None else None


def later(at, since) -> bool:
    """True when `at` is a time not before `since` (both ISO texts; `since` None: any time counts). Not before,
    rather than after: a Windows clock can read the same microsecond twice in a row."""
    a = parse_at(at)
    if a is None:
        return False
    s = parse_at(since) if since is not None else None
    return s is None or a >= s


def write_done(state_dir=None) -> str:
    """Write the marker (over any earlier one) and return its `at`."""
    from halo_harness.studio.setup_state import home_id
    where = _dir(state_dir)
    where.mkdir(parents=True, exist_ok=True)
    at = now_iso()
    tmp = where / (MARKER + ".tmp")
    tmp.write_text(json.dumps({"at": at, "home": home_id(where)}) + "\n", encoding="utf-8")
    tmp.replace(where / MARKER)
    return at


def post_done(req):
    try:
        at = write_done(req.state_dir)
    except OSError as e:
        return 500, {"error": f"setup-done.json was not written: {e}"}
    if req.server is not None:
        from halo_harness.studio.events import bridge_for
        try:
            bridge_for(req.server).publish_local({"session_id": "setup:done", "event": "setup",
                                                  "data": {"stage": "done", "at": at}, "ts": time.time()})
        except Exception:
            pass  # the GET's done_at still says so
    return 200, {"ok": True, "done_at": at}
