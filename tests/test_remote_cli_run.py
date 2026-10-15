"""tests.test_remote_cli_run -- Halo 2.0.9 round 4: `halo remote signal run |
status | off | on | pair | peers | unpair | reverify`. The bridge runs for
real in a thread over a stub transport; the kill switch is the stop file the
bridge polls; pairing runs through the same pending.json / peers.json files
the bridge uses."""
from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.cli_rig import Env, run
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials
from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.signal_rig import ACI_A, ACI_B, SAFETY_A, SAFETY_B, StubTransport, wait_for

ensure_default_provider_credentials()
test, TESTS = new_registry()


def _enable(value=True) -> None:
    from halo_harness.theme import set_config_value
    set_config_value("remote.signal.enabled", value)
    set_config_value("remote.enabled", True)  # 3.0.5.0: the Signal bridge's own switch (sockets: fleet.enabled)


@test
def test_run_status_off_on_with_a_real_bridge_loop(ctx: Ctx):
    from halo_harness.remote import bridge_state as BS, cli_run
    with Env() as env:
        ctx.check("before anything: state off", BS.read()["state"] == "off")
        rc, out, err = run(["run"])
        ctx.check("run with no account says what to do", rc == 1 and "halo remote signal setup" in err)
        env.write_signal_json(account="+15555550123")
        rc, out, _ = run(["run"])
        ctx.check("run while remote.signal.enabled is false does not start (exit 0)", rc == 0 and "is false" in out)
        from halo_harness.theme import set_config_value
        set_config_value("remote.signal.enabled", True)
        rc, out, _ = run(["run"])
        ctx.check("3.0.5.0: run while remote.enabled is false does not start either (exit 0)",
                  rc == 0 and "remote.enabled is false, so the Signal bridge is not started" in out)
        _enable()
        tr = StubTransport()
        saved, cli_run.make_transport = cli_run.make_transport, lambda cfg: tr
        result = {}
        # not run(): redirect_stdout is process-wide, so the bridge thread prints with --json (silent) instead
        t = threading.Thread(target=lambda: result.update(rc=cli_run.cmd_run(["--json"])), daemon=True)
        try:
            t.start()
            ctx.check("the bridge writes its pulse (starting)", wait_for(lambda: BS.read()["running"], 5.0))
            ctx.check("and the transport was started", wait_for(lambda: tr.started, 5.0))
            tr.sink({"kind": "notice", "name": "connected"})
            ctx.check("a connected notice moves the pulse to connected", wait_for(lambda: BS.read()["state"] == "connected", 5.0))
            tr.sink({"kind": "notice", "name": "rate_limited", "retry_after": 600, "token": "tok"})
            ctx.check("a rate limit shows as rate-limited with the pause",
                      wait_for(lambda: BS.read()["state"] == "rate-limited" and BS.read()["until"] > time.time() + 500, 5.0))
            rc, out, err = run(["run"])
            ctx.check("a second run sees the first", rc == 1 and "already running" in err)
            rc, out, _ = run(["status", "--json"])
            st = json.loads(out)
            ctx.check("status --json: bridge state, enabled, account, version pin",
                      st["bridge"]["state"] == "rate-limited" and st["enabled"] is True and st["account"] == "+15555550123"
                      and st["pinned_version"] == "0.14.9" and st["peers"] == 0 and st["signal_cli_version"] == "0.14.9")
            rc, out, _ = run(["status"])
            ctx.check("status text names the bridge and the account", "rate-limited" in out and "+15555550123" in out)
            rc, out, _ = run(["off", "--json"])
            res = json.loads(out)
            ctx.check("off stops the running bridge through the stop file", rc == 0 and res["was_running"] and res["stopped"])
            ctx.check("the bridge thread ended and the transport was stopped", wait_for(lambda: not t.is_alive(), 5.0))
            ctx.check("the pulse says stopped", BS.read()["state"] == "stopped")
            ctx.check("the stop file was cleared", not BS.stop_requested())
            from halo_harness.theme import get_config_value
            ctx.check("remote.signal.enabled is false", get_config_value("remote.signal.enabled", True) is False)
            rc, out, _ = run(["run"])
            ctx.check("a later run is a no-op until `on`", rc == 0 and "is false" in out)
            rc, out, _ = run(["on"])
            ctx.check("`on` sets it back", rc == 0 and get_config_value("remote.signal.enabled", False) is True)
            rc, out, _ = run(["off"])
            ctx.check("off with no bridge says so", rc == 0 and "No bridge was running" in out)
        finally:
            cli_run.make_transport = saved
            BS.request_stop()
            t.join(5.0)
            BS.clear_stop()


@test
def test_state_file_reads_a_dead_process_as_stopped(ctx: Ctx):
    from halo_harness.remote import bridge_state as BS
    with Env():
        ctx.check("a pulse of a pid that is gone reads stopped and not running",
                  (BS.BridgeState(pid=2 ** 22 + 12345).write("connected"), BS.read()["state"], BS.read()["running"]) == (None, "stopped", False))
        BS.BridgeState().write("connected")
        ctx.check("a live pid reads as written", BS.read()["state"] == "connected")
        ctx.check("rate-limited past its deadline reads connected",
                  (BS.BridgeState().write("rate-limited", 1.0), BS.read()["state"]) == (None, "connected"))


class _Capture:
    """Replaces cli_pair.Pairing: records the approval code and finishes the pairing like the bridge would."""
    last_code = None


def _patched_pairing(tr):
    from halo_harness.remote import cli_pair
    from halo_harness.remote.pairing import Pairing

    class Spy(Pairing):
        def approve(self, aci):
            ap = super().approve(aci)
            _Capture.last_code = ap.code

            def finish():
                time.sleep(0.4)
                self.service(tr)
                self.redeem(aci, ap.code, "+15555550101")
            threading.Thread(target=finish, daemon=True).start()
            return ap
    saved, cli_pair.Pairing = cli_pair.Pairing, Spy
    return cli_pair, saved


@test
def test_pair_lists_requests_approves_and_shows_the_secret_once_paired(ctx: Ctx):
    from halo_harness.remote import signing
    from halo_harness.remote.pairing import Pairing
    with Env():
        rc, out, _ = run(["pair"])
        ctx.check("no requests -> instructions for the phone", rc == 0 and "send any message" in out)
        p = Pairing()
        p.note_contact(ACI_A, "+15555550101", SAFETY_A)
        p.note_contact(ACI_B, None, SAFETY_B)
        p.add_notice("rate_limited", "", "Signal rate limit: sending paused for 60 s.")
        rc, out, _ = run(["pair"])
        ctx.check("requests are numbered with the ACI prefix and the grouped safety number",
                  "1  00000000" in out and "2  00000000" in out and SAFETY_A in out and "--approve" in out)
        ctx.check("notices are shown", "notice: Signal rate limit" in out)
        ctx.check("and cleared", p.notices() == [])
        rc, out, _ = run(["pair", "--json"])
        ctx.check("--json lists the requests", [r["index"] for r in json.loads(out)["pending"]] == [1, 2])
        rc, _, err = run(["pair", "--approve", "9"])
        ctx.check("an unknown request is an error", rc == 1 and "No contact request" in err)
        tr = StubTransport()
        tr.identities[ACI_A] = SAFETY_A
        cli_pair, saved = _patched_pairing(tr)
        try:
            rc, out, err = run(["pair", "--approve", "1", "--wait", "10", "--ascii"])
        finally:
            cli_pair.Pairing = saved
        code = _Capture.last_code
        ctx.check("approve prints the six-digit code and the phone instruction", rc == 0 and f"{code}" in out and "send exactly this code" in out)
        peer = Pairing().peer(ACI_A)
        ctx.check("then, once the phone redeemed it, the phrase (32 words) and the link", peer is not None
                  and out.count("halo-remote://pair?") >= 1 and len(signing.secret_to_phrase(bytes.fromhex(peer["signing"]["secret_hex"])).split()) == 32
                  and signing.secret_to_phrase(bytes.fromhex(peer["signing"]["secret_hex"])) in out)
        ctx.check("with a QR code under it (ASCII form here)", "##" in out)
        ctx.check("the trust step ran with the safety number", tr.trusts == [(ACI_A, "".join(SAFETY_A.split()))])
        rc, out, _ = run(["pair", "--approve", ACI_B[:12], "--wait", "0", "--json"])
        res = json.loads(out)
        ctx.check("approve by ACI prefix, --json, no waiting: code returned, not yet paired",
                  rc == 0 and len(res["code"]) == 6 and res["paired"] is False and res["trusted"] is False)


@test
def test_peers_unpair_reverify_never_print_secrets(ctx: Ctx):
    from halo_harness.remote.pairing import Pairing
    from tests.helpers.signal_rig import pair_peer
    with Env():
        p = Pairing(transport=StubTransport())
        secret = pair_peer(p, ACI_A, "+15555550101", SAFETY_A)
        pair_peer(p, ACI_B, None, SAFETY_B, signed=False)
        rc, out, _ = run(["peers"])
        ctx.check("peers lists both with signed / unsigned", rc == 0 and "signed" in out and "unsigned" in out and "+15555550101" in out)
        rc, jout, _ = run(["peers", "--json"])
        ctx.check("neither the table nor the JSON carries a signing secret",
                  secret.hex() not in out + jout and "secret" not in jout and len(json.loads(jout)["peers"]) == 2)
        p.block(ACI_A, SAFETY_B)
        rc, out, _ = run(["peers"])
        ctx.check("a blocked peer says reverify", "BLOCKED" in out)
        rc, out, err = run(["reverify", "00000000-0000-4000-8000-00000000000"])
        ctx.check("an ambiguous prefix asks for more characters", rc == 1 and "matches 2" in err)
        rc, out, _ = run(["reverify", ACI_A])
        ctx.check("reverify queues the trust step for the running bridge", rc == 0 and "Queued" in out)
        tr = StubTransport()
        Pairing().service(tr)
        ctx.check("the bridge's tick finishes it", tr.trusts == [(ACI_A, "".join(SAFETY_B.split()))]
                  and not Pairing().peer(ACI_A)["blocked_until_reverified"])
        rc, out, _ = run(["unpair", ACI_B, "--json"])
        ctx.check("unpair by (full) id", rc == 0 and json.loads(out)["unpaired"] == ACI_B[:8] and not Pairing().is_paired(ACI_B))
        rc, _, err = run(["unpair", "ffffffff"])
        ctx.check("an unknown prefix is an error", rc == 1 and "No paired phone" in err)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
