"""tests.test_coach_library_fleet -- Halo 3.1.6.0 R3: the improvement library
across the fleet (orchestra/coach_library_share.py, the `coach_library` fleet
command in fleet/control.py, the hub's `local/coach-library` route in
fleet/hub_recall.py, recall's `coach_library` source kind in recall.py):

1. a member's answer from its own library: entry.json, EXPERIENCE.md,
   overlay.json and files/, a `library_asked` journal line; refused under
   `fleet.recall.share: false`, `fleet.recall.hide: [coach_library]`, for an
   unknown entry and over 256 KB (with the size);
2. over tests/helpers/fleet_hub_rig.py's two homes: the hub's admin route
   forwards `{harness, entry}` to B's live session, and `fetch` writes B's entry
   in A's library under the same id with `from`, never over it again;
3. recall indexes every entry's EXPERIENCE.md as kind `coach_library` (title =
   its first heading), leaves an undone one out, prunes one whose folder went.
No model and no embedding model is ever called. Run: python -m tests.test_coach_library_fleet
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
EID = "e-20261020-b0b1"


def seed(home: Path, eid: str = EID, big: int = 0, undone: bool = False) -> str:
    from halo_harness.orchestra import coach_library as L
    doc = {"id": eid, "ts": 1792500000.0, "run": "20261020-090000-b0b1", "run_dir": "/kali/repo/.halo/orchestra/x",
           "kind": "orchestra", "project": {"name": "basket", "remote": "github.com/rolo/basket"}, "lineup": "",
           "goal": {"what": "Write basket.py", "done_when": "the tests pass"}, "source": "apply", "title": "stronger model",
           "apply_ids": ["a-0000000001"], "files": [{"path": "agents/coach-cheap.yaml", "scope": "home"}], "undone": undone,
           "changes": [{"target": "bio", "name": "coach-cheap", "field": "models.preference", "value": "or:vendor/strong"}]}
    files = {"agents/coach-cheap.yaml": "name: coach-cheap\nmodels:\n  preference: or:vendor/strong\n"}
    if big:
        files["notes/big.txt"] = "x" * big
    L.write(doc, "# give coach-cheap the stronger model\n## When it applies\nproject basket\n## Lessons\n- the cheap "
                 "lane hit the return cap; the strong one finished first try\n## Evidence\n- lane 2 returned twice\n",
            {"bios": {"coach-cheap": {"model": "or:vendor/strong"}}}, files, home)
    return str(L.entry_dir(eid, home) / L.EXPERIENCE)


def _home(config: "dict | None" = None) -> Path:
    from halo_harness.fleet import identity
    home = Path(tempfile.mkdtemp(prefix="lib-ans-")) / ".halo"
    home.mkdir(parents=True)
    (home / "config.json").write_text(json.dumps({"fleet": dict({"name": "kali"}, **(config or {}))}), encoding="utf-8")
    identity.forget_cache()
    return home


@test
def test_a_members_answer_and_what_it_refuses(ctx: Ctx):
    from halo_harness import recall_fleet as RF
    from halo_harness.fleet import identity, journal
    from halo_harness.orchestra import coach_library_share as LS
    home = _home()
    seed(home)
    out = LS.answer({"entry": EID}, by="alice", hub="hub-a", home=home)
    ctx.check(f"the entry's four parts, got {sorted(out)}", out["entry"]["id"] == EID and out["experience"].startswith("# give")
              and out["overlay"] == {"bios": {"coach-cheap": {"model": "or:vendor/strong"}}}
              and list(out["files"]) == ["agents/coach-cheap.yaml"] and out["harness"] == "kali" and 0 < out["bytes"] < 4096)
    rows = [r for r in journal.read(home) if r.get("kind") == "library_asked"]
    ctx.check(f"a library_asked line, got {rows}", len(rows) == 1 and rows[0]["entry"] == EID and rows[0]["by"] == "alice"
              and rows[0]["hub"] == "hub-a" and rows[0]["bytes"] == out["bytes"])

    def refused(fields, h) -> str:
        try:
            LS.answer(fields, by="alice", hub="hub-a", home=h)
        except RF.Shut as e:
            return str(e)
        return ""
    ctx.check("an unknown entry is refused", "no entry 'e-20261020-ffff'" in refused({"entry": "e-20261020-ffff"}, home))
    ctx.check("a word that is not an id is refused", "no entry" in refused({"entry": "../x"}, home))
    big = _home()
    seed(big, big=300 * 1024)
    msg = refused({"entry": EID}, big)
    ctx.check(f"over 256 KB: refused with the size, got {msg!r}", "KB; a fetch carries at most 256 KB" in msg and "is 3" in msg)
    ctx.check("share off answers none", "fleet.recall.share: false" in refused({"entry": EID}, _shut_home(False)))
    hidden = _home({"recall": {"hide": ["coach_library"]}})
    seed(hidden)
    ctx.check("hide coach_library keeps the library out", "fleet.recall.hide: coach_library" in refused({"entry": EID}, hidden))
    identity.forget_cache()


def _shut_home(share: bool) -> Path:
    home = _home({"recall": {"share": share}})
    seed(home)
    return home


@test
def test_the_hub_forwards_and_fetch_writes_under_the_same_id(ctx: Ctx):
    from halo_harness.config.paths import bridge_home
    from halo_harness.fleet import journal
    from halo_harness.fleet.hub import running_call
    from halo_harness.orchestra import coach_library as L
    from halo_harness.orchestra.coach_library_share import fetch
    from tests.helpers.fleet_hub_rig import HubRig, wait_for
    from tests.helpers.mission_seed import fleet
    with HubRig() as rig:
        seed(bridge_home())  # B's own library (this process's home is B)
        fleet(rig, **{"fleet.allow_control": "all"})
        wait_for(lambda: rig.member_session_online("fakesession0000000000000000000001"), 20.0)
        got = running_call(rig.home_a, "POST", "local/coach-library", {"harness": "bob@member", "entry": EID}, timeout=30.0)
        ctx.check(f"the admin route answers B's entry, got {got and (got[0], sorted(got[1]))}", got and got[0] == 200
                  and got[1]["result"]["entry"]["id"] == EID and got[1]["harness"] == "bob@member")
        ctx.check("an unknown harness is 404", running_call(rig.home_a, "POST", "local/coach-library",
                                                            {"harness": "nobody", "entry": EID}, timeout=30.0)[0] == 404)
        rc, out = fetch("bob@member", EID, home=rig.home_a, state_dir=rig.home_a)
        e = L.read(EID, rig.home_a) or {}
        ctx.check(f"fetch writes it here under the same id with from, got {rc} {out}", rc == 0 and e.get("from") == "bob@member"
                  and e.get("project", {}).get("remote") == "github.com/rolo/basket" and out["files"] == ["agents/coach-cheap.yaml"]
                  and L.stored_files(EID, rig.home_a) == L.stored_files(EID, bridge_home()))
        ctx.check("EXPERIENCE.md and overlay.json came along", L.text_of(EID, L.EXPERIENCE, rig.home_a).startswith("# give")
                  and json.loads(L.text_of(EID, L.OVERLAY, rig.home_a))["bios"])
        rc, out = fetch("bob@member", EID, home=rig.home_a, state_dir=rig.home_a)
        ctx.check(f"never over an entry that is here, got {rc} {out}", rc == 1 and "never overwrites" in out["error"])
        rc, out = fetch("bob@member", "e-20261020-ffff", home=rig.home_a, state_dir=rig.home_a)
        ctx.check(f"B refuses an unknown entry, got {rc} {out}", rc == 1 and "no entry" in out["error"])
        jrows = [r for r in journal.read(bridge_home()) if r.get("kind") == "library_asked"]
        ctx.check(f"B logged the asks in its own journal, got {len(jrows)}", len(jrows) == 2 and jrows[-1]["entry"] == EID)


@test
def test_recall_indexes_the_library_as_its_own_kind(ctx: Ctx):
    import halo_harness.providers.embeddings as EMB
    from halo_harness import recall
    from halo_harness.orchestra import coach_library as L
    state = Path(tempfile.mkdtemp(prefix="lib-index-")) / ".halo"
    path = seed(state)
    seed(state, "e-20261020-b0b2", undone=True)
    src = recall._library_sources(state)
    ctx.check(f"one source per live entry, title = its first heading, got {[s[:2] for s in src]}",
              [(s[0], s[1]) for s in src] == [(path, "give coach-cheap the stronger model")])
    saved = (EMB.embeddings_enabled, EMB.embed_texts)
    EMB.embeddings_enabled, EMB.embed_texts = (lambda: True), (lambda texts: [[1.0, 0.0] for _ in texts])
    try:
        recall.build_index(state, cwd=state)
        index = recall._load_index(recall._index_path(state))
        ctx.check(f"indexed as kind coach_library, got {[(e['kind'], e['title']) for e in index.values()]}",
                  index.get(path, {}).get("kind") == "coach_library" and len(index) == 1)
        L.forget(EID, state)
        recall.build_index(state, cwd=state)
        ctx.check("pruned once its folder went", recall._load_index(recall._index_path(state)) == {})
    finally:
        EMB.embeddings_enabled, EMB.embed_texts = saved


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="coach library fleet tests"))
