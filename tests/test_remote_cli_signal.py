"""tests.test_remote_cli_signal -- Halo 2.0.9 round 4: `halo remote signal
setup | register | link | run --daemon` (the verbs that need a signal-cli).
signal-cli is the one-shot fake in tests/helpers/fake_signal_admin.py; the
download is ALWAYS mocked (no test touches the network); the pairing, bridge
and kill-switch verbs are in tests/test_remote_cli_run.py."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.cli_rig import Env, make_archive, run
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

ensure_default_provider_credentials()
test, TESTS = new_registry()


def _cfg() -> dict:
    from halo_harness.remote.signal_config import signal_json_path
    return json.loads(signal_json_path().read_text(encoding="utf-8"))


@test
def test_dispatch_usage_and_completion_words(ctx: Ctx):
    from halo_harness.completion_cli import REMOTE_WORDS
    from halo_harness.remote.cli import SIGNAL_VERBS
    with Env():
        rc, out, _ = run([])
        ctx.check("bare `signal` prints the verb list and exits 0", rc == 0 and "register" in out and "off / on" in out)
        rc, _, err = run(["frobnicate"])
        ctx.check("an unknown verb exits 2 on stderr", rc == 2 and "usage:" in err)
        ctx.check("`remote` with no verb exits 2", run([], top=False)[0] == 2)
        for verb in SIGNAL_VERBS:
            ctx.check(f"{verb} --help exits 0", run([verb, "--help"])[0] == 0)
        ctx.check("completion offers every verb", set(SIGNAL_VERBS) <= set(REMOTE_WORDS) and "sessions" in REMOTE_WORDS)
        rc, out, _ = run(["sessions"], top=False)
        ctx.check("`remote sessions` still works", rc == 0 and "No live sessions" in out)


@test
def test_setup_download_needs_a_yes_and_is_mocked(ctx: Ctx):
    from halo_harness.remote import signal_install as inst
    with Env():
        urls, saved = [], (inst.download, inst.verify_signature, inst.native_host, inst.find_installed)

        def fake_download(url, dest, progress=None):
            urls.append(url)
            if url.endswith(".asc"):
                Path(dest).write_text("sig", encoding="utf-8")
            else:
                make_archive(Path(dest))

        inst.download, inst.native_host = fake_download, lambda *a: False
        inst.verify_signature = lambda a, s, r=None: ("verified", "gpg: good signature")
        try:
            rc, out, err = run(["setup", "--model", "dedicated"])
            ctx.check("without --yes (and no terminal) nothing is downloaded", rc == 1 and urls == [] and "--yes" in err)
            rc, out, err = run(["setup", "--model", "dedicated", "--no-download"])
            ctx.check("--no-download only looks", rc == 1 and urls == [] and "not found" in err)
            rc, out, err = run(["setup", "--model", "dedicated", "--yes", "--json"])
            res = json.loads(out)
            ctx.check("--yes downloads the archive and its .asc from the pinned tag",
                      rc == 0 and len(urls) == 2 and urls[0].startswith("https://github.com/AsamK/signal-cli/releases/download/v0.14.9/")
                      and urls[1] == urls[0] + ".asc")
            ctx.check("the signature result is reported", res["downloaded"] is True and res["signature"] == "verified")
            cfg = _cfg()
            ctx.check("signal.json points inside ~/.halo/remote/signal-cli/dist/0.14.9",
                      Path(cfg["binary"]).exists() and "dist" in Path(cfg["binary"]).parts and "0.14.9" in Path(cfg["binary"]).parts)
            ctx.check("model, stdio transport and manual receive are written",
                      cfg["identity_model"] == "dedicated" and cfg["transport"] == "stdio" and cfg["receive_mode"] == "manual")
            ctx.check("the version is read back from the binary", res["version"] == "0.14.9")
            from halo_harness.theme import get_config_value
            ctx.check("remote.signal.enabled is true", get_config_value("remote.signal.enabled", False) is True)
            dl = inst.install_dir().parent.parent / "dl"
            ctx.check("the archive was cleaned up", dl.is_dir() and not list(dl.glob("*.tar.gz")))
            before = len(urls)
            rc, out, _ = run(["setup", "--model", "linked", "--json"])
            ctx.check("a second setup reuses the install (no download) and switches model",
                      rc == 0 and len(urls) == before and _cfg()["identity_model"] == "linked" and json.loads(out)["downloaded"] is False)
        finally:
            inst.download, inst.verify_signature, inst.native_host, inst.find_installed = saved


@test
def test_setup_jre_notice_and_bad_signature(ctx: Ctx):
    from halo_harness.remote import signal_install as inst
    with Env():
        saved = (inst.download, inst.verify_signature, inst.native_host, inst.java_major)
        inst.native_host = lambda *a: False
        inst.java_major = lambda *a, **k: 17
        inst.download = lambda url, dest, progress=None: make_archive(Path(dest)) if not url.endswith(".asc") else Path(dest).write_text("s")
        inst.verify_signature = lambda a, s, r=None: ("bad", "gpg reports a BAD signature")
        try:
            rc, out, err = run(["setup", "--model", "dedicated", "--yes"])
            ctx.check("a BAD signature stops before unpacking", rc == 1 and "signature check failed" in err
                      and not (inst.install_dir()).exists())
            inst.verify_signature = lambda a, s, r=None: ("no-gpg", "gpg is not installed")
            rc, out, err = run(["setup", "--model", "dedicated", "--yes"])
            ctx.check("an unchecked signature is reported, setup continues", rc == 0 and "Signature: no-gpg" in out)
            ctx.check("an old JRE is named with the version needed", "version 25 or newer" in out and "found: 17" in out)
        finally:
            inst.download, inst.verify_signature, inst.native_host, inst.java_major = saved


@test
def test_register_captcha_rate_limit_voice_and_verify(ctx: Ctx):
    with Env("captcha") as env:
        env.write_signal_json(identity_model="dedicated")
        rc, out, err = run(["register", "+15555550123"])
        ctx.check("the captcha is explained with the URL and the flag", rc == 1 and "signalcaptchas.org" in err and "--captcha" in err)
        rc, out, err = run(["register", "+15555550123", "--captcha", "signalcaptcha://fake-token"])
        reg = [c for c in env.calls() if "register" in c][-1]
        ctx.check("the token is passed through to signal-cli", rc == 0 and "--captcha" in reg and "signalcaptcha://fake-token" in reg)
        ctx.check("the SMS request is announced with the next step", "Requested a SMS" in out and "--code" in out)
        rc, _, _ = run(["register", "+15555550123", "--captcha", "t", "--voice"])
        ctx.check("--voice works after an SMS attempt for the same number", rc == 0 and "--voice" in [c for c in env.calls() if "register" in c][-1])
        rc, _, err = run(["register", "+15555550199", "--voice"])
        ctx.check("--voice for a number with no SMS attempt says what to do first", rc == 1 and "SMS code was requested" in err)
        rc, out, _ = run(["register", "notanumber", "--json"])
        ctx.check("a malformed number is rejected before signal-cli runs", rc == 1 and json.loads(out)["error"] == "bad_number")
    with Env("ratelimit") as env:
        env.write_signal_json()
        rc, out, _ = run(["register", "+15555550123", "--json"])
        res = json.loads(out)
        ctx.check("a -5 rate limit surfaces retryAfterSeconds", rc == 1 and res["error"] == "rate_limited" and res["retryAfterSeconds"] == 3600)
        rc, _, err = run(["register", "+15555550123"])
        ctx.check("and in words", "in 3600 seconds" in err)
    with Env("ok") as env:
        env.write_signal_json()
        rc, out, err = run(["register", "+15555550123", "--code", "000000"])
        ctx.check("a wrong code fails with signal-cli's reason", rc == 1 and "wrong code" in err)
        rc, out, err = run(["register", "+15555550123", "--code", "123 456"])
        cfg = _cfg()
        ctx.check("the right code registers: account stored", rc == 0 and cfg["account"] == "+15555550123")
        from halo_harness.remote.signal_config import remote_dir
        pin_file = remote_dir() / "registration-pin"
        pin = pin_file.read_text(encoding="utf-8").strip()
        ctx.check("a registration-lock PIN (8 digits) was set and stored", len(pin) == 8 and pin.isdigit()
                  and any("setPin" in c for c in env.calls()))
        ctx.check("the PIN is never printed", pin not in out + err)
        if os.name != "nt":
            ctx.check("the PIN file is 0600", (pin_file.stat().st_mode & 0o777) == 0o600)
    with Env("locked") as env:
        env.write_signal_json()
        rc, _, err = run(["register", "+15555550123", "--code", "123456"])
        ctx.check("a locked number points at --pin", rc == 1 and "--pin" in err)
        rc, _, _ = run(["register", "+15555550123", "--code", "123456", "--pin", "999999"])
        ctx.check("and --pin completes it", rc == 0)
    with Env():
        rc, _, err = run(["register", "+15555550123"])
        ctx.check("register before setup points at setup", rc == 1 and "halo remote signal setup" in err)


@test
def test_link_shows_the_uri_and_a_qr_then_stores_the_account(ctx: Ctx):
    with Env("ok") as env:
        env.write_signal_json()
        rc, out, err = run(["link", "--name", "Halo test"])
        ctx.check("the sgnl://linkdevice URI is printed as text", rc == 0 and "sgnl://linkdevice?uuid=FAKEUUID" in out)
        ctx.check("and as a QR code (block glyphs)", "\u2588" in out or "\u2584" in out)
        ctx.check("the device name reaches signal-cli", ["link", "-n", "Halo test"] == [c for c in env.calls() if "link" in c][-1][-3:])
        cfg = _cfg()
        ctx.check("account, linked model and own ACI are stored",
                  cfg["account"] == "+15555550123" and cfg["identity_model"] == "linked"
                  and cfg["own_aci"] == "00000000-0000-4000-8000-0000000000aa")
        rc, out, _ = run(["link", "--ascii"])
        ctx.check("--ascii draws the QR with #", "##" in out and "\u2588" not in out)
        rc, out, _ = run(["link", "--json"])
        ctx.check("--json prints one object", json.loads(out)["account"] == "+15555550123")
    with Env("noscan") as env:
        env.write_signal_json()
        rc, out, err = run(["link", "--timeout", "1"])
        ctx.check("no scan -> a timeout message, URI still shown, nothing stored",
                  rc == 1 and "timed out" in err and "sgnl://" in out and "account" not in _cfg())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
