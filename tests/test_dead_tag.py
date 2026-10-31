"""tests.test_dead_tag -- Halo 3.3.7.0 R4: the deletion guard's one line (ollama_steward/dead_tag.py) and the nearest
equivalent (models_library/nearest.py), through a scratch home whose host `box` has its catalog and card through the
Ollama panel's READERS seam (tests/helpers/search_rig.SearchHome) and, for the scheduler's lines, the sched rig:

1. the nearest equivalent by family, size, quant, the window and the profile ("same family, same size, same quant,
   fits the same window"); no answer when nothing shares the family or the size (then the closest spelling);
2. a tag Halo saw there "was deleted"; one it never saw "is not on box (deleted, or never pulled there)"; a live tag
   and an unread catalog say nothing; the point line;
3. "point the role at it": roles.<role> written and nothing else, from `halo roles point` and POST roles/<r>/point;
4. the swap preview, `halo local warm --dry` and the Roles page's Problems speak the same line.
No request leaves 127.0.0.1, no model is called.
Run: python -m tests.test_dead_tag
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.search_rig import SearchHome, box_card  # noqa: E402

test, TESTS = new_registry()
GIB = 2 ** 30


def row(name: str, params: str, quant: str = "Q4_K_M", family: str = "qwen35", gb: float = 17.0) -> dict:
    from tests.helpers.steward_seed import QWEN27
    return {"model": name, "name": name, "size": int(gb * 1e9), "model_info": QWEN27,
            "details": {"family": family, "parameter_size": params, "quantization_level": quant}}


ROWS = [row("qwen3.8:27b-gpu", "27.0B"), row("qwen3.8:27b-q8", "27.0B", "Q8_0", gb=28.0),
        row("qwen3-coder:30b", "30.5B", family="qwen3moe", gb=18.6), row("llama3:8b", "8.0B", family="llama", gb=4.7)]


@test
def test_the_nearest_equivalent(ctx: Ctx):
    from halo_harness.models_library.nearest import nearest
    gone = row("qwen3.8:27b", "27.0B")
    got = nearest("qwen3.8:27b", ROWS, gone_row=gone, card=box_card(), window=32768)
    ctx.check(f"same family, same size, same quant, fits the same window, got {got}", got and got["name"] == "qwen3.8:27b-gpu"
              and got["line"] == "same family, same size, same quant, fits the same window")
    loose = nearest("qwen3.8:27b", ROWS)
    ctx.check(f"from the name alone: the family and the size, got {loose}", loose and loose["name"].startswith("qwen3.8:27b-")
              and loose["why"][:2] == ["same family", "same size"])
    ctx.check("nothing shares the family or the size: no answer", nearest("phi4:14b", ROWS) is None)


@test
def test_the_dead_tag_line(ctx: Ctx):
    from halo_harness.ollama_steward.dead_tag import check, line
    with SearchHome(card=box_card(), catalog={"models": ROWS}) as h:
        unseen = check("ol:qwen3.8:27b@box", state_dir=h.state, role="planner")
        h.profile("qwen3.8:27b", size_gb=17.0)
        seen = check("ol:qwen3.8:27b@box", state_dir=h.state, role="planner")
        live = line("ol:qwen3-coder:30b@box", state_dir=h.state)
        far = check("ol:phi4:14b@box", state_dir=h.state, role="planner")
    ctx.check(f"never seen there, got {unseen['line']!r}", unseen["dead"] and not unseen["known"]
              and unseen["line"].startswith("`qwen3.8:27b` is not on box (deleted, or never pulled there) -- nearest "
                                            "equivalent `qwen3.8:27b-gpu`"))
    ctx.check(f"seen there: was deleted, with the point line, got {seen['line']!r}", seen["known"]
              and seen["line"].startswith("`qwen3.8:27b` was deleted from box -- nearest equivalent `qwen3.8:27b-gpu` (same "
                                          "family, same size, same quant")
              and seen["line"].endswith(": halo roles point planner ol:qwen3.8:27b-gpu@box") and seen["near"] == "ol:qwen3.8:27b-gpu@box")
    ctx.check("a live tag says nothing", live == "")
    ctx.check(f"nothing like it: the closest spelling, said so, got {far['line']!r}",
              far["dead"] and "the closest spelling" in far["line"] or "no model like it there" in far["line"])
    with SearchHome(card=box_card(), catalog={"models": []}) as h:
        ctx.check("an unread catalog judges nothing", check("ol:qwen3.8:27b@box", state_dir=h.state)["judged"] is False)


@test
def test_point_the_role_at_it(ctx: Ctx):
    from halo_harness.roles_cli import cmd_roles
    from halo_harness.studio.api import Request, dispatch
    with SearchHome(card=box_card(), catalog={"models": ROWS}) as h:
        cfg = json.loads((h.state / "config.json").read_text(encoding="utf-8"))
        cfg["roles"] = {"planner": "ol:qwen3.8:27b@box", "coder": {"model": "ol:qwen3.8:27b@box", "effort": "high"}}
        (h.state / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = cmd_roles(["point", "planner", "ol:qwen3.8:27b-gpu@box"])
        st, ans = dispatch(Request(method="POST", path="roles/coder/point", query={}, body={"to": "ol:qwen3.8:27b-gpu@box"},
                                   cwd=h.root, state_dir=h.state))
        bad = dispatch(Request(method="POST", path="roles/coder/point", query={}, body={}, cwd=h.root, state_dir=h.state))
        after = json.loads((h.state / "config.json").read_text(encoding="utf-8"))
    ctx.check(f"halo roles point writes the role, got {rc} {out.getvalue()!r}", rc == 0
              and after["roles"]["planner"] == "ol:qwen3.8:27b-gpu@box" and "nothing pulled, nothing loaded" in out.getvalue())
    ctx.check(f"POST roles/coder/point keeps the effort, got {st} {ans}", st == 200 and after["roles"]["coder"] ==
              {"model": "ol:qwen3.8:27b-gpu@box", "effort": "high"})
    ctx.check(f"no target: 422, got {bad[0]}", bad[0] == 422)
    ctx.check("nothing else in config.json changed", set(after) == set(cfg))


@test
def test_the_preview_warm_and_problems_speak_it(ctx: Ctx):
    from halo_harness.local_sched.preview import preview
    from halo_harness.local_warm_cli import warm_lineup
    from halo_harness.lineup_preflight import template_problems
    from tests.helpers.sched_lineup import write
    from tests.helpers.sched_rig import BIG, CODER, SchedHome
    with SchedHome() as h:
        from halo_harness.studio import ollama_hosts_view as V
        rows = [r for r in __import__("tests.helpers.sched_rig", fromlist=["rows"]).rows().values() if r["model"] != BIG]
        V.READERS["catalog"] = lambda host: {"models": [dict(r) for r in rows] + [row("qwen3.8:27b-gpu", "27.0B")]}
        V.reset_cache()
        h.loads(BIG, 30.0)  # Halo called it there once: a record that it was installed
        write(h.state, "dead-lane", {"coder": f"ol:{CODER}@pc", "verify": f"ol:{BIG}@pc"})
        pv = preview("dead-lane", main_ref=f"ol:{CODER}@pc")
        warm = warm_lineup("dead-lane", dry=True)
        from halo_harness.teams_yaml import resolve_team_template
        probs = template_problems(resolve_team_template("dead-lane"), state_dir=h.state)
    want = f"`{BIG}` was deleted from pc -- nearest equivalent `qwen3.8:27b-gpu`"
    ctx.check(f"the swap preview's hygiene, got {pv['hygiene']}", any(want in x for x in pv["hygiene"]))
    rows = [r for host in warm["hosts"] for r in host["rows"]]
    ctx.check(f"halo local warm --dry: the row is deleted, got {rows}", any(r["state"] == "deleted" and want in r["say"]
                                                                            for r in rows))
    ctx.check(f"the Roles page's Problems, got {[p['text'] for p in probs]}", any(want in p["text"] for p in probs))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
