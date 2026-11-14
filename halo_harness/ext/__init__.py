"""halo_harness.ext -- the extension API a pack's code imports (Halo 3.2.0.0
R1, docs/EXTENSION_API.md). `API_VERSION` 1.2 (3.3.10.0 R1, 1.1: + set_mode,
current_mode; 3.3.13.0, 1.2: + remote, contributes.services (R3), + host, a section's view, a pack's routes (R2); a 1.0 or 1.1 pack keeps everything): a name listed in
`__all__` keeps its meaning for every 1.x; a pack imports this package and
nothing else of `halo_harness` (tests/test_ext_api.py checks the fixture
packs for exactly that).

    from halo_harness.ext import API_VERSION, read_yaml, get_config, publish_event

    API_VERSION / HALO_API_VERSION  "1.4": what pack.yaml's `halo_api` range is matched against
    api_version() / compatible(range) / deprecations()
                                    3.2.0.0 R7: this API's version, whether a `halo_api` range takes it under the
                                    policy below, the names announced for removal (none in 1.0)
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
    set_mode(pack_id, mode_id, on=True) / current_mode(pack_id)
                                    3.3.10.0 (API 1.1): the pack's runtime mode (mode.json); turning a
                                    mode on arms the policy hooks that name it
    testing                         3.3.12.0 R4 (API 1.1): a pack's tests -- testing.run(folder) makes every check
                                    `halo pack test` makes (a scratch home, no model, no network); Report.add for its own;
                                    3.3.13.0 R2 (API 1.2): scratch_home(), studio(folder) (a live Studio with the pack
                                    linked and granted), pack_module(folder, rel)
    remote                          3.3.13.0 R3 (API 1.2): the transport seam -- the live sessions and their control
                                    sockets, a session started for a transport, the cards' text, the notes, a voice
                                    note's transcript, a pack service's row (ext/remote.py)
    host                            3.3.13.0 R2 (API 1.2): what Halo does for the pack's code -- its state folder,
                                    models for a task, registered MCP servers and a probe, the tool env, a URL fetch,
                                    Halo as a child process, ComfyUI (ext/host.py)
    core                            3.4.0.0 B (API 1.3, draft): the core modules a shipped pack that left the core still
                                    drives -- core.module(name), core.get(name, attr), over core.REACHABLE (ext/core.py)
    Unit                            the unit of work (halo_harness.work.unit.Unit)
    is_valid_pack_id, is_valid_name, qualified_name, split_name
                                    the name rules (`<id>--<name>` for a pack's bios and lineups)

The modules under this package are its implementation; the names above are the contract.

The version policy (3.2.0.0 R7, ext/compat.py; docs/EXTENSION_API.md "Compatibility and migration"):
`API_VERSION` is MAJOR.MINOR. A minor version only adds names, and every name keeps its meaning for
every later minor of its major. A major version may remove a name, and only one `deprecations()` listed
for at least one minor version before it. A pack's `halo_api: {min, max}` is matched against it: `max`
is inclusive at its own precision, and with no `max` the pack runs on its `min`'s major only.
"""

from __future__ import annotations

API_VERSION = "1.4"  # 3.3.10.0 R1: 1.1 adds set_mode, current_mode; 3.3.13.0: 1.2 adds remote, contributes.services (R3), host, a section's view, a pack's routes (R2); 3.4.0.0: 1.3 adds contributes.cli/.slash/.doctor/.settings and core (draft); 3.5.0.0: 1.4 adds contributes.capabilities (contributes.fleet's new name). MAJOR.MINOR: a minor adds names, a major removes only names deprecations() announced
HALO_API_VERSION = API_VERSION

from halo_harness.ext.compat import api_version, compatible, deprecations  # noqa: E402  (3.2.0.0 R7)
from halo_harness.ext.config import get_config, set_config  # noqa: E402
from halo_harness.ext.events import publish_event  # noqa: E402
from halo_harness.ext.files import data_dir, pack_dir, write_private  # noqa: E402
from halo_harness.ext.grants import is_granted  # noqa: E402
from halo_harness.ext import memory  # noqa: E402  (3.2.0.0 R5: memory.write)
from halo_harness.ext import testing  # noqa: E402  (3.3.12.0 R4, API 1.1: a pack's tests, halo pack test)
from halo_harness.ext import host  # noqa: E402  (3.3.13.0 R2, API 1.2: the host services)
from halo_harness.ext.mode import current_mode, set_mode  # noqa: E402  (3.3.10.0 R1, API 1.1)
from halo_harness.ext import remote  # noqa: E402  (3.3.13.0 R3, API 1.2: the transport seam)
from halo_harness.ext import core  # noqa: E402  (3.4.0.0 B, API 1.3 draft: the core modules a shipped pack drives)
from halo_harness.ext.names import is_valid_name, is_valid_pack_id, qualified_name, split_name  # noqa: E402
from halo_harness.ext.schema import check_schema  # noqa: E402
from halo_harness.ext.yamlio import read_yaml, write_yaml  # noqa: E402
from halo_harness.work.unit import Unit  # noqa: E402

__all__ = ["API_VERSION", "HALO_API_VERSION", "read_yaml", "write_yaml", "check_schema", "get_config",
           "set_config", "write_private", "pack_dir", "data_dir", "publish_event", "is_granted", "Unit",
           "is_valid_pack_id", "is_valid_name", "qualified_name", "split_name", "memory",
           "api_version", "compatible", "deprecations",  # 3.2.0.0 R7: the version policy
           "set_mode", "current_mode",  # 3.3.10.0 R1: API 1.1
           "testing",  # 3.3.12.0 R4: API 1.1, stable (testing.run, Report, manifest, ask_policy)
           "remote", "host",  # 3.3.13.0: API 1.2, stable (the transport seam ext/remote.py; the host services ext/host.py)
           "core"]  # 3.4.0.0 B: API 1.3, draft (ext/core.py: the first-run and coach packs' door to the engine)
