"""tests.test_live_panels_more -- Halo 3.0.5.0 round R4, the rest of the panels' backend: conflicts (two sessions of
one harness editing one file, one session never) and the phone push (only while a transport listens). Companion of
tests/test_live_panels_api.py.

Run: python -m tests.test_live_panels_more
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
NOW = time.time()


def _wait(fn, timeout: float = 15.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        got = fn()
        if got:
            return got
        time.sleep(0.2)
    return None


@test
def test_conflicts_two_sessions_of_one_harness_but_never_one_session(ctx: Ctx):
    from halo_harness.live import conflicts
    proj = {"root": "/home/you/shop", "repo": "shop"}
    view = {"harnesses": [{"id": "M", "name": "kali@lab", "sessions": [
        {"session_id": "s1", "project": proj, "agents": [{"agent_id": "main", "current": "Edit: /home/you/shop/src/a.py"},
                                                         {"agent_id": "x2", "current": "Write: src/a.py"}]},
        {"session_id": "s2", "project": proj, "agents": [{"agent_id": "main", "current": "Edit: ./src/a.py"}]}]}]}
    t = conflicts.Touches()
    new = conflicts.note_view(t, view)
    ctx.check(f"three agents noted on the repo-relative path, got {new}", sorted(x[3] for x in new) == ["src/a.py"] * 3)
    found = conflicts.find(view, t, [])
    pairs = sorted(tuple(sorted((c["a"]["session_id"], c["b"]["session_id"]))) for c in found)
    ctx.check(f"s1 x s2 twice (two agents in s1), never s1 x s1, got {pairs}", pairs == [("s1", "s2"), ("s1", "s2")])
    ctx.check("a truncated label is never a file", conflicts.edited("Edit: /very/long/path/that/was/cut...") is None)


@test
def test_the_phone_push_only_while_a_transport_listens(ctx: Ctx):
    """3.3.13.0 R3: the attention queue's new rows are `asks` notes on the transports' seam (remote/notify.py) while a
    transport listens and remote.enabled is on; attention.signal false keeps them in Studio."""
    from halo_harness.config.paths import bridge_home
    from halo_harness.live import push
    from halo_harness.remote import notify as N
    from halo_harness.studio.live_watch_sources import push_ready
    from halo_harness.theme import set_config_value
    home = bridge_home()
    row = {"id": "permission:M:s2:p9", "kind": "permission", "harness": "M", "harness_name": "kali@lab", "session_id": "s2",
           "agent": "verifier", "what": "Permission: Bash", "detail": "make clean", "target": {"request_id": "p9"}}
    asks = {("M", "s2", "p9"): {"data": {"id": "p9", "name": "Bash", "input": {"command": "make clean"}}}}
    ctx.check("no transport listens: nothing is ready", not push.ready(home) and not push_ready(home))
    N.listen("signal", home)
    _rows, cur = N.since("", state_dir=home)
    try:
        ctx.check("a transport listens and remote.enabled is on (its default): ready", push.ready(home) and push_ready(home))
        set_config_value("attention.signal", False)
        from halo_harness.peers import identity
        identity.forget_cache()
        ctx.check("attention.signal false keeps it in Studio", not push_ready(home))
        set_config_value("attention.signal", True)
        identity.forget_cache()
        n = push.spool(home, [row, {**row, "id": "x", "local": True, "remote_attached": 1}], asks)
        got, _cur = N.since(cur, state_dir=home)
        ctx.check(f"one asks note (a session a phone is attached to is skipped), prefixed, got {got}", n == 1 and len(got) == 1
                  and got[0]["kind"] == "asks" and got[0]["text"].startswith("[kali@lab · verifier]")
                  and "make clean" in got[0]["text"] and got[0]["session"] == "s2")
        set_config_value("remote.enabled", False)
        ctx.check("remote.enabled false: not ready", not push.ready(home))
    finally:
        set_config_value("remote.enabled", True)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="live panels more tests"))
