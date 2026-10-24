"""tests.test_pack_memory_provenance -- a pack's memory entries with their
provenance (Halo 3.2.0.0 R5; ext/memory.py, packs/memory_meta.py, recall.py,
recall_cli.py): `ext.memory.write` writes the note and its `_meta.json`; a
stage's worker gets its run and stage from the environment; bad provenance
is one line per problem; a namespace reads its own entries and those another
pack shares with its pack (recall's filter too), never one it was not given;
`retention: run` entries go when the run ends, `days:<n>` ones with `halo
recall prune`; `halo recall --namespace ... --provenance` lists them.

Run: python -m tests.test_pack_memory_provenance
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.workflow_rig import StageWorker, WorkflowRig  # noqa: E402

test, TESTS = new_registry()


def _recall(*argv) -> "tuple[int, str]":
    from halo_harness.recall_cli import cmd_recall
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = cmd_recall(list(argv))
    return code, out.getvalue()


@test
def test_write_keeps_the_note_and_its_provenance(ctx: Ctx):
    from halo_harness.ext import memory
    from halo_harness.packs.memory_meta import meta_of
    with PacksHome() as h:
        note = memory.write("doc-review/reviews", "docs/guide.md: a dead link", {"retention": "days:30", "shared": ["release-notes"]},
                            name="guide")
        ctx.check("the note in its namespace folder", note == h.packs / ".data" / "doc-review" / "memory" / "reviews" / "guide.md"
                  and note.read_text(encoding="utf-8") == "docs/guide.md: a dead link")
        meta = json.loads((note.parent / "guide._meta.json").read_text(encoding="utf-8"))
        ctx.check(f"its _meta.json, got {meta}", meta["source"] == "user" and meta["retention"] == "days:30"
                  and meta["shared"] == ["release-notes"] and meta["run"] == "" and meta["written"].endswith("Z"))
        bare = memory.write("doc-review", "the default namespace")
        ctx.check("a bare id is the pack's default namespace", bare.parent.name == "doc-review" and meta_of(bare)["retention"] == "keep")
        old = h.packs / ".data" / "doc-review" / "memory" / "reviews" / "r2.md"
        old.write_text("an R2 note", encoding="utf-8")
        ctx.check("a note without _meta.json is the user's, kept", meta_of(old) == {"source": "user", "retention": "keep", "shared": []})
        for bad, want in ((("Doc Review/x", "t"), "is not a namespace"), (("doc-review/x", "t", {"source": "robot"}), "provenance.source is one of"),
                          (("doc-review/x", "t", {"retention": "forever"}), "provenance.retention is keep, days:<n> or run"),
                          (("doc-review/x", "t", {"retention": "run"}), "needs the run"),
                          (("doc-review/x", "t", {"shared": ["Not An Id"]}), "is not a pack id")):
            try:
                memory.write(*bad)
                why = ""
            except ValueError as e:
                why = str(e)
            ctx.check(f"{bad}: {want!r}, got {why!r}", want in why)


@test
def test_a_stages_worker_gets_its_run_and_stage(ctx: Ctx):
    from halo_harness.ext import memory
    from halo_harness.packs.memory_meta import meta_of
    with WorkflowRig() as w:
        run = w.new_run(w.compile(docs="docs").goal)
        saved = {k: os.environ.get(k) for k in ("HALO_ORCHESTRA_RUN", "HALO_ORCHESTRA_LANE")}
        os.environ.update(HALO_ORCHESTRA_RUN=str(run), HALO_ORCHESTRA_LANE="3")
        try:
            note = memory.write("doc-review/reviews", "keep the dead link finding", {"retention": "run"})
        finally:
            for k, v in saved.items():
                os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        meta = meta_of(note)
        ctx.check(f"workflow run, its run id and stage, got {meta}", meta["source"] == "workflow run" and meta["run"] == run.name
                  and meta["stage"] == "judge" and meta["retention"] == "run")
        kept = memory.write("doc-review/reviews", "keep this one", {"run": run.name})
        report = w.run(run, worker=StageWorker())
        ctx.check("the run ended: its retention-run entry is gone, the rest stay", report["status"] == "finished"
                  and not note.exists() and not note.with_name(note.stem + "._meta.json").exists() and kept.exists())


@test
def test_a_namespace_reads_its_own_and_what_is_shared_with_it(ctx: Ctx):
    from halo_harness.ext import memory
    from halo_harness.packs.memory_meta import readable, visible
    with PacksHome() as h:
        mine = memory.write("doc-review/reviews", "mine")
        shared = memory.write("release-notes/drafts", "for the reviewer", {"shared": ["doc-review"]})
        private = memory.write("release-notes/drafts", "not shared")
        other = memory.write("other-pack/notes", "shared elsewhere", {"shared": ["release-notes"]})
        names = sorted(str(e["path"]) for e in readable("doc-review/reviews"))
        ctx.check(f"own + shared with its pack, got {names}", names == sorted([str(mine), str(shared)]))
        ctx.check("recall's filter agrees", visible(str(mine), "doc-review/reviews") and visible(str(shared), "doc-review/reviews")
                  and not visible(str(private), "doc-review/reviews") and not visible(str(other), "doc-review/reviews"))
        ctx.check("yours (no namespace) still leaves every pack's folder out", not visible(str(shared), None) and not visible(str(mine), None))
        code, out = _recall("--namespace", "doc-review/reviews", "--provenance")
        ctx.check(f"halo recall --namespace --provenance lists both with their meta, got {out!r}", code == 0
                  and mine.stem in out and shared.stem in out and "shared with doc-review" in out and "retention keep" in out)
        code, out = _recall("--namespace", "doc-review/reviews", "--json")
        ctx.check("--json", code == 0 and len(json.loads(out)["entries"]) == 2)
        code, out = _recall("--namespace", "Bad NS")
        ctx.check(f"a bad namespace: 2, got {out!r}", code == 2 and "is not a namespace" in out)


@test
def test_days_retention_goes_with_prune(ctx: Ctx):
    from halo_harness.ext import memory
    from halo_harness.packs.memory_meta import meta_path, prune
    with PacksHome() as h:
        soon = memory.write("doc-review/reviews", "a week", {"retention": "days:7"})
        keep = memory.write("doc-review/reviews", "kept", {"retention": "keep"})
        ctx.check("nothing past its days yet", prune() == [])
        gone = prune(now=time.time() + 8 * 86400)
        ctx.check("eight days on: the days:7 entry goes, keep stays", [e["path"] for e in gone] == [soon] and not soon.exists()
                  and not meta_path(soon).exists() and keep.exists())
        memory.write("doc-review/reviews", "a day", {"retention": "days:0"})
        time.sleep(1.1)
        code, out = _recall("prune")
        ctx.check(f"halo recall prune, got {out!r}", code == 0 and "1 entry past their days removed" in out and "days:0" in out)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
