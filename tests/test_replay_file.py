"""tests.test_replay_file -- Halo 3.4.1.0 R1 "Time": a session's time axis (live/timeline.py), its replay as one file
(live/replay_file.py: round trip, redaction, an older file still opens), the clip's frames and file
(live/replay_clip.py), Studio's `replays/*` routes and `halo replay list | save | open | clip`.

A seeded session: main asks the owner, spawns a scout (hands back) and a fixer (fails); a fake key sits in the title,
a task, an ask and a hand-back, and the project path in the meta. Run: python -m tests.test_replay_file
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.replay_seed import FAKE_KEY, SID, T0, seed  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


@contextlib.contextmanager
def _home():
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
    with tempfile.TemporaryDirectory(prefix="halo-replay-") as d:
        os.environ["BRIDGE_TEST_HOME"] = d
        os.environ.pop("BRIDGE_STATE_DIR", None)
        try:
            from halo_harness.config.paths import bridge_home
            yield bridge_home()
        finally:
            for k, v in saved.items():
                os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


def _hist(state: Path) -> dict:
    from halo_harness.live import history
    return history.read(seed(state))


@test
def test_timeline_marks_and_bands(ctx: Ctx):
    from halo_harness.live import timeline
    with _home() as state:
        h = _hist(state)
        marks = timeline.marks(h)
        kinds = [m["kind"] for m in marks]
        ctx.check(f"a spawn per sub-agent, the scout's hand-back, the ask, the fixer's failure, the finishes: {kinds}",
                  kinds.count("spawn") == 2 and "handoff" in kinds and "ask" in kinds and "fail" in kinds and "finish" in kinds)
        ctx.check("in time order", [m["t"] for m in marks] == sorted(m["t"] for m in marks))
        ctx.check("a spawn names its parent and its task", any(m["kind"] == "spawn" and m["to"] == "main" and "find the bug" in m["text"] for m in marks))
        asks = [(round(m["t"] - T0), m["text"]) for m in marks if m["kind"] == "ask"]
        ctx.check(f"the permission card from the turn's record (its words, how it was answered) and the question, got {asks}",
                  asks[0] == (20, "Bash: rm -rf build (answered allow after 6 s)") and asks[1][0] == 70 and asks[1][1].startswith("may I push?"))
        main = [(round(x["t"] - T0), x["state"]) for x in h["states"] if x["agent_id"] == "main"]
        ctx.check(f"main waits on the owner from the card to the answer, and through the question, got {main}",
                  (20, "waiting") in main and (26, "running") in main and (70, "waiting") in main and (80, "running") in main)
        bands = timeline.bands(h)
        phases = {b["phase"] for b in bands}
        ctx.check(f"the bands carry the phase words, got {phases}", {"tool", "waiting", "thinking"} <= phases and phases <= set(timeline.PHASES))
        ctx.check("they tile the session without overlap", all(a["t1"] <= b["t0"] + 1e-6 for a, b in zip(bands, bands[1:])))
        ctx.check("each agent's own cost over time", {c["agent_id"] for c in h["agent_costs"]} == {"main", "scout1"})


@test
def test_round_trip_and_the_version_field(ctx: Ctx):
    from halo_harness.live import replay_file as RF
    with _home() as state:
        seed(state)
        p = RF.build(state, SID, lineup="none-such")
        path = RF.save(state, p)
        ctx.check(f"one file under <state>/replays/, got {path}", path.parent == state / "replays" and path.name.endswith(".halo-replay"))
        back = RF.load(path)
        ctx.check("format and version", back["format"] == "halo-replay" and back["version"] == RF.VERSION == 1)
        ctx.check("the same payload back", back == json.loads(json.dumps(p)))
        ctx.check("three agents, marks and bands", len(back["agents"]) == 3 and back["marks"] and back["bands"])
        rows = RF.saved(state)
        ctx.check("listed, newest first", [r["id"] for r in rows] == [p["id"]] and rows[0]["agents"] == 3)
        ctx.check("it says what it holds", any("not included" in line for line in back["includes"]))


@test
def test_a_seeded_key_never_reaches_the_file(ctx: Ctx):
    from halo_harness.live import replay_file as RF
    with _home() as state:
        seed(state)
        p = RF.build(state, SID)
        p["marks"].append({"t": T0 + 70, "kind": "ask", "agent_id": "main", "name": "main", "text": f"may I? {FAKE_KEY}"})
        from halo_harness.redact import sanitize_node
        path = RF.save(state, sanitize_node(p))
        raw = path.read_bytes().decode("utf-8")
        ctx.check("no key in the file", FAKE_KEY not in raw and FAKE_KEY[9:] not in raw and "zq" * 14 not in raw)
        ctx.check("where it stood, the redactor's mark", "<redacted>" in raw)
        ctx.check("no working directory or path", "secret-project" not in raw and '"cwd"' not in raw)
        built = json.dumps(RF.build(state, SID))
        ctx.check("build alone already redacts (title, task, hand-back)", FAKE_KEY not in built and "zq" * 14 not in built)


@test
def test_an_older_file_still_opens_and_a_newer_one_says_why_not(ctx: Ctx):
    from halo_harness.live import history
    from halo_harness.live import replay_file as RF
    with _home() as state:
        h = history.read(seed(state))
        old = {k: h[k] for k in ("session_id", "title", "started", "ended", "cost_usd", "agents", "states", "costs")}
        p = RF.parse(json.dumps({"harness": "you@studio", **old}))
        ctx.check("a 3.0.5.0 fleet/replay answer reads as version 1", p["version"] == 1 and p["upgraded_from"] == 0 and len(p["agents"]) == 3)
        ctx.check("and is redacted on the way in", FAKE_KEY not in json.dumps(p))
        for bad, want in (({"format": "halo-replay", "version": 99}, "version 99"), ({"x": 1}, "not a Halo replay"), ([], "not a JSON object")):
            try:
                RF.parse(json.dumps(bad))
                ctx.check(f"{bad} refused", False)
            except RF.ReplayError as e:
                ctx.check(f"{bad} refused with {want!r}: {e}", want in str(e))


@test
def test_the_clip_frames_size_and_cap(ctx: Ctx):
    from halo_harness.live import replay_clip as C
    p = {"started": T0, "ended": T0 + 600}
    a = C.plan(p, 0, 600, 16)
    ctx.check(f"600 s at 16x is 37.5 s: played faster to fit 30 s ({a['note']})", a["seconds"] <= C.MAX_SECONDS and a["speed"] == 20 and a["note"])
    ctx.check(f"5 frames a second, capped: {a['frames']}", a["frames"] == C.MAX_FRAMES == 151 and len(a["times"]) == 151)
    b = C.plan(p, 60, 120, 4)
    ctx.check(f"60 s at 4x: 15 s, 76 frames, got {b['frames']}", b["seconds"] == 15 and b["frames"] == 76 and b["times"][0] == 60 and b["times"][-1] == 120)
    try:
        import PIL  # noqa: F401
    except ImportError:
        ctx.check("Pillow absent: the clip says what it needs", "Pillow" in str(_err(lambda: C.fmt())))
        return
    from PIL import Image
    from halo_harness.live import replay_file as RF
    with _home() as state:
        seed(state)
        rid = RF.save(state, RF.build(state, SID)).name[:-len(RF.SUFFIX)]

        def frames(times):
            out = []
            for i, _t in enumerate(times):
                buf = io.BytesIO()
                im = Image.new("RGB", (1400, 840), (20, 40, 90))
                im.paste((240, 200, 40), (i * 40, 100, i * 40 + 120, 300))  # a box moving right, a frame each
                im.save(buf, "PNG")
                out.append(buf.getvalue())
            return out
        got = C.clip(state, rid, 0, 100, 16, frames=frames)
        with Image.open(got["path"]) as im:
            n, size = getattr(im, "n_frames", 1), im.size
        ctx.check(f"written under replays/clips, {got['format']}", Path(got["path"]).parent == state / "replays" / "clips")
        ctx.check(f"{C.WIDTH} px wide, {got['frames']} frames filmed and written: {n}, {size}",
                  size[0] == C.WIDTH and got["frames"] == 33 == n)
        ctx.check(f"under the size cap: {got['bytes']}", 0 < got["bytes"] < C.MAX_BYTES)


def _err(fn):
    try:
        fn()
    except Exception as e:
        return e
    return None


def _cli(argv: list) -> "tuple[int, str]":
    from halo_harness.replay_cli import cmd_replay
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        try:
            code = cmd_replay(argv)
        except SystemExit as e:
            code = e.code
    return int(code or 0), out.getvalue()


@test
def test_the_cli_verbs(ctx: Ctx):
    with _home() as state:
        seed(state)
        code, text = _cli(["list"])
        ctx.check(f"list with none says how to save one: {text!r}", code == 0 and "halo replay save" in text)
        code, text = _cli(["save", SID, "--dry-run"])
        ctx.check(f"save --dry-run says what it holds and where, writes nothing: {text!r}",
                  code == 0 and "holds:" in text and "Would write" in text and not (state / "replays").exists())
        code, text = _cli(["save", SID])
        files = list((state / "replays").glob("*.halo-replay"))
        ctx.check(f"save writes one file and says where: {text!r}", code == 0 and len(files) == 1 and str(files[0]) in text)
        code, text = _cli(["list", "--json"])
        ctx.check("list --json has it", code == 0 and json.loads(text)["replays"][0]["agents"] == 3)
        moved = state.parent / "elsewhere" / "theirs.halo-replay"
        moved.parent.mkdir(parents=True, exist_ok=True)
        data = json.loads(files[0].read_text(encoding="utf-8"))
        data["id"] = "theirs-1"
        moved.write_text(json.dumps(data), encoding="utf-8")
        code, text = _cli(["open", str(moved), "--no-studio"])
        ctx.check(f"open keeps a file from elsewhere under replays/: {text!r}", code == 0 and (state / "replays" / "theirs-1.halo-replay").is_file()
                  and "History" in text)
        code, text = _cli(["clip", "theirs-1", "--from", "0:10", "--to", "90", "--speed", "4", "--dry-run"])
        ctx.check(f"clip --dry-run says the frames, the width and the cap: {text!r}", code == 0 and "1200 px" in text and "from 10 s to 90 s" in text)
        code, text = _cli(["open", str(state / "nope.halo-replay"), "--no-studio"])
        ctx.check(f"a missing file: one line, exit 2: {text!r}", code == 2 and "no file" in text)
        code, text = _cli([SID])
        ctx.check("the 2.0.6 form still asks for --model", code == 2 and "--model" in text)


@test
def test_the_studio_routes(ctx: Ctx):
    from halo_harness.studio.replays_api import dispatch_replays
    with _home() as state:
        seed(state)
        server = SimpleNamespace(server_address=("127.0.0.1", 1), token="t", cwd=state, state_dir=state)

        def call(method, path, query=None, body=None):
            req = SimpleNamespace(method=method, path=path, query=query or {}, body=body, state_dir=state, cwd=state, server=server, params={})
            return dispatch_replays(req)
        code, plan = call("GET", "replays/plan", {"session": SID})
        ctx.check(f"plan says what Save holds, nothing written: {code}", code == 200 and plan["includes"] and not (state / "replays").exists())
        code, saved = call("POST", "replays/save", body={"session": SID})
        ctx.check("save writes it (the id carries the second it was saved)", code == 200 and Path(saved["path"]).is_file()
                  and saved["id"].startswith(SID + "-") and saved["includes"] == plan["includes"])
        code, one = call("GET", f"replays/{saved['id']}")
        ctx.check("the file's payload by id", code == 200 and one["format"] == "halo-replay")
        one["id"] = "imported-1"
        code, imp = call("POST", "replays/import", body={"text": json.dumps(one)})
        ctx.check("a file chosen in History is kept and listed", code == 200 and imp["id"] == "imported-1"
                  and len(call("GET", "replays")[1]["replays"]) == 2)
        code, bad = call("POST", "replays/import", body={"text": "{nope"})
        ctx.check(f"a bad file: 422 with why: {bad}", code == 422 and "not JSON" in bad["error"])
        code, clip = call("GET", f"replays/{saved['id']}/clip", {"from": "0", "to": "100", "speed": "16"})
        ctx.check(f"the clip's plan: frames, width, path: {code}", code == 200 and clip["frames"] == 33 and clip["width"] == 1200
                  and clip["path"].endswith((".webp", ".gif")))
        ctx.check("an unknown session is 404", call("POST", "replays/save", body={"session": "nope"})[0] == 404)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="replay file"))
