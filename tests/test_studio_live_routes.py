"""tests.test_studio_live_routes -- Halo 3.0.5.0 round R3, the routes behind Agents -> Live and Session, over real
HTTP to an in-process Studio: GET live/history (past runs by role or bio from the transcripts' meta, with the task and
the summed cost); then, over the rig (tests/helpers/studio_session_rig.py), GET live with this harness and its three
agents, and a sub-agent's meta file with its role and lineup; Live Roles' files are wired and small.

Run: python -m tests.test_studio_live_routes
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


class _Studio:
    def __enter__(self):
        from halo_harness.studio.server import start_server
        self.state = Path(tempfile.mkdtemp(prefix="live-routes-")) / ".halo"
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
                         headers={"Authorization": "Bearer " + self.srv.token, "Content-Type": "application/json",
                                  "X-Halo-Owner": __import__("halo_harness.studio.owner_proof", fromlist=["x"]).header_for(self.srv)})
            resp = conn.getresponse()
            return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
        finally:
            conn.close()


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
        status, got = s.api("GET", "live/history?role=reviewer")
        runs = got.get("runs") or []
        ctx.check(f"two reviewer runs, got {status} {[r['agent_id'] for r in runs]}", status == 200 and sorted(r["agent_id"] for r in runs) == ["r1", "r2"])
        r1 = next(r for r in runs if r["agent_id"] == "r1")
        ctx.check(f"the task (first line), the summed cost, the outcome, got {r1}",
                  r1["task"] == "Review the r1 part" and abs(r1["cost_usd"] - 0.03) < 1e-9 and r1["is_error"] is False and r1["session_id"] == "sess1")
        ctx.check("a failed run says so", next(r for r in runs if r["agent_id"] == "r2")["is_error"] is True)
        status, got = s.api("GET", "live/history?bio=implementer")
        ctx.check(f"by bio, got {got}", status == 200 and [r["agent_id"] for r in got["runs"]] == ["i1"])
        status, got = s.api("GET", "live/history?role=main")
        ctx.check(f"role main lists the sessions, got {got}", status == 200 and got["runs"][0]["session_id"] == "sess1" and got["runs"][0]["task"] == "Ship the fix")
        ctx.check("n is capped", s.api("GET", "live/history?role=reviewer&n=1")[1]["runs"].__len__() == 1)
        ctx.check("no role and no bio is a 422", s.api("GET", "live/history")[0] == 422)
        ctx.check("n out of range is a 422", s.api("GET", "live/history?role=x&n=0")[0] == 422)


@test
def test_the_rig_this_harness_three_agents_and_the_meta_role(ctx: Ctx):
    from tests.helpers.studio_session_rig import PAST_SID, StudioSessionRig
    with StudioSessionRig() as rig:
        status, view = rig.api("GET", "live")
        hs = view.get("harnesses") or []
        agents = [a for h in hs for ss in h["sessions"] for a in ss.get("agents") or []]
        ctx.check(f"this harness alone, got {[h.get('name') for h in hs]}",
                  status == 200 and [h.get("name") for h in hs] == ["you@studio"] and hs[0]["local"] is True)
        ctx.check(f"three agents at work, got {[a.get('state') for a in agents]}",
                  len(agents) == 3 and {a.get("state") for a in agents} <= {"running", "waiting"})
        ctx.check("another harness is a 404", rig.api("POST", "live/someone/s1/agents/a1/command", {"cmd": "tail", "n": 20})[0] == 404)
        metas = [json.loads(p.read_text(encoding="utf-8")) for p in rig.state.glob("sessions/*/*/subagents/agent-*.meta.json") if PAST_SID not in str(p)]  # R4 seeds a past one
        ctx.check(f"each sub-agent's meta carries its role and lineup, got {[sorted(m) for m in metas]}",
                  len(metas) == 2 and all("role" in m and "lineup" in m for m in metas))
        status, got = rig.api("GET", "live/history?bio=implementer")
        ctx.check(f"so its history lists it, got {got}", status == 200 and got["runs"][0]["task"].startswith("Implement: apply the discount"))


@test
def test_live_roles_is_wired_into_the_react_canvas(ctx: Ctx):
    """3.0.7.0 R2: Live Roles drives the React Roles canvas through the store: no framed page,
    no postMessage, and the canvas never calls the live routes itself."""
    ui = REPO / "halo_harness" / "studio" / "ui" / "src"
    frames = (ui / "routes" / "fleet" / "frames.ts").read_text(encoding="utf-8")
    ctx.check("frames.ts writes the live rows into the Roles store", "roles.update(() => ({ live: rows }))" in frames and "postMessage" not in frames)
    live = (ui / "routes" / "roles" / "live.ts").read_text(encoding="utf-8")
    ctx.check("the canvas matches agents to cards and hops across them", "export function matchNode" in live and "export function hopCard" in live and "api/live" not in live)
    ctx.check("no static/legacy left", not (REPO / "halo_harness" / "studio" / "static" / "legacy").exists())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="studio live routes tests"))
