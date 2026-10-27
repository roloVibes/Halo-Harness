"""tests.test_steward_hardware -- Halo 3.3.4.0 R1: the hardware card and
`halo ollama hardware`, on fixture logs (Windows with two starts, a Linux
journal, a Mac, no startup block), fake `/api/*` answers, fake GPU tool
output through the runner seam, a fake ssh transport, and a host where
nothing answers. Never a real server, GPU tool or ssh."""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()

FIX = Path(__file__).resolve().parent / "fixtures" / "ollama_steward"
GIB = 2 ** 30
_ENV_NAMES = ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "BRIDGE_TEST_NO_BACKGROUND_NET", "OLLAMA_HOST", "OLLAMA_API_KEY",
              "HALO_OFFLINE")
NVIDIA_GPUS = "0, NVIDIA GeForce RTX 4090, 23028, 3100\n"
NVIDIA_APPS_WDDM = ("2264, [Insufficient Permissions], [N/A]\n"
                    "5120, C:\\Program Files\\Ollama\\lib\\ollama\\llama-server.exe, [N/A]\n"
                    "6000, C:\\ComfyUI\\python_embeded\\python.exe, [N/A]\n")
NVIDIA_APPS_LINUX = "4100, /usr/local/bin/ollama, 18500\n4200, python3, 5900\n4201, python3, 100\n"


class _Env:
    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in _ENV_NAMES}
        for k in _ENV_NAMES:
            os.environ.pop(k, None)
        self.home = Path(tempfile.mkdtemp(prefix="k1-hw-"))
        os.environ.update({"BRIDGE_TEST_HOME": str(self.home), "BRIDGE_TEST_NO_BACKGROUND_NET": "1"})
        return self

    def __exit__(self, *exc):
        for k, v in self._saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


def _host(url="http://127.0.0.1:11434", ssh=None):
    from halo_harness.providers.ollama import OllamaHost
    return OllamaHost(name="box", url=url, ssh=ssh)


def _api(version="0.40.6", models=None):
    def fake(path):
        if path == "/api/version":
            return {"version": version} if version else None
        return {"models": models or []} if models is not None else None
    return fake


def _runner(answers: dict):
    seen = []

    def run(argv, timeout):
        seen.append(list(argv))
        for key, out in answers.items():
            if key in " ".join(argv):
                return out
        return None
    run.seen = seen
    return run


def _card(**kw):
    from halo_harness.ollama_steward.hardware import hardware_card
    kw.setdefault("runner", _runner({}))
    kw.setdefault("api", _api(None))
    return hardware_card(kw.pop("host", None) or _host(), **kw)


@test
def test_a_windows_log_reads_only_the_newest_start(ctx: Ctx):
    with _Env():
        card = _card(log_path=FIX / "windows-server.txt", platform="win32")
    gpu = (card["gpus"] or [{}])[0]
    s = card["server"]
    ctx.check(f"one GPU, the RTX 4090 on CUDA: {card['gpus']}", len(card["gpus"] or []) == 1 and gpu["library"] == "CUDA"
              and gpu["name"] == "NVIDIA GeForce RTX 4090")
    ctx.check(f"the newest start's free memory (21.0 GiB, not 21.9): {gpu['available_bytes']}",
              abs(gpu["available_bytes"] - 21.0 * GIB) < 0.06 * GIB)
    ctx.check(f"version 0.40.6 (not the older start's 0.40.5): {s['version']}", s["version"] == "0.40.6")
    ctx.check(f"the settings: {s}", s["max_loaded"] == 3 and s["max_loaded_auto"] is True and s["parallel"] == 1
              and s["keep_alive"] == "30m" and s["kv_cache_type"] == "q8_0" and s["flash_attention"] == "on"
              and s["gpu_overhead"] == 0 and s["source"] == "server.log")
    ctx.check(f"RAM from the newest 'system memory' line: {card['ram_bytes']}", abs(card["ram_bytes"] - 63.2 * GIB) < GIB)
    ctx.check("a discrete card is not unified memory", card["unified"] is False)


@test
def test_a_linux_journal_with_two_cards(ctx: Ctx):
    with _Env():
        card = _card(log_path=FIX / "linux-journal.txt", platform="linux")
        text = (FIX / "linux-journal.txt").read_text(encoding="utf-8")
        run = _runner({"journalctl": text})
        from_journal = _card(runner=run, platform="linux")
    s = card["server"]
    ctx.check(f"two GPUs: {card['gpus']}", len(card["gpus"] or []) == 2)
    ctx.check(f"the journal's settings: {s}", s["version"] == "0.40.11" and s["max_loaded"] == 2
              and s["max_loaded_auto"] is False and s["parallel"] == 4 and s["keep_alive"] == "1h"
              and s["kv_cache_type"] == "q4_0" and s["gpu_overhead"] == 512 * 2 ** 20)
    ctx.check(f"flash attention 'false' in the dump reads as auto or off: {s['flash_attention']}",
              s["flash_attention"] == "auto or off")
    ctx.check(f"no log file on Linux -> journalctl -u ollama is read: {run.seen}",
              any(a[:3] == ["journalctl", "-u", "ollama"] for a in run.seen))
    ctx.check(f"the journal gives the same card: {from_journal['server']}", from_journal["server"]["version"] == "0.40.11"
              and len(from_journal["gpus"] or []) == 2)


@test
def test_a_mac_log_is_unified_memory(ctx: Ctx):
    with _Env():
        card = _card(log_path=FIX / "mac-server.txt", platform="darwin")
    gpu = (card["gpus"] or [{}])[0]
    ctx.check(f"Metal, Apple M3 Max, 96 GiB: {gpu}", gpu.get("library") == "Metal" and gpu.get("name") == "Apple M3 Max"
              and gpu.get("total_bytes") == 96 * GIB)
    ctx.check("unified memory", card["unified"] is True)
    ctx.check(f"a negative keep-alive reads 'forever': {card['server']['keep_alive']}", card["server"]["keep_alive"] == "forever")
    ctx.check("keeps 1 model, not automatic", card["server"]["max_loaded"] == 1 and card["server"]["max_loaded_auto"] is False)


@test
def test_a_mac_without_a_log_reads_system_profiler_and_sysctl(ctx: Ctx):
    run = _runner({"system_profiler": "Graphics/Displays:\n    Apple M3 Max:\n      Chipset Model: Apple M3 Max\n"
                                      "      Total Number of Cores: 40\n",
                   "hw.memsize": "103079215104\n", "iogpu.wired_limit_mb": "0\n"})
    with _Env():
        card = _card(runner=run, platform="darwin")
    gpu = (card["gpus"] or [{}])[0]
    ctx.check(f"the chip from system_profiler: {gpu}", gpu.get("name") == "Apple M3 Max" and gpu.get("library") == "Metal")
    ctx.check("unified, RAM from hw.memsize", card["unified"] is True and card["ram_bytes"] == 103079215104)
    ctx.check("free memory is Halo's 70 % estimate, marked so", gpu.get("estimated") is True)


@test
def test_a_log_without_a_startup_block(ctx: Ctx):
    with _Env():
        card = _card(log_path=FIX / "no-startup.txt", platform="win32")
    from halo_harness.ollama_steward.hardware import format_card
    lines = format_card(card)
    ctx.check(f"every server field None: {card['server']}", all(v is None for v in card["server"].values()))
    ctx.check(f"a 'not read' line names the missing block: {lines}",
              any(l.startswith("not read: server.log (no startup block in") for l in lines))


@test
def test_the_api_gives_the_version_and_what_is_loaded(ctx: Ctx):
    models = [{"model": "qwen3-coder:30b", "size": 19 * GIB, "size_vram": 19 * GIB, "expires_at": "2026-10-27T14:00:00Z"},
              {"model": "qwen3.8:27b", "size": 18 * GIB, "size_vram": 16 * GIB, "expires_at": "2026-10-27T14:05:00Z"}]
    with _Env():
        card = _card(api=_api("0.40.6", models), platform="win32")
    from halo_harness.ollama_steward.hardware import format_card
    lines = format_card(card)
    ctx.check(f"version from /api/version: {card['server']}", card["server"]["version"] == "0.40.6"
              and card["server"]["source"] == "/api/version")
    ctx.check(f"two loaded models with expiry: {card['loaded']}", [m["model"] for m in card["loaded"]] ==
              ["qwen3-coder:30b", "qwen3.8:27b"] and card["loaded"][0]["expires"] == "2026-10-27T14:00:00Z")
    loaded = [l for l in lines if l.startswith("loaded: ")]
    ctx.check(f"the loaded line says where each model sits: {loaded}", loaded and "qwen3-coder:30b 19.0 GiB all on the GPU"
              in loaded[0] and "qwen3.8:27b 18.0 GiB 2.0 GiB on the CPU" in loaded[0])


@test
def test_nvidia_smi_is_live_and_names_the_other_users(ctx: Ctx):
    run = _runner({"--query-gpu": NVIDIA_GPUS, "--query-compute-apps": NVIDIA_APPS_WDDM})
    models = [{"model": "qwen3-coder:30b", "size": 15 * GIB, "size_vram": 15 * GIB}]
    with _Env():
        card = _card(log_path=FIX / "windows-server.txt", runner=run, api=_api("0.40.6", models), platform="win32")
    gpu = card["gpus"][0]
    names = [u["name"] for u in card["other_users"] or []]
    ctx.check(f"free memory is nvidia-smi's live 3100 MiB, not the log's: {gpu['available_bytes']}",
              gpu["available_bytes"] == 3100 * 2 ** 20)
    ctx.check(f"Ollama's own llama-server is not an other user: {names}", not any("llama-server" in n for n in names))
    ctx.check(f"python (the ComfyUI case) and a hidden process are: {names}", "python" in names
              and "a process this user cannot see" in names)
    rest = [u for u in card["other_users"] if u["name"].startswith("not Ollama")]
    ctx.check(f"WDDM gives no per-process bytes, so the rest is total - free - Ollama's: {rest}",
              rest and rest[0]["bytes"] == round(22.5 * GIB) - 3100 * 2 ** 20 - 15 * GIB)
    run2 = _runner({"--query-gpu": NVIDIA_GPUS, "--query-compute-apps": NVIDIA_APPS_LINUX})
    with _Env():
        linux = _card(runner=run2, platform="linux")
    ctx.check(f"Linux per-process bytes are summed by name: {linux['other_users']}",
              linux["other_users"] == [{"name": "python3", "bytes": 6000 * 2 ** 20}])


@test
def test_a_remote_host_uses_the_ssh_read(ctx: Ctx):
    ssh = _runner({"--query-gpu": "0, NVIDIA GeForce RTX 3080, 10240, 9000\n", "--query-compute-apps": ""})
    local = _runner({})
    with _Env():
        card = _card(host=_host("http://192.0.2.44:11434", ssh="user@192.0.2.44"), ssh_runner=ssh, runner=local)
    ctx.check(f"the remote card came over ssh: {card['gpus']}", card["gpus"] and card["gpus"][0]["name"] == "NVIDIA GeForce RTX 3080")
    ctx.check("no local tool ran for a remote host", not local.seen)
    ctx.check("the log is not read for a remote host", any(s["reader"] == "server.log" and not s["ok"]
                                                          and "not this machine" in s["detail"] for s in card["sources"]))


@test
def test_a_host_with_nothing_readable(ctx: Ctx):
    from halo_harness.ollama_steward.hardware import format_card, hardware_card
    with _Env() as env:
        before = sorted(p.name for p in env.home.rglob("*"))
        card = hardware_card(_host("http://192.0.2.50:11434"), api=_api(None))
        local_off = hardware_card(_host(), platform="win32")
        after = sorted(p.name for p in env.home.rglob("*"))
    for c in (card, local_off):
        ctx.check(f"every field None: {c}", c["gpus"] is None and c["unified"] is None and c["ram_bytes"] is None
                  and all(v is None for v in c["server"].values()) and c["loaded"] is None and c["other_users"] is None)
        ctx.check("read_at is set", bool(c["read_at"]))
    lines = format_card(card)
    ctx.check(f"one 'not read' line per reader: {lines}", [l.split(" (")[0] for l in lines] ==
              ["not read: server.log", "not read: /api/version and /api/ps", "not read: ssh GPU read"])
    ctx.check(f"background reads off -> nothing runs: {format_card(local_off)}",
              "not read: nvidia-smi / system_profiler (background reads are off)" in format_card(local_off))
    ctx.check(f"the card writes nothing under the home: {after}", before == after)


@test
def test_halo_ollama_hardware_prints_lines_and_json(ctx: Ctx):
    from halo_harness.ollama_cli import cmd_ollama
    with _Env():
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = cmd_ollama(["hardware"])
        jout = io.StringIO()
        with contextlib.redirect_stdout(jout):
            rc_json = cmd_ollama(["hardware", "--json"])
        bad = io.StringIO()
        with contextlib.redirect_stderr(bad):
            rc_bad = cmd_ollama(["hardware", "--host", "nope"])
    ctx.check(f"exit 0 and the 'not read' lines: {out.getvalue()!r}", rc == 0 and "not read: /api/version" in out.getvalue())
    data = json.loads(jout.getvalue() or "{}")
    ctx.check(f"--json is the card per host: {list(data)}", rc_json == 0 and data and all("server" in c for c in data.values()))
    ctx.check(f"an unknown --host is exit 1: {bad.getvalue()!r}", rc_bad == 1 and "no configured host" in bad.getvalue())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
