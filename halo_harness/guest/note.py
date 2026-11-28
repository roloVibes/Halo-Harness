"""The plugin's one hook (halo_harness/guest): Claude Code runs it, as an async exec-form command hook, for every
event the plugin's hooks file names, with the event's JSON on its input. It appends ONE line to the spool of the
bridge of its own Claude Code process and ends. It imports only the standard library (it runs as `python -I`, from
the plugin folder, a copy of this file), never prints, always exits 0, and ends within DEADLINE_S whatever happens.

* Which spool: `<guest dir>/<claude pid>.jsonl`, `<claude pid>` being this process's parent (a Windows Python
  launcher between them is stepped over: `claude_pid`); the bridge finds the same number from its own parent.
  No `<claude pid>.on` (no bridge up), an `.on` whose bridge is not alive (its pid and start mark: a bridge ended
  hard), or no spool: nothing is written, so a dead bridge's spool never grows.
* What is kept: the documented fields named in KEEP, cut (a tool's input one line of INPUT_MAX characters, a
  TodoWrite list as its steps, an Agent call as its description, type and the first line of its prompt; a tool's
  response or error RESPONSE_MAX bytes; a prompt its first PROMPT_MAX characters; a whole line LINE_MAX bytes).
  Nothing else of the input is kept: not the transcript's path, not anything of the login.
* The spool never passes SPOOL_MAX: a line that would cross it is not written (the bridge rotates the spool).
"""

import json
import os
import sys
import threading
import time

DEADLINE_S = 0.9
INPUT_MAX = 300
RESPONSE_MAX = 2048
PROMPT_MAX = 200
LINE_MAX = 8192
SPOOL_MAX = 4 * 1024 * 1024
READ_MAX = 64 * 1024 * 1024
TODO_MAX = 30  # agent_observe.PLAN_MAX: the steps a row keeps of one list
TODO_TEXT = 160  # agent_observe.PLAN_TEXT
AGENT_TOOLS = ("Agent", "Task")
STEP_OVER = ("python", "pythonw", "cmd")  # Windows: a launcher between Claude Code and this process
EVENTS = ("SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "PostToolUseFailure", "SubagentStart",
          "SubagentStop", "TaskCreated", "TaskCompleted", "Notification", "Stop", "StopFailure", "PreCompact",
          "SessionEnd")
COMMON = ("session_id", "cwd", "agent_id", "agent_type")
# per event: (field, how it is cut); "tool" = the tool input's cut, "text" = RESPONSE_MAX bytes, "short" = 200 chars
KEEP = {
    "SessionStart": (("source", "word"), ("model", "word"), ("session_title", "short")),
    "UserPromptSubmit": (("prompt", "prompt"),),
    "PreToolUse": (("tool_name", "word"), ("tool_use_id", "word"), ("tool_input", "tool")),
    "PostToolUse": (("tool_name", "word"), ("tool_use_id", "word"), ("tool_input", "tool"),
                    ("tool_response", "text"), ("duration_ms", "number")),
    "PostToolUseFailure": (("tool_name", "word"), ("tool_use_id", "word"), ("tool_input", "tool"), ("error", "text"),
                           ("is_interrupt", "flag"), ("duration_ms", "number")),
    "SubagentStart": (),
    "SubagentStop": (("last_assistant_message", "text"),),
    "TaskCreated": (("task_id", "word"), ("task_subject", "short"), ("task_description", "short")),
    "TaskCompleted": (("task_id", "word"), ("task_subject", "short")),
    "Notification": (("message", "short"), ("notification_type", "word"), ("title", "short")),
    "Stop": (("last_assistant_message", "text"),),
    "StopFailure": (("error", "word"), ("error_details", "short"), ("last_assistant_message", "text")),
    "PreCompact": (("trigger", "word"),),
    "SessionEnd": (("reason", "word"),),
}


def one_line(value, cap):
    """`value` as one line of at most `cap` characters (a dict or list as its JSON)."""
    if value is None:
        return ""
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    text = " ".join(text.split())
    return text if len(text) <= cap else text[:max(0, cap - 1)] + "…"


def first_line(value, cap):
    text = value if isinstance(value, str) else ""
    for ln in text.splitlines():
        if ln.strip():
            return one_line(ln, cap)
    return ""


def cut_bytes(value, cap):
    """`value` as text of at most `cap` UTF-8 bytes (a dict or list as its JSON)."""
    if value is None:
        return ""
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    raw = text.encode("utf-8", "replace")
    return text if len(raw) <= cap else raw[:cap].decode("utf-8", "ignore")


def cut_todos(todos):
    """TodoWrite's list as the row will keep it: the first TODO_MAX steps (past it, the first TODO_MAX - 1 and the
    one in progress), each with its number `n` in the whole list, and the whole list's counts {all, done}."""
    steps = []
    for t in todos if isinstance(todos, list) else []:
        if isinstance(t, dict) and isinstance(t.get("content"), str):
            status = t.get("status") if t.get("status") in ("pending", "in_progress", "completed") else "pending"
            steps.append({"content": one_line(t["content"], TODO_TEXT), "status": status,
                          "activeForm": one_line(t.get("activeForm") or "", TODO_TEXT), "n": len(steps) + 1})
    kept = steps[:TODO_MAX]
    now = next((s for s in steps if s["status"] == "in_progress"), None)
    if now is not None and now["n"] > TODO_MAX:
        kept = steps[:TODO_MAX - 1] + [now]
    return kept, {"all": len(steps), "done": sum(s["status"] == "completed" for s in steps)}


def cut_input(name, given):
    """A tool's input, cut: a dict whose JSON is one line of at most INPUT_MAX characters; a TodoWrite list as its
    steps (cut_todos); an Agent call as its description, type and the first line of its prompt."""
    if not isinstance(given, dict):
        return {"input": one_line(given, INPUT_MAX - 20)} if given not in (None, "") else {}
    if name == "TodoWrite":
        todos, count = cut_todos(given.get("todos"))
        return {"todos": todos, "todo_count": count}
    if name in AGENT_TOOLS:
        out = {"description": one_line(given.get("description"), 120), "subagent_type": one_line(given.get("subagent_type"), 60),
               "prompt": first_line(given.get("prompt"), 100)}
        return {k: v for k, v in out.items() if v}
    out = {}
    for key, value in given.items():
        if value is None or isinstance(value, bool):
            continue
        out[one_line(str(key), 40)] = one_line(value, INPUT_MAX)
    for _ in range(64):  # the longest value gives back what is over, until the whole fits
        over = len(json.dumps(out)) - INPUT_MAX  # measured as plain ASCII JSON: the strictest count
        if over <= 0 or not out:
            break
        key = max(out, key=lambda k: len(out[k]))
        if len(out[key]) <= over + 8:
            out.pop(key)
        else:
            out[key] = out[key][:len(out[key]) - over - 2] + "…"
    return out


def _cut(how, value):
    if how == "word":
        return one_line(value, 120) if isinstance(value, str) else None
    if how == "short":
        return one_line(value, 200) if isinstance(value, str) else None
    if how == "prompt":
        return value[:PROMPT_MAX] if isinstance(value, str) else None
    if how == "text":
        return cut_bytes(value, RESPONSE_MAX) if value is not None else None
    if how == "number":
        return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None
    if how == "flag":
        return value if isinstance(value, bool) else None
    return None


def line_of(payload, ts=None):
    """The spool line for one hook input (bytes ending in a newline), or None for an input that is not one."""
    if not isinstance(payload, dict) or payload.get("hook_event_name") not in KEEP:
        return None
    event = payload["hook_event_name"]
    out = {"ts": int(ts if ts is not None else time.time_ns()), "hook_event_name": event}
    for key in COMMON:
        if isinstance(payload.get(key), str) and payload[key]:
            out[key] = one_line(payload[key], 4096 if key == "cwd" else 120)
    for key, how in KEEP[event]:
        if how == "tool":
            value = cut_input(payload.get("tool_name"), payload.get(key))
        else:
            value = _cut(how, payload.get(key))
        if value not in (None, "", {}):
            out[key] = value
    for _ in range(4):  # a line over LINE_MAX gives back its long texts first
        raw = (json.dumps(out, ensure_ascii=False) + "\n").encode("utf-8")
        if len(raw) <= LINE_MAX:
            return raw
        for key in ("tool_response", "error", "last_assistant_message"):
            if isinstance(out.get(key), str) and len(out[key]) > 256:
                out[key] = cut_bytes(out[key], 256)
                break
        else:
            todos = (out.get("tool_input") or {}).get("todos")
            if isinstance(todos, list) and len(todos) > 5:
                out["tool_input"]["todos"] = todos[:5]
            else:
                return None
    return None


def _is_launcher(exe):
    base = os.path.basename(str(exe or "")).lower()
    base = base[:-4] if base.endswith(".exe") else base
    return base in STEP_OVER or (base.startswith("python") and base[6:].replace(".", "").isdigit())


def _win_table():
    """{pid: (parent pid, exe name)} of every process (Windows, ToolHelp), {} on any failure."""
    import ctypes
    from ctypes import wintypes

    class Entry(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                    ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD),
                    ("cntThreads", wintypes.DWORD), ("th32ParentProcessID", wintypes.DWORD),
                    ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD), ("szExeFile", ctypes.c_wchar * 260)]
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    k32.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
    k32.Process32FirstW.argtypes = k32.Process32NextW.argtypes = (wintypes.HANDLE, ctypes.POINTER(Entry))
    k32.CloseHandle.argtypes = (wintypes.HANDLE,)
    snap = k32.CreateToolhelp32Snapshot(0x2, 0)
    if not snap or snap == wintypes.HANDLE(-1).value:
        return {}
    table = {}
    try:
        entry = Entry()
        entry.dwSize = ctypes.sizeof(Entry)
        ok = k32.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            table[int(entry.th32ProcessID)] = (int(entry.th32ParentProcessID), entry.szExeFile)
            ok = k32.Process32NextW(snap, ctypes.byref(entry))
    finally:
        k32.CloseHandle(snap)
    return table


def claude_pid(ppid=None, table=None):
    """The pid of the Claude Code process that started this one: the parent, past at most two Windows launchers
    (a virtualenv's python.exe starts the real interpreter as its child). On macOS and Linux: the parent."""
    pid = os.getppid() if ppid is None else int(ppid)
    if table is None:
        if os.name != "nt":
            return pid
        table = _win_table()
    for _ in range(2):
        row = table.get(pid)
        if not row or not _is_launcher(row[1]):
            break
        pid = row[0]
    return pid


def paths(guest_dir, pid):
    """`(<pid>.on, <pid>.jsonl)` in the guest folder."""
    return os.path.join(str(guest_dir), f"{int(pid)}.on"), os.path.join(str(guest_dir), f"{int(pid)}.jsonl")


def _append_nt(path, data):
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateFileW.restype = wintypes.HANDLE
    k32.CreateFileW.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
                                wintypes.DWORD, wintypes.HANDLE)
    k32.GetFileSizeEx.argtypes = (wintypes.HANDLE, ctypes.POINTER(ctypes.c_longlong))
    k32.WriteFile.argtypes = (wintypes.HANDLE, wintypes.LPCVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
                              wintypes.LPVOID)
    k32.CloseHandle.argtypes = (wintypes.HANDLE,)
    # FILE_APPEND_DATA only: every write lands at the end, whole, whoever else appends; OPEN_EXISTING: no bridge's
    # spool, nothing written; every share flag, so the bridge can rotate the file while a hook holds it
    handle = k32.CreateFileW(path, 0x0004, 0x7, None, 3, 0x80, None)
    if not handle or handle == wintypes.HANDLE(-1).value:
        return False
    try:
        size = ctypes.c_longlong(0)
        if not k32.GetFileSizeEx(handle, ctypes.byref(size)) or size.value + len(data) > SPOOL_MAX:
            return False
        done = wintypes.DWORD(0)
        return bool(k32.WriteFile(handle, data, len(data), ctypes.byref(done), None)) and done.value == len(data)
    finally:
        k32.CloseHandle(handle)


def _append_posix(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0))  # no O_CREAT: no spool, no line
    try:
        if os.fstat(fd).st_size + len(data) > SPOOL_MAX:
            return False
        return os.write(fd, data) == len(data)
    finally:
        os.close(fd)


def _win_start(pid):
    """The creation FILETIME of a RUNNING pid as text (bg_run.process_start_time's form), else None."""
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenProcess.restype = wintypes.HANDLE
    k32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    k32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    k32.GetProcessTimes.argtypes = (wintypes.HANDLE,) + (ctypes.POINTER(wintypes.FILETIME),) * 4
    k32.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return None
    try:
        code = wintypes.DWORD(0)
        if not k32.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value != 259:  # STILL_ACTIVE
            return None
        times = [wintypes.FILETIME() for _ in range(4)]
        if not k32.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)):
            return None
        return str((times[0].dwHighDateTime << 32) | times[0].dwLowDateTime)
    finally:
        k32.CloseHandle(handle)


def bridge_alive(on):
    """The bridge the `.on` names (its `bridge_pid`, and its `bridge_start` where one was read) still runs: a pid
    the system gave to another program since is not it. An `.on` that names no bridge: not alive."""
    with open(on, "rb") as fh:
        mark = json.loads(fh.read(4096).decode("utf-8", "replace"))
    pid = mark.get("bridge_pid") if isinstance(mark, dict) else None
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return False
    began = mark.get("bridge_start")
    if os.name == "nt":
        now = _win_start(pid)
        return now is not None and (not began or now == str(began))
    if os.path.exists("/proc/self/stat"):
        try:
            with open(f"/proc/{pid}/stat", "r", encoding="utf-8", errors="replace") as fh:
                after = fh.read().rsplit(")", 1)[-1].split()
        except OSError:
            return False
        return after[0] != "Z" and (not began or after[19] == str(began))
    try:  # macOS: no start mark is read there (bridge._start_mark); the pid alone
        os.kill(pid, 0)
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def write(raw, guest_dir, pid, ts=None):
    """One hook input (its raw bytes) into the spool of Claude Code `pid`; True when a line was written. Never raises."""
    try:
        on, spool = paths(guest_dir, pid)
        if not os.path.isfile(on) or not bridge_alive(on):
            return False
        data = line_of(json.loads(raw.decode("utf-8", "replace")), ts)
        if data is None:
            return False
        return (_append_nt if os.name == "nt" else _append_posix)(spool, data)
    except Exception:
        return False


def main(argv=None):
    """The hook: `python -I note.py <guest dir>`, the event's JSON on the input. Prints nothing, exits 0."""
    killer = threading.Timer(DEADLINE_S, os._exit, (0,))
    killer.daemon = True
    killer.start()
    try:
        sys.stdout = sys.stderr = open(os.devnull, "w")
        args = sys.argv[1:] if argv is None else argv
        if args and os.path.isdir(args[0]):
            write(sys.stdin.buffer.read(READ_MAX), args[0], claude_pid())
    except BaseException:
        pass
    os._exit(0)


if __name__ == "__main__":
    main()
