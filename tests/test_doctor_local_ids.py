"""tests.test_doctor_local_ids -- Halo 3.3.6.0 R2 `halo doctor --local`'s dead role ids and Ollama version drift
(halo_harness/doctor_local_ids.py; plans/local-model-fit-brief.md D4 item 19) through the doctor rig: a scratch
home whose host `box` has its catalog through the Ollama panel's READERS seam, the versions and the staged update
through the module's seams. No request, no model call:

1. a role on a deleted tag FAILs and names the nearest equivalent ("`qwen3.8:27b` was deleted -- nearest
   `qwen3.8:27b-gpu`"); a live id passes; a cloud role is not listed; a catalog that does not answer is INFO;
2. version drift per host: older than the newest known is a WARN; "0.40.13 staged, 0.40.6 running"; the newest
   passes; drift never fails the exit;
3. `halo doctor --local` prints both kinds of line (the acceptance steps' four lines stay first).
Run: python -m tests.test_doctor_local_ids
"""
from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.search_rig import SearchHome, box_card  # noqa: E402

test, TESTS = new_registry()
CAT = {"models": [{"model": "qwen3.8:27b-gpu", "name": "qwen3.8:27b-gpu"}, {"model": "qwen3-coder:30b", "name": "qwen3-coder:30b"},
                  {"model": "nomic-embed-text:latest", "name": "nomic-embed-text:latest"}]}


@test
def test_a_dead_role_id_names_the_nearest(ctx: Ctx):
    from halo_harness.doctor_local_ids import id_steps, nearest
    with SearchHome(card=box_card(), catalog=CAT) as h:
        steps = id_steps(h.state, role_table={"coder": "ol:qwen3-coder:30b@box", "planner": "ol:qwen3.8:27b@box",
                                              "embed": "ol:nomic-embed-text@box", "reviewer": "or:some/model"},
                         main_ref="ol:qwen3.8:27b@box", versions={"box": "0.40.13"}, staged=lambda host: "")
    with SearchHome(card=box_card(), catalog={"models": []}) as h:
        quiet = id_steps(h.state, role_table={"coder": "ol:qwen3-coder:30b@box"}, main_ref="", versions={"box": "0.40.13"},
                         staged=lambda host: "")
    by = {s["step"]: s for s in steps}
    ctx.check(f"main and planner on a deleted tag FAIL with the nearest, got {by.get('role planner id')}",
              by["role main id"]["ok"] is False and by["role planner id"]["ok"] is False and
              "`qwen3.8:27b` was deleted from box -- nearest `qwen3.8:27b-gpu`" in by["role planner id"]["reason"])
    ctx.check(f"the fix names the command, got {by['role planner id']['reason']!r}",
              "halo config set roles.planner ol:qwen3.8:27b-gpu@box" in by["role planner id"]["reason"])
    ctx.check(f"a live id passes (an untagged name matches :latest), got {by.get('role coder id')} {by.get('role embed id')}",
              by["role coder id"]["ok"] and by["role embed id"]["ok"])
    ctx.check(f"a cloud role is not listed, got {sorted(by)}", "role reviewer id" not in by)
    ctx.check(f"a catalog that does not answer is INFO, got {quiet[0]}", quiet[0]["tag"] == "INFO" and quiet[0]["ok"])
    ctx.check("nearest: the same model at another tag, else the closest spelling",
              nearest("qwen3.8:27b", ["qwen3.8:27b-gpu", "llama3:8b"]) == "qwen3.8:27b-gpu"
              and nearest("qwen3-codr:30b", ["qwen3-coder:30b", "gemma3:4b"]) == "qwen3-coder:30b" and nearest("zzz", ["gemma3:4b"]) is None)


@test
def test_ollama_version_drift_per_host(ctx: Ctx):
    from halo_harness.doctor_local_ids import id_steps
    with SearchHome(card=box_card(), catalog=CAT) as h:
        old = id_steps(h.state, role_table={}, main_ref="", versions={"box": "0.40.6"}, staged=lambda host: "")
        staged = id_steps(h.state, role_table={}, main_ref="", versions={"box": "0.40.6"}, staged=lambda host: "0.40.13")
        new = id_steps(h.state, role_table={}, main_ref="", versions={"box": "0.40.13"}, staged=lambda host: "")
        none = id_steps(h.state, role_table={}, main_ref="", versions={}, staged=lambda host: "")
    ctx.check(f"older than the newest known: WARN, got {old}",
              old[0]["tag"] == "WARN" and old[0]["ok"] and "Ollama 0.40.6, 0.40.13 is newer" in old[0]["reason"])
    ctx.check(f"the Windows staged update, got {staged[0]['reason']!r}",
              staged[0]["tag"] == "WARN" and "0.40.13 staged, 0.40.6 running" in staged[0]["reason"])
    ctx.check(f"the newest passes, got {new[0]}", new[0]["ok"] and "tag" not in new[0] and "the newest known" in new[0]["reason"])
    ctx.check(f"no version read: INFO, got {none[0]}", none[0]["tag"] == "INFO")


@test
def test_halo_doctor_local_prints_them(ctx: Ctx):
    import halo_harness.doctor_local_ids as D
    from halo_harness.doctor import cmd_doctor as doctor_main
    with SearchHome(card=box_card(), catalog=CAT) as h:
        import json
        cfg = json.loads((h.state / "config.json").read_text(encoding="utf-8"))
        cfg["roles"] = {"planner": "ol:qwen3.8:27b@box"}
        (h.state / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
        saved = D._version, D.staged_update
        D._version, D.staged_update = (lambda host, versions: "0.40.6"), (lambda host: "0.40.13")
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                rc = doctor_main(["--local", "--model", "ol:qwen3-coder:30b@box"])
        finally:
            D._version, D.staged_update = saved
    lines = [ln.strip() for ln in out.getvalue().splitlines() if ln.strip().startswith("[")]
    ctx.check(f"the four acceptance lines first, then the role id and the drift lines, got {lines}",
              len(lines) >= 6 and lines[0].startswith(("[PASS] load", "[FAIL] load"))
              and any(ln.startswith("[FAIL] role planner id") and "nearest `qwen3.8:27b-gpu`" in ln for ln in lines)
              and any(ln.startswith("[WARN] ollama box") and "0.40.13 staged, 0.40.6 running" in ln for ln in lines))
    ctx.check(f"a dead id fails the exit, got {rc}", rc == 1)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
