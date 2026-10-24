"""tests.test_outcomes_rows_pick -- the outcome row knows it was a pick (Halo
3.1.9.0 R3, outcomes/records.py `picked` / `reason`):

1. `make_row`: `picked` is `auto`, `measured` or `none` (the default, and
   for a word it does not know), `reason` the pick's line ("" without one);
   an Orchestra lane's row says `none`;
2. a real session under the default auto lineup (a mocked upstream, the
   seeded index of tests/test_auto_spawn.py): a writer task's row says
   `picked: auto` with the agent row's own reason, which ends with what was
   learned for writing ("(writing 3/3 here)"); main's `model:` on the call
   leaves `picked: none` and no reason; a pick that does not resolve leaves
   `none` with the reason saying main's model ran it;
3. a `measured` card's row says `picked: measured`.
No real model call. Run: python -m tests.test_outcomes_rows_pick
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

ensure_default_provider_credentials()
test, TESTS = new_registry()


def _seed_recent(state_dir, model: str, kind: str, outcomes: list) -> None:
    """Checked rows from the last hour (inside the learning window)."""
    import time
    from halo_harness.outcomes.records import append, make_row
    now = time.time()
    append([make_row(run="seed", task=f"agent seed-{i}", source="session", model=model, kind=kind, outcome=o,
                     check="acceptance", ts=now - 600 + i) for i, o in enumerate(outcomes)], state_dir)


def _row_for(state_dir, agent_id: str) -> dict:
    from halo_harness.outcomes.records import read
    return next((r for r in read(state_dir) if r.get("task") == f"agent {agent_id}"), {})


@test
def test_make_row_carries_picked_and_reason(ctx: Ctx):
    from halo_harness.outcomes.records import make_row
    plain = make_row(run="r", task="t", source="session", outcome="passed", check="acceptance")
    ctx.check(f"no pick: picked none, reason empty, got {plain.get('picked')!r} {plain.get('reason')!r}",
              plain["picked"] == "none" and plain["reason"] == "")
    auto = make_row(run="r", task="t", source="session", outcome="passed", picked="auto", reason="an image in the task, ...")
    ctx.check("a pick: its word and its line", auto["picked"] == "auto" and auto["reason"] == "an image in the task, ...")
    odd = make_row(run="r", task="t", source="session", outcome="done", picked="guessed")
    ctx.check("a word it does not know reads none", odd["picked"] == "none")
    keys = list(plain)
    ctx.check(f"the two new keys come last; nothing else changed, got {keys}",
              keys[-2:] == ["picked", "reason"] and keys[:-2] == ["run", "task", "source", "run_dir", "bio", "model", "kind",
                                                                  "outcome", "check", "returns", "cost_usd", "tests_passed",
                                                                  "tests_failed", "sources", "evidence", "ts"])
    # an Orchestra lane's row is make_row's too (records.orchestra_rows)
    lane = make_row(run="run", task="lane 1", source="orchestra", outcome="passed", check="gate", report_ts=1.0)
    ctx.check("an Orchestra lane's row says none", lane["picked"] == "none" and lane["report_ts"] == 1.0)


@test
def test_a_spawned_members_row_says_how_its_model_was_picked(ctx: Ctx):
    from tests import test_auto_spawn as A
    mock = A._mock()
    saved = {k: os.environ.pop(k) for k in ("OPENAI_API_KEY", "OPENAI_BASE_URL") if k in os.environ}
    try:
        with A._Env() as e:
            A._seed_index(e.state_dir, A.ROWS)
            _seed_recent(e.state_dir, "or:mock/auto-cheap", "writing", ["passed"] * 3)
            session = A._session(e, mock)
            A._dispatch(session, "c1", "Summarize notes.md in two lines", description="summarize the notes")
            agent = A._child(session, "c1").get("row") or {}
            picked = _row_for(e.state_dir, agent.get("agent_id", "?"))
            A._dispatch(session, "c2", "Summarize notes.md", description="summarize the notes", model="or:mock/auto-override")
            over = _row_for(e.state_dir, (A._child(session, "c2").get("row") or {}).get("agent_id", "?"))
            eyes = {"kinds": ["visual"], "scores": {"visual": 0.9}, "facts": A._facts(0.1, 0.1, ["text", "image"])}
            A._seed_index(e.state_dir, {"oai:gpt-eyes": eyes})
            session = A._session(e, mock)
            A._dispatch(session, "c3", "Look at shot.png", description="describe the screenshot")
            fell = _row_for(e.state_dir, (A._child(session, "c3").get("row") or {}).get("agent_id", "?"))
    finally:
        os.environ.update(saved)
        mock.stop()
    ctx.check(f"the writer's pick learned from writing 3/3, got {agent.get('model_reason')!r}",
              agent.get("model") == "or:mock/auto-cheap" and str(agent.get("model_reason")).endswith("(writing 3/3 here)"))
    ctx.check(f"its outcome row: picked auto and the same reason, got {picked.get('picked')!r} {picked.get('reason')!r}",
              picked.get("picked") == "auto" and picked.get("reason") == agent.get("model_reason")
              and picked.get("kind") == "writing" and picked.get("model") == "or:mock/auto-cheap")
    ctx.check(f"main's model: on the call -- picked none, no reason, got {over.get('picked')!r} {over.get('reason')!r}",
              over.get("picked") == "none" and over.get("reason") == "" and over.get("model") == "or:mock/auto-override")
    ctx.check(f"a pick that did not resolve -- none, the reason saying main's ran it, got {fell.get('picked')!r} "
              f"{fell.get('reason')!r}", fell.get("picked") == "none"
              and fell.get("reason") == "oai:gpt-eyes has no credentials here; using main's")


@test
def test_a_measured_cards_row_says_measured(ctx: Ctx):
    from tests import test_auto_spawn as A
    from tests.test_outcomes_measured import seed_outcomes
    from halo_harness.agents_yaml import save_agent_bio
    from halo_harness.teams_yaml import save_team_template
    from halo_harness.theme import set_config_value
    mock = A._mock()
    try:
        with A._Env() as e:
            A._seed_index(e.state_dir, A.ROWS)
            save_agent_bio("measured-coder", {"description": "routes by what succeeded", "kind": "coder",
                                              "models": {"preference": "measured", "needs": ["tools"]}}, state_dir=e.state_dir)
            save_team_template("measured", {"description": "a measured coder", "routing": {"fix": "coder"},
                                            "agents": [{"agent": "default-model", "role": "main"},
                                                       {"agent": "measured-coder", "role": "coder"}]}, state_dir=e.state_dir)
            set_config_value("team", "measured")
            seed_outcomes(e.state_dir, "or:mock/auto-eyes", "code", ["passed", "passed", "passed", "failed"])
            session = A._session(e, mock)
            A._dispatch(session, "c1", "fix the bug in basket.py", description="fix the bug")
            agent = A._child(session, "c1").get("row") or {}
            row = _row_for(e.state_dir, agent.get("agent_id", "?"))
    finally:
        mock.stop()
    ctx.check(f"the measured pick ran it, got {agent.get('model')!r} {agent.get('model_reason')!r}",
              agent.get("model") == "or:mock/auto-eyes" and str(agent.get("model_reason")).endswith("(measured 3/4 code)"))
    ctx.check(f"its row: picked measured, the reason, got {row.get('picked')!r} {row.get('reason')!r}",
              row.get("picked") == "measured" and row.get("reason") == agent.get("model_reason"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
