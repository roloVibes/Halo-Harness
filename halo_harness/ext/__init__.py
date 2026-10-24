"""halo_harness.ext -- the extension API a pack's code imports (Halo 3.2.0.0
R1, docs/EXTENSION_API.md). Stable at `API_VERSION` 1.0: a name listed in
`__all__` keeps its meaning for every 1.x; a pack imports this package and
nothing else of `halo_harness` (tests/test_ext_api.py checks the fixture
packs for exactly that).

    from halo_harness.ext import API_VERSION, read_yaml, get_config, publish_event

    API_VERSION / HALO_API_VERSION  "1.0": what pack.yaml's `halo_api` range is matched against
    read_yaml(path) / write_yaml(pack_id, path, data)
                                    Halo's YAML reader and writer (the bio and lineup files' own)
    check_schema(doc, schema)       one finding per shape problem (halo_harness.schemas.check)
    get_config(pack_id, key=None, default=None) / set_config(pack_id, key, value)
                                    the pack's settings: `packs.settings.<id>` over pack.yaml's defaults
    write_private(pack_id, path, text)
                                    a 0600 file, atomically, in the pack's data folder
    pack_dir(pack_id) / data_dir(pack_id)
                                    the pack's own folder (read-only) and its data folder
    publish_event(pack_id, kind, data=None)
                                    a frame on Studio's live feed, tagged with the pack's id (3.2.0.0 R5: checked
                                    against the kind's schema, kept in the pack's events log)
    memory.write(namespace, text, provenance=None)
                                    a note in the pack's memory namespace with its provenance (3.2.0.0 R5)
    is_granted(pack_id, permission) whether you granted the pack a permission it requests
    Unit                            the unit of work (halo_harness.work.unit.Unit)
    is_valid_pack_id, is_valid_name, qualified_name, split_name
                                    the name rules (`<id>--<name>` for a pack's bios and lineups)

The modules under this package are its implementation; the names above are the contract.
"""

from __future__ import annotations

API_VERSION = "1.0"
HALO_API_VERSION = API_VERSION

from halo_harness.ext.config import get_config, set_config  # noqa: E402
from halo_harness.ext.events import publish_event  # noqa: E402
from halo_harness.ext.files import data_dir, pack_dir, write_private  # noqa: E402
from halo_harness.ext.grants import is_granted  # noqa: E402
from halo_harness.ext import memory  # noqa: E402  (3.2.0.0 R5: memory.write)
from halo_harness.ext.names import is_valid_name, is_valid_pack_id, qualified_name, split_name  # noqa: E402
from halo_harness.ext.schema import check_schema  # noqa: E402
from halo_harness.ext.yamlio import read_yaml, write_yaml  # noqa: E402
from halo_harness.work.unit import Unit  # noqa: E402

__all__ = ["API_VERSION", "HALO_API_VERSION", "read_yaml", "write_yaml", "check_schema", "get_config",
           "set_config", "write_private", "pack_dir", "data_dir", "publish_event", "is_granted", "Unit",
           "is_valid_pack_id", "is_valid_name", "qualified_name", "split_name", "memory"]
