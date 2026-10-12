"""tests.test_studio_model -- the graph Studio draws (Halo 2.1.0 round B3):
built from the same resolve functions the CLI uses, lossless YAML round
trips for every shipped lineup and bio, routing labels on delegation
edges, org and pipeline edges, problems and warnings on the nodes, the
session reader over a synthetic session directory, and `halo studio
--help` reachable from the CLI.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent


@test
def test_yaml_round_trip_is_lossless_for_every_shipped_file(ctx: Ctx):
    from halo_harness import agents_yaml as A
    from halo_harness import teams_yaml as T
    from halo_harness.studio import model as M
    for name in T.list_bundled_team_templates():
        raw = T.load_team_template_raw(name)
        back = M.from_yaml(M.to_yaml(raw))
        ctx.check(f"lineup {name} survives to_yaml/from_yaml", back == M.clean(raw))
    for name in A.list_bundled_agent_templates():
        raw = A.load_agent_bio_raw(name)
        back = M.from_yaml(M.to_yaml(raw))
        ctx.check(f"bio {name} survives to_yaml/from_yaml", back == M.clean(raw))
    ctx.check("from_yaml refuses a non-mapping", _raises(lambda: M.from_yaml("- a\n")))


def _raises(fn) -> bool:
    try:
        fn()
    except Exception:
        return True
    return False


@test
def test_graph_edges_and_diagnostics(ctx: Ctx):
    from halo_harness.studio import model as M
    raw = {
        "name": "g", "agents": [
            {"agent": "orchestrator", "role": "main", "as": "boss"},
            {"agent": "implementer", "role": "subagent", "as": "worker"},
            {"agent": "reviewer", "role": "reviewer", "as": "review"},
            {"agent": "missing-bio", "role": "custom", "as": "review"},
        ],
        "routing": {"implement": "worker", "fix": "worker", "review": "review"},
        "org": {"positions": [{"title": "Boss", "agent": "orchestrator"}, {"title": "Worker", "agent": "implementer", "reports_to": "Boss"}]},
        "pipeline": {"stages": [{"name": "implement", "role": "worker"}, {"name": "review", "role": "review"}]},
    }
    g = M.graph_for(raw, catalog={})
    nodes = {n["alias"]: n for n in g["nodes"]}
    ctx.check("one node per assignment with stable ids", len(g["nodes"]) == 4 and g["nodes"][0]["id"] == "boss#0")
    ctx.check("delegation edges from main carry the routing keys that reach each member",
              any(e["kind"] == "delegation" and e["to"] == "worker#1" and e["label"] == "implement, fix" for e in g["edges"]))
    ctx.check("an org reports_to becomes a reports edge", any(e["kind"] == "reports" and e["from"] == "worker#1" and e["to"] == "boss#0" for e in g["edges"]))
    ctx.check("pipeline stages become ordered pipeline edges", any(e["kind"] == "pipeline" and e["from"] == "worker#1" and e["to"] == "review#2" for e in g["edges"]))
    ctx.check("a missing bio is a node problem", any("not found" in p for p in g["nodes"][3]["problems"]))
    ctx.check("a duplicate alias is a warning on the second node", any("twice" in w for w in g["nodes"][3]["warnings"]))
    ctx.check("the main node resolves the bio's own model", nodes["boss"]["model"] and nodes["boss"]["kind"] == "main")
    two_mains = {"name": "m", "agents": [{"agent": "orchestrator", "role": "main"}, {"agent": "reviewer", "role": "main"}]}
    ctx.check("two mains warn on every node", all(any("role main" in w for w in n["warnings"]) for n in M.graph_for(two_mains, catalog={})["nodes"]))
    override = {"name": "o", "agents": [{"agent": "reviewer", "role": "main", "models": {"preference": "or:x/y"}}]}
    ctx.check("a per-assignment override wins over the bio", M.graph_for(override, catalog={"or:x/y": {"price": "$1/M", "context": "1M"}})["nodes"][0]["model"] == "or:x/y")


@test
def test_session_reader_over_a_synthetic_session(ctx: Ctx):
    from halo_harness.providers.config import default_state_dir
    from halo_harness.studio import model as M
    state = Path(default_state_dir())
    sess = state / "sessions" / "proj-slug"
    sess.mkdir(parents=True, exist_ok=True)
    log = sess / "abc123.jsonl"
    log.write_text("\n".join(json.dumps(n) for n in [
        {"type": "meta", "ts": 1, "seq": 0},
        {"type": "usage", "ts": 2, "seq": 1, "cost_usd": 0.5, "role": "main"},
        {"type": "usage", "ts": 3, "seq": 2, "cost_usd": 0.25, "role": "reviewer", "agent_id": "a1"},
    ]) + "\n", encoding="utf-8")
    sub = sess / "abc123" / "subagents"
    sub.mkdir(parents=True, exist_ok=True)
    (sub / "agent-a1.meta.json").write_text(json.dumps({"agent_id": "a1", "status": "running", "description": "review it", "role": "reviewer"}), encoding="utf-8")
    (sub / "agent-a1" / "subagents").mkdir(parents=True, exist_ok=True)
    (sub / "agent-a1" / "subagents" / "agent-a2.meta.json").write_text(json.dumps({"agent_id": "a2", "status": "completed"}), encoding="utf-8")
    s = M.session_payload(state)
    ctx.check("the newest session is read and reports running", s["running"] is True and s["session_id"] == "abc123")
    ctx.check("sub-agents are listed in tree order with depth and cost",
              [a["agent_id"] for a in s["agents"]] == ["a1", "a2"] and s["agents"][0]["depth"] == 0 and s["agents"][1]["depth"] == 1
              and s["agents"][0]["cost_usd"] == 0.25)
    ctx.check("per-role cost is summed", s["roles"] == {"main": 0.5, "reviewer": 0.25})
    ctx.check("layouts round-trip", (M.write_layout(state, "x", {"a": {"x": 1, "y": 2}}) or M.read_layout(state, "x")) == {"a": {"x": 1, "y": 2}})
    import shutil
    shutil.rmtree(sess, ignore_errors=True)  # leave no "running" session behind for the next module


@test
def test_cli_reaches_studio(ctx: Ctx):
    import os
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HALO_", "OPENROUTER_", "DATABRICKS_", "ANTHROPIC_"))}
    env["PYTHONPATH"] = str(REPO)
    r = subprocess.run([sys.executable, "-m", "halo_harness", "studio", "--help"], capture_output=True, text=True, timeout=60, env=env, cwd=str(REPO))
    ctx.check(f"halo studio --help prints its usage, got {r.stdout[:80]!r}", r.returncode == 0 and "--no-open" in r.stdout and "--port" in r.stdout)
    from halo_harness.completion_cli import SUBCOMMANDS
    ctx.check("studio is a completion word", "studio" in SUBCOMMANDS)
    text = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    ctx.check("the static page ships as package data", "studio/static/*.html" in text and "studio/static/*.js" in text and "studio/static/*.css" in text)


@test
def test_reports_to_connects_a_box_to_another_box(ctx: Ctx):
    """3.0.2.0: a member with org.positions[].reports_to hangs off that
    member's card instead of main; titles resolve by alias, role or agent."""
    from halo_harness.studio.model import graph_for
    raw = {"name": "t", "agents": [{"agent": "orchestrator", "role": "main", "as": "boss"},
                                   {"agent": "implementer", "role": "subagent", "as": "worker"},
                                   {"agent": "verifier", "role": "reviewer", "as": "tester"}],
           "org": {"positions": [{"title": "tester", "agent": "verifier", "reports_to": "worker"}]}}
    g = graph_for(raw, catalog={})
    ids = {n["alias"]: n["id"] for n in g["nodes"]}
    kinds = {(e["from"], e["to"]): e["kind"] for e in g["edges"]}
    ctx.check(f"worker still hangs off main, got {kinds}", kinds.get((ids["boss"], ids["worker"])) == "delegation")
    ctx.check("tester hangs off worker (a reports edge), not main", kinds.get((ids["tester"], ids["worker"])) == "reports" and (ids["boss"], ids["tester"]) not in kinds)
    raw["org"]["positions"][0]["reports_to"] = "boss"
    g2 = graph_for(raw, catalog={})
    kinds2 = {(e["from"], e["to"]): e["kind"] for e in g2["edges"]}
    ctx.check("reporting to the main box keeps the delegation edge from main", kinds2.get((ids["boss"], ids["tester"])) == "delegation" and kinds2.get((ids["tester"], ids["boss"])) == "reports")
    from pathlib import Path as _P
    REPO_DIR = _P(__file__).resolve().parent.parent
    js = (REPO_DIR / "halo_harness" / "studio" / "static" / "app.js").read_text(encoding="utf-8")
    ins = (REPO_DIR / "halo_harness" / "studio" / "static" / "inspector.js").read_text(encoding="utf-8")
    ctx.check("the page connects by drop and by a Reports-to field", "app.setReportsTo" in js and "rolesDropOn" in js and "Reports to (which box" in ins)
    canvas = (REPO_DIR / "halo_harness" / "studio" / "static" / "canvas.js").read_text(encoding="utf-8")
    ctx.check("the lock says what it is and what to do", "🔒 shipped" in canvas and "press Duplicate" in canvas and "onLock" in js)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="studio model tests"))
