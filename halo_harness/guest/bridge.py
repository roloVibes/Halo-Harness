"""halo_harness.guest.bridge -- `halo guest serve`: the plugin's stdio MCP server, a CHILD of Claude Code (never of
Halo: Halo's own plugin reader skips this plugin, config/plugins.py). It offers the model no tools. While it runs:

* it opens a control socket and a registry row exactly as every Halo session does (`remote/runtime._open`;
  `kind: guest`, `parent: claude-code:<pid>`, title "Claude Code"), so Studio attaches it like any session;
* it writes `<guest dir>/<claude pid>.on` and an empty spool (0600) beside it; the plugin's hook appends to the
  spool only while the `.on` is there; every SPOOL_POLL_S it reads the new lines into its agent tree (feed.py) and
  rotates the spool past ROTATE_AT;
* it serves `ping, status, subscribe, agents, agent_tail, agent_follow` (and `unsubscribe`, which only ends a
  feed); every other command answers "watch only" (remote/protocol.py): nothing is ever sent into his session.

It ends when its input closes (Claude Code ends it at the session's end); its row, its `.on` and its spool go with
it. A bridge ended hard leaves files of a dead pid: the next bridge sweeps them at its start; the row of a dead pid
leaves the registry by itself (remote/registry.py). It starts no process. Nothing is kept after it.
"""

from __future__ import annotations

import json
import os
import signal
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

from halo_harness.guest import DESCRIPTION, KIND, PLUGIN, TITLE, WATCH_ONLY_LINE, guest_dir
from halo_harness.guest import note
from halo_harness.remote.base import HandleError, _BaseHandle

SPOOL_POLL_S = 0.25
ROTATE_AT = 1024 * 1024
READ_CHUNK = 1024 * 1024
PROTOCOL = "2025-06-18"


class _NoLog:
    """A guest keeps no session log (Claude Code keeps its own): nothing is read from or written to one."""
    path = None

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id

    def nodes(self) -> list:
        return []

    def append_meta(self, **_kw) -> None:
        return None


class GuestSession:
    """What the registry, the agent tree and the socket read of a session; nothing runs in it."""
    agent_id = None
    model_ref = None
    busy = False
    role_name = TITLE
    opt_ins = None
    team_control = None
    job_registry = None

    def __init__(self, session_id: str) -> None:
        self.log = _NoLog(session_id)
        self.permission_engine = SimpleNamespace(mode="")


class GuestHandle(_BaseHandle):
    """The socket's handle of a guest: reads only. Every way into a session raises WATCH_ONLY_LINE."""
    kind = KIND
    watch_only = True

    def __init__(self, session: GuestSession, project, claude_pid: int) -> None:
        super().__init__(session, project)
        self.claude_pid = claude_pid
        self.feed = None  # feed.GuestFeed, once the tree exists

    def title(self) -> str:
        return TITLE

    def status(self) -> dict:
        feed = self.feed
        busy = bool(feed and feed.busy())
        from halo_harness.agent.agent_registry import tree_for
        return {"session_id": self.session_id, "cwd": str(self.cwd), "title": TITLE, "busy": busy,
                "phase": "running" if busy else "idle", "model": feed.model if feed else None,
                "cost_usd": None, "total_input_tokens": None, "total_output_tokens": None, "permission_mode": "",
                "pending": {}, "remote_attached": 0, "agents": tree_for(self.session).live_count(),
                "accepts_turns": False, "watch_only": True,
                "guest": {"claude_pid": self.claude_pid, "claude_session_id": feed.sid if feed else "",
                          "dropped": feed.dropped if feed else 0}}

    def kept_entries(self, aid: str) -> list:
        """agent_tail's entries: the lines this bridge read, never a transcript file."""
        return self.feed.entries(aid) if self.feed else []

    def tail(self, n: int = 20) -> str:
        raise HandleError(WATCH_ONLY_LINE)

    def _refuse(self, *_a, **_kw):
        raise HandleError(WATCH_ONLY_LINE)

    submit = interrupt = set_mode = set_model = set_effort = run_slash = run_bang = _refuse
    answer_permission = answer_question = answer_plan = answer_approval = control_shutdown = _refuse

    def set_remote_peer(self, peer: str, attached: bool) -> int:
        return 0


class GuestBridge:
    def __init__(self, claude_pid: int, project, *, directory: Optional[Path] = None) -> None:
        self.claude_pid = int(claude_pid)
        self.project = Path(project)
        self.dir = Path(directory) if directory is not None else guest_dir()
        self.on, self.spool = (Path(p) for p in note.paths(self.dir, self.claude_pid))
        self.old: Optional[Path] = None  # the rotated spool, read to its end at the next poll, then removed
        self.old_offset = self.offset = 0
        self.act = None
        self.handle: Optional[GuestHandle] = None
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    # ---- start / end -----------------------------------------------------------------------------------------------
    def start(self) -> Optional["GuestBridge"]:
        """Sweep, open the row, then the `.on` (so a hook writes only once the row is there). None when sessions
        open no socket here (`control.enabled` false, private): then nothing is collected."""
        from halo_harness.remote import runtime
        from halo_harness.agent.agent_registry import tree_for
        from halo_harness.guest.feed import GuestFeed
        sweep(self.dir, also=self.claude_pid)
        if not runtime.enabled():
            return None
        sid = f"guest-{self.claude_pid}-{os.getpid()}"
        self.handle = GuestHandle(GuestSession(sid), self.project, self.claude_pid)
        self.handle.feed = GuestFeed(tree_for(self.handle.session), self.handle.hub, self.handle.session, self.project)
        from halo_harness.remote import session_identity as FI
        saved = os.environ.get(FI.PARENT_ENV)
        os.environ[FI.PARENT_ENV] = f"claude-code:{self.claude_pid}"
        try:
            self.act = runtime._open(self.handle, kind=KIND)  # noqa: SLF001  (the one way a session opens its door)
        finally:
            if saved is None:
                os.environ.pop(FI.PARENT_ENV, None)
            else:
                os.environ[FI.PARENT_ENV] = saved
        if self.act is None:
            return None
        _private_file(self.spool, b"")
        _private_file(self.on, json.dumps({"claude_pid": self.claude_pid, "bridge_pid": os.getpid(),
                                           "cwd": str(self.project), "session_id": self.act.session_id}).encode())
        self._thread = threading.Thread(target=self._loop, daemon=True, name="halo-guest-spool")
        self._thread.start()
        return self

    def close(self) -> None:
        """The `.on` first (no hook writes after it), then the row, then the spool. Idempotent."""
        self._stop.set()
        _unlink(self.on)
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(2.0)
        if self.act is not None:
            from halo_harness.remote import runtime
            runtime.stop_one(self.act)
            self.act = None
        for p in (self.spool, self.old):
            _unlink(p)

    # ---- the spool -------------------------------------------------------------------------------------------------
    def _loop(self) -> None:
        while not self._stop.wait(SPOOL_POLL_S):
            try:
                self.poll()
            except Exception:
                pass

    def poll(self) -> int:
        """Read the new lines into the tree (the rotated spool's rest first); rotate past ROTATE_AT. Lines read."""
        with self._lock:
            lines = []
            if self.old is not None:
                lines += _read_lines(self.old, self.old_offset)[0]
                _unlink(self.old)
                self.old = None
            got, self.offset = _read_lines(self.spool, self.offset)
            lines += got
            if self.offset >= ROTATE_AT:
                self._rotate()
        if lines and self.handle is not None and self.handle.feed is not None:
            self.handle.feed.take(lines)
        return len(lines)

    def _rotate(self) -> None:
        """The read spool moves aside (a hook holding it still lands its line there: read at the next poll) and an
        empty one takes its place. A rename the system refuses now is tried again at the next poll."""
        aside = self.spool.with_name(f"{self.claude_pid}.{time.time_ns()}.jsonl")
        try:
            os.replace(self.spool, aside)
        except OSError:
            return
        self.old, self.old_offset, self.offset = aside, self.offset, 0
        _private_file(self.spool, b"")


def _private_file(path: Path, data: bytes) -> None:
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_BINARY", 0), 0o600)
    try:
        if data:
            os.write(fd, data)
    finally:
        os.close(fd)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _unlink(path: Optional[Path]) -> None:
    if path is None:
        return
    try:
        os.unlink(path)
    except OSError:
        pass


def _read_lines(path: Path, offset: int) -> "tuple[list, int]":
    """The whole lines of `path` after `offset` (a line still being written waits), and the new offset."""
    try:
        with open(path, "rb") as f:
            f.seek(offset)
            raw = f.read(READ_CHUNK)
    except OSError:
        return [], offset
    end = raw.rfind(b"\n")
    if end < 0:
        return [], offset
    out = []
    for ln in raw[:end].split(b"\n"):
        try:
            out.append(json.loads(ln.decode("utf-8", "replace")))
        except ValueError:
            continue
    return out, offset + end + 1


def sweep(directory: Path, also: Optional[int] = None) -> int:
    """Remove the `.on` marks and spools of Claude Code processes that are gone (a bridge ended hard), and those of
    `also` (this bridge's own Claude Code: an earlier bridge of it ended hard). How many were removed."""
    from halo_harness.remote.registry import pid_alive
    removed = 0
    try:
        names = os.listdir(directory)
    except OSError:
        return 0
    for name in names:
        head = name.split(".", 1)[0]
        if not head.isdigit() or not (name.endswith(".on") or name.endswith(".jsonl")):
            continue
        if int(head) == also or not pid_alive(int(head)):
            _unlink(Path(directory) / name)
            removed += 1
    return removed


# ---- the MCP side: stdio, newline-delimited JSON-RPC; no tools, no instructions to the model ----------------------
def answer(msg) -> Optional[dict]:
    """The reply to one MCP message (None for a notification)."""
    if not isinstance(msg, dict) or "id" not in msg or not isinstance(msg.get("method"), str):
        return None
    method, rid = msg["method"], msg["id"]
    params = msg.get("params") if isinstance(msg.get("params"), dict) else {}
    if method == "initialize":
        from halo_harness import __version__
        version = params.get("protocolVersion") if isinstance(params.get("protocolVersion"), str) else PROTOCOL
        result = {"protocolVersion": version, "capabilities": {"tools": {"listChanged": False}},
                  "serverInfo": {"name": PLUGIN, "title": "Halo (watch only)", "version": __version__,
                                 "description": DESCRIPTION}}
    elif method == "tools/list":
        result = {"tools": []}
    elif method == "ping":
        result = {}
    elif method == "tools/call":
        return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32602, "message": WATCH_ONLY_LINE + " (no tools)"}}
    else:
        return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"method not found: {method}"}}
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def mcp_loop(rf, wf) -> None:
    """Answer until the input closes."""
    for raw in iter(rf.readline, b""):
        try:
            reply = answer(json.loads(raw.decode("utf-8", "replace")))
        except ValueError:
            continue
        if reply is not None:
            wf.write((json.dumps(reply) + "\n").encode("utf-8"))
            wf.flush()


def _project(argv: list) -> Path:
    """`--project <dir>` (the plugin passes Claude Code's project folder); else this process's folder."""
    if "--project" in argv:
        i = argv.index("--project")
        given = argv[i + 1] if i + 1 < len(argv) else ""
        if given and "${" not in given and os.path.isdir(given):
            return Path(given).resolve()
    return Path.cwd().resolve()


def serve(argv: Optional[list] = None) -> int:
    """`halo guest serve [--project <dir>]`: Claude Code's MCP child. Prints only MCP on its output."""
    argv = list(sys.argv[1:] if argv is None else argv)
    out = sys.stdout.buffer
    sys.stdout = sys.stderr  # nothing but the protocol on the output
    bridge = None
    try:
        bridge = GuestBridge(note.claude_pid(), _project(argv)).start()
    except Exception as e:
        print(f"halo guest: the bridge did not open ({type(e).__name__}: {e}); Studio will not show this session",
              file=sys.stderr)
    for sig in (getattr(signal, "SIGTERM", None), getattr(signal, "SIGHUP", None)):
        if sig is not None:
            try:
                signal.signal(sig, lambda *_a: sys.exit(0))
            except (ValueError, OSError):
                pass
    try:
        mcp_loop(sys.stdin.buffer, out)
    except (KeyboardInterrupt, SystemExit, OSError):
        pass
    finally:
        if bridge is not None:
            bridge.close()
    return 0
