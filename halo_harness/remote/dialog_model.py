"""halo_harness.remote.dialog_model -- what the TUI's `/remote` dialog (and the
`/remote pair | off | status` text forms) read and do (Halo 2.0.9 round 4).

Everything here is plain file and process work with no Textual: the dialog
calls it on a worker thread and renders the result on the UI thread. The
bridge itself is never started from here -- `/remote` shows its state and
tells you to run `halo remote signal run`.
"""

from __future__ import annotations

import time
from typing import Optional

from halo_harness.remote import bridge_state as BS
from halo_harness.remote import cli_pair
from halo_harness.remote.pairing import Pairing, PairingError
from halo_harness.remote.signal_config import remote_setting, set_signal_enabled, signal_enabled

RUN_HINT = "The bridge runs in its own terminal: `halo remote signal run`."


def snapshot() -> dict:
    """Bridge state, the control-socket line, paired phones, open contact requests."""
    from halo_harness.remote.runtime import status_line
    pairing = Pairing()
    return {"bridge": BS.read(), "signal_enabled": signal_enabled(), "control": status_line(),
            "peers": cli_pair.peer_rows(pairing), "pending": cli_pair.pending_rows(pairing)}


def pop_notices() -> list:
    """Notices the bridge left (changed safety number, rate limit, captcha ...), cleared as they are read."""
    pairing = Pairing()
    notices = pairing.notices()
    if notices:
        pairing.clear_notices()
    return notices


def approve(aci: str) -> dict:
    """Issue the one-time code for a contact request: `{ok, code, expires, trusted}` or `{ok: False, error}`."""
    try:
        ap = Pairing(ttl=remote_setting("remote.pair_code_ttl_s")).approve(aci)
    except PairingError as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, "aci": aci, "code": ap.code, "expires": ap.expires, "trusted": ap.trusted}


def paired_view(aci: str) -> Optional[dict]:
    """The signing phrase and link of a peer that is now paired (None until it is)."""
    pairing = Pairing()
    return cli_pair.pair_secret_view(pairing, aci) if pairing.is_paired(aci) else None


def set_signed(aci: str, signed: bool) -> bool:
    return Pairing().set_signed(aci, signed)


def unpair(aci: str) -> bool:
    return Pairing().unpair(aci)


def reverify(aci: str) -> dict:
    try:
        return {"ok": True, "done": Pairing().reverify(aci)}
    except PairingError as e:
        return {"ok": False, "error": str(e)}


def kill_switch(wait: float = 6.0) -> dict:
    """Stop a running bridge (the stop file it polls) and set remote.signal.enabled to false."""
    was_running = BS.request_stop()
    deadline = time.time() + wait
    while was_running and BS.read()["running"] and time.time() < deadline:
        time.sleep(0.2)
    stopped = not BS.read()["running"]
    if stopped:
        BS.clear_stop()
    set_signal_enabled(False)
    return {"was_running": was_running, "stopped": stopped}


def describe(snap: dict) -> str:
    b = snap["bridge"]
    pid = f" (pid {b['pid']})" if b.get("pid") and b.get("running") else ""
    lines = [f"bridge: {b['state']}{pid}   remote.signal.enabled: {str(snap['signal_enabled']).lower()}",
             snap["control"], f"peers: {len(snap['peers'])} paired, {sum(1 for p in snap['peers'] if p['blocked'])} blocked; "
             f"{len(snap['pending'])} contact request(s) waiting"]
    for p in snap["peers"]:
        lines.append(f"  {p['aci_prefix']}  {p['number'] or '(no number)'}  {'signed' if p['signed'] else 'unsigned'}"
                     + ("  BLOCKED (reverify)" if p["blocked"] else ""))
    if b["state"] in ("off", "stopped"):
        lines.append(RUN_HINT)
    return "\n".join(lines)


def text_command(args: str) -> str:
    """`/remote [status | pair [N] | off]` as plain text (print mode and the TUI's argument forms)."""
    words = (args or "").split()
    verb = words[0].lower() if words else "status"
    if verb == "off":
        res = kill_switch()
        return ("The bridge stopped. " if res["stopped"] and res["was_running"] else
                "The bridge is still shutting down. " if res["was_running"] else "No bridge was running. ") + \
            "remote.signal.enabled is false; `halo remote signal on` turns it back on."
    if verb == "pair":
        pending = snapshot()["pending"]
        if len(words) > 1:
            target = next((r for r in pending if str(r["index"]) == words[1] or r["aci"].startswith(words[1])), None)
            if target is None:
                return f"No contact request {words[1]!r}. Run /remote pair to list them."
            res = approve(target["aci"])
            if not res["ok"]:
                return res["error"]
            return (f"Pairing code for {target['aci_prefix']}: {res['code']}\nOn the phone, send exactly this code to the Halo "
                    "number as the next message." + ("" if res["trusted"] else
                                                      "\nThe running bridge completes the trust step; " + RUN_HINT))
        if not pending:
            return "No contact requests. On the phone, send any message to the Halo number; it shows up here."
        rows = [f"{r['index']}  {r['aci_prefix']}  {r['number'] or '(no number)'}  safety number "
                f"{cli_pair._grouped(r['safety_number'])}" for r in pending]
        return "\n".join(rows) + "\nCompare the safety number on the phone, then /remote pair <N> to approve."
    if verb == "status":
        return describe(snapshot())
    return "usage: /remote [status | pair [N] | off]"
