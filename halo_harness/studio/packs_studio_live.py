"""halo_harness.studio.packs_studio_live -- the `pack_changed` frame on
Studio's live feed (Halo 3.2.0.0 R3): the shell reloads `GET
/api/pack/registry` when it arrives, so a pack you enable, disable, install,
update or remove shows (or goes) without a reload.

    watch(server)    once per server (the first registry read): a daemon
                     thread compares what the packs depend on (packs/registry.py's
                     key: each packs folder, each pack.yaml, state.json) every
                     POLL_S seconds and publishes `pack_changed` when it moved --
                     a `halo pack` run in another terminal reaches this Studio
    notify(why)      in this process: every Studio it serves hears it now
                     (packs/grants.py `changed`, after enable, disable, update,
                     remove; packs/install.py after an install)

The frame is `{"event": "pack_changed", "session_id": null, "data": {"why"}}`
through `EventBridge.publish_local`; it names no pack (the registry says).
3.2.0.0 R4: every `pack_changed` also marks this harness's capabilities
catalog stale (`fleet.capabilities.invalidate`), so the packs' fleet
capabilities are gathered afresh and the hub hears the new hash.
"""

from __future__ import annotations

import threading
import time
import weakref

POLL_S = 2.0
FRAME_KIND = "pack_changed"
_lock = threading.Lock()
_servers: "weakref.WeakSet" = weakref.WeakSet()
_last: dict = {}  # id(server) -> the signature it last published for


def signature(cwd, state_dir):
    from halo_harness.packs import discover as D
    from halo_harness.packs import registry as REG
    if not D.project_packs_dir(cwd).is_dir() and not D.user_packs_dir(state_dir).is_dir():
        return None
    return REG._key(cwd, state_dir)


def _closed(server) -> bool:
    try:
        return server.socket.fileno() == -1
    except (AttributeError, OSError, ValueError):
        return True


def publish(server, why: str = "changed") -> None:
    from halo_harness.studio.events import bridge_for
    try:
        _last[id(server)] = signature(server.cwd, server.state_dir)
        from halo_harness.fleet.capabilities import invalidate
        invalidate(server.state_dir)
        bridge_for(server).publish_local({"event": FRAME_KIND, "data": {"why": why}})
    except Exception:  # a frame that cannot go out never breaks the caller (a halo pack verb)
        pass


def _loop(ref) -> None:
    while True:
        time.sleep(POLL_S)
        srv = ref()
        if srv is None or _closed(srv):
            return
        try:
            sig = signature(srv.cwd, srv.state_dir)
        except Exception:
            sig = _last.get(id(srv))
        if sig != _last.get(id(srv)):
            publish(srv, "changed")
        del srv


def watch(server) -> None:
    with _lock:
        if server in _servers:
            return
        _servers.add(server)
        _last[id(server)] = signature(server.cwd, server.state_dir)
    threading.Thread(target=_loop, args=(weakref.ref(server),), name="halo-studio-packs", daemon=True).start()


def notify(why: str = "changed") -> None:
    for srv in list(_servers):
        if not _closed(srv):
            publish(srv, why)
