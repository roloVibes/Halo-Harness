"""tests.test_remote_notify -- the transport seam (Halo 3.3.13.0 R3; remote/notify.py, remote/notify_sources.py,
remote/session_start.py, ext/remote.py, docs/REMOTE.md "Transports"):

1. a note is written only while a transport listens (and never with `remote.enabled` false, 3.3.13.1), read back in
   order after a cursor, kinds filtered, old ones gone;
2. the core's producers: the attention queue's cards (fleet/push.spool, `asks`, `remote.enabled` the switch), a
   supervisor goal that ends (`supervisor`), the steward's attention notes (`steward`, the first tick only remembers);
3. a session started for a transport: the request, the supervisor's answer (a fake spawn), the wait for its row;
4. `halo remote signal` is one line pointing at the pack; `halo remote transports`; `/remote` is the control socket.
Run: python -m tests.test_remote_notify"""
from __future__ import annotations

import io
import os
import sys
import tempfile
import time
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


class _Home:
    def __enter__(self):
        self.saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
        os.environ.pop("BRIDGE_STATE_DIR", None)
        os.environ["BRIDGE_TEST_HOME"] = tempfile.mkdtemp(prefix="remote-notify-")
        from halo_harness.config.paths import bridge_home
        self.state = bridge_home()
        return self

    def __exit__(self, *exc):
        for k, v in self.saved.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v
        return False


@test
def test_notes_only_while_a_transport_listens(ctx: Ctx):
    from halo_harness.remote import notify as N
    with _Home():
        ctx.check("nobody listens: nothing is written", not N.notify("asks", "a card") and not N.log_path().exists())
        N.listen("signal")
        ctx.check("the transport is named", N.listening() == ["signal"])
        rows, cur = N.since("")
        ctx.check("a first read starts at now", rows == [])
        ctx.check("a kind outside the list is not written", not N.notify("gossip", "x"))
        N.notify("asks", "card one", source="r1", session="s1")
        N.notify("supervisor", "goal done")
        rows, cur2 = N.since(cur)
        ctx.check(f"read back in order, got {rows}", [r["text"] for r in rows] == ["card one", "goal done"]
                  and rows[0]["session"] == "s1")
        ctx.check("nothing new after the cursor", N.since(cur2)[0] == [])
        ctx.check("kinds filter", [r["kind"] for r in N.since(cur, kinds=("supervisor",))[0]] == ["supervisor"])
        ctx.check("a heartbeat older than LISTEN_S is not listening", N.listening(now=time.time() + N.LISTEN_S + 5) == [])
        ctx.check("a note older than KEEP_S is not read", N.since(cur, now=time.time() + N.KEEP_S + 5)[0] == [])


@test
def test_remote_enabled_false_writes_no_note(ctx: Ctx):
    """3.3.13.1 (REVIEW #19, REMOTE-2): `notify()` wrote supervisor and steward notes with the switch off."""
    from halo_harness.remote import notify as N
    from halo_harness.theme import set_config_value
    with _Home():
        N.listen("signal")
        _rows, cur = N.since("")
        set_config_value("remote.enabled", False)
        ctx.check("remote.enabled false: nothing is written", not N.notify("supervisor", "goal done")
                  and not N.notify("steward", "a note") and N.since(cur)[0] == [])
        set_config_value("remote.enabled", True)
        ctx.check("back on: it writes again", N.notify("supervisor", "goal done") and len(N.since(cur)[0]) == 1)


@test
def test_the_cores_producers(ctx: Ctx):
    from halo_harness.remote import notify as N
    with _Home() as h:
        N.listen("signal")
        _rows, cur = N.since("")
        from halo_harness.fleet import push
        row = {"id": "permission:M:s2:p9", "kind": "permission", "harness": "M", "harness_name": "kali@lab",
               "session_id": "s2", "agent": "verifier", "what": "Permission: Bash", "detail": "make clean",
               "target": {"request_id": "p9"}}
        asks = {("M", "s2", "p9"): {"data": {"id": "p9", "name": "Bash", "input": {"command": "make clean"}}}}
        ctx.check("the hub is ready while a transport listens", push.ready(h.state))
        n = push.spool(h.state, [row, {**row, "id": "x", "local": True, "remote_attached": 1}], asks)
        got, cur = N.since(cur)
        ctx.check(f"one asks note, the attached one skipped, got {got}", n == 1 and len(got) == 1
                  and got[0]["kind"] == "asks" and got[0]["text"].startswith("[kali@lab · verifier]")
                  and "make clean" in got[0]["text"] and got[0]["session"] == "s2")
        from halo_harness.theme import set_config_value
        set_config_value("remote.enabled", False)
        ctx.check("remote.enabled false: the hub is not ready", not push.ready(h.state))
        set_config_value("remote.enabled", True)
        from halo_harness.supervise import queue
        g = queue.add(h.state, "tidy the docs", repo=str(h.state), kind="job")
        queue.set_state(h.state, g["id"], "done", "done", cost_usd=0.12)
        got, cur = N.since(cur)
        ctx.check(f"a goal that ends is a supervisor note, got {got}", got and got[-1]["kind"] == "supervisor"
                  and "tidy the docs" in got[-1]["text"] and "$0.12" in got[-1]["text"])
        from halo_harness.remote.notify_sources import Steward
        st = Steward(h.state)
        rows = [{"id": "n1", "attention": True, "stage": "note", "lines": ["the coder cannot fit", "it needs 30 GB"]}]
        st._marked = lambda: list(rows)
        ctx.check("the first tick only remembers", st.tick() == 0)
        rows.append({"id": "n2", "attention": True, "stage": "change", "lines": ["num_ctx put back"]})
        ctx.check("a new attention note is a steward note", st.tick() == 1
                  and N.since(cur)[0][-1]["text"].startswith("Steward: num_ctx put back"))


@test
def test_a_session_for_a_transport(ctx: Ctx):
    from halo_harness.remote import session_start as S
    with _Home() as h:
        folder = tempfile.mkdtemp(prefix="remote-work-")
        rid = S.request(folder, "mock/fake", "signal:00000000", h.state)
        spawned = []

        def spawn(cwd, model, state_dir):
            spawned.append((str(cwd), model))
            return {"session_id": "sid-1", "pid": 1, "cwd": str(cwd), "model": model, "log": "x.log"}
        answers = S.serve(h.state, spawn=spawn)
        ctx.check(f"the supervisor answers it with a spawn, got {answers}", answers and answers[0]["session_id"] == "sid-1"
                  and spawned == [(str(Path(folder).resolve()), "mock/fake")])
        entry, line = S.wait(rid, 2.0, h.state, live=lambda sid: {"session_id": sid} if sid == "sid-1" else None)
        ctx.check(f"the requester gets its row, got {entry} {line!r}", entry == {"session_id": "sid-1"})
        bad = S.request(str(Path(folder) / "nope"), "", "", h.state)
        S.serve(h.state, spawn=spawn)
        entry, line = S.wait(bad, 2.0, h.state, live=lambda sid: None)
        ctx.check(f"a folder that is not there is one line, got {line!r}", entry is None and "not a folder" in line)
        entry, line = S.wait(S.request(folder, "", "", h.state), 0.5, h.state, live=lambda sid: None)
        ctx.check("no supervisor answering is said", entry is None and "halo supervise" in line)


@test
def test_the_cli_lines(ctx: Ctx):
    with _Home():
        from halo_harness.remote.cli import cmd_remote
        err, out = io.StringIO(), io.StringIO()
        with redirect_stderr(err):
            rc = cmd_remote(["signal", "run"])
        ctx.check(f"halo remote signal is one line pointing at the pack, got {err.getvalue()!r}", rc == 2
                  and "the signal pack" in err.getvalue() and "halo pack install signal" in err.getvalue())
        with redirect_stdout(out):
            rc = cmd_remote(["transports"])
        ctx.check("halo remote transports", rc == 0 and "transports listening: none" in out.getvalue())
        from halo_harness.remote.status import chip, text
        ctx.check("/remote is the control socket's status", "control socket:" in text("") and "remote.enabled" in text(""))
        ctx.check("/remote signal says where it went", "signal pack" in text("signal pair"))
        ctx.check("no chip with nothing listening", chip() == "")
        from halo_harness.completion_cli import REMOTE_WORDS
        ctx.check("completion has no signal verbs", "signal" not in REMOTE_WORDS and "transports" in REMOTE_WORDS)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
