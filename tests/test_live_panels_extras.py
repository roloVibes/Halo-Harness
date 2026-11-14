"""tests.test_live_panels_extras -- Halo 3.0.5.0 round R4, hand-offs, flight recordings and the canvas replay over
the rig (tests/helpers/studio_session_rig.py) and real HTTP: Take over writes the hand-off in the agent's transcript
and its parent's; Hand to writes `<repo>/.halo/handoffs/<id>.md`, then stops the agent (3.1.4.0: a leftover
`paperclip.enabled` changes nothing); a recording is one self-contained HTML with no external URL (the no-URL gate of
tests/test_studio_dist.py) that the download route serves; the replay is the ordered states of a finished session.
Companion of tests/test_live_panels_api.py.

Run: python -m tests.test_live_panels_extras
"""
from __future__ import annotations

import http.client
import json
import re
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
NO_URL = rb"https?://"  # tests/test_studio_dist.py's gate


def _tail(rig, aid: str) -> list:
    status, got = rig.api("GET", f"sessions/{rig.act.session_id}/agents/{aid}/tail?n=200")
    return got.get("events") or [] if status == 200 else []


def _raw(rig, path: str):
    conn = http.client.HTTPConnection("127.0.0.1", rig.server.server_address[1], timeout=30)
    try:
        conn.request("GET", "/api/" + path, headers={"Authorization": "Bearer " + rig.server.token})
        r = conn.getresponse()
        return r.status, dict(r.getheaders()), r.read()
    finally:
        conn.close()


@test
def test_take_over_is_recorded_in_both_transcripts(ctx: Ctx):
    from halo_harness.live import journal
    from tests.helpers.studio_session_rig import StudioSessionRig
    with StudioSessionRig() as rig:
        b = rig.agent("Research")["agent_id"]
        status, got = rig.api("POST", f"live/local/{rig.act.session_id}/agents/{b}/handoff",
                              {"mode": "take_over", "brief": "Only the tax rule: cite the line"})
        ctx.check(f"200, delivered as a redirect, got {status} {got}", status == 200 and got["result"]["result"]["mode"] == "redirect")
        mine = [e for e in _tail(rig, b) if e.get("kind") == "control" and e.get("cmd") == "agent_steer"]
        ctx.check(f"the agent's transcript records a take over, got {mine}", mine and mine[-1].get("handoff") == "take_over")
        notes = [e.get("text") for e in _tail(rig, "main") if e.get("kind") == "note"]
        ctx.check(f"its parent's transcript says it was taken over, got {notes}", any("taken over" in str(n) for n in notes))
        ctx.check("a take over needs a brief", rig.api("POST", f"live/local/{rig.act.session_id}/agents/{b}/handoff", {"mode": "take_over"})[0] == 422)
        ctx.check("an unknown mode is a 422", rig.api("POST", f"live/local/{rig.act.session_id}/agents/{b}/handoff", {"mode": "x"})[0] == 422)
        ctx.check("it is journaled", [r["action"] for r in journal.read(rig.state, 0, kinds=("handoff",))] == ["take_over"])


def _wait_listed(agent_id: str, timeout: float = 10.0) -> None:
    """The hand-off route reads the local view (a cached snapshot), not the live socket tree the rig read: wait until
    that view lists the agent, or the slow runner answers 404 "no agent" (Windows shard 0, run 41578034998)."""
    from halo_harness.peers import local_view
    deadline = time.time() + timeout
    while time.time() < deadline and not any(a.get("agent_id") == agent_id for s in local_view.snapshot().get("sessions") or []
                                                for a in s.get("agents") or []):
        time.sleep(0.1)


@test
def test_hand_to_writes_the_markdown_then_stops(ctx: Ctx):
    from halo_harness.theme import set_config_value
    from tests.helpers.studio_session_rig import StudioSessionRig
    with StudioSessionRig() as rig:
        a = rig.agent("Implement")["agent_id"]
        _wait_listed(a)  # the first hand-off hit the same cached-view 404 (Windows shard 1, run 41593119831)
        status, got = rig.api("POST", f"live/local/{rig.act.session_id}/agents/{a}/handoff", {"mode": "hand_to", "to": "you@studio"})
        path = Path(got.get("path") or "")
        md = path.read_text(encoding="utf-8") if path.is_file() else ""
        ctx.check(f"<repo>/.halo/handoffs/<id>.md, got {status} {got.get('path')}",
                  status == 200 and path.parent == rig.proj / ".halo" / "handoffs" and path.suffix == ".md")
        ctx.check("the brief: the task, who to, the hand-back section, the files", "Implement: apply the discount" in md
                  and "Handed to **you@studio** by you@studio" in md and "## Its last hand-back" in md and "## Files it touched" in md)
        ctx.check(f"then the agent is stopped, got {got.get('stopped')}", got["stopped"]["status"] == 200)
        ctx.check("hand to nobody is a 422", rig.api("POST", f"live/local/{rig.act.session_id}/agents/{a}/handoff", {"mode": "hand_to"})[0] == 422)
        set_config_value("paperclip.enabled", True)  # 3.1.4.0: a leftover section of a removed feature
        try:
            b = rig.agent("Research")["agent_id"]
            _wait_listed(b)
            status, got = rig.api("POST", f"live/local/{rig.act.session_id}/agents/{b}/handoff", {"mode": "hand_to", "to": "you@studio"})
        finally:
            set_config_value("paperclip.enabled", False)
        ctx.check(f"a leftover paperclip.enabled still writes the note, no issue, got {status} {got}",
                  status == 200 and Path(got.get("path") or "").is_file() and "issue" not in got)
        ctx.check("and that agent is stopped too", got["stopped"]["status"] == 200)


@test
def test_a_recording_is_self_contained_and_the_route_serves_it(ctx: Ctx):
    from tests.helpers.studio_session_parts import PAST_REVIEWER, PAST_SID
    from tests.helpers.studio_session_rig import StudioSessionRig
    with StudioSessionRig() as rig:
        status, got = rig.api("POST", f"live/local/{PAST_SID}/recording")
        path = Path(got.get("path") or "")
        ctx.check(f"a finished session records from disk to ~/.halo/recordings/<sid>.html, got {status} {got}",
                  status == 200 and path == rig.state / "recordings" / f"{PAST_SID}.html" and got["agents"] == 2 and got["states"] >= 4)
        body = path.read_bytes() if path.is_file() else b""
        ctx.check("no external URL anywhere in it (the dist gate)", body and not re.search(NO_URL, body))
        ctx.check("an agent's </script> never closes the data block", b"</script><script>alert" not in body and body.count(b"</script>") == 2)
        ctx.check("inline CSS and JS only, nothing loaded", b"<style>" in body and b"src=" not in body and b"<link" not in body)
        data = json.loads(re.search(rb'id="data">(.*?)</script>', body, re.S).group(1)) if body else {}
        ctx.check(f"the data: both agents, the states, the cost curve, the cwd's name only, got {sorted(data)}",
                  [a["agent_id"] for a in data["agents"]] == ["main", PAST_REVIEWER] and data["costs"][-1]["usd"] == 0.025
                  and data["cwd"] == "shop" and "https://example.com" in json.dumps(data["entries"]))
        status, headers, raw = _raw(rig, f"live/recordings/{path.name}")
        ctx.check(f"the download route serves the same bytes as HTML with its own CSP, got {status} {headers.get('Content-Type')}",
                  status == 200 and raw == body and headers["Content-Type"].startswith("text/html")
                  and "default-src 'none'" in headers["Content-Security-Policy"] and "attachment" in headers["Content-Disposition"])
        ctx.check("an unknown or traversing name is a 404", _raw(rig, "live/recordings/nope.html")[0] == 404
                  and _raw(rig, "live/recordings/..%2F..%2Fconfig.html")[0] == 404)
        status, got = rig.api("POST", f"live/local/{PAST_SID}/recording?agent={PAST_REVIEWER}")
        ctx.check(f"?agent= keeps that agent, got {got.get('name')} {got.get('agents')}", status == 200
                  and got["name"] == f"{PAST_SID}-{PAST_REVIEWER}.html" and got["agents"] == 1)
        ctx.check("an unknown session is a 404", rig.api("POST", "live/local/nosuchsession/recording")[0] == 404)


@test
def test_the_replay_route_returns_the_ordered_states(ctx: Ctx):
    from tests.helpers.studio_session_parts import PAST_REVIEWER, PAST_SID
    from tests.helpers.studio_session_rig import StudioSessionRig
    with StudioSessionRig() as rig:
        status, got = rig.api("GET", f"live/replay?session={PAST_SID}")
        states = got.get("states") or []
        ctx.check(f"200 with the agents and their states in time order, got {status} {len(states)}", status == 200 and states
                  and all(states[i]["t"] <= states[i + 1]["t"] for i in range(len(states) - 1))
                  and {s["agent_id"] for s in states} == {"main", PAST_REVIEWER})
        ctx.check("the reviewer starts after the main agent and both end done",
                  min(s["t"] for s in states if s["agent_id"] == PAST_REVIEWER) > min(s["t"] for s in states if s["agent_id"] == "main")
                  and {s["state"] for s in states if s["activity"] == "done"} == {"done"} and "entries" not in got)
        ctx.check("the agents carry what the canvas matches on (role, bio, lineup)",
                  next(a for a in got["agents"] if a["agent_id"] == PAST_REVIEWER)["lineup"] == "halo-dev-cycle")
        ctx.check("no session is a 422; an unknown one a 404", rig.api("GET", "live/replay")[0] == 422
                  and rig.api("GET", "live/replay?session=nosuch")[0] == 404)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="live panels extras tests"))
