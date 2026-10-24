"""tests.test_knowledge_fleet -- Halo 3.1.8.0 R4: findings and decisions across
the fleet (knowledge/share.py, the `knowledge` fleet command in
fleet/control.py, the hub's `local/knowledge` route in fleet/hub_recall.py,
recall_fleet's hits), over the coach library's transport:

1. a member's answer: one entry by id, or every current entry of a kind;
   scrubbed (a private path cut to its last part, a key redacted, `by` naming
   the harness id, never a person); a `knowledge_asked` journal line; refused
   under `fleet.recall.share: false`, `fleet.recall.hide: [knowledge]` /
   `[finding]`, for an unknown id and for one entry over 256 KB;
2. over tests/helpers/fleet_hub_rig.py's two homes: the hub forwards
   `{harness, id}` to B's live session, and `fetch` writes B's entry in A's
   store under the same id, read-only (`_meta.json`: source fleet, from,
   harness_name, fetched, read_only), never over it again; `--all` a kind;
3. a recall hit across the fleet carries the entry's `ref`; the owner's own
   notes (kind `note`) never leave the box.
No model and no embedding model is ever called. Run: python -m tests.test_knowledge_fleet
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
FAKE_KEY = "sk-or-v1-FAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKE1234567890abcdef"


def seed(home: Path, big: int = 0) -> "tuple[dict, dict]":
    from halo_harness.knowledge.store import write
    f = write("finding", "basket.py#total passes `pytest -q` at 3f2a1b9c0d4e",
              body="Where: C:\\Users\\alice\\repo\\basket.py and /home/alice/repo/basket.py.\n\nThe key was "
                   f"OPENROUTER_API_KEY={FAKE_KEY} in the log." + ("x" * big),
              evidence=["tests: `pytest -q` exit 0, 5 passed"], by="gate", run="r1", repo="basket", state_dir=home)
    d = write("decision", "money is Decimal", alternatives=["float"], by="supervisor", state_dir=home)
    return f, d


def _home(config: "dict | None" = None) -> Path:
    from halo_harness.fleet import identity
    home = Path(tempfile.mkdtemp(prefix="know-ans-")) / ".halo"
    home.mkdir(parents=True)
    (home / "config.json").write_text(json.dumps({"fleet": dict({"name": "kali"}, **(config or {}))}), encoding="utf-8")
    identity.forget_cache()
    return home


def _refused(fields, home) -> str:
    from halo_harness import recall_fleet as RF
    from halo_harness.knowledge import share
    try:
        share.answer(fields, by="alice", hub="hub-a", home=home)
    except RF.Shut as e:
        return str(e)
    return ""


@test
def test_a_members_answer_scrubbed_and_what_it_refuses(ctx: Ctx):
    from halo_harness.fleet import identity, journal
    from halo_harness.knowledge import share
    home = _home()
    f, d = seed(home)
    me = identity.harness(home)
    out = share.answer({"id": f["id"]}, by="alice", hub="hub-a", home=home)
    e = out["entries"][0] if out.get("entries") else {}
    ctx.check(f"one entry with its fields, got {sorted(e)}", out["harness"] == "kali" and out["harness_id"] == me["id"]
              and e.get("id") == f["id"] and e["title"] == f["title"] and e["evidence"] == f["evidence"])
    ctx.check(f"no private path, got {e.get('body')!r}", "alice" not in e.get("body", "") and "basket.py and basket.py" in e["body"])
    ctx.check("no key", FAKE_KEY not in json.dumps(out) and "FAKEFAKE" not in json.dumps(out))
    ctx.check(f"by names the harness id, never a person, got {e.get('by')}", e.get("by") == f"gate@{me['id']}")
    rows = [r for r in journal.read(home) if r.get("kind") == "knowledge_asked"]
    ctx.check(f"a knowledge_asked line, got {rows}", len(rows) == 1 and rows[0]["entry"] == f["id"] and rows[0]["by"] == "alice"
              and rows[0]["entries"] == 1 and rows[0]["bytes"] == out["bytes"])
    every = share.answer({"kind": "decision", "all": True}, by="alice", hub="hub-a", home=home)
    ctx.check("all of a kind", [x["id"] for x in every["entries"]] == [d["id"]])
    ctx.check("an unknown id", "no knowledge entry 'f-20200101-000000'" in _refused({"id": "f-20200101-000000"}, home))
    ctx.check("neither an id nor a kind with all", "names an entry id" in _refused({"kind": "finding"}, home))
    ctx.check("share off answers none", "fleet.recall.share: false" in _refused({"id": f["id"]}, _shared(False)))
    hidden = _hidden(["knowledge"])
    ctx.check("hide knowledge keeps both kinds in", "fleet.recall.hide: knowledge" in _refused({"id": seed_id(hidden)}, hidden)
              and "fleet.recall.hide: knowledge" in _refused({"kind": "decision", "all": True}, hidden))
    hidden = _hidden(["finding"])
    ctx.check("hide finding keeps the findings in, the decisions go", "fleet.recall.hide: finding" in
              _refused({"id": seed_id(hidden)}, hidden) and share.answer({"kind": "decision", "all": True}, home=hidden)["entries"])
    big = _home()
    bf, _bd = seed(big, big=300 * 1024)
    ctx.check("a body is kept to 20 000 characters, so one entry stays far under the cap",
              len(bf["body"]) == 20_000 and share.answer({"id": bf["id"]}, home=big)["bytes"] < 64 * 1024)
    saved = share.MAX_BYTES
    share.MAX_BYTES = 1500
    try:
        from halo_harness.knowledge.store import write
        for n in range(4):
            write("decision", f"decision {n} " + "y" * 300, by="user", state_dir=big)
        msg = _refused({"id": bf["id"]}, big)
        cut = share.answer({"kind": "decision", "all": True}, home=big)
    finally:
        share.MAX_BYTES = saved
    ctx.check(f"one entry over the cap: refused with its size, got {msg!r}", "KB; a fetch carries at most 1 KB" in msg)
    ctx.check(f"all: the newest that fit, the rest counted, got {len(cut['entries'])} {cut['left_out']}",
              cut["entries"] and cut["left_out"] and len(cut["entries"]) + cut["left_out"] == 5 and cut["bytes"] <= 1500)
    identity.forget_cache()


def seed_id(home: Path) -> str:
    from halo_harness.knowledge.store import current
    return next(e["id"] for e in current(home, kind="finding"))


def _shared(share: bool) -> Path:
    home = _home({"recall": {"share": share}})
    seed(home)
    return home


def _hidden(kinds: list) -> Path:
    home = _home({"recall": {"hide": kinds}})
    seed(home)
    return home


@test
def test_the_hub_forwards_and_fetch_writes_read_only(ctx: Ctx):
    from halo_harness.config.paths import bridge_home
    from halo_harness.fleet import journal
    from halo_harness.fleet.hub import running_call
    from halo_harness.knowledge import store
    from halo_harness.knowledge.share import fetch
    from tests.helpers.fleet_hub_rig import HubRig, wait_for
    from tests.helpers.mission_seed import fleet
    with HubRig() as rig:
        f, d = seed(bridge_home())  # B's own knowledge (this process's home is B)
        fleet(rig, **{"fleet.allow_control": "all"})
        wait_for(lambda: rig.member_session_online("fakesession0000000000000000000001"), 20.0)
        got = running_call(rig.home_a, "POST", "local/knowledge", {"harness": "bob@member", "id": f["id"]}, timeout=30.0)
        ctx.check(f"the admin route answers B's entry, got {got and got[0]}", got and got[0] == 200
                  and got[1]["result"]["entries"][0]["id"] == f["id"] and got[1]["harness"] == "bob@member")
        rc, out = fetch("bob@member", f["id"], home=rig.home_a, state_dir=rig.home_a)
        e = store.read(f["id"], rig.home_a) or {}
        meta = e.get("meta") or {}
        ctx.check(f"fetch writes it here under the same id, got {rc} {out}", rc == 0 and out["written"] == [f["id"]]
                  and e.get("title") == f["title"] and e.get("when") == f["when"] and e.get("by", "").startswith("gate@"))
        ctx.check(f"read-only, its _meta.json says where it came from, got {meta}", e.get("read_only")
                  and meta.get("source") == "fleet" and meta.get("harness_name") == "bob@member" and meta.get("from")
                  and meta.get("fetched"))
        rc, out = fetch("bob@member", f["id"], home=rig.home_a, state_dir=rig.home_a)
        ctx.check(f"never over an entry that is here, got {rc} {out}", rc == 1 and "never overwrites" in out["error"])
        rc, out = fetch("bob@member", kind="decision", all_kind=True, home=rig.home_a, state_dir=rig.home_a)
        ctx.check(f"--all decision, got {rc} {out}", rc == 0 and out["written"] == [d["id"]])
        rc, out = fetch("bob@member", "f-20200101-000000", home=rig.home_a, state_dir=rig.home_a)
        ctx.check(f"B refuses an unknown id, got {rc} {out}", rc == 1 and "no knowledge entry" in out["error"])
        ctx.check("a usage error is 2", fetch("bob@member", "not-an-id", home=rig.home_a)[0] == 2)
        rows = [r for r in journal.read(bridge_home()) if r.get("kind") == "knowledge_asked"]
        ctx.check(f"B logged the asks in its own journal, got {len(rows)}", len(rows) >= 3)


@test
def test_fleet_hits_carry_ref_and_notes_stay_home(ctx: Ctx):
    from halo_harness import recall_fleet as RF
    home = _home()
    f, _d = seed(home)
    note = home.parent / "vault" / "soup.md"
    note.parent.mkdir(parents=True)
    note.write_text("# Soup\ntomato soup recipe", encoding="utf-8")
    saved = RF.SEARCH
    RF.SEARCH = lambda q, k, h: [{"id": f["path"], "kind": "finding", "title": f["title"], "score": 0.9},
                                 {"id": str(note), "kind": "note", "title": "Soup", "score": 0.8}]
    try:
        out = RF.answer({"query": "basket soup", "k": 8}, by="alice", hub="hub-a", home=home)
        mine, _note = RF.local_hits("basket soup", 8, home)
    finally:
        RF.SEARCH = saved
    ctx.check(f"the finding goes with its ref, by and when, got {out['hits']}", len(out["hits"]) == 1
              and out["hits"][0]["ref"] == f["id"] and out["hits"][0]["by"] == "gate" and out["hits"][0]["when"] == f["when"])
    ctx.check("the note never leaves the box, and is not counted as hidden", out["hidden"] == 0
              and all(h["kind"] != "note" for h in out["hits"]))
    ctx.check("this harness's own view keeps the note", [h["kind"] for h in mine] == ["finding", "note"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="knowledge fleet tests"))
