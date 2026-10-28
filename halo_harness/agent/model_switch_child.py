"""halo_harness.agent.model_switch_child -- Halo 3.3.5.0 R0: the switch step
for a sub-agent on another model than its parent's (the Auto lineup's
per-task pick, a role's model, an Agent call's own `model`).

A child starts fresh, so the request that gets fitted is its FIRST one: the
system prompt and the tools it carries, plus the prompt it is handed. When
that is past `compact_at` of the child's window, the prompt is cut to fit
(its head kept) with one line saying so at the cut, and the child's
transcript gets the switch line (a `model_switch` node) -- the parent's view
shows the same line as the child's first event.
"""

from __future__ import annotations

import logging
import math
from types import SimpleNamespace
from typing import Optional

log = logging.getLogger("bridge")

MIN_PROMPT_TOKENS = 256
MARGIN = 0.9  # the turn adds its own notes to the first request (the mode line, a reminder)


def cut_note(cut_tokens: int, ref_raw: str, window: int) -> str:
    return (f"\n\n[... {cut_tokens:,} tokens of this task's text were cut to fit {ref_raw}'s window "
            f"({window:,} tokens)]")


def fit_child_prompt(child, prompt_text: str) -> "tuple[str, Optional[str]]":
    """`(prompt, line)`: the prompt the child runs (cut when it would not fit) and the switch line
    (None when the child runs on its parent's model)."""
    parent_raw = getattr(child, "_parent_model_raw", None)
    ref = getattr(child, "model_ref", None)
    if not isinstance(parent_raw, str) or ref is None or parent_raw == getattr(ref, "raw", None):
        return prompt_text, None
    try:
        from halo_harness.agent import model_switch as S
        from halo_harness.providers.ollama_prompt import CHARS_PER_TOKEN
        report = S.plan(child, ref, model_profile=getattr(child, "model_profile", None), why="auto",
                        prev_ref=SimpleNamespace(raw=parent_raw))
        import json
        base = int(report["prompt_tokens"])
        text = prompt_text or ""
        wire = len(json.dumps(text, ensure_ascii=False))  # what the request carries (escapes count)
        mine = int(math.ceil(wire / CHARS_PER_TOKEN))
        report["prompt_tokens"] = base + mine
        target = report.get("target_tokens")
        report["needs_compaction"] = bool(target and base + mine > target)
        if report["needs_compaction"]:
            room = max(MIN_PROMPT_TOKENS, int((int(target) - base) * MARGIN))
            keep_chars = max(0, int(room * CHARS_PER_TOKEN * len(text) / max(1, wire)) - 200)
            if keep_chars < len(text):
                cut = int(math.ceil((len(text) - keep_chars) / CHARS_PER_TOKEN))
                text = text[:keep_chars] + cut_note(cut, ref.raw, int(report["window"] or 0))
                report["cut_tokens"] = cut
        report["line"] = S.line_for(report)
        S.finish(child, report)
        return text, report["line"]
    except Exception:
        log.debug("model_switch_child: fitting the child's first request failed", exc_info=True)
        return prompt_text, None
