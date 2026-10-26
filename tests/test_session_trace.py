"""tests.test_session_trace -- Halo 3.3.0.0 R6: a session as one Markdown
trace (halo_harness/session_trace.py; the owner: "an export button that saves
it as an .md file, like a tracer file so we can save detailed logs of
sessions").

A seeded session log with every row kind once (a user prompt, the
assistant's text, a tool call, its 60-line result carrying a fake key and a
home path, a steer, a nudge, a compaction, an error, the usage, and the
turn's timeline with a permission answer and the turn-end marker): the trace
has each once, in time order, the totals right, the key masked, the home
path as ~, the result trimmed to 40 lines with "... (20 more lines)", and
the privacy scan finds nothing in it. `halo session export <id> --md -`,
`--md FILE`, Studio's `GET sessions/<sid>/trace.md` and `/export`
(Controller.export_session) give the same bytes; a sub-agent's rows carry
its name, model and lineup; the turn timeline keeps the turn-end marker.
Run: python -m tests.test_session_trace
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
FAKE_KEY = "sk-or-v1-" + "a1b2c3d4" * 4  # built here: never a key-shaped literal in the tree
SID = "trace0001"
T0 = 1_790_000_000.0
KINDS = ["user prompt", "assistant text", "tool call: Bash (pytest -q)", "tool result: Bash", "steer to main", "nudge",
         "compaction (auto)", "error (error)", "permission answer: allow", "turn end (done)"]


@contextlib.contextmanager
def _home():
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
    with tempfile.TemporaryDirectory(prefix="halo-trace-") as d:
        os.environ["BRIDGE_TEST_HOME"] = d
        os.environ.pop("BRIDGE_STATE_DIR", None)
        try:
            yield Path(d)
        finally:
            for k, v in saved.items():
                os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


def _seed(home: Path):
    from halo_harness.agent.log import SessionLog
    from halo_harness.agent.turn_marker import NUDGE_TEXT
    (home / "proj").mkdir(exist_ok=True)
    log = SessionLog(home / "proj", session_id=SID)
    result = "\n".join([f"LINE-{i:03d} ok" for i in range(1, 61)])
    result = result.replace("LINE-002 ok", f"LINE-002 OPENROUTER_API_KEY={FAKE_KEY} token {FAKE_KEY}")
    result = result.replace("LINE-003 ok", f"LINE-003 {Path.home() / 'projects' / 'basket' / 'basket.py'}")
    put = lambda dt, node: log._append({**node, "ts": T0 + dt})  # noqa: E731
    put(0, {"type": "meta", "model": "or:mock/glm-5-coder", "cwd": str(home / "proj")})
    put(1, {"type": "user", "content": [{"type": "text", "text": "PROMPT-1 fix the basket discount"}]})
    put(2, {"type": "assistant", "content": [{"type": "text", "text": "TEXT-1 I run the suite first."},
                                             {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "pytest -q"}}]})
    put(3, {"type": "tool_result", "tool_use_id": "t1", "content": result, "is_error": False})
    put(4, {"type": "user", "kind": "steer", "content": [{"type": "text", "text": "STEER-1 check the tax rule"}]})
    put(5, {"type": "user", "kind": "nudge", "content": [{"type": "text", "text": NUDGE_TEXT}]})
    put(6, {"type": "compacted", "trigger": "auto", "surface_op": "replace"})
    put(7, {"type": "error", "message": "ERR-1 the model call failed", "err_type": "error"})
    put(8, {"type": "usage", "usage": {"input_tokens": 1200, "output_tokens": 300}, "cost_usd": 0.0123})
    put(9, {"type": "usage", "usage": {"input_tokens": 800, "output_tokens": 200}, "cost_usd": 0.01})
    put(20, {"type": "meta", "timeline": {"turn": 1, "message_end_ms": 5000, "tools": [{"name": "Bash"}],
                                          "permission_waits": [{"start_ms": 1000, "end_ms": 3000, "decision": "allow"}],
                                          "marker": {"state": "done", "text": "◼ done · 5 s · 1 tool"}}})
    return log


def _trace(home: Path) -> "tuple[str, object]":
    from halo_harness.session_trace_cli import trace_for_path
    log = _seed(home)
    return trace_for_path(log.path), log


def _headings(text: str) -> list:
    return [ln for ln in text.split("\n") if ln.startswith("### ")]


@test
def test_every_kind_once_in_time_order(ctx: Ctx):
    with _home() as home:
        text, _ = _trace(home)
    heads = _headings(text)
    ctx.check(f"ten rows, got {len(heads)}: {heads}", len(heads) == 10)
    got = [next((k for k in KINDS if h.endswith(" · " + k) or (" · " + k) in h), "?") for h in heads]
    ctx.check(f"each kind once, in time order, got {got}", got == KINDS)
    ctx.check("each heading leads with the clock and the agent with its model",
              all(re.match(r"^### \d\d:\d\d:\d\d · main \(or:mock/glm-5-coder\) · ", h) for h in heads))
    ctx.check("the steer, the nudge and the marker carry their text",
              "STEER-1 check the tax rule" in text and "Continue." in text and "◼ done · 5 s · 1 tool" in text)


@test
def test_the_header_and_its_totals(ctx: Ctx):
    with _home() as home:
        text, _ = _trace(home)
    ctx.check("the title names the session", text.startswith(f"# Halo trace: session {SID}\n"))
    ctx.check("the model and the lineup", "- Model: or:mock/glm-5-coder · lineup: not recorded" in text)
    ctx.check("started and ended", re.search(r"- Started: \d{4}-\d\d-\d\d \d\d:\d\d:\d\d · ended: \d{4}-\d\d-\d\d \d\d:\d\d:\d\d", text) is not None)
    ctx.check(f"the totals, got {[ln for ln in text.splitlines() if 'Totals' in ln]}",
              "- Totals: turns 1 · tool calls 1 · tokens in 2000 · tokens out 500 · cost $0.0223" in text)


@test
def test_the_result_is_trimmed_fenced_and_masked(ctx: Ctx):
    with _home() as home:
        text, _ = _trace(home)
    ctx.check("the result is in a fenced block", "```text\nLINE-001 ok" in text)
    ctx.check("40 lines, then the count of the rest", "LINE-040 ok\n... (20 more lines)\n```" in text and "LINE-041" not in text)
    ctx.check("the fake key is masked", FAKE_KEY not in text and "<redacted>" in text)
    ctx.check("the home path reads ~", str(Path.home()) not in text and "~" in text and "basket.py" in text)
    from halo_harness.privacy_scan import scan_text_content
    raw = scan_text_content(f"{FAKE_KEY} {Path.home()}/x", rel_path="trace.md", allowlist=set())
    found = scan_text_content(text, rel_path="trace.md", allowlist=set())
    ctx.check(f"the privacy scan finds the raw key, and nothing in the trace, got {found}", raw and not found)


def _cli(argv: list) -> "tuple[int, bytes]":
    from halo_harness.session_trace_cli import cmd_session
    raw = io.BytesIO()
    out = io.TextIOWrapper(raw, encoding="utf-8")
    saved = sys.stdout
    sys.stdout = out
    try:
        rc = cmd_session(argv)
        out.flush()
    finally:
        sys.stdout = saved
    return rc, raw.getvalue()


@test
def test_the_cli_the_route_and_export_give_the_same_bytes(ctx: Ctx):
    from halo_harness.controller import Controller
    from halo_harness.studio import sessions_api
    with _home() as home:
        text, log = _trace(home)
        rc, printed = _cli(["export", SID, "--md", "-"])
        ctx.check(f"`--md -` prints the trace, rc {rc}", rc == 0 and printed == text.encode("utf-8"))
        rc2, _ = _cli(["export", SID[:6], "--md", str(home / "out.md")])
        ctx.check("a prefix finds it; `--md FILE` writes the same bytes", rc2 == 0 and (home / "out.md").read_bytes() == printed)
        req = SimpleNamespace(method="GET", path=f"sessions/{SID}/trace.md", params={}, body={}, query={})
        status, body = sessions_api.dispatch_sessions(req)
        ctx.check(f"GET sessions/<sid>/trace.md: 200 text/markdown, the same bytes, got {status}",
                  status == 200 and body.body == printed and body.ctype.startswith("text/markdown"))
        missing = sessions_api.dispatch_sessions(SimpleNamespace(method="GET", path="sessions/nope404/trace.md", params={}, body={}, query={}))
        ctx.check(f"an unknown session is a 404, got {missing[0]}", missing[0] == 404)
        wrote = Path(Controller.export_session(SimpleNamespace(session=SimpleNamespace(log=log))))
        ctx.check(f"/export writes beside the session log as halo-trace-<id>-<stamp>.md, got {wrote.name}",
                  wrote.parent == log.path.parent and re.fullmatch(rf"halo-trace-{SID}-\d{{4}}-\d\d-\d\d-\d{{4}}\.md", wrote.name) is not None)
        ctx.check("/export's bytes are the CLI's", wrote.read_bytes() == printed)
        rc3, _ = _cli(["export", "zz-none"])
        ctx.check("an unknown id exits 1", rc3 == 1)


@test
def test_a_sub_agents_rows_carry_its_name_model_and_lineup(ctx: Ctx):
    from halo_harness.session_trace_cli import trace_for_path
    with _home() as home:
        log = _seed(home)
        sub = log.path.parent / SID / "subagents"
        sub.mkdir(parents=True)
        (sub / "agent-ab12cd34.meta.json").write_text(json.dumps({"agent_id": "ab12cd34", "type": "general-purpose", "role": "coder",
                                                                  "model": "or:mock/qwen3-coder", "lineup": "halo-dev-cycle"}), encoding="utf-8")
        rows = [{"type": "user", "kind": "steer", "content": [{"type": "text", "text": "SUB-STEER use Decimal"}], "ts": T0 + 2.5},
                {"type": "assistant", "content": [{"type": "text", "text": "SUB-TEXT done"}], "ts": T0 + 2.6}]
        (sub / "agent-ab12cd34.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        text = trace_for_path(log.path)
    heads = _headings(text)
    ctx.check("the lineup is in the header", "lineup: halo-dev-cycle" in text)
    sub_heads = [h for h in heads if " · coder (or:mock/qwen3-coder) · " in h]
    ctx.check(f"the sub-agent's two rows, its steer named for it, got {sub_heads}",
              len(sub_heads) == 2 and sub_heads[0].endswith("steer to coder") and sub_heads[1].endswith("assistant text"))
    ctx.check("they sit in time order between main's tool call and its result",
              heads.index(sub_heads[0]) == 3 and "tool result" in heads[5])


@test
def test_the_turn_timeline_keeps_the_turn_end_marker(ctx: Ctx):
    from halo_harness import events
    from halo_harness.debug_timeline import TurnTimeline
    tl = TurnTimeline()
    tl.start_turn(1)
    tl.record_turn_event(events.turn_marker("waiting", "◼ waiting on you: permission for Bash", ask="permission", mid_turn=True))
    tl.record_turn_event(events.turn_marker("done", "◼ done · 3 s · 2 tools", tools=2))
    rec = tl.end_turn()
    ctx.check(f"the end marker is recorded, a mid-turn one is not, got {rec.get('marker')}",
              rec.get("marker") == {"state": "done", "text": "◼ done · 3 s · 2 tools"})
    from halo_harness.session_trace import trim, arg_summary
    ctx.check("a record without a marker reads as the done line", "◼ done" in __import__("halo_harness.session_trace", fromlist=["x"])._turn_rows(
        {"message_end_ms": 4000, "tools": [1]}, T0)[-1][3])
    ctx.check("trim keeps short text whole", trim("a\nb") == "a\nb")
    ctx.check("an argument summary is one line", arg_summary({"file_path": "a.py\nb"}) == "a.py b")


@test
def test_the_download_name(ctx: Ctx):
    from halo_harness.session_trace_cli import trace_name
    ctx.check("halo-trace-<id>-<yyyy-mm-dd-hhmm>.md", re.fullmatch(r"halo-trace-abc-\d{4}-\d\d-\d\d-\d{4}\.md", trace_name("abc")) is not None)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
