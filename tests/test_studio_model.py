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


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="studio model tests"))
