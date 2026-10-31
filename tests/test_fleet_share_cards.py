"""tests.test_fleet_share_cards -- Halo 3.3.7.0 R2 deliverable 7, across the fleet (fleet/ollama_share_cards.py,
ollama_share_take.take_reply, fingerprints.read's fleet rows, profiles.merge_from_hub's dialect):

1. the member's push carries `speed_cards` (benched here in the last ten minutes on a host it serves) and
   `dialect_records` (its served models', with its address and port; sent when they change);
2. the hub keeps each speed card under `<member>:<host>` in its capability cache and each dialect record on its own
   host entry at that address (never over a field its user set);
3. the hub's answer carries the fleet's fingerprints; the member keeps them with `from`, and its `fingerprints.read`
   for a host includes them ("crashed on <hub>:<member>:<host> on <date>"), so `exclude: crashed` knows them;
4. a hub profile whose dialect record changed reaches the member.
Run: python -m tests.test_fleet_share_cards
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.steward_seed import Home  # noqa: E402

test, TESTS = new_registry()
BOX = {"name": "box", "url": "http://127.0.0.1:11999"}
ADDR = "192.0.2.20"
MODEL = "qwen3-coder:30b"


def _card(host: str = "box") -> dict:
    return {"ok": True, "model": MODEL, "host": host, "digest": "sha256:c0de", "at": time.time() - 60,
            "windows": [{"window": 32768, "tok_s": 188.0, "on_gpu": True}], "cold_load_s": 21.0}


class _Addr:
    def __enter__(self):
        from halo_harness.fleet import hub
        self.saved, hub.lan_address = hub.lan_address, lambda: ADDR
        return self

    def __exit__(self, *exc):
        from halo_harness.fleet import hub
        hub.lan_address = self.saved


@test
def test_the_push_carries_speed_cards_and_dialect_records(ctx: Ctx):
    from halo_harness.fleet import ollama_share_cards as SC
    from halo_harness.providers import dialect as D
    from halo_harness.providers.local_bench_runs import save
    with Home(hosts=(BOX,)) as member, _Addr():
        SC._SENT.clear()
        save(member.state, _card())
        D.set_fields("box", MODEL, {"reply_reserve": 512, "strip_fences": True}, by="user")
        got = SC.member_payload(member.state)
        ctx.check(f"speed_cards: the card benched here, got {got['speed_cards']}", [c["model"] for c in got["speed_cards"]] == [MODEL])
        recs = got["dialect_records"]
        ctx.check(f"dialect_records: the served model's record with the address and port, got {recs}", recs
                  and recs[0]["dialect"]["reply_reserve"] == 512 and recs[0]["addr"] == ADDR and recs[0]["port"] == 11999)
        ctx.check("unchanged, it is not sent again", SC.member_payload(member.state)["dialect_records"] == [])
        for k in ("probes", "crashes", "events"):
            ctx.check(f"{k} still travel", k in got)
    payload = got
    lab = {"name": "lab", "url": f"http://{ADDR}:11999"}
    with Home(hosts=(lab,)) as hub:
        from halo_harness.providers.local_bench_runs import all_cards
        SC.take_member_payload(hub.state, "mac@lab", payload)
        cards = all_cards(hub.state, host="mac@lab:box")
        ctx.check(f"the hub keeps the card under <member>:<host>, from the member, got {cards}", cards
                  and cards[0]["from"] == "mac@lab" and cards[0]["windows"][0]["tok_s"] == 188.0)
        rec = D.stored("lab", MODEL)
        ctx.check(f"the dialect record lands on the hub's own entry at that address, got {rec}", rec.get("reply_reserve") == 512
                  and (rec.get("from") or {}).get("reply_reserve") == "hub")
        D.set_fields("lab", MODEL, {"reply_reserve": 1024}, by="user")
        SC.take_dialects(hub.state, "mac@lab", payload["dialect_records"])
        ctx.check("never over the hub user's own field", D.stored("lab", MODEL).get("reply_reserve") == 1024)


@test
def test_the_fleets_fingerprints_come_back(ctx: Ctx):
    from halo_harness.fleet import ollama_share_cards as SC
    from halo_harness.fleet.ollama_share_take import take_reply
    from halo_harness.ollama_steward import fingerprints as F
    fp = {"host": "pc", "model": MODEL, "signature": "CUDA IMA", "at": time.time() - 3600, "count": 2,
          "window_used": 65536, "kv_cache_type": "q8_0", "flash_attention": True, "spill": True}
    with Home(hosts=(BOX,)) as hub:
        F._write(hub.state, [fp])
        F.take(hub.state, "kali@lab", [{**fp, "host": "default", "at": time.time() - 60}])
        extra = SC.reply_extra(hub.state, "mac@lab", "pc-hub")
        ctx.check(f"the answer carries the hub's and the other members' rows, got {[r['host'] for r in extra['fingerprints']]}",
                  {r["host"] for r in extra["fingerprints"]} == {"pc", "kali@lab:default"} and extra["fleet_from"] == "pc-hub")
        mine = SC.reply_extra(hub.state, "kali@lab", "pc-hub")
        ctx.check("never a member's own rows sent back to it", all(r.get("from") != "kali@lab" for r in mine["fingerprints"]))
    with Home(hosts=(BOX,)) as member:
        take_reply({**extra, "profiles": {}}, member.state)
        rows = F.read(member.state, host="box")
        ctx.check(f"the member's read for its own host includes the fleet's rows, got {[r['line'] for r in rows]}",
                  len(rows) == 2 and all(r.get("from") == "pc-hub" for r in rows)
                  and any(r["line"].startswith("crashed on pc-hub:pc on ") for r in rows))
        from halo_harness.models_library.search import crash_for
        ctx.check("exclude: crashed knows the fleet's failure", crash_for({"name": MODEL, "model": MODEL, "tag": "30b"}, rows)
                  is not None or crash_for({"ref": f"ol:{MODEL}@box", "name": "qwen3-coder", "tag": "30b"}, rows) is not None)


@test
def test_a_hub_dialect_change_reaches_the_member(ctx: Ctx):
    from halo_harness.ollama_steward.profiles import all_profiles, merge_from_hub
    with Home(hosts=(BOX,)):
        merge_from_hub({f"box|{MODEL}": {"num_ctx": 32768, "by": "steward"}})
        n = merge_from_hub({f"box|{MODEL}": {"num_ctx": 32768, "by": "steward",
                                             "dialect": {"reply_reserve": 512, "from": {"reply_reserve": "ledger"}}}})
        ctx.check(f"the dialect alone changed: taken, got {n} {all_profiles().get(f'box|{MODEL}')}", n == 1
                  and (all_profiles().get(f"box|{MODEL}") or {}).get("dialect", {}).get("reply_reserve") == 512)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
