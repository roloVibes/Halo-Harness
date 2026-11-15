"""tests.helpers.config_read -- a test home's config.json, read the way the product's own readers ride out Windows.

    config_json(state) -> dict    `<state>/config.json` as the server last wrote it ({} when there is none)

On Windows the server's atomic replace of the file denies a read for a moment (PermissionError; CI runs 43173639949
and 43739114021). The product's writers and readers retry (privateio._replace_with_retry); a helper that read the
file raw failed the whole driver run instead. The read is tried again for up to two seconds, then raises.
"""
from __future__ import annotations

import json
import time
from pathlib import Path


def config_json(state) -> dict:
    path = Path(state) / "config.json"
    for attempt in range(40):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except PermissionError:
            if attempt == 39:
                raise
            time.sleep(0.05)
    return {}
