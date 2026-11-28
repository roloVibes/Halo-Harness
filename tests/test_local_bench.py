"""tests.test_local_bench -- Halo 3.3.6.0 R5 deliverables 1-3, the bench (providers/local_bench.py,
local_bench_runs.py, local_bench_cli.py) on the scripted fake Ollama (tests/helpers/mock_ollama_bench.py: realistic
durations, a load per window, a spill past the model's GPU limit), no model call, nothing sent but to the fake:

1. the battery: the cold load from the first load's `load_duration`, one untimed warm-up per load, then per window
   (8k, 32k, the planner's ceiling) a ~60 % prompt and a 256-token reply: prompt tok/s, tok/s, TTFT, size_vram,
   on_gpu; the scripted spill at the ceiling; `max_gpu_window` beside the planner's number; `reserve_floor` from
   128/256/512 (a thinking model needs 512); `--quick` = the ceiling alone;
2. the store: cache[digest]["speed_card"][host], the battery profile's speed mirroring the ceiling row, the measured
   facts beside it untouched;
3. where it shows: the card's table and the "where it sits" GPU window, the badge ("fits, ~41 tok/s at 32k"), the
   stale mark ("measured on 0.40.6", a changed tag), placement preferring the bench's window, the KV dial verified at
   the type in force, the Library and Hosts rows;
4. it waits (one line, nothing sent) while the host had a call in the last minute or a session uses it; the cost
   line; `halo local bench` / `halo models bench`.
Run: python -m tests.test_local_bench
"""
from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
ensure_default_provider_credentials()

from tests.helpers import mock_ollama_bench as MB  # noqa: E402
from tests.helpers.bench_rig import BenchRig  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


@test
def test_the_battery_on_the_fake(ctx: Ctx):
    with BenchRig() as rig:
        lines: list = []
        c = rig.bench("bn-coder:30b", on_line=lines.append)
        ws = [w["window"] for w in c["windows"]]
        ctx.check(f"three windows: 8k, 32k, the planner's ceiling, got {ws} (ceiling {c['planner_window']})",
                  c["ok"] and ws[:2] == [8192, 32768] and ws[2] == c["planner_window"] > 32768)
        ctx.check(f"the cold load from the first load, got {c['cold_load_s']}", c["cold_load_s"] == 21.0)
        calls = rig.mock.bench_calls
        timed = [x for x in calls if x[2] == 256]
        ctx.check(f"every window's first call is the untimed warm-up (num_predict 8), got {calls[:6]}",
                  [x[2] for x in calls[:6]] == [8, 256, 8, 256, 8, 256] and all(x[3] for x in calls[:6:2])
                  and not any(x[3] for x in timed))
        w8, w32, top = c["windows"]
        ctx.check(f"8k and 32k on the GPU with real rates (never the warm-up's 5.7), got {w8} {w32}",
                  w8["on_gpu"] and w32["on_gpu"] and w8["tok_s"] > 150 and w8["prompt_tok_s"] > 2000
                  and w8["ttft_ms"] < w32["ttft_ms"] and w8["size_vram"] == w8["size"])
        ctx.check(f"the scripted spill at the ceiling, got {top}", top["on_gpu"] is False and top["size_vram"] < top["size"]
                  and top["tok_s"] < 50)
        ctx.check(f"max_gpu_window 32k beside the planner's number, got {c['max_gpu_window']} {c['planner_window']}",
                  c["max_gpu_window"] == 32768 and c["planner_window"] != 32768)
        ctx.check(f"the reserve: 128 cut, 256 not, got {c['reserve_probes']} -> {c['reserve_floor']}",
                  c["reserve_floor"] == 256 and [p["cut"] for p in c["reserve_probes"]] == [True, False]
                  and all(p["window"] == 32768 for p in c["reserve_probes"]))
        prompts = [b for b in rig.chats() if (b.get("options") or {}).get("num_predict") == 256]
        sizes = [len(b["messages"][-1]["content"]) for b in prompts[:3]]
        ctx.check(f"each timed prompt ~60 % of its window (4 chars a token), got {sizes}",
                  all(abs(s / (w * 0.6 * 4) - 1) < 0.05 for s, w in zip(sizes, ws)))
        ctx.check(f"the exact window, reply room and keep_alive on the wire, got {prompts[0].get('options')}",
                  prompts[0]["options"]["num_ctx"] == 8192 and prompts[0]["keep_alive"] == "10m")
        ctx.check(f"one line per window as it lands, the warm-up named, got {lines}",
                  any("warming (the first call after a load is never timed)" in x for x in lines)
                  and any(x.startswith("32k: prompt") and "on the GPU" in x for x in lines)
                  and any("spills to the CPU" in x for x in lines))
        ctx.check(f"a full bench on realistic durations: {MB.script_seconds(rig.mock)} s of the card",
                  200 < MB.script_seconds(rig.mock) < 900)
        t = rig.bench("bn-thinker:9b")
        ctx.check(f"a long reply needs 512, got {t['reserve_floor']}", t["reserve_floor"] == 512)
        q = rig.bench("bn-small:9b", quick=True)
        ctx.check(f"--quick: the ceiling alone, got {[w['window'] for w in q['windows']]}",
                  q["quick"] and [w["window"] for w in q["windows"]] == [q["planner_window"]] and q["reserve_floor"] == 256)


@test
def test_the_store_and_the_mirror(ctx: Ctx):
    from halo_harness.providers.local_bench_runs import all_cards, load
    from halo_harness.providers.ollama_capability import save_profile
    with BenchRig(["bn-coder:30b"]) as rig:
        save_profile(rig.state, {"model": "bn-coder:30b", "host": "fake", "digest": "sha256:bn-coder-30b", "probe_set": "battery-2",
                                 "probed_at": 1.0, "tools": "yes", "speed": {"tok_s": 99.0, "at_window": 8192}})
        from halo_harness.providers.ollama_capability import load_capability_cache, save_capability_cache
        cache = load_capability_cache(rig.state)
        cache["sha256:bn-coder-30b"]["measured"] = {"fake": {"facts": {"tok_s": {"value": 77.0, "source": "the ledger"}}, "at": 1.0}}
        save_capability_cache(rig.state, cache)
        entry0 = rig.cache()["sha256:bn-coder-30b"]
        c = rig.bench("bn-coder:30b")
        e = rig.cache()["sha256:bn-coder-30b"]
        card = e["speed_card"]["fake"]
        ctx.check(f"the card under its digest and host, got {sorted(card)}", card["max_gpu_window"] == 32768
                  and card["ollama_version"] == "0.40.13" and len(card["windows"]) == 3 and "ok" not in card)
        sp = e["battery"]["fake"]["speed"]
        ctx.check(f"the profile's speed mirrors the ceiling row, got {sp}", sp["from"] == "bench"
                  and sp["at_window"] == c["windows"][-1]["window"] and sp["tok_s"] == c["windows"][-1]["tok_s"])
        ctx.check("the measured facts are not written over", e.get("measured") == entry0["measured"] and e["measured"])
        ctx.check("load and all_cards find it", load(rig.state, "fake", "bn-coder:30b")["digest"] == "sha256:bn-coder-30b"
                  and len(all_cards(rig.state, "fake")) == 1)


@test
def test_where_it_shows_and_the_stale_mark(ctx: Ctx):
    from halo_harness.models_library.rows import _bench_speed
    from halo_harness.providers import local_bench_runs as R
    from halo_harness.providers.fit_meter import speed_word
    from halo_harness.providers.kv_dial import dial_for
    from halo_harness.providers.model_card_blocks import block_lines
    from halo_harness.providers.placement import usable_window
    with BenchRig(["bn-coder:30b"]) as rig:
        rig.bench("bn-coder:30b")
        row = {**MB.row("bn-coder:30b"), "model_info": MB.MODELS["bn-coder:30b"]["info"]}
        card = {"kind": "ollama", "host": "fake", "name": "bn-coder:30b", "blocks": {"sits": {"chip": "coder", "chips": ["coder"],
                                                                                              "mark": "verified"}}}
        R.with_speed_card(card, rig.state, row=row)
        sc = card["speed_card"]
        ctx.check(f"the card's speed card, fresh, got {sc['stale']!r}", sc["stale"] == "" and sc["max_gpu_window"] == 32768)
        measured = [x["text"] for x in card["blocks"]["measured"]]
        ctx.check(f"the Measured block's three-window table, got {measured}",
                  measured[0].startswith("speed card (the bench") and any(x.startswith("8k: prompt") for x in measured)
                  and any("stays on the GPU up to 32k (the planner says" in x for x in measured)
                  and any(x == "reply reserve: at least 256 (a 256-token reply was cut below it)" for x in measured))
        out = block_lines(card["blocks"])
        ctx.check(f"where it sits cites the GPU window, got {out}", out[0] == "  where it sits: coder · on the GPU up to 32k (the bench)")
        word = speed_word("fits", card["speed"])
        ctx.check(f"the badge reads the ceiling row, got {word!r}", word.startswith("fits, ~") and word.endswith("k"))
        from halo_harness.studio import ollama_hosts_view as V
        rig.card["server"]["version"] = "0.40.14"
        V.card_of(rig.host)  # the Ollama panel's cache, as Studio's rows read it
        R.with_speed_card(card, rig.state, row=row)
        ctx.check(f"a newer Ollama marks it stale, got {card['speed']['stale']!r} {speed_word('spill', card['speed'])!r}",
                  card["speed"]["stale"] == "measured on 0.40.13" and speed_word("spill", card["speed"]).endswith("(measured on 0.40.13)"))
        ctx.check("a changed tag marks it stale", R.stale(sc, digest="sha256:other") == "measured on an older build of this tag")
        ctx.check("placement prefers the bench's window", usable_window({"host": "fake", "model": "bn-coder:30b",
                                                                         "window": {"usable": 122880}}, rig.state) == 32768)
        d = dial_for(rig.host, "bn-coder:30b", state_dir=rig.state, card=rig.card, row=row)
        ctx.check(f"the KV dial: the type in force verified, the rest computed, got {d['text']!r} {d['rows']}",
                  "q8_0 verified by the bench up to 32k, the rest computed" in d["text"]
                  and {r["kv"]: r["from"] for r in d["rows"]}.get("f16") == "computed" and d["apply"]["to"] == 32768)
        ctx.check("the Library row's badge speed", (_bench_speed({"source": "ollama", "tag_or_file": "bn-coder:30b"}, "fake")
                                                    or {}).get("from") == "bench")
        from halo_harness.studio.local_hosts_view import _benched
        ctx.check("the Hosts page's loaded row", (_benched([{"model": "bn-coder:30b"}], "fake")[0]["bench"] or "").endswith("(the bench)"))


@test
def test_it_waits_while_the_card_is_busy_and_the_cost_line(ctx: Ctx):
    from halo_harness.providers.local_bench import cost_line, estimate
    from tests.helpers.steward_seed import line
    with BenchRig(["bn-small:9b"]) as rig:
        rig.home.calls(line(host={"name": "fake", "url": rig.mock.base_url}, model="bn-small:9b", ago=10))
        got = rig.bench("bn-small:9b")
        ctx.check(f"a call 10 s ago: one line, nothing sent, got {got.get('say')!r}", not got["ok"]
                  and got["say"].startswith("fake answered a call 10 s ago (bn-small:9b)") and not rig.chats())
    with BenchRig(["bn-small:9b"]) as rig:
        got = rig.bench("bn-small:9b", sessions=lambda: [{"session_id": "s-1", "model": "ol:qwen3.5:9b@fake", "pid": -1}])
        ctx.check(f"a session on the host: one line, got {got.get('say')!r}", not got["ok"]
                  and got["say"].startswith("session s-1 is using ol:qwen3.5:9b@fake on fake") and not rig.chats())
        n, said = estimate(rig.host, "bn-small:9b", card=rig.card, state_dir=rig.state)
        ctx.check(f"the cost line: time and a busy card, no dollars, got {said!r}",
                  said == cost_line("fake", n) == f"local: ~{n} min on fake, the card is busy meanwhile, writes the speed "
                  "card; no tokens leave this machine" and "$" not in said)
        from halo_harness.providers.local_bench import bench
        from halo_harness.providers.ollama import OllamaHost
        far = bench(OllamaHost(name="lan", url="http://192.0.2.10:11434"), "x", state_dir=rig.state, sessions=lambda: [])
        ctx.check(f"a real address under the test flag: nothing sent, got {far.get('say')!r}", not far["ok"] and not rig.chats())


@test
def test_halo_local_bench_and_models_bench(ctx: Ctx):
    from halo_harness.catalog_cli import cmd_models
    from halo_harness.local_bench_cli import cmd_bench
    with BenchRig(["bn-small:9b", "bn-thinker:9b"]) as rig:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cmd_bench(["--host", "fake", "--model", "bn-small:9b", "--yes", "--quick"])
        text = out.getvalue().splitlines()
        ctx.check(f"the cost line first, the lines, then the speed card, got {text}", code == 0
                  and text[0].startswith("local: ~") and text[1] == "bn-small:9b on fake:"
                  and any("warming" in x for x in text) and any(x.strip().startswith("speed card (the bench") for x in text))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cmd_models(["bench", "--host", "fake", "--all", "--yes", "--quick"])
        heads = [x for x in out.getvalue().splitlines() if x.endswith(" on fake:")]
        ctx.check(f"halo models bench --all: every installed model, largest first, got {heads}", code == 0 and len(heads) == 2)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cmd_bench(["--host", "fake"])
        ctx.check(f"no model named: it says how, got {out.getvalue()!r}", code == 2 and "--model M" in out.getvalue())


# ---- 3.6.0.25 T: the sweep (providers/local_sweep.py, local_sweep_run.py) on the fake --------------------------------

GIB, MIB = 2 ** 30, 2 ** 20


def _mem(rig, total: int):
    """The card's memory as this machine's probe would read it: the fake's /api/ps size_vram against `total`."""
    def read():
        used = sum(int(e.get("size_vram") or 0) for e in (rig.mock.ps_response or {}).get("models") or [])
        return {"used": used, "free": total - used, "total": total}
    return read


def _sweep(rig, name: str, **kw):
    from halo_harness.providers.local_sweep_run import sweep
    kw.setdefault("sessions", lambda: [])
    kw.setdefault("memory", _mem(rig, 24 * GIB))
    return sweep(rig.host, name, state_dir=rig.state, card=rig.card, **kw)


def _ws(got) -> list:
    return [r["window"] for r in got["record"]["windows"]]


def _loads(rig, name: str) -> int:
    return sum(1 for x in rig.mock.bench_calls if x[0] == name and x[2] == 8)


@test
def test_the_sweep_starts_at_the_estimate_and_steps_up_to_the_first_spill(ctx: Ctx):
    from halo_harness.providers import local_sweep as S
    from halo_harness.providers.local_bench import plan_windows
    with BenchRig(["sw-up:8b"]) as rig:
        info = MB.SWEEP["sw-up:8b"]["info"]
        _w, ceiling, _s = plan_windows(rig.card, MB.row("sw-up:8b"), info, quick=True)
        got = _sweep(rig, "sw-up:8b", max_loads=1)
        ctx.check(f"the first load is at Halo's own estimate ({ceiling} on the grid), got {_ws(got)}",
                  got["ok"] and _ws(got) == [S.grid(ceiling)])
    with BenchRig(["sw-up:8b"]) as rig:
        got = _sweep(rig, "sw-up:8b", start=32768)
        rec = got["record"]
        ctx.check(f"up by 16,384 to the first spill, got {_ws(got)}", _ws(got) == [32768, 49152, 65536, 81920])
        ctx.check(f"the states, got {[r['state'] for r in rec['windows']]}",
                  [r["state"] for r in rec["windows"]] == ["on the card"] * 3 + ["spilled"])
        ctx.check(f"the pick and its one line, got {rec['pick']} {rec['why']!r}",
                  rec["pick"] == 65536 and rec["why"] == "65,536: the next step spilled")
        timed = [b for b in rig.chats() if (b.get("options") or {}).get("num_predict") == 256]
        layers = MB.SWEEP["sw-up:8b"]["info"]["qwen35.block_count"] + 1
        ctx.check(f"every layer asked onto the card; one timed call a window, two where the speed fell more than 40 % "
                  f"(the spill), got {[b['options'].get('num_gpu') for b in timed]} {[r['timed'] for r in rec['windows']]}",
                  [r["timed"] for r in rec["windows"]] == [1, 1, 1, 2] and len(timed) == 5
                  and all(b["options"].get("num_gpu") == layers for b in timed))
        w = rec["windows"][0]
        ctx.check(f"the card's used and free memory and both speeds per window, got {w}",
                  w["free_mib"] == (24 * GIB - w["size_vram"]) // MIB and w["used_mib"] == w["size_vram"] // MIB
                  and w["tok_s"] > 50 and w["prompt_tok_s"] > 1000 and w["timed"] == 1)
        ctx.check(f"the loaded models put back (the guard's line), got {got.get('left')!r}",
                  str(got.get("left") or "").startswith("left fake as it found it"))
    with BenchRig(["sw-up:8b"]) as rig:
        got = _sweep(rig, "sw-up:8b", start=98304)
        ctx.check(f"down from a spilling start to the first window on the card, got {_ws(got)} {got['record']['why']!r}",
                  _ws(got) == [98304, 81920, 65536] and got["record"]["pick"] == 65536
                  and got["record"]["why"] == "65,536: the next step spilled")


@test
def test_the_cliff_the_room_and_unknown_free_memory(ctx: Ctx):
    from halo_harness.providers import local_sweep as S
    with BenchRig(["sw-cliff:8b"]) as rig:
        got = _sweep(rig, "sw-cliff:8b", start=32768)
        rows = got["record"]["windows"]
        slow = rows[-1]
        ctx.check(f"a window wholly on the card at a third of the speed: recorded, past the cliff, got {slow}",
                  _ws(got) == [32768, 49152, 65536] and slow["on_card"] is True and slow["state"] == "on the card, but slow"
                  and slow["slow"] and slow["timed"] == 2)
        ctx.check(f"never picked; the line says how much slower, got {got['record']['why']!r}",
                  got["record"]["pick"] == 49152 and got["record"]["why"].startswith("49,152: the next step was ")
                  and got["record"]["why"].endswith("x slower"))
    with BenchRig(["sw-up:8b"]) as rig:
        at49 = 5 * GIB + 49152 * 98304
        got = _sweep(rig, "sw-up:8b", start=32768, memory=_mem(rig, at49 + 200 * MIB))
        ctx.check(f"under 300 MiB free is no room: not picked, the line says so, got {_ws(got)} {got['record']['why']!r}",
                  _ws(got) == [32768, 49152] and got["record"]["pick"] == 32768
                  and got["record"]["why"] == "32,768: the next step left 200 MiB free on the card (under 300)")
    with BenchRig(["sw-short:8b"]) as rig:
        got = _sweep(rig, "sw-short:8b", start=32768, memory=lambda: None)
        rows = got["record"]["windows"]
        ctx.check(f"a host that does not tell: free unknown, never invented, got {[S.row_line(r) for r in rows]}",
                  all(r["free_mib"] is None and r["used_mib"] is None for r in rows)
                  and all("free unknown" in S.row_line(r) for r in rows))
        ctx.check(f"at most the trained window: the model's own limit, got {_ws(got)} {got['record']['why']!r}",
                  _ws(got) == [32768, 40960] and got["record"]["why"] == "40,960: the model's own limit")


@test
def test_six_loads_a_stop_and_a_second_start(ctx: Ctx):
    import threading
    with BenchRig(["sw-up:8b"]) as rig:
        got = _sweep(rig, "sw-up:8b", start=8192)
        ctx.check(f"six loads at most, got {_ws(got)} ({_loads(rig, 'sw-up:8b')} loads) {got['record']['why']!r}",
                  _ws(got) == [8192, 16384, 24576, 32768, 49152, 65536] and _loads(rig, "sw-up:8b") == 6
                  and got["record"]["why"].startswith("65,536: the largest measured; the loads were used"))
        again = _sweep(rig, "sw-up:8b")
        ctx.check(f"a second start at the cap loads nothing, got {again.get('say')!r}", again.get("capped")
                  and _loads(rig, "sw-up:8b") == 6)
        more = _sweep(rig, "sw-up:8b", max_loads=8)
        ctx.check(f"asked for more, it goes on from there, got {_ws(more)} {more['record']['why']!r}",
                  _ws(more)[-1] == 81920 and more["record"]["why"] == "65,536: the next step spilled")
    with BenchRig(["sw-up:8b"]) as rig:
        stop = threading.Event()
        got = _sweep(rig, "sw-up:8b", start=32768, stop=stop,
                     on_line=lambda s: stop.set() if s.startswith("32,768: on the card") else None)
        ctx.check(f"a Stop ends it after the running load and keeps what landed, got {_ws(got)} {got['say']!r}",
                  got["stopped"] and _ws(got) == [32768] and "stopped" in got["say"])
        from halo_harness.providers import local_sweep as S
        kept = S.load(rig.state, rig.host.url, "sw-up:8b")
        ctx.check(f"saved as it landed, got {kept and [r['window'] for r in kept['windows']]}",
                  kept and [r["window"] for r in kept["windows"]] == [32768])
        on = _sweep(rig, "sw-up:8b")
        ctx.check(f"a second start goes on from there, got {_ws(on)}", _ws(on) == [32768, 49152, 65536, 81920])


@test
def test_one_sweep_per_server_and_the_record_keyed_by_digest_and_server(ctx: Ctx):
    from halo_harness.providers import local_sweep as S
    from halo_harness.providers.ollama_calibrate import has_calibration_entry, lookup_learned_cap
    from halo_harness.providers.ollama_hw import fit_settings_of
    from halo_harness.providers.ollama_measure_guard import measuring
    with BenchRig(["sw-up:8b"]) as rig:
        with measuring(rig.host, "bn-other:1b", rig.state) as g:
            busy = _sweep(rig, "sw-up:8b", start=32768)
        ctx.check(f"a measurement holds the server: one line, nothing loaded, got {busy.get('say')!r}",
                  g.ok and not busy["ok"] and "is running already" in busy["say"] and not rig.chats())
        got = _sweep(rig, "sw-up:8b", start=32768)
        fs = fit_settings_of(rig.host)
        cap = lookup_learned_cap(rig.state, host_url=rig.host.url, model="sw-up:8b", digest="sha256:sw-up-8b",
                                 ollama_version="0.40.13", fit_settings=fs)
        ctx.check(f"the pick is the measured window `halo local measure`, the estimate and the twin read, got {cap}",
                  cap == got["record"]["pick"] == 65536
                  and has_calibration_entry(rig.state, host_url=rig.host.url, model="sw-up:8b", digest="sha256:sw-up-8b",
                                            ollama_version="0.40.13", fit_settings=fs))
        from halo_harness.providers.ollama_tune import plan_twin
        tw = plan_twin(rig.host, "sw-up:8b", state_dir=rig.state)
        ctx.check(f"the twin's window is the pick, got {getattr(tw, 'window', None)}", getattr(tw, "window", None) == 65536)
        srv = got["record"]["server"]
        ctx.check(f"kept under the digest and the server, got {srv}", srv.get("version") == "0.40.13"
                  and S.load(rig.state, rig.host.url, "sw-up:8b", digest="sha256:sw-up-8b", server=srv)
                  and S.load(rig.state, rig.host.url, "sw-up:8b", digest="sha256:other", server=srv) is None
                  and S.load(rig.state, rig.host.url, "sw-up:8b", digest="sha256:sw-up-8b",
                             server={**srv, "version": "0.40.14"}) is None)
        done = _sweep(rig, "sw-up:8b")
        ctx.check(f"a finished sweep is not run again, got {done.get('say')!r}", done.get("already")
                  and done["say"].startswith("swept already for this digest and server: 65,536"))
        rig.mock.version_response = {"version": "0.40.14"}
        from halo_harness.providers.ollama import reset_ollama_version_cache
        reset_ollama_version_cache()
        fresh = _sweep(rig, "sw-up:8b", start=49152)
        ctx.check(f"another server version: the kept sweep is not used, got {_ws(fresh)}", _ws(fresh)[0] == 49152)


@test
def test_a_model_that_does_not_load_is_no_fit_reading(ctx: Ctx):
    from halo_harness.providers.ollama_calibrate import has_calibration_entry
    with BenchRig(["sw-new:8b"]) as rig:
        got = _sweep(rig, "sw-new:8b", start=32768)
        rec = got["record"]
        ctx.check(f"one load, its error kept, no pick, the sweep ends, got {_ws(got)} {rec['why']!r}",
                  _ws(got) == [32768] and rec["windows"][0]["state"] == "did not load" and rec["pick"] is None
                  and "unknown model architecture" in rec["why"] and rec["done"])
        ctx.check("no calibration entry: a failed load is not 'does not fit'",
                  not has_calibration_entry(rig.state, host_url=rig.host.url, model="sw-new:8b"))


@test
def test_the_pick_names_its_real_bound(ctx: Ctx):
    """After the check: a model trained past Halo's 131,072 cap on a host with no max_ctx stops at Halo's cap and says
    so (never "the host's max_ctx"); a host whose max_ctx is the bound says that."""
    import dataclasses
    with BenchRig(["sw-long:4b"]) as rig:
        got = _sweep(rig, "sw-long:4b", start=98304)
        ctx.check(f"Halo's cap, not the host's max_ctx, got {_ws(got)} {got['record']['why']!r}",
                  _ws(got) == [98304, 114688, 131072] and got["record"]["why"] == "131,072: Halo's 131,072 cap")
    with BenchRig(["sw-long:4b"]) as rig:
        from halo_harness.providers.local_sweep_run import sweep
        host = dataclasses.replace(rig.host, max_ctx=114688)
        got = sweep(host, "sw-long:4b", state_dir=rig.state, card=rig.card, start=98304, sessions=lambda: [],
                    memory=_mem(rig, 24 * GIB))
        ctx.check(f"the host's max_ctx when it is the bound, got {_ws(got)} {got['record']['why']!r}",
                  _ws(got) == [98304, 114688] and got["record"]["why"] == "114,688: the host's max_ctx")


@test
def test_a_proposal_above_the_top_is_refused_even_without_a_trained_window(ctx: Ctx):
    """After the check: `only` (the tuner's ask) is bounded by the sweep's top (the trained window or Halo's cap, and
    the host's max_ctx), also when the header does not say the trained window."""
    with BenchRig(["sw-nohead:8b"]) as rig:
        got = _sweep(rig, "sw-nohead:8b", only=10 ** 9)
        ctx.check(f"10**9 with no trained window: refused, nothing loaded, got {got.get('say')!r}",
                  got.get("refused") is True and not got["ok"] and _loads(rig, "sw-nohead:8b") == 0
                  and "131,072" in got["say"])
        ok = _sweep(rig, "sw-nohead:8b", only=65536)
        ctx.check(f"a window under the top is measured, got {ok.get('say')!r}", ok["ok"] and _ws(ok) == [65536])


class _NoPs:
    """The host's client, whose /api/ps read fails from the `fail_from`-th read on (local_bench._ps then reads {})."""

    def __init__(self, host, fail_from: int):
        from halo_harness.providers.capability_battery import HostClient
        self.inner, self.fail_from, self.n = HostClient(host), fail_from, 0

    def call(self, method, path, body=None, timeout=10.0):
        if path == "/api/ps":
            self.n += 1
            if self.n >= self.fail_from:
                return {"error": "timed out"}
        return self.inner.call(method, path, body=body, timeout=timeout)


@test
def test_a_failed_ps_read_is_unknown_never_a_spill(ctx: Ctx):
    """After the check: when /api/ps does not answer, the window is "unknown: /api/ps did not answer", never "spilled":
    never picked, never the pick's reason "the next step spilled", and no "does not fit" reading."""
    from halo_harness.providers.ollama_calibrate import has_calibration_entry
    with BenchRig(["sw-up:8b"]) as rig:
        got = _sweep(rig, "sw-up:8b", start=32768, client=_NoPs(rig.host, 2))
        rows = got["record"]["windows"]
        ctx.check(f"the second window unknown, the sweep stops there, got {[(r['window'], r.get('state')) for r in rows]}",
                  _ws(got) == [32768, 49152] and rows[1]["on_card"] is None
                  and rows[1]["state"] == "unknown: /api/ps did not answer")
        ctx.check(f"the pick is the window read on the card; its reason is no spill, got {got['record']['why']!r}",
                  got["record"]["pick"] == 32768 and "spilled" not in got["record"]["why"]
                  and "/api/ps did not answer" in got["record"]["why"])
    with BenchRig(["sw-up:8b"]) as rig:
        got = _sweep(rig, "sw-up:8b", start=32768, client=_NoPs(rig.host, 1))
        ctx.check(f"an unknown start: no pick, no step down, no 'does not fit', got {_ws(got)} {got['record']['why']!r}",
                  _ws(got) == [32768] and got["record"]["pick"] is None and "spill" not in got["record"]["why"]
                  and not has_calibration_entry(rig.state, host_url=rig.host.url, model="sw-up:8b"))


@test
def test_halo_local_bench_sweep(ctx: Ctx):
    from halo_harness.local_bench_cli import cmd_bench
    with BenchRig(["sw-short:8b"]) as rig:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cmd_bench(["--host", "fake", "--sweep", "sw-short:8b", "--yes", "--loads", "2"])
        text = out.getvalue().splitlines()
        ctx.check(f"the cost line first (loads, what it unloads, what it writes), the windows, the pick, got {text}",
                  code == 0 and text[0].startswith("local: ~") and "at most 2 loads of sw-short:8b" in text[0]
                  and "puts it back" in text[0] and "nothing to the Ollama store" in text[0]
                  and text[1] == "sw-short:8b on fake:" and any(x.strip().startswith("the pick: ") for x in text))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
