"""tests.test_live_groups -- Halo 3.3.16.3 "Live in groups": what an agent row carries so Studio's Live can box the
agents of one task (agent/agent_hooks.py `spawn_of`, agent/agent_observe.py's per-reply `_said`): `spawn: {step,
description, lead}` -- every Agent call of one reply shares the step (the parent's id and its reply count), a call in
the next reply has another, a count job queued then built keeps the step it was queued with, `lead` is the last line
the parent wrote in that reply; a square's agent row carries the square's DOES line (workflows/receipts.py). The
grouping itself is Studio's (routes/crew/live/groups.ts): its rule is pinned in the source here. Pure; no model.
Run: python -m tests.test_live_groups
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace as NS

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _ev(kind: str, **data):
    return NS(kind=kind, data=data)


def _reply(tree, aid: str, text: str) -> None:
    """One model reply of `aid`: its text, then its end (the tool calls run after it)."""
    tree.observe(aid, _ev("message_start"))
    for chunk in (text[: len(text) // 2], text[len(text) // 2:]):
        tree.observe(aid, _ev("text_delta", text=chunk))
    tree.observe(aid, _ev("message_end"))


def _tree():
    from halo_harness.agent.agent_registry import AgentTree
    from halo_harness.agent.agent_registry import tree_for
    root = NS(agent_id=None, model_ref=None, log=None)
    return root, tree_for(root)


def _spawn(root, aid: str, desc: str, prompt: str = "do it") -> None:
    from halo_harness.agent.agent_hooks import register_child
    child = NS(log=None, opt_ins=None)
    register_child(root, child, agent_id=aid, spec=NS(name="general-purpose"), model="or:mock/m", role="reader",
                   task_text=f"{desc}\n{prompt}")


@test
def test_one_reply_shares_a_step_the_next_has_another(ctx: Ctx):
    root, tree = _tree()
    tree.started("main", root, "read the three PDFs and review")
    _reply(tree, "main", "Let me look.\nI'll read the three PDFs side by side.")
    for i in range(3):
        _spawn(root, f"r{i}", f"Read PDF {i + 1}")
    _reply(tree, "main", "")
    _spawn(root, "v1", "Review the notes")
    rows = {r["agent_id"]: r for r in tree.public_rows()}
    steps = [rows[f"r{i}"]["spawn"]["step"] for i in range(3)]
    ctx.check(f"the three of one reply share a step, got {steps}", len(set(steps)) == 1 and steps[0] == "main#1")
    ctx.check(f"each keeps its own description, got {[rows[f'r{i}']['spawn']['description'] for i in range(3)]}",
              [rows[f"r{i}"]["spawn"]["description"] for i in range(3)] == ["Read PDF 1", "Read PDF 2", "Read PDF 3"])
    ctx.check(f"the lead is the parent's last line in that reply, got {rows['r0']['spawn']['lead']!r}",
              rows["r0"]["spawn"]["lead"] == "I'll read the three PDFs side by side.")
    v = rows["v1"]["spawn"]
    ctx.check(f"a spawn of the next reply is a step of its own with no lead, got {v}", v["step"] == "main#2" and v["lead"] == "")


@test
def test_a_queued_job_keeps_its_step_and_a_prompt_without_a_description(ctx: Ctx):
    from halo_harness.agent.agent_hooks import register_queued
    root, tree = _tree()
    tree.started("main", root, "go")
    _reply(tree, "main", "Fanning out.")
    register_queued(root, "q1", name="general-purpose", task="Summarise chapter one", description="Summarise (1/2)")
    _reply(tree, "main", "later words")
    _spawn(root, "q1", "Summarise (1/2)")  # the job starts after main moved on: the step it was queued with stays
    _spawn(root, "p1", "", "Check the links in README.md\nthen say which are dead")
    rows = {r["agent_id"]: r for r in tree.public_rows()}
    ctx.check(f"the queued job's step is its queue time's, got {rows['q1']['spawn']}", rows["q1"]["spawn"]["step"] == "main#1"
              and rows["q1"]["spawn"]["description"] == "Summarise (1/2)" and rows["q1"]["spawn"]["lead"] == "Fanning out.")
    ctx.check(f"no description: the prompt's first line, got {rows['p1']['spawn']}",
              rows["p1"]["spawn"]["description"] == "Check the links in README.md")


@test
def test_a_square_agent_carries_its_does_line(ctx: Ctx):
    from halo_harness.workflows import receipts
    root, tree = _tree()
    _spawn(root, "c1", "square media")
    receipts.mark_child(root, NS(agent_id="c1"), "media", "session", does="Reads PDFs for a model that cannot.")
    key = receipts.node(root, "code", "orchestra", state="running", does="Makes a code change.")
    rows = {r["agent_id"]: r for r in tree.public_rows()}
    ctx.check(f"the session square's agent, got {rows['c1'].get('square')}",
              rows["c1"]["square"] == {"name": "media", "engine": "session", "does": "Reads PDFs for a model that cannot."})
    ctx.check(f"the orchestra square's node, got {rows[key].get('square')}", rows[key]["square"]["does"] == "Makes a code change.")


def _todo(content: str, status: str = "pending", active: str = "") -> dict:
    return {"content": content, "status": status, "activeForm": active or f"Doing {content}"}


def _write_plan(tree, aid: str, todos: list, call: str, ok: bool = True) -> str:
    """One TodoWrite of `aid`: its call (the input on tool_use_ready), what its row says while it runs, its result."""
    tree.observe(aid, _ev("tool_use_ready", id=call, name="TodoWrite", input={"todos": todos}))
    doing = tree.row(aid).get("current")
    tree.observe(aid, _ev("tool_result", id=call, ok=ok, summary="Todos updated"))
    return doing


@test
def test_a_todowrite_puts_the_plan_on_the_row(ctx: Ctx):
    """3.6.0.23 PV ruling 1: a successful TodoWrite keeps that agent's list on its row (`plan`), the last call replacing
    it, capped in count and length; a refused one changes nothing; a sub-agent keeps its own. Ruling 6: while the call
    runs the "doing" line says the plan's size, never its raw JSON."""
    from halo_harness.agent.agent_observe import PLAN_MAX, PLAN_TEXT
    from halo_harness.agent.agent_registry import FIELDS
    root, tree = _tree()
    ctx.check("`plan` is an agent row field", "plan" in FIELDS)
    tree.started("main", root, "build the parser and its tests")
    ctx.check(f"no plan before the first list, got {tree.row('main').get('plan')!r}", not tree.row("main").get("plan"))
    doing = _write_plan(tree, "main", [_todo("Read the code", "completed"), _todo("Write the parser", "in_progress", "Writing the parser"), _todo("Test it")], "t1")
    ctx.check(f"the doing line says the plan's size, got {doing!r}", doing == "TodoWrite: plan of 3 steps" and "{" not in doing)
    plan = tree.row("main").get("plan")
    ctx.check(f"the plan is on main's row, got {plan}", plan == [
        {"content": "Read the code", "status": "completed", "activeForm": "Doing Read the code", "n": 1},
        {"content": "Write the parser", "status": "in_progress", "activeForm": "Writing the parser", "n": 2},
        {"content": "Test it", "status": "pending", "activeForm": "Doing Test it", "n": 3}])
    ctx.check(f"with its true counts, got {tree.row('main').get('plan_count')}", tree.row("main").get("plan_count") == {"all": 3, "done": 1})
    _write_plan(tree, "main", [_todo("One step only", "in_progress")], "t2")
    ctx.check(f"the next list replaces it, got {tree.row('main')['plan']}", [t["content"] for t in tree.row("main")["plan"]] == ["One step only"])
    _write_plan(tree, "main", [_todo("a", "in_progress"), _todo("b", "in_progress")], "t3", ok=False)
    ctx.check("a refused TodoWrite changes nothing", [t["content"] for t in tree.row("main")["plan"]] == ["One step only"])
    ctx.check(f"after the call the doing line is back to thinking, got {tree.row('main')['current']!r}", tree.row("main")["current"] == "thinking")
    _write_plan(tree, "main", [_todo("x" * 900) for _ in range(PLAN_MAX + 5)], "t4")
    big = tree.row("main")["plan"]
    ctx.check(f"capped: at most {PLAN_MAX} steps, each at most {PLAN_TEXT} characters, got {len(big)} / {len(big[0]['content'])}",
              len(big) == PLAN_MAX and len(big[0]["content"]) <= PLAN_TEXT and len(big[0]["activeForm"]) <= PLAN_TEXT)
    _spawn(root, "h1", "Check the docs")
    tree.started("h1", NS(model_ref=None), "Check the docs")
    _write_plan(tree, "h1", [_todo("Open README", "in_progress")], "s1")
    rows = {r["agent_id"]: r for r in tree.public_rows()}
    ctx.check(f"a sub-agent keeps its own plan, main keeps his, got {rows['h1'].get('plan')}",
              [t["content"] for t in rows["h1"]["plan"]] == ["Open README"] and len(rows["main"]["plan"]) == PLAN_MAX)


@test
def test_main_objective_is_the_latest_prompt_of_four_words(ctx: Ctx):
    """3.6.0.23 PV ruling 2: main's `objective` is the first line of the person's latest prompt with at least four
    words; a short reply ("yes", "go on") keeps the one that was there; empty before such a prompt; no model call."""
    from halo_harness.agent.agent_registry import FIELDS
    root, tree = _tree()
    ctx.check("`objective` is an agent row field", "objective" in FIELDS)
    ctx.check(f"empty at first, got {tree.row('main').get('objective')!r}", not tree.row("main").get("objective"))
    tree.started("main", root, "ok go")
    ctx.check(f"a short first prompt sets none, got {tree.row('main').get('objective')!r}", not tree.row("main").get("objective"))
    tree.started("main", root, "Fix the login page so it remembers me\nand add a test")
    ctx.check(f"four words or more: its first line, got {tree.row('main')['objective']!r}",
              tree.row("main")["objective"] == "Fix the login page so it remembers me")
    for short in ("yes", "go on", "  do it now  "):
        tree.started("main", root, short)
    ctx.check(f"short replies keep it, got {tree.row('main')['objective']!r}", tree.row("main")["objective"] == "Fix the login page so it remembers me")
    tree.started("main", root, "now write the release notes for it " + "x" * 300)
    ctx.check(f"capped as `task` is, got {len(tree.row('main')['objective'])}", len(tree.row("main")["objective"]) <= 120
              and tree.row("main")["objective"] == tree.row("main")["task"])
    _spawn(root, "h1", "Read the long report today")
    tree.started("h1", NS(model_ref=None), "Read the long report today please")
    ctx.check(f"a helper's row has no objective, got {tree.row('h1').get('objective')!r}", not tree.row("h1").get("objective"))


@test
def test_a_slash_command_sets_the_objective_from_what_was_typed(ctx: Ctx):
    """3.6.0.23 PV after the check: a skill's or a custom command's slash line sends main its EXPANDED body ("Base
    directory for this skill: <path>" first); the objective is the person's own words, the line he typed
    (controller.run_slash puts it on the turn's meta as `typed`), never the body's first line."""
    from halo_harness.controller import Controller
    sent: list = []
    body = "Base directory for this skill: /opt/skills/review/with/a/long/path\n\nReview the code: $ARGUMENTS"
    fake = NS(registry=NS(resolve=lambda n: NS(kind="prompt", source="skill", allowed_tools=None,
                                                run=lambda a, f: body)),
              facade=None, cwd=Path("."), session=NS(permission_engine=None, tool_env=None, mcp_manager=None,
                                                     queue_log_write=lambda *a, **k: None),
              submit=lambda text, images=None, pasted=None, meta=None: sent.append((text, meta)))
    out = Controller.run_slash(fake, "review", "the basket discount order")
    ctx.check(f"the expanded body goes to main as before, got {out!r} {sent}",
              out == "" and len(sent) == 1 and sent[0][0].startswith("Base directory for this skill:"))
    meta = sent[0][1] if sent else None
    ctx.check(f"the typed line rides the turn's meta, got {meta!r}",
              isinstance(meta, dict) and meta.get("typed") == "/review the basket discount order")
    root, tree = _tree()
    root._turn_meta = meta
    tree.started("main", root, sent[0][0] if sent else body)
    ctx.check(f"the objective is what he typed, got {tree.row('main').get('objective')!r}",
              tree.row("main").get("objective") == "/review the basket discount order")
    root._turn_meta = {"typed": "/review"}
    tree.started("main", root, body)
    ctx.check(f"a slash line under four words keeps it, got {tree.row('main').get('objective')!r}",
              tree.row("main").get("objective") == "/review the basket discount order")
    root._turn_meta = {"via": "studio"}
    tree.started("main", root, "Fix the login page so it remembers me")
    ctx.check(f"a plain prompt (no `typed`) is its own first line, got {tree.row('main').get('objective')!r}",
              tree.row("main").get("objective") == "Fix the login page so it remembers me")


@test
def test_a_spawn_keeps_the_words_of_its_parents_step_in_progress(ctx: Ctx):
    """3.6.0.23 PV ruling 5: an agent's `spawn.plan_step` is the WORDS of its parent's step in progress at its start,
    frozen (a list rewritten afterwards does not change them); none when the parent had no step in progress; an
    agent started by an agent gets its own parent's step, or none."""
    root, tree = _tree()
    tree.started("main", root, "review the three reports for me")
    _spawn(root, "a0", "Before any plan")
    _write_plan(tree, "main", [_todo("Read the reports", "completed"), _todo("Compare the numbers", "in_progress")], "t1")
    _spawn(root, "a1", "Compare report one")
    _write_plan(tree, "main", [_todo("Something else entirely", "in_progress")], "t2")
    _spawn(root, "a2", "Do the other thing")
    _write_plan(tree, "main", [_todo("All of it", "completed")], "t3")
    _spawn(root, "a3", "Tidy up")
    tree.started("a1", NS(model_ref=None), "Compare report one")
    child = NS(log=None, opt_ins=None, agent_id="a1", _agent_tree=tree)
    _write_plan(tree, "a1", [_todo("Open report one", "in_progress")], "c1")
    from halo_harness.agent.agent_hooks import register_child
    register_child(child, NS(log=None, opt_ins=None), agent_id="g1", spec=NS(name="general-purpose"), model=None, role=None, task_text="Count rows")
    register_child(NS(log=None, opt_ins=None, agent_id="a2", _agent_tree=tree), NS(log=None, opt_ins=None), agent_id="g2", spec=NS(name="general-purpose"),
                   model=None, role=None, task_text="Count more rows")
    rows = {r["agent_id"]: r for r in tree.public_rows()}
    got = {k: rows[k]["spawn"].get("plan_step") for k in ("a0", "a1", "a2", "a3", "g1", "g2")}
    ctx.check(f"each keeps the words of its parent's step at its start, got {got}", got == {
        "a0": None, "a1": "Compare the numbers", "a2": "Something else entirely", "a3": None,
        "g1": "Open report one", "g2": None})


@test
def test_a_list_over_the_cap_keeps_its_counts_and_the_step_in_progress(ctx: Ctx):
    """3.6.0.23 PV after the review, fault 4: a list of more than PLAN_MAX steps is never cut silently: the row carries
    the true counts (`plan_count`), each kept step its number `n`; the step in progress is always kept (the first
    PLAN_MAX - 1 and that one), so the hover and a spawn's `plan_step` see it."""
    from halo_harness.agent.agent_observe import PLAN_MAX
    root, tree = _tree()
    tree.started("main", root, "work through the long list today")
    todos = [_todo(f"step {i}", "completed" if i <= 10 else "pending") for i in range(1, 41)]
    todos[34] = _todo("step 35", "in_progress", "Doing step 35")
    _write_plan(tree, "main", todos, "t1")
    row = tree.row("main")
    ns = [t["n"] for t in row["plan"]]
    ctx.check(f"the true counts of the whole list, got {row.get('plan_count')}", row.get("plan_count") == {"all": 40, "done": 10})
    ctx.check(f"the first {PLAN_MAX - 1} and the step in progress, got {ns}", ns == list(range(1, PLAN_MAX)) + [35])
    ctx.check(f"the kept step in progress, got {row['plan'][-1]}", row["plan"][-1]["status"] == "in_progress" and row["plan"][-1]["content"] == "step 35")
    _spawn(root, "a1", "Help with step 35")
    ctx.check(f"a spawn past the cap gets its step, got {tree.row('a1')['spawn'].get('plan_step')!r}", tree.row("a1")["spawn"].get("plan_step") == "step 35")
    _write_plan(tree, "main", [_todo(f"s{i}") for i in range(1, 36)], "t2")
    row = tree.row("main")
    ctx.check(f"no step in progress: the first {PLAN_MAX}, counted all, got {len(row['plan'])} {row.get('plan_count')}",
              [t["n"] for t in row["plan"]] == list(range(1, PLAN_MAX + 1)) and row.get("plan_count") == {"all": 35, "done": 0})


def _real_session():
    """A real `agent.loop.Session` (tests/helpers/turn_session.py, its own scratch home); nothing here calls a model."""
    from tests.helpers.turn_session import new_session
    return new_session(mock=NS(base_url="http://127.0.0.1:9"), model="or:mock/pv-clear")


def _with_plan(tree, session) -> list:
    tree.started("main", session, "Fix the basket discount order today")
    _write_plan(tree, "main", [_todo("Read basket.py", "in_progress")], "t1")
    frames: list = []
    tree.add_listener(lambda k, a, d: frames.append((k, a, d)))
    return frames


def _check_empty(ctx: Ctx, tree, frames: list, what: str) -> None:
    row = tree.row("main")
    ctx.check(f"{what}: main's row has no plan and no objective, got {row.get('plan')!r} {row.get('objective')!r}",
              not row.get("plan") and not row.get("plan_count") and not row.get("objective"))
    ctx.check(f"{what}: the row's other fields stay, got {row.get('task')!r}", row.get("task") == "Fix the basket discount order today")
    pub = [d for k, a, d in frames if k == "agent_state" and a == "main"]
    ctx.check(f"{what}: the row is published, got {len(pub)}", bool(pub) and not pub[-1].get("plan") and not pub[-1].get("objective"))


@test
def test_clear_drops_mains_plan_and_objective(ctx: Ctx):
    """Fault 1 after the review: `/clear` starts a new conversation, so main's row starts empty ("none yet", "no plan yet")."""
    from halo_harness.agent.agent_registry import tree_for
    session = _real_session()
    tree = tree_for(session)
    frames = _with_plan(tree, session)
    session.clear()
    _check_empty(ctx, tree, frames, "after /clear")


@test
def test_an_in_app_resume_drops_mains_plan_and_objective(ctx: Ctx):
    """Fault 1 after the review: an in-app `/resume` (session_switch.pump_resume) switches the conversation: main's row
    starts empty (the resumed session's plan is not rebuilt in this release)."""
    from halo_harness.agent.agent_registry import tree_for
    from halo_harness.agent.session_switch import pump_resume
    session = _real_session()
    old = session.log.session_id
    session.log.append_user([{"type": "text", "text": "an earlier conversation"}])
    session.clear()
    tree = tree_for(session)
    frames = _with_plan(tree, session)
    said: list = []
    pump_resume(session, {"session_id": old}, said.append)
    ctx.check(f"the resume switched, got {session.log.session_id} / {[getattr(e, 'kind', '') for e in said]}", session.log.session_id == old)
    _check_empty(ctx, tree, frames, "after a resume")


@test
def test_a_steered_slash_line_keeps_what_was_typed_when_it_becomes_a_turn(ctx: Ctx):
    """Fault 3 after the review: a slash line typed while a turn runs is steered as its body; when no safe point took
    it, it is resubmitted as its own turn WITH its `typed` meta, so the objective is still his words."""
    import queue
    from halo_harness.agent.agent_registry import tree_for
    from halo_harness.controller import Controller
    session = _real_session()
    body = "Look over the code carefully: the basket discount order"
    session._busy.set()
    Controller.submit(NS(session=session, events=queue.Queue(), commands=queue.Queue()), body,
                      meta={"typed": "/pvcheck the basket discount order"})
    session._end_busy_period()
    commands: queue.Queue = queue.Queue()
    session._resubmit_leftover_steers(commands)
    cmd = commands.get_nowait()
    ctx.check(f"the text and its meta ride together, got {cmd.data}",
              cmd.data.get("text") == body and (cmd.data.get("meta") or {}).get("typed") == "/pvcheck the basket discount order")
    session._turn_meta = cmd.data.get("meta")  # what Session.run does with a `user_input`
    tree = tree_for(session)
    tree.started("main", session, body)
    ctx.check(f"the objective is what he typed, got {tree.row('main').get('objective')!r}",
              tree.row("main").get("objective") == "/pvcheck the basket discount order")


@test
def test_a_headless_slash_line_sets_the_objective_from_what_was_typed(ctx: Ctx):
    """Fault 2 after the review: `halo -p "/command args"` sends main the command's expanded body; the turn's meta
    carries the typed line, so main's objective is his words, never the body's first line."""
    import contextlib
    import io
    import os
    from halo_harness import headless
    from halo_harness.agent.agent_registry import tree_for
    from halo_harness.agent.loop import Session
    from tests.helpers.fake_home import build_fake_home
    from tests.helpers.mock_openai import SCENARIOS, MockUpstream, _finish
    fh = build_fake_home()
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_OPENROUTER_BASE_URL")}
    os.environ["BRIDGE_TEST_HOME"] = str(fh["home"])
    (Path(fh["proj"]) / ".claude" / "commands").mkdir(parents=True, exist_ok=True)
    (Path(fh["proj"]) / ".claude" / "commands" / "pvcheck.md").write_text("Look over the code carefully: $ARGUMENTS\n", encoding="utf-8")
    SCENARIOS["pv-headless"] = lambda h, body: _finish(h, [
        {"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
        {"choices": [{"index": 0, "delta": {"content": "PV-OK"}}]},
        {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}])
    mock = MockUpstream().start()
    seen: list = []
    real_turn = Session.turn

    def recording_turn(self, text, *a, **kw):
        seen.append((self, text))
        yield from real_turn(self, text, *a, **kw)
    Session.turn = recording_turn
    try:
        os.environ["BRIDGE_OPENROUTER_BASE_URL"] = mock.base_url
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            headless.run_print_mode(prompt="/pvcheck the basket discount order", cwd=fh["proj"],
                                    model_ref_raw="or:mock/pv-headless", max_turns=2)
    finally:
        Session.turn = real_turn
        mock.stop()
        for k, v in saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
    ctx.check(f"main was sent the expanded body, got {[t for _, t in seen]}", len(seen) == 1 and seen[0][1].startswith("Look over the code carefully"))
    obj = tree_for(seen[0][0]).row("main").get("objective") if seen else None
    ctx.check(f"the objective is what he typed, got {obj!r}", obj == "/pvcheck the basket discount order")


@test
def test_studio_groups_by_these_fields(ctx: Ctx):
    """The rule Studio draws by (routes/crew/live/groups.ts): siblings of one step, two or more, are a task group; a
    square's agent and the agents under it are its group; the rest of a lineup tier's agents are grouped by the tier."""
    src = (REPO / "halo_harness" / "studio" / "ui" / "src" / "routes" / "crew" / "live" / "groups.ts").read_text(encoding="utf-8")
    for needle in ("spawn?.step", "square", "tier", "MIN_TASK = 2"):
        ctx.check(f"groups.ts reads {needle!r}", needle in src)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
