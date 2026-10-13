"""halo_harness.providers.anthropic_caps -- per-model Messages API behaviour
for Claude ids, read from DATA (`model_table.json`'s
`anthropic_model_capabilities` section), never from model-name checks
scattered through the request builders.

Claude ids are not tabled per row like the Databricks/OpenRouter open-weight
models: every Claude generation of one family behaves the same from a given
version onward, so the table is keyed by family with the version each
behaviour starts at:

- `adaptive_thinking_from`: `thinking: {type: adaptive}` + `output_config.
  effort` from this version on; older ids take `thinking.budget_tokens`.
- `effort_xhigh_from`: `output_config.effort` accepts `xhigh` from this
  version on; older adaptive ids accept low/medium/high/max only.
- `forced_tool_choice_rejected_from`: `tool_choice` `{type: any}` /
  `{type: tool}` is rejected (400) from this version on; absent = accepted.

A threshold of "0" means every version of that family. The id parser reads
`<family>-<major>[-.<minor>]` (`claude-opus-4-6`, `databricks-claude-
sonnet-5-5`, `claude-haiku-5.5`) and the external `claude-<major>-<minor>-
<family>` order (`us-anthropic-claude-3-7-sonnet-...`); a snapshot date is
never read as a minor version. An id it cannot parse keeps the old
behaviour: adaptive only when it names opus/fable, no xhigh, forced
tool_choice accepted.
"""

from __future__ import annotations

import re
from typing import Optional, Tuple

_ID_RE = re.compile(r"(opus|sonnet|haiku|fable|mythos)[-_](\d+)(?:[-_.](\d{1,2})(?!\d))?")
_REV_ID_RE = re.compile(r"claude[-_](\d+)(?:[-_.](\d{1,2})(?!\d))?[-_](opus|sonnet|haiku)")

_SECTION = "anthropic_model_capabilities"


def parse_family_version(model_id: str) -> "Optional[Tuple[str, Tuple[int, int]]]":
    """`("sonnet", (4, 6))` for `claude-sonnet-4-6`; None when the id names
    no recognised family with a version."""
    low = (model_id or "").lower()
    rev = _REV_ID_RE.search(low)
    if rev is not None:
        return rev.group(3), (int(rev.group(1)), int(rev.group(2) or 0))
    m = _ID_RE.search(low)
    if m is None:
        return None
    return m.group(1), (int(m.group(2)), int(m.group(3) or 0))


def _threshold(text) -> "Optional[Tuple[int, int]]":
    if text is None:
        return None
    parts = str(text).strip().split(".")
    try:
        return int(parts[0]), int(parts[1]) if len(parts) > 1 and parts[1] else 0
    except ValueError:
        return None


def _families(model_table: "Optional[dict]" = None) -> dict:
    section = (model_table or {}).get(_SECTION)
    if not isinstance(section, dict):
        from halo_harness.providers.profiles import load_model_table
        section = load_model_table().get(_SECTION)
    fams = (section or {}).get("families") if isinstance(section, dict) else None
    return fams if isinstance(fams, dict) else {}


def _from(row: dict, field: str, version: "Tuple[int, int]") -> bool:
    th = _threshold(row.get(field))
    return th is not None and version >= th


def capabilities(model_id: str, model_table: "Optional[dict]" = None) -> dict:
    """`{"adaptive_thinking", "effort_xhigh", "forced_tool_choice"}` (all
    bool) for one Claude model id; see the module docstring."""
    parsed = parse_family_version(model_id)
    row = _families(model_table).get(parsed[0]) if parsed else None
    if parsed is None or not isinstance(row, dict):
        low = (model_id or "").lower()
        return {"adaptive_thinking": "opus" in low or "fable" in low,
                "effort_xhigh": False, "forced_tool_choice": True}
    version = parsed[1]
    rejected = _threshold(row.get("forced_tool_choice_rejected_from"))
    return {
        "adaptive_thinking": _from(row, "adaptive_thinking_from", version),
        "effort_xhigh": _from(row, "effort_xhigh_from", version),
        "forced_tool_choice": rejected is None or version < rejected,
    }
