"""tests.test_fleet_mission -- Halo 3.0.6.0 "Fleet Missions" round R7: the
plan. The lead is a fake (a fixed answer); everything else is code: a part
whose needs only one harness meets is pinned there with the reason (gridcraft
on the Windows host, nmap on the Kali box), a capability nobody has makes a
part `unassignable`, overlapping claims become a `depends_on` with the why,
a bad answer is retried once with the problems, an owner's edit (reassign,
drop) is checked again in code, and approval waits for every part to have a
harness. The routes and CLI: tests/test_fleet_mission_api.py.

Run: python -m tests.test_fleet_mission
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials

ensure_default_provider_credentials()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
A_ID, B_ID = "a" * 16, "b" * 16


class _Home:
    def __enter__(self):
        self.saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "BRIDGE_TEST_NO_BACKGROUND_NET")}
        os.environ.pop("BRIDGE_STATE_DIR", None)
        self.root = Path(tempfile.mkdtemp(prefix="mission-"))
        os.environ.update(BRIDGE_TEST_HOME=str(self.root), BRIDGE_TEST_NO_BACKGROUND_NET="1")
        from halo_harness.config.paths import bridge_home
        from halo_harness.fleet import identity
        identity.forget_cache()
        self.home = bridge_home()
        self.home.mkdir(parents=True, exist_ok=True)
        return self

    def __exit__(self, *exc):
        for k, v in self.saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        return False


def _entries() -> list:
    from tests.helpers.mission_seed import kali_box, windows_host
    a = {"id": A_ID, "name": "win@host", "os": "windows"}
    b = {"id": B_ID, "name": "kali@box", "os": "linux"}
    return [{"harness": A_ID, "name": "win@host", "local": True, "online": True, "catalog": windows_host(a)},
            {"harness": B_ID, "name": "kali@box", "local": False, "online": True, "catalog": kali_box(b)}]


def _draft(home, repo: bool = True) -> str:
    from halo_harness.fleet import mission as M
    from halo_harness.fleet import mission_store as S
    mid = M.new_id()
    S.create(home, M.new_doc(mid=mid, goal="Scan the lab and report the findings", hub={"id": A_ID, "name": "win@host"},
                             repo={"name": "lab", "base": "0" * 40} if repo else None))
    return mid


@test
def test_the_plan_pins_parts_by_capability_with_reasons(ctx: Ctx):
    from halo_harness.fleet import mission_plan as P
    from halo_harness.fleet import mission_store as S
    from tests.helpers.mission_seed import FakeLead, lead_answer
    with _Home() as h:
        mid = _draft(h.home)
        lead = FakeLead(lead_answer(repo=True))
        plan = P.plan(h.home, mid, _entries(), call_model=lead, load={A_ID: 3, B_ID: 0})
        parts = {p["title"]: p for p in plan["parts"]}
        scan, book = parts["Scan the lab network"], parts["Build the findings workbook"]
        ctx.check(f"the nmap part is pinned to the Kali box, got {scan['harness']} {scan['reason']!r}",
                  scan["harness"] == B_ID and scan["pinned"] and "nmap" in scan["reason"] and "kali@box" in scan["reason"])
        ctx.check(f"the gridcraft part is pinned to the Windows host, got {book['harness']} {book['reason']!r}",
                  book["harness"] == A_ID and book["pinned"] and "gridcraft" in book["reason"])
        ex = parts["Try the exploit"]
        ctx.check(f"a capability nobody has is unassignable with the reason, got {ex['unassignable']!r}",
                  ex["harness"] is None and "metasploit" in str(ex["unassignable"]))
        page, links = parts["Write the report page"], parts["Link the report from the docs"]
        ctx.check(f"overlapping claims run in sequence: the later waits, got {page['depends_on']} {links['depends_on']}",
                  page["depends_on"] == [links["id"]] and not links["depends_on"]
                  and any("both claim" in n for n in plan["notes"]))
        ctx.check("the lead's depends_on is mapped to the new ids", book["depends_on"] == [scan["id"]])
        ctx.check(f"merge order: the lead's, repo parts only, got {plan['merge_order']}",
                  plan["merge_order"] == [links["id"], page["id"]])
        ctx.check("a files part works in artifacts/<n>/", scan["claims"] == [f"artifacts/{scan['id']}/**"]
                  and scan["outputs"] == [f"artifacts/{scan['id']}/scan.xml"])
        ctx.check("an untied repo part goes to the least busy harness", page["harness"] == B_ID and "least busy" in page["reason"])
        prompt = lead.prompts[0]
        ctx.check("the lead saw one block per harness and what only one has", "### win@host (the hub's own harness)" in prompt
                  and "### kali@box" in prompt and "only kali@box has: cli:nmap" in prompt and "mcp gridcraft: write_range" in prompt)
        d = S.folder(h.home, mid)
        md = (d / "MISSION.md").read_text(encoding="utf-8")
        ctx.check("MISSION.md has the plan table with reasons", "| Part | Title | Harness | Why |" in md
                  and "kali@box (pinned)" in md and "only win@host has gridcraft" in md)
        brief = (d / "parts" / scan["id"] / "brief.md").read_text(encoding="utf-8")
        ctx.check("each part has its brief with its claims", "Run nmap" in brief and f"artifacts/{scan['id']}/**" in brief)
        saved = json.loads((d / "plan.json").read_text(encoding="utf-8"))
        ctx.check("plan.json keeps the parts, merge order and notes", [p["id"] for p in saved["parts"]] == ["1", "2", "3", "4", "5"]
                  and saved["merge_order"] == plan["merge_order"] and saved["lead_cost_usd"] == 0.001)
        claims = json.loads((d / "claims.json").read_text(encoding="utf-8"))
        ctx.check("claims.json per part", claims[page["id"]] == ["docs/report/**"])
        ctx.check("the mission is planned", S.need(h.home, mid)["state"] == "planned")


@test
def test_rules_overlap_has_and_prefer(ctx: Ctx):
    from halo_harness.fleet.mission_plan_rules import assign, covers, has, overlap
    for a, b, want in (("src/a.py", "src/a.py", True), ("src", "src/a.py", True), ("src/**", "src/x/y.py", True),
                       ("src/*.py", "src/a.py", True), ("src/*.py", "src/x/a.py", False), ("docs/**", "src/**", False),
                       ("**/test_*.py", "tests/test_a.py", True), ("a/*.md", "a/*.txt", False), ("lib/a*", "lib/ab*", True)):
        ctx.check(f"overlap({a!r}, {b!r}) is {want}", overlap(a, b) is want)
    ctx.check("covers: a path inside a claim", covers(["artifacts/2/**"], "artifacts/2/x.xlsx")
              and not covers(["artifacts/2/**"], "artifacts/3/x.xlsx") and not covers(["src/a.py"], "src/b.py"))
    win, kali = _entries()[0]["catalog"], _entries()[1]["catalog"]
    for need, cat, want in (("gridcraft", win, True), ("gridcraft/write_range", win, True), ("write_range", win, True),
                            ("nmap", kali, True), ("cli:nmap", win, False), ("gpu", win, True), ("gpu", kali, False),
                            ("4090", win, True), ("kali", kali, True), ("repo:ledger", kali, True), ("pentest", kali, True),
                            ("comfyui", win, True), ("xlsx", win, True), ("metasploit", win, False)):
        ctx.check(f"has({need!r}) on {(cat.get('hardware') or {}).get('distro')} is {want}", bool(has(cat, need)) is want)
    entries = _entries()
    both = [dict(e, catalog={**e["catalog"], "tags": ["shared"]}) for e in entries]
    part = assign({"id": "1", "needs": ["shared"], "harness": "", "reason": ""}, both, ["kali@box"], {A_ID: 0, B_ID: 9})
    ctx.check(f"fleet.mission.prefer breaks a tie before load, got {part['harness']} {part['reason']!r}",
              part["harness"] == B_ID and "fleet.mission.prefer" in part["reason"])
    part = assign({"id": "1", "needs": ["shared"], "harness": "win@host", "reason": "it has the files"}, both, ["kali@box"], {})
    ctx.check("the lead's pick stands when it meets the needs", part["harness"] == A_ID and part["reason"] == "it has the files")
    part = assign({"id": "1", "needs": ["nmap", "gridcraft"], "harness": "", "reason": ""}, entries, [], {})
    ctx.check("needs no one harness meets: unassignable, split it", part["harness"] is None and "split" in part["unassignable"])


@test
def test_a_bad_answer_is_retried_then_edits_are_checked_in_code(ctx: Ctx):
    from halo_harness.fleet import mission as M
    from halo_harness.fleet import mission_plan as P
    from halo_harness.fleet import mission_store as S
    from halo_harness.fleet.mission_plan_check import ready
    from tests.helpers.mission_seed import FakeLead, lead_answer
    with _Home() as h:
        mid = _draft(h.home)
        bad = json.dumps({"parts": [{"id": "x", "title": "", "brief": "b", "depends_on": ["nope"], "claims": ["/etc/passwd"]}]})
        lead = FakeLead(bad, lead_answer(repo=True))
        plan = P.plan(h.home, mid, _entries(), call_model=lead)
        ctx.check(f"a bad first answer is retried once with the problems, got {plan['attempts']}", plan["attempts"] == 2
                  and "has no title" in lead.prompts[1] and "not repo-relative" in lead.prompts[1])
        ctx.check("the approval waits for the unassignable part", any("unassignable" in p for p in ready(plan)))
        try:
            P.edit(h.home, mid, "2", _entries(), harness="kali@box")
            ctx.check("giving the gridcraft part to the Kali box is refused", False)
        except M.MissionError as e:
            ctx.check(f"giving the gridcraft part to the Kali box is refused: {e}", e.status == 422 and "gridcraft" in str(e))
        plan = P.edit(h.home, mid, "5", _entries(), drop=True, by="owner")
        ctx.check("dropping the unassignable part leaves a plan ready to approve", not ready(plan) and len(plan["parts"]) == 4)
        plan = P.edit(h.home, mid, "3", _entries(), harness="win@host", by="owner")
        page = next(p for p in plan["parts"] if p["id"] == "3")
        ctx.check(f"a reassigned part keeps the owner's choice, sequencing recomputed, got {page}",
                  page["harness"] == A_ID and "owner" in page["reason"] and page["depends_on"] == ["4"])
        doc = S.need(h.home, mid)
        ctx.check("the decisions are kept for the report", [d["what"] for d in doc["decisions"]][:2]
                  == ["dropped part 5 (Try the exploit)", "part 3 to win@host"] and doc["decisions"][0]["by"] == "owner")
        mid2 = _draft(h.home, repo=False)
        try:
            P.plan(h.home, mid2, _entries(), call_model=FakeLead("no json here"))
            ctx.check("two bad answers fail the plan", False)
        except M.MissionError as e:
            ctx.check(f"two bad answers: 422 and the mission stays drafted: {e}", e.status == 422
                      and S.need(h.home, mid2)["state"] == "drafted" and S.need(h.home, mid2)["plan_problems"])


@test
def test_a_mission_card_is_a_mission_ask_row_and_edits_read_from_text(ctx: Ctx):
    from halo_harness.fleet import attention
    from halo_harness.fleet.mission_attention import edit_from_text
    from halo_harness.studio.fleet_answer import ANSWER, NEEDS_TEXT, SET_ASIDE
    view = {"harnesses": [{"id": B_ID, "name": "kali@box", "local": True, "sessions": [
        {"session_id": "s1", "title": "work", "agents": [], "pending": {"question": ["fleet-ask:mission-0123abcd", "fleet-ask:99"]}}]}]}
    rows = attention.build(view, now=1000.0)
    kinds = sorted(r["kind"] for r in rows)
    ctx.check(f"a run_task card is a mission_ask row, a steer card stays fleet_ask, got {kinds}", kinds == ["fleet_ask", "mission_ask"])
    ask = next(r for r in rows if r["kind"] == "mission_ask")
    ctx.check("mission_ask: allow / deny / open", set(ask["keys"]) == {"a", "r", "o"} and ("mission_ask", "a") in ANSWER
              and ANSWER[("mission_ask", "r")] == {"answer": "deny"})
    ctx.check("mission_plan's edit needs text; mission_claim is set aside", ("mission_plan", "r") in NEEDS_TEXT
              and "mission_claim" in SET_ASIDE)
    ctx.check("edits from the row's text", edit_from_text("part 2 to kali@box") == {"part": "2", "harness": "kali@box"}
              and edit_from_text("drop 3") == {"part": "3", "drop": True} and edit_from_text("3 -> win") == {"part": "3", "harness": "win"}
              and edit_from_text("make it nicer") == {})


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="fleet mission tests"))
