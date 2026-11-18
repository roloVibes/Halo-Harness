"""tests.helpers.scratch_seven -- Halo 3.6.0.5 (a): a map of his of seven boxes, for the browser tests that edit, drag,
lock or need the default's boxes. The default (Auto, the shipped `auto.yaml`) is never edited and is drawn as groups
from package (b) on; these tests do their editing on this scratch map, named by the constant NAME (never a literal:
tests/helpers/studio_session_map_down_draw.py writes its own, different map named `seven`).

    write_seven(state_dir) -> Path   `<state_dir>/crew/maps/seven-boxes.yaml`: the shipped auto.yaml as crew.store.read
                                     reads it, named NAME, no `about:` (map/1, the same seven boxes and lines)
"""
from __future__ import annotations

from pathlib import Path

NAME = "seven-boxes"


def write_seven(state_dir) -> Path:
    from halo_harness.crew import store
    raw = dict(store.read(store.SHIPPED / "maps" / "auto.yaml") or {})
    raw.pop("about", None)
    raw["name"] = NAME
    path = Path(state_dir) / "crew" / "maps" / f"{NAME}.yaml"
    store.write_text(path, store.dump(raw))
    return path
