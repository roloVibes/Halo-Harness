"""tests.test_packs_roles -- a pack's bios and lineups (Halo 3.2.0.0 R2,
docs/PACKS.md "A pack's bios" / "A pack's lineups"): the model from
`models.capabilities` (the best catalog row, a family first, your default
when none has the tags), a bio naming one provider and a lineup naming a
stray workflow as manifest problems naming the line, `tools.needs` loading
with a doctor row naming the grant, the memory namespace keeping recall
apart, the lineup's acceptance as the Orchestra defaults, a file of yours
named like a pack's winning (the pack's listed as shadowed), a disabled
pack adding no group. No model is called; the catalog is a list.
Run: python -m tests.test_packs_roles
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import DOC_REVIEW, FIXTURES, PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()

ROWS = [{"ref": "or:vendor/cheap-long", "provider": "openrouter", "context_tokens": 400_000, "price_in_per_m": 0.2},
        {"ref": "or:vendor/claude-sonnet-9", "provider": "openrouter", "context_tokens": 300_000, "price_in_per_m": 1.0},
        {"ref": "or:vendor/workhorse-long", "provider": "openrouter", "context_tokens": 1_000_000, "price_in_per_m": 2.0},
        {"ref": "or:vendor/short", "provider": "openrouter", "context_tokens": 32_000, "price_in_per_m": 5.0}]


def _doctor(h, check: str) -> list:
    from halo_harness.packs.doctor import problems
    return [p for p in problems(cwd=h.repo) if p["check"] == check]


@test
def test_a_pack_bio_runs_on_the_best_catalog_model_with_its_tags(ctx: Ctx):
    from halo_harness import agents_yaml as A
    with PacksHome() as h:
        h.catalog(ROWS)
        h.config({"model": "or:vendor/my-default"})
        h.install(h.source(), enable=True)
        h.install(h.source("rare-caps"), enable=True)
        rev = A.resolve_agent_bio("doc-review--reviewer", cwd=h.repo)
        ctx.check(f"long-context: the workhorse-tier row with the larger window, got {rev['models']} {rev.get('_model')}",
                  rev["models"]["preference"] == "or:vendor/workhorse-long" and rev["_model"]["how"] == "capabilities")
        wri = A.resolve_agent_bio("doc-review--writer", cwd=h.repo)
        ctx.check(f"the writer: its family first (claude-sonnet), tags inherited, got {wri['models']}",
                  wri["models"]["preference"] == "or:vendor/claude-sonnet-9" and wri["_model"]["prefer"] == "claude-sonnet")
        watcher = A.resolve_agent_bio("rare-caps--watcher", cwd=h.repo)
        ctx.check(f"no row has video + image-out + long-context: your default, with the line, got {watcher.get('_model')}",
                  watcher["models"]["preference"] == "or:vendor/my-default" and watcher["_model"]["how"] == "default"
                  and "no model in the catalog has video, image-out, long-context" in watcher["_model"]["problem"])
        rows = _doctor(h, "bio-model")
        ctx.check(f"doctor: one row per capability set nothing has, got {[r['text'] for r in rows]}",
                  len(rows) == 1 and rows[0]["pack"] == "rare-caps" and "halo models --refresh" in rows[0]["fix"])
        h.write(".halo/agents/mine.yaml", "models: {preference: 'or:vendor/short', capabilities: [long-context]}\n")
        mine = A.resolve_agent_bio("mine", cwd=h.repo)
        ctx.check(f"a bio of yours: a full ref in preference pins it, got {mine['models']}",
                  mine["models"]["preference"] == "or:vendor/short" and mine["_model"]["how"] == "preference")
        ctx.check("a bio of yours may ask by tag too; an unknown tag is a validator line",
                  any("'telepathy' is not one of" in p for p in A.validate_agent_bio({"models": {"capabilities": ["telepathy"]}})))


@test
def test_the_enriched_row_tags(ctx: Ctx):
    """3.2.1.0 R1: reasoning, open-weights and audio-out from 3.1.9.0 R1's row keys; `local` from the row when it says."""
    from halo_harness.packs import bio_models as BM
    full = {"ref": "or:vendor/thinker", "provider": "openrouter", "reasoning": {"kind": "native", "efforts": ["low", "high"]},
            "open_weights": True, "modalities_in": ["text", "audio"], "modalities_out": ["text", "audio"], "tools": True}
    got = BM.row_tags(full)
    ctx.check(f"a row stating them all, got {sorted(got)}", {"reasoning", "open-weights", "audio-out", "audio", "tools"} <= got)
    plain = {"ref": "or:vendor/plain", "provider": "openrouter", "reasoning": {"kind": "none"}, "open_weights": False,
             "modalities_out": ["text"], "local": False}
    ctx.check(f"kind none, open_weights false, text out: none of the three, got {BM.row_tags(plain)}",
              not {"reasoning", "open-weights", "audio-out"} & BM.row_tags(plain))
    ctx.check("an unknown reasoning (None) or open_weights (None) is not a tag",
              not {"reasoning", "open-weights"} & BM.row_tags({"ref": "x", "reasoning": None, "open_weights": None}))
    router = {"ref": "hf:org/model", "provider": "huggingface", "local": False}
    ctx.check("an HF router row that says local: False is remote", "local" not in BM.row_tags(router))
    ctx.check("a row with local: True is local", "local" in BM.row_tags({"ref": "x", "provider": "openrouter", "local": True}))
    ctx.check("a row without the key: the provider decides (ollama)", "local" in BM.row_tags({"ref": "ol:m", "provider": "ollama"}))
    ctx.check("the three are tags a bio may ask for", {"reasoning", "open-weights", "audio-out"} <= set(BM.TAGS))
    got = BM.pick({"capabilities": ["reasoning", "open-weights"]}, rows=[plain, full])
    ctx.check(f"a bio asking for reasoning + open-weights gets the row with both, got {got}",
              got["ref"] == "or:vendor/thinker" and got["how"] == "capabilities")


@test
def test_a_pack_bio_naming_one_provider_is_a_manifest_problem_naming_the_line(ctx: Ctx):
    from halo_harness.packs.discover import read_pack
    from halo_harness.packs.install import install
    with PacksHome() as h:
        lines = read_pack(h.source("provider-pinned"), "source").problems
        ctx.check(f"the or: preference, with its file and line, got {lines}",
                  any(ln.startswith("agents/pinned.yaml line 5: models.preference 'or:vendor/some-model' names one provider")
                      for ln in lines))
        ctx.check("models.provider, with its file and line", any(ln.startswith("agents/routed.yaml line 6: models.provider")
                                                                for ln in lines))
        ok, out = install(str(h.source("provider-pinned")), cwd=h.repo)
        ctx.check(f"install checks first and refuses it, got {out}", not ok and not (h.packs / "provider-pinned").exists())
        ok_fixture = read_pack(DOC_REVIEW, "source").problems
        ctx.check(f"a family name (claude-sonnet) and tags are fine, got {ok_fixture}", ok_fixture == [])


@test
def test_needs_load_and_name_the_grant(ctx: Ctx):
    from halo_harness import agents_yaml as A
    from halo_harness.packs.discover import read_pack
    with PacksHome() as h:
        h.catalog(ROWS)
        h.install(h.source(), enable=True, grants=["hooks", "mcp:lint"])
        ctx.check("the reviewer loads with bash not granted", A.resolve_agent_bio("doc-review--reviewer", cwd=h.repo) is not None)
        rows = _doctor(h, "bio-need")
        ctx.check(f"one row for bash naming both bios and the command, got {[(r['text'], r['fix']) for r in rows]}",
                  len(rows) == 1 and "bios doc-review--reviewer, doc-review--writer use bash" in rows[0]["text"]
                  and rows[0]["fix"] == "halo pack enable doc-review --grant bash")
        h.cli("enable", "doc-review", "--grant", "bash")
        ctx.check("granted: the row is gone", _doctor(h, "bio-need") == [])
        src = h.source(folder="unrequested")
        (src / "pack.yaml").write_text((src / "pack.yaml").read_text(encoding="utf-8").replace(", bash]", "]"), encoding="utf-8")
        lines = read_pack(src, "source", folder_is_id=False).problems
        ctx.check(f"a need pack.yaml does not request: a manifest line, got {lines}",
                  any("tools.needs 'bash' is not in pack.yaml's permissions" in ln for ln in lines))


@test
def test_the_memory_namespace_keeps_recall_apart(ctx: Ctx):
    from halo_harness import agents_yaml as A
    from halo_harness import recall
    from halo_harness.packs import memory as M
    import halo_harness.providers.embeddings as E
    with PacksHome() as h:
        h.install(h.source(), enable=True)
        rev = A.resolve_agent_bio("doc-review--reviewer", cwd=h.repo)
        ctx.check(f"the reviewer's namespace sits under its pack, got {M.bio_namespace(rev)}", M.bio_namespace(rev) == "doc-review/reviews")
        h.write(".halo/agents/plain.yaml", "context: {memory: {namespace: reviews}}\n")
        ctx.check("a bio of yours has none (it reads yours, as before)", M.bio_namespace(A.resolve_agent_bio("plain", cwd=h.repo)) is None)
        ctx.check("the default is the pack's id", M.bio_namespace({"_pack": "doc-review"}) == "doc-review/doc-review")
        mine = M.namespace_dir("doc-review/reviews", state_dir=h.state)
        h.write("notes-a.md", "a review note\n", base=mine)
        h.write("notes-b.md", "another pack's note\n", base=M.namespace_dir("other-pack/reviews", state_dir=h.state))
        folder, line = M.member_note(rev, h.state)
        ctx.check(f"a team member on it is told its folder, got {line!r}", folder == mine and "doc-review/reviews" in line)
        saved = (E.embeddings_enabled, E.embed_texts)
        E.embeddings_enabled, E.embed_texts = (lambda: True), (lambda texts: [[1.0, 0.0] for _ in texts])
        try:
            report = recall.build_index(h.state, cwd=h.repo)
            index = h.state / "index" / "embeddings.jsonl"
            with index.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"id": str(h.home / "your-note.md"), "kind": "memory", "title": "yours", "mtime": 1, "vec": [1.0, 0.0]}) + "\n")
            got = lambda ns: sorted(Path(x["id"]).name for x in recall.search("note", state_dir=h.state, refresh=False, namespace=ns))  # noqa: E731
            ctx.check(f"the pack notes are indexed (one store), got {report}", report["embedded"] == 2)
            ctx.check(f"the namespace reads its own notes only, got {got('doc-review/reviews')}", got("doc-review/reviews") == ["notes-a.md"])
            ctx.check(f"another pack's reads its own, got {got('other-pack/reviews')}", got("other-pack/reviews") == ["notes-b.md"])
            ctx.check(f"yours leaves every pack out, got {got(None)}", got(None) == ["your-note.md"])
        finally:
            E.embeddings_enabled, E.embed_texts = saved


@test
def test_a_lineups_workflows_and_acceptance(ctx: Ctx):
    from halo_harness import teams_yaml as T
    from halo_harness.orchestra.goal import Goal
    from halo_harness.packs.discover import read_pack
    from halo_harness.packs.lineup_run import acceptance_problems, goal_defaults, run_defaults
    with PacksHome() as h:
        lines = read_pack(h.source("stray-workflow"), "source").problems
        ctx.check(f"a stray workflow name: one line naming it and the file's line, got {lines}",
                  lines == ["teams/flow.yaml line 5: workflows 'publish' is not one of the pack's contributes.workflows (review)"])
        h.install(h.source(), enable=True)
        raw = T.load_team_template_raw("doc-review--review", cwd=h.repo)
        ctx.check("the review lineup validates (two tiers, acceptance, workflows)",
                  T.validate_team_template(raw, name="doc-review--review", cwd=h.repo) == [])
        resolved = T.resolve_team_template("doc-review--review", cwd=h.repo)
        ctx.check(f"workflows carry through, got {resolved.get('workflows')}", resolved.get("workflows") == ["review"])
        ctx.check(f"the Orchestra defaults, got {run_defaults('doc-review--review', cwd=h.repo)}",
                  run_defaults("doc-review--review", cwd=h.repo) == {"test": "python -m pytest -q", "review": True})
        goal = Goal(what="w", done_when="d", stop_when="s", lineup="doc-review--review")
        taken = goal_defaults(goal, cwd=h.repo)
        ctx.check(f"a run on it starts with them, got {goal.test!r} {goal.plan!r} {taken}",
                  goal.test == "python -m pytest -q" and goal.plan == "review" and len(taken) == 2)
        typed = Goal(lineup="doc-review--review", test="make check")
        goal_defaults(typed, cwd=h.repo, explicit_test=True)
        ctx.check("what you type wins", typed.test == "make check")
        bad = acceptance_problems({"workflows": "review", "acceptance": {"test": 3, "review": "yes"}})
        ctx.check(f"bad values: one line each, got {bad}", len(bad) == 3)


@test
def test_a_file_of_yours_named_like_a_pack_bio_wins_and_the_pack_is_shadowed(ctx: Ctx):
    from halo_harness import agents_yaml as A
    from halo_harness.packs.roles import list_lines, shadow_of
    from halo_harness.teams_cli_views import agent_group_lines
    with PacksHome() as h:
        h.install(h.source(), enable=True)
        mine = h.write(".halo/agents/doc-review--reviewer.yaml",
                       (FIXTURES / "user-files" / "doc-review--reviewer.yaml").read_text(encoding="utf-8"))
        found = A.find_agent_bio_path("doc-review--reviewer", cwd=h.repo)
        ctx.check(f"yours is the one read, got {found}", found == (mine, "user"))
        lines = list_lines("bios", A.list_agent_bios(cwd=h.repo), cwd=h.repo)
        ctx.check(f"halo agents list: the pack's group says it is shadowed, got {lines[-3:]}",
                  "  doc-review--reviewer  shadowed by ~/.halo/agents/doc-review--reviewer.yaml" in lines
                  and "pack doc-review:" in lines and "doc-review--reviewer" in lines)
        grouped = agent_group_lines(cwd=h.repo)
        ctx.check("halo agents: the pack group too", any("doc-review--reviewer -- shadowed by ~/.halo/agents/" in ln for ln in grouped))
        ctx.check("the row knows whose name it shadows", shadow_of("bios", "doc-review--reviewer", "user", cwd=h.repo) == "doc-review")
        from halo_harness.packs.doctor import problems
        ctx.check("doctor names it (yours is used)", any("yours is used" in p["text"] for p in problems(cwd=h.repo)))


@test
def test_a_disabled_pack_adds_no_group(ctx: Ctx):
    from halo_harness import agents_yaml as A
    from halo_harness import teams_yaml as T
    from halo_harness.packs.roles import list_lines, pack_groups
    from halo_harness.studio.packs_roles_api import active_packs
    with PacksHome() as h:
        h.install(h.source())
        names = A.list_agent_bios(cwd=h.repo)
        ctx.check("no group, no pack name", pack_groups("bios", cwd=h.repo) == [] and list_lines("bios", names, cwd=h.repo) == names
                  and not any(n.startswith("doc-review--") for n in names + T.list_team_templates(cwd=h.repo)))
        ctx.check("Studio's Roles groups by no pack", active_packs(h.repo, h.state) == [])
        h.cli("enable", "doc-review")
        ctx.check("enabled: its group", [g[0] for g in pack_groups("lineups", cwd=h.repo)] == ["doc-review"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
