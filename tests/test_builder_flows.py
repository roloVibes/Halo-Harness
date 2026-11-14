"""tests.test_builder_flows -- Halo 3.6.0.0 R1: the builder's preview / apply / undo and its cap, through Studio's own
routes (studio/builder_api.py) with a scripted fake model (tests/helpers/crew_rig.py `scripted`), and one turn through
the repo's fake provider (the mock upstream) to show the real call path.

1. "make a security gate": the preview's lines -- the agent itself ticked, every line that lets it do more (a connected
   tool, run commands, change files, works on its own) unticked; Apply with what came ticked writes an agent that only
   reads and asks before changes; no route, no reply pre-ticks a widening line;
2. ticking one widening line writes that one; Undo puts every touched file back byte for byte (a made file goes);
3. a change, a copy, a delete (not while a workflow names the agent: the reply says which), a choice question;
4. Write it for me: an unsaved agent's draft comes back as a `fill` line (nothing written), a saved one's as a change;
5. the cap: a turn stops at it, the next request answers 429 with the one line, the meta says so; apply knows only its
   preview's ids and needs the owner's proof;
6. one turn through the mock upstream (no CALLER): its reply, its cost added to the day.
Run: python -m tests.test_builder_flows
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.crew_rig import DRAFT, CrewRig  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _ask(rig, text: str, cid: str, selection=None):
    return rig.api("POST", "builder/ask", {"tab": "agents", "text": text, "conversation_id": cid, "selection": selection or {}})


def _agent(rig, name: str) -> dict:
    from halo_harness.crew import store
    return store.read(store.path_for("agent", name, state_dir=rig.state)) or {}


@test
def test_make_an_agent_preview_apply(ctx: Ctx):
    with CrewRig() as rig:
        rig.studio()
        st, r = _ask(rig, "make a security gate", "c1")
        ctx.check(f"200 and a reply, got {st} {r.get('reply')!r}", st == 200 and "security-gate" in r.get("reply", ""))
        rows = r.get("changes") or []
        widen = [c for c in rows if c["widen"]]
        ctx.check(f"one create line, ticked; four widening lines, got {[(c['kind'], c['widen'], c['ticked']) for c in rows]}",
                  [c["kind"] for c in rows][0] == "create" and rows[0]["ticked"] and len(widen) == 4)
        ctx.check("no widening line comes ticked", all(not c["ticked"] for c in widen))
        ctx.check("each says what it lets the agent do", sorted(c["summary"].split(": ", 1)[1] for c in widen) ==
                  ["Change files", "Connected tool: github", "Run commands", "works on its own (your deny rules still hold)"])
        st, got = rig.api("POST", "builder/apply", {"conversation_id": "c1", "change_ids": [c["id"] for c in rows if c["ticked"]]})
        a = _agent(rig, "security-gate")
        ctx.check(f"applied: the agent reads and asks before changes, got {st} {a}", st == 200 and a.get("uses") == ["read"]
                  and a.get("careful") == "ask-changes" and got.get("undo_id"))
        ctx.check("the preview is gone after Apply", rig.api("POST", "builder/apply", {"conversation_id": "c1", "change_ids": []})[0] == 409)


@test
def test_a_ticked_widening_line_and_undo(ctx: Ctx):
    with CrewRig() as rig:
        rig.studio()
        _st, r = _ask(rig, "make a security gate", "c2")
        rows = r["changes"]
        bash = next(c for c in rows if c["summary"].endswith("Run commands"))
        ids = [c["id"] for c in rows if c["ticked"]] + [bash["id"]]
        _st, got = rig.api("POST", "builder/apply", {"conversation_id": "c2", "change_ids": ids})
        ctx.check(f"the ticked one is written, the others not, got {_agent(rig, 'security-gate').get('uses')}",
                  _agent(rig, "security-gate").get("uses") == ["read", "bash"])
        from halo_harness.crew import store
        path = store.path_for("agent", "security-gate", state_dir=rig.state)
        before = path.read_bytes()
        _st, r = _ask(rig, "give yourself more", "c3")
        ctx.check("a change to another agent first needs it", r["changes"] == [])
        st, u = rig.api("POST", "builder/undo", {"undo_id": got["undo_id"]})
        ctx.check(f"Undo of a create: the file is gone, got {st} {u}", st == 200 and not path.exists())
        store.write_text(path, before.decode("utf-8"))
        _st, r = rig.api("POST", "builder/ask", {"tab": "agents", "text": "write the instructions for security-gate", "conversation_id": "c4"})
        _st, got = rig.api("POST", "builder/apply", {"conversation_id": "c4", "change_ids": [c["id"] for c in r["changes"]]})
        ctx.check("a saved agent's draft is written", _agent(rig, "security-gate").get("instructions") == DRAFT)
        rig.api("POST", "builder/undo", {"undo_id": got["undo_id"]})
        ctx.check("Undo puts the file back byte for byte", path.read_bytes() == before)
        ctx.check("an undo id once only", rig.api("POST", "builder/undo", {"undo_id": got["undo_id"]})[0] == 404)


@test
def test_change_copy_remove_and_a_question(ctx: Ctx):
    from halo_harness.crew import store
    from halo_harness.crew import tools
    with CrewRig() as rig:
        rig.studio()
        ctxd = {"cwd": rig.proj, "state_dir": rig.state, "selection": {}, "draft": lambda n, d: ("x", 0.0)}
        copy = tools.run("agent_copy", {"name": "reviewer", "new_name": "my-reviewer"}, ctxd)
        ctx.check(f"a copy of a starter: one create line (it only reads), got {[c['summary'] for c in copy['rows']]}",
                  len(copy["rows"]) == 1 and copy["rows"][0]["op"]["op"] == "copy")
        from halo_harness.crew import changes
        changes.apply(copy["rows"], [copy["rows"][0]["id"]], cwd=rig.proj, state_dir=rig.state)
        ch = tools.run("agent_change", {"name": "my-reviewer", "fields": {"model": "or:mock/x", "uses": ["edit"]}}, ctxd)
        kinds = sorted((c["summary"], c["widen"]) for c in ch["rows"])
        ctx.check(f"model (not widening), edit added (widening), read dropped (not), got {kinds}",
                  [w for _s, w in kinds].count(True) == 1 and len(kinds) == 3)
        wf = {"format": "workflow/1", "name": "ship", "for": "x", "steps": [{"name": "a", "agents": ["my-reviewer"]}]}
        store.write_text(store.path_for("workflow", "ship", state_dir=rig.state), store.dump(wf))
        rm = tools.run("agent_remove", {"name": "my-reviewer"}, ctxd)
        ctx.check(f"not while a workflow names it, and the reply says which, got {rm['text']!r}", rm["rows"] == [] and "workflow ship" in rm["text"])
        st, r = rig.api("DELETE", "crew/agent/my-reviewer")
        ctx.check(f"the page's Delete says the same, got {st} {r}", st == 409 and "workflow ship" in r.get("error", ""))
        _st, q = _ask(rig, "which reviewer should check the build", "c5")
        ctx.check(f"a choice question, its recommendation first, got {q.get('question')}",
                  (q.get("question") or {}).get("choices", [""])[0].startswith("my-reviewer (recommended"))


@test
def test_write_it_for_me_on_an_unsaved_agent_fills_the_form(ctx: Ctx):
    with CrewRig() as rig:
        rig.studio()
        sel = {"agent": "fresh-one", "unsaved": {"name": "fresh-one", "does": "Checks the totals of receipts."}}
        _st, r = _ask(rig, "write the instructions for fresh-one from what it does", "c6", sel)
        rows = r["changes"]
        ctx.check(f"one fill line with the draft, got {rows}", len(rows) == 1 and rows[0]["kind"] == "fill" and rows[0]["fill"]["value"] == DRAFT)
        st, got = rig.api("POST", "builder/apply", {"conversation_id": "c6", "change_ids": [rows[0]["id"]]})
        ctx.check(f"nothing written, the text handed to the form, got {got}", st == 200 and got["wrote"] == [] and got["filled"][0]["value"] == DRAFT)


@test
def test_the_cap_and_the_owner(ctx: Ctx):
    from halo_harness.crew import builder_cap
    from halo_harness.theme import set_config_value
    with CrewRig() as rig:
        rig.studio()
        set_config_value(builder_cap.CAP_KEY, 0.01)
        st, r = _ask(rig, "make a security gate", "c7")
        ctx.check(f"the turn stops at the cap after one call, got {st} {r.get('reply')!r}", st == 200 and r.get("capped") and r["reply"].startswith("Today's builder cap ($0.01) is reached"))
        st, r = _ask(rig, "make a security gate", "c8")
        ctx.check(f"the next request: 429 and the line, no model call, got {st}", st == 429 and "Settings -> Studio -> Builder" in r.get("error", ""))
        ctx.check("the meta says so", rig.api("GET", "builder")[1].get("reached") is True)
        set_config_value(builder_cap.CAP_KEY, 1.0)
        _st, r = _ask(rig, "make a security gate", "c9")
        st, bad = rig.api("POST", "builder/apply", {"conversation_id": "c9", "change_ids": ["cdeadbeef"]})
        ctx.check(f"an id not in the preview: 422, got {st}", st == 422)
        st, _x = rig.api("POST", "builder/apply", {"conversation_id": "c9", "change_ids": [r["changes"][0]["id"]]}, owner=False)
        ctx.check(f"without the owner's proof: 403, got {st}", st == 403)
        ctx.check("the text of a request cannot raise the cap: no tool for it", not any("cap" in n for n in __import__("halo_harness.crew.tools", fromlist=["TOOLS"]).TOOLS))


@test
def test_one_turn_through_the_mock_upstream(ctx: Ctx):
    from halo_harness.crew import builder
    from halo_harness.theme import set_config_value
    from tests.helpers.mock_openai import SCENARIOS, ScriptedTurns
    from tests.helpers.session_rig import text_step
    with CrewRig() as rig:
        builder.CALLER = None
        SCENARIOS["crew-builder"] = ScriptedTurns([text_step(json.dumps({"reply": "Hello from the mock."}))])
        try:
            set_config_value("studio.builder.model", "or:mock/crew-builder")
            out = builder.turn(rig.state, rig.proj, "agents", {}, "hello", "c10", [])
            ctx.check(f"the reply came through the provider, got {out.get('reply')!r}", out.get("reply") == "Hello from the mock.")
            ctx.check(f"its cost is on the day's spend, got {out['meta']}", out["meta"]["spent_usd"] > 0 and out["meta"]["model"] == "or:mock/crew-builder")
        finally:
            SCENARIOS.pop("crew-builder", None)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
