"""halo_harness.update_note -- the words after an update answer that came from the cache (Halo 3.3.16.0).

`latest_available` answers from `~/.halo/update-check.json` when the live check fails (offline, a short outage, a
rate limit) or is switched off. Until now that answer printed exactly like a live one, so a box behind a dead router
read "available (stable): v3.3.14.0" and `halo update` said "already up to date" while a newer tag existed. Every
place that prints the answer appends `cache_note(avail)`:

    (from the cache, checked 6 h ago; the live check failed: network unavailable -- run `halo update --check` again
     when you are online)
"""
from __future__ import annotations

import time


def age_words(seconds: float) -> str:
    s = max(0, int(seconds))
    if s < 90:
        return f"{s} s"
    if s < 5400:
        return f"{round(s / 60)} min"
    if s < 172800:
        return f"{round(s / 3600)} h"
    return f"{round(s / 86400)} d"


def cache_note(avail: dict, now: float | None = None) -> str:
    """"" for a live answer; otherwise one parenthetical saying the answer is the cache's, how old it is, and why the
    live check did not replace it (when it was tried)."""
    if not isinstance(avail, dict) or avail.get("source") != "cache":
        return ""
    checked = avail.get("checked_at")
    age = f", checked {age_words((now if now is not None else time.time()) - float(checked))} ago" if checked else ""
    why = avail.get("live_reason")
    if why:
        return f" (from the cache{age}; the live check failed: {why} -- run `halo update --check` again when you are online)"
    return f" (from the cache{age}; {avail.get('reason') or 'the live check did not run'})"
