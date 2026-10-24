"""tests.test_packs_roles_api -- Studio's Roles over packs, through the API
(Halo 3.2.0.0 R2, studio/packs_roles_api.py; the Chrome checks are
tests/test_packs_roles_studio.py): `GET state` / `roles/packs` name the
packs that run; Clone copies a pack's bio or lineup into your folder as
`<name>` with `from_pack`, answers 409 (never writing) when a file of yours
or a shipped one has the name, and writes only with `replace`; a row says
whose name a file of yours shadows; a card warns of an ungranted need and of
tags no catalog model has; Apply of a pack's lineup writes config.json only.
Run: python -m tests.test_packs_roles_api
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _call(h, method: str, path: str, body=None, query=None):
    from halo_harness.studio import api
    return api.dispatch(api.Request(method=method, path=path, query=query or {}, body=body or {}, cwd=h.repo,
                                    state_dir=h.state))


def _hashes(folder: Path) -> dict:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.glob("*.yaml"))} if folder.is_dir() else {}


@test
def test_state_names_the_packs_that_run(ctx: Ctx):
    with PacksHome() as h:
        h.install(h.source())
        ctx.check("a disabled pack: none", _call(h, "GET", "state")[1]["packs"] == [] and _call(h, "GET", "roles/packs")[1] == [])
        h.cli("enable", "doc-review")
        got = _call(h, "GET", "roles/packs")[1]
        ctx.check(f"enabled: its id, name and version, got {got}",
                  got == [{"id": "doc-review", "name": "Documentation Review", "version": "1.0.0", "scope": "user"}])
        ctx.check("and in state", _call(h, "GET", "state")[1]["packs"] == got)


@test
def test_clone_copies_with_from_pack_and_asks_before_any_file_of_yours(ctx: Ctx):
    with PacksHome() as h:
        h.install(h.source(), enable=True)
        pack_files = _hashes(h.packs / "doc-review" / "agents")
        status, out = _call(h, "POST", "roles/clone", {"kind": "bio", "name": "doc-review--writer"})
        mine = h.state / "agents" / "writer.yaml"
        text = mine.read_text(encoding="utf-8") if mine.is_file() else ""
        ctx.check(f"no collision: 201, writer.yaml with from_pack, got {status} {out}",
                  status == 201 and out["name"] == "writer" and "from_pack: doc-review@1.0.0" in text
                  and "extends: doc-review--reviewer" in text)
        before = mine.read_bytes()
        status, out = _call(h, "POST", "roles/clone", {"kind": "bio", "name": "doc-review--writer"})
        ctx.check(f"yours has the name: 409, nothing written, got {status} {out}",
                  status == 409 and out["exists"] is True and out["shipped"] is False and mine.read_bytes() == before)
        status, out = _call(h, "POST", "roles/clone", {"kind": "bio", "name": "doc-review--writer", "as": "writer-2"})
        ctx.check("another name: 201", status == 201 and (h.state / "agents" / "writer-2.yaml").is_file())
        status, out = _call(h, "POST", "roles/clone", {"kind": "bio", "name": "doc-review--writer", "replace": True})
        ctx.check(f"replace (the confirm's answer): 201, replaced, got {out}", status == 201 and out["replaced"] is True)
        status, out = _call(h, "POST", "roles/clone", {"kind": "bio", "name": "doc-review--reviewer"})
        ctx.check(f"a shipped name (reviewer): 409 too, got {status} {out.get('error')}",
                  status == 409 and out["shipped"] is True and not (h.state / "agents" / "reviewer.yaml").exists())
        status, out = _call(h, "POST", "roles/clone", {"kind": "lineup", "name": "doc-review--review"}, {"scope": "project"})
        lineup = h.repo / ".halo" / "teams" / "review.yaml"
        body = lineup.read_text(encoding="utf-8") if lineup.is_file() else ""
        ctx.check(f"a lineup to the project scope: its members stay the pack's bios, got {status}",
                  status == 201 and "agent: doc-review--writer" in body and "from_pack: doc-review@1.0.0" in body)
        status, out = _call(h, "POST", "roles/clone", {"kind": "bio", "name": "coder"})
        ctx.check(f"not a pack's: 404, got {status} {out}", status == 404 and "not a pack's bio" in out["error"])
        ctx.check("the pack's files are untouched", _hashes(h.packs / "doc-review" / "agents") == pack_files)


@test
def test_rows_say_what_they_shadow_and_where_they_came_from(ctx: Ctx):
    with PacksHome() as h:
        h.install(h.source(), enable=True)
        h.write(".halo/agents/doc-review--reviewer.yaml", "description: mine\n")
        _call(h, "POST", "roles/clone", {"kind": "lineup", "name": "doc-review--review"})
        bios = {b["name"]: b for b in _call(h, "GET", "bios")[1]}
        row = bios["doc-review--reviewer"]
        ctx.check(f"your file's row names the pack it shadows, got {row}",
                  row["scope"] == "user" and row["shadows"] == "doc-review"
                  and row["shadowed_by"] == "~/.halo/agents/doc-review--reviewer.yaml")
        # yours wins everywhere: the pack's writer `extends: reviewer` reads your file now, so no tags come with it
        ctx.check(f"the writer is the pack's and extends yours, got {bios['doc-review--writer']}",
                  bios["doc-review--writer"]["scope"] == "pack:doc-review" and bios["doc-review--writer"]["capabilities"] == []
                  and bios["doc-review--writer"]["shadows"] == "")
        lineups = {r["name"]: r for r in _call(h, "GET", "lineups")[1]}
        ctx.check(f"the clone says where it came from, got {lineups['review']}", lineups["review"]["from_pack"] == "doc-review@1.0.0")
        status, data = _call(h, "GET", "lineup/doc-review--review")
        ctx.check("the pack's lineup payload names its pack (it opens read-only)", status == 200 and data["pack"] == "doc-review")


@test
def test_a_card_warns_of_an_ungranted_need_and_tags_no_model_has(ctx: Ctx):
    with PacksHome() as h:
        h.install(h.source(), enable=True)
        h.catalog([])
        status, data = _call(h, "GET", "lineup/doc-review--review")
        warns = [w for n in data["graph"]["nodes"] for w in n["warnings"]]
        ctx.check(f"each card: bash not granted (the command) and no model with long-context, got {warns}",
                  any("uses bash, which is not granted: halo pack enable doc-review --grant bash" in w for w in warns)
                  and any("no model in the catalog has long-context" in w for w in warns))
        ctx.check("the Problems panel lists them", any("--grant bash" in f["text"] for f in data["findings"]))
        h.cli("enable", "doc-review", "--grant", "bash")
        h.catalog([{"ref": "ol:long-1", "provider": "ollama", "context_tokens": 262144}])
        status, data = _call(h, "GET", "lineup/doc-review--review")
        nodes = data["graph"]["nodes"]
        ctx.check(f"granted and matched: no warning, the card runs on the pick, got {[(n['model'], n['model_source'], n['warnings']) for n in nodes]}",
                  all(not n["warnings"] for n in nodes) and any(n["model_source"] == "capabilities" for n in nodes)
                  and all(n["model"] == "ol:long-1" for n in nodes))


@test
def test_new_and_duplicate_never_write_over_a_file_of_yours(ctx: Ctx):
    with PacksHome() as h:
        h.install(h.source(), enable=True)
        mine = h.write(".halo/teams/review.yaml", "description: mine\nroles: {main: coder}\n")
        bio = h.write(".halo/agents/writer.yaml", "description: my writer\n")
        before = mine.read_bytes(), bio.read_bytes()
        status, out = _call(h, "POST", "lineup", {"name": "review", "from": "doc-review--review"})
        ctx.check(f"Duplicate a pack lineup onto your name: 409, got {status} {out.get('error')}", status == 409 and "already yours" in out["error"])
        status, _out = _call(h, "POST", "bio", {"name": "writer", "from": "doc-review--writer"})
        ctx.check("the same for a bio", status == 409 and (mine.read_bytes(), bio.read_bytes()) == before)
        status, _out = _call(h, "POST", "lineup", {"name": "review-2", "from": "doc-review--review"})
        ctx.check("another name: created", status == 201 and (h.state / "teams" / "review-2.yaml").is_file())


@test
def test_applying_a_packs_lineup_writes_config_only(ctx: Ctx):
    with PacksHome() as h:
        h.install(h.source(), enable=True)
        h.write(".halo/agents/writer.yaml", "description: my own writer\n")
        h.write(".halo/teams/mine.yaml", "roles: {main: writer}\n")
        agents, teams = _hashes(h.state / "agents"), _hashes(h.state / "teams")
        status, out = _call(h, "POST", "lineup/doc-review--review/apply")
        import json
        cfg = json.loads((h.state / "config.json").read_text(encoding="utf-8"))
        ctx.check(f"applied: the active team is the pack's lineup, got {status} {cfg.get('team')}",
                  status == 200 and cfg.get("team") == "doc-review--review")
        ctx.check("no bio or lineup file of yours changed", _hashes(h.state / "agents") == agents
                  and {k: v for k, v in _hashes(h.state / "teams").items() if k in teams} == teams)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
