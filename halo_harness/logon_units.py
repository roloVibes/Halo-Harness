"""halo_harness.logon_units -- the "at logon" files that start one of Halo's background programs when you log in
(Halo 2.0.9 round 4 as remote/daemon_units.py, the Signal bridge's; 3.3.13.0 R3: renamed for what it is, the
supervisor's and the host's, now that the supervisor runs the packs' services, the Signal pack's bridge among them).

One unit per OS, written into the program's own state folder and never enabled by Halo: the caller prints the
single command that enables it.

    linux    <stem>.service        systemd user unit
    macos    <label>.plist         launchd agent
    windows  <stem>-task.xml       Task Scheduler task (at logon)

    SUPERVISOR                     the supervisor's unit: halo-supervise, dev.halo.supervise (halo supervise --service)
    halo_argv()                    how a unit starts halo: the `halo` command on PATH, else this Python -m halo_harness
    write_unit(os, argv, env, unit, out_dir) -> (path, enable command)
    enable_command(os, path, task) the one command per OS

`JAVA_TOOL_OPTIONS` is carried into the systemd unit and the launchd plist when it is set in the environment that
writes it (the proxied-VM recipe a service like the Signal pack's signal-cli reads); the Windows task does not carry
it, and a systemd value is written as given (docs/SUPERVISE.md "The service files", 3.3.14.0 REVIEW #27).
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Optional
from xml.sax.saxutils import escape

OS_NAMES = ("linux", "macos", "windows")
# 3.1.8.0 R1: a Unit names the service's files, label, description and the Task Scheduler name.
SUPERVISOR = {"stem": "halo-supervise", "label": "dev.halo.supervise",
              "desc": "Halo supervisor (the goal queue and the packs' services)", "task": "Halo Supervise"}


def files_for(stem: str, label: str) -> dict:
    return {"linux": f"{stem}.service", "macos": f"{label}.plist", "windows": f"{stem}-task.xml"}


def os_name(platform: Optional[str] = None) -> str:
    p = platform if platform is not None else sys.platform
    return "windows" if p.startswith("win") else ("macos" if p == "darwin" else "linux")


def halo_argv() -> list:
    """How a unit starts halo: the `halo` command when it is on PATH, otherwise this interpreter with `-m halo_harness`."""
    exe = shutil.which("halo")
    return [exe] if exe else [sys.executable, "-m", "halo_harness"]


def _quote(word: str) -> str:
    return '"' + word.replace("\\", "\\\\").replace('"', '\\"') + '"' if any(c in word for c in ' \t"\\') else word


def render_systemd(argv: list, env: Optional[dict] = None, desc: str = SUPERVISOR["desc"]) -> str:
    lines = ["[Unit]", f"Description={desc}", "After=network-online.target",
             "Wants=network-online.target", "", "[Service]", "Type=simple",
             "ExecStart=" + " ".join(_quote(w) for w in argv), "Restart=on-failure", "RestartSec=5"]
    for k, v in sorted((env or {}).items()):
        lines.append(f'Environment="{k}={v}"')
    lines += ["", "[Install]", "WantedBy=default.target", ""]
    return "\n".join(lines)


def render_launchd(argv: list, env: Optional[dict] = None, label: str = SUPERVISOR["label"]) -> str:
    args = "".join(f"    <string>{escape(w)}</string>\n" for w in argv)
    envs = ""
    if env:
        envs = "  <key>EnvironmentVariables</key>\n  <dict>\n" + "".join(
            f"    <key>{escape(k)}</key>\n    <string>{escape(v)}</string>\n" for k, v in sorted(env.items())) + "  </dict>\n"
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
            '<plist version="1.0">\n<dict>\n'
            f"  <key>Label</key>\n  <string>{escape(label)}</string>\n"  # 3.3.7.0 R1: the unit's own label
            f"  <key>ProgramArguments</key>\n  <array>\n{args}  </array>\n{envs}"
            # restart on failure only (as systemd / Task Scheduler): the kill switch's clean exit stays down
            "  <key>RunAtLoad</key>\n  <true/>\n"
            "  <key>KeepAlive</key>\n  <dict>\n    <key>SuccessfulExit</key>\n    <false/>\n  </dict>\n"
            "  <key>StandardOutPath</key>\n  <string>/dev/null</string>\n"
            "  <key>StandardErrorPath</key>\n  <string>/dev/null</string>\n"
            "</dict>\n</plist>\n")


def render_task_xml(argv: list, desc: str = SUPERVISOR["desc"]) -> str:
    args = " ".join(f'"{w}"' if " " in w else w for w in argv[1:])
    return ('<?xml version="1.0" encoding="UTF-16"?>\n'
            '<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">\n'
            f"  <RegistrationInfo><Description>{escape(desc)}</Description></RegistrationInfo>\n"
            "  <Triggers><LogonTrigger><Enabled>true</Enabled></LogonTrigger></Triggers>\n"
            "  <Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>"
            "<DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>"
            "<StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>"
            "<ExecutionTimeLimit>PT0S</ExecutionTimeLimit>"
            "<RestartOnFailure><Interval>PT1M</Interval><Count>99</Count></RestartOnFailure></Settings>\n"
            f"  <Actions Context=\"Author\"><Exec><Command>{escape(argv[0])}</Command>"
            f"<Arguments>{escape(args)}</Arguments></Exec></Actions>\n</Task>\n")


def enable_command(os_n: str, path: Path, task: str = SUPERVISOR["task"]) -> str:
    if os_n == "linux":
        return f"systemctl --user link {path} && systemctl --user enable --now {path.name}"
    if os_n == "macos":
        return f"launchctl bootstrap gui/$(id -u) {path}"
    return f'schtasks /Create /TN "{task}" /XML "{path}"'


def write_unit(os_n: Optional[str] = None, argv: Optional[list] = None, env: Optional[dict] = None,
               unit: Optional[dict] = None, out_dir=None) -> tuple:
    """Write the unit for `os_n`; returns `(path, enable_command)`. Nothing is enabled. `unit`
    (default SUPERVISOR) names the files/label/description/task; `out_dir` (default the supervisor's folder)
    is where it is written (3.1.8.0 R1: the supervisor writes under its own state dir)."""
    os_n = os_n or os_name()
    if os_n not in OS_NAMES:
        raise ValueError(f"os must be one of {', '.join(OS_NAMES)}")
    unit = unit or SUPERVISOR
    argv = argv or halo_argv() + ["supervise"]
    if env is None:
        env = {k: os.environ[k] for k in ("JAVA_TOOL_OPTIONS",) if os.environ.get(k)}
    text = (render_systemd(argv, env, unit["desc"]) if os_n == "linux" else
            render_launchd(argv, env, unit["label"]) if os_n == "macos" else render_task_xml(argv, unit["desc"]))
    from halo_harness.privateio import write_private_atomic
    if out_dir is None:
        from halo_harness.supervise.queue import root
        out_dir = root()
    base = Path(out_dir)
    base.mkdir(parents=True, exist_ok=True)
    path = base / files_for(unit["stem"], unit["label"])[os_n]
    if os_n == "windows":  # Task Scheduler reads the UTF-16 (BOM) form its own export writes
        path.write_bytes(text.encode("utf-16"))
    else:
        write_private_atomic(path, text)
    return path, enable_command(os_n, path, unit["task"])
