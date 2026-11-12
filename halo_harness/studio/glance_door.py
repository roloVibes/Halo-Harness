"""halo_harness.studio.glance_door -- how the glance reaches a phone (Halo 3.4.1.0 R4; docs/STUDIO-live.md "The glance",
docs/REMOTE.md "The glance from a phone").

The glance is `/?mode=glance` on the same loopback Studio, with the same token. Studio answers 127.0.0.1 alone (its
peer and its Host header, studio/server.py), so the one door from another device is the one Studio already prints: an
SSH forward of its port. A phone's SSH app forwards the phone's own 127.0.0.1:<port> through this machine's SSH
server, and the page, the token and the owner proof are exactly what they are here. Nothing here binds, listens or
changes a firewall: `door` only asks whether an SSH server answers on this machine (a connect to 127.0.0.1:22) and,
when one does, which address and user a phone's SSH app would use.

    door(server)           GET glance/door: {here, url, port, ssh, lan, user, steps, line, qr}
    over_ssh(port, mode)   the terminal's "Over SSH" line, and the phone's line when the mode is glance
    note(where, mode)      only the phone's line ("" unless the mode is glance); `where` is a port or a URL
"""

from __future__ import annotations

import getpass
import re

SSH_PORT = 22  # the door's port; a test points it at a listener of its own
PATH = "/?mode=glance"
OFF = ("This page is this-machine-only: Studio answers 127.0.0.1 alone and no SSH server answers on this machine, so a "
       "phone cannot reach it. With an SSH server on here, this shows the address to type (docs/REMOTE.md).")


def ssh_on(timeout: float = 0.3) -> bool:
    """An SSH server answers on this machine (a connect to 127.0.0.1:SSH_PORT, nothing sent: launch.py's loopback probe)."""
    from halo_harness.studio.launch import port_answers
    return port_answers(SSH_PORT, timeout)


def _user() -> str:
    try:
        return getpass.getuser() or "you"
    except Exception:
        return "you"


def _lan() -> str:
    from halo_harness.peers.net import lan_address
    return lan_address()


def steps(port: int, lan: str, user: str) -> list:
    """What to do on the phone, in order, when the door is on."""
    return [f"In an SSH app on the phone, connect to {user}@{lan} and forward the phone's port {port} to 127.0.0.1:{port}.",
            "Scan the code with the phone's camera, or type the address under it, to open the page in the phone's browser.",
            "Keep the SSH app connected while you look; the page reconnects by itself and says when it is stale."]


def door(server) -> dict:
    """Where the glance is: here, and from a phone when an SSH server answers on this machine."""
    port = int(server.server_address[1])
    here = f"http://127.0.0.1:{port}{PATH}"
    url = f"{here}#t={server.token}"
    on = ssh_on()
    out = {"here": here, "url": url, "port": port, "ssh": on, "lan": "", "user": "", "steps": [], "qr": [],
           "line": OFF}
    if on:
        lan, user = _lan(), _user()
        out.update(lan=lan, user=user, steps=steps(port, lan, user), qr=qr_rows(url),
                   line=f"From a phone: through this machine's SSH server ({user}@{lan}), the same page on the phone's "
                        f"own 127.0.0.1:{port}.")
    return out


def qr_rows(text: str) -> list:
    """The QR matrix of `text` as rows of '0' / '1' ([] when it does not fit a QR this encoder makes)."""
    try:
        from halo_harness.remote.qr import encode
        return ["".join("1" if v else "0" for v in row) for row in encode(text)]
    except Exception:
        return []


def _port(where) -> int:
    if isinstance(where, int):
        return where
    m = re.search(r":(\d+)/", str(where or ""))
    return int(m.group(1)) if m else 0


def note(where, mode) -> str:
    """The terminal's phone line for `halo studio --mode glance` ("" for any other mode)."""
    if mode != "glance":
        return ""
    if not ssh_on():
        return "\nThe glance: " + OFF
    port = _port(where)
    return (f"\nThe glance from a phone: an SSH app on the phone forwards its port {port} to 127.0.0.1:{port} through "
            f"{_user()}@{_lan()}, then opens the same address in its browser.")


def over_ssh(port: int, mode=None) -> str:
    """`halo studio`'s second line: the SSH forward for another machine, and the phone's line for the glance."""
    return f"Over SSH: ssh -L {port}:127.0.0.1:{port} <host>, then open the same URL on your machine." + note(port, mode)


def get_door(req):
    return 200, door(req.server)


def dispatch_glance(req):
    if req.method == "GET" and req.path == "glance/door":
        return get_door(req)
    return 404, {"error": f"no route {req.method} /api/{req.path}"}
