"""tests.test_builder_workflows -- Halo 3.6.0.0 R2: the builder on the Workflows tab, through Studio's own routes with the
scripted fake model (tests/helpers/crew_rig.py `scripted`):

1. "make a review workflow: my-reviewer, then tester, repeat until the tests pass, at most 3 times" -> ONE preview: a
   create line for the workflow, a line per step, and (my-reviewer is not an agent of theirs) the proposal: my-reviewer's
   own create line (it carries the body the card's "make it" fills the form with) and its widening line (Run commands)
   UNTICKED; no workflow line widens; one Apply writes both files, one Undo puts both back byte for byte;
2. no path pre-ticks a widening line: not the agent a step adds, not the model's own `ticked` words, not Apply of every
   id that came ticked;
3. the step tools on a saved workflow: add, change, move, take out; a starter is copied first; a workflow on a map is
   not deleted (the reply says which map);
4. Write it for me on an unsaved workflow: a create with the drafted steps; on a saved one: step lines;
5. try_workflow starts the same throwaway run the page's button does and writes nothing; the builder's cap counts
   only its own calls and covers these tools too (429 past it).
Run: python -m tests.test_builder_workflows
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.crew_rig import CALL_USD, CrewRig  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
ASK = "make a review workflow: my-reviewer, then tester, repeat until the tests pass, at most 3 times"


def _ask(rig, text: str, cid: str, selection=None):
    return rig.api("POST", "builder/ask", {"tab": "workflows", "text": text, "conversation_id": cid, "selection": selection or {}})


def _files(rig) -> dict:
    crew = rig.state / "crew"
    return {str(p.relative_to(crew)): p.read_bytes() for p in crew.rglob("*.yaml")} if crew.is_dir() else {}


def _save(rig, kind: str, raw: dict) -> None:
    from halo_harness.crew import store
    store.write_text(store.path_for(kind, raw["name"], state_dir=rig.state), store.dump(raw))


@test
def test_one_preview_across_agents_and_workflows(ctx: Ctx):
    with CrewRig() as rig:
        rig.studio()
        before = _files(rig)
        st, r = _ask(rig, ASK, "w1")
        rows = r.get("changes") or []
        kinds = [(c["kind"], c["target"], c["widen"], c["ticked"]) for c in rows]
        ctx.check(f"200, a create line for the workflow first and a line per step, got {st} {kinds}",
                  st == 200 and kinds[0][:2] == ("create", "workflow:review-loop") and
                  [k[1] for k in kinds[1:3]] == ["workflow:review-loop"] * 2 and "step 2: Test (tester)" in rows[2]["summary"])
        ctx.check("the step line says the repeat", "repeat until the tests pass, at most 3 times" in rows[2]["summary"])
        agent = [c for c in rows if c["target"] == "agent:my-reviewer"]
        ctx.check(f"the agent it does not have is proposed: its create line carries the body for make it, got {[c['summary'] for c in agent]}",
                  agent and agent[0]["kind"] == "create" and agent[0].get("body", {}).get("name") == "my-reviewer")
        widen = [c for c in rows if c["widen"]]
        ctx.check(f"what lets it do more (Run commands, changes files on its own) is unticked, got {[(c['summary'], c['ticked']) for c in widen]}",
                  len(widen) == 2 and all(not c["ticked"] and c["target"] == "agent:my-reviewer" for c in widen))
        ctx.check("no workflow line widens", not any(c["widen"] for c in rows if c["target"].startswith("workflow:")))
        ghosts = [c.get("ghost") for c in rows if c.get("ghost")]
        ctx.check(f"each step line carries its ghost step for the form, got {[g['op'] for g in ghosts]}",
                  [g["op"] for g in ghosts] == ["step_add", "step_add"] and ghosts[1]["step"]["agents"] == ["tester"])
        st, got = rig.api("POST", "builder/apply", {"conversation_id": "w1", "change_ids": [c["id"] for c in rows if c["ticked"]]})
        from halo_harness.crew import store
        wf = store.read(store.path_for("workflow", "review-loop", state_dir=rig.state)) or {}
        ag = store.read(store.path_for("agent", "my-reviewer", state_dir=rig.state)) or {}
        ctx.check(f"one Apply wrote the workflow (2 steps) and the agent (reads, asks before changes), got {st} {got.get('wrote')}",
                  st == 200 and len(got["wrote"]) == 2 and [s["name"] for s in wf.get("steps") or []] == ["Review", "Test"]
                  and wf["steps"][1]["repeat"] == {"until": "the tests pass", "max": 3} and ag.get("uses") == ["read"]
                  and ag.get("careful") == "ask-changes")
        st, u = rig.api("POST", "builder/undo", {"undo_id": got["undo_id"]})
        ctx.check(f"one Undo: both files as before (gone), got {st} {u}", st == 200 and _files(rig) == before)


@test
def test_no_path_pre_ticks_a_widening_line(ctx: Ctx):
    with CrewRig() as rig:
        rig.studio()
        _st, r = _ask(rig, ASK, "w2")
        rows = r["changes"]
        ctx.check("every widening line comes unticked from the server", all(not c["ticked"] for c in rows if c["widen"]))
        from halo_harness.crew import builder
        held = builder.pending(rig.state, "w2")
        ctx.check("and is held unticked server side", all(not c["ticked"] for c in held if c["widen"]))
        ok = [c["id"] for c in rows if not c["widen"]]
        _st, got = rig.api("POST", "builder/apply", {"conversation_id": "w2", "change_ids": ok})
        from halo_harness.crew import store
        ag = store.read(store.path_for("agent", "my-reviewer", state_dir=rig.state)) or {}
        ctx.check(f"Apply of everything not widening writes no command access, got {ag.get('uses')} {ag.get('careful')}",
                  ag.get("uses") == ["read"] and ag.get("careful") == "ask-changes")


@test
def test_the_step_tools_and_the_rules(ctx: Ctx):
    from halo_harness.crew import tools
    with CrewRig() as rig:
        _save(rig, "agent", {"format": "agent/1", "name": "my-reviewer", "does": "Reviews.", "model": "auto", "uses": ["read"], "careful": "ask-changes"})
        _save(rig, "workflow", {"format": "workflow/1", "name": "loop", "for": "Review then test.", "steps": [
            {"name": "Review", "agents": ["my-reviewer"]}, {"name": "Test", "agents": ["tester"]}]})
        c = {"cwd": rig.proj, "state_dir": rig.state}
        add = tools.run("step_add", {"workflow": "loop", "step": {"name": "Ship", "agents": ["ops"], "when": {"says": ["ship"]}}, "index": 2}, c)
        mv = tools.run("step_move", {"workflow": "loop", "index": 1, "to": 2}, c)
        ch = tools.run("step_change", {"workflow": "loop", "index": 2, "fields": {"repeat": {"until": "clean", "max": 2}}}, c)
        rm = tools.run("step_remove", {"workflow": "loop", "index": 2}, c)
        ctx.check(f"each answers one line, none widens, got {[x['rows'][0]['summary'] for x in (add, mv, ch, rm)]}",
                  all(len(x["rows"]) == 1 and not x["rows"][0]["widen"] for x in (add, mv, ch, rm)))
        from halo_harness.crew.changes import apply
        got = apply(add["rows"], [add["rows"][0]["id"]], state_dir=rig.state)
        from halo_harness.crew import store
        wf = store.read(store.path_for("workflow", "loop", state_dir=rig.state))
        ctx.check(f"step_add as step 2, got {got['ok']} {[s['name'] for s in wf['steps']]}", [s["name"] for s in wf["steps"]] == ["Review", "Ship", "Test"])
        bad = tools.run("step_change", {"workflow": "loop", "index": 1, "fields": {"repeat": {"until": "x", "max": 40}}}, c)
        ctx.check(f"a repeat past 10 is refused in the reply, got {bad['text']!r}", not bad["rows"] and "max: 1-10" in bad["text"])
        st = tools.run("step_add", {"workflow": "review", "step": {"name": "x", "agents": ["tester"]}}, c)
        ctx.check(f"a starter is copied first, got {st['text']!r}", not st["rows"] and "workflow_copy it first" in st["text"])
        _save(rig, "map", {"format": "map/1", "name": "everyday", "boxes": [{"id": "l", "workflow": "loop"}], "lines": [{"from": "main", "to": "l", "when": "always"}]})
        rm = tools.run("workflow_remove", {"name": "loop"}, c)
        ctx.check(f"a workflow on a map is not deleted, the reply says which, got {rm['text']!r}", not rm["rows"] and "everyday" in rm["text"])
        cp = tools.run("workflow_copy", {"name": "review", "new_name": "my-review"}, c)
        ctx.check(f"a copy of a starter: one create line, got {cp['rows'][0]['summary']!r}", cp["rows"][0]["kind"] == "create")


@test
def test_write_it_for_me_on_the_workflows_tab(ctx: Ctx):
    with CrewRig() as rig:
        rig.studio()
        sel = {"workflow": "new-flow", "unsaved": {"name": "new-flow", "for": "Review then test", "steps": []}}
        _st, r = _ask(rig, "Draft the steps from what it is for", "w3", sel)
        ctx.check(f"an unsaved workflow: a create line and its steps, got {[c['summary'][:40] for c in r['changes']]}",
                  r["changes"] and r["changes"][0]["kind"] == "create" and r["changes"][0]["target"] == "workflow:new-flow")
        _save(rig, "workflow", {"format": "workflow/1", "name": "saved-flow", "for": "Review.", "steps": [{"name": "Review", "agents": ["reviewer"]}]})
        _st, r = _ask(rig, "Draft the steps from what it is for", "w4", {"workflow": "saved-flow"})
        ctx.check(f"a saved one: step lines, got {[c['summary'] for c in r['changes']]}",
                  [c["target"] for c in r["changes"]] == ["workflow:saved-flow"] and r["changes"][0]["ghost"]["op"] == "step_add")


@test
def test_try_workflow_writes_nothing_and_the_cap(ctx: Ctx):
    from halo_harness.crew import builder_cap
    with CrewRig() as rig:
        rig.studio()
        _save(rig, "workflow", {"format": "workflow/1", "name": "review-loop", "for": "Review.", "steps": [{"name": "Review", "agents": ["reviewer"]}]})
        before = _files(rig)
        spent = builder_cap.spent(rig.state)
        st, r = _ask(rig, "try the loop", "w5")
        ctx.check(f"a run started, no line to tick, got {st} {r.get('changes')} {[t.get('id') for t in r.get('tries') or []]}",
                  st == 200 and r["changes"] == [] and len(r.get("tries") or []) == 1 and r["tries"][0]["kind"] == "workflow")
        ctx.check("nothing written", _files(rig) == before)
        ctx.check(f"the builder's spend is its own two calls, got {builder_cap.spent(rig.state) - spent}",
                  abs(builder_cap.spent(rig.state) - spent - 2 * CALL_USD) < 1e-9)
        import json
        (rig.state / "config.json").write_text(json.dumps({"model": "or:mock/crew-try", "remote": {"enabled": False},
                                                          "studio": {"builder": {"cap_usd": 0.01}}}), encoding="utf-8")
        st, r = _ask(rig, ASK, "w6")
        ctx.check(f"past the cap: 429 and the one line, got {st} {r.get('error', '')[:60]!r}", st == 429 and "cap" in r.get("error", ""))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
