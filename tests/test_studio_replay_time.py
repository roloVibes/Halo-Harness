"""tests.test_studio_replay_time -- Agents -> Live's scrubber and the replay file in headless Chrome (Halo 3.4.1.0 R1
"Time"), through tests/helpers/studio_replay_time.py (skipped without Chrome); no model call:

1. History's row opens an ended session on the scrubber at its end: one mark per spawn, hand-off, ask, failure and
   finish, the phase bands;
2. the canvas is redrawn as it was at three seeded moments (who existed, each state), with the banner's moment, the
   sentence rebuilt for that moment (an ask first) and the cost so far;
3. Play at 16x moves the moment and pauses;
4. Save says what the file holds, what it costs and where it writes, then writes it; Export a clip saves first and says
   its frames, width, format and path; with Pillow hidden it still says them, one line says what to install and Export
   is off (3.4.1.0 R6); Now returns to what runs;
5. a saved file is a History row; Open a file takes one made elsewhere and keeps it; `?replay=<id>&at=22` opens it at
   that moment;
6. `halo replay clip` films a saved replay in Chrome and writes one animated file 1200 px wide.
Run: python -m tests.test_studio_replay_time
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.driver_got import got as driver_got  # noqa: E402
from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
_RUN: dict = {}
REPO = Path(__file__).resolve().parent.parent


def _got(ctx: Ctx) -> dict:
    return driver_got(ctx, "tests.helpers.studio_replay_time", why="the scrubber needs headless Chrome", cache=_RUN, timeout=300)


@test
def test_a_row_opens_on_the_scrubber_with_marks_and_bands(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"nine marks, got {got.get('opened')}", got.get("opened") == "9")
    ctx.check(f"every kind of mark, got {got.get('kinds')}", set(got.get("kinds") or []) == {"spawn", "handoff", "ask", "fail", "finish"})
    ctx.check(f"the phase bands, got {got.get('bands')}", {"thinking", "tool", "waiting", "writing"} <= set(got.get("bands") or []))
    ctx.check(f"it opens at its end, got {got.get('at_end')}", got.get("at_end") == "100")


@test
def test_the_canvas_as_it_was_at_three_moments(ctx: Ctx):
    got = _got(ctx)
    a, b, c = got.get("at5") or {}, got.get("at22") or {}, got.get("at95") or {}
    ctx.check(f"+5 s: main alone, at work, nothing spent, got {a}", a.get("nodes") == [["main", "running"]] and a.get("cost") == "$0.0000")
    ctx.check(f"+22 s: main waits on you, the scout and the fixer work, got {b.get('nodes')}",
              sorted(b.get("nodes") or []) == [["fixer1", "running"], ["main", "waiting"], ["scout1", "running"]])
    ctx.check(f"+22 s: the sentence says the ask first, got {b.get('said')!r}", str(b.get("said")).startswith("waiting on you: main asks: Bash: rm -rf build"))
    ctx.check(f"+95 s: the scout done, the fixer failed, $0.03 spent, got {c}",
              sorted(c.get("nodes") or []) == [["fixer1", "failed"], ["main", "running"], ["scout1", "done"]] and c.get("cost") == "$0.0300")
    ctx.check(f"the banner names the moment, got {b.get('banner')!r}", str(b.get("banner")).startswith("replay -- ") and "ship it" in str(b.get("banner")))
    ctx.check(f"who works, got {a.get('lit')} / {b.get('lit')} / {c.get('lit')}", a.get("lit") == "main" and b.get("lit") == "main,fixer,scout" and c.get("lit") == "main")


@test
def test_play_moves_and_pauses(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"Play at 16x moved the moment, got {got.get('moving')}", (got.get("moving") or 0) >= 16)
    ctx.check(f"and pauses, got {got.get('paused')}", got.get("paused") == "paused")


@test
def test_save_and_clip_say_what_they_write_first(ctx: Ctx):
    got = _got(ctx)
    holds, says = got.get("holds") or [], got.get("says") or []
    ctx.check(f"Save lists what the file holds and what it leaves out, got {holds}",
              len(holds) == 5 and holds[0].startswith("3 agents") and any(h.startswith("not included") for h in holds))
    ctx.check(f"DOES / COSTS / WRITES before it writes, got {says}", len(says) == 3 and says[1] == "nothing: no model call" and ".halo-replay" in says[2])
    folder = str(got.get("wrote") or "").rsplit("replays", 1)[0]
    ctx.check(f"it wrote one file where it said (the name carries the second it was saved), got {got.get('wrote')!r}",
              str(got.get("wrote")).endswith(".halo-replay") and bool(folder) and says[2].startswith(folder + "replays"))
    clip = got.get("clip_says") or []
    ctx.check(f"a clip of an unsaved session saves first, said, got {got.get('clip_first')}", "Save writes it first" in str((got.get("clip_first") or [""])[0]))
    ctx.check(f"then its frames, width, format and path, got {clip}",
              len(clip) == 3 and "1200 px wide" in clip[0] and "frames" in clip[0] and "at most 30 s" in clip[0] and "clips" in clip[2])
    hidden, back = got.get("clip_hidden") or [], got.get("clip_back") or []
    ctx.check(f"Pillow hidden: the plan still says the frames, one line says what to install, Export is off, got {hidden}",
              len(hidden) == 3 and "frames" in hidden[0] and "needs Pillow" in hidden[1] and "halo-harness[images]" in hidden[1]
              and hidden[2] is True)
    ctx.check(f"Pillow back: the line goes where Pillow is installed (here: {got.get('clip_pillow')}), got {back}",
              len(back) == 2 and back[0] is (not got.get("clip_pillow")) and "frames" in back[1])
    ctx.check(f"the replay is now the saved file, and Now returns, got {got.get('now_file')} / {got.get('now')}",
              str(got.get("now_file")).startswith("replay0000seed") and got.get("now") == "now")


@test
def test_files_open_from_history_and_the_door(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"a saved file is a History row, got {got.get('rows')}", "file" in (got.get("rows") or []))
    ctx.check(f"Open a file takes one made elsewhere and keeps it, got {got.get('picked')} / {got.get('kept')}",
              got.get("picked") == "elsewhere-1" and got.get("kept") is True)
    ctx.check(f"?replay=<id>&at=22 opens it at that moment, got {got.get('door')}",
              sorted(got.get("door") or []) == [["fixer1", "running"], ["main", "waiting"], ["scout1", "running"]])


@test
def test_halo_replay_clip_films_one_file(ctx: Ctx):
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (the clip is filmed in headless Chrome)")
    try:
        import PIL  # noqa: F401
    except ImportError:
        raise SkipTest("no Pillow (the clip is assembled with it)")
    from PIL import Image
    from tests.helpers.chrome_lock import chrome_lock
    with tempfile.TemporaryDirectory(prefix="halo-clip-") as home:
        env = {**driver_env(REPO), "BRIDGE_TEST_HOME": home, "HALO_CHROME": find_chrome() or ""}
        env.pop("BRIDGE_STATE_DIR", None)
        from tests.helpers.replay_seed import SID, seed
        seed(Path(home) / ".halo")

        def halo(*args: str) -> subprocess.CompletedProcess:
            return subprocess.run([sys.executable, "-m", "halo_harness", "replay", *args], capture_output=True, encoding="utf-8",
                                  errors="replace", env=env, cwd=home, timeout=240, stdin=subprocess.DEVNULL)
        saved = halo("save", SID)
        ctx.check(f"saved: {saved.stdout[-200:]!r} {saved.stderr[-200:]!r}", saved.returncode == 0)
        rid = next((Path(home) / ".halo" / "replays").glob("*.halo-replay")).name[: -len(".halo-replay")]
        with chrome_lock():
            r = halo("clip", rid, "--from", "0", "--to", "100", "--speed", "16")
        ctx.check(f"filmed: {r.stdout[-300:]!r} {r.stderr[-300:]!r}", r.returncode == 0 and "Wrote " in r.stdout)
        clips = list((Path(home) / ".halo" / "replays" / "clips").glob(f"{rid}-0-100.*"))
        ctx.check(f"one file under replays/clips, got {clips}", len(clips) == 1)
        with Image.open(clips[0]) as im:
            ctx.check(f"1200 px wide, animated, got {im.size} {getattr(im, 'n_frames', 1)}", im.size[0] == 1200 and getattr(im, "n_frames", 1) >= 2)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="studio replay time"))
