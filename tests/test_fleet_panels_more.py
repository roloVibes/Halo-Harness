"""tests.test_fleet_panels_more -- Halo 3.0.5.0 "Fleet" round R4, the rest of
the panels' backend: conflicts (two harnesses editing one file through the
feed tap, two sessions of one harness, one session never), the health subset
(read-only, cached 60 s, a member's through `status` + `doctor`), and the
digest computed in code (per harness: sessions, cost, decisions and by whom,
files, errors, hand-offs). Companion of tests/test_fleet_panels_api.py.

Run: python -m tests.test_fleet_panels_more
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
NOW = time.time()


def _wait(fn, timeout: float = 15.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        got = fn()
        if got:
            return got
        time.sleep(0.2)
    return None


@test
def test_conflicts_two_sessions_of_one_harness_but_never_one_session(ctx: Ctx):
    from halo_harness.fleet import conflicts
    proj = {"root": "/home/kali/shop", "repo": "shop"}
    view = {"harnesses": [{"id": "M", "name": "kali@lab", "sessions": [
        {"session_id": "s1", "project": proj, "agents": [{"agent_id": "main", "current": "Edit: /home/kali/shop/src/a.py"},
                                                         {"agent_id": "x2", "current": "Write: src/a.py"}]},
        {"session_id": "s2", "project": proj, "agents": [{"agent_id": "main", "current": "Edit: ./src/a.py"}]}]}]}
    t = conflicts.Touches()
    new = conflicts.note_view(t, view)
    ctx.check(f"three agents noted on the repo-relative path, got {new}", sorted(x[3] for x in new) == ["src/a.py"] * 3)
    found = conflicts.find(view, t, [])
    pairs = sorted(tuple(sorted((c["a"]["session_id"], c["b"]["session_id"]))) for c in found)
    ctx.check(f"s1 x s2 twice (two agents in s1), never s1 x s1, got {pairs}", pairs == [("s1", "s2"), ("s1", "s2")])
    ctx.check("a truncated label is never a file", conflicts.edited("Edit: /very/long/path/that/was/cut...") is None)


@test
def test_a_conflict_across_two_harnesses_is_found_listed_and_raised(ctx: Ctx):
    from halo_harness.fleet import journal
    from halo_harness.fleet.identity import harness
    from tests.helpers.studio_fleet_member import REVIEWER
    from tests.helpers.studio_fleet_rig import MEMBER, MEMBER_SID, StudioFleetRig
    with StudioFleetRig() as rig:
        a = rig.agent("Implement")
        rig.api("GET", "fleet/attention")  # the watcher runs, its tap is on the feed
        rig.server.events.publish({"session_id": rig.act.session_id, "harness": harness()["id"], "event": "agent_state",
                                   "agent_id": a["agent_id"], "ts": time.time(),
                                   "data": {**a, "current": f"Edit: {rig.proj / 'basket.py'}"}})
        rig.hub.state.frames(MEMBER, {"link": "rig-link", "frames": [{"session_id": MEMBER_SID, "event": "agent_state",
                                                                     "agent_id": REVIEWER["agent_id"], "ts": time.time(),
                                                                     "data": {**REVIEWER, "state": "running",
                                                                              "current": "Edit: /home/kali/shop/basket.py"}}]})
        got = _wait(lambda: (lambda r: r if r[1].get("conflicts") else None)(rig.api("GET", "fleet/conflicts")))
        cs = (got or (0, {}))[1].get("conflicts") or []
        c = cs[0] if cs else {}
        ctx.check(f"one conflict on shop/basket.py between the two harnesses, got {cs}", len(cs) == 1 and c["repo"] == "shop"
                  and c["file"] == "basket.py" and {c["a"]["harness_name"], c["b"]["harness_name"]} == {"rolo@studio", "kali@lab"}
                  and c["source"] == "edit")
        rooms = got[1]["rooms"] if got else []
        ctx.check(f"the shop room holds both cards with branch and worktree, got {rooms}", len(rooms) == 1 and rooms[0]["key"] == "shop"
                  and {x["branch"] for x in rooms[0]["cards"]} == {"feature/basket", "review/basket"})
        rows = rig.api("GET", "fleet/attention")[1]["rows"]
        row = next((r for r in rows if r["kind"] == "conflict"), None)
        ctx.check(f"an attention row names both and the file, got {row and row['what']}",
                  row is not None and row["what"].endswith("are both editing basket.py") and "reviewer" in row["what"])
        files = [r for r in journal.read(rig.state, NOW - 60) if r["kind"] == "file"]
        ctx.check(f"both edits are journaled, got {[(f['harness_name'], f['file']) for f in files]}",
                  {(f["harness_name"], f["file"]) for f in files} >= {("rolo@studio", "basket.py"), ("kali@lab", "basket.py")})


def _stub_providers():
    from halo_harness.fleet import health
    saved = health._provider
    health._provider = lambda name, label, probe: {"name": label, "configured": True, "reachable": True if probe else None, "note": ""}
    health.forget()
    return lambda: (setattr(health, "_provider", saved), health.forget())


def _tree(root: Path) -> dict:
    return {str(p.relative_to(root)): (p.stat().st_size, p.stat().st_mtime_ns) for p in root.rglob("*")} if root.exists() else {}


@test
def test_health_is_read_only_cached_and_asks_a_member_once(ctx: Ctx):
    from halo_harness.config.paths import bridge_home
    from halo_harness.fleet import control, health, protocol
    from tests.helpers.studio_fleet_rig import StudioFleetRig
    undo = _stub_providers()
    try:
        before = _tree(bridge_home())
        got = health.subset()
        ctx.check(f"the subset: version, providers, disk, sockets, studio, status, got {sorted(got)}",
                  {"version", "python", "os", "providers", "disk", "sockets", "studio", "status", "checked"} <= set(got) and got["status"] == "ok")
        ctx.check("and nothing under the home changed", _tree(bridge_home()) == before)
        ctx.check("doctor is a read command of the fleet protocol", "doctor" in protocol.READ_CMDS)
        out = control.run(object(), {"cmd": "doctor"}, {"share": "status", "allow_control": "none", "allow_answers": False})
        ctx.check(f"a member answers doctor even with control off, got {out.get('state')}", out["state"] == "done" and out["result"]["status"] == "ok")
        with StudioFleetRig() as rig:
            health.forget()
            status, got = rig.api("GET", "fleet/health")
            rows = {r["name"]: r for r in got.get("harnesses") or []}
            m = rows.get("kali@lab") or {}
            ctx.check(f"both harnesses, the member's from its doctor answer, got {status} {sorted(rows)}", status == 200
                      and set(rows) == {"rolo@studio", "kali@lab"} and rows["rolo@studio"]["status"] == "ok"
                      and m.get("version") == "3.0.5.0" and m.get("session_model") == "or:deepseek/deepseek-v4" and m.get("cached") is False)
            asked = [d["cmd"] for d in rig.member_cmds]
            got2 = rig.api("GET", "fleet/health")[1]
            ctx.check(f"the second call comes from the 60 s cache, got {[r['cached'] for r in got2['harnesses']]}",
                      all(r["cached"] for r in got2["harnesses"]) and [d["cmd"] for d in rig.member_cmds] == asked
                      and asked.count("doctor") == 1 and asked.count("status") == 1)
            rig.api("GET", "fleet/health?refresh=1")
            ctx.check("refresh=1 asks again", [d["cmd"] for d in rig.member_cmds].count("doctor") == 2)
    finally:
        undo()


class _Bridge:
    def __init__(self, folder: Path):
        self.pairing = type("P", (), {"dir": folder.parent, "peers": lambda _self: {"aci-1": {}, "aci-2": {"blocked_until_reverified": True}}})()
        self.sent: list = []

    def say(self, aci, text, card=False):
        self.sent.append((aci, text, card))


@test
def test_the_phone_push_only_when_enabled_running_and_paired(ctx: Ctx):
    import os
    from halo_harness.config.paths import bridge_home
    from halo_harness.fleet import push
    from halo_harness.studio.fleet_watch_io import push_ready
    from halo_harness.theme import set_config_value
    home = bridge_home()
    row = {"id": "permission:M:s2:p9", "kind": "permission", "harness": "M", "harness_name": "kali@lab", "session_id": "s2",
           "agent": "verifier", "what": "Permission: Bash", "detail": "make clean", "target": {"request_id": "p9"}}
    asks = {("M", "s2", "p9"): {"data": {"id": "p9", "name": "Bash", "input": {"command": "make clean"}}}}
    ctx.check("off by default: nothing is ready", not push.ready(home) and not push_ready(home))
    (home / "remote").mkdir(parents=True, exist_ok=True)
    (home / "remote" / "peers.json").write_text(json.dumps({"peers": {"aci-1": {}}}), encoding="utf-8")
    (home / "remote" / "bridge.json").write_text(json.dumps({"state": "connected", "pid": os.getpid(), "started": time.time()}), encoding="utf-8")
    set_config_value("remote.enabled", True)
    try:
        ctx.check("enabled, running and paired: ready", push.ready(home) and push_ready(home))
        set_config_value("fleet.attention.signal", False)
        from halo_harness.fleet import identity
        identity.forget_cache()
        ctx.check("fleet.attention.signal false keeps it in Studio", not push_ready(home))
        set_config_value("fleet.attention.signal", True)
        identity.forget_cache()
        n = push.spool(home, [row, {**row, "id": "x", "local": True, "remote_attached": 1}], asks)
        folder = home / "remote" / push.SPOOL
        ctx.check(f"one card spooled (a session a phone is attached to is skipped), got {n}", n == 1 and len(list(folder.glob("*.json"))) == 1)
        (folder / "0-old.json").write_text(json.dumps({"id": "old", "created": time.time() - push.KEEP_S - 5, "text": "stale"}), encoding="utf-8")
        b = _Bridge(folder)
        sent = push.drain(b)
        ctx.check(f"the bridge sends it to the paired, unblocked phone as a card, prefixed, got {b.sent}",
                  sent == 1 and len(b.sent) == 1 and b.sent[0][0] == "aci-1" and b.sent[0][2] is True
                  and b.sent[0][1].startswith("[kali@lab · verifier]") and "make clean" in b.sent[0][1])
        ctx.check("the spool is empty after, the stale card dropped unsent", not list(folder.glob("*.json")))
    finally:
        set_config_value("remote.enabled", False)


def _jline(f, **row) -> None:
    f.write(json.dumps(row) + "\n")


@test
def test_the_digest_counts_per_harness_in_code(ctx: Ctx):
    from halo_harness.fleet import digest, journal
    from tests.helpers.studio_fleet_parts import PAST_SID, seed_past
    root = Path(tempfile.mkdtemp(prefix="digest-"))
    home, proj = root / ".halo", root / "shop"
    proj.mkdir(parents=True)
    seed_past(home, proj, t0=NOW - 3600)
    m = {"harness": "M", "harness_name": "kali@lab"}
    journal.path(home).parent.mkdir(parents=True, exist_ok=True)
    with open(journal.path(home), "w", encoding="utf-8") as f:
        _jline(f, ts=NOW - 900, kind="session_start", session_id="ms1", title="review", started=NOW - 1000, **m)
        _jline(f, ts=NOW - 300, kind="session_start", session_id="ms1", title="review", started=NOW - 1000, **m)
        _jline(f, ts=NOW - 300, kind="session_start", session_id="old", title="old", started=NOW - 3 * 86400, **m)
        _jline(f, ts=NOW - 8000, kind="cost", session_id="ms1", usd=0.10, **m)
        _jline(f, ts=NOW - 100, kind="cost", session_id="ms1", usd=0.30, **m)
        _jline(f, ts=NOW - 90, kind="file", session_id="ms1", file="src/a.py", **m)
        _jline(f, ts=NOW - 80, kind="error", session_id="ms1", text="pytest failed", **m)
        _jline(f, ts=NOW - 70, kind="decision", session_id="ms1", what="Approval (reviewer)", answer="accept", by="rolo@studio", row_kind="approval", **m)
        _jline(f, ts=NOW - 60, kind="handoff", session_id="ms1", action="hand_to", to="bob@laptop", by="rolo@studio", **m)
        _jline(f, ts=NOW - 50, kind="session_end", session_id="ms1", title="review", **m)
        _jline(f, ts=NOW - 9000, kind="decision", session_id="ms0", what="too old", answer="x", by="x", **m)
    d = digest.compute(home, NOW - 7200, now=NOW, local_id="L", local_name="rolo@studio")
    hs = {h["name"]: h for h in d["harnesses"]}
    me, km = hs.get("rolo@studio") or {}, hs.get("kali@lab") or {}
    ctx.check(f"this harness from its transcripts: the past session started and ended, its cost and files, got {me}",
              [s["session_id"] for s in me["started"]] == [PAST_SID] and [s["session_id"] for s in me["ended"]] == [PAST_SID]
              and abs(me["cost_usd"] - 0.025) < 1e-9 and me["files"] == ["basket.py"] and me["local"] is True)
    ctx.check(f"the member from the journal: one start (once), its end, cost since, got {km}",
              [s["session_id"] for s in km["started"]] == ["ms1"] and len(km["ended"]) == 1 and abs(km["cost_usd"] - 0.20) < 1e-9)
    ctx.check("decisions with who answered, files, errors, hand-offs",
              [(x["answer"], x["by"]) for x in km["decisions"]] == [("accept", "rolo@studio")] and km["files"] == ["src/a.py"]
              and len(km["errors"]) == 1 and km["handoffs"][0]["to"] == "bob@laptop")
    ctx.check(f"totals add up, got {d['totals']}", d["totals"]["started"] == 2 and d["totals"]["decisions"] == 1
              and abs(d["totals"]["cost_usd"] - 0.225) < 1e-9)
    ctx.check("the text form names both", "kali@lab" in digest.text(d) and "rolo@studio (this harness)" in digest.text(d))
    ctx.check("since: 2h, 45m, browser milliseconds, ISO", abs(digest.parse_since("2h", NOW) - (NOW - 7200)) < 1e-6
              and abs(digest.parse_since("45m", NOW) - (NOW - 2700)) < 1e-6 and digest.parse_since(str(int(NOW * 1000))) == int(NOW * 1000) / 1000
              and digest.parse_since("2026-10-14T09:00") > 0)
    try:
        digest.parse_since("yesterday-ish")
        ctx.check("a since that does not parse raises", False)
    except ValueError:
        pass


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="fleet panels more tests"))
