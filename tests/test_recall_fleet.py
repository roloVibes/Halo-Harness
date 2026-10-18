"""tests.test_recall_fleet -- Halo 3.1.2.0 R3: recall across the fleet
(halo_harness/recall_fleet.py, halo_harness/fleet/hub_recall.py, the
`recall` fleet command and the hub's routes).

No embedding model is ever called: `recall_fleet.SEARCH` is replaced with a
fake keyed by each home, so a hit carries its own excerpt and type. Two
parts:

1. `fan_out` / `merged` over a FakeState: the merge by score, each hit
   labelled with its harness, an offline member skipped, one with no live
   session noted, a member that times out, one that refuses (share off);
2. over tests/helpers/fleet_hub_rig.py's two homes: home B answers the real
   `recall` command from its own index through control.py, the hub merges it
   with home A's, `fleet.recall.share: false` keeps B out, `fleet.recall.hide`
   drops a kind, and B's journal gets the `recall_asked` line.

Run: python -m tests.test_recall_fleet
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def hit(score, title, kind="memory", excerpt="", mtype=None):
    h = {"id": f"/x/{title}.md", "score": score, "title": title, "kind": kind, "excerpt": excerpt or title}
    if mtype:
        h["type"] = mtype
    return h


class FakeState:
    """Enough of hub_state for fan_out / merged: a view and a commands.send."""

    def __init__(self, harnesses, answers, home, name="hub"):
        self._harnesses = harnesses
        self._answers = answers  # harness id -> (status, body) | ("slow", seconds)
        self.home = home
        self.name = name
        self.sent = []
        self.commands = self

    def view(self):
        return {"harnesses": self._harnesses}

    def send(self, hid, sid, cmd, fields, *, by, wait_s=5.0):
        self.sent.append((hid, cmd, dict(fields), by))
        ans = self._answers.get(hid)
        if isinstance(ans, tuple) and ans and ans[0] == "slow":
            time.sleep(min(ans[1], wait_s + 0.5))
            return 504, {"error": "no answer yet"}
        return ans or (504, {"error": "no answer yet"})


@test
def test_fan_out_merges_labels_and_marks_each_members_state(ctx: Ctx):
    import tempfile
    from halo_harness import recall_fleet as RF
    from halo_harness.fleet import hub_recall as HR
    home = Path(tempfile.mkdtemp(prefix="recall-local-"))
    RF.SEARCH = lambda q, k, h: [hit(0.95, "local-top"), hit(0.40, "local-low")]
    try:
        harnesses = [
            {"id": "A", "name": "hub", "local": True},
            {"id": "B", "name": "kali", "online": True, "sessions": [{"session_id": "s-b", "kind": "tui"}]},
            {"id": "C", "name": "box", "online": True, "sessions": [{"session_id": "s-c", "kind": "tui"}]},
            {"id": "D", "name": "away", "online": False, "sessions": [{"session_id": "s-d", "kind": "tui"}]},
            {"id": "E", "name": "bare", "online": True, "sessions": []},
            {"id": "F", "name": "mute", "online": True, "sessions": [{"session_id": "s-f", "kind": "tui"}]},
        ]
        answers = {
            "B": (200, {"result": {"hits": [{"score": 0.99, "title": "b-top", "kind": "memory", "excerpt": "from kali"},
                                            {"score": 0.20, "title": "b-low", "kind": "session", "excerpt": "old"}]}}),
            "C": (403, {"error": "box does not share its recall (fleet.recall.share: false)"}),
            "F": ("slow", 9.0),
        }
        state = FakeState(harnesses, answers, home)
        hub = type("H", (), {"state": state, "home": home})()
        out = HR.merged(hub, "the query", k=5, by="hub", wait_s=0.4)
        titles = [h["title"] for h in out["hits"]]
        ctx.check(f"hits merge best-first, got {titles}", titles == ["b-top", "local-top", "local-low", "b-low"])
        ctx.check("each hit is labelled with its harness",
                  {h["title"]: h["harness"] for h in out["hits"]}["b-top"] == "kali"
                  and {h["title"]: h["harness"] for h in out["hits"]}["local-top"] == "hub")
        ctx.check("an excerpt is capped at 300 chars", all(len(h["excerpt"]) <= 300 for h in out["hits"]))
        rows = {r["name"]: r for r in out["harnesses"]}
        ctx.check(f"B answered two, got {rows['kali']}", rows["kali"]["state"] == "answered" and rows["kali"]["hits"] == 2)
        ctx.check("the sharing-off member is not_shared", rows["box"]["state"] == "not_shared" and "share" in rows["box"]["note"])
        ctx.check("the offline member is skipped with no command sent",
                  rows["away"]["state"] == "offline" and not any(s[0] == "D" for s in state.sent))
        ctx.check("the member with no session is noted", rows["bare"]["state"] == "no_session")
        ctx.check("the slow member times out", rows["mute"]["state"] == "timeout")
        ctx.check("the local harness heads the list and shares its own hits", out["harnesses"][0]["local"]
                  and out["harnesses"][0]["hits"] == 2)
    finally:
        RF.SEARCH = None


@test
def test_hide_and_share_off_on_a_members_answer(ctx: Ctx):
    import tempfile
    from halo_harness import recall_fleet as RF
    from halo_harness.fleet import identity
    home = Path(tempfile.mkdtemp(prefix="recall-ans-")) / ".halo"
    home.mkdir(parents=True)
    saved = identity.home
    identity.home = lambda: home
    RF.SEARCH = lambda q, k, h: [hit(0.9, "a-memory", "memory"), hit(0.8, "a-session", "session"),
                                 hit(0.7, "a-feedback", "memory", mtype="feedback")]
    try:
        import json
        (home / "config.json").write_text(json.dumps({"fleet": {"name": "kali", "recall": {"hide": ["session", "feedback"]}}}),
                                          encoding="utf-8")
        identity.forget_cache()
        out = RF.answer({"query": "x", "k": 8}, by="alice", hub="hub-a")
        ctx.check(f"the session and the feedback kind are hidden, got {[h['title'] for h in out['hits']]}",
                  [h["title"] for h in out["hits"]] == ["a-memory"] and out["hidden"] == 2)
        from halo_harness.fleet import journal
        rows = [r for r in journal.read(home) if r.get("kind") == "recall_asked"]
        ctx.check(f"a journal line records the ask, got {rows}",
                  len(rows) == 1 and rows[0]["by"] == "alice" and rows[0]["hub"] == "hub-a"
                  and rows[0]["hits"] == 1 and rows[0]["hidden"] == 2 and rows[0]["query"] == "x")
        (home / "config.json").write_text(json.dumps({"fleet": {"name": "kali", "recall": {"share": False}}}),
                                          encoding="utf-8")
        identity.forget_cache()
        raised = False
        try:
            RF.answer({"query": "x", "k": 8}, by="alice", hub="hub-a")
        except RF.Shut as e:
            raised = "recall" in str(e)
        ctx.check("share: false makes the member refuse", raised)
    finally:
        RF.SEARCH = None
        identity.home = saved
        identity.forget_cache()


@test
def test_over_two_homes_the_hub_merges_the_members_own_index(ctx: Ctx):
    from halo_harness import recall_fleet as RF
    from halo_harness.fleet import journal
    from halo_harness.fleet.hub_recall import merged
    from tests.helpers.fleet_hub_rig import HubRig, wait_for
    from tests.helpers.mission_seed import fleet

    def search(q, k, h):
        p = str(h)
        if "fleet-a" in p:  # the hub's own index
            return [hit(0.5, "hub-note", "memory", "a note on the hub")]
        return [hit(0.97, "kali-top", "memory", "how to fix the bash tool"),
                hit(0.30, "kali-old", "session", "an old session")]
    RF.SEARCH = search
    try:
        with HubRig() as rig:
            fleet(rig, **{"fleet.allow_control": "all"})
            wait_for(lambda: rig.member_session_online("fakesession0000000000000000000001"), 20.0)
            out = wait_for(lambda: (lambda o: o if any(h["harness"] == "bob@member" for h in o["hits"]) else None)(
                merged(rig.hub, "fix the bash tool", k=5, by="alice@hub")), 20.0)
            ctx.check("the hub asked B and merged its hits with its own", out is not None)
            titles = [(h["harness"], h["title"]) for h in out["hits"]]
            ctx.check(f"B's top hit outranks the hub's, each labelled, got {titles}",
                      titles[0] == ("bob@member", "kali-top") and ("alice@hub", "hub-note") in titles)
            rows = {r["name"]: r for r in out["harnesses"]}
            ctx.check("B answered from its own index", rows["bob@member"]["state"] == "answered" and rows["bob@member"]["hits"] == 2)
            from halo_harness.config.paths import bridge_home
            jrows = [r for r in journal.read(bridge_home()) if r.get("kind") == "recall_asked"]
            ctx.check(f"B logged the ask in its own journal, got {jrows[-1:]}",
                      jrows and jrows[-1]["hits"] == 2 and jrows[-1]["query"] == "fix the bash tool")
            rig.set_b(**{"fleet.recall.share": False})
            off = wait_for(lambda: (lambda o: o if {r["name"]: r for r in o["harnesses"]}["bob@member"]["state"] == "not_shared"
                                    else None)(merged(rig.hub, "fix the bash tool", k=5, by="alice@hub")), 20.0)
            ctx.check("with share off, B is not_shared and contributes nothing",
                      off is not None and not any(h["harness"] == "bob@member" for h in off["hits"]))
    finally:
        RF.SEARCH = None


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="recall fleet tests"))
