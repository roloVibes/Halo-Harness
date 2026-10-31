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
        ctx.check("a changed tag marks it stale", R.stale(sc, digest="sha256:other") == "measured before the tag changed")
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


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
