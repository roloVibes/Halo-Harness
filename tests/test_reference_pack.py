"""tests.test_reference_pack -- the shipped Documentation Review pack, end to
end (Halo 3.2.0.0 R6): the regression test of the whole extension API. Over a
fresh home and a git repo with two Markdown files, no core change and no
model call:

1. `halo pack list --available` names it (the packs Halo ships, the last
   place a bare id is looked for); `halo pack install doc-review` installs
   it from there, disabled; `halo pack enable doc-review --grant-all`; `halo
   pack doctor` finds nothing; its README is the guide (every file, one line);
2. its review workflow runs through the mock lead and stage workers to the
   typed review-report artifact and the report;
3. Studio: its section and the "Last review report" artifact panel are in
   the registry, the panel's route draws that run's report, its lineup is
   under Roles; its fleet capability is in the catalog, available here;
4. its lint MCP server, started from its `.mcp.json` the way a session
   starts it (`${halo_python}`, R7), answers initialize, tools/list and check_links;
5. 3.2.0.0 R7: an update from a newer copy keeps 1.0.0 as doc-review.previous;
   `halo pack remove doc-review`: nothing of the pack is left in the home --
   not its folder, not the `.previous` copy, no file the journal still owns --
   only what the user made (a bio cloned from it, a setting) and Halo's own
   records (state.json without it, the journal).

Run: python -m tests.test_reference_pack
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import DOC_REVIEW  # noqa: E402
from tests.helpers.packs_studio import PackStudio  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.workflow_rig import GOOD_REPORT, StageWorker, WorkflowRig  # noqa: E402

test, TESTS = new_registry()
ROW = {"ref": "or:anthropic/claude-sonnet-4.6", "provider": "openrouter", "tools": True, "context_tokens": 262144}
OWN = {".halo/packs/state.json", ".halo/packs/journal.jsonl"}  # Halo's own records of what it installed


class RefRig(PackStudio, WorkflowRig):
    """The workflow rig's repo and catalog, the pack not installed yet, served by a real Studio."""
    INSTALL = False


def _files(home: Path) -> "set[str]":
    return {p.relative_to(home).as_posix() for p in home.rglob("*") if p.is_file() and "__pycache__" not in p.parts}


def _mcp(pack_root: Path, repo: Path) -> "list[dict]":
    """3.2.0.0 R7: started the way a session starts it -- its `.mcp.json` through the plugin-root channel,
    `${halo_python}` expanded to Halo's Python, PYTHONPATH from the pack's env."""
    import os
    from halo_harness.config.plugins import discover_plugin_mcp_servers
    servers, _notices = discover_plugin_mcp_servers(env=dict(os.environ), extra_roots=[str(pack_root)])
    cfg = servers["plugin_doc-review_lint"]
    msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "check_links", "arguments": {"path": "docs/guide.md"}}}]
    r = subprocess.run([cfg.command] + list(cfg.args), env={**os.environ, **cfg.env}, input="\n".join(json.dumps(m) for m in msgs) + "\n",
                       capture_output=True, text=True, encoding="utf-8", cwd=str(repo), timeout=60)
    return [json.loads(line) for line in r.stdout.splitlines() if line.strip()]


@test
def test_the_reference_pack_end_to_end(ctx: Ctx):
    with RefRig() as h:
        h.catalog([ROW])
        before = _files(h.home)
        code, out, _err = h.cli("list", "--available")
        ctx.check(f"list --available names it from the shipped folder, got {out!r}", code == 0 and "available (halo pack install <id>):" in out
                  and "doc-review  1.0.0     Documentation Review  from " in out and out.rstrip().endswith("halo_harness/templates/packs"))
        code, out, err = h.cli("install", "doc-review")
        ctx.check(f"installed by id, disabled, got {code} {out.splitlines()[:1]} {err!r}", code == 0 and out.startswith("installed doc-review 1.0.0 at ")
                  and "(disabled)" in out.splitlines()[0])
        from halo_harness.packs.state import entry
        ctx.check("from the shipped folder", Path(entry("doc-review")["source"]) == DOC_REVIEW)
        code, out, _err = h.cli("enable", "doc-review", "--grant-all")
        ctx.check(f"enabled with its grants, got {out.splitlines()[:5]}", code == 0 and all(f"{g}" in out for g in ("mcp:lint", "hooks", "bash"))
                  and "not granted" not in out)
        code, out, _err = h.cli("doctor")
        ctx.check(f"halo pack doctor finds nothing, got {out!r}", code == 0 and "RESULT: 0 problem(s)" in out)
        readme = (h.packs / "doc-review" / "README.md").read_text(encoding="utf-8")
        listed = [p.relative_to(DOC_REVIEW).as_posix() for p in sorted(DOC_REVIEW.rglob("*")) if p.is_file() and "__pycache__" not in p.parts]
        ctx.check(f"its README explains every file, missing {[f for f in listed if f'`{f}`' not in readme]}",
                  all(f"`{f}`" in readme for f in listed) and "halo pack doctor" in readme and "halo_api" in readme)

        run = h.new_run(h.compile(docs="docs").goal)
        report = h.run(run, worker=StageWorker())
        art = (report.get("artifacts") or [{}])[0]
        ctx.check(f"its workflow runs to the typed artifact, got {report['status']} {art}", report["status"] == "finished"
                  and art.get("schema") == "review-report" and art.get("view") == "table" and art.get("ok") is True)

        from halo_harness.packs.studio_registry import registry
        entry_ = next(p for p in registry(cwd=h.repo)["packs"] if p["id"] == "doc-review")
        panels = {x["id"]: x["kind"] for s in entry_["sections"] for x in s["panels"]}
        ctx.check(f"its section and its artifact panel in Studio's registry, got {panels}", [s["id"] for s in entry_["sections"]] == ["doc-review--docs"]
                  and panels.get("doc-review--report") == "artifact")
        status, body, _ = h.call("GET", "pack/doc-review/artifact/review-report")
        ctx.check(f"the panel draws that run's report, got {status} {body.get('run')} {body.get('view')}", status == 200
                  and body["data"] == GOOD_REPORT and body["run"] == run.name and body["view"] == "table")
        status, rows, _ = h.call("GET", "lineups")
        mine = [r for r in rows if r.get("name") == "doc-review--review"]
        ctx.check(f"its lineup under Roles, got {[(r['name'], r['scope']) for r in mine]}", status == 200 and len(mine) == 1
                  and "doc-review" in mine[0]["scope"])
        from halo_harness.fleet import capabilities as caps
        cap = next(p for p in caps.gather(h.state, cwd=h.repo)["packs"] if p["id"] == "doc-review")["capabilities"][0]
        ctx.check(f"its fleet capability in the catalog, available, got {cap}", cap["name"] == "docs.review" and cap["available"] is True)

        replies = _mcp(h.packs / "doc-review", h.repo)
        by_id = {r.get("id"): r for r in replies}
        ctx.check(f"its lint MCP server answers, got {replies}", by_id.get(1, {}).get("result", {}).get("serverInfo", {}).get("name") == "doc-review-lint"
                  and [t["name"] for t in by_id.get(2, {}).get("result", {}).get("tools", [])] == ["check_links", "check_headings"]
                  and by_id.get(3, {}).get("result", {}).get("content", [{}])[0].get("text") == "guide.md line 3: missing.md is not there")

        status, body, _ = h.call("POST", "roles/clone", {"kind": "bio", "name": "doc-review--writer", "as": "my-writer"})
        ctx.check(f"you clone its writer bio, got {status}", status == 201)
        status, _body, _ = h.call("POST", "pack/doc-review/settings", {"values": {"style": "long"}})
        ctx.check("you set a setting", status == 200)
        newer = Path(tempfile.mkdtemp(prefix="doc-review-next-")) / "doc-review"  # 3.2.0.0 R7: a newer version, outside the home
        shutil.copytree(DOC_REVIEW, newer, ignore=shutil.ignore_patterns("__pycache__"))
        (newer / "pack.yaml").write_text((newer / "pack.yaml").read_text(encoding="utf-8").replace("version: 1.0.0", "version: 1.0.1"),
                                         encoding="utf-8")
        from halo_harness.packs import state as S
        S.put("doc-review", {"source": str(newer)})
        code, out, _err = h.cli("update", "doc-review")
        ctx.check(f"an update keeps 1.0.0 as doc-review.previous, got {out.splitlines()[1:2]}", code == 0
                  and (h.packs / "doc-review.previous" / "pack.yaml").is_file())
        code, out, _err = h.cli("remove", "doc-review")
        ctx.check(f"removed, your setting listed as staying, got {out!r}", code == 0 and "its folder is gone" in out
                  and "your settings packs.settings.doc-review stay" in out
                  and "removed doc-review.previous, the version the last update replaced" in out)
        from halo_harness.packs import journal as J
        ctx.check("no doc-review.previous is left, and the journal owns no file of it any more",
                  not (h.packs / "doc-review.previous").exists() and J.owned("doc-review") == {})
        shutil.rmtree(newer.parent, ignore_errors=True)
        left = _files(h.home) - before
        pack_files = {f for f in left if f.startswith(".halo/packs/") and f not in OWN}
        ctx.check(f"nothing of the pack is left in ~/.halo/packs, got {sorted(pack_files)}", not pack_files and not (h.packs / "doc-review").exists())
        state = json.loads((h.packs / "state.json").read_text(encoding="utf-8"))
        ctx.check("state.json no longer lists it", state["installed"] == {})
        ctx.check(f"what you made stays, got {sorted(left)}", ".halo/agents/my-writer.yaml" in left
                  and "from_pack: doc-review@1.0.0" in (h.home / ".halo" / "agents" / "my-writer.yaml").read_text(encoding="utf-8"))
        shipped = {p.name for p in DOC_REVIEW.rglob("*") if p.is_file()} - {"README.md"}
        stray = sorted(f for f in left if Path(f).name in shipped)
        ctx.check(f"no copy of one of its files anywhere in the home, got {stray}", not stray)


@test
def test_the_shipped_pack_needs_the_halo_it_ships_in(ctx: Ctx):
    """3.2.0.0 R7: the reference pack's `halo` range takes this Halo, and from 3.2.0.0 on it is `{min: "<major.minor>"}` of
    the release it ships in -- scripts/release.py sets it in pack.yaml in the same commit as `__version__`."""
    from halo_harness import __version__
    from halo_harness.agents_yaml import _read_yaml_file
    from halo_harness.packs import semver as V
    rng = (_read_yaml_file(DOC_REVIEW / "pack.yaml") or {}).get("halo")
    ctx.check(f"this Halo ({__version__}) is inside {rng}", V.in_range(__version__, rng))
    if V.compare(__version__, "3.2") >= 0:
        want = ".".join(__version__.split(".")[:2])
        ctx.check(f'from 3.2.0.0 on pack.yaml says halo: {{min: "{want}"}}, the release it ships in, got {rng}',
                  rng == {"min": want})


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
