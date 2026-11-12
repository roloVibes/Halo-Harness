"""halo_harness.replay_verbs -- `halo replay list | save | open | clip` (Halo 3.4.1.0 R1 "Time"): the replay file
(live/replay_file.py) and its clip (live/replay_clip.py) from the terminal. docs/REPLAY.md.

    halo replay list [--json]                          the saved replays under <state>/replays/, newest first
    halo replay save <session> [--lineup NAME] [--dry-run] [--json]
                                                       says what the file holds and where it goes, then writes it
    halo replay open <file> [--no-studio] [--json]     checks the file, keeps it under <state>/replays/ (History lists
                                                       it) and opens Studio's Agents -> Live on it
    halo replay clip <file|id> [--from T] [--to T] [--speed N] [--dry-run] [--json]
                                                       films the range on Live and writes one WebP (else GIF), 1200 px
                                                       wide, at most 30 s; T is seconds or m:ss since the start
    halo replay compare <a> <b> [--split T] [--json]   3.4.1.0 R2: two runs side by side (live/compare.py), nothing
                                                       written; a, b: a session id, a goal run id or a .halo-replay
                                                       (path or saved id); the same one twice splits it at T

3.4.1.0 R2: `save` takes a goal run id of the repo you are in too (live/replay_run.py).

`halo replay <session-id> --model <ref>` (2.0.6 R4, replay_cli.py) is unchanged.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

VERBS = ("list", "save", "open", "clip", "compare")


def _state():
    from halo_harness.config.paths import bridge_home
    return bridge_home()


def _secs(v: Optional[str]) -> Optional[float]:
    if v in (None, ""):
        return None
    parts = str(v).split(":")
    try:
        return float(sum(float(p) * 60 ** i for i, p in enumerate(reversed(parts))))
    except ValueError:
        raise SystemExit(f"halo replay: not a time: {v!r} (seconds, or m:ss)") from None


def _span(r: dict) -> str:
    s = r.get("secs")
    return "?" if s is None else f"{int(s // 60)} min {int(s % 60):02d} s" if s >= 60 else f"{s:.0f} s"


def _list(args) -> int:
    from halo_harness.live import replay_file
    rows = replay_file.saved(_state())
    if args.json:
        print(json.dumps({"dir": str(replay_file.replays_dir(_state())), "replays": rows}, indent=2))
        return 0
    if not rows:
        print(f"No saved replays in {replay_file.replays_dir(_state())}. Save one: halo replay save <session>")
        return 0
    for r in rows:
        cost = f"${r['cost_usd']:.2f}" if isinstance(r.get("cost_usd"), (int, float)) else "$?"
        print(f"{r['id']}  {r['agents']} agents  {_span(r)}  {cost}  {r['title'] or '(untitled)'}")
    return 0


def _save(args) -> int:
    from halo_harness.live import history, replay_file, replay_run
    try:
        run_dir = None if history.find(_state(), args.session) else replay_run.find(Path.cwd(), args.session)
        p = (replay_run.build_run(_state(), run_dir) if run_dir is not None
             else replay_file.build(_state(), args.session, lineup=args.lineup, cwd=Path.cwd()))
    except replay_file.ReplayError as e:
        print(f"halo replay save: {e}", file=sys.stderr)
        return 2
    path = replay_file.replays_dir(_state()) / f"{p['id']}{replay_file.SUFFIX}"
    if not args.json:
        print(f"The replay of {p.get('run_id') or p['session_id']} holds:")
        for line in p["includes"]:
            print(f"  - {line}")
        print(("Would write " if args.dry_run else "Writing ") + str(path))
    if args.dry_run:
        return 0
    path = replay_file.save(_state(), p)
    if args.json:
        print(json.dumps({"ok": True, "id": p["id"], "path": str(path), "bytes": path.stat().st_size, "includes": p["includes"]}, indent=2))
    else:
        print(f"Wrote {path} ({path.stat().st_size} bytes). Open it anywhere: halo replay open {path.name}")
    return 0


def _take(arg: str) -> "tuple[dict, Path]":
    """A file path or a saved id -> (payload, its path under <state>/replays/); a file elsewhere is copied there."""
    from halo_harness.live import replay_file
    known = replay_file.path_for(_state(), arg)
    if known is not None:
        return replay_file.load(known), known
    src = Path(arg).expanduser()
    if not src.is_file():
        raise replay_file.ReplayError(f"no file {arg!r} and no saved replay of that id")
    p = replay_file.load(src)
    dest = replay_file.replays_dir(_state()) / f"{p['id']}{replay_file.SUFFIX}"
    if src.resolve() != dest.resolve():
        dest = replay_file.save(_state(), p)
    return p, dest


def _open(args) -> int:
    from halo_harness.live import replay_file
    try:
        p, path = _take(args.file)
    except replay_file.ReplayError as e:
        print(f"halo replay open: {e}", file=sys.stderr)
        return 2
    row = replay_file.row(p, path)
    url = ""
    if not args.no_studio:
        from halo_harness.studio.launch import launch_detached
        url = launch_detached("agents", cwd=Path.cwd(), state_dir=_state())
        if url:
            head, _, frag = url.partition("#")
            url = f"{head}{'&' if '?' in head else '?'}view=live&replay={p['id']}" + (f"#{frag}" if frag else "")
            from halo_harness.studio.launch import _open as browse
            browse(url)
    if args.json:
        print(json.dumps({"ok": True, **row, "url": url, "includes": p.get("includes") or []}, indent=2))
        return 0
    print(f"{p['id']}: {row['title'] or '(untitled)'} -- {row['agents']} agents, {row['marks']} marks, {_span(row)}"
          + (" (an older file, read as version 1)" if p.get("upgraded_from") is not None else ""))
    print(f"Kept at {path}; History on Agents -> Live lists it.")
    print(f"Studio: {url}" if url else "Open it in Studio: halo studio, then Agents -> Live -> History.")
    return 0


def _clip(args) -> int:
    from halo_harness.live import replay_clip, replay_file
    try:
        p, path = _take(args.file)
        plan = replay_clip.plan(p, _secs(args.from_), _secs(args.to), args.speed)
        kind = replay_clip.fmt()
    except (replay_file.ReplayError, replay_clip.ClipError) as e:
        print(f"halo replay clip: {e}", file=sys.stderr)
        return 2
    if not args.json:
        print(f"Films {p['id']} from {plan['from']:.0f} s to {plan['to']:.0f} s at {plan['speed']:g}x: {plan['frames']} frames, "
              f"{plan['seconds']} s, {replay_clip.WIDTH} px wide, {kind.upper()} (at most {replay_clip.MAX_SECONDS} s)."
              + (f" Note: {plan['note']}." if plan["note"] else ""))
    if args.dry_run:
        return 0
    try:
        got = replay_clip.clip(_state(), p["id"], plan["from"], plan["to"], plan["speed"], cwd=Path.cwd())
    except (replay_clip.ClipError, TimeoutError, RuntimeError) as e:
        print(f"halo replay clip: {e}", file=sys.stderr)
        return 2
    print(json.dumps(got, indent=2) if args.json else f"Wrote {got['path']} ({got['bytes']} bytes, {got['frames']} frames).")
    return 0


def _compare(args) -> int:
    from halo_harness.live import compare
    try:
        pa = compare.resolve(_state(), args.a, cwd=Path.cwd())
        pb = pa if args.b == args.a else compare.resolve(_state(), args.b, cwd=Path.cwd())
    except compare.CompareError as e:
        print(f"halo replay compare: {e}", file=sys.stderr)
        return 2
    got = compare.compare(pa, pb, split=_secs(args.split), same=args.a == args.b)
    if args.json:
        print(json.dumps(got, indent=2))
        return 0
    a, b = got["a"], got["b"]
    for side in (a, b):
        print(f"{side['label']}: {side['kind']} {side['id']} -- {side['title'] or '(untitled)'}")
    width = max(len(r["label"]) for r in got["rows"])
    for r in got["rows"]:
        mark = {"a": f"A {r['word']}", "b": f"B {r['word']}", "same": "same"}.get(r["better"] or "", r["word"] or "")
        print(f"  {r['label']:<{width}}  A {r['a']['text']}  |  B {r['b']['text']}" + (f"  [{mark}]" if mark else ""))
    print("What differed:")
    for line in got["differed"]:
        print(f"  - {line}")
    return 0


def cmd_verbs(argv: list) -> int:
    ap = argparse.ArgumentParser(prog="halo replay", description="A run's replay as one file: list, save, open, clip.")
    sub = ap.add_subparsers(dest="verb", required=True)
    s = sub.add_parser("list", help="the saved replays, newest first")
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("save", help="save a session's or a goal run's replay as one file under <state>/replays/")
    s.add_argument("session")
    s.add_argument("--lineup", default=None, help="the lineup whose blocks go in (default: the one in use)")
    s.add_argument("--dry-run", action="store_true", help="say what it would hold and where, write nothing")
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("open", help="open a replay file on Agents -> Live")
    s.add_argument("file")
    s.add_argument("--no-studio", action="store_true", help="check and keep it; do not open Studio")
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("clip", help="film a range to one animated file")
    s.add_argument("file")
    s.add_argument("--from", dest="from_", default=None)
    s.add_argument("--to", default=None)
    s.add_argument("--speed", type=float, default=None)
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("compare", help="two runs side by side: a session, a goal run or a .halo-replay each")
    s.add_argument("a")
    s.add_argument("b")
    s.add_argument("--split", default=None, help="the same run twice: split it here (seconds or m:ss; default its first steer, else halfway)")
    s.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    return {"list": _list, "save": _save, "open": _open, "clip": _clip, "compare": _compare}[args.verb](args)
