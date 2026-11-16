"""halo_harness.studio.setup_done -- Setup's Done (Halo 3.3.3.0 R1, "Setup hands
off to halo"; docs/STUDIO-sections.md "Setup"). The Summary's "Done: start
halo" posts `setup/done`; the terminal that ran `halo init` is waiting for it
(halo_harness/init_wait.py) and starts halo there.

    POST setup/done      writes `<state dir>/setup-done.json` {"at": <iso utc>, "home": <home_id>} (over any
                         earlier one), publishes a `setup` frame {stage: "done", at} on the live feed (another
                         open Studio tab on Setup leaves it too) -> 200 {ok: true, done_at, starts, line}
                         3.3.15.0 R6 `starts`: "init" (a `halo init` terminal waits: "halo is starting in your
                         terminal"), "terminal" (none waits: Studio opened a terminal running halo) or "none" (none
                         could open: "no terminal found to start halo in; run `halo` yourself"); `line` says which
    GET  setup/state     carries `done_at`: the marker's `at`, or null (studio/setup_state.py); 3.3.15.0 R6
                         `init_waiting`: a `halo init` terminal waits for Done now (studio/init_waiting.py)

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


def is_new(at, before) -> bool:
    """True when `at` is a Done written since the wait began: it parses and is not `before`, the marker's `at` when
    the wait began (None: there was none). Not "later than the wait's start": a wall clock stepped back during Setup
    (NTP after a VM restore or a wake) gave a fresh Done an earlier time, and init waited for ever (fx studio)."""
    a = parse_at(at)
    if a is None:
        return False
    b = parse_at(before) if before is not None else None
    return b is None or a != b


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


def starts_halo(state_dir, cwd) -> "tuple[str, str]":
    """3.3.15.0 R6: who starts halo after Done: `("init", line)` when a `halo init` terminal waits for it
    (studio/init_waiting.py), `("terminal", line)` when Studio opened one (studio/halo_terminal.py), `("none", line)`
    when neither could: the line says to run `halo`."""
    from halo_harness.studio import halo_terminal, init_waiting
    if init_waiting.waiting(state_dir):
        return "init", halo_terminal.INIT_LINE
    opened, line = halo_terminal.open_halo(cwd or Path.cwd())
    return ("terminal" if opened else "none"), line


NO_PROVIDER = ("No provider is set up yet, and halo cannot start a session without one: set one up on the Providers "
               "page, then pick a default model.")
NO_MODEL = "No default model is picked yet, and halo cannot start a session without one: pick one on the Default model page."


def _set_providers(cwd) -> "list[str]":
    from halo_harness.init_providers import TAB_PROVIDERS, tab_credential_state
    out = []
    for name in TAB_PROVIDERS:
        try:
            if tab_credential_state(name, cwd=cwd).get("configured"):
                out.append(name)
        except Exception:
            continue
    return out


def _any_provider(cwd) -> bool:
    return bool(_set_providers(cwd))


def _not_ready(line: str, page: str, cwd) -> dict:
    """jb10: `usable` -- a provider a session can call is set up (the rail ticks Providers only then): one with a
    key or a login. An Ollama host alone is not: it is usable once one of its models is the default (then `ok`)."""
    return {"ok": False, "line": line, "page": page, "usable": any(p != "ollama" for p in _set_providers(cwd))}


def ready(cwd=None, state_dir=None) -> dict:
    """Local models only (fix): `{ok, line, page}`, whether a session started now has a model it can call, decided by
    the resolver a session uses (resolve_default_model_raw -> parse_model_ref -> the session's credentials; no server
    is asked). Not ok: `line` says what is missing and `page` is the Setup page that fixes it (providers | model).
    A Setup that added only an Ollama host and picked no model ended in 'OpenRouter not configured'."""
    from types import SimpleNamespace

    from halo_harness.headless import _resolve_creds
    from halo_harness.model import no_default_model_line, parse_model_ref, resolve_default_model_raw
    from halo_harness.providers.config import listing_effective_env, load_routes
    env = listing_effective_env(Path(cwd) if cwd else None)
    routes = load_routes(_dir(state_dir) / "routes.json")
    raw = resolve_default_model_raw(routes, env=env)
    try:
        creds = _resolve_creds(parse_model_ref(raw, routes), SimpleNamespace(effective_env=env))
    except Exception as e:  # a ref the resolver refuses (a disabled provider, a name it does not know)
        return _not_ready(f"The default model {raw} cannot be used ({e}): pick another on the Default model page.",
                          "model", cwd)
    if creds is not None:
        return {"ok": True, "line": "", "page": "", "usable": True}
    if no_default_model_line(raw, routes):
        return _not_ready(NO_MODEL, "model", cwd) if _any_provider(cwd) else _not_ready(NO_PROVIDER, "providers", cwd)
    return _not_ready(f"The default model {raw} has no provider set up here: set one up on the Providers page, or pick "
                      "another model on the Default model page.", "providers", cwd)


def post_done(req):
    why = ready(req.cwd, req.state_dir)  # the page offers no Done then; a Done sent anyway gets the same line
    if not why["ok"]:
        return 409, {"error": why["line"], "ready": why}
    try:
        at = write_done(req.state_dir)
    except OSError as e:
        return 500, {"error": f"setup-done.json was not written: {e}"}
    try:
        starts, line = starts_halo(req.state_dir, req.cwd)
    except Exception as e:  # the Done still counts; the line says what to do
        from halo_harness.studio.halo_terminal import NO_TERMINAL
        starts, line = "none", f"{NO_TERMINAL} ({type(e).__name__})"
    if req.server is not None:
        from halo_harness.studio.events import bridge_for
        try:
            bridge_for(req.server).publish_local({"session_id": "setup:done", "event": "setup",
                                                  "data": {"stage": "done", "at": at}, "ts": time.time()})
        except Exception:
            pass  # the GET's done_at still says so
    return 200, {"ok": True, "done_at": at, "starts": starts, "line": line}
