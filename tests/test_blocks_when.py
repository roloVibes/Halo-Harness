"""tests.test_blocks_when -- the "when" a block's line carries (Halo 3.3.16.3 "Blocks", workflows/when.py,
when_route.py, router.py, when_store.py, tools/workflow.py): a lineup's `workflows:` item `{ref, when: {needs, words,
mode}}` beside plain refs. needs narrow what a square covers; words fire on what the task says; `named` only by name;
`always` first; `off` never; a plain ref keeps today's rule and today's reason; the receipt's reason names the rule
that fired; the auto lineup keeps its rules in config `workflows.when`, a lineup of yours in its items (a plain item
stays plain, a rule survives enable / disable of another square); the CLI's `--when` and `halo workflows when`; the
Workflow tool's description says each rule. Fakes only, no model call.
Run: python -m tests.test_blocks_when
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def squares(h, *names):
    from halo_harness.workflows.spec import find
    return [find(n, cwd=h.repo)[0] for n in names]


def rules(**kw):
    from halo_harness.workflows.when import read
    return {k: read(v) for k, v in kw.items()}


@test
def test_the_rule_reads_labels_and_parses(ctx: Ctx):
    from halo_harness.workflows import when as W
    r = W.read({"ref": "media", "when": {"needs": ["pdf", "images"], "words": "scan, Fax"}})
    ctx.check(f"images reads as vision, words lower, got {r}", r.needs == ["pdf", "vision"] and r.words == ["scan", "fax"] and r.mode == "auto")
    ctx.check("a plain ref has no rule", W.read("media") is None and W.read({"ref": "media"}) is None)
    ctx.check(f"labels, got {W.label(r)!r}", W.label(r) == "needs pdf, images · says scan, fax")
    ctx.check("the plain label is its covers", W.label(None, ["pdf", "vision", "media"]) == "needs pdf, images")
    ctx.check("named / always / off", [W.label(W.read({"mode": m})) for m in ("named", "always", "off")] == ["by name only", "always first", "not connected"])
    ctx.check(f"a sentence, got {W.sentence(r, 'media')!r}",
              W.sentence(W.read({"needs": ["pdf", "audio"]}), "media") == "main hands media work when it needs a PDF or audio")
    ctx.check("parse needs / words / modes", W.parse("needs=pdf,audio") == ({"needs": ["pdf", "audio"]}, "")
              and W.parse("words=review,audit")[0] == {"words": ["review", "audit"]} and W.parse("always") == ({"mode": "always"}, "")
              and W.parse("auto") == ({}, ""))
    ctx.check(f"a bad need is one line, got {W.parse('needs=smell')}", W.parse("needs=smell")[0] is None and "smell" in W.parse("needs=smell")[1])
    ctx.check("problems name a bad mode", any("mode" in p for p in W.problems({"mode": "sometimes"})))


@test
def test_needs_narrow_and_the_reason_names_the_rule(ctx: Ctx):
    from halo_harness.workflows import receipts, router
    with PacksHome() as h:
        on = squares(h, "media", "review")
        plain = router.route("summarize report.pdf", ["report.pdf"], squares=on, takes=["text"])
        ctx.check(f"a plain ref keeps today's reason, got {plain.why!r}",
                  plain.square.ref == "media" and plain.why == "handing the PDF to media: your model takes text only" and plain.rule == "")
        r = router.route("summarize report.pdf", ["report.pdf"], squares=on, takes=["text"], rules=rules(media={"needs": ["pdf"]}))
        ctx.check(f"the reason names the rule, got {r.why!r}", r.why == "handing the PDF to media: when main needs pdf" and r.rule == "when main needs pdf")
        out = type("O", (), {"status": "done", "gives_miss": "", "stop": "", "cost_usd": 0.0, "run_id": "", "model": ""})()
        rec = receipts.make(r, out, files=["report.pdf"])
        ctx.check(f"the receipt carries the rule, got {rec.get('rule')!r}", rec["rule"] == "when main needs pdf" and "when main needs pdf" in receipts.line(rec))
        r = router.route("describe shot.png", ["shot.png"], squares=on, takes=["text"], rules=rules(media={"needs": ["pdf"]}))
        ctx.check(f"needs narrowed to pdf: an image finds no square, got {r.why!r}", r.refused and r.square is None)


@test
def test_words_named_always_off(ctx: Ctx):
    from halo_harness.workflows import router
    with PacksHome() as h:
        on = squares(h, "media", "review", "plan")
        r = router.route("give the parser an audit", (), squares=on, takes=["text"], rules=rules(review={"words": ["audit"]}))
        ctx.check(f"words fire, got {r.why!r}", r.square.ref == "review" and r.why == 'handing the task to review: when the task says "audit"')
        r = router.route("plan the move", (), squares=on, takes=["text"], rules=rules(plan={"mode": "named"}))
        ctx.check(f"named is never picked by need, got {r.square.ref if r.square else r.why!r}", r.square is None or r.square.ref != "plan")
        r = router.route("anything", (), name="plan", squares=on, takes=["text"], rules=rules(plan={"mode": "named"}))
        ctx.check(f"named by name works, got {r.why!r}", r.square.ref == "plan" and r.why == "handing the task to plan: asked for by name")
        r = router.route("say hello", (), squares=on, takes=["text"], rules=rules(plan={"mode": "always"}))
        ctx.check(f"always first takes a task with no need, got {r.why!r}", r.square.ref == "plan" and r.rule == "always first")
        r = router.route("read a.pdf", (), need="pdf", squares=on, takes=["text"], rules=rules(plan={"mode": "always"}))
        ctx.check(f"a need given goes by the need, got {r.square.ref}", r.square.ref == "media")
        r = router.route("read a.pdf", ["a.pdf"], squares=on, takes=["text"], rules=rules(media={"mode": "off"}))
        ctx.check(f"off is never picked, got {r.why!r}", r.square is None and r.refused)
        r = router.route("x", (), name="media", squares=on, takes=["text"], rules=rules(media={"mode": "off"}))
        ctx.check(f"off by name says not connected, got {r.why!r}", r.refused and "not connected" in r.why)


def cli(*argv) -> "tuple[int, str]":
    from halo_harness.workflows.squares_cli import cmd_workflows
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        code = cmd_workflows(list(argv))
    return code, buf.getvalue()


@test
def test_the_auto_lineup_keeps_rules_in_config(ctx: Ctx):
    from halo_harness.workflows.when_store import rules_for
    with PacksHome() as h:
        code, out = cli("enable", "media", "--when", "needs=pdf,audio", "--repo", str(h.repo))
        ctx.check(f"enable --when, got {code} {out!r}", code == 0 and "media on the auto lineup: when needs pdf, audio" in out)
        conf = json.loads((h.state / "config.json").read_text(encoding="utf-8"))
        ctx.check(f"config workflows.when, got {conf.get('workflows')}", conf["workflows"]["when"] == {"media": {"needs": ["pdf", "audio"]}})
        code, out = cli("when", "media", "--repo", str(h.repo))
        ctx.check(f"halo workflows when, got {out!r}", code == 0 and "main hands media work when it needs a PDF or audio" in out)
        code, out = cli("list", "--repo", str(h.repo))
        ctx.check(f"list has the when column, got {out!r}", "when: needs pdf, audio" in out)
        ctx.check("rules_for reads it", rules_for(None, cwd=h.repo)["media"].needs == ["pdf", "audio"])
        code, out = cli("disable", "media", "--repo", str(h.repo))
        conf = json.loads((h.state / "config.json").read_text(encoding="utf-8"))
        ctx.check(f"disable forgets the rule, got {conf['workflows']}", conf["workflows"].get("when") == {})
        code, out = cli("enable", "media", "--when", "needs=smell", "--repo", str(h.repo))
        ctx.check(f"a bad rule is exit 2, got {code} {out!r}", code == 2 and "smell" in out)


@test
def test_a_lineup_of_yours_keeps_rules_in_its_items(ctx: Ctx):
    from halo_harness.agents_yaml import _read_yaml_file
    from halo_harness.teams_yaml import validate_team_template
    from halo_harness.workflows import registry
    from halo_harness.workflows.when_store import set_rule
    with PacksHome() as h:
        h.write(".halo/teams/mine.yaml", "name: mine\nagents:\n  - {agent: default-model, role: main}\nworkflows: [media]\n")
        ok, line = set_rule("media", {"words": ["scan"]}, "mine", cwd=h.repo)
        ok2, _ = registry.enable("review", "mine", cwd=h.repo)
        raw = _read_yaml_file(h.state / "teams" / "mine.yaml")
        ctx.check(f"the rule in the item, a plain one stays plain, got {raw.get('workflows')}",
                  ok and ok2 and raw["workflows"] == [{"ref": "media", "when": {"words": ["scan"]}}, "review"])
        ctx.check("enabled_refs reads both", registry.enabled_refs("mine", cwd=h.repo) == ["media", "review"])
        ctx.check(f"the lineup validates, got {validate_team_template(raw, cwd=h.repo)}", not [p for p in validate_team_template(raw, cwd=h.repo) if "workflows" in p])
        registry.disable("review", "mine", cwd=h.repo)
        raw = _read_yaml_file(h.state / "teams" / "mine.yaml")
        ctx.check(f"disabling another keeps the rule, got {raw['workflows']}", raw["workflows"] == [{"ref": "media", "when": {"words": ["scan"]}}])
        ok, _ = set_rule("media", {}, "mine", cwd=h.repo)
        raw = _read_yaml_file(h.state / "teams" / "mine.yaml")
        ctx.check(f"the plain rule writes a plain ref back, got {raw['workflows']}", raw["workflows"] == ["media"])
        bad = validate_team_template({**raw, "workflows": [{"ref": "media", "when": {"mode": "often"}}]}, cwd=h.repo)
        ctx.check(f"a bad rule is a problem line, got {bad}", any("when.mode" in p for p in bad))
        ok, line = set_rule("plan", {"mode": "named"}, "mine", cwd=h.repo)
        ctx.check(f"a square not on the board says enable it first, got {line!r}", not ok and "enable it first" in line)


@test
def test_the_tool_description_says_each_rule(ctx: Ctx):
    from halo_harness.workflows.when_tool import has_reach, squares_tail
    with PacksHome() as h:
        on = squares(h, "media", "review", "plan")
        ctx.check("no rules: today's words", squares_tail(on[:1], {}) == " Enabled squares: media (covers pdf, vision, audio, video, media).")
        tail = squares_tail(on, rules(review={"words": ["audit"]}, plan={"mode": "always"}, media={"mode": "off"}))
        ctx.check(f"each rule said, off left out, got {tail!r}",
                  "review (when the task says audit)" in tail and "plan (always first" in tail and "media" not in tail)
        ctx.check("always and words reach whatever the model takes", has_reach(rules(plan={"mode": "always"})) and not has_reach(rules(media={"needs": ["pdf"]})))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
