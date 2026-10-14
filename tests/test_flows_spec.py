"""tests.test_flows_spec -- the flow file (Halo 3.0.4.0 round R3): every
`validate_flow` line (errors and warnings), `$.<step>.<path>` references
with quoted keys and indexes, finding a flow (project beats user beats
template), the shipped social-post template validating clean, and the
marketing org built in and installable.
"""

from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once

ensure_scoped_state_dir_once()

from tests.helpers.fake_flow import template_spec  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _lines(data, **kw):
    from halo_harness.flows.spec import validate_flow
    return validate_flow(data, env=kw.pop("env", {}), **kw)


def _has(lines, needle):
    return any(needle in line for line in lines)


@test
def test_template_validates_clean(ctx: Ctx):
    from halo_harness.flows.spec import errors, template_names
    ctx.check("social-post is a shipped template", "social-post" in template_names())
    lines = _lines(template_spec())
    ctx.check(f"the template validates with no lines at all, got {lines}", lines == [])
    ctx.check("errors() of nothing is nothing", errors(lines) == [])


@test
def test_every_error_line(ctx: Ctx):
    ctx.check("not a mapping", _lines([1]) == ["a flow file is a mapping with name, steps, ..."])
    ctx.check("no steps", _has(_lines({"name": "x"}), "steps: a non-empty list"))
    ctx.check("no name", _has(_lines({"steps": [{"id": "d", "kind": "done"}]}), "name: give the flow a name"))
    ctx.check("budget not a number", _has(_lines({"name": "x", "budget_usd": "lots", "steps": [{"id": "d", "kind": "done"}]}),
                                          "budget_usd: a non-negative number"))
    base = template_spec()

    def edit(fn):
        spec = copy.deepcopy(base)
        fn(spec["steps"])
        return _lines(spec)
    ctx.check("unknown kind", _has(edit(lambda s: s[6].update(kind="teleport")), "step measure: unknown kind 'teleport'"))
    ctx.check("duplicate id", _has(edit(lambda s: s[2].update(id="plan")), "step plan: duplicate id"))
    ctx.check("missing id", _has(edit(lambda s: s[7].pop("id")), "step #8: needs an id"))
    ctx.check("a step that is not a mapping", _has(edit(lambda s: s.insert(1, "oops")), "step #2: a mapping with id and kind"))
    ctx.check("a ref to a later step", _has(edit(lambda s: s[1]["inputs"].update(brief="$.render.prompt")),
                                            "step plan: $.render.prompt refers to a later step 'render'"))
    ctx.check("a ref to an unknown step", _has(edit(lambda s: s[1]["inputs"].update(brief="$.nowhere.x")),
                                               "refers to an unknown step 'nowhere'"))
    ctx.check("a bad ref", _has(edit(lambda s: s[1]["inputs"].update(brief="$.intake[oops]")), "neither a quoted key nor an index"))
    ctx.check("a step budget that is not a number", _has(edit(lambda s: s[1].update(budget_usd=-1)),
                                                         "step plan: budget_usd is a non-negative number"))
    ctx.check("a bad form field", _has(edit(lambda s: s[0]["form"].update(age="years")), "form field age: 'years'"))
    ctx.check("an intake without a form", _has(edit(lambda s: s[0].pop("form")), "an intake step has a form"))
    ctx.check("confirm without a render before it", _has(edit(lambda s: s.pop(3)),
                                                         "step approve: a confirm step needs a render step before it"))
    ctx.check("on_fail must name an earlier render", _has(edit(lambda s: s[4].update(on_fail="redo:plan")),
                                                          "on_fail is \"redo:<an earlier render step>\""))
    ctx.check("roles uses lineup:", _has(edit(lambda s: s[1].update(uses="standard")), "a roles step uses \"lineup:<name>\""))
    ctx.check("a lineup that does not resolve", _has(edit(lambda s: s[1].update(uses="lineup:nope")),
                                                     "lineup 'nope' does not resolve (known: "))
    ctx.check("roles needs role names", _has(edit(lambda s: s[1].update(roles=[])), "roles is a non-empty list"))
    ctx.check("org uses org:", _has(edit(lambda s: s[2].update(uses="marketing")), "an org step uses \"org:<name>\""))
    ctx.check("an org load_org cannot find", _has(edit(lambda s: s[2].update(uses="org:ghosts")),
                                                  "org 'ghosts' is not found or does not validate (known: "))
    ctx.check("render uses comfy:", _has(edit(lambda s: s[3].update(uses="text-to-image-qwen")),
                                         "a render step uses \"comfy:<workflow>\""))


@test
def test_warning_lines(ctx: Ctx):
    from halo_harness.flows.spec import errors
    spec = template_spec()
    spec["steps"][3]["uses"] = "comfy:My saved one"
    lines = _lines(spec)
    ctx.check(f"an unknown workflow is a warning, got {lines}", lines and lines[0].startswith("warning: step render: workflow")
              and errors(lines) == [])
    from halo_harness.config.paths import bridge_home
    cache = Path(bridge_home()) / "media-models.json"
    old = cache.read_text(encoding="utf-8") if cache.is_file() else None
    cache.write_text(json.dumps({"scanned": 1, "url": "x", "rows": [], "workflows": ["My saved one.json"]}), encoding="utf-8")
    try:
        ctx.check("a workflow saved in the inventory cache is known", _lines(spec) == [])
    finally:
        cache.unlink() if old is None else cache.write_text(old, encoding="utf-8")
    wf = Path(tempfile.mkdtemp(prefix="flow-wf-")) / "graph.json"
    wf.write_text("{}", encoding="utf-8")
    spec["steps"][3]["uses"] = f"comfy:{wf}"
    ctx.check("a workflow file is known", _lines(spec) == [])
    live = template_spec()
    live["steps"][5]["live"] = True
    ctx.check("live posting without Postiz credentials is a warning",
              _lines(live) == ["warning: step publish: live: true, and neither POSTIZ_API_KEY nor ~/.postiz/credentials.json is set"])
    ctx.check("POSTIZ_API_KEY clears it", _lines(live, env={"POSTIZ_API_KEY": "x"}) == [])
    over = template_spec(budget_usd=1.0)
    lines = _lines(over)
    ctx.check(f"step budgets above the run budget is a warning, got {lines}",
              lines == ["warning: the step budgets add up to $3.50, above the run budget $1.00; the run stops at its own budget"])


@test
def test_refs(ctx: Ctx):
    from halo_harness.flows.refs import parse_ref, refs_in, resolve_ref, resolve_value
    out = {"marketing": {"positions": {"Art Director": {"prompt": "p"}, "Copywriter": {"text": "c"}}},
           "approve": {"accepted": ["a.png", "b.png"]}, "intake": {"brief": "b", "platforms": ["x"]}}
    ctx.check("a quoted key with a space", resolve_ref("$.marketing.positions['Art Director'].prompt", out) == "p")
    ctx.check("a double-quoted key", resolve_ref('$.marketing.positions["Art Director"].prompt', out) == "p")
    ctx.check("dotted keys", resolve_ref("$.marketing.positions.Copywriter.text", out) == "c")
    ctx.check("an index and a negative index", resolve_ref("$.approve.accepted[0]", out) == "a.png"
              and resolve_ref("$.approve.accepted[-1]", out) == "b.png")
    ctx.check("a whole step output", resolve_ref("$.intake", out) == out["intake"])
    ctx.check("parse_ref splits keys and indexes", parse_ref("$.a['b c'][2].d") == ["a", "b c", 2, "d"])
    for bad, want in (("$.approve.accepted[9]", "has no item [9]"), ("$.marketing.positions.Analyst", "has no key 'Analyst'"),
                      ("$.later.x", "step 'later' has no output yet")):
        try:
            resolve_ref(bad, out)
            msg = ""
        except KeyError as e:
            msg = str(e.args[0])
        ctx.check(f"{bad} -> {want!r}, got {msg!r}", want in msg)
    for bad in ("$.", "$.a[", "$.a b", "plain"):
        try:
            parse_ref(bad)
            raised = False
        except ValueError:
            raised = True
        ctx.check(f"{bad!r} is not a reference", raised)
    ctx.check("resolve_value walks dicts and lists", resolve_value({"t": "$.intake.brief", "l": ["$.intake.platforms", 3],
                                                                   "s": "plain"}, out) == {"t": "b", "l": [["x"], 3], "s": "plain"})
    ctx.check("refs_in lists every ref", refs_in({"a": "$.x.y", "b": ["$.z", "no"]}) == ["$.x.y", "$.z"])


@test
def test_find_flow_precedence_and_vars(ctx: Ctx):
    from halo_harness.flows.spec import find_flow, flows_dir, render_vars, step_by_id, template_path
    ctx.check("a template is found by name", find_flow("social-post", cwd=tempfile.mkdtemp()) == template_path("social-post"))
    d = flows_dir()
    d.mkdir(parents=True, exist_ok=True)
    user = d / "social-post.flow.yaml"
    user.write_text("name: social-post\nsteps: [{id: d, kind: done}]\n", encoding="utf-8")
    try:
        ctx.check("the user's flow beats the template", find_flow("social-post", cwd=tempfile.mkdtemp()) == user)
        proj = Path(tempfile.mkdtemp(prefix="flow-proj-"))
        (proj / ".halo").mkdir()
        (proj / ".halo" / "flow.yaml").write_text("name: social-post\nsteps: [{id: d, kind: done}]\n", encoding="utf-8")
        ctx.check("the project's flow beats the user's", find_flow("social-post", cwd=proj) == proj / ".halo" / "flow.yaml")
        ctx.check("a project flow with another name does not", find_flow("other", cwd=proj) is None)
    finally:
        user.unlink()
    ctx.check("{{intake.project}} is filled", render_vars("{{intake.project}}", {"project": "demo"}) == "demo"
              and render_vars("{{ intake.missing }}", {}) == "")
    ctx.check("step_by_id", step_by_id(template_spec(), "render")["kind"] == "render" and step_by_id(template_spec(), "x") is None)


@test
def test_marketing_org_shipped(ctx: Ctx):
    from halo_harness.orgs import _BUILTIN_ORGS, find_position, install_org_template, list_orgs, load_org, validate_org
    org = _BUILTIN_ORGS["marketing"]
    ctx.check("the marketing org validates", validate_org(org) == [])
    ctx.check("it is listed and loads", "marketing" in list_orgs() and load_org("marketing") is not None)
    ad = find_position(org, "Art Director")
    ctx.check("the Art Director needs approval and has the ComfyUI tools",
              ad["requires_approval"] is True and ad["tools"] == ["mcp__comfyui__*", "Read"])
    root = find_position(org, "Strategist")
    ctx.check("the Strategist is the planner root over five positions", root["role"] == "planner"
              and root["reports"] == ["Researcher", "Copywriter", "Art Director", "Publisher", "Analyst"])
    ctx.check("the Publisher posts through postiz", find_position(org, "Publisher")["tools"] == ["Bash(postiz:*)"])
    ctx.check("the org budget is $3.00 and every position has one", org["budget_usd"] == 3.0
              and all(isinstance(p.get("budget_usd"), float) for p in org["positions"]))
    ok, problems = install_org_template("marketing", force=True)
    ctx.check(f"halo org install marketing works, got {problems}", ok)
    ctx.check("the template file ships beside the package", (Path(__file__).resolve().parent.parent / "halo_harness"
              / "templates" / "orgs" / "marketing.json").is_file())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="flow spec tests"))
