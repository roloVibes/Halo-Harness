"""halo_harness.tools.builder_tool -- the `Builder` tool: Studio's builder tools, offered to main in a session (Halo
3.6.0.0 R3). The work is crew/tools.py (the one implementation) through crew/session_tool.py; this is its wire shape.

In an interactive session agent/loop.py shows the approval card (the question round trip) and writes only what the
person picked; `run()` below is the path with no one to answer (print mode, a test's dispatch): it previews and writes
nothing. Offered to the top session of the terminal and of Studio's sessions (headless.build_session, not bare, not
print mode).

3.6.0.10 MW batch 4 (the owner, 2026-11-21): its "when" sentence has two forms, chosen ONCE per session at its start
(crew/session_start.tool_state sets `on_auto`, by agent/helpers_words.on_auto): on Auto main may also propose an agent or
a workflow by itself (WHEN_AUTO); everywhere else today's words, byte for byte (WHEN). A lean main reads short words
(tools/lean_descriptions.py): `short_tail` gives the session's sentence and the tools by name with their argument names,
made from crew/tools.py TOOLS (`listed`, `arg_names`), the same table the long words use.
"""

from __future__ import annotations

import re

from halo_harness.tools.base import Tool, ToolContext, ToolResult

NAME = "Builder"
WHEN = "Use it when the person asks for an agent, a workflow or a map change, never on your own."
WHEN_AUTO = ("Use it when the person asks for an agent, a workflow or a map change, or by yourself to propose an agent "
             "or a workflow for work that will come back.")
DESCRIPTION = (
    "Make or change the person's agents, workflows and maps (their Halo configuration files) -- the same tools as Studio's "
    "builder box. Send {\"tool\": <name>, \"args\": {...}}, or {\"changes\": [{\"tool\", \"args\"}, ...]} for several at once "
    "(one approval card). Nothing is written until the person approves the card; a line that lets an agent do more is "
    "its own choice and never ticked for them. {\"undo\": <id>} puts an applied change back. studio_show answers questions "
    "about a map, the lists or a run and changes nothing. " + WHEN + " In a session on Auto, make the workflow and the "
    "agents it needs, with no map, unless "
    "the person asks for a map. Asked which map or workflow this session uses, answer from the [Halo] note or call studio_show "
    "(what: map); never search the disk; nothing needs a restart. The tools:")
_ARG = re.compile(r'[{}\[\]]|"([^"]+)"(\??)')


def wanted(*, bare: bool = False, print_mode: bool = False, disallow=(), deny_rules=(), tools=None) -> bool:
    """3.6.0.19 LM: the one rule for "this session has the Builder": a session someone answers (not bare, not print
    mode), the tool not disallowed (`--disallowedTools`, a bare deny rule) and in `--tools` when that names a list.
    headless.build_session registers it by this rule; agent/prompt_measure measures the session it builds."""
    from halo_harness.permissions import bare_deny_tool_names, split_tool_rule_list
    return (not bare and not print_mode and NAME not in (disallow or ())
            and NAME not in bare_deny_tool_names(list(deny_rules or ()))
            and (tools is None or tools.strip() == "default" or NAME in split_tool_rule_list(tools)))


def listed() -> list:
    """[(name, spec)] of the builder tools main is offered (crew/tools.py TOOLS; Try runs from Studio only)."""
    from halo_harness.crew.tools import TOOLS
    return [(n, spec) for n, (_fn, spec) in TOOLS.items() if not n.startswith("try_")]


def arg_names(spec: str) -> list:
    """A tool's top-level argument names from its TOOLS spec, `?` kept on an optional one."""
    out, depth = [], 0
    for m in _ARG.finditer(spec):
        tok = m.group(0)
        if tok in "{[":
            depth += 1
        elif tok in "}]":
            depth -= 1
        elif depth == 1:
            out.append(m.group(1) + m.group(2))
    return out


def short_tail(description: str) -> str:
    """The short words' end: the session's own "when" sentence (read from its long words) and the tools by name."""
    when = WHEN_AUTO if WHEN_AUTO in str(description or "") else WHEN
    return " " + when + " The tools and their args (? optional):" + "".join(
        f"\n  {n} {{{', '.join(arg_names(spec))}}}" for n, spec in listed())


class BuilderTool(Tool):
    name = NAME
    result_cap = None
    on_auto = False  # set once, at the session's start (crew/session_start.tool_state); never changed afterwards

    @property
    def description(self) -> str:
        head = DESCRIPTION.replace(WHEN, WHEN_AUTO) if self.on_auto else DESCRIPTION
        return head + "".join(f"\n  {n} {spec}" for n, spec in listed())

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
