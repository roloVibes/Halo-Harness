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
it. A bridge ended hard leaves files of a dead pid: the hook writes nothing to them (its `.on` names a bridge that is
not alive, note.bridge_alive), and they are swept (guest.sweep_dead) by `halo update` after its stops, `halo guest
status` and `uninstall`, `halo doctor`'s row, a Studio start and the next bridge's start; the row of a dead pid
leaves the registry by itself (remote/registry.py). It starts no process. Nothing is kept after it.

3.6.0.26 H, hand-outs (`guest.hand_out local`, read once at its start; docs/GUEST.md "Hand-outs"): it calls
closing.install() FIRST, offers five tools (guest/tools.py) and starts each hand-out's worker as its own child
(guest/hand_out.py); a worker's row in its tree is Halo's (`agent_stop` on it stops the job), every other row stays
watch only. With the setting off none of that is imported, installed or started.
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

from halo_harness.guest import DESCRIPTION, HAND_OUT_DESCRIPTION, KIND, PLUGIN, TITLE, WATCH_ONLY_LINE, guest_dir
from halo_harness.guest import note
from halo_harness.remote.base import HandleError, _BaseHandle

SPOOL_POLL_S = 0.25
ROTATE_AT = 1024 * 1024
READ_CHUNK = 1024 * 1024
SPOOL_YOUNG_S = 30.0  # a spool with no `.on` this young may be a starting bridge's (its `.on` comes next)
PROTOCOL = "2025-06-18"
REVISIONS = ("2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25")  # the MCP revisions this server implements


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
        self.hand_outs = None  # hand_out.HandOuts, when hand-outs are on

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
                          "dropped": feed.dropped if feed else 0, **_hand_out_status(self.hand_outs)}}

    def serve_own(self, cmd: str, req: dict):
        """3.6.0.26 H: the one command a guest serves past watch only: `agent_stop` on a hand-out worker's row (Halo's
        own: it stops that job). None for every other command and row (remote/protocol.py answers watch only)."""
        job = self.hand_outs.by_row(str(req.get("agent_id") or "")) if self.hand_outs is not None else None
        if cmd != "agent_stop" or job is None:
            return None
        via = " ".join(str(req.get("via") or "Studio").split())[:32] or "Studio"
        return {"agent_id": job.aid, "stopping": [job.aid], "said": job.stop(f"{via} (its Stop)")}

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
                                           "bridge_start": _start_mark(os.getpid()), "cwd": str(self.project),
                                           "session_id": self.act.session_id}).encode())
        self._thread = threading.Thread(target=self._loop, daemon=True, name="halo-guest-spool")
        self._thread.start()
        return self

    def close(self) -> None:
        """The `.on` first (no hook writes after it), then the spool (the session's words go first: Windows may end
        this process a moment after its input closes), then the row. Idempotent."""
        self._stop.set()
        _unlink(self.on)
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(2.0)
        for p in (self.spool, self.old):
            _unlink(p)
        if self.act is not None:
            from halo_harness.remote import runtime
            runtime.stop_one(self.act)
            self.act = None

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


def _start_mark(pid: int) -> Optional[str]:
    """The pid's start time where it is read with no process started (Windows, /proc), else None (macOS: `ps`)."""
    from halo_harness.bg_run import no_proc, process_start_time
    return None if no_proc() else process_start_time(pid)


def _bridge_runs(on: Path, claude: int) -> bool:
    """The bridge that wrote this `.on` still runs: its pid lives and began when the mark says (a pid the system gave
    to another program since is not it). A mark of an older build, with no bridge pid: its Claude Code's pid lives."""
    from halo_harness.remote.registry import pid_alive
    try:
        mark = json.loads(on.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        mark = None
    bridge = mark.get("bridge_pid") if isinstance(mark, dict) else None
    if not isinstance(bridge, int) or isinstance(bridge, bool):
        return pid_alive(claude)
    if not pid_alive(bridge):
        return False
    began, now = mark.get("bridge_start"), _start_mark(bridge)
    if not began or not now:
        return True
    from halo_harness.bg_run import start_matches
    return start_matches(bridge, began, now)


def sweep(directory: Path, also: Optional[int] = None) -> int:
    """Remove what a bridge that ended hard left: a `.on` whose BRIDGE is gone takes its spools with it, whatever its
    Claude Code's pid names now (Windows gives a pid to the next program at once); a spool with no `.on` stays only
    while it is a moment old (a bridge writes its spool, then its `.on`); and everything of `also` (this bridge's own
    Claude Code: an earlier bridge of it ended hard). How many were removed."""
    removed = 0
    try:
        names = os.listdir(directory)
    except OSError:
        return 0
    live = set()
    for name in names:
        head = name.split(".", 1)[0]
        if name.endswith(".on") and head.isdigit() and int(head) != also:
            if _bridge_runs(Path(directory) / name, int(head)):
                live.add(int(head))
    for name in names:
        head = name.split(".", 1)[0]
        if not head.isdigit() or not name.endswith((".on", ".jsonl", ".json", ".plans")) or int(head) in live:
            continue
        path = Path(directory) / name
        if int(head) != also and name.endswith(".jsonl") and f"{head}.on" not in names and _young(path):
            continue
        if name.endswith(".plans"):  # a hand-out's plan-mode folder (guest/hand_out.HandOuts.plans)
            import shutil
            shutil.rmtree(path, ignore_errors=True)
        else:
            _unlink(path)
        removed += 1
    return removed


def _young(path: Path) -> bool:
    try:
        return time.time() - os.stat(path).st_mtime < SPOOL_YOUNG_S
    except OSError:
        return False


# ---- the MCP side: stdio, newline-delimited JSON-RPC; no tools, no instructions to the model ----------------------
def _hand_out_status(jobs) -> dict:
    if jobs is None:
        return {}
    from halo_harness.guest.tools import status_of
    return status_of(jobs)


def revision(asked) -> str:
    """The client's revision when this server implements it; else the newest it implements (never an echo of one it
    does not know)."""
    return asked if asked in REVISIONS else REVISIONS[-1]


def answer(msg, hand_outs: bool = False) -> Optional[dict]:
    """The reply to one MCP message (None for a notification). `hand_outs`: the tools of guest/tools.py are on."""
    if not isinstance(msg, dict) or "id" not in msg or not isinstance(msg.get("method"), str):
        return None
    method, rid = msg["method"], msg["id"]
    params = msg.get("params") if isinstance(msg.get("params"), dict) else {}
    if method == "initialize":
        from halo_harness import __version__
        asked = params.get("protocolVersion")
        # off: release 1's echo, byte for byte; on: never an echo of a revision this server does not implement
        version = (revision(asked) if hand_outs else asked) if isinstance(asked, str) else PROTOCOL
        result = {"protocolVersion": version, "capabilities": {"tools": {"listChanged": False}},
                  "serverInfo": {"name": PLUGIN, "title": "Halo (watch only)", "version": __version__,
                                 "description": DESCRIPTION}}
        if hand_outs:
            from halo_harness.guest.tools import INSTRUCTIONS
            result["serverInfo"].update(title="Halo (watch, local hand-outs)", description=HAND_OUT_DESCRIPTION)
            result["instructions"] = INSTRUCTIONS
    elif method == "tools/list":
        if hand_outs:
            from halo_harness.guest.tools import tool_list
            result = {"tools": tool_list()}
        else:
            result = {"tools": []}
    elif method == "ping":
        result = {}
    elif method == "tools/call":
        return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32602, "message": WATCH_ONLY_LINE + " (no tools)"}}
    else:
        return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"method not found: {method}"}}
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def mcp_loop(rf, wf, tools=None) -> None:
    """Answer until the input closes. `tools` (guest/tools.Tools, hand-outs on): its loop, which keeps reading while
    a call runs."""
    if tools is not None:
        tools.loop(rf, wf)
        return
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
    from halo_harness.guest.hand_out import setting
    on = setting()[0] == "local"  # read once: a change takes a new session (or a reconnect of this server)
    if on:  # FIRST, before any thread that could start a process: the Job (Windows), the owner watch, the ledger owner
        from halo_harness import closing
        closing.install()
    bridge = tools = None
    claude, project = note.claude_pid(), _project(argv)
    try:
        bridge = GuestBridge(claude, project).start()
    except Exception as e:
        print(f"halo guest: the bridge did not open ({type(e).__name__}: {e}); Studio will not show this session",
              file=sys.stderr)
    if on:
        from halo_harness.guest.tools import Tools
        tools = Tools(bridge, project, claude_pid=claude, directory=guest_dir())
    for sig in (getattr(signal, "SIGTERM", None), getattr(signal, "SIGHUP", None)):
        if sig is not None:
            try:
                signal.signal(sig, lambda *_a: sys.exit(0))
            except (ValueError, OSError):
                pass
    try:
        mcp_loop(sys.stdin.buffer, out, tools)
    except (KeyboardInterrupt, SystemExit, OSError):
        pass
    finally:
        if tools is not None:
            tools.close()  # every job stopped (politely, then by closing's stop) and its file removed
        if bridge is not None:
            bridge.close()
    return 0
