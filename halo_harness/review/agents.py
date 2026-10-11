"""halo_harness.review.agents -- the review sub-agents and how one child runs.

Reviewers and the judge are read-only (`Read`, `Glob`, `Grep`, `Bash` with
read-only commands, no Edit/Write); the fixer is a full-tool coder. All run
through the ordinary sub-agent runtime (`agent.subagent.run_agent_call`), so
the model comes from the `reviewer` / `judge` / `coder` roles, the session's
concurrency gate bounds them, costs roll up into the session, and they show in
`/tasks`.
"""

from __future__ import annotations

import dataclasses
import re
import threading
from dataclasses import dataclass
from typing import Callable, Optional

from halo_harness import events
from halo_harness.config.agents_md import AgentSpec
from halo_harness.review.dimensions import prompt_text

READ_ONLY_TOOLS = ["Read", "Glob", "Grep", "Bash"]
JUDGE_NAME = "review-judge"
FIXER_NAME = "review-fixer"

_TASK_HEAD = re.compile(r'^\s*<task_result task_id="([^"]*)">\n?')
_TASK_TAIL = re.compile(r"\n?</task_result>\s*$")
_FORWARD_AS_IS = ("subagent_queued", "subagent_start", "subagent_end", "permission_request", "question",
                  "plan_review", "approval_request")


def reviewer_name(dimension: str) -> str:
    return f"review-{dimension}"


def review_specs(dimensions: "list[str]") -> "dict[str, AgentSpec]":
    specs: "dict[str, AgentSpec]" = {}
    for dim in dimensions:
        specs[reviewer_name(dim)] = AgentSpec(
            name=reviewer_name(dim), description=f"Read-only {dim} reviewer for /review", role="reviewer",
            tools=list(READ_ONLY_TOOLS), omit_claude_md=True, body=prompt_text(dim), source="built-in")
    specs[JUDGE_NAME] = AgentSpec(
        name=JUDGE_NAME, description="Read-only judge that verifies one review finding", role="judge",
        tools=list(READ_ONLY_TOOLS), omit_claude_md=True, body=prompt_text("judge"), source="built-in")
    specs[FIXER_NAME] = AgentSpec(
        name=FIXER_NAME, description="Applies a minimal fix for one confirmed review finding", role="coder",
        tools=None, disallowed_tools=["Agent", "Task"], body=prompt_text("fixer"), source="built-in")
    return specs


def review_runtime(runtime, dimensions: "list[str]"):
    """A copy of the session's AgentRuntime that also knows the review agents.
    Shares the task map, lock, live-children map and concurrency gate."""
    agents = dict(runtime.agents)
    agents.update(review_specs(dimensions))
    return dataclasses.replace(runtime, agents=agents)


def make_sink(sink: Optional[Callable]) -> Optional[Callable]:
    """Forward only what the TUI needs from the children: cards starting and
    ending, asks, and a phase/tool signal for each card. The reviewers' own
    text stays out of the transcript (the cards show the result)."""
    if sink is None:
        return None

    def forward(ev) -> None:
        kind = getattr(ev, "kind", None)
        if kind in _FORWARD_AS_IS:
            sink(ev)
        elif kind == "phase":
            from halo_harness.agent.subagent import _bg_phase_word
            word = _bg_phase_word((ev.data or {}).get("state"), (ev.data or {}).get("kind"))
            if word:
                progress = events.subagent_progress(phase_word=word)
                progress.agent_id = getattr(ev, "agent_id", None)
                sink(progress)
        elif kind == "tool_use_ready":
            progress = events.subagent_progress(tool_call=True)
            progress.agent_id = getattr(ev, "agent_id", None)
            sink(progress)
    return forward


@dataclass
class ChildResult:
    text: str = ""
    is_error: bool = False
    task_id: Optional[str] = None
    aborted: bool = False


def split_task_result(content: str) -> "tuple[str, Optional[str]]":
    """`(inner text, task_id)` from a `<task_result>`-wrapped hand-back."""
    m = _TASK_HEAD.match(content or "")
    if not m:
        return (content or "").strip(), None
    inner = _TASK_TAIL.sub("", content[m.end():])
    return inner.strip(), (m.group(1) or None)


def aborted(rt) -> bool:
    ev = getattr(rt.parent, "abort", None)
    return bool(ev is not None and ev.is_set())


def run_child(rt, *, subagent: str, prompt: str, description: str, tool_id: str, sink: Optional[Callable] = None,
              task_id: Optional[str] = None) -> ChildResult:
    """Run (or, with `task_id`, resume) one review sub-agent to completion."""
    from halo_harness.agent.subagent import run_agent_call
    if aborted(rt):
        return ChildResult("", True, None, aborted=True)
    if task_id:
        tool_input = {"task_id": task_id, "prompt": prompt}
    else:
        tool_input = {"subagent_type": subagent, "prompt": prompt, "description": description[:60]}
    try:
        _events, result = run_agent_call(runtime=rt, tool_id=tool_id, tool_input=tool_input, tool_name="Agent",
                                         on_event=make_sink(sink))
    except Exception as e:   # the runtime never raises; this keeps a bug from ending the whole review
        return ChildResult(f"{type(e).__name__}: {e}", True, None)
    text, new_id = split_task_result(result.content)
    return ChildResult(text, bool(result.is_error), new_id or task_id, aborted=aborted(rt))


def run_jobs(rt, jobs: "list[Callable[[], object]]") -> list:
    """Run `jobs` in parallel under the session's concurrency gate
    (`agents.max_concurrent`); results come back in job order. A job that
    raises yields the exception object in its slot."""
    from halo_harness.agent.subagent import effective_max_concurrent
    if not jobs:
        return []
    limit = effective_max_concurrent(rt)
    results: list = [None] * len(jobs)

    def _wrap(i: int, fn: Callable) -> Callable:
        def _run() -> None:
            try:
                results[i] = fn()
            except Exception as e:
                results[i] = e
        return _run

    with rt.concurrency_semaphore.pool(max_workers=min(limit, len(jobs)), limit=limit) as pool:
        for f in [pool.submit(_wrap(i, fn)) for i, fn in enumerate(jobs)]:
            f.result()
    return results


_counter_lock = threading.Lock()
_counter = [0]


def next_tool_id(prefix: str) -> str:
    with _counter_lock:
        _counter[0] += 1
        return f"{prefix}-{_counter[0]}"
