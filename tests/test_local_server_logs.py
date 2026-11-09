"""tests.test_local_server_logs -- a server's log tail reads that server's files only (Halo 3.3.14.0 R2;
providers/local_server.tail, studio/local_server_api.py, ollama_steward/log_tail.local_tail):

1. REVIEW #39 (LOCAL-5): `tail(id)` for an id no registry row has reads nothing (`../x`, an absolute path, a plain
   name), and Studio's `local/server/<id>/log` answers 404; a registry row's log still reads;
2. REVIEW #42 (LOCAL-8): llama-6000's rotation set is llama-6000.log, llama-6000-1.log, llama-6000.log.1: a sibling
   server whose id shares the prefix (llama-60001) is never mixed in.
Run: python -m tests.test_local_server_logs"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.config_seed import ConfigHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


@test
def test_an_unknown_id_reads_nothing(ctx: Ctx):
    from halo_harness.providers import local_runtime as R
    from halo_harness.providers.local_server import servers_dir, tail
    from halo_harness.studio.local_server_api import server_act
    with ConfigHome() as h:
        state = h.home / ".halo"
        other = h.home / "elsewhere" / "app.log"
        other.parent.mkdir(parents=True)
        other.write_text("a line of some other program's log\n", encoding="utf-8")
        logs = servers_dir(state)
        logs.mkdir(parents=True, exist_ok=True)
        (logs / "orphan.log").write_text("an old line\n", encoding="utf-8")
        for key in ("../../elsewhere/app", str(h.home / "elsewhere" / "app"), "orphan"):
            got = tail(key, 10, state_dir=state)
            ctx.check(f"tail({key!r}) reads nothing, got {got}", got["ok"] is False and got["lines"] == []
                      and "no server Halo started" in got["say"])
        req = SimpleNamespace(state_dir=state, query={"n": "5"})
        code, body = server_act(req, "../../elsewhere/app", "log")
        ctx.check(f"Studio answers 404, got {code} {body}", code == 404 and not body.get("lines"))
        (logs / "llama-6000.log").write_text("srv  ready\n", encoding="utf-8")
        R.save_registry(state, [{"id": "llama-6000", "model": "m", "port": 6000, "pid": None, "halo": True,
                                 "kind": "llama-server", "log": str(logs / "llama-6000.log")}])
        got = tail("llama-6000", 10, state_dir=state)
        ctx.check(f"a registry row's log reads, got {got}", got["ok"] and got["lines"] == ["srv  ready"])


@test
def test_the_rotation_set_is_that_servers_own(ctx: Ctx):
    from halo_harness.ollama_steward.log_tail import local_tail
    with ConfigHome() as h:
        d = h.home / "servers"
        d.mkdir()
        files = {"llama-6000.log.1": "oldest line of llama-6000", "llama-6000-1.log": "older line of llama-6000",
                 "llama-6000.log": "line of llama-6000", "llama-60001.log": "line of llama-60001 (another server)",
                 "llama-6000-extra.log": "a file that is not a rotation"}
        now = time.time()
        for i, (name, text) in enumerate(files.items()):
            (d / name).write_text(text + "\n", encoding="utf-8")
            os.utime(d / name, (now - 100 + i, now - 100 + i))
        got = local_tail(d / "llama-6000.log", 50)
        ctx.check(f"only llama-6000's files, oldest first, got {got}", got == [
            "oldest line of llama-6000", "older line of llama-6000", "line of llama-6000"])
        ctx.check("the sibling's own tail reads its file", local_tail(d / "llama-60001.log", 50) == [
            "line of llama-60001 (another server)"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
