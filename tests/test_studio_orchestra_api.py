"""tests.test_studio_orchestra_api -- Halo 3.0.3.0 round R4: the Studio
Orchestra view's routes (`/api/orchestra/...`, studio/orchestra_api.py).

Over a real temp git repo holding a finished R2 run (basket.py, five lanes,
lane 5's import conflicting with lane 4's, a fresh judge, a report): the run
list, the run payload, events since N, the one-file view (a claimed, a
writing and a merged band), stop, release and steal (422 / 403 where they
fit); and `POST run` through the `RUNNER` seam with the R2 fakes: 201, the
`orchestra_state` frames on `/api/events`, a 409 while it is live, a dry run.
No model is ever called.

Run: python tests/test_studio_orchestra_api.py
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers import orchestra_studio_rig as R  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
GOAL = {"what": "Write the five functions of basket.py", "done_when": "the tests pass", "stop_when": "two returns",
        "workers": 5, "files": ["basket.py"]}


@test
def test_runs_run_payload_and_events(ctx: Ctx):
    repo, run_dir = R.finished_run()
    try:
        with R.Studio(repo) as s:
            st, rows = s.get("orchestra/runs")
            ctx.check(f"one run row, got {st} {rows}", st == 200 and len(rows) == 1)
            row = rows[0]
            ctx.check(f"the row's fields, got {row}", row["run_id"] == run_dir.name and row["state"] == "finished"
                      and row["workers"] == 5 and row["goal_what"].startswith("Write the five")
                      and abs(row["cost_usd"] - 0.0115) < 1e-9 and isinstance(row["created"], float))
            st, data = s.get(f"orchestra/{run_dir.name}")
            keys = {"run", "goal", "workflow", "split", "lanes", "claims", "merge", "report", "events_count", "live"}
            ctx.check(f"the payload's keys, got {sorted(data)}", st == 200 and keys <= set(data))
            ctx.check("five lanes, all merged", [l["state"] for l in data["lanes"]] == ["merged"] * 5)
            ctx.check("one conflict judged", len(data["merge"]["conflicts"]) == 1 and data["merge"]["conflicts"][0]["lane"] == 5)
            ctx.check("the report and its eight checks", data["report"]["status"] == "finished" and len(data["report"]["checks"]) == 8)
            ctx.check("not live, no live claims", data["live"] is False and data["claims"] == [] and data["run"]["state"] == "finished")
            ctx.check("a unique id prefix finds the run", s.get(f"orchestra/{run_dir.name[:15]}")[0] == 200)
            ctx.check("an unknown run is a 404", s.get("orchestra/19990101-000000-abcd")[0] == 404)
            ctx.check("no token, no answer", s.get("orchestra/runs", token="")[0] == 401)
            st, ev = s.get(f"orchestra/{run_dir.name}/events?since=0")
            n = data["events_count"]
            ctx.check(f"every event line, got {len(ev['events'])} of {n}", st == 200 and len(ev["events"]) == n and ev["next"] == n)
            st, tail = s.get(f"orchestra/{run_dir.name}/events?since={n - 3}")
            ctx.check("since N gives only the newer lines", len(tail["events"]) == 3 and tail["next"] == n
                      and tail["events"][-1]["kind"] == "report")
            ctx.check("since must be a number", s.get(f"orchestra/{run_dir.name}/events?since=x")[0] == 422)
            ctx.check("an unknown method is a 405", s.call("DELETE", f"orchestra/{run_dir.name}")[0] == 405)
    finally:
        R.cleanup(repo)


@test
def test_file_view_bands(ctx: Ctx):
    from halo_harness.orchestra.claims import ClaimLog
    repo, run_dir = R.finished_run()
    log = ClaimLog(run_dir)
    log.claim("w1/main", "basket.py#add_item")
    log.claim("w2/main", "basket.py#remove_item")
    log.mark_writing("w2/main", "basket.py#remove_item")
    try:
        with R.Studio(repo) as s:
            st, view = s.get(f"orchestra/{run_dir.name}/file?path=basket.py")
            ctx.check(f"200 with path, base and regions, got {st}", st == 200 and view["path"] == "basket.py"
                      and view["base"] and len(view["regions"]) == 5)
            ctx.check("the base is the finished branch", view["base_ref"] == f"orchestra/{run_dir.name}"
                      and not any("NotImplementedError" in line for line in view["base"]))
            by = {r["key"].split("#")[1]: r for r in view["regions"]}
            ctx.check(f"a claimed band, got {by['add_item']['state']}", by["add_item"]["state"] == "claimed"
                      and by["add_item"]["holder"] == "w1/main" and by["add_item"]["lane"] == 1)
            ctx.check(f"a writing band, got {by['remove_item']['state']}", by["remove_item"]["state"] == "writing")
            ctx.check("the other three are merged", all(by[f]["state"] == "merged" for f in ("subtotal", "apply_discount", "total")))
            total = by["total"]
            ctx.check(f"a band carries its lines and the lane's text, got {total}",
                      total["start_line"] < total["end_line"] and total["text"][0].startswith("def total(")
                      and any("InvalidOperation" in line for line in total["text"]))
            lines = [r["start_line"] for r in view["regions"]]
            ctx.check("bands in file order", lines == sorted(lines))
            ctx.check("the first goal file by default", s.get(f"orchestra/{run_dir.name}/file")[1].get("path") == "basket.py")
            ctx.check("a file outside the goal is a 422", s.get(f"orchestra/{run_dir.name}/file?path=test_basket.py")[0] == 422)
    finally:
        R.cleanup(repo)


@test
def test_the_run_payload_carries_the_hand_off_fields(ctx: Ctx):
    """3.0.9.0 R1: lane 2 takes lane 1's summary: GET orchestra/<run> has every lane's handoff,
    after, base and gave, and the workflow's after edge with its label and the layers."""
    repo, run_dir = R.finished_run(chain=True)
    try:
        with R.Studio(repo) as s:
            st, data = s.get(f"orchestra/{run_dir.name}")
            lanes = {l["lane"]: l for l in data["lanes"]}
            ctx.check(f"every lane has the four fields, got {sorted(lanes[1])}",
                      st == 200 and all({"handoff", "after", "base", "gave"} <= set(l) for l in lanes.values()))
            ctx.check(f"lane 2 starts after lane 1, from its head, got {lanes[2]['after']} {lanes[2]['base'][:12]}",
                      lanes[2]["after"] == ["job-1"] and lanes[2]["handoff"] == {"needs": [{"from": "job-1", "take": "summary"}]}
                      and lanes[2]["base"] == lanes[1]["head"] and lanes[3]["base"] == data["split"]["base"])
            ctx.check(f"lane 1 gave its summary and its unit, got {lanes[1]['gave']}",
                      [(g["kind"], g["path"]) for g in lanes[1]["gave"]] == [("summary", "lanes/1/summary.md"), ("files", "basket.py#add_item")])
            edges = [e for e in data["workflow"]["edges"] if e["kind"] == "after"]
            ctx.check(f"the after edge and the layers, got {edges} {data['workflow'].get('layers')}",
                      edges == [{"from": "worker-1", "to": "worker-2", "kind": "after", "label": "summary"}]
                      and data["workflow"]["layers"] == [[1, 3, 4, 5], [2]])
            ctx.check("still five merged lanes and the judged conflict", [l["state"] for l in data["lanes"]] == ["merged"] * 5
                      and data["merge"]["conflicts"][0]["lane"] == 5 and data["merge"]["order"] == [1, 3, 4, 5, 2])
    finally:
        R.cleanup(repo)


@test
def test_stop_release_and_steal(ctx: Ctx):
    from halo_harness.orchestra.claims import ClaimLog
    repo, run_dir = R.finished_run()
    ClaimLog(run_dir).claim("w3/main", "basket.py#subtotal")
    rid = run_dir.name
    try:
        with R.Studio(repo) as s:
            ctx.check("release needs a key", s.post(f"orchestra/{rid}/release", {})[0] == 422)
            ctx.check("a key outside the goal's files is a 422", s.post(f"orchestra/{rid}/release", {"key": "x.py#f"})[0] == 422)
            ctx.check("an unclaimed key is a 422", s.post(f"orchestra/{rid}/release", {"key": "basket.py#total"})[0] == 422)
            st, err = s.post(f"orchestra/{rid}/release", {"key": "basket.py#subtotal", "holder": "w9/main"})
            ctx.check(f"another holder's name is a 403, got {st} {err}", st == 403 and err.get("holder") == "w3/main")
            st, ok = s.post(f"orchestra/{rid}/release", {"key": "basket.py#subtotal"})
            ctx.check(f"released, got {st} {ok}", st == 200 and ok["holder"] == "w3/main" and ok["claims"] == [])
            st, err = s.post(f"orchestra/{rid}/steal", {"key": "basket.py#total", "by": "w4/main"})
            ctx.check(f"only the lead steals, got {st} {err}", st == 403 and "only the lead" in err["error"])
            st, ok = s.post(f"orchestra/{rid}/steal", {"key": "basket.py#total"})
            ctx.check(f"the lead steals, got {st} {ok}", st == 200 and ok["holder"] == "orchestra/lead"
                      and [c["key"] for c in ok["claims"]] == ["basket.py#total"])
            st, ok = s.post(f"orchestra/{rid}/stop", {"reason": "enough"})
            ctx.check(f"stop writes stop.json, got {st} {ok}", st == 200 and ok["ok"] and (run_dir / "stop.json").is_file())
            last = s.get(f"orchestra/{rid}/events?since=0")[1]["events"][-1]
            ctx.check(f"the stop is in the run log, got {last['text']}", last["text"] == "stop requested: enough")
    finally:
        R.cleanup(repo)


@test
def test_post_run_streams_state_frames_and_holds_one_run(ctx: Ctx):
    from halo_harness.studio import orchestra_api, orchestra_live
    from tests.helpers import orchestra_fixtures as F
    repo = F.make_repo("orch-studio-post-")
    gate = threading.Event()
    saved = orchestra_api.RUNNER
    orchestra_api.RUNNER = R.fake_runner(gate)
    try:
        with R.Studio(repo) as s:
            st, err = s.post("orchestra/run", dict(GOAL, what=""))
            ctx.check(f"an invalid goal is a 422 with its lines, got {st} {err}", st == 422 and "WHAT YOU WANT" in err["problems"][0])
            ctx.check("a file not in the repo is a 422", s.post("orchestra/run", dict(GOAL, files=["nope.py"]))[0] == 422)
            rd = R.Reader(f"{s.base}/api/events?t={s.srv.token}&sessions=all")
            try:
                st, ok = s.post("orchestra/run", dict(GOAL, test=f"{F.PY} -m unittest -q test_basket"))
                ctx.check(f"201 with the run id, got {st} {ok}", st == 201 and ok["run_id"])
                rid = ok.get("run_id", "")
                frame = rd.wait(lambda k, f: k == "orchestra_state" and f["session_id"] == f"orchestra:{rid}", 5)
                ctx.check("an orchestra_state frame arrives on /api/events", frame is not None)
                if frame:
                    ctx.check(f"the frame carries the run log entry, got {frame['data']}",
                              frame["data"]["run"] == rid and "elapsed_s" in frame["data"] and frame["data"]["kind"] == "state")
                st, busy = s.post("orchestra/run", GOAL)
                ctx.check(f"a second run while one is live is a 409, got {st} {busy}", st == 409 and busy.get("run_id") == rid)
                ctx.check("the payload says live", s.get(f"orchestra/{rid}")[1].get("live") is True)
                gate.set()
                ctx.check("the run ends", orchestra_live.wait(60))
                rep = rd.wait(lambda k, f: k == "orchestra_report", 5)
                ctx.check("the report frame arrives", rep is not None and rep["data"]["data"]["status"] == "finished")
                data = s.get(f"orchestra/{rid}")[1]
                ctx.check(f"finished, not live, got {data['run']['state']}", data["run"]["state"] == "finished" and data["live"] is False)
                st, ok = s.post("orchestra/run", dict(GOAL, dry_run=True))
                ctx.check(f"a dry run starts, got {st}", st == 201 and ok.get("dry_run") is True)
                orchestra_live.wait(30)
                dry = s.get(f"orchestra/{ok.get('run_id')}")[1]
                ctx.check(f"the dry run's split, nothing claimed, got {dry.get('dry_run')}",
                          len((dry.get("dry_run") or {}).get("jobs") or []) == 5 and dry["lanes"] == []
                          and dry["claims"] == [] and dry["run"]["state"] == "dry run")
            finally:
                rd.close()
    finally:
        gate.set()
        orchestra_live.wait(30)
        orchestra_api.RUNNER = saved
        R.cleanup(repo)



ACCEPT_LINEUP = """roles:
  main: default-model
acceptance: {test: python -m unittest -q test_basket, review: true}
"""


@test
def test_post_run_takes_the_lineups_acceptance(ctx: Ctx):
    """3.2.1.0 R1: POST orchestra/run with a lineup whose acceptance names a test and review: goal.json gets both
    (packs.lineup_run.goal_defaults, as `halo orchestra new`), the 201 carries the lines; a typed test wins."""
    import json as _json
    from halo_harness.studio import orchestra_api, orchestra_live
    from tests.helpers import orchestra_fixtures as F
    repo = F.make_repo("orch-studio-lineup-")
    (repo / ".halo" / "teams").mkdir(parents=True, exist_ok=True)
    (repo / ".halo" / "teams" / "accept.yaml").write_text(ACCEPT_LINEUP, encoding="utf-8")
    saved = orchestra_api.RUNNER
    orchestra_api.RUNNER = R.fake_runner()
    try:
        with R.Studio(repo) as s:
            st, ok = s.post("orchestra/run", dict(GOAL, lineup="accept", dry_run=True, force=True))
            ctx.check(f"201 with the lines it took, got {st} {ok}", st == 201 and len(ok.get("taken") or []) == 2
                      and ok["taken"][0].startswith("test: python -m unittest -q test_basket (from lineup accept")
                      and ok.get("test") == "python -m unittest -q test_basket" and ok.get("plan") == "review")
            orchestra_live.wait(30)
            goal = _json.loads((repo / ".halo" / "orchestra" / ok["run_id"] / "goal.json").read_text(encoding="utf-8"))
            ctx.check(f"goal.json has the test and plan: review, got {goal.get('test')!r} {goal.get('plan')!r}",
                      goal.get("test") == "python -m unittest -q test_basket" and goal.get("plan") == "review")
            st, typed = s.post("orchestra/run", dict(GOAL, lineup="accept", test="make check", dry_run=True, force=True))
            orchestra_live.wait(30)
            goal = _json.loads((repo / ".halo" / "orchestra" / typed["run_id"] / "goal.json").read_text(encoding="utf-8"))
            ctx.check(f"a typed test wins (review still taken), got {goal.get('test')!r} {typed.get('taken')}",
                      st == 201 and goal.get("test") == "make check" and goal.get("plan") == "review"
                      and [ln.split(" ")[0] for ln in typed.get("taken") or []] == ["plan:"])
            st, plain = s.post("orchestra/run", dict(GOAL, dry_run=True))
            orchestra_live.wait(30)
            ctx.check(f"no lineup: nothing taken, no key, got {st} {plain}", st == 201 and "taken" not in plain)
    finally:
        orchestra_live.wait(30)
        orchestra_api.RUNNER = saved
        R.cleanup(repo)


@test
def test_the_coach_route_reads_the_run_and_keeps_its_card(ctx: Ctx):
    """3.0.9.0 R3: GET orchestra/<run>/coach -> the coach's result (orchestra/coach.py), computed once and kept in
    <run>/coach.json; the R2 run's judged conflict (lane 5 with lane 4) is a structure card. 3.1.6.0 R2: POST .../probe
    shows the cost line, then runs on a thread beside the console (feed frames, 409 while it runs), its card leads."""
    repo, run_dir = R.finished_run()
    try:
        with R.Studio(repo) as s:
            st, data = s.get(f"orchestra/{run_dir.name}/coach")
            ctx.check(f"200 and the shape, got {st} {sorted(data)}", st == 200 and data["kind"] == "orchestra"
                      and data["run"] == run_dir.name and data["cached"] is False and data["model"] is False)
            ids = [x["id"] for x in data["suggestions"]]
            ctx.check(f"the judged conflict, got {ids}", "structure-5-after-4" in ids)
            ctx.check("kept in coach.json", (run_dir / "coach.json").is_file())
            st, again = s.get(f"orchestra/{run_dir.name}/coach")
            ctx.check("the second read is the kept card", st == 200 and again["cached"] is True
                      and again["suggestions"] == data["suggestions"])
            ctx.check("an unknown run is a 404", s.get("orchestra/nope/coach")[0] == 404)
            ctx.check("POST is a 405", s.post(f"orchestra/{run_dir.name}/coach", {})[0] == 405)
            from tests.helpers.coach_probe_rig import studio_probe  # 3.1.6.0 R2: POST <coach>/probe
            got = studio_probe(s, run_dir)
            ctx.check(f"probe: the cost line first, nothing run, got {got['cost']}", got["cost"][0] == 200 and got["nothing_ran"]
                      and got["cost"][1]["estimate"]["line"].startswith("probe: 2 runs, up to $0.0345"))
            ctx.check(f"confirm: 202 on a thread, a 409 while it runs, got {got['start']} {got['again'][0]} {got['live']}",
                      got["start"][0] == 202 and got["again"][0] == 409 and got["live"] is True)
            f = got["frame"] or {}
            ctx.check(f"its step lines as orchestra_state frames naming no console run, got {f}", f.get("session_id") ==
                      f"coach-probe:{run_dir.name}" and "run" not in (f.get("data") or {}) and got["done"] is not None)
            card = got["coach"]["suggestions"][0]
            ctx.check(f"the probe's card leads, one run listed, got {card['kind']} {got['coach']['probe']} {len(got['runs'])}",
                      card["kind"] == "probe" and got["coach"]["probe"]["state"] == "done" and len(got["runs"]) == 1)
    finally:
        R.cleanup(repo)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="studio orchestra api tests"))
