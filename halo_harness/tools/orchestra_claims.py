"""halo_harness.tools.orchestra_claims -- the Orchestra's claim tools (Halo
3.0.3.0): `OrchestraClaim`, `OrchestraRelease`, `OrchestraClaims`,
`OrchestraNote`.

Registered beside the task board tools, and only when the session runs
inside a run: $HALO_ORCHESTRA_RUN names the run folder
(`<repo>/.halo/orchestra/<run-id>`). The holder is built from the session
folder (`claims.holder_for(ctx.session_dir)`: `<session_id>/<agent_id>`, the
same name the claim guard on Write/Edit uses). The rule an agent follows:
read the goal, list the claims, claim the smallest key, edit, release, note.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from halo_harness.tools.base import Tool, ToolContext, ToolResult

_MAX_UNITS_LISTED = 200


def _run_dir(ctx: ToolContext) -> Optional[Path]:
    from halo_harness.orchestra.guard import run_dir_from_env
    env = ctx.env if isinstance(ctx.env, dict) and ctx.env.get("HALO_ORCHESTRA_RUN") else os.environ
    return run_dir_from_env(env)


def _setup(ctx: ToolContext):
    """`(run_dir, holder, ClaimLog)` or a ToolResult error."""
    from halo_harness.orchestra.claims import ClaimLog, holder_for
    run_dir = _run_dir(ctx)
    if run_dir is None:
        return ToolResult("This session is not inside an Orchestra run ($HALO_ORCHESTRA_RUN is not a run "
                          "folder).", is_error=True)
    if ctx.session_dir is None:
        return ToolResult("No session directory is available, so there is no holder name.", is_error=True)
    return run_dir, holder_for(ctx.session_dir), ClaimLog(run_dir)


def _snapshot(run_dir, holder: str, key: str, ctx: ToolContext) -> None:
    """A worker lane keeps the unit's written text (the run's record-equals-disk check)."""
    try:
        from halo_harness.orchestra.workers import record_written
        env = ctx.env if isinstance(ctx.env, dict) else {}
        lane = env.get("HALO_ORCHESTRA_LANE") or os.environ.get("HALO_ORCHESTRA_LANE")
        record_written(run_dir, holder, key, ctx.cwd, int(lane) if str(lane or "").isdigit() else None)
    except (OSError, ValueError):
        pass


def _edited_since_release(log, key: str) -> bool:
    """A `writing` line for `key` since its last release: an edit made under
    this lane's earlier holder, carried over when the claim moved (a worker
    run again after a failure re-claims and finds the unit already written)."""
    ops = [e.get("op") for e in log.entries() if e.get("key") == key]
    last_release = max((i for i, op in enumerate(ops) if op in ("release", "expire")), default=-1)
    return "writing" in ops[last_release + 1:] and ops[-1] != "written"


def _key_arg(input) -> Optional[str]:
    key = input.get("key") if isinstance(input, dict) else None
    return key.strip() if isinstance(key, str) and key.strip() else None


class OrchestraClaimTool(Tool):
    name = "OrchestraClaim"
    description = (
        "Claim one unit of a shared file in this Orchestra run before you edit it. A key is `path` (the whole "
        "file), `path#function` (a Python function or class; `Class.method` for a method) or `path#heading-slug` "
        "(a Markdown section). Claim the SMALLEST unit you need: other workers edit the rest of the file at the "
        "same time. OrchestraClaims lists the keys and who holds what. When a unit is taken, the answer names the holder and when the "
        "claim expires: claim another unit, wait, or ask the lead. Re-claiming your own key renews it."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "key": {"type": "string", "description": "e.g. basket.py#total"},
            "ttl": {"type": "integer", "description": "Seconds the claim lasts (default 900, 30..86400)"},
            "note": {"type": "string", "description": "Optional: what you are about to do"},
        },
        "required": ["key"],
    }

    def summary(self, input: dict) -> str:
        return f"OrchestraClaim({_key_arg(input) or ''})"

    def run(self, input: dict, ctx: ToolContext) -> ToolResult:
        input = input if isinstance(input, dict) else {}
        key = _key_arg(input)
        if key is None:
            return ToolResult("The key parameter is required (e.g. basket.py#total).", is_error=True)
        ttl = input.get("ttl", 900)
        if isinstance(ttl, bool) or not isinstance(ttl, int) or not 30 <= ttl <= 86400:
            return ToolResult("ttl is a whole number of seconds from 30 to 86400.", is_error=True)
        setup = _setup(ctx)
        if isinstance(setup, ToolResult):
            return setup
        run_dir, holder, log = setup
        from halo_harness.orchestra.claims import clock_text
        result = log.claim(holder, key, ttl_s=ttl, note=str(input.get("note") or ""))
        if not result.ok:
            return ToolResult(f"Not claimed: {result.text}. Pick a unit nobody holds (OrchestraClaims lists them) "
                              "or wait and claim again.", is_error=True)
        files = _goal_files(run_dir)
        extra = "" if key.split("#")[0] in files else (
            f" Note: {key.split('#')[0]!r} is not one of the goal's files ({', '.join(files) or 'none'}); "
            "the claim is recorded but nothing guards that file.")
        return ToolResult(f"Claimed `{key}` as {holder} until {clock_text(result.expires)}. Edit it now; "
                          f"OrchestraRelease `{key}` when your edit is written.{extra}")


class OrchestraReleaseTool(Tool):
    name = "OrchestraRelease"
    description = ("Release a unit you claimed with OrchestraClaim, once your edit is written, so another worker "
                   "can take it. Then add an OrchestraNote saying what you changed.")
    input_schema = {"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]}

    def summary(self, input: dict) -> str:
        return f"OrchestraRelease({_key_arg(input) or ''})"

    def run(self, input: dict, ctx: ToolContext) -> ToolResult:
        key = _key_arg(input)
        if key is None:
            return ToolResult("The key parameter is required.", is_error=True)
        setup = _setup(ctx)
        if isinstance(setup, ToolResult):
            return setup
        _, holder, log = setup
        current = log.active().get(key)
        if current is not None and current.holder == holder and (
                current.state == "writing" or _edited_since_release(log, key)):
            log.mark_written(holder, key)
        if current is not None and current.holder == holder:
            _snapshot(setup[0], holder, key, ctx)
        result = log.release(holder, key)
        if not result.ok:
            return ToolResult(f"Not released: {result.text}. OrchestraClaims shows what you hold.", is_error=True)
        return ToolResult(f"Released `{key}`. Add an OrchestraNote with what you changed.")


class OrchestraClaimsTool(Tool):
    name = "OrchestraClaims"
    is_read_only = True
    description = ("List this Orchestra run's goal files, their claimable units (keys and lines) and every live "
                   "claim: who holds it, its state (claimed/writing/written) and when it expires.")
    input_schema = {"type": "object", "properties": {}}

    def summary(self, input: dict) -> str:
        return "OrchestraClaims()"

    def run(self, input: dict, ctx: ToolContext) -> ToolResult:
        setup = _setup(ctx)
        if isinstance(setup, ToolResult):
            return setup
        run_dir, holder, log = setup
        from halo_harness.orchestra.claims import clock_text
        from halo_harness.orchestra.goal import repo_root_of
        from halo_harness.orchestra.index import index_file
        active = log.active()
        out = [f"run {run_dir.name}; you are {holder}"]
        out.append("live claims:" if active else "live claims: none")
        for c in sorted(active.values(), key=lambda c: c.key):
            mine = " (yours)" if c.holder == holder else ""
            out.append(f"  {c.key}  {c.holder}{mine}  {c.state}  until {clock_text(c.expires)}")
        roots = [Path(ctx.cwd), repo_root_of(run_dir)]
        listed = 0
        for rel in _goal_files(run_dir):
            root = next((r for r in roots if (r / rel).is_file()), roots[-1])
            out.append(f"units of {rel}:")
            for u in index_file(root / rel, root=root):
                if listed >= _MAX_UNITS_LISTED:
                    break
                held = active.get(u.key)
                tag = f"  held by {held.holder}" if held else ""
                out.append(f"  {u.key}  lines {u.start_line}-{u.end_line}{tag}")
                listed += 1
        return ToolResult("\n".join(out))


class OrchestraNoteTool(Tool):
    name = "OrchestraNote"
    description = ("Add a line to this Orchestra run's timed log (events.jsonl): what you changed, what you found, "
                   "what the next worker should know. The lead and Studio read it.")
    input_schema = {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}

    def summary(self, input: dict) -> str:
        text = input.get("text") if isinstance(input, dict) else ""
        return f"OrchestraNote({str(text or '')[:50]})"

    def run(self, input: dict, ctx: ToolContext) -> ToolResult:
        text = input.get("text") if isinstance(input, dict) else None
        if not isinstance(text, str) or not text.strip():
            return ToolResult("The text parameter is required.", is_error=True)
        setup = _setup(ctx)
        if isinstance(setup, ToolResult):
            return setup
        run_dir, holder, _ = setup
        from halo_harness.orchestra import events as run_events
        run_events.log(run_dir, "note", f"{holder}: {text.strip()}", holder=holder)
        return ToolResult("Noted in the run log.")


def _goal_files(run_dir: Path) -> list:
    from halo_harness.orchestra.goal import load_goal, norm_file
    try:
        return [norm_file(f) for f in load_goal(run_dir / "goal.json").files]
    except ValueError:
        return []


def orchestra_tools(env=None) -> list:
    """The four tools when this process runs inside a run, else []."""
    from halo_harness.orchestra.guard import run_dir_from_env
    if run_dir_from_env(env) is None:
        return []
    return [OrchestraClaimTool(), OrchestraClaimsTool(), OrchestraNoteTool(), OrchestraReleaseTool()]
