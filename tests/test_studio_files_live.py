"""tests.test_studio_files_live -- Halo 3.2.2.0 R6: Studio sees what the
session changes. `studio/files_live.py` polls the lineup, bio, config and
layout files (here every 0.1 s) and publishes one `files_changed` frame per
change set and kind:

1. a lineup written -> one frame naming it (kind lineups);
2. three files in a burst -> one frame with the three names;
3. a file deleted -> its name under `removed`;
4. config.json -> kind config; a layout -> kind layouts; a bio -> kind bios;
5. a Studio started in the home dir (cwd/.halo is the state dir) lists the
   folder once;
6. through a real server: the frame reaches a browser queue, even one that
   follows a single session, and server_close stops the watcher.

Run: python -m tests.test_studio_files_live
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
POLL = 0.1


class _Home:
    """A temp state dir (`<tmp>/.halo`) and project (`<tmp>/proj`) with a watcher on a 0.1 s poll."""

    def __init__(self, project_is_home: bool = False):
        self.root = Path(tempfile.mkdtemp(prefix="studio-files-live-"))
        self.state = self.root / ".halo"
        for sub in ("teams", "agents", "studio/layouts"):
            (self.state / sub).mkdir(parents=True)
        self.proj = self.root if project_is_home else self.root / "proj"
        self.proj.mkdir(exist_ok=True)
        self.frames: list = []
        self._lock = threading.Lock()

    def __enter__(self):
        from halo_harness.studio.files_live import Watcher
        self.w = Watcher(self.proj, self.state, self._got, poll=POLL).start()
        return self

    def __exit__(self, *a):
        self.w.stop()
        time.sleep(POLL * 2)
        shutil.rmtree(self.root, ignore_errors=True)

    def _got(self, frame: dict) -> None:
        with self._lock:
            self.frames.append(frame)

    def write(self, rel: str, text: str = "name: x\n") -> None:
        p = self.state / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def wait(self, n: int = 1, timeout: float = 4.0, quiet: float = 0.6) -> list:
        """The frames once `n` arrived and nothing more came for `quiet` seconds."""
        end = time.time() + timeout
        while time.time() < end and len(self.frames) < n:
            time.sleep(0.02)
        time.sleep(quiet)
        with self._lock:
            got, self.frames = list(self.frames), []
        return got


def _data(frames: list) -> list:
    return [f.get("data") for f in frames]


@test
def test_a_lineup_written_is_one_frame_naming_it(ctx: Ctx):
    with _Home() as h:
        h.write("teams/alpha.yaml")
        got = h.wait()
        ctx.check(f"one frame, kind lineups, naming alpha, got {_data(got)}",
                  _data(got) == [{"kind": "lineups", "names": ["alpha"], "removed": []}])
        f = got[0] if got else {}
        ctx.check(f"the frame's shape: studio's files_changed with a ts, got {f}",
                  f.get("session_id") == "studio" and f.get("event") == "files_changed" and isinstance(f.get("ts"), float))
        h.write("teams/alpha.yaml", "name: alpha\ndescription: edited by a session\n")
        ctx.check("an edit of it is another frame", _data(h.wait()) == [{"kind": "lineups", "names": ["alpha"], "removed": []}])
        ctx.check("nothing moves: no frame", h.wait(1, timeout=0.5, quiet=0.2) == [])


@test
def test_a_burst_of_three_files_is_one_frame(ctx: Ctx):
    with _Home() as h:
        for n in ("one", "two", "three"):
            h.write(f"teams/{n}.yaml")
        got = _data(h.wait())
        ctx.check(f"one frame with the three names, got {got}",
                  got == [{"kind": "lineups", "names": ["one", "three", "two"], "removed": []}])


@test
def test_a_deleted_file_is_named_under_removed(ctx: Ctx):
    with _Home() as h:
        h.write("agents/scout.yaml")
        h.wait()
        (h.state / "agents" / "scout.yaml").unlink()
        got = _data(h.wait())
        ctx.check(f"kind bios, removed scout, got {got}", got == [{"kind": "bios", "names": [], "removed": ["scout"]}])


@test
def test_config_layouts_and_bios_each_have_their_kind(ctx: Ctx):
    with _Home() as h:
        h.write("config.json", json.dumps({"team": "alpha"}))
        ctx.check("config.json -> kind config", _data(h.wait()) == [{"kind": "config", "names": ["config"], "removed": []}])
        h.write("studio/layouts/alpha.json", json.dumps({"nodes": {}, "tiers": {}}))
        ctx.check("a layout -> kind layouts", _data(h.wait()) == [{"kind": "layouts", "names": ["alpha"], "removed": []}])
        h.write("agents/scout.yaml")
        h.write("teams/beta.yaml")
        got = _data(h.wait(2))
        ctx.check(f"a bio and a lineup together: one frame per kind, got {got}",
                  got == [{"kind": "lineups", "names": ["beta"], "removed": []}, {"kind": "bios", "names": ["scout"], "removed": []}])
        h.write("teams/.hidden.yaml")
        h.write("teams/notes.txt")
        ctx.check("a dot file or another suffix is no lineup", h.wait(1, timeout=0.6, quiet=0.1) == [])


@test
def test_project_halo_and_state_dir_the_same_folder_list_once(ctx: Ctx):
    from halo_harness.studio.files_live import folders, snapshot
    with _Home(project_is_home=True) as h:
        ctx.check("the teams folder is listed once", len(folders(h.proj, h.state)["lineups"]) == 1)
        h.write("teams/solo.yaml")
        got = _data(h.wait())
        ctx.check(f"one frame naming it once, got {got}", got == [{"kind": "lineups", "names": ["solo"], "removed": []}])
        ctx.check("one signature for it", len(snapshot(h.proj, h.state)["lineups"]["solo"]) == 1)
    with _Home() as h:
        (h.proj / ".halo" / "teams").mkdir(parents=True)
        (h.proj / ".halo" / "teams" / "repo.yaml").write_text("name: repo\n", encoding="utf-8")
        got = _data(h.wait())
        ctx.check(f"the project's .halo/teams is watched too, got {got}", got == [{"kind": "lineups", "names": ["repo"], "removed": []}])


@test
def test_the_frame_reaches_a_browser_and_server_close_stops_the_watch(ctx: Ctx):
    from halo_harness.studio.events import bridge_for
    from halo_harness.studio.server import start_server
    old = os.environ.get("HALO_STUDIO_FILES_POLL_S")
    os.environ["HALO_STUDIO_FILES_POLL_S"] = str(POLL)
    root = Path(tempfile.mkdtemp(prefix="studio-files-srv-"))
    state = root / ".halo"
    (state / "teams").mkdir(parents=True)
    srv = start_server(port=0, cwd=root / "proj", state_dir=state)
    try:
        w = srv.files_watch
        ctx.check("start_server started the watcher on the env poll", w is not None and abs(w.poll - POLL) < 1e-9)
        bridge = bridge_for(srv)
        everyone, one = bridge.subscribe("all"), bridge.subscribe("some-session")
        (state / "teams" / "live.yaml").write_text("name: live\n", encoding="utf-8")

        def first(q):
            end = time.time() + 4
            while time.time() < end:
                f = q.get(0.2)
                if f and f.get("event") == "files_changed":
                    return f
            return None
        got = first(everyone)
        ctx.check(f"the browser hears it, got {got}", bool(got) and got["data"] == {"kind": "lineups", "names": ["live"], "removed": []})
        ctx.check("a browser following one session hears it too", bool(first(one)))
    finally:
        srv.server_close()
        if old is None:
            os.environ.pop("HALO_STUDIO_FILES_POLL_S", None)
        else:
            os.environ["HALO_STUDIO_FILES_POLL_S"] = old
    ctx.check("server_close stopped the watcher", srv.files_watch.stopped)
    time.sleep(POLL * 3)
    ctx.check("its thread ended", not (srv.files_watch._thread and srv.files_watch._thread.is_alive()))
    shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
