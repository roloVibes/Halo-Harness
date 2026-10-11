"""tests.helpers.fake_signal_admin -- a stand-in for signal-cli's one-shot
commands (`--version`, `register`, `verify`, `setPin`, `link`, `listAccounts`)
for the `halo remote signal` CLI tests. Behaviour comes from FAKE_SIGNAL_MODE
(ok | captcha | ratelimit | locked | noscan); every call appends its argv
to FAKE_SIGNAL_LOG (one JSON list per line). Fake values only."""
from __future__ import annotations

import json
import os
import sys
import time

ACCOUNT = "+15555550123"
ACI = "00000000-0000-4000-8000-0000000000aa"


def main(argv: list) -> int:
    log = os.environ.get("FAKE_SIGNAL_LOG")
    if log:
        with open(log, "a", encoding="utf-8") as f:
            f.write(json.dumps(argv) + "\n")
    mode = os.environ.get("FAKE_SIGNAL_MODE", "ok")
    if "--version" in argv:
        print("signal-cli " + os.environ.get("FAKE_SIGNAL_VERSION", "0.14.9"))
        return 0
    words, i = [], 0
    while i < len(argv):
        if argv[i] in ("-d", "-a", "-o"):
            i += 2
            continue
        words.append(argv[i])
        i += 1
    cmd, rest = (words[0], words[1:]) if words else ("", [])
    if cmd == "register":
        if mode == "ratelimit":
            print("Rate limit reached: retryAfterSeconds: 3600", file=sys.stderr)
            return 5
        if mode == "captcha" and "--captcha" not in rest:
            print("Captcha required for verification, use --captcha CAPTCHA", file=sys.stderr)
            return 1
        return 0
    if cmd == "verify":
        code = rest[0] if rest else ""
        if mode == "locked" and "--pin" not in rest:
            print("Registration Lock failed: a PIN is required", file=sys.stderr)
            return 1
        if code != "123456":
            print("Verification failed: wrong code", file=sys.stderr)
            return 1
        return 0
    if cmd == "setPin":
        return 0
    if cmd == "listAccounts":
        print(json.dumps([{"number": ACCOUNT, "aci": ACI}]))
        return 0
    if cmd == "link":
        print("sgnl://linkdevice?uuid=FAKEUUID&pub_key=FAKEKEY", flush=True)
        if mode == "noscan":
            time.sleep(30)
            return 1
        time.sleep(0.2)
        print("Associated with: " + ACCOUNT, flush=True)
        return 0
    print("unknown command " + cmd, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
