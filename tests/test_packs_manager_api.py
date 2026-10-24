"""tests.test_packs_manager_api -- the Pack Manager's routes (Halo 3.2.0.0 R6,
studio/packs_manager_api.py, packs/manager.py, packs/sources.py) over a real
server and a scratch home; no model call:

1. `GET pack/manager`: an empty home lists no pack and, last, the packs Halo
   ships (doc-review, with the details `halo pack inspect` reads); the token
   guard holds;
2. `POST pack/install` by id from the shipped folder, publishing
   `pack_changed`; a second install answers the CLI's own line;
3. enable (a grant it does not request: the CLI's line), grant on and off,
   disable, grant on a disabled pack, update, remove (keep_config) -- each the
   function `halo pack` runs, each answering its lines, each publishing
   `pack_changed`; a pack that is not here is a 404 with the CLI's line;
4. `POST pack/sources` add / remove: packs.sources in config.json, the
   folder's packs in the manager, a refusal in the CLI's words;
5. compatibility in the doctor's words: a missing dependency on the row, an
   API range this Halo is outside on a source pack's details (install refuses
   it with that line);
6. `pack/<id>/settings` reads and writes a disabled pack's settings (R3's
   config route stays 404 for it);
7. methods: a GET on a verb, a POST on the manager are 405;
8. `POST orchestra/run {workflow, inputs}`: a missing input is a 422 with the
   compile's lines; with its input the workflow runs from Studio through the
   mock lead and workers to its typed artifact.

Run: python -m tests.test_packs_manager_api
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_studio import PackStudio, next_kind  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.workflow_rig import WorkflowRig  # noqa: E402

test, TESTS = new_registry()


def _cli_lines(err: str) -> "list[str]":
    return [ln[len("halo pack: "):] for ln in err.splitlines() if ln.startswith("halo pack: ")]


@test
def test_the_manager_route_lists_the_shipped_pack(ctx: Ctx):
    from halo_harness.packs.sources import shipped_dir
    with PackStudio() as s:
        status, body, _ = s.call("GET", "pack/manager")
        ctx.check(f"200 and no pack yet, got {status} {body.get('packs')}", status == 200 and body["packs"] == [])
        last = body["sources"][-1]
        ctx.check(f"the shipped folder is the last source, got {last['source']} {last['kind']}",
                  last["kind"] == "shipped" and Path(last["source"]) == shipped_dir() and not last["configured"])
        p = last["packs"][0]
        ctx.check(f"doc-review, not installed, got {p['id']} {p['installed']}", p["id"] == "doc-review" and not p["installed"])
        d = p["details"]
        ctx.check(f"its details read like halo pack inspect, got {d['name']} {d['halo_api']} {d['requested']}",
                  d["name"] == "Documentation Review" and d["halo_api"] == "1.0 to 1.9" and d["requested"] == ["mcp:lint", "hooks", "bash"]
                  and d["contributes_lines"][0] == "contributes:" and [w["ref"] for w in d["workflows"]] == ["doc-review/review"])
        ctx.check("this Halo's API", body["halo_api"] == "1.0" and d["this_api"] == "1.0")
        status, _raw, _h = s.raw("/api/pack/manager", token="wrong")
        ctx.check(f"a wrong token is 401, got {status}", status == 401)


@test
def test_install_by_id_and_the_clis_line_on_a_second_one(ctx: Ctx):
    with PackStudio() as s:
        q = s.frames()
        status, body, _ = s.call("POST", "pack/install", {"id": "doc-review"})
        ctx.check(f"201, install's lines, got {status} {body.get('lines', [''])[0]!r}", status == 201 and body["ok"]
                  and body["lines"][0].startswith("installed doc-review 1.0.0 at ") and body["id"] == "doc-review")
        ctx.check("pack_changed went out", next_kind(q, "pack_changed") is not None)
        from halo_harness.packs.state import entry
        ctx.check("the record names the shipped folder as its source", Path(entry("doc-review")["source"]).parts[-3:] == ("templates", "packs", "doc-review"))
        row = s.call("GET", "pack/manager")[1]["packs"][0]
        ctx.check(f"the row: disabled, nothing granted, got {row['state']} {row['granted']}", row["state"] == "disabled" and row["granted"] == [])
        status, body, _ = s.call("POST", "pack/install", {"id": "doc-review"})
        code, _out, err = s.cli("install", "doc-review")
        ctx.check(f"the second: 422 with the CLI's own line, got {status} {body.get('problems')} vs {err!r}",
                  status == 422 and code == 1 and body["problems"] == _cli_lines(err))


@test
def test_each_verb_runs_the_clis_function_and_answers_its_lines(ctx: Ctx):
    with PackStudio() as s:
        s.call("POST", "pack/install", {"id": "doc-review"})
        q = s.frames()
        status, body, _ = s.call("POST", "pack/doc-review/enable", {"grants": ["nope"]})
        _c, _o, err = s.cli("enable", "doc-review", "--grant", "nope")
        ctx.check(f"a grant it does not request: the CLI's line, got {body.get('problems')}", status == 422 and body["problems"] == _cli_lines(err)
                  and body["error"] == "doc-review does not request nope; it requests: mcp:lint, hooks, bash")
        status, body, _ = s.call("POST", "pack/doc-review/enable", {"grants": ["bash"]})
        ctx.check(f"enabled with bash, got {status} {body.get('lines')}", status == 200 and body["lines"][0] == "enabled doc-review 1.0.0"
                  and "  bash: granted" in body["lines"])
        ctx.check("pack_changed on enable", next_kind(q, "pack_changed") is not None)
        status, body, _ = s.call("POST", "pack/doc-review/grant", {"need": "hooks", "on": True})
        ctx.check(f"grant on: hooks granted, got {body.get('lines')}", status == 200 and "  hooks (hooks/hooks.json): granted" in body["lines"])
        status, body, _ = s.call("POST", "pack/doc-review/grant", {"need": "hooks", "on": False})
        ctx.check(f"grant off: taken back, got {body.get('lines')}", status == 200 and body["lines"][0] == "took back hooks from doc-review")
        from halo_harness.packs import state as S
        ctx.check("state.json holds bash only", S.granted("doc-review", S.load()) == ["bash"])
        status, body, _ = s.call("POST", "pack/doc-review/disable", {})
        ctx.check(f"disable's lines, got {body.get('lines')}", status == 200 and body["lines"][0].startswith("disabled doc-review"))
        status, body, _ = s.call("POST", "pack/doc-review/grant", {"need": "bash", "on": True})
        _c, _o, err = s.cli("grant", "doc-review", "bash")
        ctx.check(f"a grant on a disabled pack: the CLI's line, got {body.get('problems')}", status == 422 and body["problems"] == _cli_lines(err)
                  and "halo pack enable doc-review --grant bash" in body["error"])
        status, body, _ = s.call("POST", "pack/doc-review/update", {})
        ctx.check(f"update's lines (3.2.0.0 R7: the same source, nothing new), got {body.get('lines')}", status == 200
                  and body["lines"][0].startswith("doc-review 1.0.0 is up to date"))
        status, body, _ = s.call("POST", "pack/doc-review/remove", {"keep_config": True})
        ctx.check(f"remove --keep-config's lines, got {body.get('lines')}", status == 200 and body["lines"][0].startswith("removed doc-review: ")
                  and body["lines"][-1].startswith("kept its record"))
        status, body, _ = s.call("POST", "pack/zzz/enable", {})
        _c, _o, err = s.cli("enable", "zzz")
        ctx.check(f"a pack that is not here: 404 with the CLI's line, got {status} {body.get('problems')}", status == 404
                  and body["problems"] == _cli_lines(err))
        status, body, _ = s.call("POST", "pack/zzz/remove", {})
        _c, _o, err = s.cli("remove", "zzz")
        ctx.check(f"remove of one not here: the CLI's line, got {body.get('problems')}", status == 404 and body["problems"] == _cli_lines(err))


@test
def test_sources_add_and_remove(ctx: Ctx):
    from halo_harness.theme import get_config_value
    with PackStudio() as s:
        folder = s.source("studio-bundle").parent
        q = s.frames()
        status, body, _ = s.call("POST", "pack/sources", {"add": str(folder)})
        ctx.check(f"added, got {status} {body.get('lines')}", status == 200 and body["lines"] == [f"added {folder} to packs.sources (it holds studio-bundle)"]
                  and get_config_value("packs.sources") == [str(folder)])
        ctx.check("pack_changed on a source added", next_kind(q, "pack_changed") is not None)
        srcs = s.call("GET", "pack/manager")[1]["sources"]
        ctx.check(f"the folder first, then the shipped one, got {[x['kind'] for x in srcs]}", [x["kind"] for x in srcs] == ["folder", "shipped"]
                  and [p["id"] for p in srcs[0]["packs"]] == ["studio-bundle"])
        code, out, _err = s.cli("sources")
        lines = out.splitlines()
        ctx.check(f"halo pack sources lists them in that order, got {lines}", code == 0 and lines[0].startswith("packs.sources, searched in this order")
                  and lines[1].endswith("(folder): studio-bundle 0.1.0") and lines[2].endswith("(shipped): doc-review 1.0.0"))
        status, body, _ = s.call("POST", "pack/install", {"id": "studio-bundle"})
        ctx.check(f"installed by id from the source, got {status}", status == 201 and body["source"] == str(folder / "studio-bundle"))
        gone = str(s.home / "gone")
        status, body, _ = s.call("POST", "pack/sources", {"add": gone})
        _c, _o, err = s.cli("sources", "add", gone)
        ctx.check(f"a folder that is not there: the CLI's line, got {body.get('problems')}", status == 422 and body["problems"] == _cli_lines(err))
        status, body, _ = s.call("POST", "pack/sources", {"remove": str(folder)})
        ctx.check(f"removed, got {body.get('lines')}", status == 200 and get_config_value("packs.sources") == [])
        status, body, _ = s.call("POST", "pack/sources", {"remove": str(folder)})
        _c, _o, err = s.cli("sources", "remove", str(folder))
        ctx.check(f"not in the list: the CLI's line, got {body.get('problems')}", status == 422 and body["problems"] == _cli_lines(err))


@test
def test_compatibility_lines_in_the_doctors_words(ctx: Ctx):
    with PackStudio() as s:
        folder = s.home / "more-packs"
        for pid, extra in (("needs-base", 'requires: [{pack: base-docs, version: "1.2"}]'), ("future-api", "")):
            (folder / pid).mkdir(parents=True)
            api = '{min: "9.0"}' if pid == "future-api" else '{min: "1.0"}'
            (folder / pid / "pack.yaml").write_text(f"id: {pid}\nname: {pid}\nversion: 0.1.0\nhalo_api: {api}\n{extra}\n", encoding="utf-8")
        s.call("POST", "pack/sources", {"add": str(folder)})
        status, body, _ = s.call("POST", "pack/install", {"id": "needs-base"})
        ctx.check(f"installed, got {status}", status == 201)
        data = s.call("GET", "pack/manager")[1]
        row = next(p for p in data["packs"] if p["id"] == "needs-base")
        ctx.check(f"a missing dependency, as resolve says it, got {row['compat']} {row['requires']}",
                  row["compat"] == ["needs-base requires base-docs, which is not installed"]
                  and row["requires"] == [{"pack": "base-docs", "version": ">= 1.2", "met": False, "have": "", "running": False}])
        src = next(p for x in data["sources"] for p in x["packs"] if p["id"] == "future-api")
        ctx.check(f"an API range this Halo is outside, before you install it, got {src['details']['compat']}",
                  src["details"]["compat"] == ["pack future-api needs extension API 9.0 or a later 9.x; this Halo has 1.0"])
        status, body, _ = s.call("POST", "pack/install", {"id": "future-api"})
        ctx.check(f"and install refuses it with the same line, got {status} {body.get('problems')}", status == 422
                  and body["problems"] == src["details"]["compat"])


@test
def test_settings_of_a_disabled_pack(ctx: Ctx):
    from halo_harness.theme import get_config_value
    with PackStudio() as s:
        s.install_pack(enable=False)
        status, body, _ = s.call("GET", "pack/doc-review/settings")
        ctx.check(f"its fields while disabled, got {status} {[f['key'] for f in body.get('fields', [])]}", status == 200
                  and [f["key"] for f in body["fields"]] == ["style", "max_findings"])
        status, body, _ = s.call("POST", "pack/doc-review/settings", {"values": {"style": "long"}})
        ctx.check("a good value is written", status == 200 and get_config_value("packs.settings.doc-review.style") == "long")
        status, body, _ = s.call("POST", "pack/doc-review/settings", {"values": {"style": "huge"}})
        ctx.check(f"a bad one is 422, nothing written, got {status} {body.get('error')}", status == 422
                  and get_config_value("packs.settings.doc-review.style") == "long")
        ctx.check("R3's config route stays for running packs only", s.call("GET", "pack/doc-review/config")[0] == 404)
        ctx.check("a pack that is not here", s.call("GET", "pack/zzz/settings")[0] == 404)


@test
def test_methods(ctx: Ctx):
    with PackStudio() as s:
        ctx.check("GET on a verb: 405", s.call("GET", "pack/doc-review/enable")[0] == 405)
        ctx.check("POST on the manager: 405", s.call("POST", "pack/manager", {})[0] == 405)
        ctx.check("GET on install: 405", s.call("GET", "pack/install")[0] == 405)
        status, body, _ = s.call("POST", "pack/install", {})
        ctx.check(f"install with nothing to install: 422, got {status}", status == 422 and "source" in body["error"])


class StudioRig(PackStudio, WorkflowRig):
    """The workflow rig (doc-review enabled with bash, a repo with docs/*.md) served by a real Studio."""


@test
def test_run_a_workflow_from_studio(ctx: Ctx):
    from halo_harness.orchestra.report import load_report
    from halo_harness.studio import orchestra_api, orchestra_live
    from tests.helpers.workflow_rig import FakeLead, StageWorker, fake_judge
    saved = orchestra_api.RUNNER
    orchestra_api.RUNNER = lambda run_dir, goal, model: {"model_calls": FakeLead(), "spawn": StageWorker(), "judge": fake_judge,
                                                         "plan_poll_s": 0.05}
    try:
        with StudioRig() as s:
            status, body, _ = s.call("POST", "orchestra/run", {"workflow": "doc-review/review", "inputs": {}})
            ctx.check(f"a missing input: 422 with the compile's lines, got {status} {body.get('problems')}", status == 422
                      and any("docs" in p for p in body["problems"]) and body["error"].startswith("doc-review/review does not compile"))
            status, body, _ = s.call("POST", "orchestra/run", {"workflow": "nope/none"})
            ctx.check(f"an unknown workflow: 404, got {status}", status == 404)
            status, body, _ = s.call("POST", "orchestra/run", {"workflow": "doc-review/review", "inputs": {"docs": "docs"}})
            ctx.check(f"201 with its run, got {status} {body}", status == 201 and body.get("run_id"))
            from halo_harness.orchestra import plan as P
            from halo_harness.studio import orchestra_model as OM
            run_dir = OM.find_run(OM.repo_of(s.repo), body["run_id"])
            goal = json.loads((run_dir / "goal.json").read_text(encoding="utf-8"))
            ctx.check(f"the goal is the compiled workflow, got {goal.get('workflow', {}).get('ref')}", goal["workflow"]["ref"] == "doc-review/review"
                      and goal["lineup"] == "doc-review--review" and goal["plan"] == "review")
            from tests.helpers.packs_studio import until
            ctx.check("its plan waits for the review", until(lambda: P.is_planned(run_dir), 20))
            P.approve(run_dir, P.current_jobs(run_dir), by="test")
            ctx.check("the run ends", orchestra_live.wait(60))
            report = load_report(run_dir) or {}
            art = report.get("artifacts") or [{}]
            ctx.check(f"finished with its typed artifact, got {report.get('status')} {art}", report.get("status") == "finished"
                      and art[0].get("schema") == "review-report" and art[0].get("ok") is True)
    finally:
        orchestra_api.RUNNER = saved


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
