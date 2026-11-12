"""tests.helpers.no_pillow -- Pillow hidden from this process for a block (Halo 3.4.1.0 R6), so a box that has Pillow
tests the no-Pillow path too: `import PIL` (and every `from PIL import ...`) raises ImportError inside the block, the
way it does where Pillow is not installed; after it, the modules are back as they were.

    with no_pillow():
        ...   # replay_clip.encoder() says Pillow is missing; a clip's encode refuses before anything is written

It is process-wide (sys.modules): an in-process Studio's handler threads see it too, which is what a Chrome driver
that serves Studio in its own process wants.
"""
from __future__ import annotations

import sys
from contextlib import contextmanager


def _ours(name: str) -> bool:
    return name == "PIL" or name.startswith("PIL.")


@contextmanager
def no_pillow():
    saved = {k: v for k, v in sys.modules.items() if _ours(k)}
    for k in saved:
        del sys.modules[k]
    sys.modules["PIL"] = None  # type: ignore[assignment]  # the import system's "not importable" marker
    try:
        yield
    finally:
        for k in [k for k in sys.modules if _ours(k)]:
            del sys.modules[k]
        sys.modules.update(saved)


def has_pillow() -> bool:
    try:
        import PIL  # noqa: F401
    except ImportError:
        return False
    return True
