"""tests.helpers.layout_watch -- which widgets ask for a screen layout of
their own accord (Halo 3.1.3.0 R2, the in-place repaints).

`Static.update(content)` asks Textual for a layout of the whole screen, and
a periodic repaint (a status-bar tick, a level-band frame) used to do that
once a second and more. `watch_own_layout_requests` wraps `refresh` on the
given widget instances and records every `layout=True` (or recompose)
request that has Halo's own code on the stack: the old `update` path, or
`inplace.update_in_place` falling back to a layout. Textual's own requests
(a size change on resize goes through `_size_updated`) carry no
`halo_harness` frame and are not counted, so a resize test is not at the
mercy of how Textual batches its layouts on a slow runner.
"""

from __future__ import annotations

import contextlib
import traceback


@contextlib.contextmanager
def watch_own_layout_requests(*widgets):
    """Yield the list of class names of every layout request one of
    `widgets` made from Halo code while the block ran (empty = all repaints
    were in place)."""
    asked: list = []
    for widget in widgets:
        original = widget.refresh

        def refresh(*regions, repaint=True, layout=False, recompose=False,
                    _orig=original, _name=type(widget).__name__):
            if layout or recompose:
                frames = traceback.extract_stack(limit=14)[:-1]
                if any("halo_harness" in frame.filename for frame in frames):
                    asked.append(_name)
            return _orig(*regions, repaint=repaint, layout=layout, recompose=recompose)

        widget.refresh = refresh
    try:
        yield asked
    finally:
        for widget in widgets:
            widget.__dict__.pop("refresh", None)
