"""halo_signal.setup -- the pack's Setup check blocks (pack.yaml `contributes.setup`; Studio's Setup -> Signal and
`halo setup signal`). Each prints its lines and ends 0 (green) or 1 (what is missing, and what to do):

    box       signal-cli found on this machine, its version, Java when the JVM build needs it, the install line
    link      link this computer to your phone's Signal as a device: the QR code to scan (a helper waits for the scan)
    test      a test message to every paired phone (Note to Self with a linked account), through the running bridge
    pair      a pairing phrase and its QR code; run again: "waiting for a text from a new number" / "paired +1...0100"
    phones    the paired phones, signing, home folders, notes
    service   the bridge as the supervisor runs it, and how to start the supervisor at logon
"""

from __future__ import annotations

from halo_harness.ext import remote as R

from halo_signal import PACK, box, ctl, ctl_account, settings


def check_box() -> int:
    ok, lines = box.report(settings.load_signal())
    print("\n".join(lines))
    return 0 if ok else 1


OFFLINE = "Halo's offline mode is on: {what} needs Signal's servers, so nothing was done (network.offline)."


def check_link() -> int:
    cfg = settings.load_signal()
    if cfg.get("account"):
        print(f"This computer already speaks Signal as {cfg['account']} ({cfg.get('identity_model')}).")
        return 0
    if R.offline():
        print(OFFLINE.format(what="linking"))
        return 0
    if box.find(cfg)[0] is None:
        print("signal-cli is not installed yet: the first block (Signal on this box) says how.")
        return 1
    return ctl_account.link([])


def check_test() -> int:
    if R.offline():
        print(OFFLINE.format(what="a test message"))
        return 0
    if not settings.load_signal().get("account"):
        print("No Signal account yet: link this computer first.")
        return 1
    return ctl.test([])


def check_pair() -> int:
    pairing = ctl._pairing()
    inv = pairing.invite_state()
    if inv["state"] == "waiting":
        print("Pairing phrase: " + ctl._invite_line(inv))
        return 0
    if inv["state"] == "paired":
        print("Pairing phrase: " + ctl._invite_line(inv))
        ctl.phones([])
        return 0
    return ctl.pair([])


def check_phones() -> int:
    ctl.phones([])
    return 0


def check_service() -> int:
    row = R.service(PACK, "bridge")
    print("The bridge: " + (ctl._svc_line(row) if row else "not in the supervisor's list yet (the pack needs the "
                            "services grant, then halo supervise runs it)"))
    print("\n".join(R.logon_lines()))
    if R.offline():
        print(OFFLINE.format(what="the bridge"))
        return 0
    return 0 if row and row.get("state") == "running" else 1


BLOCKS = {"box": check_box, "link": check_link, "test": check_test, "pair": check_pair, "phones": check_phones,
          "service": check_service}
