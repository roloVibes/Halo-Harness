"""tests.test_fleet_mission_asks -- Halo 3.4.1.0 R5 (live re-check defect 32): a mission part on a harness in permission
mode `default`. The live check: a files-only part ("write kali-ok into kali.txt") failed on Kali because its session
was print mode, where the Write the mode asks about is a deny -- so every part on such a harness failed.

Now (fleet/mission_wait.py): (a) a Write inside the part's own outputs folder `artifacts/<n>/` is the mission's own
bookkeeping and needs no ask -- only there, checked against `..`, `\\\\?\\` / `\\\\.\\` / UNC spellings, NTFS streams,
links out (a junction for the folder, a symlink under it); (b) any other call that would ask WAITS as a card on that
machine (the session's waiters, answered through its control socket), the part reads "waiting on you (on <machine>)"
on the hub, and after `fleet.mission.ask_wait_min` it ends "not done: nobody answered ...". Nothing else is allowed.
Run: python -m tests.test_fleet_mission_asks
"""
from __future__ import annotations
from tests.helpers import fleet_pack as _fleet_pack  # noqa: E402  (the fleet pack on, its modules by their old names)
_fleet_pack.on()

import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

ensure_scoped_state_dir_once()
test, TESTS = new_registry()
MID = "m-20261112-a5c0"


def _link_dir(link: Path, target: Path) -> None:
    try:
        import _winapi  # Windows: a junction needs no admin
        _winapi.CreateJunction(str(target), str(link))
    except ImportError:
        link.symlink_to(target, target_is_directory=True)


def _folder() -> Path:
    root = Path(tempfile.mkdtemp(prefix="mission-own-"))
    (root / MID / "artifacts" / "2").mkdir(parents=True)
    (root / MID / "artifacts" / "3").mkdir(parents=True)
    (root / "outside").mkdir()
    return root


@test
def test_the_own_folder_and_every_escape(ctx: Ctx):
    from halo_harness.fleet.mission_wait import own_write
    root = _folder()
    m, out = root / MID, root / "outside"
    own = lambda raw: own_write(m, "2", raw, m)  # noqa: E731
    ctx.check("artifacts/2/kali.txt, relative and absolute", own("artifacts/2/kali.txt") and own(str(m / "artifacts" / "2" / "kali.txt")))
    ctx.check("a sub-folder of its own folder", own("artifacts/2/deep/x.txt"))
    for raw, why in (("artifacts/2", "the folder itself"), ("MISSION.md", "the mission's own file"), ("artifacts/3/x.txt", "another part's"),
                     ("artifacts/2/../../MISSION.md", "`..` out"), ("artifacts/2/../2/x.txt", "`..` even back in"),
                     ("artifacts/2/x.txt:hidden", "an NTFS stream"), ("\\\\?\\" + str(m / "artifacts" / "2" / "x.txt"), "a \\\\?\\ spelling"),
                     ("\\\\.\\" + str(m / "artifacts" / "2" / "x.txt"), "a \\\\.\\ spelling"),
                     ("//localhost/C$/x/artifacts/2/x.txt", "an admin-share spelling"), (str(out / "x.txt"), "outside")):
        ctx.check(f"not its own: {why} ({raw})", not own(raw))
    _link_dir(m / "artifacts" / "2" / "out", out)
    ctx.check("a link under its folder pointing out", not own("artifacts/2/out/x.txt"))
    try:
        (out / "secret.txt").write_text("s", encoding="utf-8")
        os.symlink(out / "secret.txt", m / "artifacts" / "2" / "s.txt")
        ctx.check("a file link pointing out", not own("artifacts/2/s.txt"))
    except (OSError, NotImplementedError):
        pass  # Windows without the symlink privilege: the junction above covers a link out
    other = Path(tempfile.mkdtemp(prefix="mission-other-"))
    (m / "artifacts" / "3").rmdir()
    _link_dir(m / "artifacts" / "3", other)
    ctx.check("its folder itself a junction out (part 3's)", not own_write(m, "3", "artifacts/3/x.txt", m))


@test
def test_the_engine_allows_the_own_folder_and_nothing_else(ctx: Ctx):
    from types import SimpleNamespace
    from halo_harness.fleet.mission_guard import MissionClaimGuard, install
    from halo_harness.fleet.mission_wait import waits
    from halo_harness.permissions import PermissionEngine
    m = _folder() / MID
    engine = PermissionEngine(mode="default", cwd=m, print_mode=True)
    session = SimpleNamespace(permission_engine=engine, interactive=False)
    ctx.check("as the live check: print mode refuses the part's own output",
              engine.decide("Write", {"file_path": "artifacts/2/kali.txt", "content": "x"}).action == "deny")
    waits(session)
    ctx.check("waits(): an ask stays an ask and parks", engine.print_mode is False and session.interactive is True)
    install(engine, MissionClaimGuard(m, ["artifacts/2/**"], mission=MID, part="2", own=m))
    d = engine.decide("Write", {"file_path": "artifacts/2/kali.txt", "content": "x"})
    ctx.check(f"its own outputs folder: allowed, the reason says why, got {d.action} {d.reason!r}",
              d.action == "allow" and "own outputs folder" in d.reason)
    ctx.check("a command: still an ask (a card), never allowed by the mission",
              engine.decide("Bash", {"command": "nmap --version"}).action == "ask")
    for raw in ("artifacts/2/../../MISSION.md", "artifacts/3/x.txt", "\\\\?\\" + str(m / "artifacts" / "2" / "x.txt")):
        got = engine.decide("Write", {"file_path": raw, "content": "x"}).action
        ctx.check(f"{raw}: not allowed (the claim guard refuses or the mode asks), got {got}", got in ("deny", "ask"))
    repo = PermissionEngine(mode="default", cwd=m, print_mode=False)
    install(repo, MissionClaimGuard(m, ["artifacts/2/**"], mission=MID, part="2"))
    ctx.check("a repo part (no own folder): a write in its claims still asks",
              repo.decide("Write", {"file_path": "artifacts/2/kali.txt", "content": "x"}).action == "ask")


def _seed(home: Path, wait_min: float) -> Path:
    from halo_harness.fleet import mission_store as S
    from halo_harness.peers import identity
    me = identity.harness(home)
    (home / "config.json").write_text(json.dumps({"fleet": {"mission": {"ask_wait_min": wait_min}}}), encoding="utf-8")
    identity._cache.clear()
    S.create(home, {"id": MID, "goal": "two parts", "state": "running", "created": time.time(), "hub": {"id": me["id"], "name": me["name"]},
                    "parts": {"2": {"state": "running", "harness": me["id"], "harness_name": me["name"]}}})
    return S.folder(home, MID)


def _build(answer: "threading.Event | None"):
    from halo_harness.permissions import PermissionEngine
    from tests.helpers.fake_remote_session import FakeSession

    def build(cwd, home):
        session = FakeSession(f"ask{time.time_ns():x}"[:32].ljust(32, "0"))
        session.permission_engine = PermissionEngine(mode="default", cwd=cwd, print_mode=True)
        session._permission_waiters = {}

        def run(prompt: str, handle=None) -> dict:
            eng = session.permission_engine
            if eng.decide("Write", {"file_path": "artifacts/2/kali.txt", "content": "x"}).action == "allow":
                (Path(cwd) / "artifacts" / "2" / "kali.txt").write_text("kali-ok\n", encoding="utf-8")
            d = eng.decide("Bash", {"command": "nmap --version"})
            if d.action == "ask":  # as the loop parks it (agent/loop.py: _permission_waiters, resolve_permission)
                slot = {"event": threading.Event(), "decision": None, "tool_name": "Bash", "tool_input": {"command": "nmap --version"}}
                session._permission_waiters["t1"] = slot
                while not slot["event"].wait(0.05) and not session.abort.is_set():
                    pass
                session._permission_waiters.pop("t1", None)
                if session.abort.is_set():
                    return {"ok": False, "text": "interrupted", "cost_usd": 0.002, "error": "interrupted"}
            return {"ok": True, "text": "wrote it\n\nOutcome: done", "cost_usd": 0.003, "session_id": session.log.session_id}
        return session, run, lambda: None
    return build


def _run(home: Path, build) -> "tuple[object, list]":
    from halo_harness.fleet import mission_store as S
    from halo_harness.fleet import mission_worker as W
    from halo_harness.fleet.mission_doc import status_table
    from halo_harness.fleet.mission_worker_run import WorkerRun
    W.BUILD = build
    f = {"mission": MID, "part": "2", "title": "write kali.txt", "brief": "write kali-ok into kali.txt", "kind": "files",
         "claims": ["artifacts/2/**"], "outputs": ["artifacts/2/kali.txt"], "depends_on": [], "repo": None, "needs": [],
         "take": "outputs", "handoffs": [], "base": None, "branch": f"mission/{MID}/2", "cwd": None, "budget_usd": None,
         "mirror": {"mode": "local"}}
    r = WorkerRun(f, home=home, hub="hub", by="me", entry=None, origin=None)
    seen: list = []
    r.place()
    t = threading.Thread(target=r.run, daemon=True)
    t.start()
    while t.is_alive():
        doc = S.load(home, MID) or {}
        seen.append(status_table(doc))
        t.join(0.2)
    W.BUILD = None
    return r, seen


@test
def test_a_card_nobody_answers_ends_the_part_not_done(ctx: Ctx):
    from halo_harness.config.paths import bridge_home
    home = bridge_home()
    folder = _seed(home, 0.02)  # 1.2 s
    r, seen = _run(home, _build(None))
    ctx.check(f"its own output was written with no ask: {(folder / 'artifacts/2/kali.txt').is_file()}", (folder / "artifacts/2/kali.txt").is_file())
    ctx.check(f"while it waited the hub read 'waiting on you (on <machine>)': {[s for s in seen if 'waiting on you' in s][:1]}",
              any("waiting on you (on " in s and "Bash nmap --version" in s for s in seen))
    res = r.result or {}
    ctx.check(f"then the part ended not done: nobody answered, got {res.get('state')} {res.get('error')!r}",
              res.get("state") == "failed" and str(res.get("error")).startswith("not done: nobody answered Bash nmap --version on ")
              and "fleet.mission.ask_wait_min" in str(res.get("error")))
    from halo_harness.fleet import mission_store as S
    ctx.check("the card's mark is gone from mission.json", "asking" not in S.need(home, MID)["parts"]["2"])


@test
def test_an_answered_card_lets_the_part_finish(ctx: Ctx):
    import shutil
    from halo_harness.config.paths import bridge_home
    home = bridge_home()
    shutil.rmtree(home / "fleet" / "missions" / MID, ignore_errors=True)
    _seed(home, 30)
    from halo_harness.fleet import mission_worker as W
    build, shown = _build(None), []

    def answering(cwd, h):
        session, run, close = build(cwd, h)

        def answer() -> None:  # the owner answers the card (Studio's Attention -> the control socket) once it shows
            from halo_harness.fleet import mission_store as S
            for _ in range(400):
                slot = (session._permission_waiters or {}).get("t1")
                from halo_harness.fleet.mission_doc import status_table
                doc = S.load(h, MID) or {}
                if slot and ((doc.get("parts") or {}).get("2") or {}).get("asking"):
                    shown.append(status_table(doc))  # what the hub showed when the owner answered (no timing window)
                    slot["decision"] = {"action": "allow"}
                    slot["event"].set()
                    return
                time.sleep(0.05)
        threading.Thread(target=answer, daemon=True).start()
        return session, run, close
    r, _seen = _run(home, answering)
    ctx.check(f"the part was shown waiting, then done once answered: {shown} {(r.result or {}).get('state')}",
              any("waiting on you (on " in s for s in shown) and (r.result or {}).get("state") == "done")
    W.BUILD = None


@test
def test_the_hub_side_and_the_plan_note(ctx: Ctx):
    from halo_harness.config.paths import bridge_home
    from halo_harness.fleet import mission_store as S
    from halo_harness.fleet.mission_assign import mode_note
    from halo_harness.fleet.mission_wait import note
    home = bridge_home()
    hid = S.need(home, MID)["parts"]["2"]["harness"]
    data = {"action": "mission_wait", "mission": MID, "part": "2", "what": "Bash nmap --version", "since": 1.0, "on": "kali@kali"}
    ctx.check("a frame from another harness is ignored", not note(home, {"harness": "someone-else", "data": data}))
    ctx.check("the part's own harness: marked", note(home, {"harness": hid, "data": data})
              and S.need(home, MID)["parts"]["2"]["asking"]["on"] == "kali@kali")
    note(home, {"harness": hid, "data": {**data, "what": None}})
    ctx.check("answered: the mark is gone", "asking" not in S.need(home, MID)["parts"]["2"])
    e = {"name": "kali@kali", "catalog": {"harness": {"permission_mode": "default", "mission_ask_wait_min": 30}}}
    said = mode_note(e)
    ctx.check(f"the plan says the part waits as a card for 30 min, its own folder needs no ask: {said!r}",
              "waits as a card" in said and "30 min" in said and "own outputs folder with the Write tool needs no ask" in said and "refused" not in said)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="fleet mission asks tests"))
