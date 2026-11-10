"""halo_harness.model_takes -- what a model takes (Halo 3.3.15.0 R2, "the
picker says what a model takes").

`takes_words(row)` reads the facts a catalog row already carries (the same
keys `capabilities.capability_profile` and `capabilities_line.best_at_line`
read: `modalities_in`, `modalities_out`, `image_output`, `tools` plus the
measured tool facts, `reasoning`) and answers the words in one fixed order:

    text vision audio video pdf    what it reads (text always)
    image                          what it makes beyond text
    tools think                    tool calls and reasoning, when stated or measured

A row whose catalog states no inputs reads `?` in place of the input words
(the house rule: `?` = not known, never blank): `["?"]`, or `["?", "tools"]`
when only the tool flag is stated. Nothing is guessed.

The same words feed the terminal `/model` picker's `takes=` column
(`model_display.format_picker_row`), the `/model <ref>` confirmation, the
`halo models` table's `takes` column, `halo models show` and Studio's
`takes` row key (studio/model.py), which the shared ModelTakes chips draw.
"""

from __future__ import annotations

from typing import Optional

UNKNOWN = "?"
TAKES_ORDER = ("text", "vision", "audio", "video", "pdf", "image", "tools", "think")
_INPUTS = (("image", "vision"), ("audio", "audio"), ("video", "video"), ("pdf", "pdf"))
# the picker pads the column to this width so the price columns after it line up for the common rows
# ("text,vision,pdf,tools,think" is 27); a longer list pushes the row, it is never cut
TAKES_WIDTH = 27
# what the column means, in the picker's header line and the `halo models` header
TAKES_HEADER = "takes = what it reads (text vision audio video pdf), image = makes images, tools, think = reasons"


def _seq(row: dict, key: str) -> Optional[set]:
    v = row.get(key)
    if isinstance(v, (list, tuple, set)) and v:
        return {str(x).strip().lower() for x in v}
    return None


def takes_words(row: Optional[dict]) -> list:
    """The words in TAKES_ORDER (`?` first when no input list is stated)."""
    row = row if isinstance(row, dict) else {}
    if isinstance(row.get("takes"), (list, tuple)) and row.get("takes"):  # 3.3.17.0 R2: a row that states its own (cp:work)
        return [str(w) for w in row["takes"]]
    ins = _seq(row, "modalities_in")
    if ins is None:
        words = [UNKNOWN]
    else:
        if ins & {"file", "document"}:
            ins.add("pdf")
        words = ["text"] + [word for m, word in _INPUTS if m in ins]
    outs = _seq(row, "modalities_out")
    if row.get("image_output") is True or (outs is not None and "image" in outs):
        words.append("image")
    from halo_harness.capabilities_facts import tools_state
    try:
        tools = tools_state(row)[0]
    except Exception:
        tools = None
    if tools is True:
        words.append("tools")
    r = row.get("reasoning")
    if isinstance(r, dict) and r.get("kind") in ("native", "openai"):
        words.append("think")
    return words


def takes_text(row: Optional[dict], sep: str = ",") -> str:
    """`text,vision,pdf,tools,think`, or `?` (never blank)."""
    return sep.join(takes_words(row)) or UNKNOWN


def picker_cell(row: Optional[dict]) -> str:
    """The `takes=` cell, padded to TAKES_WIDTH."""
    return f"{takes_text(row):<{TAKES_WIDTH}}"


def cache_entry(ref: str, state_dir=None) -> dict:
    """The best-at cache's entry for `ref` (a file read, never a rebuild, never a request): `{kinds, line, facts}`,
    {} when the cache or the ref is missing. Tries the ref as given, then with an `or:` prefix added or dropped."""
    if not ref:
        return {}
    try:
        from halo_harness.models_best_at import load
        if state_dir is None:
            from halo_harness.config.paths import bridge_home
            state_dir = bridge_home()
        rows = (load(state_dir) or {}).get("rows") or {}
    except Exception:
        return {}
    for key in (ref, ref[3:] if ref.startswith("or:") else f"or:{ref}"):
        got = rows.get(key)
        if isinstance(got, dict):
            return got
    return {}


def takes_for_ref(ref: str, state_dir=None, row: Optional[dict] = None) -> "tuple[list, str]":
    """(takes words, the honest line) for `ref`: from `row` when the caller has it, else the best-at cache's facts.
    `(["?"], "")` when neither knows the model."""
    entry = cache_entry(ref, state_dir)
    if row is None:
        row = entry.get("facts") if isinstance(entry.get("facts"), dict) else None
    line = str(entry.get("line") or "")
    if row is not None and not line:
        try:
            from halo_harness.capabilities_line import best_at_line
            line = best_at_line({**row, "ref": ref})
        except Exception:
            line = ""
    return (takes_words(row) if row is not None else [UNKNOWN]), line


def confirm_suffix(refs, state_dir=None) -> str:
    """The words `/model <ref>`'s one-line confirmation ends with: " · takes text,vision,pdf,tools". `refs`: the ref
    as typed, then the session's resolved one (an alias such as `sonnet` is cached under the ref it resolves to);
    the first the best-at cache knows answers, else `?`."""
    words = [UNKNOWN]
    for ref in [r for r in (refs if isinstance(refs, (list, tuple)) else [refs]) if r]:
        words, _line = takes_for_ref(str(ref), state_dir)
        if words != [UNKNOWN]:
            break
    return f" · takes {','.join(words)}"
