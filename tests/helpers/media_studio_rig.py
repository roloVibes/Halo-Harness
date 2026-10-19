"""tests.helpers.media_studio_rig -- a Studio server over a temp state dir
with a FakeComfy server beside it and `media_api.URL` pointed at it (first
written for Halo 3.0.4.0 R5 as flow_studio_rig; the flow runs went with Flow
in 3.1.4.0). The JSON client and the SSE reader are orchestra_studio_rig's.
No model, no real ComfyUI.
"""
from __future__ import annotations

import shutil
import tempfile
import time
from pathlib import Path

from tests.helpers.fake_comfy import FakeComfy
from tests.helpers.orchestra_studio_rig import Reader, Studio as _OrchestraStudio

__all__ = ["MediaStudio", "Reader", "wait_for"]


class MediaStudio(_OrchestraStudio):
    """`with MediaStudio() as s:` -- s.state (the state dir), s.comfy (FakeComfy), s.call/get/post."""

    def __init__(self, cwd=None):
        super().__init__(Path(cwd) if cwd else Path(tempfile.mkdtemp(prefix="media-studio-cwd-")))
        self._own_cwd = cwd is None

    def __enter__(self):
        from halo_harness.studio import media_api
        self.comfy = FakeComfy()
        super().__enter__()
        self._saved = media_api.URL
        media_api.URL = self.comfy.url
        return self

    def __exit__(self, *a):
        from halo_harness.studio import media_api
        media_api.URL = self._saved
        super().__exit__(*a)
        self.comfy.close()
        if self._own_cwd:
            shutil.rmtree(self.repo, ignore_errors=True)


def wait_for(pred, timeout: float = 15.0, step: float = 0.02) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if pred():
            return True
        time.sleep(step)
    return bool(pred())
