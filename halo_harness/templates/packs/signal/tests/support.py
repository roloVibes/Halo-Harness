"""tests.support -- the signal pack's test kit: a tiny runner, a scratch home, the stub transport, the fake clock and
the phone's side (envelopes as signal-cli writes them). Every id and number is fake (+1555 01xx numbers).

    test, TESTS = registry(); main(TESTS) -> exit code     @test def test_x(ctx): ctx.check(what, ok)
    scratch_home()                       BRIDGE_TEST_HOME a fresh folder unless the runner (halo pack test) set one
    StubTransport                        records every send, typing call, receipt and trust; .deliver(params)
    FakeClock, wait_for(cond), data_message(...), untrusted(...), reaction(...), sync_sent(...)
"""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
import traceback
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parent.parent
if str(PACK_ROOT) not in sys.path:
    sys.path.insert(0, str(PACK_ROOT))

ACI_A = "00000000-0000-4000-8000-000000000001"
ACI_B = "00000000-0000-4000-8000-000000000002"
NUM_A, NUM_B, ACCOUNT = "+15550100", "+15550101", "+15550199"
SAFETY = "11111 22222 33333 44444 55555 66666 77777 88888 99999 00000 11111 22222"


def scratch_home() -> str:
    if not os.environ.get("BRIDGE_TEST_HOME"):
        os.environ["BRIDGE_TEST_HOME"] = tempfile.mkdtemp(prefix="signal-pack-home-")
    os.environ.pop("BRIDGE_STATE_DIR", None)
    os.environ.setdefault("BRIDGE_TEST_NO_BACKGROUND_NET", "1")
    os.environ.setdefault("OLLAMA_HOST", "http://127.0.0.1:9")
    return os.environ["BRIDGE_TEST_HOME"]


scratch_home()  # before anything reads the state folder


class Ctx:
    def __init__(self) -> None:
        self.failures: list = []

    def check(self, what: str, ok) -> bool:
        if not ok:
            self.failures.append(what)
        return bool(ok)


def registry():
    tests: list = []

    def test(fn):
        tests.append(fn)
        return fn
    return test, tests


new_registry = registry  # the name the modules ported from Halo's own tests use


class Home:
    """A fresh BRIDGE_TEST_HOME for one block, the one before put back after."""

    def __init__(self) -> None:
        self.saved = os.environ.get("BRIDGE_TEST_HOME")
        self.path = tempfile.mkdtemp(prefix="signal-home-")
        os.environ["BRIDGE_TEST_HOME"] = self.path

    def __enter__(self) -> "Home":
        return self

    def __exit__(self, *exc) -> bool:
        if self.saved is None:
            os.environ.pop("BRIDGE_TEST_HOME", None)
        else:
            os.environ["BRIDGE_TEST_HOME"] = self.saved
        return False


def main(tests: list) -> int:
    scratch_home()
    failed = 0
    for fn in tests:
        ctx = Ctx()
        t0 = time.monotonic()
        try:
            fn(ctx)
        except Exception:
            ctx.failures.append("raised:\n" + traceback.format_exc())
        took = time.monotonic() - t0
        if ctx.failures:
            failed += 1
            print(f"[FAIL] {fn.__name__} ({took:.1f}s)")
            for f in ctx.failures:
                print(f"    - {f}")
        else:
            print(f"[PASS] {fn.__name__} ({took:.1f}s)")
    print(f"RESULT: {len(tests)} tests, {len(tests) - failed} passed, {failed} failed")
    return 1 if failed else 0


def wait_for(cond, timeout: float = 5.0, step: float = 0.02) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(step)
    return bool(cond())


class FakeClock:
    def __init__(self, start: float = None) -> None:
        self.now = time.time() if start is None else start
        self.mono = 1000.0

    def time(self) -> float:
        return self.now

    def monotonic(self) -> float:
        return self.mono

    def advance(self, s: float) -> None:
        self.now += s
        self.mono += s


class StubTransport:
    """The transport surface the bridge uses, recording everything; `deliver(params)` plays an inbound item."""

    def __init__(self) -> None:
        from halo_signal.typing_keeper import TypingKeeper
        self.sent, self.receipts, self.trusts, self.typing_calls = [], [], [], []
        self.identities: dict = {}
        self.files: dict = {}        # attachment id -> (bytes, content type)
        self.send_error = None
        self.sink = lambda item: None
        self.typing = TypingKeeper(self, 0.05)
        self._lock = threading.Lock()

    def set_sink(self, fn) -> None:
        self.sink = fn

    def start(self) -> "StubTransport":
        return self

    def stop(self) -> None:
        self.typing.stop_all()

    def deliver(self, params: dict) -> None:
        self.sink({"kind": "envelope", "envelope": params["envelope"], "exception": params.get("exception"),
                   "account": params.get("account")})

    def send(self, recipient, text="", *, attachment=None, styles=None, note_to_self=None):
        if self.send_error is not None:
            raise self.send_error
        with self._lock:  # signal-cli answers a send with its timestamp (3.3.13.1: a reaction names one)
            ts = 1_700_000_000_000 + len(self.sent)
            self.sent.append({"to": recipient, "text": text, "attachment": attachment, "styles": styles, "ts": ts})
        return {"timestamp": ts}

    def sent_ts(self, needle: str) -> int:
        """The sent timestamp of the first message holding `needle` (a card's, for a reaction on it)."""
        with self._lock:
            return next(s["ts"] for s in self.sent if needle in (s["text"] or ""))

    def texts(self, to=None) -> list:
        with self._lock:
            return [s["text"] for s in self.sent if to in (None, s["to"])]

    def send_typing(self, recipient, stop=False):
        with self._lock:
            self.typing_calls.append((recipient, stop))

    def send_receipt(self, recipient, timestamp, kind="read"):
        self.receipts.append((recipient, timestamp, kind))

    def safety_number(self, aci):
        return self.identities.get(aci)

    def trust(self, recipient, safety_number):
        self.trusts.append((recipient, safety_number))

    def take_attachments(self, attachments, want_text, inbox=None):
        text, got = None, []
        for a in attachments or []:
            data, ctype = self.files.get(a.get("id"), (b"", a.get("contentType")))
            if want_text and ctype == "text/x-signal-plain" and text is None:
                text = data.decode("utf-8")
            elif want_text and inbox is not None:
                Path(inbox).mkdir(parents=True, exist_ok=True)
                dest = Path(inbox) / f"{a['id']}-{a.get('filename') or 'file'}"
                dest.write_bytes(data)
                got.append({"path": str(dest), "content_type": ctype, "filename": a.get("filename") or "file",
                            "voice": str(ctype).startswith("audio/")})
        return text, got


def envelope(uuid: str, number=None, ts: int = 0, **body) -> dict:
    env = {"source": number or uuid, "sourceNumber": number, "sourceUuid": uuid, "sourceDevice": 1, "timestamp": ts}
    env.update(body)
    return {"envelope": env, "account": ACCOUNT}


def data_message(uuid: str, text, ts: int, number=None, attachments=None, group=None, reaction=None) -> dict:
    dm = {"timestamp": ts, "message": text, "attachments": attachments or []}
    if group:
        dm["groupInfo"] = {"groupId": group, "type": "DELIVER"}
    if reaction:
        dm["reaction"] = reaction
    return envelope(uuid, number, ts, dataMessage=dm)


def reaction(uuid: str, emoji: str, ts: int, number=None, target=None) -> dict:
    """`target`: the reacted-to message's sent timestamp (a card's: StubTransport.sent_ts)."""
    return data_message(uuid, None, ts, number, reaction={"emoji": emoji, "isRemove": False,
                                                          "targetSentTimestamp": ts - 1000 if target is None else target})


def untrusted(uuid: str, number=None, ts: int = 0) -> dict:
    p = envelope(uuid, number, ts)
    p["exception"] = {"message": f"Untrusted identity: {number or uuid}", "type": "UntrustedIdentityException"}
    return p


def sync_sent(own_uuid: str, text: str, ts: int) -> dict:
    sent = {"destinationUuid": own_uuid, "timestamp": ts, "message": text}
    return envelope(own_uuid, ACCOUNT, ts, syncMessage={"sentMessage": sent})


def now_ms() -> int:
    return int(time.time() * 1000)
