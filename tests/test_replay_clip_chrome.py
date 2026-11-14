"""tests.test_replay_clip_chrome -- the clip's Chrome never holds the live Studio's token, and on Linux / macOS it opens
no DevTools port (Halo 3.4.1.2, the 2026-11-12 review's SERVERS-5 and PACKS-8; live/clip_chrome.py, live/clip_pipe.py,
live/replay_clip.py `_studio`):

1. the Chrome a clip starts carries `--remote-debugging-pipe` and no `--remote-debugging-port` where pipes work (POSIX),
   `--remote-debugging-port=0` only on Windows; on POSIX a real Chrome answers over the pipe and writes no
   DevToolsActivePort file (no port was opened).
2. Studio's Export a clip films through a throwaway Studio of its own: its token is not the live one, it answers the
   replay page's GETs and nothing else (no write, no settings values, no fleet view, no live feed), and stopping it
   leaves the local servers a Studio started alone.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.owner_rig import fetch  # noqa: E402
from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all  # noqa: E402

TIER = "full"  # a real headless Chrome in the last test: the full tier
test, TESTS = new_registry()


@test
def test_servers_5_the_clip_chrome_never_opens_a_debugging_port_where_pipes_work(ctx: Ctx):
    from halo_harness.live import clip_chrome, clip_pipe
    seen: list = []

    def fake(argv, *a, **kw):
        seen.append(list(argv))
        raise OSError("stop here")
    was = (clip_pipe.spawn, clip_chrome.subprocess.Popen)
    clip_pipe.spawn, clip_chrome.subprocess.Popen = fake, fake
    try:
        try:
            clip_chrome.Chrome("chrome", 800, 600)
        except OSError:
            pass
    finally:
        clip_pipe.spawn, clip_chrome.subprocess.Popen = was
    argv = seen[0] if seen else []
    if os.name == "posix":
        ctx.check(f"POSIX: --remote-debugging-pipe, no port, got {argv}", "--remote-debugging-pipe" in argv
                  and not any(a.startswith("--remote-debugging-port") for a in argv))
    else:
        ctx.check(f"Windows: the port, only because pipes cannot be handed over there, got {argv}",
                  "--remote-debugging-port=0" in argv and not clip_chrome.pipe_ok())


@test
def test_servers_5_export_a_clip_films_through_a_throwaway_read_only_studio(ctx: Ctx):
    from tests.helpers.packs_studio import PackStudio
    from halo_harness.live import replay_clip
    from halo_harness.providers import local_runtime
    with PackStudio() as s:
        stopped: list = []
        was_stop = local_runtime.stop_all_managed_servers_except_kept
        local_runtime.stop_all_managed_servers_except_kept = lambda *a, **k: stopped.append(a)
        try:
            base, token, stop = replay_clip._studio(s.state, s.repo)
            ctx.check("its token is its own", token != s.token and not base.endswith(f":{s.srv.server_address[1]}"))
            auth = {"Authorization": "Bearer " + token}
            ok = [p for p in ("state", "pack/registry", "replays", "lineups") if fetch(f"{base}/api/{p}", headers=auth)[0] == 200]
            ctx.check(f"the replay page's GETs answer, got {ok}", len(ok) == 4)
            for path in ("settings/values", "live", "sessions", "setup/state", "local/hosts"):
                ctx.check(f"GET {path}: refused", fetch(f"{base}/api/{path}", headers=auth)[0] == 403)
            for method, path in (("POST", "settings/set"), ("POST", "sessions/new"), ("POST", "shutdown"), ("PUT", "bio/x")):
                ctx.check(f"{method} {path}: refused", fetch(f"{base}/api/{path}", method=method, data=b"{}", headers=auth)[0] == 403)
            ctx.check("no live feed", fetch(f"{base}/api/events?t={token}")[0] == 403)
            ctx.check("the shell's page is served", fetch(base + "/")[0] == 200)
            stop()
            ctx.check(f"stopping it leaves the local servers alone, got {stopped}", not stopped)
        finally:
            local_runtime.stop_all_managed_servers_except_kept = was_stop
        filmed: list = []
        was_film = replay_clip.film
        replay_clip.film = lambda b, t, rid, times, exe: filmed.append((b, t)) or [b"x"]
        was_asm, was_find = replay_clip.assemble, replay_clip.fmt
        replay_clip.assemble, replay_clip.fmt = (lambda pngs, path, fps=5: 1), (lambda: "webp")
        try:
            from tests.helpers.replay_seed import SID, seed
            seed(s.state)
            from halo_harness.replay_verbs import cmd_verbs
            import contextlib
            import io
            with contextlib.redirect_stdout(io.StringIO()):
                cmd_verbs(["save", SID])
            rid = next((s.state / "replays").glob("*.halo-replay")).name[: -len(".halo-replay")]
            had = os.environ.get("HALO_CHROME")
            os.environ["HALO_CHROME"] = had or sys.executable  # find_chrome needs an existing path; film is stubbed
            try:
                status, got, _h = s.call("POST", f"replays/{rid}/clip", {"from": 0, "to": 100, "speed": 16})
            finally:
                os.environ.pop("HALO_CHROME", None) if had is None else None
            ctx.check(f"Export a clip answered, got {status} {got}", status == 200)
            ctx.check(f"the live token never reached the filming, got {[t[:4] for _b, t in filmed]}",
                      filmed and all(t != s.token for _b, t in filmed))
        finally:
            replay_clip.film, replay_clip.assemble, replay_clip.fmt = was_film, was_asm, was_find


@test
def test_servers_5_a_real_chrome_answers_over_the_pipe(ctx: Ctx):
    from halo_harness.live import clip_chrome
    if not clip_chrome.pipe_ok():
        raise SkipTest("pipes are POSIX only (the Windows clip films a throwaway Studio over the port)")
    from tests.helpers.chrome_driver import find_chrome
    from tests.helpers.chrome_lock import chrome_lock
    exe = find_chrome()
    if not exe:
        raise SkipTest("no Chrome found")
    with chrome_lock():
        c = clip_chrome.Chrome(exe, 800, 600)
        try:
            c.call("Page.navigate", url="data:text/html,<p id=x>piped</p>")
            got = c.wait("document.getElementById('x') && document.getElementById('x').textContent", 20)
            ctx.check(f"the page answered over the pipe, got {got!r}", got == "piped")
            ctx.check("no DevToolsActivePort file: no port was opened",
                      not os.path.exists(os.path.join(c.profile, "DevToolsActivePort")))
            ctx.check(f"its argv, got {c.argv}", "--remote-debugging-pipe" in c.argv)
        finally:
            c.close()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
