"""halo_harness.tui.dialogs.model_picker_takes -- the `/model` picker's
honest line (Halo 3.3.15.0 R2, "the picker says what a model takes").

When the highlight moves onto a model row, the picker's subtitle (the
footer's line, `#model-footer`) shows that model's `best_at_line` -- "vision+
pdf in, tools, reasoning, long context (1M), premium; no audio" -- read from
the best-at cache the picker already loads once (`ModelPicker._best_at_rows`,
models_best_at: a file read while fresh, never a request), else scored from
the row the picker holds (capabilities_line.best_at_line, pure). With
nothing highlighted (a filter that matches nothing, the Agents source's rows)
the footer comes back. Kept out of model_picker.py so that file does not grow.
"""

from __future__ import annotations

from typing import Optional

from halo_harness.model_display import PICKER_FOOTER

FOOTER_ID = "model-footer"


def highlighted_model(picker) -> Optional[dict]:
    """The model row under the highlight, None on nothing, a header, or an Agents-source row."""
    if getattr(picker, "_source", "models") != "models":
        return None
    try:
        from textual.widgets import OptionList
        option_list = picker.query_one("#model-list", OptionList)
        index = option_list.highlighted
        if index is None:
            return None
        ref = option_list.get_option_at_index(index).id
    except Exception:
        return None
    if not ref:
        return None
    return next((m for m in (getattr(picker, "_filtered", None) or []) if isinstance(m, dict) and m.get("ref") == ref), None)


def line_for(picker, model: dict) -> str:
    """The honest line for `model`: the best-at cache's, else scored from the row itself."""
    ref = model.get("ref") or ""
    try:
        line = ((picker._best_at_rows() or {}).get(ref) or {}).get("line") or ""
    except Exception:
        line = ""
    if line:
        return line
    try:
        from halo_harness.capabilities_line import best_at_line
        return best_at_line(model)
    except Exception:
        return ""


def subtitle_text(picker) -> str:
    """What `#model-footer` shows now: the highlighted model's line, else the footer."""
    model = highlighted_model(picker)
    if model is None:
        return PICKER_FOOTER
    line = line_for(picker, model)
    return line or PICKER_FOOTER


def sync_subtitle(picker) -> None:
    """Draw `subtitle_text` into the footer's line; never raises (a closing screen has no widgets)."""
    try:
        from rich.text import Text
        from textual.widgets import Static
        picker.query_one(f"#{FOOTER_ID}", Static).update(Text(subtitle_text(picker)))  # plain text, never markup
    except Exception:
        pass
