"""tests.test_workflow_schema -- a pack's workflow file (Halo 3.2.0.0 R5,
schemas/workflow_yaml.py, packs/workflow_rules.py, packs/workflow_stages.py,
packs/typed.py): the doc-review fixture declares every key and validates
clean; the JSON twin lists the same keys; each failure fixture (a stage
cycle, an unknown role, an output nobody gives, an input of the wrong type)
is one manifest line per problem naming the key and its line; every other
meaning is one line; a typo names the closest key; artifact and event
schemas are checked with the manifest; an artifact failing its schema is
one line per problem.

Run: python -m tests.test_workflow_schema
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import DOC_REVIEW, FIXTURES, fixture  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent


def _problems(name: str) -> list:
    from halo_harness.packs.discover import read_pack
    return read_pack(fixture(name), "source").problems


def _variant(edit) -> list:
    """The doc-review pack with its review.yaml text changed by `edit(text) -> text`: the workflow lines."""
    d = Path(tempfile.mkdtemp(prefix="wf-variant-")) / "doc-review"
    shutil.copytree(DOC_REVIEW, d)
    try:
        p = d / "workflows" / "review.yaml"
        p.write_text(edit(p.read_text(encoding="utf-8")), encoding="utf-8")
        from halo_harness.packs.discover import read_pack
        return [ln for ln in read_pack(d, "source").problems if "workflow" in ln]
    finally:
        shutil.rmtree(d.parent, ignore_errors=True)


@test
def test_the_fixture_uses_every_key_and_the_twin_has_them(ctx: Ctx):
    import yaml
    from halo_harness.schemas import workflow_yaml as W
    ctx.check(f"doc-review validates clean, got {_problems('doc-review')}", _problems("doc-review") == [])
    data = yaml.safe_load((DOC_REVIEW / "workflows" / "review.yaml").read_text(encoding="utf-8"))
    ctx.check(f"every top key, got {list(data)}", set(data) == set(W.TOP_KEYS) - {"stop_when"})
    used = {k for s in data["stages"] for k in s}
    ctx.check(f"the stages use every stage key but after_event, got {sorted(used)}", used == set(W.STAGE_KEYS) - {"after_event"})
    schema = json.loads((REPO / "halo_harness" / "packs" / "schema" / "workflow.schema.json").read_text(encoding="utf-8"))
    d = schema["$defs"]
    ctx.check("the twin's top keys", tuple(schema["properties"]) == W.TOP_KEYS)
    ctx.check("its stage keys", tuple(d["stage"]["properties"]) == W.STAGE_KEYS)
    ctx.check("its when, give, take keys", tuple(d["when"]["properties"]) == W.WHEN_KEYS
              and tuple(d["give"]["properties"]) == W.GIVE_KEYS and tuple(d["take"]["properties"]) == W.TAKE_KEYS)
    ctx.check("its input, output, prerequisite keys", tuple(d["input"]["properties"]) == W.INPUT_KEYS
              and tuple(d["output"]["properties"]) == W.OUTPUT_KEYS and tuple(schema["properties"]["prerequisites"]["properties"]) == W.PREREQ_KEYS)
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    ctx.check("the schema ships as package data", '"packs/schema/*.json"' in pyproject)


@test
def test_each_failure_fixture_names_the_key_and_its_line(ctx: Ctx):
    cases = {
        "wf-cycle": ["workflows/flow.yaml line 4: stages.draft.after: draft waits for itself",
                     "workflows/flow.yaml line 8: stages.polish.after: polish waits for itself"],
        "wf-unknown-role": ["workflows/flow.yaml line 6: stages.audit.role 'auditor' is not a bio of the pack"],
        "wf-no-giver": ["workflows/flow.yaml line 4: outputs.notes: no stage gives it -- stage write gives summary (summary)"],
        "wf-input-type": ["workflows/flow.yaml line 4: inputs.docs.default is a path"],
    }
    for name, want in cases.items():
        got = _problems(name)
        ctx.check(f"{name}: {len(want)} line(s), got {got}", len(got) == len(want)
                  and all(g.startswith(w) for g, w in zip(got, want)))


@test
def test_every_meaning_is_one_line(ctx: Ctx):
    cases = [
        (lambda t: t.replace("    retries: 1\n", "    retires: 1\n"), "closest known key: 'retries'"),
        (lambda t: t.replace("after: [read]", "after: [raed]"), "stages.judge.after 'raed' is not a stage"),
        (lambda t: t.replace("{from: read, take: notes}", "{from: read, take: findings}"), "'findings' from read, which gives notes"),
        (lambda t: t.replace("not-empty: true}", "not-empty: true, exists: true}"), "say one of exists, equals, not-empty"),
        (lambda t: t.replace("output: judge.verdict", "output: write.report"), "'write' is not a stage write runs after"),
        (lambda t: t.replace("{input: docs, match: \"*.md\"}", "style"), "'style' is not a path input"),
        (lambda t: t.replace("retries: 2", "retries: -1"), "stages.write.retries -1 is not a number 0 or more"),
        (lambda t: t.replace("gate: human", "gate: maybe"), "'maybe' is human or auto"),
        (lambda t: t.replace("evidence: [report]", "evidence: [reprt]"), "'reprt' is not an output, a give of write"),
        (lambda t: t.replace("needs: [docs.review]", "needs: [docs.lint]"), "'docs.lint' is not a capability the pack declares"),
        (lambda t: t.replace("    retries: 2\n", "    retries: 2\n    after_event: doc-review:review.started\n"),
         "'review.started' is not one of the pack's contributes.events"),
        (lambda t: t.replace('"artifact:review-report"', '"artifact:review-notes"'), "the pack lists no artifact schema 'review-notes'"),
        (lambda t: t.replace("grants: [bash]", "grants: [network]"), "'network' is not a permission the pack requests"),
        (lambda t: t.replace("name: review\n", "name: reviews\n", 1), "'reviews' differs from the file's name"),
        (lambda t: t.replace("style: {type: text,", "style: {type: blob,"), "'blob' is not text, path, json"),
    ]
    for edit, want in cases:
        got = _variant(edit)
        ctx.check(f"{want!r}: one line with a line number, got {got}", len(got) == 1 and want in got[0] and " line " in got[0])


@test
def test_artifact_event_and_panel_schemas_are_checked_with_the_manifest(ctx: Ctx):
    import yaml
    from halo_harness.packs.manifest import validate_manifest
    d = Path(tempfile.mkdtemp(prefix="wf-typed-")) / "doc-review"
    shutil.copytree(DOC_REVIEW, d)
    try:
        data = yaml.safe_load((d / "pack.yaml").read_text(encoding="utf-8"))
        data["contributes"]["artifacts"] = ["review-report", "missing-schema"]
        lines = validate_manifest(data, root=d)
        ctx.check(f"an artifact schema the pack lacks, got {lines}", lines == ["contributes.artifacts[1]: artifacts/missing-schema.json is not in the pack"])
        (d / "events" / "review.done.json").write_text('{"type": "object", "x-halo-view": "chart"}', encoding="utf-8")
        data["contributes"]["artifacts"] = ["review-report"]
        lines = validate_manifest(data, root=d)
        ctx.check(f"a view hint Studio has not got, got {lines}", len(lines) == 1 and "x-halo-view 'chart'" in lines[0])
        (d / "events" / "review.done.json").unlink()
        data["contributes"]["events"] = [{"kind": "review.done", "schema": "events/nope.json"}]
        lines = validate_manifest(data, root=d)
        ctx.check(f"an event entry's schema file, got {lines}", lines == ["contributes.events[0].schema: events/nope.json is not in the pack"])
        data["contributes"]["events"] = ["review.done"]
        panel = data["contributes"]["studio"]["sections"][0]["panels"][3]
        panel["schema"] = "review-notes"
        lines = validate_manifest(data, root=d)
        ctx.check(f"an artifact panel names a schema of the pack, got {lines}", len(lines) == 1 and "schema 'review-notes' is not one of contributes.artifacts" in lines[0])
    finally:
        shutil.rmtree(d.parent, ignore_errors=True)


@test
def test_an_artifact_failing_its_schema_is_a_line_per_problem(ctx: Ctx):
    from halo_harness.packs.typed import artifact_schema, check, view_of
    schema = artifact_schema(DOC_REVIEW, "review-report")
    bad = json.loads((FIXTURES.parent / "workflows" / "report-bad.json").read_text(encoding="utf-8"))
    got = check(bad, schema)
    ctx.check(f"five problems, each its key, got {got}", got == [
        "findings[0].line is a whole number, got the string 'four'",
        "findings[0].severity is one of high, medium, low, got the string 'urgent'",
        "unknown key 'score'; nothing reads it", "findings[1].file is required", "findings[1].finding is required"])
    ctx.check("a good report has none", check({"summary": "ok", "findings": []}, schema) == [])
    ctx.check("its view is table", view_of(schema) == "table" and view_of({}) == "keyvalue")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
