"""tests.helpers.fake_signal_cli -- a stand-in for `signal-cli ... jsonRpc`.

Run as a script (the transport spawns `[sys.executable, <this file>, <the real
signal-cli flags>, --fake-ctl CTL, --fake-log LOG]`; `--fake-listen PORT
--fake-portfile F` makes it a one-client TCP daemon instead): newline JSON-RPC
2.0 over stdio, every request logged to LOG, orders read from CTL (a JSON-lines
file the test appends to; only lines added after the child started count):

    {"op": "emit", "params": {...}}      a `receive` notification (held until
                                         subscribeReceive in manual mode)
    {"op": "identity", "uuid", "number", "safetyNumber", "trust"}
    {"op": "untrusted", "uuid", "number", "held_text"}   the untrusted-identity
                                         notification; `trust` then redelivers
    {"op": "fail", "method", "code", "times", "data"}    error replies
    {"op": "exit"}                       the child dies (a crash)

Imported by tests: `FakeSignal` (files + config) and the envelope builders, whose
key names follow SIGNAL-RESEARCH.md section 3. Every id and number is fake.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

ACCOUNT = "+15555550123"


def envelope(uuid: str, number=None, ts: int = 0, **body) -> dict:
    env = {"source": number or uuid, "sourceNumber": number, "sourceUuid": uuid, "sourceName": "name",
           "sourceDevice": 1, "timestamp": ts, "serverReceivedTimestamp": ts + 5, "serverDeliveredTimestamp": ts + 9}
    env.update(body)
    return {"envelope": env, "account": ACCOUNT}


def data_message(uuid: str, text: str, ts: int, number=None, attachments=None, group=None) -> dict:
    dm = {"timestamp": ts, "message": text, "expiresInSeconds": 0, "viewOnce": False, "mentions": [],
          "attachments": attachments or [], "contacts": []}
    if group:  # a message posted in a Signal group (JsonDataMessage.groupInfo)
        dm["groupInfo"] = {"groupId": group, "groupName": "group", "revision": 1, "type": "DELIVER"}
    return envelope(uuid, number, ts, dataMessage=dm)


def attachment(att_id: str, content_type: str, size: int = 10) -> dict:
    return {"contentType": content_type, "filename": None, "id": att_id, "size": size}


def sync_sent(own_uuid: str, text: str, ts: int, dest_uuid=None, group=None) -> dict:
    sent = {"destination": None, "destinationUuid": dest_uuid or own_uuid, "timestamp": ts, "message": text,
            "expiresInSeconds": 0, "viewOnce": False}
    if group:
        sent["groupInfo"] = {"groupId": group, "groupName": "group", "revision": 1, "type": "DELIVER"}
    return envelope(own_uuid, ACCOUNT, ts, syncMessage={"sentMessage": sent})


def untrusted_notice(uuid: str, number=None, ts: int = 0) -> dict:
    params = envelope(uuid, number, ts)
    params["exception"] = {"message": f"Untrusted identity: {number or uuid}", "type": "UntrustedIdentityException"}
    return params


# ---- the child process ------------------------------------------------------------------
class _Child:
    def __init__(self, args: list) -> None:
        self.opts = {"-a": "", "--receive-mode": "on-start", "--fake-ctl": "", "--fake-log": "", "--fake-listen": "",
                     "--fake-portfile": ""}
        self.sink_out = sys.stdout
        i = 0
        while i < len(args):
            if args[i] in self.opts or args[i] in ("--trust-new-identities", "-d"):
                self.opts[args[i]] = args[i + 1] if i + 1 < len(args) else ""
                i += 1
            i += 1
        self.out_lock = threading.Lock()
        self.subscribed = self.opts["--receive-mode"] != "manual"
        self.held: list = []
        self.fails: list = []
        self.identities: dict = {}
        self.untrusted: dict = {}
        self.log(argv=args)

    def log(self, **rec) -> None:
        if self.opts["--fake-log"]:
            with open(self.opts["--fake-log"], "a", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")

    def out(self, obj: dict) -> None:
        with self.out_lock:
            self.sink_out.write(json.dumps(obj) + "\n")
            self.sink_out.flush()

    def notify(self, params: dict) -> None:
        if not self.subscribed:
            self.held.append(params)
            return
        if self.opts["--receive-mode"] == "manual":
            params = {"subscription": 0, "result": params}
        self.out({"jsonrpc": "2.0", "method": "receive", "params": params})

    def control(self, op: dict) -> None:
        kind = op.get("op")
        if kind == "emit":
            self.notify(op["params"])
        elif kind == "identity":
            self.identities[op["uuid"]] = {"number": op.get("number"), "uuid": op["uuid"], "fingerprint": "ab" * 10,
                                           "safetyNumber": op["safetyNumber"], "scannableSafetyNumber": "c2Fm",
                                           "trustLevel": op.get("trust", "UNTRUSTED"), "addedTimestamp": 1}
        elif kind == "untrusted":
            self.untrusted[op["uuid"]] = op.get("held_text")
            self.notify(untrusted_notice(op["uuid"], op.get("number"), int(time.time() * 1000)))
        elif kind == "fail":
            self.fails.append(dict(op))
        elif kind == "exit":
            os._exit(3)

    def watch_ctl(self) -> None:
        path = self.opts["--fake-ctl"]
        if not path:
            return
        pos = os.path.getsize(path) if os.path.exists(path) else 0
        while True:
            time.sleep(0.01)
            try:
                with open(path, "rb") as f:
                    f.seek(pos)
                    data = f.read()
            except OSError:
                continue
            cut = data.rfind(b"\n")
            if cut < 0:
                continue
            pos += cut + 1
            for line in data[:cut + 1].splitlines():
                if line.strip():
                    self.control(json.loads(line.decode("utf-8")))

    def failure(self, method: str):
        for f in self.fails:
            if f["method"] == method and f.get("times", 1) > 0:
                f["times"] = f.get("times", 1) - 1
                return {"code": f["code"], "message": f"injected {f['code']}", "data": f.get("data")}
        return None

    def call(self, method: str, params: dict):
        err = self.failure(method)
        if err:
            return None, err
        if method == "subscribeReceive":
            self.subscribed = True
            held, self.held = self.held, []
            threading.Timer(0.02, lambda: [self.notify(p) for p in held]).start()
            return 0, None
        if method == "send":
            return {"timestamp": int(time.time() * 1000), "results": [{"type": "SUCCESS"}]}, None
        if method in ("sendTyping", "sendReceipt"):
            return {}, None
        if method == "listIdentities":
            want = params.get("number")
            return [v for k, v in self.identities.items() if want in (None, k, v.get("number"))], None
        if method == "trust":
            uuid = params.get("recipient")
            ident = self.identities.get(uuid)
            given = params.get("verifiedSafetyNumber")
            if ident and "".join(str(given).split()) != "".join(ident["safetyNumber"].split()):
                return None, {"code": -1, "message": "Invalid safety number"}
            if ident:
                ident["trustLevel"] = "TRUSTED_VERIFIED"
            held = self.untrusted.pop(uuid, None)
            if held:
                threading.Timer(0.05, lambda: self.notify(
                    data_message(uuid, held, int(time.time() * 1000)))).start()
            return {}, None
        if method in ("version", "submitRateLimitChallenge"):
            return {"version": "0.14.9"}, None
        return None, {"code": -32601, "message": f"Method not found: {method}"}

    def serve(self, rfile=None) -> None:
        for raw in rfile or sys.stdin:
            if not raw.strip():
                continue
            req = json.loads(raw)
            self.log(method=req.get("method"), params=req.get("params"))
            result, error = self.call(req["method"], req.get("params") or {})
            reply = {"jsonrpc": "2.0", "id": req.get("id")}
            reply.update({"error": error} if error else {"result": result})
            self.out(reply)

    def run(self) -> None:
        threading.Thread(target=self.watch_ctl, daemon=True).start()
        if not self.opts["--fake-listen"]:
            self.serve()
            return
        import socket
        srv = socket.socket()
        srv.bind(("127.0.0.1", int(self.opts["--fake-listen"])))
        srv.listen(1)
        Path(self.opts["--fake-portfile"]).write_text(str(srv.getsockname()[1]), encoding="utf-8")
        while True:  # a daemon: one client at a time, the next after a disconnect
            conn, _ = srv.accept()
            self.sink_out = conn.makefile("w", encoding="utf-8")
            try:
                self.serve(conn.makefile("r", encoding="utf-8"))
            except OSError:
                pass
            conn.close()


# ---- test-side handle ---------------------------------------------------------------------
class FakeSignal:
    """Files and config for one fake signal-cli; `config()` is a signal.json dict."""

    def __init__(self, root=None) -> None:
        self.root = Path(root or tempfile.mkdtemp(prefix="fake-signal-"))
        self.ctl = self.root / "ctl.jsonl"
        self.log = self.root / "log.jsonl"
        self.data_dir = self.root / "signal-cli"
        self.ctl.write_text("", encoding="utf-8")
        self.log.write_text("", encoding="utf-8")

    def config(self, **over) -> dict:
        cfg = {"binary": [sys.executable, str(Path(__file__).resolve())], "account": ACCOUNT,
               "data_dir": str(self.data_dir), "receive_mode": "manual", "transport": "stdio",
               "extra_args": ["--fake-ctl", str(self.ctl), "--fake-log", str(self.log)]}
        cfg.update(over)
        return cfg

    def order(self, **op) -> None:
        with open(self.ctl, "a", encoding="utf-8") as f:
            f.write(json.dumps(op) + "\n")

    def emit(self, params: dict) -> None:
        self.order(op="emit", params=params)

    def records(self) -> list:
        out = []
        for line in self.log.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append(json.loads(line))
        return out

    def requests(self, method: str = None) -> list:
        rows = [r for r in self.records() if "method" in r]
        return [r for r in rows if method is None or r["method"] == method]

    def argvs(self) -> list:
        return [r["argv"] for r in self.records() if "argv" in r]


if __name__ == "__main__":
    _Child(sys.argv[1:]).run()
