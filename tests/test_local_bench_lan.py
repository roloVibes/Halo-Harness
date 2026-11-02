"""tests.test_local_bench_lan -- Halo 3.3.8.1 "Bench from any halo" deliverables 1, 3b and 4: a bench (and the battery)
run from a peer against an Ollama host this machine does not serve says so on its card (providers/local_bench_link.py),
on the bench's scripted fake (tests/helpers/bench_rig.py; `over_the_lan` makes every host another machine's and fixes
the link's RTT), no model call, nothing sent but to the fake on 127.0.0.1:

1. the label, the link line and the offer, a host at a 192.0.2.x placeholder (never asked: the test flag stops the
   probe), the readers' pick (a machine-own card over a LAN one of the same age class, else the newer);
2. a bench over the LAN: the label is the first line said and the card's first line, the card keeps `over_lan`,
   `measured_from`, `link` in its own slot; the badge, the Hosts row and the cost line say it; a later bench from the
   machine itself replaces it; a newer Ollama's LAN card wins over an older own one;
3. the battery from a peer: its speed row (tok/s, TTFT) carries the fields, the gates do not; the placement latency
   line says it;
4. `halo local bench` from a peer: the cost line with the label, the offer line, `--json` with the fields.
Run: python -m tests.test_local_bench_lan
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
ensure_default_provider_credentials()

from tests.helpers.bench_rig import BenchRig, over_the_lan  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
LABEL = "measured over the LAN from mac: includes the link (RTT 1.8 ms, wired)"


@test
def test_the_label_the_link_and_the_pick(ctx: Ctx):
    from halo_harness.fleet import ollama_share as S
    from halo_harness.providers import local_bench_link as L
    from halo_harness.providers.ollama import OllamaHost
    far = OllamaHost(name="lan", url="http://192.0.2.10:11434")
    ctx.check("a host on loopback is this machine's: no label", L.over_lan(OllamaHost(name="me", url="http://127.0.0.1:11434")) is None)
    saved = S.served_here
    S.served_here = lambda _u: False
    try:
        got = L.over_lan(far)
    finally:
        S.served_here = saved
    ctx.check(f"a placeholder host is never asked under the test flag, got {got}", got["over_lan"] and got["link"]["rtt_ms"] is None
              and got["link"]["line"].startswith("RTT not measured: not asked in tests"))
    with over_the_lan():
        ctx.check(f"the label, got {L.label(far)!r}", L.label(far) == LABEL)
    ctx.check("the link line words", L.link_line(12.0, "Wi-Fi") == "RTT 12 ms, Wi-Fi" and L.link_line(0.4, None) == "RTT 0.4 ms")
    offer = L.offer_line(far.url, far.name, bench=True)
    ctx.check(f"the offer: serve there, join here, the grant, got {offer!r}", offer.startswith(
        "a card without the link: `halo host serve` on 192.0.2.10 (`halo host install` for a service), then "
        "`halo host join 192.0.2.10` here and `halo host grant ") and offer.endswith(" control` there"))
    now = time.time()
    own = {"digest": "d1", "ollama_version": "0.40.13", "at": now - 3 * 86400, "over_lan": False}
    lan = {"digest": "d1", "ollama_version": "0.40.13", "at": now - 3600, "over_lan": True}
    ctx.check("same age class: the machine's own card wins over a newer LAN one", L.pick(own, lan, now) is own)
    ctx.check("a newer Ollama: the newer (LAN) card wins", L.pick(own, {**lan, "ollama_version": "0.40.14"}, now)["over_lan"])
    ctx.check("another age bucket: the newer wins", L.pick({**own, "at": now - 40 * 86400}, lan, now) is lan)
    ctx.check("one card alone is read", L.pick(None, lan) is lan and L.pick(own, None) is own)


@test
def test_a_bench_over_the_lan_labels_its_card_and_an_own_one_replaces_it(ctx: Ctx):
    from halo_harness.providers import local_bench_runs as R
    from halo_harness.providers.fit_meter import speed_word
    from halo_harness.providers.local_bench import cost_line
    from halo_harness.providers.local_bench_link import over_lan
    from halo_harness.studio.local_hosts_view import _benched
    with BenchRig(["bn-small:9b"]) as rig, over_the_lan():
        said: list = []
        c = rig.bench("bn-small:9b", quick=True, lan=over_lan(rig.host, rig.state), on_line=said.append)
        ctx.check(f"the label is the first line said, got {said[:2]}", c["ok"] and said[0] == LABEL)
        ctx.check(f"the card keeps the fields, got {c.get('measured_from')} {c.get('link')}", c["over_lan"] is True
                  and c["measured_from"] == "mac" and c["link"]["rtt_ms"] == 1.8 and c["link"]["kind"] == "wired")
        ctx.check(f"the card's first line is the label, got {R.lines(c)[:2]}", R.lines(c)[0] == LABEL
                  and R.lines(c)[1].startswith("speed card (the bench"))
        e = rig.cache()["sha256:bn-small-9b"]
        ctx.check(f"its own slot, the machine-own slot empty, got {sorted(e)}", e["speed_card_lan"]["fake"]["over_lan"]
                  and "fake" not in (e.get("speed_card") or {}))
        card = R.load(rig.state, "fake", "bn-small:9b")
        ctx.check("load reads it", card and card["over_lan"] and R.view(card)["link"]["line"] == "RTT 1.8 ms, wired")
        word = speed_word("fits", R.mirror(card))
        ctx.check(f"the badge says where it was measured, got {word!r}", word.endswith("(over the LAN from mac)"))
        row = _benched([{"model": "bn-small:9b"}], "fake")[0]["bench"]
        ctx.check(f"the Hosts row too, got {row!r}", str(row).endswith("(the bench, over the LAN from mac)"))
        line = cost_line("fake", 3, LABEL)
        ctx.check(f"the cost line carries the label, got {line!r}", line == "local: ~3 min on fake, the card is busy meanwhile, "
                  "writes the speed card; no tokens leave the LAN; " + LABEL)
    with BenchRig(["bn-small:9b"]) as rig:
        with over_the_lan():
            rig.bench("bn-small:9b", quick=True, lan=over_lan(rig.host, rig.state))
        own = rig.bench("bn-small:9b", quick=True)
        e = rig.cache()["sha256:bn-small-9b"]
        ctx.check(f"a later bench from the machine itself replaces it, got {sorted(e)}", own["over_lan"] is False
                  and not (e.get("speed_card_lan") or {}).get("fake") and e["speed_card"]["fake"]["over_lan"] is False)
        ctx.check("the card's lines say which: the machine's own", R.lines(R.load(rig.state, "fake", "bn-small:9b"))[0]
                  .startswith("speed card (the bench"))
        newer = {**own, "over_lan": True, "measured_from": "mac", "link": {"rtt_ms": 2.0, "kind": None, "line": "RTT 2.0 ms"},
                 "at": own["at"] + 60}
        R.save(rig.state, newer)
        ctx.check("a LAN card of the same age class: the machine's own is read", R.load(rig.state, "fake", "bn-small:9b")["over_lan"] is False)
        R.save(rig.state, {**newer, "ollama_version": "0.40.14"})
        ctx.check("a LAN card on a newer Ollama: it is read", R.load(rig.state, "fake", "bn-small:9b")["over_lan"] is True)


@test
def test_the_battery_from_a_peer_labels_its_speed_row(ctx: Ctx):
    from halo_harness.local_sched.bundle_fit import _latency
    from tests.helpers.battery_rig import BatteryRig
    with BatteryRig(["bt-coder:30b"]) as rig, over_the_lan():
        p = rig.probe("bt-coder:30b")
        sp = p.get("speed") or {}
        ctx.check(f"the speed row carries the fields, got {sp}", p["ok"] and sp.get("over_lan") is True
                  and sp.get("measured_from") == "mac" and sp["link"]["line"] == "RTT 1.8 ms, wired" and "ttft_ms" in sp)
        ctx.check("the gates are location-free: no LAN field on them", not any(k in p for k in ("over_lan", "measured_from", "link"))
                  and p.get("tools") in ("yes", "no"))
        ms, line = _latency("bt-coder:30b", "fake", rig.state)
        ctx.check(f"the placement latency line says it, got {ms} {line!r}", isinstance(ms, int)
                  and line.endswith("; over the LAN from mac: includes the link)"))
    with BatteryRig(["bt-coder:30b"]) as rig:
        sp = rig.probe("bt-coder:30b").get("speed") or {}
        ctx.check(f"from the machine itself: unlabelled, got {sorted(sp)}", "over_lan" not in sp)


@test
def test_halo_local_bench_from_a_peer(ctx: Ctx):
    from halo_harness.local_bench_cli import cmd_bench
    with BenchRig(["bn-small:9b"]) as rig, over_the_lan():
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cmd_bench(["--host", "fake", "--model", "bn-small:9b", "--yes", "--quick"])
        text = out.getvalue().splitlines()
        ctx.check(f"the cost line with the label, then the offer, then the card's label, got {text[:4]}", code == 0
                  and text[0].startswith("local: ~") and text[0].endswith("no tokens leave the LAN; " + LABEL)
                  and text[1].startswith("a card without the link: `halo host serve` on 127.0.0.1")
                  and any(x.strip() == LABEL for x in text[3:]))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cmd_bench(["--host", "fake", "--model", "bn-small:9b", "--yes", "--quick", "--json"])
        body = out.getvalue()
        cards = json.loads(body[body.index("["):])
        ctx.check(f"--json carries measured_from and link, got {cards[0].get('measured_from')} {cards[0].get('link')}",
                  code == 0 and cards[0]["over_lan"] and cards[0]["measured_from"] == "mac" and cards[0]["link"]["rtt_ms"] == 1.8)
        ctx.check("nothing but the fake was asked", all(r.get("path", "").startswith("/api/") for r in rig.mock.requests))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
