"""halo_harness.tools.builder_tool -- the `Builder` tool: Studio's builder tools, offered to main in a session (Halo
3.6.0.0 R3). The work is crew/tools.py (the one implementation) through crew/session_tool.py; this is its wire shape.

In an interactive session agent/loop.py shows the approval card (the question round trip) and writes only what the
person picked; `run()` below is the path with no one to answer (print mode, a test's dispatch): it previews and writes
nothing. Offered to the top session of the terminal and of Studio's sessions (headless.build_session, not bare, not
print mode).
"""

from __future__ import annotations

from halo_harness.tools.base import Tool, ToolContext, ToolResult

NAME = "Builder"
DESCRIPTION = (
    "Make or change the person's agents, workflows and maps (their Halo configuration files) -- the same tools as Studio's "
    "builder box. Send {\"tool\": <name>, \"args\": {...}}, or {\"changes\": [{\"tool\", \"args\"}, ...]} for several at once "
    "(one approval card). Nothing is written until the person approves the card; a line that lets an agent do more is "
    "its own choice and never ticked for them. {\"undo\": <id>} puts an applied change back. studio_show answers questions "
    "about a map, the lists or a run and changes nothing. Use it when the person asks for an agent, a workflow or a map "
    "change, never on your own. The tools:")


class BuilderTool(Tool):
    name = NAME
    result_cap = None

    @property
    def description(self) -> str:
        from halo_harness.crew.tools import TOOLS
        return DESCRIPTION + "".join(f"\n  {n} {spec}" for n, (_fn, spec) in TOOLS.items() if not n.startswith("try_"))

    @property
    def input_schema(self) -> dict:
        return {"type": "object", "properties": {
            "tool": {"type": "string", "description": "One of the builder's tools (agent_make, map_line_add, studio_show, ...)"},
            "args": {"type": "object", "description": "The tool's arguments"},
            "changes": {"type": "array", "items": {"type": "object"}, "description": "Several {tool, args} for one card"},
            "undo": {"type": "string", "description": "An undo id from an earlier Builder result"},
        }}

    def summary(self, input: dict) -> str:
        input = input if isinstance(input, dict) else {}
        what = input.get("tool") or (f"{len(input.get('changes') or [])} changes" if input.get("changes") else "") or \
            (f"undo {input.get('undo')}" if input.get("undo") else "?")
        return f"Builder({what})"

    def run(self, input: dict, ctx: ToolContext) -> ToolResult:
        from halo_harness.crew.session_tool import no_one_to_ask, preview

        class _S:
            cwd = ctx.cwd
        pv = preview(_S(), input)
        return ToolResult(no_one_to_ask(pv))
