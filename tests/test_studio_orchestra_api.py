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


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="studio orchestra api tests"))
