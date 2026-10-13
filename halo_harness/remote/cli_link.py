"""halo_harness.remote.cli_link -- `halo remote signal link` (Halo 2.0.9
round 4): link signal-cli as a secondary device of your own Signal account.

signal-cli prints a `sgnl://linkdevice?...` URI and then waits for the phone
to scan it. The URI is shown as text and as a terminal QR code (scan it from
Signal: Settings, Linked devices, Link new device). When the phone confirms,
signal-cli names the account and Halo stores it in signal.json with the
`linked` identity model (commands travel through Note to Self).
"""

from __future__ import annotations

import queue
import re
import subprocess
import threading
import time

from halo_harness.remote import cli_common as C
from halo_harness.remote.signal_config import load_signal_config

URI = re.compile(r"sgnl://linkdevice\?\S+")
ASSOCIATED = re.compile(r"Associated with:\s*(\S+)", re.I)
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)


def _own_aci(cfg: dict, account: str):
    """Best effort: the account's own ACI from `-o json listAccounts` (None when not offered)."""
    try:
        res = C.run_cli(cfg, "listAccounts", json_out=True, timeout=30)
        import json
        for row in json.loads(res.stdout or "[]"):
            if isinstance(row, dict) and row.get("number") in (account, None):
                for key in ("aci", "uuid"):
                    if UUID.match(str(row.get(key) or "")):
                        return row[key]
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return None


def cmd_link(argv: list) -> int:
    p = C.make_parser("link", "Link signal-cli to your own Signal account (shows a QR code to scan).")
    p.add_argument("--name", default="Halo", help="the device name the phone shows (default Halo)")
    p.add_argument("--ascii", action="store_true", help="draw the QR code with # instead of block glyphs")
    p.add_argument("--timeout", type=float, default=180.0, help="seconds to wait for the scan (default 180)")
    a, rc = C.parse(p, argv)
    if a is None:
        return rc
    cfg, bad = C.configured(a.json)
    if cfg is None:
        return bad
    argv_ = C.cli_argv(cfg, "link", "-n", a.name)
    try:
        proc = subprocess.Popen(argv_, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace", bufsize=1, env=C.child_env())
    except OSError as e:
        return C.fail(a.json, "spawn_failed", f"Could not start signal-cli: {e}")
    lines: "queue.Queue" = queue.Queue()
    threading.Thread(target=lambda: ([lines.put(x) for x in proc.stdout], lines.put(None)), daemon=True).start()
    uri = account = None
    tail = []
    deadline = time.monotonic() + a.timeout
    while time.monotonic() < deadline:
        try:
            line = lines.get(timeout=0.25)
        except queue.Empty:
            continue
        if line is None:
            break
        tail.append(line.strip())
        m = URI.search(line)
        if m and uri is None:
            uri = m.group(0)
            if not a.json:
                print("Open Signal on the phone: Settings, Linked devices, Link new device, and scan:")
                C.print_qr(uri, a.ascii)
                print(uri + "\nWaiting for the phone...")
        m = ASSOCIATED.search(line)
        if m:
            account = m.group(1)
            break
    try:
        proc.wait(timeout=15 if account else 0.1)
    except subprocess.TimeoutExpired:
        proc.terminate()
    if not account:
        why = "timed out waiting for the scan" if uri else "signal-cli did not print a link; " + " ".join(tail[-3:])[:200]
        return C.fail(a.json, "link_failed", f"Linking did not finish: {why}.", uri=uri)
    aci = _own_aci(cfg, account)
    upd = {"account": account, "identity_model": "linked"}
    if aci:
        upd["own_aci"] = aci
    C.save_signal_config(**upd)
    load_signal_config()
    if a.json:
        C.emit_json({"ok": True, "account": account, "own_aci": aci, "uri": uri})
    else:
        print(f"Linked as {account}." + ("" if aci else " Add \"own_aci\" (your account's ACI) to signal.json for Note to Self."))
        print("Next: halo remote signal run")
    return 0
