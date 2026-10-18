"""tests.test_fleet_mission_handoffs -- Halo 3.0.9.0 round R1: mission parts
hand off through their `outputs` and a sequenced repo part starts from the
earlier part's head (fleet/mission_handoff.py), over real temp git repos and
tests/helpers/mission_seed.py (the lead, the judge and the worker sessions
are fakes; no model is called).

1. This harness alone: part 3 depends on two repo parts: it starts from the
   merge of their heads (result.json and the part state carry the base, the
   report names it), its prompt lists its hand-offs.
2. Two dependency heads that conflict go to the (fake) judge: its answer
   applied by code; an answer that does not fit fails the start with the
   judge's reason.
3. mission_files: a dependent part reads exactly its dependency's outputs
   and hand-back; `take: all` reads its whole artifacts folder.
4. Over two homes: the member's part waits for the hub's part and starts
   from its head, which comes to it as parts/<n>/base.bundle.

Run: python -m tests.test_fleet_mission_handoffs
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.test_fleet_mission_merge import _answer, _repo  # noqa: E402

test, TESTS = new_registry()


@test
def test_a_part_with_two_repo_dependencies_starts_from_their_merge(ctx: Ctx):
    from halo_harness.config.paths import bridge_home
    from halo_harness.fleet import mission_api as A
    from halo_harness.fleet import mission_store as S
    from halo_harness.fleet import mission_worker as W
    from halo_harness.fleet.identity import harness
    from halo_harness.orchestra.gitops import show
    from tests.helpers.fleet_caps_seed import seed
    from tests.helpers.mission_seed import FakeJudge, FakeLead, reset_fakes, wait_state, windows_host, worker
    from tests.helpers.orchestra_fixtures import git
    home = bridge_home()
    seed(home, windows_host(harness()))
    repo = _repo()
    base = git(repo, "rev-parse", "HEAD").strip()
    A.LEAD = FakeLead(_answer([
        {"id": "a", "title": "Page A", "brief": "Write A.", "kind": "repo", "claims": ["docs/a/**"]},
        {"id": "b", "title": "Page B", "brief": "Write B.", "kind": "repo", "claims": ["docs/b/**"]},
        {"id": "c", "title": "Index", "brief": "Link A and B.", "kind": "repo", "claims": ["docs/index.md"],
         "depends_on": ["a", "b"]}], ["a", "b", "c"]))
    A.JUDGE = judge = FakeJudge()
    started, prompts = [], {}
    build = worker({"1": {"writes": ["docs/a/page.md"]}, "2": {"writes": ["docs/b/page.md"]},
                    "3": {"writes": ["docs/index.md"]}}, started)

    def spy(cwd, home_):
        session, run, close = build(cwd, home_)

        def run2(prompt, handle=None):
            prompts[Path(cwd).name] = prompt
            prompts[Path(cwd).name + ":files"] = sorted(p.relative_to(cwd).as_posix() for p in Path(cwd).rglob("page.md"))
            return run(prompt, handle)
        return session, run2, close
    W.BUILD = spy
    mctx = A.Ctx(home, None, by="owner", cwd=str(repo))
    mid = A.create(mctx, {"goal": "Write two pages and their index"})[1]["mission"]["id"]
    A.run(mctx, mid)
    doc = wait_state(home, mid, ("done", "failed", "stopped"), 90)
    ctx.check(f"done, got {doc['state']} {doc.get('stop_reason')}", doc["state"] == "done")
    heads = sorted(git(repo, "rev-parse", f"mission/{mid}/{n}").strip() for n in ("1", "2"))
    b3 = doc["parts"]["3"]["base"]
    parents = sorted(git(repo, "rev-list", "--parents", "-n", "1", b3).split()[1:]) if b3 else []
    ctx.check(f"part 3's base is the merge of parts 1 and 2, got {parents}", parents == heads and judge.calls == [])
    ctx.check("parts 1 and 2 start from the mission's base", doc["parts"]["1"]["base"] == doc["parts"]["2"]["base"] == base)
    ctx.check(f"both pages were in part 3's worktree when it started, got {prompts.get('3:files')}",
              prompts.get("3:files") == ["docs/a/page.md", "docs/b/page.md"])
    res = json.loads(S.read_text(S.folder(home, mid), "parts/3/result.json"))
    ctx.check("result.json carries the base", res["base"] == b3)
    ctx.check("its prompt lists the hand-offs and the start", "Hand-offs from part(s) 1, 2" in prompts.get("3", "")
              and "parts/1/handback.md" in prompts["3"] and f"starts from {b3[:12]}" in prompts["3"])
    report = json.loads(S.read_text(S.folder(home, mid), "report.json"))
    rows = {p["id"]: p for p in report["parts"]}
    ctx.check("report.json names each part's base", rows["3"]["base"] == b3 and rows["1"]["base"] == base)
    md = S.read_text(S.folder(home, mid), "report.md")
    ctx.check("report.md has the Base column", "| Base |" in md and f"`{b3[:7]}` (after 1, 2)" in md)
    ctx.check("the merged branch has all three files", all(show(repo, f"mission/{mid}/merged", f) for f in
                                                             ("docs/a/page.md", "docs/b/page.md", "docs/index.md")))
    reset_fakes()


def _two_branch_doc(home, judge_text: str = ""):
    """A mission whose parts 1 and 2 changed one file two ways (real branches), part 3 waits for both."""
    from halo_harness.fleet import mission as M
    from halo_harness.fleet import mission_store as S
    from tests.helpers.orchestra_fixtures import git
    repo = _repo()
    base = git(repo, "rev-parse", "HEAD").strip()
    mid = M.new_id()
    for n, line in (("1", "from part one"), ("2", "from part two")):
        git(repo, "checkout", "-q", "-b", f"mission/{mid}/{n}", base)
        (repo / "docs" / "report" / "links.md").write_text(f"links\n{line}\n", encoding="utf-8", newline="\n")
        git(repo, "commit", "-qam", f"part {n}")
    git(repo, "checkout", "-q", base)
    doc = M.new_doc(mid=mid, goal="Both links", hub={"id": "h", "name": "alice@hub"})
    doc["repo"] = {"name": "lab", "base": base}
    S.create(home, doc)
    S.set_local(home, mid, repo_root=str(repo))
    doc["parts"] = {n: {"state": "done", "files": ["docs/report/links.md"], "ended": float(n)} for n in ("1", "2")}
    plan = {"parts": [{"id": "1", "kind": "repo"}, {"id": "2", "kind": "repo"},
                      {"id": "3", "kind": "repo", "depends_on": ["1", "2"], "outputs": []}]}
    return repo, doc, plan


@test
def test_dependency_heads_that_conflict_go_to_the_judge(ctx: Ctx):
    from halo_harness.config.paths import bridge_home
    from halo_harness.fleet.mission_handoff import start_base
    from halo_harness.orchestra.gitops import show
    from tests.helpers.mission_seed import FakeJudge
    home = bridge_home()
    repo, doc, plan = _two_branch_doc(home)
    judge = FakeJudge()
    base, why = start_base(home, doc, plan, plan["parts"][2], judge)
    ctx.check(f"the judge resolved it, got {base} {why!r} {judge.calls}", base and not why and judge.calls == [("docs/report/links.md", 1)])
    text = show(repo, base, "docs/report/links.md") or ""
    ctx.check(f"its answer was applied by code: both lines, got {text!r}", "from part one" in text and "from part two" in text)
    ctx.check("the start is on mission/<id>/3-base", show(repo, f"mission/{doc['id']}/3-base", "docs/report/links.md") == text)
    repo, doc, plan = _two_branch_doc(home)
    base, why = start_base(home, doc, plan, plan["parts"][2], FakeJudge("<<<<<<< ours\nstill both\n>>>>>>> theirs"))
    ctx.check(f"an answer that does not fit fails the start with the reason, got {base} {why!r}",
              base is None and "part 3's dependencies conflicted and the judge's answer did not fit the hunks" == why)


@test
def test_a_dependent_part_reads_exactly_the_outputs(ctx: Ctx):
    from halo_harness.config.paths import bridge_home
    from halo_harness.fleet import mission as M
    from halo_harness.fleet import mission_plan as P
    from halo_harness.fleet import mission_store as S
    from halo_harness.fleet.mission_files import serve
    home = bridge_home()

    def seeded(take: str) -> str:
        mid = M.new_id()
        S.create(home, M.new_doc(mid=mid, goal="Scan, then book", hub={"id": "hub", "name": "alice@hub"}))
        parts = [{"id": "1", "title": "scan", "brief": "scan", "kind": "files", "harness": "hub", "claims": ["artifacts/1/**"],
                  "depends_on": [], "outputs": ["artifacts/1/scan.xml"]},
                 {"id": "2", "title": "book", "brief": "book", "kind": "files", "harness": "member", "claims": ["artifacts/2/**"],
                  "depends_on": ["1"], "outputs": [], "take": take}]
        P._commit(home, mid, {"v": 1, "mission": mid, "parts": parts, "merge_order": [], "notes": []}, "test", "seeded")
        for rel in ("artifacts/1/scan.xml", "artifacts/1/raw.pcap", "parts/1/handback.md", "parts/1/result.json",
                    "parts/2/base.bundle"):
            S.write_text(S.folder(home, mid), rel, "x\n")
        return mid
    mid = seeded("outputs")
    listed = sorted(f["path"] for f in serve(home, "member", {"op": "list", "mission": mid})[1]["files"])
    ctx.check(f"take outputs: the outputs and the hand-back only, got {listed}",
              "artifacts/1/scan.xml" in listed and "parts/1/handback.md" in listed and "artifacts/1/raw.pcap" not in listed
              and "parts/1/result.json" not in listed and "parts/2/base.bundle" in listed)
    ctx.check("get of a non-output answers 403", serve(home, "member", {"op": "get", "mission": mid, "path": "artifacts/1/raw.pcap"})[0] == 403)
    mid = seeded("all")
    listed = sorted(f["path"] for f in serve(home, "member", {"op": "list", "mission": mid})[1]["files"])
    ctx.check(f"take all: the whole artifacts folder, got {listed}", "artifacts/1/raw.pcap" in listed and "artifacts/1/scan.xml" in listed
              and "parts/1/result.json" not in listed)


@test
def test_a_members_sequenced_part_starts_from_the_hubs_head(ctx: Ctx):
    from halo_harness.fleet import mission_store as S
    from halo_harness.orchestra.gitops import show
    from tests.helpers.fleet_hub_rig import HubRig
    from tests.helpers.mission_seed import fleet, mission_ctx, reset_fakes, wait_state
    from tests.helpers.orchestra_fixtures import git
    hub_repo = _repo()
    with HubRig() as rig:
        member_repo = Path(rig.root_b)
        git(member_repo, "init", "-q")
        for k, v in (("user.name", "t"), ("user.email", "t@t"), ("core.autocrlf", "false")):
            git(member_repo, "config", k, v)
        git(member_repo, "remote", "add", "origin", "https://example.invalid/lab.git")
        git(member_repo, "fetch", "-q", str(hub_repo), "HEAD")
        git(member_repo, "checkout", "-q", "-b", "main", "FETCH_HEAD")
        fleet(rig, **{"fleet.allow_control": "all"})
        answer = _answer([{"id": "b", "title": "Book notes", "brief": "Write the book notes.", "kind": "repo",
                           "needs": ["gridcraft"], "claims": ["docs/book/**"]},
                          {"id": "s", "title": "Scan notes", "brief": "Write the scan notes after the book.", "kind": "repo",
                           "needs": ["nmap"], "claims": ["docs/scan/**"], "depends_on": ["b"]}], ["b", "s"])
        A, mctx = mission_ctx(rig, answer, {"1": {"writes": ["docs/book/notes.md"]}, "2": {"writes": ["docs/scan/notes.md"]}}, [])
        mctx.cwd = str(hub_repo)
        mid = A.create(mctx, {"goal": "Write both notes, the scan after the book"})[1]["mission"]["id"]
        A.run(mctx, mid)
        doc = wait_state(rig.home_a, mid, ("done", "failed", "stopped"), 90)
        ctx.check(f"done, got {doc['state']} {doc.get('stop_reason')}", doc["state"] == "done")
        head1 = git(hub_repo, "rev-parse", f"mission/{mid}/1").strip()
        ctx.check(f"the member's part started from the hub part's head, got {doc['parts']['2'].get('base')}",
                  doc["parts"]["2"]["base"] == head1 and doc["parts"]["2"]["harness"] == rig.b_id)
        ctx.check("its start went over as parts/2/base.bundle", (S.folder(rig.home_a, mid) / "parts" / "2" / "base.bundle").is_file())
        ctx.check("so the member's branch carries the book notes", show(hub_repo, f"mission/{mid}/2", "docs/book/notes.md") == "part 1\n")
        merged = f"mission/{mid}/merged"
        ctx.check("both files on the merged branch", show(hub_repo, merged, "docs/scan/notes.md") == "part 2\n"
                  and show(hub_repo, merged, "docs/book/notes.md") == "part 1\n" and doc["merge"]["merged"] == ["1", "2"])
        reset_fakes()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="fleet mission hand-off tests"))
