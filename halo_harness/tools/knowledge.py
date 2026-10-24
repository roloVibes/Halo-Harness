"""halo_harness.tools.knowledge -- the agents' knowledge tools (Halo 3.1.8.0 R4,
docs/KNOWLEDGE.md "The tools"): `knowledge_add` writes a finding or a
decision to this harness's knowledge (`<state>/knowledge/`, by
`agent:<session>/<agent>`), `knowledge_search` returns the entries that rank
for some words, with the line that tells the agent to cite the id of any it
reuses (knowledge/cite.py). Both touch only the harness's own knowledge
store, so the permission engine allows them in every mode like TodoWrite
(an explicit deny or ask rule still wins).
"""

from __future__ import annotations

import os
from pathlib import Path

from halo_harness.tools.base import Tool, ToolContext, ToolResult


def _by(ctx: ToolContext) -> str:
    from halo_harness.orchestra.claims import holder_for
    top, _, agent = holder_for(ctx.session_dir).partition("/")
    return f"agent:{top[:8]}/{agent or 'main'}"


def _strings(value) -> list:
    if isinstance(value, str):
        return [value]
    return [str(v) for v in value if str(v).strip()] if isinstance(value, list) else []


class KnowledgeAddTool(Tool):
    name = "knowledge_add"
    description = (
        "Save what you established so later sessions, Orchestra runs and the other harnesses of the fleet can reuse "
        "it. kind `finding`: a fact you verified -- give evidence lines (the command you ran and its result, the "
        "file and line you read). kind `decision`: a choice you took -- say why in the body and list the "
        "alternatives. Returns the entry's id (f-... or d-...); cite that id when you reuse it later."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "kind": {"type": "string", "enum": ["finding", "decision"]},
            "title": {"type": "string", "description": "One line: what was found or decided"},
            "body": {"type": "string", "description": "What, where and why, in plain prose"},
            "evidence": {"type": "array", "items": {"type": "string"},
                         "description": "e.g. \"`python -m pytest -q` exit 0, 12 passed\" or \"read basket.py:40\""},
            "alternatives": {"type": "array", "items": {"type": "string"}, "description": "A decision: what else was possible"},
            "tags": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["kind", "title"],
    }

    def summary(self, input: dict) -> str:
        return f"knowledge_add({(input or {}).get('kind') or '?'}: {str((input or {}).get('title') or '')[:60]})"

    def run(self, input: dict, ctx: ToolContext) -> ToolResult:
        from halo_harness.knowledge.store import KnowledgeError, write
        input = input if isinstance(input, dict) else {}
        run = os.environ.get("HALO_ORCHESTRA_RUN") or ""
        try:
            entry = write(str(input.get("kind") or ""), str(input.get("title") or ""), body=str(input.get("body") or ""),
                          evidence=_strings(input.get("evidence")), alternatives=_strings(input.get("alternatives")),
                          tags=_strings(input.get("tags")), by=_by(ctx), run=Path(run).name if run else "",
                          repo=Path(str(ctx.cwd)).name if ctx.cwd else "")
        except KnowledgeError as e:
            return ToolResult(f"Not saved: {e}", is_error=True)
        extra = f", confidence {entry['confidence']}" if entry.get("confidence") else ""
        return ToolResult(f"Saved {entry['kind']} {entry['id']}{extra}: {entry['title']}")


class KnowledgeSearchTool(Tool):
    name = "knowledge_search"
    description = (
        "Search this harness's findings and decisions (what earlier sessions and runs verified or chose) for some "
        "words. Each hit shows its id, kind, who found or decided it and when. Cite the id of any entry you reuse "
        "in your answer, e.g. (f-20261024-a1b2c3)."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Words about what you need to know"},
            "kind": {"type": "string", "enum": ["finding", "decision"], "description": "Only this kind"},
            "k": {"type": "integer", "description": "At most this many hits (default 5, up to 20)"},
        },
        "required": ["query"],
    }
    is_read_only = True

    def summary(self, input: dict) -> str:
        return f"knowledge_search({str((input or {}).get('query') or '')[:60]})"

    def run(self, input: dict, ctx: ToolContext) -> ToolResult:
        from halo_harness.knowledge.cite import snapshot
        from halo_harness.knowledge.search import KINDS, search
        input = input if isinstance(input, dict) else {}
        query = " ".join(str(input.get("query") or "").split())
        if not query:
            return ToolResult("The query parameter is required: some words about what you need to know.", is_error=True)
        kind = input.get("kind")
        try:
            k = max(1, min(20, int(input.get("k") or 5)))
        except (TypeError, ValueError):
            k = 5
        hits = search(query, k=k, kinds=(kind,) if kind in KINDS else KINDS)
        return ToolResult(snapshot(hits) if hits else f"No finding or decision here matches \"{query}\".")
