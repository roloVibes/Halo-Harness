"""tests.test_flows_graph -- Halo 3.0.9.0 round R2: a saved flow as a graph
(flows/graph.py) and its one write route, `PUT flow/templates/<name>`
(studio/flow_api_edit.py).

1. The social-post template's steps in dependency layers (from their
   `$.<step>` refs; the confirm step after its render, metrics after the
   post, done last), the confirm step marked as the gate.
2. Two steps that read only the intake share a layer; `reorder` swaps them
   in the file text, comments kept, every other line as it was.
3. The route: an order change of a user flow is written; one that makes a
   step read a later one is a 422 and nothing changes; a shipped template is
   copied to the user's flows first (Halo's own file never changes); bad
   YAML, a missing body, an unknown flow.

Run: python -m tests.test_flows_graph
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

ensure_scoped_state_dir_once()
test, TESTS = new_registry()

TWO = """# a flow with two independent steps
name: two-ways
steps:
  - id: intake
    kind: intake
    form: {brief: text}
  - id: plan          # the planner reads the brief
    kind: roles
    uses: lineup:standard
    roles: [planner]
    inputs: {brief: "$.intake.brief"}
  - id: research
    kind: roles
    uses: lineup:standard
    roles: [researcher]
    inputs: {brief: "$.intake.brief"}
  - id: done
    kind: done
"""


@test
def test_social_post_in_layers_with_its_gate(ctx: Ctx):
    from halo_harness.flows import spec
    from halo_harness.flows.graph import graph_rows
    rows = graph_rows(spec.load_flow(spec.template_path("social-post")))
    ctx.check(f"eight steps in file order, got {[r['id'] for r in rows]}",
              [r["id"] for r in rows] == ["intake", "plan", "marketing", "render", "approve", "publish", "measure", "done"])
    ctx.check(f"one layer each, got {[r['layer'] for r in rows]}", [r["layer"] for r in rows] == list(range(8)))
    by = {r["id"]: r for r in rows}
    ctx.check(f"refs make the edges, got {by['marketing']['deps']} {by['publish']['deps']}",
              by["marketing"]["deps"] == ["plan", "intake"] and by["publish"]["deps"] == ["marketing", "approve", "intake"])
    ctx.check("approve confirms the render and is the gate; measure samples the post",
              by["approve"]["deps"] == ["render"] and by["approve"]["gate"] is True and by["measure"]["deps"] == ["publish"]
              and [r["id"] for r in rows if r["gate"]] == ["approve"])


@test
def test_independent_steps_share_a_layer_and_reorder_keeps_the_text(ctx: Ctx):
    import yaml
    from halo_harness.flows.graph import graph_rows, reorder
    rows = graph_rows(yaml.safe_load(TWO))
    ctx.check(f"plan and research share layer 1, got {[(r['id'], r['layer']) for r in rows]}",
              [r["layer"] for r in rows] == [0, 1, 1, 2])
    text = reorder(TWO, ["intake", "research", "plan", "done"])
    ctx.check("the steps swap", [s["id"] for s in yaml.safe_load(text)["steps"]] == ["intake", "research", "plan", "done"])
    ctx.check("every line kept, the comments too", sorted(text.splitlines()) == sorted(TWO.splitlines())
              and "  - id: plan          # the planner reads the brief" in text and text.startswith("# a flow with"))
    try:
        reorder(TWO, ["intake", "plan"])
        ctx.check("a partial order is refused", False)
    except ValueError as e:
        ctx.check(f"a partial order is refused, got {e}", "every step once" in str(e))


@test
def test_the_put_route_writes_the_new_order(ctx: Ctx):
    from halo_harness.flows import spec
    from tests.helpers.flow_studio_rig import FlowStudio
    with FlowStudio() as s:
        flows = s.state / "flows"
        flows.mkdir(parents=True, exist_ok=True)
        path = flows / "two-ways.flow.yaml"
        path.write_text(TWO, encoding="utf-8")
        st, ok = s.call("PUT", "flow/templates/two-ways", {"order": ["intake", "research", "plan", "done"]})
        ctx.check(f"200 with the new steps, got {st} {ok}", st == 200 and ok["source"] == "user"
                  and [r["id"] for r in ok["steps"]] == ["intake", "research", "plan", "done"])
        ctx.check("the file has the new order", path.read_text(encoding="utf-8").index("id: research") < path.read_text(encoding="utf-8").index("id: plan"))
        row = next(r for r in s.get("flow/templates")[1] if r["name"] == "two-ways")
        ctx.check("GET flow/templates reads it back", [st_["id"] for st_ in row["steps"]] == ["intake", "research", "plan", "done"])
        before = path.read_text(encoding="utf-8")
        st, err = s.call("PUT", "flow/templates/two-ways", {"order": ["plan", "intake", "research", "done"]})
        ctx.check(f"a step reading a later one is a 422, got {st} {err}", st == 422 and "refers to a later step" in err["error"]
                  and path.read_text(encoding="utf-8") == before)
        shipped = spec.template_path("social-post")
        original = shipped.read_bytes()
        order = ["intake", "plan", "marketing", "render", "approve", "measure", "publish", "done"]
        st, ok = s.call("PUT", "flow/templates/social-post", {"order": order})
        user = flows / "social-post.flow.yaml"
        ctx.check(f"a shipped template is copied to the user's flows, got {st} {ok.get('path')}", st == 200
                  and Path(ok["path"]) == user and shipped.read_bytes() == original and user.is_file())
        ctx.check("bad YAML is a 422", s.call("PUT", "flow/templates/two-ways", {"yaml": "name: [unclosed"})[0] == 422)
        ctx.check("a renamed flow is a 422", s.call("PUT", "flow/templates/two-ways", {"yaml": TWO.replace("two-ways", "other")})[0] == 422)
        ctx.check("no body is a 422", s.call("PUT", "flow/templates/two-ways", {})[0] == 422)
        ctx.check("an unknown flow is a 404", s.call("PUT", "flow/templates/nope", {"order": []})[0] == 404)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="flow graph tests"))
