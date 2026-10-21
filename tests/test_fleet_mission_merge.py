"""tests.test_fleet_mission_merge -- Halo 3.0.6.0 "Fleet Missions" round R7:
repo parts, over real temp git repos (the lead, the judge and the worker
sessions are fakes; git is real).

1. This harness alone: two repo parts whose claims overlap run in sequence
   (the later waits), each on `mission/<id>/<part>` in its own worktree;
   they merge into `mission/<id>/merged` in the plan's merge_order; since
   3.0.9.0 the later part starts from the earlier part's head, so the file
   both touched does not conflict (the judge is not asked: the two-dependency
   conflict is in tests/test_fleet_mission_handoffs.py); the files part's
   output is in artifacts/.
2. `stop` stops a part running on this harness.
3. Over two homes (tests/helpers/fleet_hub_rig.py): the member's repo part
   comes back as a git bundle through mission_files and merges.

Run: python -m tests.test_fleet_mission_merge
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _repo(path=None) -> Path:
    from tests.helpers.orchestra_fixtures import git
    repo = Path(path or tempfile.mkdtemp(prefix="mission-repo-"))
    (repo / "docs" / "report").mkdir(parents=True, exist_ok=True)
    (repo / "docs" / "report" / "links.md").write_text("links\n", encoding="utf-8", newline="\n")
    (repo / ".gitignore").write_text(".halo/\n", encoding="utf-8", newline="\n")
    git(repo, "init", "-q")
    for k, v in (("user.name", "t"), ("user.email", "t@t"), ("core.autocrlf", "false"), ("commit.gpgsign", "false")):
        git(repo, "config", k, v)
    git(repo, "remote", "add", "origin", "https://example.invalid/lab.git")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base")
    return repo


def _answer(parts: list, order: list) -> str:
    return json.dumps({"parts": parts, "merge_order": order})


@test
def test_repo_parts_run_in_sequence_each_from_the_earlier_head_and_merge_in_order(ctx: Ctx):
    from halo_harness.config.paths import bridge_home
    from halo_harness.fleet import mission_api as A
    from halo_harness.fleet import mission_store as S
    from halo_harness.fleet import mission_worker as W
    from halo_harness.fleet.identity import harness
    from halo_harness.orchestra.gitops import merges_on, show
    from tests.helpers.fleet_caps_seed import seed
    from tests.helpers.mission_seed import FakeJudge, FakeLead, reset_fakes, wait_state, windows_host, worker
    from tests.helpers.orchestra_fixtures import git
    home = bridge_home()
    seed(home, windows_host(harness()))
    repo = _repo()
    base = git(repo, "rev-parse", "HEAD").strip()
    A.LEAD = FakeLead(_answer([
        {"id": "book", "title": "Workbook", "brief": "Make it.", "kind": "files", "needs": ["gridcraft"], "outputs": ["book.xlsx"]},
        {"id": "page", "title": "Report page", "brief": "Write the page.", "kind": "repo", "claims": ["docs/report/**"]},
        {"id": "link", "title": "Link it", "brief": "Add the link.", "kind": "repo", "claims": ["docs/report/links.md"]}],
        ["link", "page"]))
    A.JUDGE = judge = FakeJudge()
    started = []
    W.BUILD = worker({"1": {"writes": ["artifacts/1/book.xlsx"], "cost": 0.03},
                      "2": {"writes": ["docs/report/index.md", "docs/report/links.md"], "cost": 0.02,
                            "content": {"docs/report/links.md": "links\nfrom the page\n"}},
                      "3": {"writes": ["docs/report/links.md"], "cost": 0.01,
                            "content": {"docs/report/links.md": "links\nfrom the link part\n"}}}, started)
    mctx = A.Ctx(home, None, by="owner", cwd=str(repo))
    status, body = A.create(mctx, {"goal": "Write the report page and link it"})
    mid = body["mission"]["id"]
    parts = {p["id"]: p for p in body["plan"]["parts"]}
    ctx.check(f"the overlapping repo parts run in sequence by merge order, got {parts['2']['depends_on']}",
              status == 200 and parts["2"]["depends_on"] == ["3"] and body["mission"]["repo"]["name"] == "lab"
              and body["mission"]["repo"]["base"] == base)
    A.run(mctx, mid)
    doc = wait_state(home, mid, ("done", "failed", "stopped"), 90)
    ctx.check(f"done, got {doc['state']} {doc.get('stop_reason')}", doc["state"] == "done")
    order = [p for p, _t in started]
    ctx.check(f"part 2 started after part 3 finished, got {order}", order.index("3") < order.index("2"))
    merged = f"mission/{mid}/merged"
    merges = [m[1] for m in merges_on(repo, merged, base)]
    ctx.check(f"merged one at a time in merge_order (3 then 2), got {merges}",
              [m.split("merge part ")[1].split(" ")[0] for m in merges] == ["3", "2"])
    final = show(repo, merged, "docs/report/links.md") or ""
    head3 = git(repo, "rev-parse", f"mission/{mid}/3").strip()
    ctx.check(f"3.0.9.0: part 2 started from part 3's head, got {doc['parts']['2'].get('base')} vs {head3}",
              doc["parts"]["2"]["base"] == head3 and doc["parts"]["3"]["base"] == base
              and git(repo, "merge-base", "--is-ancestor", head3, f"mission/{mid}/2") == "")
    ctx.check(f"so the file both touched did not conflict: part 2's text, no judge, got {final!r}",
              judge.calls == [] and final == "links\nfrom the page\n")
    m = doc["merge"]
    ctx.check("merge recorded: order, merged, no conflict", m["order"] == ["3", "2"] and m["merged"] == ["3", "2"]
              and m["conflicts"] == [] and m["finished"] == git(repo, "rev-parse", merged).strip())
    ctx.check("each part ran on its own branch", all(git(repo, "rev-parse", "--verify", f"mission/{mid}/{n}").strip() for n in ("2", "3")))
    ctx.check("the files part's output is in artifacts/", (S.folder(home, mid) / "artifacts" / "1" / "book.xlsx").is_file()
              and not m["missing_outputs"])
    ctx.check("the parts' worktrees are gone, the branches stay", "missions" not in git(repo, "worktree", "list"))
    reset_fakes()


@test
def test_stop_stops_a_part_running_here(ctx: Ctx):
    from halo_harness.config.paths import bridge_home
    from halo_harness.fleet import mission_api as A
    from halo_harness.fleet import mission_store as S
    from halo_harness.fleet import mission_worker as W
    from tests.helpers.fleet_hub_rig import wait_for
    from tests.helpers.mission_seed import FakeLead, gate, reset_fakes, wait_state, worker
    home = bridge_home()
    A.LEAD = FakeLead(_answer([{"id": "a", "title": "Long", "brief": "Take long.", "kind": "files"},
                               {"id": "b", "title": "After", "brief": "Then.", "kind": "files", "depends_on": ["a"]}], []))
    W.BUILD = worker({}, [], {"1": gate()})
    mctx = A.Ctx(home, None, by="owner", cwd=None)
    mid = A.create(mctx, {"goal": "Take long", "repo": False})[1]["mission"]["id"]
    A.run(mctx, mid)
    ctx.check("part 1 runs", bool(wait_for(lambda: W.running(mid), 10)))
    status, body = A.stop(mctx, mid, "enough")
    doc = wait_state(home, mid, ("stopped",), 20)
    ctx.check(f"stopped with the reason, got {doc['state']} {doc['stop_reason']}", doc["state"] == "stopped"
              and doc["stop_reason"] == "enough" and doc["parts"]["1"]["state"] == "stopped" and doc["parts"]["2"]["state"] == "skipped")
    res = wait_for(lambda: S.read_text(S.folder(home, mid), "parts/1/result.json"), 10)
    # the worker writes its result before its thread ends (on_done, the cleanup): read on the instant the file
    # lands, `running` can still list it for a tick (the Linux runner did, once) -- wait for the thread too
    ended = wait_for(lambda: not W.running(mid), 10)
    ctx.check(f"the worker itself ended stopped, got {bool(res)} ended={bool(ended)}", bool(res) and json.loads(res)["state"] == "stopped" and bool(ended))
    ctx.check("the decision is kept", any("enough" in d["what"] for d in doc["decisions"]))
    reset_fakes()


@test
def test_a_members_repo_part_comes_back_as_a_bundle(ctx: Ctx):
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
        answer = _answer([{"id": "s", "title": "Scan notes", "brief": "Write the scan notes.", "kind": "repo",
                           "needs": ["nmap"], "claims": ["docs/scan/**"]},
                          {"id": "b", "title": "Book notes", "brief": "Write the book notes.", "kind": "repo",
                           "needs": ["gridcraft"], "claims": ["docs/book/**"]}], ["s", "b"])
        A, mctx = mission_ctx(rig, answer, {"1": {"writes": ["docs/scan/notes.md"], "cost": 0.04},
                                            "2": {"writes": ["docs/book/notes.md"], "cost": 0.02}}, [])
        mctx.cwd = str(hub_repo)
        status, body = A.create(mctx, {"goal": "Write both notes"})
        mid = body["mission"]["id"]
        ctx.check(f"the scan part goes to the member, got {[p['harness'] for p in body['plan']['parts']]}",
                  status == 200 and body["plan"]["parts"][0]["harness"] == rig.b_id)
        A.run(mctx, mid)
        doc = wait_state(rig.home_a, mid, ("done", "failed", "stopped"), 90)
        ctx.check(f"done, got {doc['state']} {doc.get('stop_reason')}", doc["state"] == "done")
        puts = [r["path"] for r in S.read_log(rig.home_a, mid, ("file_put",))]
        ctx.check(f"the member pushed its branch as a bundle, got {puts}", "parts/1/branch.bundle" in puts and doc["parts"]["1"]["bundle"])
        merged = f"mission/{mid}/merged"
        ctx.check("both parts' files are on the merged branch", show(hub_repo, merged, "docs/scan/notes.md") == "part 1\n"
                  and show(hub_repo, merged, "docs/book/notes.md") == "part 2\n" and doc["merge"]["merged"] == ["1", "2"])
        reset_fakes()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="fleet mission merge tests"))
