"""tests.test_fleet_studio_routes -- Halo 3.0.5.0 "Fleet" round R3, the
routes behind the Studio Fleet section and Live Roles, over real HTTP to an
in-process Studio: POST fleet/pair (a one-time code, the join line, the QR
matrix), GET/POST fleet/settings (share and control as config keys, a bad
value or a config that does not parse leaves the file alone), POST
fleet/kick, GET fleet/history (past runs by role or bio from the transcripts'
meta, with the task and the summed cost); then, over the two-harness rig
(tests/helpers/studio_fleet_rig.py), GET fleet with both harnesses and five
agents, a member's tail through the hub, and a sub-agent's meta file with its
role and lineup; the framed page's Live Roles files are wired and small.

Run: python -m tests.test_fleet_studio_routes
"""
from __future__ import annotations

import http.client
import json
import sys
import tempfile
import threading
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
LEGACY = REPO / "halo_harness" / "studio" / "static" / "legacy"


class _Studio:
    def __enter__(self):
        from halo_harness.studio.server import start_server
        self.state = Path(tempfile.mkdtemp(prefix="fleet-routes-")) / ".halo"
        self.state.mkdir()
        self.srv = start_server(port=0, cwd=self.state.parent, state_dir=self.state)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *a):
        self.srv.shutdown()
        self.srv.server_close()

    def api(self, method: str, path: str, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.srv.server_address[1], timeout=30)
        try:
            conn.request(method, "/api/" + path, body=json.dumps(body).encode("utf-8") if body is not None else None,
                         headers={"Authorization": "Bearer " + self.srv.token, "Content-Type": "application/json"})
            resp = conn.getresponse()
            return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
        finally:
            conn.close()


@test
def test_pair_makes_a_one_time_code_with_its_join_line_and_qr(ctx: Ctx):
    from halo_harness.fleet.pairing import HubPairing
    with _Studio() as s:
        status, got = s.api("POST", "fleet/pair", {"ttl": 600})
        ctx.check(f"200 and six words, got {status} {got.get('code')!r}", status == 200 and len(str(got.get("code")).split()) == 6)
        ctx.check(f"the join line names the hub and the code, got {got.get('join')!r}",
                  got["join"].startswith("halo fleet join ") and got["url"] in got["join"] and f'--code "{got["code"]}"' in got["join"])
        m = got.get("matrix") or []
        ctx.check(f"the QR is a square matrix of 0/1, got {len(m)} rows", len(m) >= 21 and all(len(r) == len(m) and set(r) <= {0, 1} for r in m))
        ctx.check("the QR carries the join address, not the code", got["qr"].startswith("halo-fleet://join?v=1&url=") and got["code"] not in got["qr"])
        ctx.check("no hub runs here: it says so", got.get("hub_running") is False and got.get("ttl") == 600)
        ctx.check("the code is kept as a hash for this home's hub", HubPairing(s.state).active_codes() == 1)
        ctx.check("a ttl that is not a number is a 422", s.api("POST", "fleet/pair", {"ttl": "soon"})[0] == 422)


@test
def test_settings_read_and_write_share_and_control(ctx: Ctx):
    with _Studio() as s:
        status, got = s.api("GET", "fleet/settings")
        ctx.check(f"the defaults: events and ask, no hub, nobody, got {got}", status == 200 and got["share"] == "events"
                  and got["allow_control"] == "ask" and got["hubs"] == [] and got["members"] == [] and got["hub"]["serving"] is False)
        ctx.check("the levels to pick from", got["levels"] == {"share": ["status", "events", "full"], "allow_control": ["none", "ask", "all"]})
        status, got = s.api("POST", "fleet/settings", {"share": "full", "allow_control": "all"})
        cfg = json.loads((s.state / "config.json").read_text(encoding="utf-8"))
        ctx.check(f"written as fleet.share / fleet.allow_control, got {cfg}", status == 200 and cfg["fleet"] == {"share": "full", "allow_control": "all"}
                  and got["share"] == "full" and got["allow_control"] == "all")
        before = (s.state / "config.json").read_bytes()
        ctx.check("a level that does not exist is a 422", s.api("POST", "fleet/settings", {"share": "everything"})[0] == 422)
        ctx.check("nothing to set is a 422", s.api("POST", "fleet/settings", {})[0] == 422)
        ctx.check("and the file is untouched", (s.state / "config.json").read_bytes() == before)
        (s.state / "config.json").write_text("{not json", encoding="utf-8")
        ctx.check("a config.json that does not parse: 409, never overwritten",
                  s.api("POST", "fleet/settings", {"share": "status"})[0] == 409 and (s.state / "config.json").read_text(encoding="utf-8") == "{not json")


@test
def test_kick_removes_a_member(ctx: Ctx):
    from halo_harness.fleet.pairing import HubPairing
    with _Studio() as s:
        HubPairing(s.state).add_member({"id": "abc123member", "name": "kali@lab", "host": "kali"}, b"k" * 32)
        status, got = s.api("GET", "fleet/settings")
        ctx.check(f"the member is listed without its key, got {got['members']}",
                  [m["id"] for m in got["members"]] == ["abc123member"] and "key_hex" not in got["members"][0])
        status, got = s.api("POST", "fleet/kick", {"harness": "abc123member"})
        ctx.check(f"kicked, got {status} {got}", status == 200 and got["kicked"]["name"] == "kali@lab" and not HubPairing(s.state).members())
        ctx.check("an unknown member is a 404", s.api("POST", "fleet/kick", {"harness": "nobody"})[0] == 404)
        ctx.check("no member named is a 422", s.api("POST", "fleet/kick", {})[0] == 422)


def _seed_history(state: Path) -> None:
    sub = state / "sessions" / "C--work-shop" / "sess1" / "subagents"
    sub.mkdir(parents=True)
    for aid, bio, role, err in (("r1", "reviewer", "reviewer", False), ("r2", "reviewer", "reviewer", True), ("i1", "implementer", None, False)):
        (sub / f"agent-{aid}.meta.json").write_text(json.dumps({"agent_id": aid, "type": bio, "role": role, "lineup": "halo-dev-cycle",
                                                                 "model": "or:x/y", "started": 100.0, "finished": 160.0,
                                                                 "status": "completed", "is_error": err}), encoding="utf-8")
        lines = [{"type": "meta"}, {"type": "user", "content": [{"type": "text", "text": f"Review the {aid} part\nin depth"}]},
                 {"type": "usage", "usage": {}, "cost_usd": 0.01}, {"type": "usage", "usage": {}, "cost_usd": 0.02}]
        (sub / f"agent-{aid}.jsonl").write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")
    (state / "sessions" / "C--work-shop" / "sess1.jsonl").write_text(json.dumps({"type": "user", "content": "Ship the fix"}) + "\n", encoding="utf-8")


@test
def test_history_lists_past_runs_by_role_or_bio(ctx: Ctx):
    with _Studio() as s:
        _seed_history(s.state)
        status, got = s.api("GET", "fleet/history?role=reviewer")
        runs = got.get("runs") or []
        ctx.check(f"two reviewer runs, got {status} {[r['agent_id'] for r in runs]}", status == 200 and sorted(r["agent_id"] for r in runs) == ["r1", "r2"])
        r1 = next(r for r in runs if r["agent_id"] == "r1")
        ctx.check(f"the task (first line), the summed cost, the outcome, got {r1}",
                  r1["task"] == "Review the r1 part" and abs(r1["cost_usd"] - 0.03) < 1e-9 and r1["is_error"] is False and r1["session_id"] == "sess1")
        ctx.check("a failed run says so", next(r for r in runs if r["agent_id"] == "r2")["is_error"] is True)
        status, got = s.api("GET", "fleet/history?bio=implementer")
        ctx.check(f"by bio, got {got}", status == 200 and [r["agent_id"] for r in got["runs"]] == ["i1"])
        status, got = s.api("GET", "fleet/history?role=main")
        ctx.check(f"role main lists the sessions, got {got}", status == 200 and got["runs"][0]["session_id"] == "sess1" and got["runs"][0]["task"] == "Ship the fix")
        ctx.check("n is capped", s.api("GET", "fleet/history?role=reviewer&n=1")[1]["runs"].__len__() == 1)
        ctx.check("no role and no bio is a 422", s.api("GET", "fleet/history")[0] == 422)
        ctx.check("n out of range is a 422", s.api("GET", "fleet/history?role=x&n=0")[0] == 422)


@test
def test_the_rig_two_harnesses_five_agents_a_member_tail_and_the_meta_role(ctx: Ctx):
    from tests.helpers.studio_fleet_rig import MEMBER, MEMBER_SID, StudioFleetRig
    with StudioFleetRig() as rig:
        status, view = rig.api("GET", "fleet")
        hs = view.get("harnesses") or []
        agents = [a for h in hs for ss in h["sessions"] for a in ss.get("agents") or []]
        ctx.check(f"two harnesses, this one first, got {[h.get('name') for h in hs]}",
                  status == 200 and [h.get("name") for h in hs] == ["rolo@studio", "kali@lab"] and hs[0]["local"] is True)
        ctx.check(f"five agents in three states, got {[a.get('state') for a in agents]}",
                  len(agents) == 5 and {a.get("state") for a in agents} == {"running", "waiting", "done"})
        status, got = rig.api("POST", f"fleet/{MEMBER}/{MEMBER_SID}/agents/r7e1v2w3/command", {"cmd": "tail", "n": 20})
        ctx.check(f"a member's tail through the hub, got {status}",
                  status == 200 and [e["kind"] for e in got["result"]["events"]] == ["user", "tool_call", "tool_result", "handback"])
        metas = [json.loads(p.read_text(encoding="utf-8")) for p in rig.state.glob("sessions/*/*/subagents/agent-*.meta.json")]
        ctx.check(f"each sub-agent's meta carries its role and lineup, got {[sorted(m) for m in metas]}",
                  len(metas) == 2 and all("role" in m and "lineup" in m for m in metas))
        status, got = rig.api("GET", "fleet/history?bio=implementer")
        ctx.check(f"so its history lists it, got {got}", status == 200 and got["runs"][0]["task"].startswith("Implement: apply the discount"))


@test
def test_live_roles_files_are_wired_and_small(ctx: Ctx):
    page = (LEGACY / "index.html").read_text(encoding="utf-8")
    ctx.check("index.html loads live.css, live.js and live-tab.js after embed.js",
              'href="live.css"' in page and page.index('src="embed.js"') < page.index('src="live.js"') < page.index('src="live-tab.js"'))
    ctx.check("the canvas decorates after every render", "window.haloLive.decorate(this)" in (LEGACY / "canvas.js").read_text(encoding="utf-8"))
    live = (LEGACY / "live.js").read_text(encoding="utf-8")
    ctx.check("live.js runs only framed and asks the shell, never the fleet routes",
              "embedded=1" in live and "fleet-ready" in live and "api/fleet" not in live and "api.post" not in live)
    long = [f"{p.name}={n}" for p in LEGACY.iterdir() if p.suffix in (".js", ".css", ".html") and (n := len(p.read_text(encoding="utf-8").splitlines())) > 250]
    ctx.check(f"every static/legacy file is at most 250 lines, over: {long}", not long)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="fleet studio routes tests"))
