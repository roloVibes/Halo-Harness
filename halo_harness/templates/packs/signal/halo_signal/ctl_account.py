"""halo_signal.ctl_account -- the Signal account of this computer: `/signal link` and `/signal register`.

    /signal link [--name Halo]   link this computer to your own Signal as a device (Signal on the phone: Settings ->
                                 Linked devices -> Link new device, then scan the QR code shown). A helper waits for
                                 the scan in the background for up to 3 minutes (link.json says where it is), so the
                                 command returns at once; run it again to see "waiting" or "linked as ...". The
                                 conversation then lives in your Note to Self chat.
    /signal register +<number> [--captcha signalcaptcha://...] [--voice] [--code <code>] [--pin <pin>]
                                 a number of Halo's own (a dedicated SIM or VoIP number): Signal asks for a captcha
                                 first (https://signalcaptchas.org/registration/generate.html), then the SMS (or voice)
                                 code; a registration-lock PIN is set and kept in the data folder (0600)

Neither runs while the bridge runs on the same account folder: `/signal off` first.
"""

from __future__ import annotations

import json
import re
import secrets
import subprocess
import sys
import time
from pathlib import Path

from halo_harness.ext import remote as R

from halo_signal import PACK, files, settings
from halo_signal.signalcli import cli_argv, rpc_once, run_cli

URI = re.compile(r"sgnl://linkdevice\?\S+")
ASSOCIATED = re.compile(r"Associated with:\s*(\S+)", re.I)
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
E164 = re.compile(r"^\+[1-9]\d{6,14}$")
CAPTCHA_URL = "https://signalcaptchas.org/registration/generate.html"
LINK_WAIT_S = 180.0


def _link_state() -> dict:
    return files.read_json(files.path("link.json"))


def _set_link(**row) -> None:
    files.write_text(files.path("link.json"), json.dumps({**row, "at": time.time()}))


def _show_uri(uri: str) -> None:
    print("On the phone: Signal -> Settings -> Linked devices -> Link new device, and scan:\n")
    print(R.qr_text(uri))
    print(f"\n{uri}\nThen `/signal link` again says \"linked\" (the helper waits up to {int(LINK_WAIT_S // 60)} minutes).")


def link(args) -> int:
    st = _link_state()
    fresh = time.time() - float(st.get("at") or 0) < LINK_WAIT_S
    if st.get("state") == "waiting" and fresh and st.get("uri"):
        _show_uri(st["uri"])
        return 0
    if st.get("state") == "linked" and "--again" not in args:
        print(f"Linked as {st.get('account')}: the conversation is your Note to Self chat. (`--again` links anew.)")
        return 0
    name = args[args.index("--name") + 1] if "--name" in args and args.index("--name") + 1 < len(args) else "Halo"
    _set_link(state="starting")
    helper = [sys.executable, str(Path(__file__).resolve().parent.parent / "bin" / "signal.py"), "link-helper", name]
    kw: dict = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if sys.platform == "win32":
        kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "CREATE_NO_WINDOW", 0)
    else:
        kw["start_new_session"] = True
    try:
        subprocess.Popen(helper, **kw)
    except OSError as e:
        print(f"The link helper did not start: {e}")
        return 1
    end = time.monotonic() + 20.0
    while time.monotonic() < end:
        st = _link_state()
        if st.get("uri") or st.get("state") == "failed":
            break
        time.sleep(0.2)
    if st.get("uri"):
        _show_uri(st["uri"])
        return 0
    print("Linking did not start: " + (st.get("line") or "signal-cli printed no link in 20 s (is it installed? "
                                       "Setup -> Signal on this box)"))
    return 1


def _own_aci(cfg: dict, account: str):
    try:
        res = run_cli(cfg, "listAccounts", json_out=True, timeout=30)
        for row in json.loads(res.stdout or "[]"):
            if isinstance(row, dict) and row.get("number") in (account, None):
                for key in ("aci", "uuid"):
                    if UUID.match(str(row.get(key) or "")):
                        return row[key]
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return None


def link_helper(args) -> int:
    """The background half of `/signal link`: signal-cli link, its URI written to link.json, the account saved."""
    cfg = settings.load_signal()
    name = args[0] if args else "Halo"
    try:
        proc = subprocess.Popen(cli_argv(cfg, "link", "-n", name), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1)
    except OSError as e:
        _set_link(state="failed", line=f"signal-cli did not start: {e}")
        return 1
    import threading
    watchdog = threading.Timer(LINK_WAIT_S, proc.terminate)  # signal-cli may wait for a scan forever
    watchdog.daemon = True
    watchdog.start()
    account, uri, tail = None, None, []
    end = time.monotonic() + LINK_WAIT_S
    for line in proc.stdout:
        tail.append(line.strip())
        m = URI.search(line)
        if m and uri is None:
            uri = m.group(0)
            _set_link(state="waiting", uri=uri)
        m = ASSOCIATED.search(line)
        if m or time.monotonic() > end:
            account = m.group(1) if m else None
            break
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.terminate()
    watchdog.cancel()
    if not account:
        _set_link(state="failed", line=("no scan in time" if uri else "signal-cli: " + " ".join(tail[-3:])[:200]))
        return 1
    upd = {"account": account, "identity_model": "linked"}
    aci = _own_aci(cfg, account)
    if aci:
        upd["own_aci"] = aci
    settings.save_signal(**upd)
    _set_link(state="linked", account=account)
    R.service_ask(PACK, "bridge", "start")
    return 0


def register(args) -> int:
    nums = [a for a in args if a.startswith("+")]
    opt = {k: args[args.index(k) + 1] for k in ("--captcha", "--code", "--pin") if k in args and args.index(k) + 1 < len(args)}
    if not nums or not E164.match(nums[0]):
        print("Usage: /signal register +<number in international form> [--captcha <signalcaptcha://...>] [--voice] "
              "[--code <code>] [--pin <pin>]")
        return 2
    number, cfg = nums[0], settings.load_signal()
    if "--code" in opt:
        return _verify(cfg, number, re.sub(r"\D", "", opt["--code"]), opt.get("--pin", ""))
    words = ["register"] + (["--voice"] if "--voice" in args else []) + (["--captcha", opt["--captcha"]] if "--captcha" in opt else [])
    res = run_cli(cfg, *words, account=number)
    out = ((res.stdout or "") + (res.stderr or "")).strip()
    if res.returncode == 0:
        print(f"Asked Signal for a {'voice call' if '--voice' in args else 'SMS'} code for {number}. Then:\n"
              f"  /signal register {number} --code <code>")
        return 0
    if re.search(r"captcha", out, re.I):
        print(f"Signal wants a captcha first: open {CAPTCHA_URL} in a browser, solve it, copy the link behind "
              f"'Open Signal' (signalcaptcha://...), then:\n  /signal register {number} --captcha <that link>")
        return 1
    print(f"Registration did not go through: {out[:300] or 'signal-cli reported an error'}")
    return 1


def _verify(cfg: dict, number: str, code: str, pin: str) -> int:
    if pin:
        r = rpc_once(cfg, "verify", {"account": number, "verificationCode": code, "pin": pin})
        ok, why = r.ok, r.message
    else:
        res = run_cli(cfg, "verify", code, account=number)
        ok, why = res.returncode == 0, ((res.stdout or "") + (res.stderr or "")).strip()
    if not ok:
        hint = " The number has a registration lock: add --pin <its PIN>." if re.search(r"pin|lock", why, re.I) else ""
        print(f"Verification failed: {why[:300]}{hint}")
        return 1
    settings.save_signal(account=number, identity_model="dedicated")
    pin_file = files.path("registration-pin")
    if not pin_file.exists():
        new = pin or "".join(secrets.choice("0123456789") for _ in range(8))
        if rpc_once(cfg, "setPin", {"pin": new}, account=number).ok:
            files.write_text(pin_file, new + "\n")
            print(f"Registration lock PIN saved in {pin_file} (0600); keep a copy elsewhere.")
    print(f"Registered {number}. The bridge starts with the supervisor; then `/signal pair` pairs your phone.")
    R.service_ask(PACK, "bridge", "start")
    return 0
