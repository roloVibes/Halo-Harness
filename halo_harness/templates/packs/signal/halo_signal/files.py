"""halo_signal.files -- the pack's data folder (`~/.halo/packs/.data/signal/`, ext.data_dir) and its JSON files.

    home() -> Path                 the data folder, made on first use
    path(*parts) -> Path           a file in it
    read_json(path, default)       a mapping, or `default`
    edit_json(path, default)       a locked read / change / write (0600, atomic) -- a context manager yielding the dict
    write_text(path, text)         0600, atomic, inside the data folder (ext.write_private); OSError with its line
    migrate() -> [line]            the one-time move of what ~/.halo/remote/ held for Signal before 3.3.13.0

What lives here: signal.json (signal-cli's account settings), signal-cli/ (signal-cli's own data, `-d`), peers.json
(paired phones), invites.json (open pairing phrases), phones.json (each phone's session, home folder, notes),
pending.json (notices), audit.jsonl (one hashed line per command), health.json (the service's pulse), inbox/
(files a phone sent, for the session to read), link.json (a device link in progress).
"""

from __future__ import annotations

import json
import os
import shutil
import time
from contextlib import contextmanager
from pathlib import Path

from halo_harness.ext import data_dir, write_private

from halo_signal import PACK

LOCK_WAIT_S = 10.0
LOCK_STALE_S = 30.0
MARK = ".moved-from-remote"
MOVED = ("signal.json", "peers.json", "pending.json", "audit.jsonl", "audit.jsonl.1", "registration-pin",
         "register.json", "signal-cli")
DROPPED = ("bridge.json", "stop", "fleet-push")


def home() -> Path:
    d = data_dir(PACK)
    d.mkdir(parents=True, exist_ok=True)
    return d


def path(*parts: str) -> Path:
    return home().joinpath(*parts)


def read_json(p, default=None):
    try:
        data = json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {} if default is None else default
    return data if isinstance(data, dict) else ({} if default is None else default)


def write_text(p, text: str) -> None:
    lines = write_private(PACK, str(p), text)
    if lines:
        raise OSError(lines[0])


@contextmanager
def _lock(p: Path):
    lock = Path(str(p) + ".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    end = time.monotonic() + LOCK_WAIT_S
    fd = None
    while fd is None:
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > LOCK_STALE_S:
                    lock.unlink()
                    continue
            except OSError:
                continue
            if time.monotonic() > end:
                break  # a stuck lock never stops the bridge: the edit goes ahead without it
            time.sleep(0.02)
    try:
        yield
    finally:
        if fd is not None:
            os.close(fd)
            try:
                lock.unlink()
            except OSError:
                pass


@contextmanager
def edit_json(p, default: dict):
    p = Path(p)
    with _lock(p):
        data = read_json(p, json.loads(json.dumps(default)))
        yield data
        write_text(p, json.dumps(data, indent=2, sort_keys=True))


def old_remote() -> Path:
    """`~/.halo/remote/`: the state folder is three levels above the data folder (<state>/packs/.data/signal)."""
    return home().parents[2] / "remote"


def migrate() -> "list[str]":
    """Move the Signal files of a Halo before 3.3.13.0 into the data folder, once; one line when it did."""
    mark = path(MARK)
    if mark.exists():
        return []
    old = old_remote()
    found = [n for n in MOVED if (old / n).exists()] if old.is_dir() else []
    moved = []
    for name in found:
        dest = path(name)
        if dest.exists():
            continue
        try:
            shutil.move(str(old / name), str(dest))
            moved.append(name)
        except OSError:
            continue
    for name in DROPPED:
        target = old / name
        try:
            shutil.rmtree(target) if target.is_dir() else target.unlink()
        except OSError:
            pass
    if "signal.json" in moved:
        cfg = read_json(path("signal.json"))
        if str(cfg.get("data_dir") or "") in (str(old / "signal-cli"), ""):
            cfg["data_dir"] = ""  # the default: the data folder's signal-cli/
            write_text(path("signal.json"), json.dumps(cfg, indent=2, sort_keys=True))
    try:
        write_text(mark, json.dumps({"at": time.time(), "moved": moved}))
    except OSError:
        return []
    return [f"moved {', '.join(moved)} from {old} into the signal pack's data folder {home()} (once)"] if moved else []
