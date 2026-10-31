"""tests.test_postmortem -- Halo 3.3.6.0 R4 deliverable 5, the answer post-mortem (agent/postmortem.py,
studio/postmortem_api.py, `halo session postmortem`, `/why`), through the loop rig (a real Session over a fake
Ollama on 127.0.0.1:0) and fixture ledger lines for its turns:

1. a healthy turn: "nothing cut; 92 % of the prompt reused from cache", the details (model, host, the prompt's
   parts, tools, the dialect in force);
2. each cause reconstructed: the prompt cut (where, how much), an empty reply from a small budget (num_predict hit),
   thinking only (the transcript), memory-dominated, no tools offered; the ladder's rungs in the details;
3. the turn picked by number or by time (a Live row's `at`); a turn with no local call says so;
4. `/why [turn]` in the TUI's command set, `halo session postmortem --turn N [--json]`, GET sessions/<sid>/postmortem.
Run: python -m tests.test_postmortem
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402

ensure_default_provider_credentials()
from tests.helpers.model_switch_rig import Rig  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.test_dialect_loop import reply, say, script  # noqa: E402

test, TESTS = new_registry()
COMP = {"system": 3500, "memory": 900, "topic_index": 300, "tools_schema": 2100, "history": 1200, "user": 40, "total": 8040}


def _line(rig, sid: str, turn: int, ago: float = 30.0, **kw) -> None:
    from halo_harness.ollama_steward.ledger import blank_line, now_iso, record_call
    base = {"host": {"name": "lan", "url": rig.mock.base_url}, "model": "mid:14b", "kind": "turn", "status": 200,
            "session": sid, "turn": turn, "num_ctx_sent": 32768, "estimate_tokens": 9064, "prompt_eval_count": 640,
            "eval_count": 120, "done_reason": "stop", "tools_count": 12, "composition": COMP, "cache_reused_pct": 92,
            "dialect_record": {"placement": "system", "reserve": 1024, "repair": 1, "guard": False, "thinking": "native"},
            "at": now_iso(time.time() - ago)}
    record_call(rig.state_dir, blank_line(**{**base, **kw}))


@test
def test_a_healthy_turn_and_the_details(ctx: Ctx):
    from halo_harness.agent.postmortem import postmortem
    with Rig() as rig:
        rig.mock.scenarios["mid:14b"] = script([reply("fine")])
        s = rig.session("ol:mid:14b@lan")
        rig.run(s, [say("hello")])
        sid = s.log.session_id
        real = postmortem(rig.state_dir, sid, nodes=s.log.nodes())
        ctx.check(f"the session's own turn reconstructed from its ledger line, got {real}", real["ok"] and real["turn"] == 1
                  and real["model"] == "mid:14b" and real["host"] == "lan")
        _line(rig, "fx-healthy", 1)
        got = postmortem(rig.state_dir, "fx-healthy", nodes=[])
        ctx.check(f"the healthy line, got {got['line']!r}", got["line"] == "nothing cut; 92 % of the prompt reused from cache")
        d = "\n".join(got["details"])
        ctx.check(f"the details: model and host, the parts, tools, the dialect, got {d!r}",
                  "mid:14b on lan, turn 1, 1 call" in d and "prompt 8,040: system 3,500 · memory 900" in d
                  and "tools offered: 12" in d and "dialect in force: instructions in system" in d)


@test
def test_each_cause(ctx: Ctx):
    from halo_harness.agent.postmortem import postmortem
    with Rig() as rig:
        _line(rig, "fx", 1, trimmed=True, prompt_eval_count=16386, estimate_tokens=30756, log_events=["prompt-trimmed"])
        cut = postmortem(rig.state_dir, "fx", turn=1, nodes=[])
        ctx.check(f"cut: where and how much, got {cut['line']!r}", cut["line"].startswith("the prompt was cut at 16,386 of 32,768")
                  and "about 14,370 tokens were dropped" in cut["line"] and "task summary at the front was dropped" in cut["line"])
        _line(rig, "fx", 2, done_reason="length", eval_count=256, tools_count=0, body_flags={"tools": False})
        budget = postmortem(rig.state_dir, "fx", turn=2, nodes=[])
        ctx.check(f"an empty reply from a small budget, and no tools, got {budget['line']!r}",
                  budget["line"].startswith("the reply hit its budget (256 tokens, num_predict)")
                  and "no tools were offered" in budget["line"])
        _line(rig, "fx", 3, composition={**COMP, "memory": 6000, "topic_index": 900, "total": 9000})
        mem = postmortem(rig.state_dir, "fx", turn=3, nodes=[])
        ctx.check(f"memory-dominated, got {mem['line']!r}", mem["line"].startswith("memory was 77% of the prompt (6,900 of 9,000"))
        nodes = [{"type": "user", "content": [{"type": "text", "text": "one"}]},
                 {"type": "assistant", "content": [{"type": "text", "text": "a"}]},
                 {"type": "user", "content": [{"type": "text", "text": "two"}]},
                 {"type": "assistant", "content": [{"type": "thinking", "text": "long thought"}, {"type": "text", "text": " "}]}]
        _line(rig, "fx", 2, ago=5, ladder=[{"rung": "repair", "trigger": "empty", "line": "rung 1: repair -- asked again"}],
              loop=True)
        think = postmortem(rig.state_dir, "fx", turn=2, nodes=nodes)
        ctx.check(f"thinking only from the transcript, got {think['causes'].get('thinking_only')}",
                  "thinking_only" in think["causes"] and think["calls"] == 2)
        ctx.check(f"the ladder and the loop in the details, got {think['details'][-3:]}",
                  "ladder: rung 1: repair -- asked again" in think["details"]
                  and "the loop guard saw it repeat itself" in think["details"])
        at = postmortem(rig.state_dir, "fx", at=time.time() - 25, nodes=[])
        ctx.check(f"the turn picked by time (a Live row), got turn {at['turn']}", at["turn"] in (1, 2, 3) and at["ok"])
        none = postmortem(rig.state_dir, "no-such-session")
        ctx.check(f"no local call: said, got {none['line']!r}", not none["ok"] and "no local call is recorded" in none["line"])


@test
def test_why_the_cli_and_the_route(ctx: Ctx):
    from halo_harness.commands.builtins import HeadlessFacade, _cmd_why
    from halo_harness.session_trace_cli import cmd_session
    from halo_harness.studio.api import Request, dispatch
    with Rig() as rig:
        rig.mock.scenarios["mid:14b"] = script([reply("fine"), reply("again")])
        s = rig.session("ol:mid:14b@lan")
        rig.run(s, [say("hello"), say("and again")])
        sid = s.log.session_id
        out = _cmd_why("", HeadlessFacade(cwd=Path(rig.fh["proj"]), session=s))
        ctx.check(f"/why: the newest turn, got {out!r}", out.startswith("turn 2: ") and "mid:14b on lan, turn 2" in out)
        out = _cmd_why("1", HeadlessFacade(cwd=Path(rig.fh["proj"]), session=s))
        ctx.check(f"/why 1, got {out[:40]!r}", out.startswith("turn 1: "))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = cmd_session(["postmortem", "--session", sid, "--turn", "1", "--json"])
        got = json.loads(buf.getvalue())
        ctx.check(f"halo session postmortem --json, got {rc} {got.get('turn')}", rc == 0 and got["turn"] == 1 and got["ok"])
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = cmd_session(["postmortem"])
        ctx.check(f"no session: the newest that called a local model, got {buf.getvalue()[:60]!r}",
                  rc == 0 and buf.getvalue().startswith(f"turn 2 of {sid}: "))
        code, body = dispatch(Request(method="GET", path=f"sessions/{sid}/postmortem", query={"turn": "1"}, body={},
                                      cwd=Path(rig.fh["proj"]), state_dir=rig.state_dir, server=None))
        ctx.check(f"GET sessions/<sid>/postmortem, got {code} {body.get('cli')}", code == 200 and body["turn"] == 1
                  and body["cli"] == f"halo session postmortem --session {sid} --turn 1")
        code, body = dispatch(Request(method="GET", path=f"sessions/{sid}/postmortem", query={"agent": "abc123"}, body={},
                                      cwd=Path(rig.fh["proj"]), state_dir=rig.state_dir, server=None))
        ctx.check(f"a sub-agent with no local call: ok false, said, got {code} {body.get('line')!r}",
                  code == 200 and body["ok"] is False and body["session"] == "agent-abc123")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
