"""halo_harness.packs.journal -- every file a pack operation writes or
removes, one row each, in `<state>/packs/journal.jsonl` (Halo 3.2.0.0 R1;
the row shape of orchestra/coach_record.py, with content hashes):

    {"ts": 1760800000.0, "op": "install" | "update" | "remove" | "rollback", "op_id": "install-<8 hex>",
     "pack": "<id>", "path": "<absolute path>", "existed": false, "before": null | "<sha256>",
     "after": null | "<sha256>"}

3.2.0.0 R7 adds rows with no `path` (`owned` skips them): an update's start
`{op: "update", op_id, pack, mark: "start", from, to}`, a settings rename
`{op: "migrate" | "unmigrate", op_id, pack, setting, to, value}` (packs/migrate.py),
and a swap `{op: "update" | "rollback", op_id, pack, swap: "<id>.previous", ...}`.

`owned(pack_id)` reads the journal back: the files the pack's operations
wrote and the hash each one was left with. A file there that still holds
that hash is the pack's own; one that differs is yours (you edited it), and
a file the journal never wrote is yours too -- an update or a remove leaves
both where they are. `Op` is one operation: `write` / `delete` keep a backup
of what they replace (`<state>/packs/.backup/<op_id>/`), `rollback()` puts
every file back when a later step fails, `commit()` drops the backup.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from typing import Optional

FILE = "journal.jsonl"


def journal_path(state_dir=None) -> Path:
    from halo_harness.packs.state import packs_home
    return packs_home(state_dir) / FILE


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path) -> Optional[str]:
    try:
        return sha_bytes(Path(path).read_bytes())
    except OSError:
        return None


def rows(state_dir=None, *, pack: Optional[str] = None) -> "list[dict]":
    try:
        lines = journal_path(state_dir).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and (pack is None or row.get("pack") == pack):
            out.append(row)
    return out


def norm(path) -> str:
    """One spelling per file (resolved, case-folded where the filesystem is): the key `owned` uses."""
    try:
        return os.path.normcase(str(Path(path).resolve()))
    except (OSError, ValueError):
        return os.path.normcase(str(path))


def owned(pack_id: str, state_dir=None, *, before_op: Optional[str] = None) -> "dict[str, str]":
    """`{norm(path): the hash the pack's last operation left it with}` (removed files are not listed);
    `before_op` (3.2.0.0 R7, rollback): as it was before the first row of that operation."""
    out: "dict[str, str]" = {}
    for row in rows(state_dir, pack=pack_id):
        if before_op is not None and row.get("op_id") == before_op:
            break
        path = row.get("path")
        if not isinstance(path, str):
            continue
        if row.get("after"):
            out[norm(path)] = row["after"]
        else:
            out.pop(norm(path), None)
    return out


def _append(row: dict, state_dir=None) -> None:
    path = journal_path(state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(row, sort_keys=False) + "\n")


def _write_bytes(path: Path, data: bytes, mode: Optional[int] = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        if mode is not None:
            os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


class Op:
    """One install / update / remove: its rows, its backups, its rollback."""

    def __init__(self, op: str, pack_id: str, *, state_dir=None):
        from halo_harness.packs.state import packs_home
        self.op, self.pack, self.state_dir = op, pack_id, state_dir
        self.op_id = f"{op}-{uuid.uuid4().hex[:8]}"
        self.backup = packs_home(state_dir) / ".backup" / self.op_id
        self.done: "list[dict]" = []

    def _row(self, path: Path, existed: bool, before, after, op: Optional[str] = None) -> dict:
        row = {"ts": round(time.time(), 3), "op": op or self.op, "op_id": self.op_id, "pack": self.pack,
               "path": str(path), "existed": existed, "before": before, "after": after}
        _append(row, self.state_dir)
        return row

    def _keep(self, path: Path) -> None:
        dest = self.backup / f"{len(self.done)}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)

    def write(self, path, data: bytes, *, mode: Optional[int] = None) -> None:
        path = Path(path)
        before = sha(path)
        if before is not None:
            self._keep(path)
        _write_bytes(path, data, mode)
        self.done.append(self._row(path, before is not None, before, sha_bytes(data)))

    def delete(self, path) -> None:
        path = Path(path)
        before = sha(path)
        if before is None:
            return
        self._keep(path)
        path.unlink()
        self.done.append(self._row(path, True, before, None))

    def rollback(self) -> "list[str]":
        """Every file of this operation back as it was, newest first; one line per file it could not restore."""
        problems = []
        for i in range(len(self.done) - 1, -1, -1):
            row = self.done[i]
            path, kept = Path(row["path"]), self.backup / f"{i}"
            try:
                if sha(path) != row["after"]:
                    problems.append(f"{path}: changed since this {self.op} wrote it; left as it is")
                    continue
                if row["before"] is None:
                    path.unlink(missing_ok=True)
                else:
                    _write_bytes(path, kept.read_bytes())
                self._row(path, row["after"] is not None, row["after"], row["before"], op="rollback")
            except OSError as e:
                problems.append(f"{path}: {e}")
        self.done = []
        self.commit()
        return problems

    def commit(self) -> None:
        shutil.rmtree(self.backup, ignore_errors=True)
        try:
            self.backup.parent.rmdir()  # `.backup` itself, once no operation keeps one
        except OSError:
            pass


def prune_empty_dirs(root, *, keep_root: bool = False) -> None:
    """Remove the empty folders under `root` (and `root` itself when it ends up empty, unless `keep_root`)."""
    root = Path(root)
    if not root.is_dir():
        return
    for d in sorted((p for p in root.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
        try:
            d.rmdir()
        except OSError:
            pass
    if keep_root:
        return
    try:
        root.rmdir()
    except OSError:
        pass
