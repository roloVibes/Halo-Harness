"""halo_harness.replay -- Halo 2.0.6 round 4: session replay for model
swaps.

The v2.0.4 model review's item 3: "record a native transcript, replay it
against a different model with the same tools and the same transcript
prefix, compare the outcomes side by side ('did swapping the researcher
from one model to another help?' answered with a diff). This extends the
gym from synthetic evals to real task history."

The primitive is the proven resume path, not a new engine: `fork_session`
copies the log under a fresh id, the fork is TRUNCATED to just before the
target turn's user node (everything before it becomes the shared prefix),
and the target turn's own original prompt is re-sent through plain print
mode against the swapped model -- same cwd, same tools, same hooks, same
everything `halo -p` already does. The ORIGINAL session file is never
appended to (fork-first, exactly like `--fork-session`).

A turn is a REAL user prompt (not a notice/command) plus everything the
session did until the next real prompt. `--turn N` replays turn N
(1-based, default 1 -- "the task, fresh"); the comparison is the
original's turn-N outcome vs the replay's.
"""

from __future__ import annotations

import difflib
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from halo_harness.agent import sessions as agent_sessions

# Mirrors controller.py's own _NON_PROMPT_USER_KINDS (kept local on
# purpose: that set is controller-internal and this module must not drag
# the TUI/controller import graph into a CLI-only path).
# review finding 86: the kinds the log actually writes (compaction summary
# and re-appended tail, continuation, background agent/job notices, steer)
# are telemetry's set; the older names below stay for logs that used them.
from halo_harness.telemetry import _NON_PROMPT_USER_KINDS as _LOGGED_NON_PROMPT_KINDS
from halo_harness.textlines import split_lines

_NON_PROMPT_USER_KINDS = _LOGGED_NON_PROMPT_KINDS | frozenset({
    "command", "notice", "subagent", "tool_result", "interrupt", "compact",
    "steer", "system", "error",
})


@dataclass
class ReplayTurn:
    index: int                      # 1-based
    user_text: str
    node_line: int                  # the user node's 0-based line in the file
    assistant_text: str = ""
    tool_names: list = field(default_factory=list)
    cost_usd: Optional[float] = None
    tokens_in: int = 0
    tokens_out: int = 0


def parse_turns(log_path: Path) -> "list[ReplayTurn]":
    """The session's real turns, in order. `node_line` is the user node's
    own line index -- the truncation point for a replay of THAT turn is
    the byte offset of the line AFTER everything before it (see
    `replay_session`)."""
    turns: "list[ReplayTurn]" = []
    current: Optional[ReplayTurn] = None
    try:
        lines = split_lines(log_path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return []
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            node = json.loads(line)
        except ValueError:
            continue
        ntype = node.get("type")
        if ntype == "user" and node.get("kind") not in _NON_PROMPT_USER_KINDS:
            raw = node.get("text")
            if not isinstance(raw, str):
                raw = node.get("content")
            if isinstance(raw, str):
                text = raw
            elif isinstance(raw, list):
                # a child session's own user nodes carry content BLOCKS
                text = "".join(b.get("text", "") for b in raw
                               if isinstance(b, dict) and b.get("type") == "text")
            else:
                text = ""
            if current is not None:
                turns.append(current)
            current = ReplayTurn(index=len(turns) + 1, user_text=text.strip(), node_line=i)
        elif current is not None and ntype == "assistant":
            for block in node.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "text":
                    current.assistant_text += block.get("text", "")
                elif isinstance(block, dict) and block.get("type") == "tool_use":
                    current.tool_names.append(block.get("name", "?"))
        elif current is not None and ntype == "usage":
            usage = node.get("usage") or {}
            current.tokens_in += int(usage.get("input_tokens") or 0)
            current.tokens_out += int(usage.get("output_tokens") or 0)
            cost = node.get("cost_usd")
            if isinstance(cost, (int, float)):
                current.cost_usd = (current.cost_usd or 0.0) + cost
    if current is not None:
        turns.append(current)
    return turns


def _truncate_fork(fork_path: Path, keep_lines: int) -> None:
    """Cut the fork's file down to its first `keep_lines` lines -- the
    shared prefix everything before the target turn produced."""
    lines = split_lines(fork_path.read_text(encoding="utf-8", errors="replace"), keepends=True)
    fork_path.write_text("".join(lines[:keep_lines]), encoding="utf-8")


def _first_divergence(a: str, b: str) -> "Optional[int]":
    """1-based line number of the first differing line, None when the
    texts are identical (an empty text vs a non-empty one diverges at
    line 1). A plain line-by-line compare -- ndiff's own interleaved
    output would make the number lie about WHICH line diverged."""
    if a == b:
        return None
    la, lb = a.splitlines(), b.splitlines()
    for i in range(max(len(la), len(lb))):
        if i >= len(la) or i >= len(lb) or la[i] != lb[i]:
            return i + 1
    return 1


def replay_session(cwd, session_id: str, *, model: str, turn: Optional[int] = None,
                   max_turns: int = 10, timeout: float = 600.0,
                   extra_env: "Optional[dict]" = None,
                   python: "Optional[str]" = None) -> dict:
    """Fork `session_id`, truncate the fork to just before turn N's user
    node, re-send that turn's own prompt against `model` through print
    mode, and return the side-by-side report. The original file is never
    touched (the fork is a byte copy, per `fork_session`)."""
    log_path = agent_sessions.sessions_dir(cwd) / f"{session_id}.jsonl"
    turns = parse_turns(log_path)
    if not turns:
        return {"ok": False, "error": f"session {session_id} has no replayable turns"}
    target = turns[0] if turn is None else turns[turn - 1] if 1 <= (turn or 0) <= len(turns) else None
    if target is None:
        return {"ok": False, "error": f"turn {turn} out of range (1..{len(turns)})"}

    fork_id = agent_sessions.fork_session(cwd, session_id)
    fork_path = agent_sessions.sessions_dir(cwd) / f"{fork_id}.jsonl"
    _truncate_fork(fork_path, keep_lines=target.node_line)

    env = dict(__import__("os").environ)
    if extra_env:
        env.update(extra_env)
    argv = [python or sys.executable, "-m", "halo_harness", "-p", target.user_text,
            "--model", model, "--cwd", str(cwd), "--session-id", fork_id,
            "--max-turns", str(max_turns)]
    try:
        proc = subprocess.run(argv, env=env, cwd=str(cwd), capture_output=True, text=True,
                              timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"the replay run timed out after {timeout:.0f}s"}

    replay_turns = parse_turns(fork_path)
    replay_turn = replay_turns[-1] if replay_turns else None
    report = {
        "ok": proc.returncode == 0 and replay_turn is not None,
        "session_id": session_id, "fork_id": fork_id,
        "turn": target.index, "turns_total": len(turns),
        "original": _turn_summary(target),
        "replay": _turn_summary(replay_turn) if replay_turn else None,
        "replay_exit": proc.returncode,
        "replay_stderr_tail": (proc.stderr or "")[-400:],
    }
    if replay_turn is not None:
        div = _first_divergence(target.assistant_text.strip(), replay_turn.assistant_text.strip())
        report["same_answer"] = div is None
        report["first_divergence_line"] = div
    return report


def _turn_summary(t: ReplayTurn) -> dict:
    return {"user": t.user_text[:120], "assistant_chars": len(t.assistant_text.strip()),
            "tools": sorted(set(t.tool_names)), "tokens_in": t.tokens_in, "tokens_out": t.tokens_out,
            "cost_usd": round(t.cost_usd, 6) if t.cost_usd is not None else None}


def format_report(r: dict) -> str:
    """The human side-by-side (the CLI's default output; --json prints the
    dict raw)."""
    if not r.get("ok"):
        detail = r.get("error") or f"replay run exit {r.get('replay_exit')}"
        return f"replay failed: {detail}"
    o, p = r["original"], r["replay"] or {}
    lines = [f"replay of session {r['session_id']} turn {r['turn']}/{r['turns_total']}"
             f" (fork {r['fork_id']})"]
    lines.append(f"  original: {o['assistant_chars']} chars, {o['tokens_in']}in/{o['tokens_out']}out tok, "
                 f"${(o['cost_usd'] or 0.0):.4f}, tools: {', '.join(o['tools']) or '-'}")
    lines.append(f"  replay:   {p.get('assistant_chars', 0)} chars, {p.get('tokens_in', 0)}in/"
                 f"{p.get('tokens_out', 0)}out tok, ${p.get('cost_usd') or 0.0:.4f}, "
                 f"tools: {', '.join(p.get('tools') or []) or '-'}")
    if r.get("same_answer"):
        lines.append("  final answer: SAME")
    else:
        lines.append(f"  final answer: DIFFERENT (first divergence at line {r.get('first_divergence_line')})")
    return "\n".join(lines)
