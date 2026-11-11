"""tests.test_policy_audit -- every verdict is in the audit (Halo 3.3.10.0 R2; packs/policy_audit.py, cli_policy.py
`log`, policy_views `status`, packs/manager.py, agent/agent_transcript.py, tui/dispatch.py, the Session feed):

1. `halo pack policy log [<pack>] [--since]` prints each verdict a session got (text and JSON), `--since` narrows;
2. `halo pack policy status` shows each policy's process and its verdict counts;
3. the Pack Manager row carries the armed policies and the last verdict;
4. the agent transcript entries (a tail and a live event) carry the line; the feed frame carries the field; no new
   event kind;
5. the TUI's tool card draws `policy: deny -- ...` on its line; the Session feed's tool row draws it (the source);
6. a fleet mission records the requester's armed policy ids, and each part's dispatch carries them.
Run: python -m tests.test_policy_audit
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.helpers import fleet_pack as _fleet_pack  # noqa: E402  (the fleet pack on, its modules by their old names)
_fleet_pack.on()

from tests.helpers.policy_session import Upstream, fenced_home, outside, session_in  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.turn_session import text_step, tool_step  # noqa: E402

test, TESTS = new_registry()
ROOT = Path(__file__).resolve().parent.parent
UI = ROOT / "halo_harness" / "studio" / "ui" / "src"
LINE = "policy: deny -- fence: outside the project"


def _denied_turn(h, scenario: str):
    with Upstream(scenario, [tool_step("Write", {"file_path": str(outside(h)), "content": "x"}), text_step("ok")]) as up:
        s = session_in(h, up)
        evs = list(s.turn("write it"))
    return s, evs


@test
def test_the_log_prints_every_verdict(ctx: Ctx):
    with fenced_home() as h:
        s, _ = _denied_turn(h, "pa-log")
        code, out, err = h.cli("policy", "log", "policy-fence")
        ctx.check(f"exit 0 and the verdict's line, got {code} {out!r} {err!r}", code == 0
                  and "policy-fence  deny -- fence: outside the project  (Write, " in out and "rule outside-project" in out)
        code, out, _ = h.cli("policy", "log", "--since", "1h")
        ctx.check("every pack, the last hour: it is there", code == 0 and "deny -- fence: outside the project" in out)
        later = str(time.time() + 7200)  # two hours ahead: nothing logged after it
        code, out, _ = h.cli("policy", "log", "--since", later)
        ctx.check(f"--since past it: none, got {out!r}", code == 0 and out.startswith("No verdict of a pack's policy is logged in that time"))
        code, out, _ = h.cli("policy", "log", "policy-fence", "--json")
        rows = json.loads(out)["verdicts"] if code == 0 else []
        ctx.check(f"--json: the rows, the session named, got {rows}", rows and rows[-1]["verdict"] == "deny"
                  and rows[-1]["session"] == s.log.session_id and rows[-1]["at"] == "before" and "input" not in rows[-1])
        code, _, err = h.cli("policy", "log", "--since", "yesterday-ish")
        ctx.check(f"an unreadable --since is a usage line, got {code} {err!r}", code == 2 and "--since takes" in err)


@test
def test_status_shows_the_process_and_the_counts(ctx: Ctx):
    from halo_harness.agent import policy_gate as G
    with fenced_home() as h:
        G.warm(h.repo)
        _denied_turn(h, "pa-status")
        code, out, _ = h.cli("policy", "status")
        ctx.check(f"the process runs, its verdicts counted, got {out!r}", code == 0 and "process running (pid " in out
                  and "verdicts: deny 1" in out and "(halo pack policy log policy-fence)" in out)
        code, out, _ = h.cli("policy", "status", "--json")
        p = json.loads(out)["packs"][0]["policies"][0]
        ctx.check(f"the JSON twin, got {p.get('process')} {p.get('verdicts')}", str(p.get("process")).startswith("running (pid ")
                  and p.get("verdicts") == {"deny": 1})


@test
def test_the_pack_manager_row(ctx: Ctx):
    from halo_harness.packs.manager import payload
    with fenced_home() as h:
        _denied_turn(h, "pa-manager")
        row = next(p for p in payload(cwd=h.repo)["packs"] if p["id"] == "policy-fence")
        b = row.get("policy") or {}
        ctx.check(f"armed, the mode, the last verdict, got {b}", b.get("armed") == ["fence"] and b.get("mode") == "fenced"
                  and b.get("last") == "deny -- fence: outside the project (Write)" and b.get("counts") == {"deny": 1})
        ui = (UI / "routes" / "packs" / "manager" / "Installed.tsx").read_text(encoding="utf-8")
        ctx.check("the row draws it as pm-policy", 'data-testid="pm-policy"' in ui and "b.last" in ui)
    with fenced_home(install=False) as h:
        ctx.check("a pack without policies: no block", all(p.get("policy") is None for p in payload(cwd=h.repo)["packs"]))


@test
def test_the_transcript_entries_and_the_feed_carry_the_line(ctx: Ctx):
    from halo_harness import events
    from halo_harness.agent.agent_transcript import entries_from_nodes as entries, entry_from_event
    from halo_harness.remote.feed import event_frame
    with fenced_home() as h:
        s, evs = _denied_turn(h, "pa-entries")
        tail = [e for e in entries(s.log.nodes()) if e["kind"] == "tool_result"]
        ctx.check(f"a tail entry carries it, got {tail}", tail and tail[-1].get("policy") == LINE)
        res = next(e for e in evs if e.kind == "tool_result")
        ctx.check("a live entry carries it", (entry_from_event(res) or {}).get("policy") == LINE)
        frame = event_frame(res)
        ctx.check("the feed frame carries the field", frame["data"][events.TOOL_POLICY_FIELD]["line"] == LINE)
    ctx.check("no new event kind", "policy" not in events.EVENT_KINDS and events.TOOL_POLICY_FIELD == "policy")


class _Transcript:
    def __init__(self, card):
        self.tool_cards = {card.tool_use_id: card}
        self.waits = []

    def phase_wait_target(self, turn, what):
        self.waits.append(what)


@test
def test_the_tui_line_and_the_session_feed_row(ctx: Ctx):
    from halo_harness.events import Event
    from halo_harness.tui.dispatch import apply_event
    from halo_harness.tui.widgets.cards import ToolCard
    card = ToolCard(tool_use_id="t1", header="Write(/tmp/x)")
    app = SimpleNamespace(transcript=_Transcript(card), notify=lambda *a, **k: None, status_bar=None)
    data = {"id": "t1", "ok": False, "summary": LINE + " (pack policy-fence, rule outside-project)",
            "policy": {"line": LINE, "verdicts": []}}
    asyncio.run(apply_event(app, Event("tool_result", data, turn=1)))
    ctx.check(f"the card's line carries the verdict, got {card.header!r}", card.header == f"Write(/tmp/x)  {LINE}"
              and card.status == "error")
    feed = (UI / "routes" / "shared" / "liveFeed.ts").read_text(encoding="utf-8")
    row = (UI / "routes" / "session" / "LiveTool.tsx").read_text(encoding="utf-8")
    ctx.check("the Session feed takes the frame's line", "policyLine(d.policy)" in feed and "String(e.policy" in feed)
    ctx.check("its tool row draws it", 'data-testid="session-live-policy"' in row and "{l.policy}" in row)


@test
def test_a_fleet_mission_records_the_armed_policies(ctx: Ctx):
    from halo_harness.fleet import mission_api as A
    from halo_harness.fleet import mission_store as S
    from halo_harness.fleet.mission_dispatch import Dispatch
    from tests.helpers.mission_seed import FakeLead
    plan = {"parts": [{"id": "1", "title": "Write", "brief": "Write it.", "kind": "files", "needs": [], "est_cost_usd": 0.1}],
            "merge_order": []}
    A.LEAD = FakeLead(json.dumps(plan))
    try:
        with fenced_home() as h:
            status, body = A.create(A.Ctx(h.state, None, by="me", cwd=h.repo), {"goal": "Write the notes", "repo": False})
            mid = body["mission"]["id"]
            doc = json.loads((S.folder(h.state, mid) / "mission.json").read_text(encoding="utf-8"))
            ctx.check(f"the mission file records them, got {status} {doc.get('policies')}", doc.get("policies") == ["policy-fence/fence"])
            f = Dispatch.fields(doc, {"id": "1", "kind": "files"}, plan)
            ctx.check(f"a part's dispatch carries them, got {f.get('policies')}", f.get("policies") == ["policy-fence/fence"])
        with fenced_home(armed=False) as h:
            status, body = A.create(A.Ctx(h.state, None, by="me", cwd=h.repo), {"goal": "Write the notes", "repo": False})
            ctx.check("none armed: no key at all", "policies" not in body["mission"]
                      and "policies" not in Dispatch.fields(body["mission"], {"id": "1", "kind": "files"}, plan))
    finally:
        A.LEAD = None


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
