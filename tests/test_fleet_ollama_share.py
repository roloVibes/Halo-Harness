"""tests.test_fleet_ollama_share -- Halo 3.3.4.0 R2: the hub sees every
halo's calls (halo_harness/fleet/ollama_share.py). Two Halo homes on one
machine (tests/helpers/fleet_hub_rig.py: A runs the hub on 127.0.0.1:0, this
process is member B):

1. B's ledger lines for a host B does not serve reach A's ledger with
   `from` = B's name; the line for B's own loopback server stays on B;
2. `fleet.ollama.share: false` sends none; `true` sends B's own server's too;
3. the hub's append for two members: `read_calls` on the hub returns both
   members' lines beside its own, each with its `from`; the forwarder's
   cursor survives a rotation and never sends a line twice;
4. 3.3.4.0 R4: the hub's newest steward note reaches the member (hub-note.json).
Never a real server or a real model call.
Run: python -m tests.test_fleet_ollama_share
"""
from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.fleet_hub_rig import HubRig, wait_for  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()

REMOTE = {"name": "pc", "url": "http://192.0.2.10:11434"}
LOOPBACK = {"name": "default", "url": "http://127.0.0.1:11434"}


def _record(host: dict, model: str) -> None:
    from halo_harness.config.paths import bridge_home
    from halo_harness.ollama_steward import ledger
    ledger.record_call(bridge_home(), {"host": host, "model": model, "status": 200, "prompt_eval_count": 1200})


def _hub_lines(rig) -> list:
    from halo_harness.ollama_steward.ledger import read_calls
    return read_calls(rig.home_a)


class _Fast:
    def __enter__(self):
        from halo_harness.fleet import ollama_share
        self._saved = (ollama_share.FLUSH_S, ollama_share.CHECK_S)
        ollama_share.FLUSH_S, ollama_share.CHECK_S = 0.2, 0.05
        return self

    def __exit__(self, *exc):
        from halo_harness.fleet import ollama_share
        ollama_share.FLUSH_S, ollama_share.CHECK_S = self._saved


@test
def test_a_members_lines_reach_the_hubs_ledger_with_from_and_its_own_server_stays_home(ctx: Ctx):
    with _Fast(), HubRig() as rig:
        rig.join()
        _record(REMOTE, "qwen3.8:27b")
        _record(LOOPBACK, "small:1b")
        _controller, act = rig.session()
        wait_for(lambda: rig.member_session(act.session_id))
        got = wait_for(lambda: [x for x in _hub_lines(rig) if x.get("model") == "qwen3.8:27b"], 8)
        ctx.check(f"the call to the PC reached the hub's ledger, got {got}", bool(got))
        ctx.check(f"with from = B's name, got {[x.get('from') for x in got or []]}",
                  bool(got) and all(x.get("from") == "bob@member" for x in got))
        ctx.check("the line kept its fields", bool(got) and got[0].get("host") == REMOTE
                  and got[0].get("prompt_eval_count") == 1200 and got[0].get("status") == 200)
        time.sleep(0.6)
        ctx.check("the call to B's own loopback server stayed on B (auto)",
                  not [x for x in _hub_lines(rig) if x.get("model") == "small:1b"])
        _record(REMOTE, "second:7b")
        again = wait_for(lambda: [x for x in _hub_lines(rig) if x.get("model") == "second:7b"], 8)
        ctx.check("a later line follows on the next flush", bool(again))
        ctx.check("and the first one was sent once only",
                  len([x for x in _hub_lines(rig) if x.get("model") == "qwen3.8:27b"]) == 1)


@test
def test_the_hubs_steward_note_reaches_the_member(ctx: Ctx):
    """3.3.4.0 R4: the hub's newest steward note travels in the answer to the member's POST; the member keeps it
    (hub-note.json) and its TUI line reads "steward on <hub>: <first line>"."""
    from halo_harness.config.paths import bridge_home
    from halo_harness.ollama_steward import notes
    with _Fast(), HubRig() as rig:
        notes.append(rig.home_a, "note", "the 27B on pc spilled to the CPU while an image job held the card",
                     lines=["the 27B on pc spilled to the CPU while an image job held the card"], attention=True)
        rig.join()
        _record(REMOTE, "qwen3.8:27b")
        _controller, act = rig.session()
        wait_for(lambda: rig.member_session(act.session_id))
        got = wait_for(lambda: notes.hub_note(bridge_home()), 10)
        ctx.check(f"the member keeps the hub's note, got {got}", bool(got) and got["line"].startswith("the 27B on pc")
                  and got["attention"] is True)
        line = notes.member_line(got)
        ctx.check(f"the member's line names the hub, got {line!r}", line.startswith("steward on ") and "the 27B on pc" in line)


@test
def test_the_scope_off_sends_none_and_true_sends_the_own_server_too(ctx: Ctx):
    with _Fast(), HubRig() as rig:
        rig.set_b(**{"fleet.ollama.share": False})
        rig.join()
        _record(REMOTE, "off:1b")
        _controller, act = rig.session()
        wait_for(lambda: rig.member_session(act.session_id))
        time.sleep(1.2)
        ctx.check(f"fleet.ollama.share false: nothing reached the hub, got {_hub_lines(rig)}", not _hub_lines(rig))
        rig.set_b(**{"fleet.ollama.share": True})
        _record(LOOPBACK, "own:1b")
        got = wait_for(lambda: [x for x in _hub_lines(rig) if x.get("model") == "own:1b"], 8)
        ctx.check("fleet.ollama.share true: B's own server's call reaches the hub", bool(got))
        ctx.check("a line recorded while the scope was off is never sent later",
                  not [x for x in _hub_lines(rig) if x.get("model") == "off:1b"])


@test
def test_the_hub_keeps_two_members_lines_beside_its_own(ctx: Ctx):
    from halo_harness.fleet.ollama_share import accept, served_here, wanted
    from halo_harness.ollama_steward import ledger
    home = Path(tempfile.mkdtemp(prefix="l2_hub-")) / ".halo"
    ledger.append_lines(home, [ledger.blank_line(host=REMOTE, model="m", **{"from": None})])
    n1 = accept(home, "mac@book", [{"host": REMOTE, "model": "m", "from": "spoofed", "extra": "dropped"}])
    n2 = accept(home, "kali@vm", [{"host": REMOTE, "model": "m"}, "not a line"])
    rows = ledger.read_calls(home, host="pc")
    ctx.check(f"each member's lines appended, got {n1} {n2}", n1 == 1 and n2 == 1)
    ctx.check(f"read_calls returns the hub's own line and both members', got {[r.get('from') for r in rows]}",
              [r.get("from") for r in rows] == [None, "mac@book", "kali@vm"])
    ctx.check("the hub sets `from` itself and keeps only the ledger's fields",
              "extra" not in rows[1] and set(rows[1]) == set(ledger.FIELDS))
    ctx.check("the loopback rule", served_here("http://127.0.0.1:11434") and served_here("http://localhost:11434")
              and not served_here("http://192.0.2.10:11434"))
    ctx.check("auto: a remote host's line goes, the own server's does not, a line taken in as a hub never",
              wanted({"host": REMOTE}, "auto") and not wanted({"host": LOOPBACK}, "auto")
              and wanted({"host": LOOPBACK}, "all") and not wanted({"host": REMOTE}, "off")
              and not wanted({"host": REMOTE, "from": "someone@else"}, "all"))


class _Link:
    def __init__(self):
        self.sent = []

    def request(self, method, path, body):
        self.sent.extend(body.get("lines") or [])
        return {"ok": True}


@test
def test_the_cursor_survives_a_rotation_and_never_sends_twice(ctx: Ctx):
    from halo_harness.fleet import ollama_share
    from halo_harness.ollama_steward import ledger
    home = Path(tempfile.mkdtemp(prefix="l2_fwd-")) / ".halo"
    fwd = ollama_share.Forwarder({"hub_id": "hub-1"}, home=home)
    link = _Link()
    ledger.append_lines(home, [ledger.blank_line(host=REMOTE, model=f"a{i}", **{"from": None}) for i in range(3)])
    ctx.check("a forced tick sends the three lines", fwd.tick(link, "L", force=True) == 3)
    ctx.check("nothing new: a second tick sends none", fwd.tick(link, "L", force=True) == 0)
    ledger.append_lines(home, [ledger.blank_line(host=REMOTE, model="b0", **{"from": None})])
    path = ledger.traffic_path(home)
    path.replace(path.with_name(ledger.ROTATED_FILE))
    ledger.append_lines(home, [ledger.blank_line(host=REMOTE, model="c0", **{"from": None})])
    fwd.tick(link, "L", force=True)
    ctx.check(f"after a rotation: the old file's last line, then the new file's, got {[x['model'] for x in link.sent]}",
              [x["model"] for x in link.sent] == ["a0", "a1", "a2", "b0", "c0"])
    saved = ollama_share.MAX_LINES
    ollama_share.MAX_LINES = 2
    try:
        ledger.append_lines(home, [ledger.blank_line(host=REMOTE, model=f"d{i}", **{"from": None}) for i in range(3)])
        fwd.tick(link, "L", force=True)
        fwd.tick(link, "L", force=True)
    finally:
        ollama_share.MAX_LINES = saved
    ctx.check(f"a batch over the cap goes in two requests, none lost, got {[x['model'] for x in link.sent[5:]]}",
              [x["model"] for x in link.sent[5:]] == ["d0", "d1", "d2"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
