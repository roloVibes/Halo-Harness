"""tests.test_team_blocks -- Halo 3.0.8.0 round R1: block ledgers and the
stage write guard (halo_harness/team/blocks.py, guard.py): a member claims a
markdown section by writing it, a second member's write to that section is
refused naming the block and the holder while another section goes through,
a whole-file Write overlaps a held section, the release frees it; the
`file` and `none` claim modes; a file block's ledger beside the file;
changes.jsonl lines and state.json; writes outside the stage's blocks, in
no block or into a ledger refused; a path outside the repo untouched; the
run log's claim/change lines; `block_status`; install_from_env. No model.

Run: python -m tests.test_team_blocks
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers import team_rig as R  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _setup():
    from halo_harness.team import spec as S
    from halo_harness.team.board import new_run
    from halo_harness.team.run import rows_for
    root, state = R.repo()
    team = S.load_team(root, state)
    run_dir = new_run(root, team, rows_for(team, state_dir=state))
    return root, team, run_dir


def _guard(root, team, run_dir, member, stage, writes):
    from halo_harness.team.guard import TeamClaimGuard, write_scope
    path = write_scope(run_dir / f"scope-{member}-{stage}.json", root=root, run_dir=run_dir, stage=stage, member=member,
                       writes=writes, blocks=team["blocks"])
    return TeamClaimGuard.from_file(path)


def _edit(guard, path, old):
    from halo_harness.permissions import Decision
    return guard.check("Edit", {"file_path": str(path), "old_string": old, "new_string": "X"}, Decision("allow", "base"))


def _write(guard, path, tool="Write"):
    from halo_harness.permissions import Decision
    return guard.check(tool, {"file_path": str(path), "content": "x"}, Decision("allow", "base"))


@test
def test_claim_write_refuse_release_on_markdown_sections(ctx: Ctx):
    from halo_harness.team import blocks as B
    root, team, run_dir = _setup()
    intro = root / "content" / "intro.md"
    writer = _guard(root, team, run_dir, "writer", "draft", ["copy"])
    editor = _guard(root, team, run_dir, "editor", "draft", ["copy"])
    d = _edit(writer, intro, "more")
    ctx.check(f"the writer's edit of Overview is allowed and claims it, got {d.action} {d.reason}",
              d.action == "allow" and "section:intro.md#overview" in d.reason and d.source == "team")
    from halo_harness.team.spec import block_by_id
    copy = block_by_id(team, "copy")
    held = B.claim_log(root, copy).active()
    ctx.check(f"the claim is live and writing, got {[(c.key, c.holder, c.state) for c in held.values()]}",
              [(c.key, c.holder, c.state) for c in held.values()] == [("section:intro.md#overview", "writer@draft", "writing")])
    d = _edit(editor, intro, "more")
    ctx.check(f"the editor's edit of the same section is refused naming block and holder, got {d.reason!r}",
              d.action == "deny" and d.reason.startswith("block `copy`: `section:intro.md#overview` is held by writer@draft until "))
    d = _edit(editor, intro, "hello")
    ctx.check(f"another section goes through, got {d.action} {d.reason}", d.action == "allow" and "#intro" in d.reason)
    d = _write(editor, intro)
    ctx.check(f"a whole-file Write overlaps a held section, got {d.reason!r}",
              d.action == "deny" and "is held by writer@draft" in d.reason)
    ctx.check("the writer releases", B.release_holder(root, copy, "writer@draft") == ["section:intro.md#overview"])
    ctx.check("then the editor's edit goes through", _edit(editor, intro, "more").action == "allow")
    state = json.loads((root / "content" / ".halo-block" / "state.json").read_text(encoding="utf-8"))
    ctx.check(f"state.json names the block, the last change and the holders, got {state}",
              state["block"] == "copy" and state["holders"] == {"editor@draft": ["section:intro.md#intro",
                                                                                  "section:intro.md#overview"]}
              and state["last_change"]["member"] == "editor")
    ctx.check("the ledger is never committed", (root / "content" / ".halo-block" / ".gitignore").read_text(encoding="utf-8").strip().endswith("*"))


@test
def test_changes_lines_and_the_run_log(ctx: Ctx):
    from halo_harness.team import blocks as B
    from halo_harness.team.board import read_events
    from halo_harness.team.spec import block_by_id
    root, team, run_dir = _setup()
    writer = _guard(root, team, run_dir, "writer", "draft", ["copy"])
    _edit(writer, root / "content" / "intro.md", "more")
    _write(writer, root / "content" / "new.md")
    lines = B.changes(root, block_by_id(team, "copy"))
    ctx.check(f"two change lines, got {lines}", len(lines) == 2 and set(lines[0]) == {"ts", "by", "member", "stage", "op",
                                                                                      "key", "summary"})
    ctx.check("each names who, the stage, the op and the key",
              (lines[0]["by"], lines[0]["member"], lines[0]["stage"], lines[0]["op"], lines[0]["key"], lines[0]["summary"])
              == ("writer@draft", "writer", "draft", "edit", "section:intro.md#overview", "Edit content/intro.md")
              and (lines[1]["op"], lines[1]["key"]) == ("write", "section:new.md"))
    kinds = [(e["kind"], e["data"].get("refused", False)) for e in read_events(run_dir)]
    ctx.check(f"the run log has claim and change lines, got {kinds}",
              kinds == [("claim", False), ("change", False), ("claim", False), ("change", False)])
    ctx.check("since skips lines", len(B.changes(root, block_by_id(team, "copy"), 1)) == 1)


@test
def test_file_and_none_modes_and_a_file_block_ledger(ctx: Ctx):
    from halo_harness.team import blocks as B
    from halo_harness.team.spec import block_by_id
    root, team, run_dir = _setup()
    g = _guard(root, team, run_dir, "writer", "build", ["site", "notes"])
    d = _write(g, root / "site" / "index.html")
    ctx.check(f"file mode claims file:<rel>, got {d.reason}", d.action == "allow" and "`file:index.html`" in d.reason)
    other = _guard(root, team, run_dir, "editor", "build", ["site"])
    d = _write(other, root / "site" / "index.html")
    ctx.check(f"the same file is refused to another member, got {d.reason}", d.action == "deny" and "writer@build" in d.reason)
    d = _write(other, root / "NOTES.md")
    ctx.check("a block the stage does not write is refused", d.action == "deny" and "block `notes`" in d.reason)
    d = _write(g, root / "NOTES.md")
    notes = block_by_id(team, "notes")
    ctx.check(f"claims: none logs the write without a claim, got {d.reason}",
              d.action == "allow" and B.claim_log(root, notes).active() == {} and B.changes(root, notes)[0]["key"] == "NOTES.md")
    ctx.check("a file block's ledger sits beside it", (root / "NOTES.md.halo-block" / "changes.jsonl").is_file())


@test
def test_refusals_outside_the_scope_and_the_untouched_paths(ctx: Ctx):
    from halo_harness.permissions import Decision
    from halo_harness.team.board import read_events
    root, team, run_dir = _setup()
    g = _guard(root, team, run_dir, "writer", "draft", ["copy"])
    d = _write(g, root / "site" / "x.html")
    ctx.check(f"a block outside the stage's writes, got {d.reason!r}",
              d.action == "deny" and d.reason == "`site/x.html` is in block `site`; stage `draft` writes `copy`")
    d = _write(g, root / "README.md")
    ctx.check(f"a path in no block, got {d.reason!r}", d.action == "deny" and "is in no block" in d.reason)
    d = _write(g, root / "content" / ".halo-block" / "state.json")
    ctx.check(f"a block ledger, got {d.reason!r}", d.action == "deny" and "team ledger file" in d.reason)
    d = _write(g, run_dir / "board.json")
    ctx.check("the run ledger", d.action == "deny" and "team ledger file" in d.reason)
    ctx.check("a path outside the repo keeps the base decision", _write(g, Path(R.repo()[0]) / "x.md") is None)
    ctx.check("a read tool is untouched", g.check("Read", {"file_path": str(root / "site" / "x")}, Decision("allow", "b")) is None)
    refused = [e for e in read_events(run_dir) if e["data"].get("refused")]
    ctx.check(f"each refusal is a claim line with refused: true, got {len(refused)}", len(refused) == 4
              and refused[0]["kind"] == "claim" and refused[0]["stage"] == "draft")
    asked = g.check("Edit", {"file_path": str(root / "content" / "intro.md"), "old_string": "hello", "new_string": "y"},
                    Decision("ask", "your rule", matched_rule=object()))
    ctx.check("the user's own ask rule still asks (the write is logged)", asked is None)


@test
def test_block_status_and_install_from_env(ctx: Ctx):
    from halo_harness.team import SCOPE_ENV
    from halo_harness.team.blocks import all_status, block_status
    from halo_harness.team.guard import TeamClaimGuard, install_from_env
    root, team, run_dir = _setup()
    g = _guard(root, team, run_dir, "writer", "draft", ["copy"])
    _edit(g, root / "content" / "intro.md", "more")
    st = block_status(team, "copy")
    ctx.check(f"block_status keys, got {sorted(st)}", set(st) == {"id", "kind", "path", "claims", "ledger", "exists",
                                                                 "holders", "last_change", "changes_count", "recent"})
    ctx.check("holders and changes", st["holders"][0]["holder"] == "writer@draft" and st["changes_count"] == 1
              and st["recent"][0]["key"] == "section:intro.md#overview" and st["exists"] is True)
    ctx.check("an unknown block is None; all_status lists every block",
              block_status(team, "nope") is None and [b["id"] for b in all_status(team)] == ["copy", "site", "notes"])

    class Engine:
        guards: list = []
    eng = Engine()
    eng.guards = []
    scope = run_dir / "scope-writer-draft.json"
    ctx.check("no env, no guard", install_from_env(eng, env={}) is None and eng.guards == [])
    got = install_from_env(eng, env={SCOPE_ENV: str(scope)})
    again = install_from_env(eng, env={SCOPE_ENV: str(scope)})
    ctx.check("the guard is added once", isinstance(got, TeamClaimGuard) and again is got and len(eng.guards) == 1)


@test
def test_a_session_in_a_stage_installs_the_guard_and_the_engine_uses_it(ctx: Ctx):
    import os
    import tempfile
    from halo_harness import permissions as P
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.agent.loop import Session
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.providers.stream import ProviderCreds
    from halo_harness.team import SCOPE_ENV
    from halo_harness.team.guard import TeamClaimGuard
    root, team, run_dir = _setup()
    scope = _guard(root, team, run_dir, "writer", "draft", ["copy"]).scope
    path = run_dir / "scope-writer-draft.json"
    saved = os.environ.get(SCOPE_ENV)

    def make():
        return Session(cwd=root, model_ref=parse_model_ref("or:mock/x"), model_profile=ModelProfile(),
                       creds=ProviderCreds(base_url="http://127.0.0.1:1", api_key="k"),
                       state_dir=Path(tempfile.mkdtemp(prefix="team-sess-state-")), model_label="mock/x",
                       session_context=SessionContext(cwd=root, model_label="mock/x"),
                       permission_engine=P.PermissionEngine(mode="auto", cwd=root))
    try:
        os.environ.pop(SCOPE_ENV, None)
        ctx.check("outside a stage a session has no team guard",
                  not any(isinstance(g, TeamClaimGuard) for g in make().permission_engine.guards))
        os.environ[SCOPE_ENV] = str(path)
        eng = make().permission_engine
        guards = [g for g in eng.guards if isinstance(g, TeamClaimGuard)]
        ctx.check(f"inside a stage: one TeamClaimGuard for writer@draft, got {len(guards)}",
                  len(guards) == 1 and guards[0].holder == scope["holder"] == "writer@draft")
        d = eng.decide("Write", {"file_path": str(root / "site" / "x.html"), "content": "x"})
        ctx.check(f"the engine refuses a write outside the stage's blocks, got {d.action} {d.reason!r}",
                  d.action == "deny" and "stage `draft` writes `copy`" in d.reason)
        d = eng.decide("Write", {"file_path": str(root / "content" / "b.md"), "content": "x"})
        ctx.check(f"and allows one inside, got {d.action}", d.action == "allow")
    finally:
        if saved is None:
            os.environ.pop(SCOPE_ENV, None)
        else:
            os.environ[SCOPE_ENV] = saved


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="team block tests"))
