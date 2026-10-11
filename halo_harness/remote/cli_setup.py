"""halo_harness.remote.cli_setup -- `halo remote signal setup` and `register`
(Halo 2.0.9 round 4).

setup    pick the identity model, find or download the pinned signal-cli
         (the download needs an explicit yes), write signal.json
register captcha-gated registration of the dedicated number, then the
         verification code, then a registration-lock PIN kept in
         `<remote>/registration-pin` (0600)
"""

from __future__ import annotations

import json
import re
import secrets
import shutil
import time
from pathlib import Path

from halo_harness.privateio import write_private_atomic
from halo_harness.remote import cli_common as C
from halo_harness.remote import signal_install as inst
from halo_harness.remote.signal_config import load_signal_config, remote_dir, set_signal_enabled

CAPTCHA_URL = "https://signalcaptchas.org/registration/generate.html"
E164 = re.compile(r"^\+[1-9]\d{6,14}$")
SIZE_MB = {"native": 117, "jvm": 124}


def _pick_binary(a, cfg: dict, say) -> "tuple[object, str]":
    """`(binary or None, note)`: an explicit path, the pinned install, or one on PATH."""
    if a.binary:
        return a.binary, "using --binary"
    done = inst.find_installed(a.jvm)
    if done is not None:
        return str(done), f"found {done}"
    onpath = None if a.jvm else shutil.which("signal-cli")
    if onpath:
        return onpath, f"found {onpath} on PATH"
    return None, ""


def cmd_setup(argv: list) -> int:
    p = C.make_parser("setup", "Choose the identity model and find or download signal-cli " + inst.VERSION + ".")
    p.add_argument("--model", choices=("dedicated", "linked"), help="dedicated number (default) or linked device")
    p.add_argument("--yes", action="store_true", help="agree to the signal-cli download without asking")
    p.add_argument("--no-download", action="store_true", help="only look for an installed signal-cli")
    p.add_argument("--binary", help="use this signal-cli instead of looking or downloading")
    p.add_argument("--jvm", action="store_true", help="use the JVM build even on Linux x86-64 (needs a JRE 25; "
                   "use it behind a proxy, where the native build is untested)")
    a, rc = C.parse(p, argv)
    if a is None:
        return rc
    say = (lambda m: None) if a.json else print
    model = a.model
    if not model:
        say("How should Halo appear on Signal?\n  1  a dedicated number of its own (recommended)\n"
            "  2  a linked device on your own account (commands go through Note to Self)")
        model = "linked" if C.ask("Choose 1 or 2 [1]: ", "1") == "2" else "dedicated"
    cfg = load_signal_config()
    binary, note = _pick_binary(a, cfg, say)
    native = inst.native_host() and not a.jvm
    major = None if native else inst.java_major()
    jre_ok = native or (major is not None and major >= inst.MIN_JRE)
    status = {"downloaded": False, "signature": None}
    if binary is None:
        name = inst.asset_name(jvm=a.jvm)
        mb = SIZE_MB["native" if native else "jvm"]
        say(f"signal-cli {inst.VERSION} is not installed. Halo can download {name} (about {mb} MB)\n"
            f"from {inst.asset_url(name)}\ninto {inst.install_dir(a.jvm)} (nothing is installed system-wide).")
        if a.no_download:
            return C.fail(a.json, "not_installed", "signal-cli was not found and --no-download was given. "
                          f"Install signal-cli {inst.VERSION} and re-run setup, or pass --binary PATH.")
        if not (a.yes or C.ask("Download it now? [y/N]: ", "n").lower() in ("y", "yes")):
            return C.fail(a.json, "download_declined", "Nothing was downloaded. Re-run with --yes to download, "
                          "or install signal-cli yourself and pass --binary PATH.")
        try:
            path, sig = inst.install(say, jvm=a.jvm)
        except inst.InstallError as e:
            return C.fail(a.json, "install_failed", str(e))
        binary, note = str(path), "downloaded"
        status = {"downloaded": True, "signature": sig}
    version = inst.version_of(binary)
    if not jre_ok:
        say(f"This host needs a Java runtime, version {inst.MIN_JRE} or newer, for the JVM build of signal-cli "
            f"(found: {'none' if major is None else major}). Install one, then run `halo remote signal status`.")
    if version and version != inst.VERSION:
        say(f"signal-cli reports {version}; Halo is pinned to {inst.VERSION}.")
    C.save_signal_config(binary=binary, identity_model=model, transport="stdio", receive_mode="manual",
                         version=version or inst.VERSION)
    set_signal_enabled(True)
    nxt = ("halo remote signal register +<number>" if model == "dedicated" else "halo remote signal link")
    result = {"ok": True, "identity_model": model, "binary": binary, "version": version, "jre_ok": jre_ok,
              "note": note, **status, "next": nxt}
    if a.json:
        C.emit_json(result)
    else:
        print(f"signal.json written ({model}, signal-cli {version or 'version unknown'}, {note}).\nNext: {nxt}")
    return 0


def _retry_after(text: str):
    m = re.search(r'retryAfterSeconds"?\s*[:=]\s*(\d+)|[Rr]etry after (\d+)|(\d+) seconds', text)
    return int(next(g for g in m.groups() if g)) if m else None


def _state_path() -> Path:
    return remote_dir() / "register.json"


def _sms_attempted(number: str) -> bool:
    try:
        return json.loads(_state_path().read_text(encoding="utf-8")).get("number") == number
    except (OSError, ValueError):
        return False


def _request(cfg: dict, a) -> "tuple[int, str, dict]":
    """One `register` call. Returns (rc, kind, details); kind is ok | captcha | rate_limited | error."""
    args = ["register"] + (["--voice"] if a.voice else []) + (["--captcha", a.captcha] if a.captcha else [])
    res = C.run_cli(cfg, *args, account=a.number)
    out = (res.stdout or "") + (res.stderr or "")
    if res.returncode == 0:
        if not a.voice:
            write_private_atomic(_state_path(), json.dumps({"number": a.number, "sms_at": time.time()}))
        return 0, "ok", {}
    if res.returncode == 5 or re.search(r"rate.?limit", out, re.I):
        return 1, "rate_limited", {"retryAfterSeconds": _retry_after(out), "detail": out.strip()[:300]}
    if re.search(r"captcha", out, re.I):
        return 1, "captcha", {"detail": out.strip()[:300]}
    return 1, "error", {"detail": out.strip()[:300]}


def _verify(cfg: dict, a) -> int:
    code = re.sub(r"\D", "", a.code)
    res = C.run_cli(cfg, "verify", code, *(["--pin", a.pin] if a.pin else []), account=a.number)
    if res.returncode != 0:
        out = ((res.stdout or "") + (res.stderr or "")).strip()
        hint = " The number has a registration lock; add --pin <its PIN>." if re.search(r"pin|lock", out, re.I) else ""
        return C.fail(a.json, "verify_failed", f"Verification failed: {out[:300]}{hint}")
    C.save_signal_config(account=a.number, identity_model="dedicated")
    pin_file = remote_dir() / "registration-pin"
    locked = False
    if not pin_file.exists():
        pin = a.pin or "".join(secrets.choice("0123456789") for _ in range(8))
        set_res = C.run_cli(cfg, "setPin", pin, account=a.number)
        if set_res.returncode == 0:
            write_private_atomic(pin_file, pin + "\n")
            locked = True
    if a.json:
        C.emit_json({"ok": True, "account": a.number, "registration_lock": locked, "pin_file": str(pin_file) if locked else None})
    else:
        print(f"Registered {a.number}. " + (f"Registration lock PIN saved to {pin_file} (mode 0600); keep a copy elsewhere."
                                           if locked else "The registration lock could not be set; run setPin by hand."))
        print("Next: halo remote signal run, then message the number from your phone and use `halo remote signal pair`.")
    return 0


def cmd_register(argv: list) -> int:
    p = C.make_parser("register", "Register the dedicated number with Signal (captcha, then the SMS code).")
    p.add_argument("number", help="the number in international form, e.g. +15555550123")
    p.add_argument("--captcha", help="the signalcaptcha://... token from the captcha page")
    p.add_argument("--voice", action="store_true", help="ask for a voice call (only after an SMS code was requested)")
    p.add_argument("--code", help="the verification code; completes registration")
    p.add_argument("--pin", help="the registration-lock PIN, when the number already has one")
    a, rc = C.parse(p, argv)
    if a is None:
        return rc
    if not E164.match(a.number):
        return C.fail(a.json, "bad_number", "The number must look like +15555550123 (international form).")
    cfg, bad = C.configured(a.json)
    if cfg is None:
        return bad
    if a.code:
        return _verify(cfg, a)
    if a.voice and not _sms_attempted(a.number):
        return C.fail(a.json, "sms_first", "signal-cli can request a voice call only after an SMS code was requested "
                      "for this number. Run `halo remote signal register " + a.number + "` first and wait a minute.")
    rc, kind, info = _request(cfg, a)
    if kind == "captcha" and not a.json and not a.captcha and C.interactive():
        print(f"Signal wants a captcha first. Open {CAPTCHA_URL} in a browser on this network, solve it, and copy\n"
              "the link behind 'Open Signal' (it starts with signalcaptcha://).")
        a.captcha = C.ask("Paste the token: ")
        if a.captcha:
            rc, kind, info = _request(cfg, a)
    if kind == "ok":
        how = "voice call" if a.voice else "SMS"
        if a.json:
            C.emit_json({"ok": True, "requested": how, "next": f"halo remote signal register {a.number} --code <code>"})
            return 0
        print(f"Requested a {how} verification code for {a.number}.")
        code = C.ask("Enter the code (or press Enter to finish later): ") if C.interactive() else ""
        if code:
            a.code = code
            return _verify(cfg, a)
        print(f"Finish with: halo remote signal register {a.number} --code <code>")
        return 0
    if kind == "captcha":
        return C.fail(a.json, "captcha_required", f"Signal wants a captcha. Open {CAPTCHA_URL}, solve it, then run:\n"
                      f"  halo remote signal register {a.number} --captcha <signalcaptcha://...>", captcha_url=CAPTCHA_URL)
    if kind == "rate_limited":
        wait = info.get("retryAfterSeconds")
        return C.fail(a.json, "rate_limited", "Signal rate limit: try again " +
                      (f"in {wait} seconds." if wait else "later (Signal did not say when)."), retryAfterSeconds=wait)
    return C.fail(a.json, "register_failed", f"Registration failed: {info.get('detail') or 'signal-cli reported an error'}")
