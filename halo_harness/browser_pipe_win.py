"""halo_harness.browser_pipe_win -- Windows: the DevTools pipe of Halo's browser (browser_cdp.py) by HANDLES, no port
(3.6.0.6 W). Python cannot hand a child CRT descriptors 3 and 4 on Windows, but Chrome and Edge take two inherited
pipe handles by `--remote-debugging-pipe --remote-debugging-io-pipes=<read>,<write>` (proven by a real run of both
on Windows 11, 2026-11-20). The two child ends are inheritable and are the ONLY handles passed on (STARTUPINFO's
handle list); every other handle of this process stays out of the browser.

The browser starts suspended, joins a Job object of its own (nested in Halo's, so a hard end of Halo still ends it)
and only then runs: every process it starts is in that Job from its first instruction, and `end_job` ends exactly
those (never by name, never anything else). Stdlib only (ctypes, msvcrt).

    spawn(argv, popen) -> (proc, read_fd, write_fd, job)   argv without the pipe switches; popen is the Popen to use
    end_job(job)                                          every process of the browser's Job, now; the handle closed
"""

from __future__ import annotations

import os
import subprocess

CREATE_SUSPENDED = 0x00000004
CREATE_NO_WINDOW = 0x08000000


def _resume(proc) -> None:
    import ctypes
    ntdll = ctypes.WinDLL("ntdll")
    ntdll.NtResumeProcess.argtypes = (ctypes.c_void_p,)
    ntdll.NtResumeProcess(ctypes.c_void_p(int(proc._handle)))


def spawn(argv: list, popen=None, *, show: bool = False, env=None):
    """Start the browser with the pipe on two handles; returns (proc, fd to read from, fd to write to, job or None)."""
    import msvcrt
    from halo_harness import closing
    popen = popen or subprocess.Popen
    to_child_r, to_child_w = os.pipe()
    from_child_r, from_child_w = os.pipe()
    h_in, h_out = msvcrt.get_osfhandle(to_child_r), msvcrt.get_osfhandle(from_child_w)
    os.set_handle_inheritable(h_in, True)
    os.set_handle_inheritable(h_out, True)
    si = subprocess.STARTUPINFO()
    si.lpAttributeList = {"handle_list": [h_in, h_out]}
    flags = CREATE_SUSPENDED | (0 if show else CREATE_NO_WINDOW)
    full = [argv[0], "--remote-debugging-pipe", f"--remote-debugging-io-pipes={h_in},{h_out}", *argv[1:]]
    try:
        proc = popen(full, startupinfo=si, close_fds=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, creationflags=flags, env=env)
    except BaseException:
        for fd in (to_child_r, to_child_w, from_child_r, from_child_w):
            os.close(fd)
        raise
    os.close(to_child_r)
    os.close(from_child_w)
    job = closing.new_job(0)
    try:
        if job and not closing._k32().AssignProcessToJobObject(job, int(proc._handle)):
            closing._k32().CloseHandle(job)
            job = None
    finally:
        _resume(proc)
    return proc, from_child_r, to_child_w, job


def end_job(job) -> None:
    """Every process still in the browser's Job ends now; the Job's handle is closed."""
    if not job:
        return
    from halo_harness import closing
    k32 = closing._k32()
    try:
        k32.TerminateJobObject(job, 1)
    finally:
        k32.CloseHandle(job)
