"""halo_harness.studio.files_live -- the `files_changed` frame on Studio's
live feed (Halo 3.2.2.0 R6, "I have to refresh the page"): what Studio shows
is what is on disk, as it changes.

A session's model edits an agent file, `halo maps use` sets config.json's
`crew.map`, a workflow is saved from the terminal: none of those writers publishes
anything (and none has to: this watcher sees every writer, the model's Edit
tool included). Each Studio server runs one daemon thread (started by
`server.start_server`, stopped by its `server_close`, the shape of
packs_studio_live.py) that lists, every POLL_S seconds (1.5;
`HALO_STUDIO_FILES_POLL_S` for tests):

    agents    the user `crew/agents/` and the project `.halo/crew/agents/` (`*.yaml`)
    workflows the user `crew/workflows/` and the project `.halo/crew/workflows/`
    maps      the user `crew/maps/` and the project `.halo/crew/maps/`
              (3.6.0.0 R5b: the crew folders, where it watched `teams/` and `agents/`)
    config    `config.json` in the state dir (`crew.map`, `roles.*`, `model`...)
    layouts   `studio/layouts/*.json` (the canvas positions; `_pc-x.json`
              lists as `_pc-x`)

by name, mtime and size. A change is gathered for DEBOUNCE_S (0.3 s, again
while files keep moving) and published once per kind:

    {"session_id": "studio", "event": "files_changed", "ts": ...,
     "data": {"kind": "agents", "names": [added or modified], "removed": [...]}}

through `EventBridge.publish_local`. The packs' own folders are
packs_studio_live.py's (`pack_changed`). Studio's own writes (a PUT agent,
workflow, map or layout) also come back as a frame 1.5 s later: that is fine, the page
that wrote is already current (it compares what it reads with what it holds).
"""

from __future__ import annotations

import os
import threading
import time
import weakref
from pathlib import Path

DEFAULT_POLL_S = 1.5
DEBOUNCE_S = 0.3
SETTLE_ROUNDS = 10  # a folder still moving after this many debounces publishes what it has
FRAME_KIND = "files_changed"
KINDS = ("agents", "workflows", "maps", "config", "layouts")


def poll_s() -> float:
    try:
        v = float(os.environ.get("HALO_STUDIO_FILES_POLL_S") or DEFAULT_POLL_S)
    except ValueError:
        v = DEFAULT_POLL_S
    return max(0.02, v)


def folders(cwd, state_dir) -> dict:
    """kind -> [(folder, suffix)], each folder once (a Studio started in the home dir has `.halo` twice). 3.6.0.0 R5c:
    the project's `.halo/crew` only in a trusted folder -- the rule crew/store.folders reads it by."""
    from halo_harness.crew.store import folders as crew_folders
    state = Path(state_dir)
    proj = [f.parent.parent for f, scope in crew_folders("agent", cwd=cwd, state_dir=state) if scope == "project"]
    out: dict = {"agents": [], "workflows": [], "maps": [], "config": [], "layouts": [(state / "studio" / "layouts", ".json")]}
    for kind in ("agents", "workflows", "maps"):
        seen = set()
        for base in [state] + proj:
            d = base / "crew" / kind
            key = os.path.normcase(os.path.abspath(str(d)))
            if key not in seen:
                seen.add(key)
                out[kind].append((d, ".yaml"))
    return out


def _listing(folder: Path, suffix: str) -> dict:
    out: dict = {}
    try:
        entries = list(os.scandir(folder))
    except OSError:  # not there (yet): nothing listed
        return out
    for e in entries:
        if not e.name.endswith(suffix) or e.name.startswith("."):
            continue
        try:
            st = e.stat()
            if not e.is_file():
                continue
        except OSError:  # removed while listed: the next look says so
            continue
        out.setdefault(e.name[: -len(suffix)], []).append((str(folder), st.st_mtime_ns, st.st_size))
    return out


def snapshot(cwd, state_dir) -> dict:
    """kind -> {name: a sorted tuple of (folder, mtime_ns, size)} for every file it covers."""
    snap: dict = {}
    for kind, dirs in folders(cwd, state_dir).items():
        names: dict = {}
        for d, suffix in dirs:
            for name, sig in _listing(d, suffix).items():
                names.setdefault(name, []).extend(sig)
        snap[kind] = {n: tuple(sorted(v)) for n, v in names.items()}
    cfg = Path(state_dir) / "config.json"
    try:
        st = cfg.stat()
        snap["config"] = {"config": ((str(cfg), st.st_mtime_ns, st.st_size),)}
    except OSError:
        snap["config"] = {}
    return snap


def diff(old: dict, new: dict) -> list:
    """The `data` of each kind that moved between two snapshots (KINDS order), names sorted."""
    out = []
    for kind in KINDS:
        a, b = old.get(kind) or {}, new.get(kind) or {}
        names = sorted(n for n, sig in b.items() if a.get(n) != sig)
        removed = sorted(n for n in a if n not in b)
        if names or removed:
            out.append({"kind": kind, "names": names, "removed": removed})
    return out


class Watcher:
    """Polls the folders of one Studio (cwd, state_dir) and calls `publish(frame)` once per change set and kind."""

    def __init__(self, cwd, state_dir, publish, *, poll: "float | None" = None, debounce: float = DEBOUNCE_S, alive=None):
        self.cwd, self.state_dir, self._publish, self._alive = cwd, state_dir, publish, alive
        self.poll = poll if poll is not None else poll_s()
        self.debounce = debounce
        self._stop = threading.Event()
        self._thread: "threading.Thread | None" = None
        self.last = snapshot(cwd, state_dir)  # the base: taken now, so a change right after the start is seen
        self.published = 0

    def start(self) -> "Watcher":
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="halo-studio-files", daemon=True)
            self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()

    stopped = property(lambda self: self._stop.is_set())

    def _run(self) -> None:
        while not self._stop.wait(self.poll):
            if self._alive is not None and not self._alive():  # the server went (closed, or never closed and collected)
                return
            try:
                self.tick()
            except Exception:  # one bad look never ends the watcher
                pass

    def tick(self) -> list:
        """One look: when something moved, wait until the folders hold still (DEBOUNCE_S, at most
        SETTLE_ROUNDS times), then publish one frame per kind that moved. Returns the frames."""
        now = snapshot(self.cwd, self.state_dir)
        if now == self.last:
            return []
        for _ in range(SETTLE_ROUNDS):
            if self._stop.wait(self.debounce):
                return []
            again = snapshot(self.cwd, self.state_dir)
            if again == now:
                break
            now = again
        frames = [{"session_id": "studio", "event": FRAME_KIND, "ts": time.time(), "data": d} for d in diff(self.last, now)]
        self.last = now
        for f in frames:
            try:
                self._publish(f)
                self.published += 1
            except Exception:  # a frame that cannot go out never ends the watcher
                pass
        return frames


def _closed(server) -> bool:
    try:
        return server.socket.fileno() == -1
    except (AttributeError, OSError, ValueError):
        return True


def watch(server) -> "Watcher | None":
    """The server's watcher (`server.files_watch`), started once; its frames go to every browser of the server."""
    if getattr(server, "files_watch", None) is not None:
        return server.files_watch

    ref = weakref.ref(server)  # the thread holds no server alive

    def alive() -> bool:
        srv = ref()
        return srv is not None and not _closed(srv)

    def publish(frame: dict) -> None:
        from halo_harness.studio.events import bridge_for
        srv = ref()
        if srv is not None:
            bridge_for(srv).publish_local(frame)
            if (frame.get("data") or {}).get("kind") == "config":  # 3.6.0.0 R13: `halo config set ollama.steward.job`
                from halo_harness.studio.server import sync_steward
                sync_steward(srv)

    try:
        server.files_watch = Watcher(server.cwd, server.state_dir, publish, alive=alive).start()
    except Exception:  # Studio still serves; the pages just do not hear disk changes
        server.files_watch = None
    return server.files_watch
