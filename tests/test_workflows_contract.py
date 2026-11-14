"""tests.test_workflows_contract -- a square is a workflow with a contract (Halo 3.3.16.0 R3,
workflows/contract.py, schemas/workflow_yaml.py, packs/workflow_rules.py): `gives` is required once a file
says any other contract key; `covers` / `takes` / `gives` words are the known ones; the root `takes` is
words while a stage's `takes` stays its hand-offs (and a hand-off written at the root says where it
belongs); engine, band and limits are checked; old files (no contract) still load and validate clean; the
JSON twin lists the keys; a pack's bad contract is a manifest line naming the key and its line. No model call.

Run: python -m tests.test_workflows_contract
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import DOC_REVIEW  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
SQUARE = {"name": "x", "does": "Reads PDFs.", "takes": ["text", "pdf"], "gives": ["text"], "covers": ["pdf"],
          "lineup": {"lead": {"bio": "auto-media", "model": "auto"}}, "engine": "session",
          "budget": {"band": "low", "cap_usd": 1}, "limits": {"depth": 1, "turns": 10, "wall_s": 60},
          "stages": [{"id": "look", "takes": [{"from": "a", "take": "summary"}]}]}


@test
def test_a_full_square_reads_and_has_no_problem(ctx: Ctx):
    from halo_harness.workflows.contract import problems, read
    c = read(SQUARE)
    ctx.check(f"no problem, got {problems(SQUARE)}", problems(SQUARE) == [])
    ctx.check("a square", c.square and c.engine == "session" and c.band == "low" and c.cap_usd == 1.0)
    ctx.check(f"the lead, got {c.lead()}", c.lead() == ("auto-media", "auto"))
    ctx.check(f"the limits chip, got {c.limits_chip()!r}", c.limits_chip() == "depth 1 · 10 turns · 60 s")
    ctx.check(f"the contract line, got {c.line('x')!r}", c.line("x") == "x · Reads PDFs. · text,pdf -> text · low · depth 1")


@test
def test_the_defaults_and_the_description_alias(ctx: Ctx):
    from halo_harness.workflows.contract import read
    c = read({"name": "old", "description": "An old workflow.", "stages": [{"id": "a"}]})
    ctx.check("does falls back to description", c.does == "An old workflow.")
    ctx.check("not a square without gives", not c.square)
    ctx.check(f"defaults: orchestra, mid, depth 1, got {c.engine} {c.band} {c.depth}", (c.engine, c.band, c.depth) == ("orchestra", "mid", 1))
    ctx.check("mission runs as orchestra", read({"engine": "mission"}).run_engine() == "orchestra")


@test
def test_gives_is_required_once_the_file_is_a_square(ctx: Ctx):
    from halo_harness.workflows.contract import problems
    got = problems({"covers": ["pdf"], "engine": "session"})
    ctx.check(f"one gives line, got {got}", any(p.startswith("gives: a square says what it gives") for p in got))
    ctx.check("a plain workflow (no contract key) has none", problems({"name": "p", "description": "d"}) == [])


@test
def test_the_words_are_known(ctx: Ctx):
    from halo_harness.workflows.contract import problems
    got = problems({"gives": ["text", "essay"], "covers": ["pdfs"], "takes": ["text", "smell"]})
    ctx.check(f"each unknown word one line, got {got}",
              "gives 'essay' is not a kind a square gives (text, files, report, repo-change)" in got
              and any(p.startswith("covers 'pdfs' is not a need a square covers (pdf, vision") for p in got)
              and any(p.startswith("takes 'smell' is not a kind a square takes") for p in got))
    got = problems({"gives": ["text"], "engine": "cloud", "budget": {"band": "max", "cap_usd": -1},
                    "limits": {"depth": -1, "turns": 0}, "lineup": {"members": []}})
    for want in ("engine 'cloud' is not session, orchestra or mission", "budget.band 'max' is not low, mid or high",
                 "budget.cap_usd is dollars, 0 or more", "limits.depth is a whole number, 0 or more",
                 "limits.turns is a whole number, 1 or more"):
        ctx.check(f"{want!r} in {got}", want in got)
    ctx.check("a lineup object names its lead", any(p.startswith("lineup.lead: a square's lineup names its lead") for p in got))


@test
def test_root_takes_are_words_and_a_stage_takes_stay_hand_offs(ctx: Ctx):
    from halo_harness.workflows.contract import problems
    ctx.check("the stage's [{from, take}] is no contract problem", problems(SQUARE) == [])
    got = problems({"gives": ["text"], "takes": [{"from": "a", "take": "summary"}]})
    ctx.check(f"a hand-off at the root says where it belongs, got {got}",
              any("at the root is what the square accepts" in p and "belongs on a stage" in p for p in got))


@test
def test_the_schema_and_its_twin_list_the_square_keys(ctx: Ctx):
    from halo_harness.schemas import workflow_yaml as W
    ctx.check("the square keys are top keys", set(W.SQUARE_KEYS) <= set(W.TOP_KEYS))
    schema = json.loads((REPO / "halo_harness" / "packs" / "schema" / "workflow.schema.json").read_text(encoding="utf-8"))
    ctx.check("the twin's top keys", tuple(schema["properties"]) == W.TOP_KEYS)
    ctx.check("the twin's covers words", schema["properties"]["covers"]["items"]["enum"]
              == ["pdf", "vision", "audio", "video", "code", "plan", "research", "media", "review", "work-data"])


def _pack_lines(edit) -> list:
    d = Path(tempfile.mkdtemp(prefix="wf-contract-")) / "doc-review"
    shutil.copytree(DOC_REVIEW, d)
    try:
        p = d / "workflows" / "review.yaml"
        p.write_text(edit(p.read_text(encoding="utf-8")), encoding="utf-8")
        from halo_harness.packs.discover import read_pack
        return [ln for ln in read_pack(d, "source").problems if "workflow" in ln]
    finally:
        shutil.rmtree(d.parent, ignore_errors=True)


@test
def test_old_files_load_and_a_packs_bad_contract_is_a_manifest_line(ctx: Ctx):
    ctx.check("doc-review (no contract) validates clean", _pack_lines(lambda t: t) == [])
    got = _pack_lines(lambda t: t + "\ngives: [text]\ncovers: [pdfs]\n")
    ctx.check(f"the covers word named with its file and line, got {got}",
              any(ln.startswith("workflows/review.yaml line") and "covers 'pdfs' is not a need a square covers" in ln for ln in got))
    got = _pack_lines(lambda t: t + "\ncovers: [review]\ngives: [text]\nengine: session\n")
    ctx.check(f"a good contract adds nothing, got {got}", got == [])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
