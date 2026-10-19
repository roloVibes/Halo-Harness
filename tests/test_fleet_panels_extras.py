"""tests.test_fleet_panels_extras -- Halo 3.0.5.0 "Fleet" round R4, hand-offs,
flight recordings, the canvas replay and the `halo fleet record | digest`
verbs, over the two-harness rig (tests/helpers/studio_fleet_rig.py) and real
HTTP: Take over writes the hand-off in the agent's transcript and its
parent's; Hand to writes `<repo>/.halo/handoffs/<id>.md`, then stops the
agent (3.1.4.0: a leftover `paperclip.enabled` changes nothing); a
recording is one self-contained HTML with no external URL (the no-URL gate of
tests/test_studio_dist.py) that the download route serves; the replay is the
ordered states of a finished session. Companion of tests/test_fleet_panels_api.py.

Run: python -m tests.test_fleet_panels_extras
"""
from __future__ import annotations

import http.client
import json
import re
import sys
import tempfile
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
def test_take_over_is_recorded_in_both_transcripts_and_reaches_a_member(ctx: Ctx):
    from halo_harness.fleet import journal
    from tests.helpers.studio_fleet_rig import MEMBER, MEMBER_SID, StudioFleetRig
    with StudioFleetRig() as rig:
        b = rig.agent("Research")["agent_id"]
        status, got = rig.api("POST", f"fleet/local/{rig.act.session_id}/agents/{b}/handoff",
                              {"mode": "take_over", "brief": "Only the tax rule: cite the line"})
        ctx.check(f"200, delivered as a redirect, got {status} {got}", status == 200 and got["result"]["result"]["mode"] == "redirect")
        mine = [e for e in _tail(rig, b) if e.get("kind") == "control" and e.get("cmd") == "agent_steer"]
        ctx.check(f"the agent's transcript records a take over, got {mine}", mine and mine[-1].get("handoff") == "take_over")
        notes = [e.get("text") for e in _tail(rig, "main") if e.get("kind") == "note"]
        ctx.check(f"its parent's transcript says it was taken over, got {notes}", any("taken over" in str(n) for n in notes))
        ctx.check("a take over needs a brief", rig.api("POST", f"fleet/local/{rig.act.session_id}/agents/{b}/handoff", {"mode": "take_over"})[0] == 422)
        ctx.check("an unknown mode is a 422", rig.api("POST", f"fleet/local/{rig.act.session_id}/agents/{b}/handoff", {"mode": "x"})[0] == 422)
        status, got = rig.api("POST", f"fleet/{MEMBER}/{MEMBER_SID}/agents/main/handoff", {"mode": "take_over", "brief": "Write the review now"})
        doc = rig.member_cmds[-1] if rig.member_cmds else {}
        ctx.check(f"a member's agent: the steer goes through the hub as a hand-off, got {status} {doc.get('fields')}",
                  status == 200 and doc.get("cmd") == "agent_steer" and doc["fields"].get("handoff") is True
                  and doc["fields"].get("mode") == "redirect")
        ctx.check("both are journaled", [r["action"] for r in journal.read(rig.state, 0, kinds=("handoff",))] == ["take_over", "take_over"])


@test
def test_hand_to_writes_the_markdown_then_stops(ctx: Ctx):
    from halo_harness.theme import set_config_value
    from tests.helpers.studio_fleet_rig import MEMBER, StudioFleetRig
    with StudioFleetRig() as rig:
        a = rig.agent("Implement")["agent_id"]
        status, got = rig.api("POST", f"fleet/local/{rig.act.session_id}/agents/{a}/handoff", {"mode": "hand_to", "to": "kali@lab"})
        path = Path(got.get("path") or "")
        md = path.read_text(encoding="utf-8") if path.is_file() else ""
        ctx.check(f"<repo>/.halo/handoffs/<id>.md, got {status} {got.get('path')}",
                  status == 200 and path.parent == rig.proj / ".halo" / "handoffs" and path.suffix == ".md")
        ctx.check("the brief: the task, who to, the hand-back section, the files", "Implement: apply the discount" in md
                  and "Handed to **kali@lab** by rolo@studio" in md and "## Its last hand-back" in md and "## Files it touched" in md)
        ctx.check(f"then the agent is stopped, got {got.get('stopped')}", got["stopped"]["status"] == 200)
        ctx.check("hand to nobody is a 422", rig.api("POST", f"fleet/local/{rig.act.session_id}/agents/{a}/handoff", {"mode": "hand_to"})[0] == 422)
        set_config_value("paperclip.enabled", True)  # 3.1.4.0: a leftover section of a removed feature
        try:
            b = rig.agent("Research")["agent_id"]
            status, got = rig.api("POST", f"fleet/local/{rig.act.session_id}/agents/{b}/handoff", {"mode": "hand_to", "to": MEMBER})
        finally:
            set_config_value("paperclip.enabled", False)
        ctx.check(f"a leftover paperclip.enabled still writes the note, no issue, got {status} {got}",
                  status == 200 and Path(got.get("path") or "").is_file() and "issue" not in got)
        ctx.check("and that agent is stopped too", got["stopped"]["status"] == 200)


@test
def test_a_recording_is_self_contained_and_the_route_serves_it(ctx: Ctx):
    from tests.helpers.studio_fleet_parts import PAST_REVIEWER, PAST_SID
    from tests.helpers.studio_fleet_rig import MEMBER, MEMBER_SID, StudioFleetRig
    with StudioFleetRig() as rig:
        status, got = rig.api("POST", f"fleet/local/{PAST_SID}/recording")
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
        status, headers, raw = _raw(rig, f"fleet/recordings/{path.name}")
        ctx.check(f"the download route serves the same bytes as HTML with its own CSP, got {status} {headers.get('Content-Type')}",
                  status == 200 and raw == body and headers["Content-Type"].startswith("text/html")
                  and "default-src 'none'" in headers["Content-Security-Policy"] and "attachment" in headers["Content-Disposition"])
        ctx.check("an unknown or traversing name is a 404", _raw(rig, "fleet/recordings/nope.html")[0] == 404
                  and _raw(rig, "fleet/recordings/..%2F..%2Fconfig.html")[0] == 404)
        status, got = rig.api("POST", f"fleet/local/{PAST_SID}/recording?agent={PAST_REVIEWER}")
        ctx.check(f"?agent= keeps that agent, got {got.get('name')} {got.get('agents')}", status == 200
                  and got["name"] == f"{PAST_SID}-{PAST_REVIEWER}.html" and got["agents"] == 1)
        status, got = rig.api("POST", f"fleet/{MEMBER}/{MEMBER_SID}/recording")
        ctx.check(f"a member's session records from its agents' tails through the hub, got {status} {got.get('agents')}",
                  status == 200 and got["agents"] == 2 and Path(got["path"]).is_file()
                  and not re.search(NO_URL, Path(got["path"]).read_bytes()))
        ctx.check("an unknown session is a 404", rig.api("POST", "fleet/local/nosuchsession/recording")[0] == 404)


@test
def test_the_replay_route_returns_the_ordered_states(ctx: Ctx):
    from tests.helpers.studio_fleet_parts import PAST_REVIEWER, PAST_SID
    from tests.helpers.studio_fleet_rig import StudioFleetRig
    with StudioFleetRig() as rig:
        status, got = rig.api("GET", f"fleet/replay?session={PAST_SID}")
        states = got.get("states") or []
        ctx.check(f"200 with the agents and their states in time order, got {status} {len(states)}", status == 200 and states
                  and all(states[i]["t"] <= states[i + 1]["t"] for i in range(len(states) - 1))
                  and {s["agent_id"] for s in states} == {"main", PAST_REVIEWER})
        ctx.check("the reviewer starts after the main agent and both end done",
                  min(s["t"] for s in states if s["agent_id"] == PAST_REVIEWER) > min(s["t"] for s in states if s["agent_id"] == "main")
                  and {s["state"] for s in states if s["activity"] == "done"} == {"done"} and "entries" not in got)
        ctx.check("the agents carry what the canvas matches on (role, bio, lineup)",
                  next(a for a in got["agents"] if a["agent_id"] == PAST_REVIEWER)["lineup"] == "halo-dev-cycle")
        ctx.check("no session is a 422; an unknown one a 404", rig.api("GET", "fleet/replay")[0] == 422
                  and rig.api("GET", "fleet/replay?session=nosuch")[0] == 404)


@test
def test_halo_fleet_record_and_digest_from_the_command_line(ctx: Ctx):
    from halo_harness.fleet import journal
    from tests.helpers.fleet_hub_rig import cli
    from tests.helpers.studio_fleet_parts import PAST_SID, seed_past
    root = Path(tempfile.mkdtemp(prefix="fleet-cli-"))
    (root / "shop").mkdir()
    seed_past(root / ".halo", root / "shop", t0=time.time() - 1800)
    journal.append(root / ".halo", "decision", harness="M", harness_name="kali@lab", what="Plan review", answer="approve", by="rolo")
    rc, out, err = cli(str(root), "record", PAST_SID[:12], "--json")
    got = json.loads(out) if rc == 0 else {}
    ctx.check(f"record by an id prefix writes the recording, got {rc} {err[-300:]}", rc == 0
              and Path(got["path"]) == root / ".halo" / "recordings" / f"{PAST_SID}.html" and got["agents"] == 2)
    rc, out, err = cli(str(root), "record", PAST_SID, "--agent", "nobody")
    ctx.check(f"an unknown agent: exit 1 with the agents listed, got {rc}", rc == 1 and "rv0past1" in err)
    rc, out, err = cli(str(root), "record", "zzzz")
    ctx.check("an unknown session: exit 1", rc == 1 and "no session" in err)
    rc, out, err = cli(str(root), "digest", "--since", "2h", "--json")
    d = json.loads(out) if rc == 0 else {}
    names = {h["name"]: h for h in d.get("harnesses") or []}
    ctx.check(f"digest --json: this harness's past session and the member's decision, got {rc} {sorted(names)}",
              rc == 0 and d["totals"]["started"] == 1 and names["kali@lab"]["decisions"][0]["answer"] == "approve")
    rc, out, err = cli(str(root), "digest", "--since", "45m")
    ctx.check(f"digest as text, got {out[:200]!r}", rc == 0 and out.startswith("Since ") and "kali@lab" in out)
    ctx.check("a since that does not parse: exit 1", cli(str(root), "digest", "--since", "later")[0] == 1)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="fleet panels extras tests"))
