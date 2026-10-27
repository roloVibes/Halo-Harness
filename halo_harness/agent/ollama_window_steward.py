"""halo_harness.agent.ollama_window_steward -- Halo 3.3.4.0 R3: the two
parked 3.2.3.0 bugs the steward's rules found, fixed on the session side
(agent/ollama_window.py keeps the window rule; this is what it lacked).

- `compact_due` -- the compaction trigger, per model, BEFORE the call.
  `_maybe_auto_compact` runs after a step, on the reply's own prompt count,
  against the window that call was sent at; on an Ollama route that window
  follows the prompt up to the ceiling and the reply's room is squeezed to
  make it fit, so a request whose prompt part sits anywhere up to the
  ceiling minus 1,024 went out uncompacted (a big tool result took a
  session from under the trigger to 99 % of the window in one step, and the
  reply was cut there). Now a request whose prompt part passes the
  profile's `compact_at` (0.8 when unset) of the largest window the call
  can get compacts first. A compaction that freed nothing is not repeated
  until the prompt grew by a tenth of the window again.
- `squeezed_cut` -- a reply that stopped at a `num_predict` the WINDOW
  squeezed (`WindowChoice.num_predict`, the room left under the ceiling) is
  the window filling up, the same "context full" as a reply cut at the
  window's end -- it was missed whenever Ollama read fewer tokens than
  Halo's estimate (`is_window_cut` asks for 97 % of the window), and the
  cut reply was kept as a finished answer, so the next request carried the
  cut text again. Now it takes the trim recovery (a larger window or
  compaction, the cut reply never kept).
"""

from __future__ import annotations

import time
from typing import Optional

REGROW_SHARE = 0.1
NOTE_FRESH_S = 3600.0  # a profile changed in the last hour says its note once per session


def note_prepared(st: dict, estimate: int, reserve: int, session=None) -> None:
    """After a compaction `compact_due` asked for, the first request's
    prompt part is the mark the next compaction must pass. A profile the
    steward (or the hub) changed since this session's last call says its
    note once, in the status area (the session's Ollama notices)."""
    profile = (st.get("last") or {}).get("profile") or {}
    if profile.get("at") and profile.get("by") in ("steward", "hub") and profile["at"] != st.get("profile_at"):
        st["profile_at"] = profile["at"]
        from halo_harness.ollama_steward.ledger import parse_at
        fresh = time.time() - (parse_at(profile["at"]) or 0) < NOTE_FRESH_S
        notices = getattr(session, "_pending_ollama_notices", None)
        if fresh and isinstance(notices, list) and profile.get("note"):
            notices.append(profile["note"])
    if st.get("compact_pending"):
        st["compact_pending"] = False
        st["compacted_at"] = max(0, int(estimate) - int(reserve))


def compact_due(session) -> Optional[str]:
    """The one line when the session's own request is past `compact_at` of
    the most its window can be (the caller compacts first), else None."""
    from halo_harness.agent.ollama_window import _state
    from halo_harness.ollama_steward.profiles import compact_at
    from halo_harness.providers.ollama_prompt import fmt_tokens, fmt_window
    st = _state(session)
    last = st.get("last")
    if not last or not last["choice"].fits:
        return None
    window = last["choice"].ceiling or 0
    part = int(last["estimate"]) - int(last.get("reserve") or 0)
    share = compact_at(last.get("profile"))
    if window <= 0 or part <= share * window:
        return None
    mark = st.get("compacted_at")
    if isinstance(mark, int) and part <= mark + REGROW_SHARE * window:
        return None
    st["compact_pending"] = True
    return (f"the request ({fmt_tokens(part)} tokens) is past {int(share * 100)} % of {last['model']}'s window on "
            f"{last['host_name']} ({fmt_window(window)}): compacted before the call")


def squeezed_cut(session, done_reason, eval_count, num_predict) -> bool:
    """A `done_reason: "length"` reply that used the room the window left it."""
    from halo_harness.agent.ollama_window import _state
    last = _state(session).get("last") or {}
    room = getattr(last.get("choice"), "num_predict", None)
    if done_reason != "length" or not isinstance(room, int) or room <= 0:
        return False
    if not isinstance(eval_count, int) or not isinstance(num_predict, int) or num_predict <= 0:
        return False
    return num_predict <= room and eval_count >= 0.9 * num_predict


def host_for(session, host, ref, env=None):
    """A profile's `host_for`: ask this model on that host instead (a host
    entry configured here). Returns `(host, ref)` for the window decision and
    leaves the creds override `_build_request` uses (None: no redirect)."""
    session._ollama_creds_override = None
    try:
        from halo_harness.ollama_steward.profiles import lookup
        from halo_harness.providers.ollama import resolve_ollama_host
        other_name = (lookup(host, ref.model) or {}).get("host_for")
        other = resolve_ollama_host(other_name, env) if other_name else None
    except Exception:
        return host, ref
    if other is None or str(other.url).rstrip("/") == str(host.url).rstrip("/"):
        return host, ref
    import dataclasses
    from halo_harness.providers.stream import ProviderCreds
    session._ollama_creds_override = ProviderCreds(base_url=other.url, api_key=other.api_key or "")
    try:
        return other, dataclasses.replace(ref, host=other.name)
    except (TypeError, ValueError):
        return other, ref
