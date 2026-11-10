"""halo_harness.tools.copilot_ask -- the `copilot_ask` tool: ask your work's Copilot from inside any agent (Halo
3.3.17.0 R2, docs/PROVIDERS-copilot.md "The tool `copilot_ask`").

`copilot_ask {prompt, files?: [url], web?: bool}` -> the answer, then its citations as numbered lines (and the
sensitivity label when there is one); the call and the answer land in the transcript like any tool result. It is
registered once `copilot.tenant` and `copilot.client_id` are set (tools/registry.py `default_tools`), belongs to the
`web` capability (isolation/capabilities.py), and a bio or a lineup card allows it like any other tool. Not signed in
(or any other failure) is one line with the next step. The session's one Copilot conversation is shared with a
`cp:work` turn (`session._copilot_conversation`). Each call marks the session's cost incomplete: Copilot is billed by
the tenant, never in dollars here (providers/copilot_cost.py).
"""

from __future__ import annotations

from halo_harness.tools.base import Tool, ToolContext, ToolResult

NAME = "copilot_ask"
DESCRIPTION = (
    "Ask the user's work Microsoft 365 Copilot, which holds their work data: mail, meetings and transcripts, Teams "
    "chats, OneDrive and SharePoint files, people and enterprise search, trimmed to what the user may see. Use it for "
    "questions about their work (\"what did we decide about X\", \"summarize this SharePoint file\", \"who owns Y\"). "
    "`prompt` is self-contained; `files` are OneDrive or SharePoint URLs for Copilot to read; `web: false` keeps the "
    "answer to work data. The answer ends with its citations as numbered lines; cite them when you use them. Copilot "
    "keeps the conversation for this session, so a follow-up can say \"and last quarter?\".")

INPUT_SCHEMA = {"type": "object", "properties": {
    "prompt": {"type": "string", "description": "What to ask Copilot, self-contained"},
    "files": {"type": "array", "items": {"type": "string"}, "description": "OneDrive or SharePoint file URLs for Copilot to read"},
    "web": {"type": "boolean", "description": "false: answer from work data only (default: the copilot.web setting)"},
}, "required": ["prompt"]}


def _session(ctx: ToolContext):
    return getattr(getattr(ctx, "agent_runtime", None), "parent", None)


class CopilotAskTool(Tool):
    name = NAME
    description = DESCRIPTION
    input_schema = INPUT_SCHEMA
    is_read_only = True
    result_cap = 60_000

    def pool_wait_s(self, input: dict):
        return 180.0  # a Copilot answer can take a minute; the read-only pool waits for it

    def summary(self, input: dict) -> str:
        input = input if isinstance(input, dict) else {}
        return f"copilot_ask({str(input.get('prompt') or '')[:60]})"

    def permission_content(self, input: dict) -> str:
        return str((input or {}).get("prompt") or "") if isinstance(input, dict) else ""

    def run(self, input: dict, ctx: ToolContext) -> ToolResult:
        from halo_harness.providers.copilot import Conversation, ask, format_answer
        from halo_harness.providers.copilot_cost import mark_unpriced
        from halo_harness.providers.copilot_net import CopilotError
        input = input if isinstance(input, dict) else {}
        prompt = str(input.get("prompt") or "").strip()
        if not prompt:
            return ToolResult("The prompt parameter is required", is_error=True)
        files = [str(f) for f in input.get("files") or [] if isinstance(f, str) and f.strip()]
        web = input.get("web") if isinstance(input.get("web"), bool) else None
        session = _session(ctx)
        conv = getattr(session, "_copilot_conversation", None)
        if not isinstance(conv, Conversation):
            conv = Conversation()
            if session is not None:
                try:
                    session._copilot_conversation = conv
                except Exception:
                    pass
        try:
            answer = ask(prompt, files=files, web=web, conversation=conv)
        except CopilotError as e:
            return ToolResult(e.line, is_error=True)
        mark_unpriced(getattr(session, "cost_meter", None))
        return ToolResult(format_answer(answer))


def copilot_tools() -> list:
    """[CopilotAskTool()] once Copilot is set up here (copilot.tenant and copilot.client_id), else []."""
    try:
        from halo_harness.providers.copilot_config import load
        return [CopilotAskTool()] if load().configured else []
    except Exception:
        return []
