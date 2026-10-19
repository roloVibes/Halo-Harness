"""tests.test_review3_c3 -- pins for the 3.0.2.0 review fix pass, round
C-studio-tools, part 3: Studio's lineup graph (item 38, the Paperclip
install, went with Paperclip in 3.1.4.0).

  * item 37   a hand-edited lineup or bio opens, with the validator's words
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.test_review3_c import _Studio  # noqa: E402  (scopes the state dir the same way)
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


@test
def test_item37_a_hand_edited_lineup_still_opens(ctx: Ctx):
    from halo_harness import agents_yaml as A
    from halo_harness.studio import model as M
    raw = {"name": "handy", "agents": [
        {"agent": "orchestrator", "role": "main", "instances": "two", "use_for": "review"},
        {"agent": "reviewer", "role": "reviewer", "instances": True},
        {"agent": "implementer", "role": "subagent", "instances": 0},
        {"agent": "orchestrator", "role": "subagent", "instances": 3, "use_for": ["a", "b"]},
    ]}
    nodes = M.graph_for(raw, catalog={})["nodes"]
    ctx.check("a non-integer / bool / zero instances is 1 with the validator's sentence",
              [n["instances"] for n in nodes[:3]] == [1, 1, 1] and all('"instances" must be a positive integer' in n["problems"] for n in nodes[:3]))
    ctx.check("a good count is kept and not flagged", nodes[3]["instances"] == 3 and not any("instances" in p for p in nodes[3]["problems"]))
    ctx.check("use_for counts only as a list (a string is not split into characters)", nodes[0]["use_for"] == [] and nodes[3]["use_for"] == ["a", "b"])
    real = A.resolve_agent_bio
    A.resolve_agent_bio = lambda name, **kw: {"tools": ["Read", "Write"], "models": ["x"], "_source": "user", "kind": "main"}
    try:
        n = M.graph_for({"name": "t", "agents": [{"agent": "odd", "role": "main"}]}, catalog={})["nodes"][0]
    finally:
        A.resolve_agent_bio = real
    ctx.check("a bio spelling tools as a list does not raise; the node shows 0 tools", n["tools"] == 0 and n["model"] == "")


@test
def test_item37_the_lineup_route_answers_200_with_problems(ctx: Ctx):
    import urllib.request
    with _Studio() as s:
        teams = s.state / "teams"
        teams.mkdir(parents=True, exist_ok=True)
        (teams / "handy.yaml").write_text("name: handy\nagents:\n  - agent: orchestrator\n    role: main\n    instances: two\n", encoding="utf-8")
        req = urllib.request.Request(f"http://127.0.0.1:{s.port}/api/lineup/handy", headers={"Authorization": "Bearer " + s.srv.token})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        ctx.check("GET /api/lineup/handy is a 200 with a graph", r.status == 200 and len(data["graph"]["nodes"]) == 1)
        ctx.check(f"the validator's line is in problems, got {data['problems']}", any("instances" in p for p in data["problems"]))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="review3 c3 tests"))
