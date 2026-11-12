"""tests.test_pool_members -- Halo 3.3.8.0 R1 deliverable 1: the pool's members (local_pool/members.py), each member's
free VRAM from its host card (local_pool/budget.py) and the link the card now carries (local_pool/link.py), over
tests/helpers/pool_rig.py's scratch home and tests/helpers/host_rig.py's fake host; no model call, never a request
beyond 127.0.0.1:

1. pool.json: add / remove / load, an IP literal accepted, the validation lines (a name twice, a host:port twice, a
   port out of range, a weight of 0, an unknown member), `[2001:db8::1]:50053` parsed;
2. a paired host's member: its GPU, total, usable with the helper, the resident model out, a claim out (a claimed
   model already resident counted once), the card's link "2.5 GbE"; the card wins over a stated VRAM and says so; a
   second member on that machine is refused (its card would count twice);
3. this machine's member (`local`): the local card (ollama_hosts_view.READERS), its resident model out;
4. a bare address: VRAM not read without --vram, "VRAM as you stated it" with it (vram_source stated);
5. the tensor split follows FREE VRAM (27.7 / 22.7 -> 0.5496 / 0.4504), the weights you set when every member has
   one, a member with no VRAM read left out;
6. the link readers per OS behind the RUNNER seam (Windows Get-NetAdapter wired and Wi-Fi, Linux /sys, macOS
   networksetup), unknown under the test flag with no seam, and the card's hardware block carries it;
7. the wireless rule: the adapter type first ("Wi-Fi (adapter)"), the RTT second ("12 ms -- Wi-Fi?").
Run: python -m tests.test_pool_members
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.pool_rig import PoolHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
GIB = 2 ** 30


@test
def test_pool_json_add_remove_and_the_lines(ctx: Ctx):
    from halo_harness.local_pool import members as M
    with PoolHome() as h:
        ok, lines, rows = M.add("worker1", "worker1.local:50052")
        ctx.check(f"added, no card there: the --vram line, got {ok} {lines}", ok and "--vram" in lines[0])
        ok, lines, rows = M.add("worker2", "192.0.2.12", vram_gb=24)
        ctx.check(f"an IP literal is accepted, the port defaults to 50052, got {rows}", ok and rows[1] == {
            "name": "worker2", "host": "192.0.2.12", "rpc_port": 50052, "vram_gb": 24.0})
        got = json.loads(M.path(h.state).read_text(encoding="utf-8"))
        ctx.check(f"pool.json under <state>/pool/, version 1, got {got}", got["version"] == 1 and len(got["members"]) == 2
                  and M.path(h.state).parent.name == "pool")
        for args, kw, want in ((("worker1", "worker3.local"), {}, "worker1 is a member twice"),
                               (("worker3", "192.0.2.12:50052"), {}, "192.0.2.12:50052 is the member worker2 already"),
                               (("worker3", "worker3.local:70000"), {}, "port 70000 is out of range (1-65535)"),
                               (("worker3", "worker3.local"), {"weight": 0}, "a weight is a number above 0"),
                               (("worker3", "worker3.local:abc"), {}, "the port after ':' is a number")):
            ok, lines, _rows = M.add(*args, **kw)
            ctx.check(f"{args} {kw}: refused with {want!r}, got {ok} {lines}", not ok and want in " ".join(lines))
        ctx.check("nothing refused was written", len(M.load(h.state)) == 2)
        ctx.check(f"[2001:db8::1]:50053 parses, got {M.parse_target('[2001:db8::1]:50053')}",
                  M.parse_target("[2001:db8::1]:50053") == ("2001:db8::1", 50053) and M.parse_target("pc-host") == ("pc-host", None))
        ok, lines, rows = M.remove("worker1")
        ctx.check(f"removed, one left, got {ok} {lines}", ok and [r["name"] for r in rows] == ["worker2"]
                  and "1 member left" in lines[0])
        ok, lines, _ = M.remove("nobody")
        ctx.check(f"an unknown member: one line naming the members, got {lines}", not ok and "members: worker2" in lines[0])
        h.config(**{"pool.rpc_port": 50060})
        ok, _l, rows = M.add("worker4", "worker4.local")
        ctx.check(f"pool.rpc_port is the default port, got {rows[-1]}", ok and rows[-1]["rpc_port"] == 50060)


@test
def test_a_paired_hosts_card_gives_the_free_vram(ctx: Ctx):
    from halo_harness.local_pool import members as M
    from halo_harness.local_pool.budget import budgets
    from halo_harness.local_sched import claims_file as CF
    from tests.helpers.host_rig import HostRig, readers
    link = {"type": "wired", "speed_mbps": 2500, "iface": "eth0", "source": "fixture"}
    with HostRig(readers_={**readers(), "link": lambda: dict(link)}) as rig:
        rig.start()
        rig.pair()
        M.add("pc", "pc-host", state_dir=rig.peer)
        CF.put(CF.host_file(rig.home), {"bundle": "voice", "host": "pc", "model": "kokoro:82m", "gb": 1.5})
        CF.put(CF.host_file(rig.home), {"bundle": "coder-first", "host": "pc", "model": "qwen3.8:27b", "gb": 18.0})
        r = budgets(state_dir=rig.peer)[0]
        ctx.check(f"the card through the host: a 24 GB card, 22.0 usable, 18.0 resident out, 1.5 claimed out, 2.5 free, "
                  f"got {r}", r["kind"] == "paired" and r["gpu"] == "a 24 GB card" and r["total_gb"] == 24.0
                  and r["usable_gb"] == 22.0 and r["resident_gb"] == 18.0 and r["resident"] == ["qwen3.8:27b"]
                  and r["claims_gb"] == 1.5 and r["free_gb"] == 2.5 and r["vram_source"] == "card")
        ctx.check(f"the source names the host, the link is the card's, got {r['source']!r} {r['link_word']!r}",
                  "halo host pc-host at 127.0.0.1" in r["source"] and r["link_word"] == "2.5 GbE")
        ctx.check(f"the line says each number, got {r['line']!r}", r["line"].startswith(
            "pc (pc-host:50052): a 24 GB card 24.0 GB -- 22.0 GB usable, 18.0 GB resident (qwen3.8:27b), 1.5 GB claimed, "
            "2.5 GB free; link 2.5 GbE"))
        M.remove("pc", state_dir=rig.peer)
        M.add("pc", "pc-host", vram_gb=30, state_dir=rig.peer)
        r = budgets(state_dir=rig.peer)[0]
        ctx.check(f"the card wins over a stated VRAM and says so, got {r['free_gb']} {r['source']!r}",
                  r["free_gb"] == 2.5 and "wins over the 30 GB you stated" in r["source"])
        ok, lines, _rows = M.add("pc2", "pc-host:50060", state_dir=rig.peer)
        ctx.check(f"a second member on the same paired host is refused (its card would count twice), got {ok} {lines}",
                  not ok and "is the machine of the member pc already" in lines[0])


@test
def test_this_machine_is_read_locally(ctx: Ctx):
    from halo_harness.local_pool import members as M
    from halo_harness.local_pool.budget import budgets
    from halo_harness.studio import ollama_hosts_view as V
    from tests.helpers.ollama_panel_seed import cards
    with PoolHome() as h:
        M.add("me", "local", state_dir=h.state)
        V.READERS["card"] = lambda host: cards()["sagan"]
        try:
            V.reset_cache()
            r = budgets(state_dir=h.state)[0]
        finally:
            V.READERS.pop("card", None)
            V.reset_cache()
        ctx.check(f"local: a 10 GB card, the 7 GB resident model out, 3.0 free, got {r}", r["kind"] == "local"
                  and r["total_gb"] == 10.0 and r["resident_gb"] == 7.0 and r["free_gb"] == 3.0
                  and r["source"].startswith("this machine's card"))


@test
def test_a_bare_address_is_read_as_you_state_it(ctx: Ctx):
    from halo_harness.local_pool import members as M
    from halo_harness.local_pool.budget import budgets
    with PoolHome() as h:
        M.add("worker1", "worker1.local", state_dir=h.state)
        M.add("worker2", "192.0.2.12", vram_gb=11, state_dir=h.state)
        a, b = budgets(state_dir=h.state)
        ctx.check(f"no card, no --vram: not read, the line says how, got {a['line']!r}", a["free_gb"] is None
                  and a["vram_source"] == "unknown" and "add --vram <GB> to state it" in a["line"])
        ctx.check(f"--vram 11: VRAM as you stated it, got {b}", b["free_gb"] == 11.0 and b["vram_source"] == "stated"
                  and "VRAM as you stated it" in b["line"])


@test
def test_the_tensor_split_follows_free_vram(ctx: Ctx):
    from halo_harness.local_pool.budget import tensor_split, split_from
    from tests.helpers.pool_rig import rows
    two = rows(27.7, 22.7)
    ctx.check(f"27.7 / 22.7 GB free -> 0.5496 / 0.4504, got {tensor_split(two)}", tensor_split(two) == [0.5496, 0.4504]
              and split_from(two) == "free VRAM")
    three = rows(24.0, 24.0, 11.0) + [{"name": "worker4", "free_gb": None}]
    ctx.check(f"24 / 24 / 11 and one unread member -> 0.4068 / 0.4068 / 0.1864, got {tensor_split(three)}",
              tensor_split(three) == [0.4068, 0.4068, 0.1864])
    weighted = [{**r, "weight": w} for r, w in zip(rows(27.7, 22.7), (60, 40))]
    ctx.check(f"every member's weight set: 0.6 / 0.4, got {tensor_split(weighted)}", tensor_split(weighted) == [0.6, 0.4]
              and split_from(weighted) == "the weights you set")
    ctx.check("nothing read: no split", tensor_split([{"name": "x", "free_gb": None}]) == [])


WIN_WIRED = json.dumps({"Name": "Ethernet", "InterfaceDescription": "Realtek PCIe 2.5GbE", "PhysicalMediaType": "802.3",
                        "NdisPhysicalMedium": 14, "LinkSpeed": "2.5 Gbps", "ReceiveLinkSpeed": 2500000000})
WIN_WIFI = json.dumps([{"Name": "Wi-Fi", "InterfaceDescription": "Wireless LAN adapter", "PhysicalMediaType": "Native 802.11",
                        "NdisPhysicalMedium": 9, "LinkSpeed": "866.7 Mbps", "ReceiveLinkSpeed": 866700000}])
IP_ADDR = "2: eth0    inet 192.0.2.21/24 brd 192.0.2.255 scope global eth0\\       valid_lft forever\n"
MAC_IFCONFIG = "lo0: flags=8049<UP>\n\tinet 127.0.0.1 netmask 0xff000000\nen0: flags=8863<UP>\n\tinet 192.0.2.31 netmask 0xffffff00\n"
MAC_PORTS = "Hardware Port: Ethernet\nDevice: en1\n\nHardware Port: Wi-Fi\nDevice: en0\nEthernet Address: aa\n"
MAC_ETH_PORTS = "Hardware Port: Thunderbolt Ethernet\nDevice: en0\n"
MAC_MEDIA = "en0: flags=8863<UP>\n\tmedia: autoselect (1000baseT <full-duplex>)\n\tstatus: active\n"


def _runner(system: str, out: dict, files: "dict | None" = None, exists=()) -> dict:
    return {"system": lambda: system, "run": lambda argv: out.get(argv[0] if argv[0] != "ifconfig" or len(argv) == 1
                                                                  else "ifconfig " + argv[1]),
            "read": lambda p: (files or {}).get(p), "exists": lambda p: p in exists}


@test
def test_the_link_readers_per_os(ctx: Ctx):
    from halo_harness.local_pool import link as L
    with PoolHome():
        ctx.check(f"the test flag, no seam: unknown, got {L.read('192.0.2.21')}", L.read("192.0.2.21")["type"] == "unknown"
                  and L.read("192.0.2.21")["source"] == "not read in tests")
        cases = (("windows wired", _runner("windows", {"powershell": WIN_WIRED}), "192.0.2.21", "wired", 2500, "2.5 GbE"),
                 ("windows Wi-Fi", _runner("windows", {"powershell": WIN_WIFI}), "192.0.2.21", "wireless", 866,
                  "Wi-Fi (adapter)"),
                 ("linux wired", _runner("linux", {"ip": IP_ADDR}, {"/sys/class/net/eth0/speed": "1000\n"}), "192.0.2.21",
                  "wired", 1000, "1 GbE"),
                 ("linux wireless", _runner("linux", {"ip": IP_ADDR}, {}, ("/sys/class/net/eth0/wireless",)), "192.0.2.21",
                  "wireless", None, "Wi-Fi (adapter)"),
                 ("macos Wi-Fi", _runner("darwin", {"ifconfig": MAC_IFCONFIG, "networksetup": MAC_PORTS}), "192.0.2.31",
                  "wireless", None, "Wi-Fi (adapter)"),
                 ("macos ethernet", _runner("darwin", {"ifconfig": MAC_IFCONFIG, "networksetup": MAC_ETH_PORTS,
                                                       "ifconfig en0": MAC_MEDIA}), "192.0.2.31", "wired", 1000, "1 GbE"),
                 ("linux, no interface carries it", _runner("linux", {"ip": IP_ADDR}), "192.0.2.99", "unknown", None,
                  "unknown"))
        for label, runner, addr, kind, speed, word in cases:
            L.RUNNER.clear()
            L.RUNNER.update(runner)
            got = L.read(addr)
            ctx.check(f"{label}: {kind} {speed} {word!r}, got {got} {L.word(got)!r}", got["type"] == kind
                      and got["speed_mbps"] == speed and L.word(got) == word)
        L.RUNNER.clear()
        from halo_harness.peers.capabilities_host import hardware
        hw = hardware(Path("."), spawn=False)
        ctx.check(f"the capability catalog's hardware carries the link, got {hw.get('link')}",
                  hw.get("link") == {"type": "unknown", "speed_mbps": None})


@test
def test_the_adapter_type_beats_the_rtt(ctx: Ctx):
    from halo_harness.local_pool.scan import wifi_word
    ctx.check("a wireless adapter says Wi-Fi for certain, whatever the RTT",
              wifi_word({"link": {"type": "wireless"}, "rtt_alive": True, "rtt_ms": 0.4}) == "Wi-Fi (adapter)")
    ctx.check("past 10 ms an RTT only suspects it", wifi_word({"link": {"type": "unknown"}, "rtt_alive": True,
                                                               "rtt_ms": 12.4}) == "12 ms -- Wi-Fi?")
    ctx.check("a quick wired RTT", wifi_word({"link": {"type": "wired"}, "rtt_alive": True, "rtt_ms": 0.42}) == "0.4 ms")
    ctx.check("no scan yet", wifi_word({"link": {}, "rtt_alive": None}) == "not probed (Scan)")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
