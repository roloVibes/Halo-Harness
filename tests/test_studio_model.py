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
        "org": {"positions": [{"title": "Boss", "agent": "orchestrator"}, {"title": "Worker", "agent": "implementer", "reports_to": "Boss"}]},  # removed in 3.1.4.0
        "pipeline": {"stages": [{"name": "implement", "role": "worker"}, {"name": "review", "role": "review"}]},
    }
    g = M.graph_for(raw, catalog={})
    nodes = {n["alias"]: n for n in g["nodes"]}
    ctx.check("one node per assignment with stable ids", len(g["nodes"]) == 4 and g["nodes"][0]["id"] == "boss#0")
    ctx.check("delegation edges from main carry the routing keys that reach each member",
              any(e["kind"] == "delegation" and e["to"] == "worker#1" and e["label"] == "implement, fix" for e in g["edges"]))
    ctx.check("a leftover org reports_to draws nothing (3.1.4.0)", not any(e["kind"] == "reports" for e in g["edges"]))
    ctx.check("pipeline stages become ordered pipeline edges", any(e["kind"] == "pipeline" and e["from"] == "worker#1" and e["to"] == "review#2" for e in g["edges"]))
    ctx.check("a missing bio is a node problem", any("not found" in p for p in g["nodes"][3]["problems"]))
    ctx.check("a duplicate alias is a warning on the second node", any("twice" in w for w in g["nodes"][3]["warnings"]))
    ctx.check("the main node resolves the bio's own model", nodes["boss"]["model"] and nodes["boss"]["kind"] == "main")
    two_mains = {"name": "m", "agents": [{"agent": "orchestrator", "role": "main"}, {"agent": "reviewer", "role": "main"}]}
    ctx.check("two mains warn on every node", all(any("role main" in w for w in n["warnings"]) for n in M.graph_for(two_mains, catalog={})["nodes"]))
    override = {"name": "o", "agents": [{"agent": "reviewer", "role": "main", "models": {"preference": "or:x/y"}}]}
    ctx.check("a per-assignment override wins over the bio", M.graph_for(override, catalog={"or:x/y": {"price": "$1/M", "context": "1M"}})["nodes"][0]["model"] == "or:x/y")
    over = M.graph_for(override, catalog={})["nodes"][0]  # 3.1.4.0 R4: the strip's "the bio's own (<model>)"
    plain = M.graph_for({"name": "p", "agents": [{"agent": "reviewer", "role": "main"}]}, catalog={})["nodes"][0]
    ctx.check(f"a node names its bio's own model beside the override, got {over.get('bio_model')!r} / {plain['model']!r}",
              over.get("bio_model") == plain["model"] == plain.get("bio_model") and over["bio_model"] != "or:x/y")


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
    ctx.check("layouts round-trip (3.0.7.0: the {nodes, tiers} shape)",
              (M.write_layout(state, "x", {"a": {"x": 1, "y": 2}}) or M.read_layout(state, "x"))
              == {"nodes": {"a": {"x": 1, "y": 2}}, "tiers": {}})
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
    ctx.check("the shell's build ships as package data, the classic page no more", "studio/static/dist/*" in text and "studio/static/legacy" not in text)


@test
def test_every_card_hangs_off_main(ctx: Ctx):
    """3.1.4.0: the lineup `org:` section is gone: a leftover
    org.positions[].reports_to draws no edge and every non-main card hangs
    off main by its delegation edge; the React canvas has no Reports-to."""
    from halo_harness.studio.model import graph_for
    raw = {"name": "t", "agents": [{"agent": "orchestrator", "role": "main", "as": "boss"},
                                   {"agent": "implementer", "role": "subagent", "as": "worker"},
                                   {"agent": "verifier", "role": "reviewer", "as": "tester"}],
           "org": {"positions": [{"title": "tester", "agent": "verifier", "reports_to": "worker"}]}}
    g = graph_for(raw, catalog={})
    ids = {n["alias"]: n["id"] for n in g["nodes"]}
    kinds = {(e["from"], e["to"]): e["kind"] for e in g["edges"]}
    ctx.check(f"worker hangs off main, got {kinds}", kinds.get((ids["boss"], ids["worker"])) == "delegation")
    ctx.check("tester hangs off main too, no reports edge", kinds.get((ids["boss"], ids["tester"])) == "delegation"
              and "reports" not in kinds.values())
    from pathlib import Path as _P
    roles = _P(__file__).resolve().parent.parent / "halo_harness" / "studio" / "ui" / "src" / "routes" / "roles"
    canvas, assign, parts = ((roles / f).read_text(encoding="utf-8") for f in ("Canvas.tsx", "Assignment.tsx", "CanvasParts.tsx"))
    ctx.check("the React canvas has no drop-to-report and no Reports-to field",
              "setReportsTo" not in canvas and 'label="Reports to"' not in assign and '"reports"' not in parts)
    ctx.check("a shipped bio's badge says what it is and what to do", "Duplicate it in the Bios panel" in parts)


@test
def test_graph_emits_tiers(ctx: Ctx):
    """3.0.7.0 R1: graph["tiers"] -- the declared tiers plus the implicit
    last tier; one implicit tier `all` when none are declared."""
    from halo_harness.studio.model import graph_for
    agents = [{"agent": "orchestrator", "role": "main"}, {"agent": "implementer", "role": "subagent", "as": "worker"},
              {"agent": "verifier", "role": "reviewer"}]
    g = graph_for({"agents": agents}, catalog={})
    ctx.check(f"no tiers: one implicit tier 'all' holding every card, got {g['tiers']}", g["tiers"] == [
        {"name": "all", "members": ["main", "worker", "reviewer"], "max_parallel": None, "model": None, "trigger": None,
         "index": 0, "implicit": True, "node_ids": ["main#0", "worker#1", "reviewer#2"]}])
    g = graph_for({"agents": agents, "tiers": [{"name": "top", "members": ["main"]},
                                               {"name": "workers", "members": ["worker"], "max_parallel": 3}]},
                  catalog={})
    ctx.check(f"declared tiers then the implicit 'rest', got {g['tiers']}",
              [(t["name"], t["members"], t["max_parallel"], t["index"], t["implicit"], t["node_ids"]) for t in g["tiers"]]
              == [("top", ["main"], None, 0, False, ["main#0"]), ("workers", ["worker"], 3, 1, False, ["worker#1"]),
                  ("rest", ["reviewer"], None, 2, True, ["reviewer#2"])])


@test
def test_layout_shapes_old_and_new(ctx: Ctx):
    """3.0.7.0 R1: a layout is {nodes: {id: {x,y}}, tiers: {name: {collapsed}}};
    the old flat {id: {x,y}} reads as {nodes: <it>, tiers: {}}; the API view
    keeps the flat positions too, for a reader of the old flat file."""
    import tempfile
    from halo_harness.studio import model as M
    state = Path(tempfile.mkdtemp(prefix="studio-layout-")) / ".halo"
    d = M.layouts_dir(state)
    d.mkdir(parents=True)
    (d / "old.json").write_text(json.dumps({"main#0": {"x": 5, "y": 6}}), encoding="utf-8")
    ctx.check("the old flat file reads as the new shape",
              M.read_layout(state, "old") == {"nodes": {"main#0": {"x": 5, "y": 6}}, "tiers": {}})
    ctx.check("a missing layout is the empty new shape", M.read_layout(state, "none") == {"nodes": {}, "tiers": {}})
    M.write_layout(state, "new", {"main#0": {"x": 1, "y": 2}}, tiers={"top": {"collapsed": True}})
    on_disk = json.loads((d / "new.json").read_text(encoding="utf-8"))
    ctx.check(f"write_layout writes the new shape, got {on_disk}",
              on_disk == {"nodes": {"main#0": {"x": 1, "y": 2}}, "tiers": {"top": {"collapsed": True}}})
    M.write_layout(state, "new", {"main#0": {"x": 9, "y": 9}})
    ctx.check("a positions-only save keeps the saved tier state", M.read_layout(state, "new") ==
              {"nodes": {"main#0": {"x": 9, "y": 9}}, "tiers": {"top": {"collapsed": True}}})
    M.write_layout(state, "new", M.read_layout(state, "new"))
    ctx.check("a whole layout round-trips", M.read_layout(state, "new")["tiers"] == {"top": {"collapsed": True}})
    view = M.legacy_layout_view(M.read_layout(state, "new"))
    ctx.check(f"the API view has nodes, tiers and the flat positions, got {view}",
              view == {"main#0": {"x": 9, "y": 9}, "nodes": {"main#0": {"x": 9, "y": 9}}, "tiers": {"top": {"collapsed": True}}})
    ctx.check("an empty layout's API view is {}", M.legacy_layout_view(M.read_layout(state, "none")) == {})
    ui = REPO / "halo_harness" / "studio" / "ui" / "src" / "routes"
    ctx.check("3.0.7.0 R2: the React readers take `nodes` and the flat map alike",
              all('"nodes" in' in (ui / d / "sync.ts").read_text(encoding="utf-8") or "r.nodes" in (ui / d / "sync.ts").read_text(encoding="utf-8") for d in ("roles",)))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="studio model tests"))
