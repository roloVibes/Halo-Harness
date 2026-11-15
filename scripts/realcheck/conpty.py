"""scripts/realcheck/conpty.py -- Windows: a child in a pseudoconsole (ConPTY), the terminal Windows Terminal itself
gives a program. Ctrl+C is the byte 0x03 typed into it (the console turns it into CTRL_C_EVENT, or a key for a
program that reads raw keys); closing the window is ClosePseudoConsole (CTRL_CLOSE_EVENT to every program in it);
a hard kill is TerminateProcess of the top process. ctypes only."""
from __future__ import annotations

import ctypes
import subprocess
import sys
import threading
from ctypes import wintypes

from realcheck.term import _Base

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
HANDLE, DWORD, BOOL = wintypes.HANDLE, wintypes.DWORD, wintypes.BOOL
EXTENDED_STARTUPINFO_PRESENT, CREATE_UNICODE_ENVIRONMENT = 0x00080000, 0x00000400
PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE = 0x00020016
STARTF_USESTDHANDLES = 0x00000100
STILL_ACTIVE = 259


class COORD(ctypes.Structure):
    _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]


class STARTUPINFOW(ctypes.Structure):
    _fields_ = [("cb", DWORD), ("lpReserved", wintypes.LPWSTR), ("lpDesktop", wintypes.LPWSTR),
                ("lpTitle", wintypes.LPWSTR), ("dwX", DWORD), ("dwY", DWORD), ("dwXSize", DWORD), ("dwYSize", DWORD),
                ("dwXCountChars", DWORD), ("dwYCountChars", DWORD), ("dwFillAttribute", DWORD), ("dwFlags", DWORD),
                ("wShowWindow", wintypes.WORD), ("cbReserved2", wintypes.WORD), ("lpReserved2", ctypes.c_void_p),
                ("hStdInput", HANDLE), ("hStdOutput", HANDLE), ("hStdError", HANDLE)]


class STARTUPINFOEXW(ctypes.Structure):
    _fields_ = [("StartupInfo", STARTUPINFOW), ("lpAttributeList", ctypes.c_void_p)]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [("hProcess", HANDLE), ("hThread", HANDLE), ("dwProcessId", DWORD), ("dwThreadId", DWORD)]


k32.CreatePseudoConsole.argtypes = [COORD, HANDLE, HANDLE, DWORD, ctypes.POINTER(HANDLE)]
k32.CreatePseudoConsole.restype = ctypes.c_long
k32.ClosePseudoConsole.argtypes = [HANDLE]
k32.ClosePseudoConsole.restype = None
k32.CreatePipe.argtypes = [ctypes.POINTER(HANDLE), ctypes.POINTER(HANDLE), ctypes.c_void_p, DWORD]
k32.InitializeProcThreadAttributeList.argtypes = [ctypes.c_void_p, DWORD, DWORD, ctypes.POINTER(ctypes.c_size_t)]
k32.UpdateProcThreadAttribute.argtypes = [ctypes.c_void_p, DWORD, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t,
                                          ctypes.c_void_p, ctypes.c_void_p]
k32.DeleteProcThreadAttributeList.argtypes = [ctypes.c_void_p]
k32.CreateProcessW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p, ctypes.c_void_p, BOOL, DWORD,
                               ctypes.c_void_p, wintypes.LPCWSTR, ctypes.POINTER(STARTUPINFOEXW),
                               ctypes.POINTER(PROCESS_INFORMATION)]
k32.ReadFile.argtypes = [HANDLE, ctypes.c_void_p, DWORD, ctypes.POINTER(DWORD), ctypes.c_void_p]
k32.WriteFile.argtypes = [HANDLE, ctypes.c_void_p, DWORD, ctypes.POINTER(DWORD), ctypes.c_void_p]
k32.WaitForSingleObject.argtypes = [HANDLE, DWORD]
k32.WaitForSingleObject.restype = DWORD
k32.GetExitCodeProcess.argtypes = [HANDLE, ctypes.POINTER(DWORD)]
k32.TerminateProcess.argtypes = [HANDLE, wintypes.UINT]
k32.CloseHandle.argtypes = [HANDLE]
k32.SetConsoleCtrlHandler.argtypes = [ctypes.c_void_p, BOOL]


def _pipe() -> "tuple[HANDLE, HANDLE]":
    r, w = HANDLE(), HANDLE()
    if not k32.CreatePipe(ctypes.byref(r), ctypes.byref(w), None, 0):
        raise ctypes.WinError(ctypes.get_last_error())
    return r, w


def _env_block(env: dict):
    items = sorted(env.items(), key=lambda kv: kv[0].upper())
    return ctypes.create_unicode_buffer("\0".join(f"{k}={v}" for k, v in items) + "\0")


class ConPtyTerminal(_Base):
    def __init__(self, argv, *, env, cwd, cols: int = 120, rows: int = 40) -> None:
        super().__init__()
        in_r, self._in_w = _pipe()
        self._out_r, out_w = _pipe()
        self._hpc = HANDLE()
        hr = k32.CreatePseudoConsole(COORD(cols, rows), in_r, out_w, 0, ctypes.byref(self._hpc))
        if hr != 0:
            raise OSError(f"CreatePseudoConsole failed: 0x{hr & 0xFFFFFFFF:08x}")
        size = ctypes.c_size_t(0)
        k32.InitializeProcThreadAttributeList(None, 1, 0, ctypes.byref(size))
        self._attrs = ctypes.create_string_buffer(size.value)
        if not k32.InitializeProcThreadAttributeList(self._attrs, 1, 0, ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        if not k32.UpdateProcThreadAttribute(self._attrs, 0, PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE, self._hpc,
                                             ctypes.sizeof(HANDLE), None, None):
            raise ctypes.WinError(ctypes.get_last_error())
        si = STARTUPINFOEXW()
        si.StartupInfo.cb = ctypes.sizeof(STARTUPINFOEXW)
        si.StartupInfo.dwFlags = STARTF_USESTDHANDLES  # null std handles: the child takes the pseudoconsole's
        si.lpAttributeList = ctypes.cast(self._attrs, ctypes.c_void_p)
        pi = PROCESS_INFORMATION()
        # "Ctrl+C is ignored" is inherited by a child: a launcher (a CI runner, an msys shell) may have set it on this
        # process, and a person's terminal never does, so it is cleared here before the child starts
        from realcheck import winproc
        self.cleared_how = winproc.clear_own_ignore_ctrl_c()[1]
        cmd = ctypes.create_unicode_buffer(subprocess.list2cmdline([str(a) for a in argv]))
        block = _env_block(env)
        if not k32.CreateProcessW(None, cmd, None, None, False, EXTENDED_STARTUPINFO_PRESENT | CREATE_UNICODE_ENVIRONMENT,
                                  block, str(cwd), ctypes.byref(si), ctypes.byref(pi)):
            err = ctypes.get_last_error()
            k32.ClosePseudoConsole(self._hpc)
            raise ctypes.WinError(err)
        k32.CloseHandle(pi.hThread)
        k32.CloseHandle(in_r)
        k32.CloseHandle(out_w)
        self._proc, self.pid = pi.hProcess, int(pi.dwProcessId)
        self._closed = False
        flags = winproc.console_flags(self.pid)
        self.child_ignores_ctrl_c = bool(flags is not None and flags & winproc.IGNORE_CTRL_C)
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self) -> None:
        buf = ctypes.create_string_buffer(65536)
        n = DWORD(0)
        while k32.ReadFile(self._out_r, buf, 65536, ctypes.byref(n), None) and n.value:
            self._got(buf.raw[:n.value])

    def write(self, data: bytes) -> None:
        if self._closed:
            return
        n = DWORD(0)
        k32.WriteFile(self._in_w, data, len(data), ctypes.byref(n), None)

    def close_window(self) -> None:
        if self._closed:
            return
        self._closed = True
        # ClosePseudoConsole may wait for the output to drain: the pump keeps reading; a thread keeps this call short
        t = threading.Thread(target=k32.ClosePseudoConsole, args=(self._hpc,), daemon=True)
        t.start()
        t.join(10)

    def console_event(self, event: int) -> bool:
        """CTRL_C_EVENT (0) or CTRL_BREAK_EVENT (1) to every program in this pseudoconsole, the way the console
        raises it: a helper with no console of its own attaches to the child's and calls GenerateConsoleCtrlEvent.
        Ctrl+Break is the one a program cannot switch off."""
        helper = ("import ctypes, sys\nk = ctypes.windll.kernel32\nk.FreeConsole()\n"
                  f"ok = k.AttachConsole({self.pid}) and (k.SetConsoleCtrlHandler(None, True) or True) "
                  f"and k.GenerateConsoleCtrlEvent({int(event)}, 0)\nsys.exit(0 if ok else 1)\n")
        try:
            r = subprocess.run([sys.executable, "-c", helper], timeout=20, stdin=subprocess.DEVNULL,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               creationflags=0x00000008)  # DETACHED_PROCESS: free to attach to the child's console
            return r.returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False

    def ctrl_break(self) -> bool:
        return self.console_event(1)

    def hard_kill(self) -> None:
        k32.TerminateProcess(self._proc, 1)

    def poll(self):
        code = DWORD(0)
        if k32.GetExitCodeProcess(self._proc, ctypes.byref(code)) and code.value != STILL_ACTIVE:
            return int(code.value)
        return None

    def wait(self, timeout: float):
        k32.WaitForSingleObject(self._proc, max(0, int(timeout * 1000)))
        return self.poll()

    def cleanup(self) -> None:
        self.close_window()
        k32.CloseHandle(self._in_w)
