"""halo_harness.packs.policy_proc -- the long-lived process of one policy hook (Halo 3.3.10.0 R1;
docs/EXTENSION_API.md "Policy hooks").

The policy's `run` starts ONCE (a Windows spawn costs 100-300 ms, a session makes thousands of tool calls) and
speaks JSON lines: Halo writes one request per line on its stdin, it writes one answer per line on its stdout,
each answer carrying its request's `id`. A request waits for its answer up to the budget; an answer that comes
later is read and dropped when it arrives (its id is an earlier request's), so it never answers the next one.
The process ending, a write into a closed pipe, a line that is not a JSON object: each is the request's error,
said in one line, and the next request starts the process again. The write has the same budget (3.3.14.0 R2): a
process that stops reading its input is ended at the budget, said once, and the next request starts it again.

    p = PolicyProcess(argv, cwd=root, env=env)
    answer, why, ms = p.ask({"id": ..., "tool": ..., ...}, budget_s=2.0)   # (dict, '', ms) or (None, why, ms)
    p.stop()                                                               # EOF on stdin, then the process group
"""

from __future__ import annotations

import itertools
import json
import os
import queue
from halo_harness import subprocess_safe as subprocess
import threading
import time

TAIL = 2000  # bytes of the process's stderr kept for its error line
_ids = itertools.count(1)


class PolicyProcess:
    def __init__(self, argv, *, cwd, env, label: str = "", on_change=None):
        self.argv, self.cwd, self.env, self.label = [str(a) for a in argv], str(cwd), dict(env), label
        self.on_change = on_change  # 3.3.10.0 R2: on_change("start" | "stop", pid), the audit's process rows
        self.proc = None
        self.lines: "queue.Queue" = queue.Queue()
        self.err = b""
        self.lock = threading.Lock()
        self.started = 0  # how many times it was started (once, unless it ended)
        self.dropped = 0  # late answers read and dropped

    @property
    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    @property
    def pid(self):
        return self.proc.pid if self.proc is not None else None

    def start(self) -> str:
        """'' when it runs; else the one line saying why it does not."""
        if self.alive:
            return ""
        flags = 0
        if os.name == "nt":
            flags = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            self.proc = subprocess.Popen(self.argv, cwd=self.cwd, env=self.env, stdin=subprocess.PIPE,
                                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=flags,
                                         start_new_session=(os.name != "nt"))
        except (OSError, ValueError) as e:
            self.proc = None
            return f"it did not start: {e}"
        self.started += 1
        self._tell("start", self.proc.pid)
        self.lines = queue.Queue()
        self.err = b""
        proc, lines = self.proc, self.lines
        threading.Thread(target=self._read, args=(proc, lines), daemon=True, name=f"policy-out-{self.label}").start()
        threading.Thread(target=self._drain, args=(proc,), daemon=True, name=f"policy-err-{self.label}").start()
        return ""

    def _tell(self, change: str, pid) -> None:
        if self.on_change is not None:
            try:
                self.on_change(change, pid)
            except Exception:  # the audit row never stops a verdict
                pass

    def _read(self, proc, lines) -> None:
        try:
            for raw in proc.stdout:
                lines.put(raw.decode("utf-8", "replace").strip())
        except (OSError, ValueError):
            pass
        lines.put(None)  # the process closed its stdout: it ended

    def _drain(self, proc) -> None:
        try:
            for raw in proc.stderr:
                self.err = (self.err + raw)[-TAIL:]
        except (OSError, ValueError):
            pass

    def _ended(self) -> str:
        code = None
        if self.proc is not None:
            try:
                code = self.proc.wait(timeout=1.0)  # its stdout closed: it is exiting, the code comes at once
            except subprocess.TimeoutExpired:
                code = None
        tail = self.err.decode("utf-8", "replace").strip().splitlines()[-1:] if self.err else []
        return "the process ended" + (f" (exit {code})" if code is not None else "") + (f": {tail[0][:200]}" if tail else "")

    def ask(self, request: dict, budget_s: float) -> "tuple[dict | None, str, int]":
        """One request and its answer within `budget_s`: `(answer, '', ms)`, or `(None, why, ms)`."""
        with self.lock:
            t0 = time.monotonic()
            why = self.start()
            if why:
                return None, why, _ms(t0)
            rid = str(request.get("id") or f"r{next(_ids)}")
            line = json.dumps({**request, "id": rid}, ensure_ascii=False) + "\n"
            # 3.3.14.0 R2 (REVIEW #12, PERMS-6): the write has the budget too; a policy that stops reading its input
            # (a big Write's request fills the pipe) is ended at the budget and the next call starts it again
            done, failed = threading.Event(), []
            threading.Thread(target=_write, args=(self.proc, line.encode("utf-8"), done, failed), daemon=True,
                             name=f"policy-in-{self.label}").start()
            if not done.wait(max(0.0, float(budget_s))):
                self._kill()
                return None, (f"policy did not answer in {float(budget_s):g}s (it stopped reading its input; the "
                              "next call starts it again)"), _ms(t0)
            if failed:
                return None, self._ended(), _ms(t0)
            deadline = t0 + max(0.0, float(budget_s))
            while True:
                left = deadline - time.monotonic()
                if left <= 0:
                    return None, f"no answer within {int(budget_s * 1000)} ms", _ms(t0)
                try:
                    got = self.lines.get(timeout=left)
                except queue.Empty:
                    continue
                if got is None:
                    self.lines.put(None)  # stays ended for the next look
                    return None, self._ended(), _ms(t0)
                if not got:
                    continue
                try:
                    answer = json.loads(got)
                except ValueError:
                    return None, f"a malformed answer (not JSON): {got[:120]}", _ms(t0)
                if not isinstance(answer, dict):
                    return None, f"a malformed answer (not a JSON object): {got[:120]}", _ms(t0)
                if str(answer.get("id")) != rid:
                    self.dropped += 1  # a late answer to an earlier request
                    continue
                return answer, "", _ms(t0)

    def _kill(self) -> None:
        """Out of step with its input: the process group ends now (no EOF wait), its pipes are closed."""
        proc, self.proc = self.proc, None
        if proc is None:
            return
        self._tell("stop", proc.pid)
        from halo_harness.tools._proc import _kill_process_group
        _kill_process_group(proc)
        try:
            proc.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            pass
        for stream in (proc.stdin, proc.stdout, proc.stderr):
            try:
                stream.close()
            except (OSError, ValueError, AttributeError):
                pass

    def stop(self) -> None:
        proc, self.proc = self.proc, None
        if proc is None:
            return
        self._tell("stop", proc.pid)
        try:
            proc.stdin.close()  # EOF: a well-behaved policy ends on its own
        except (OSError, ValueError):
            pass
        try:
            proc.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            from halo_harness.tools._proc import _kill_process_group
            _kill_process_group(proc)
            try:
                proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                pass
        for stream in (proc.stdout, proc.stderr):
            try:
                stream.close()
            except (OSError, ValueError, AttributeError):
                pass


def _write(proc, data: bytes, done, failed: list) -> None:
    try:
        proc.stdin.write(data)
        proc.stdin.flush()
    except (OSError, ValueError, AttributeError) as e:
        failed.append(e)
    done.set()


def _ms(t0: float) -> int:
    return int(round((time.monotonic() - t0) * 1000))
