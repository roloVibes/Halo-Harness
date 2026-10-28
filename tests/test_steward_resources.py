"""tests.test_steward_resources -- Halo 3.3.5.0 R1: the Local tab's live samples
(halo_harness/ollama_steward/resources.py, resources_readers.py, resources_system.py, resources_share.py):

1. the readers on fixture outputs per OS: nvidia-smi as this build PC really answers it (one card, `0, 30, 23028, 28`;
   every compute process `[N/A]` under Windows WDDM), two NVIDIA cards, rocm-smi's JSON, a Mac's ioreg + sysctl +
   memory_pressure (GPU use n/a when the registry does not say it), /proc/meminfo and /proc/stat, the Windows
   GlobalMemoryStatusEx / GetSystemTimes seams; nothing runs under the test flag without a seam;
2. the sampler on a fake clock: one sample a second per host, the holder from /api/ps when the driver names no
   bytes (and the compute process when it does), `others`, the `resources` frames, the 5-minute store, the
   recent file and `read_recent` with `lan_url`; the watch lease and its owners;
3. the fit planner's "others" share reads the newest sample when it is newer than the card;
4. the hub's 5-minute store through the fleet rig: a member's samples ride its ledger push and land under the hub's
   own name for the host; GET /api/local/resources and /api/local/hosts on the hub show them.
Never a real tool, a real server or a model call.
Run: python -m tests.test_steward_resources
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
GIB, MIB = 2 ** 30, 2 ** 20
PC_NVIDIA = "0, 30, 23028, 28\n"  # this build PC's real answer (utilization %, MiB used, MiB total, deg C)
PC_APPS = "2264, [Insufficient Permissions], [N/A]\n29196, C:\\Program Files\\Some App\\app.exe, [N/A]\n"
ROCM = json.dumps({"card0": {"GPU use (%)": "41", "VRAM Total Memory (B)": str(16 * GIB),
                             "VRAM Total Used Memory (B)": str(6 * GIB), "Temperature (Sensor edge) (C)": "55.0"}})
IOREG = '| "PerformanceStatistics" = {"In use system memory"=12884901888,"Alloc system memory"=20000000000}\n'


def seams(answers: dict, platform: str = "linux", files: "dict | None" = None, win=None):
    from halo_harness.ollama_steward.resources_readers import Seams
    return Seams(runner=lambda argv, t: answers.get(argv[0] if argv[0] != "nvidia-smi" else argv[1].split("=")[0]),
                 read_file=lambda p: (files or {}).get(p), platform=platform, win=win, injected=True)


@test
def test_the_gpu_readers_per_os(ctx: Ctx):
    from halo_harness.ollama_steward import resources_readers as rr
    g, why = rr.gpu(seams({"--query-gpu": PC_NVIDIA}, "win32"))
    ctx.check(f"this PC's nvidia-smi: 0 %, 30 MiB of 23,028 MiB, 28 C, got {g} {why}",
              g == {"gpu": 0, "vram_used": 30 * MIB, "vram_total": 23028 * MIB, "temp": 28.0, "cards": 1,
                    "source": "nvidia-smi --query-gpu"})
    two = rr.parse_nvidia("10, 1000, 24564, 40\n50, 3000, 24564, 70\n")
    ctx.check(f"two cards: the memory summed, the use averaged, the hottest, got {two}",
              two["gpu"] == 30 and two["vram_used"] == 4000 * MIB and two["temp"] == 70.0 and two["cards"] == 2)
    ctx.check("a [N/A] field is unknown, not zero", rr.parse_nvidia("[N/A], 100, 8192, [N/A]\n")["gpu"] is None)
    apps, _ = rr.apps(seams({"--query-compute-apps": PC_APPS}, "win32"))
    ctx.check(f"WDDM: every process's bytes unknown, a hidden name None, got {apps}",
              [a["bytes"] for a in apps] == [None, None] and apps[0]["name"] is None)
    g, _ = rr.gpu(seams({"rocm-smi": ROCM}))
    ctx.check(f"rocm-smi's JSON when nvidia-smi is absent, got {g}", g and g["gpu"] == 41 and g["vram_used"] == 6 * GIB
              and g["vram_total"] == 16 * GIB and g["temp"] == 55.0 and g["source"] == "rocm-smi --json")
    g, why = rr.gpu(seams({}))
    ctx.check(f"neither tool: no reading and why, got {g} {why!r}", g is None and "nvidia-smi or rocm-smi" in why)
    mac = seams({"sysctl": str(36 * GIB), "ioreg": IOREG, "powermetrics": None}, "darwin")
    g, _ = rr.gpu(mac)
    ctx.check(f"a Mac: ioreg's memory in use over hw.memsize, unified, GPU use n/a without powermetrics, got {g}",
              g and g["vram_used"] == 12884901888 and g["vram_total"] == 36 * GIB and g["unified"] and g["gpu"] is None
              and g["gpu_na"] is True and "ioreg" in g["source"])
    g, _ = rr.gpu(seams({"sysctl": str(36 * GIB), "ioreg": IOREG.replace("}", ',"Device Utilization %"=17}')}, "darwin"))
    ctx.check(f"a Mac whose registry says the utilization, got {g and g['gpu']}", g and g["gpu"] == 17)
    off = rr.Seams(runner=lambda *a: PC_NVIDIA, platform="linux")
    ctx.check("under the test flag a reader with no injected seam runs nothing", rr.gpu(off)[0] is None)


@test
def test_ram_and_cpu_per_os(ctx: Ctx):
    from halo_harness.ollama_steward import resources_system as rs
    meminfo = "MemTotal:       65536000 kB\nMemFree:  1000 kB\nMemAvailable:   16384000 kB\n"
    r, _ = rs.ram(seams({}, "linux", {"/proc/meminfo": meminfo}))
    ctx.check(f"Linux: MemTotal - MemAvailable, got {r}", r["used"] == (65536000 - 16384000) * 1024 and r["total"] == 65536000 * 1024)
    r, _ = rs.ram(seams({}, "win32", win={"mem": lambda: (40 * GIB, 64 * GIB)}))
    ctx.check(f"Windows: GlobalMemoryStatusEx, got {r}", r == {"used": 40 * GIB, "total": 64 * GIB, "source": "GlobalMemoryStatusEx"})
    r, _ = rs.ram(seams({"sysctl": str(32 * GIB), "memory_pressure": "System-wide memory free percentage: 75%\n"}, "darwin"))
    ctx.check(f"a Mac: memory_pressure's free share of hw.memsize, got {r}", r and r["used"] == 8 * GIB and r["total"] == 32 * GIB)
    stat = iter(["cpu  100 0 100 800 0 0 0\n", "cpu  200 0 200 1600 0 0 0\n"])
    cpu = rs.Cpu(seams({}, "linux", None))
    cpu.seams.read_file = lambda p: next(stat)
    first, why = cpu.read()
    second, src = cpu.read()
    ctx.check(f"Linux CPU: the first read None, then the busy share between two, got {first} {why!r} {second} {src}",
              first is None and second == 20.0 and src == "/proc/stat")
    times = iter([(800, 900, 100), (1600, 1800, 200)])
    wcpu = rs.Cpu(seams({}, "win32", win={"times": lambda: next(times)}))
    wcpu.read()
    got = wcpu.read()
    ctx.check(f"Windows CPU: GetSystemTimes (the kernel time holds the idle), got {got}", got == (20.0, "GetSystemTimes"))
    ctx.check("a Mac's CPU: ps over the core count", rs.Cpu(seams({"ps": "10.0\n20.0\n"}, "darwin")).read()[1].startswith("ps -A"))


@test
def test_the_sampler_on_a_fake_clock(ctx: Ctx):
    from halo_harness.ollama_steward import resources as R
    from halo_harness.ollama_steward.resources_share import read_recent
    from halo_harness.providers.ollama import OllamaHost
    R.STORE.clear()
    state = Path(tempfile.mkdtemp(prefix="l1_res-")) / ".halo"
    host = OllamaHost(name="box", url="http://127.0.0.1:11434")
    t = [1000.0]
    frames: list = []
    ps = {"models": [{"model": "qwen3.5:9b", "size": 7 * GIB, "size_vram": 7 * GIB, "context_length": 32768}]}
    s = R.Sampler(state, publish=frames.append, clock=lambda: t[0], hosts=lambda: [host], ps=lambda h: ps,
                  seams=seams({"--query-gpu": "55, 9000, 24564, 61\n", "--query-compute-apps": "4242, ollama, [N/A]\n"},
                              "linux", {"/proc/meminfo": "MemTotal: 1048576 kB\nMemAvailable: 524288 kB\n",
                                        "/proc/stat": "cpu  1 0 1 8 0 0 0\n"}))
    for _ in range(400):
        s.sample_once()
        t[0] += 1.0
    rows = R.STORE.recent("box", now=t[0])
    last = rows[-1]
    ctx.check(f"one sample a second, the last 5 minutes kept, got {len(rows)}", 295 <= len(rows) <= 301)
    ctx.check(f"the sample's figures, got {({k: last[k] for k in ('gpu', 'vram_used', 'vram_total', 'temp', 'ram_used')})}",
              last["gpu"] == 55 and last["vram_used"] == 9000 * MIB and last["temp"] == 61.0 and last["ram_used"] == 512 * MIB)
    ctx.check(f"WDDM-style [N/A] bytes: the holder is /api/ps's model, got {last['holder']} {last['sources']['holder']}",
              last["holder"] == "qwen3.5:9b" and last["sources"]["holder"].startswith("/api/ps"))
    ctx.check(f"others: VRAM used minus Ollama's models, got {last['others']}", last["others"] == 9000 * MIB - 7 * GIB)
    ctx.check(f"a `resources` frame a sample, got {len(frames)} {frames[-1]['event']}", len(frames) == 400 and frames[-1]["event"] == "resources")
    with_bytes = R.build_sample(host, 1.0, {"vram_used": 10 * GIB, "vram_total": 24 * GIB}, "", [
        {"pid": 1, "name": "ComfyUI", "bytes": 3 * GIB}, {"pid": 2, "name": "ollama", "bytes": 6 * GIB}], ps["models"],
        None, "", None, "")
    ctx.check(f"bytes per process: the biggest holder named, Ollama's own process left to its models, got {with_bytes['holders']}",
              [h["name"] for h in with_bytes["holders"]] == ["qwen3.5:9b", "ComfyUI"] and with_bytes["others"] == 3 * GIB)
    got = read_recent(state, t[0] - 30, lan="192.0.2.40")
    ctx.check(f"the recent file: the last minute, newer than the cursor, with lan_url, got {len(got)} {got and got[-1]['lan_url']}",
              0 < len(got) <= 31 and got[-1]["lan_url"] == "http://192.0.2.40:11434")
    R.STORE.clear()


@test
def test_the_watch_lease_and_the_planner_share(ctx: Ctx):
    from halo_harness.ollama_steward import resources as R
    from halo_harness.ollama_steward.fit import card_budget
    R.stop_all()
    st = R.want(None, "tab", True, lease=30, start=False)
    ctx.check(f"the tab's lease turns it on, got {st}", st["on"] and st["owners"] == ["tab"])
    ctx.check("a lease that ran out turns it off", not R.wanted(now=10 ** 12))
    R.want(None, "job", True, lease=None, start=False)
    ctx.check("the job's hold has no end", R.wanted(now=10 ** 12) and R.status()["owners"] == ["job"])
    R.want(None, "job", False)
    ctx.check("released: off", not R.wanted())
    import time
    card = {"gpus": [{"total_bytes": 24 * GIB}], "other_users": [{"name": "ComfyUI", "bytes": 1 * GIB}],
            "read_at": "2000-01-01T00:00:00Z", "server": {}}
    ctx.check("no sample: the card's own others", card_budget(card, "pc")["others"] == 1 * GIB)
    R.STORE.add({"host": "pc", "t": time.time(), "others": 5 * GIB})
    b = card_budget(card, "pc")
    ctx.check(f"a newer sample: its others (ComfyUI started since the card was read), got {b['others']} {b['others_from']}",
              b["others"] == 5 * GIB and b["others_from"] == "sample" and b["budget"] == 19 * GIB)
    ctx.check("another host keeps the card's", card_budget(card, "samus")["others"] == 1 * GIB)
    R.STORE.clear()


@test
def test_the_hubs_store_through_the_fleet_rig(ctx: Ctx):
    from tests.helpers.fleet_hub_rig import HubRig, wait_for
    from tests.helpers.local_seed import member_samples
    from halo_harness.fleet import hub as fleet_hub, ollama_share
    from halo_harness.ollama_steward import resources as R
    R.STORE.clear()
    saved = (ollama_share.FLUSH_S, ollama_share.CHECK_S, fleet_hub.lan_address)
    ollama_share.FLUSH_S, ollama_share.CHECK_S = 0.2, 0.05
    fleet_hub.lan_address = lambda: "192.0.2.30"
    try:
        with HubRig() as rig:
            (rig.home_a / "config.json").write_text(json.dumps({"fleet": {"name": "alice@hub"}, "ollama": {
                "hosts": [{"name": "mac", "url": "http://192.0.2.30:11434"}]}}), encoding="utf-8")
            rig.join()
            from halo_harness.config.paths import bridge_home
            from halo_harness.ollama_steward import ledger
            b = Path(bridge_home())
            ledger.record_call(b, {"host": {"name": "pc", "url": "http://192.0.2.10:11434"}, "model": "m", "status": 200})
            (b / "ollama" / "resources-recent.json").write_text(json.dumps({"at": 0, "samples": member_samples()}), encoding="utf-8")
            _c, act = rig.session()
            wait_for(lambda: rig.member_session(act.session_id))
            got = wait_for(lambda: R.STORE.recent("mac"), 10)
            ctx.check(f"the member's samples reached the hub under its own name for the host, got {len(got or [])}",
                      bool(got) and got[-1]["from"] == "bob@member" and got[-1]["member_host"] == "local")
            status, body = rig.api("GET", "local/resources?host=mac")
            ctx.check(f"GET /api/local/resources on the hub shows them, got {status} {len(body.get('samples') or [])}",
                      status == 200 and len(body.get("samples") or []) >= 10)
            status, body = rig.api("GET", "local/hosts")
            mac = next((h for h in body.get("hosts") or [] if h["name"] == "mac"), {})
            ctx.check(f"its card: through the member that serves it, got {mac.get('controls')}",
                      status == 200 and mac.get("controls", {}).get("member") == "bob@member")
    finally:
        ollama_share.FLUSH_S, ollama_share.CHECK_S, fleet_hub.lan_address = saved
        R.STORE.clear()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
