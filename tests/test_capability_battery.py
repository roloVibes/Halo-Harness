"""tests.test_capability_battery -- Halo 3.3.6.0 R1: the battery
(providers/capability_battery.py, battery_probes.py, battery_profile.py)
against the scripted fake Ollama (tests/helpers/mock_ollama_battery.py: a
coder that passes everything, a model that answers empty with a schema, a
thinking model, a fenced-JSON model, a wrong-ID model):

1. every probe's verdict and the profile's fields per kind, `agentic_ready`,
   `interactive`, where it sits, the quirks, the evidence kept;
2. the warm-up call is never timed (tok/s from the structured probe), the
   cold load from the warm-up's `load_duration`, the thinking model re-asked
   at 600 tokens;
3. the cache: the profile in `ollama-capabilities.json` under the digest and
   host (the record's `tool_calls` follows it), a second run answers from it
   with no chat, a changed Ollama version / digest / probe set re-runs, force
   re-runs;
4. never a real host under the flag (a LAN placeholder, the made-up default):
   nothing is sent;
5. `halo models probe`: the cost line first, one line per probe, the profile;
   `--json`; the fit with a hardware card (usable window, co-reside / pivot).
Run: python -m tests.test_capability_battery
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
ensure_default_provider_credentials()

from tests.helpers.battery_rig import BatteryRig, gpu_card  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
WANT = {  # tools, system_role, instruction, output, identifiers, reasoning, agentic_ready, interactive, sits
    "bt-coder:30b": ("yes", "honoured", "strict", "json", "trusted", "none", True, "yes", "full agent"),
    "bt-mute:24b": ("no", "weak", "task-shaped", "fenced-json", "unverified", "none", False, "no", "bulk worker · non-agentic"),
    "bt-thinker:27b": ("yes", "honoured", "task-shaped", "prose", "trusted", "thinking", False, "yes", "reasoner"),
    "bt-fence:14b": ("yes", "honoured", "strict", "fenced-json", "trusted", "none", True, "yes", "full agent"),
    "bt-wrongid:8b": ("yes", "weak", "task-shaped", "json", "unverified", "thinking", False, "yes", "reasoner"),
}
KEYS = ("tools", "system_role", "instruction", "output", "identifiers", "reasoning", "agentic_ready", "interactive", "sits")


@test
def test_every_probe_on_every_scripted_model(ctx: Ctx):
    with BatteryRig() as rig:
        for name, want in WANT.items():
            p = rig.probe(name)
            got = tuple(p.get(k) for k in KEYS)
            ctx.check(f"{name}: {dict(zip(KEYS, want))}, got {dict(zip(KEYS, got))}", got == want)
            ctx.check(f"{name}: the evidence keeps every probe's answer, got {sorted(p['evidence'])}",
                      sorted(p["evidence"]) == sorted(["warmup", "tools", "system", "instruction", "json", "reference"]))
            for k in ("window", "kv_per_token", "size_gb", "speed", "resident", "quirks", "probed_at", "digest",
                      "ollama_version", "probe_set", "output_why", "chips"):
                ctx.check(f"{name}: the profile has {k}", k in p)
        mute = rig.probe("bt-mute:24b", force=True)
        ctx.check(f"the empty-with-a-schema model: why it is no, got {mute['tools_why']!r}", mute["tools_why"].startswith("an empty reply"))
        ctx.check(f"its chips say not interactive, got {mute['chips']}", "not interactive" in mute["chips"])
        ctx.check(f"its quirks say it, got {mute['quirks']}", any("tool call" in q for q in mute["quirks"])
                  and any("system prompts" in q for q in mute["quirks"]) and any("reference ids" in q for q in mute["quirks"]))
        thinker = rig.cache()["sha256:bt-thinker-27b"]["battery"]["fake"]
        ctx.check(f"the thinker's JSON failure says why (prose), got {thinker['output_why']!r}", thinker["output_why"].startswith("prose"))
        ctx.check(f"the wrong-ID model's answer is kept, got {rig.probe('bt-wrongid:8b')['identifiers_why']!r}",
                  "CWE-601" in rig.probe("bt-wrongid:8b")["identifiers_why"])


@test
def test_the_warm_up_is_never_timed_and_a_thinker_is_re_asked(ctx: Ctx):
    with BatteryRig(["bt-coder:30b", "bt-thinker:27b"]) as rig:
        p = rig.probe("bt-coder:30b")
        ctx.check(f"tok/s from the structured probe (300 / 1.6 s), not the warm-up's 5.7, got {p['speed']}",
                  p["speed"]["tok_s"] == 187.5)
        ctx.check(f"the cold load is the warm-up's load_duration (6.5 s), got {p['speed']['cold_load_s']}",
                  p["speed"]["cold_load_s"] == 6.5 and p["speed"]["warm_at_start"] is False)
        ctx.check(f"TTFT from the warm structured call, got {p['speed']['ttft_ms']}", p["speed"]["ttft_ms"] == 121)
        first = rig.chats()[0]
        ctx.check(f"the first call is the warm-up, got {first['messages']}", "ready" in first["messages"][0]["content"])
        ctx.check(f"num_predict capped on every probe, got {[b['options']['num_predict'] for b in rig.chats()]}",
                  all(0 < b["options"]["num_predict"] <= 600 for b in rig.chats()))
        rig.mock.clear()
        t = rig.probe("bt-thinker:27b")
        caps = [b["options"]["num_predict"] for b in rig.chats()]
        ctx.check(f"each empty-content probe asked once more at 600, got {caps}", caps.count(600) == 5)
        ctx.check(f"the first (empty) answer kept beside the second, got {sorted(t['evidence']['system'])}",
                  "first" in t["evidence"]["system"] and t["evidence"]["system"]["first"]["content"] == "")
        ctx.check(f"a cold model's ps after: verified on the GPU at the window used, got {t['window']}",
                  t["window"]["verified"] is True and t["window"]["used"] == 32768)


@test
def test_the_cache_key_is_digest_version_and_probe_set(ctx: Ctx):
    from halo_harness.providers import battery_probes as B
    with BatteryRig(["bt-coder:30b"]) as rig:
        rig.probe("bt-coder:30b")
        entry = rig.cache()["sha256:bt-coder-30b"]
        ctx.check(f"kept in the existing capability cache under the digest and host, got {sorted(entry)}",
                  "fake" in entry["battery"] and entry["tool_calls"] is True)
        ctx.check("the record names the version and the probe set",
                  entry["battery"]["fake"]["ollama_version"] == "0.40.13" and entry["battery"]["fake"]["probe_set"] == B.PROBE_SET)
        n = len(rig.chats())
        again = rig.probe("bt-coder:30b")
        ctx.check(f"a second run answers from the cache, no chat, got cached={again.get('cached')} chats {len(rig.chats()) - n}",
                  again.get("cached") is True and len(rig.chats()) == n)
        rig.probe("bt-coder:30b", force=True)
        ctx.check(f"force runs it again, got {len(rig.chats()) - n} chats", len(rig.chats()) - n == 6)
        n = len(rig.chats())
        rig.mock.version_response = {"version": "0.41.0"}
        p = rig.probe("bt-coder:30b")
        ctx.check(f"a new Ollama version re-runs, got cached={p.get('cached')}", not p.get("cached") and len(rig.chats()) > n)
        n = len(rig.chats())
        rig.mock.tags_response["models"][0]["digest"] = "sha256:new-weights"
        p = rig.probe("bt-coder:30b")
        ctx.check(f"a new digest re-runs, got {p.get('digest')} cached={p.get('cached')}",
                  p["digest"] == "sha256:new-weights" and not p.get("cached") and "sha256:new-weights" in rig.cache())
        saved, B.PROBE_SET = B.PROBE_SET, "battery-test"
        try:
            n = len(rig.chats())
            p = rig.probe("bt-coder:30b")
            ctx.check("a new probe set re-runs", not p.get("cached") and len(rig.chats()) > n)
        finally:
            B.PROBE_SET = saved


@test
def test_never_a_real_host_under_the_flag(ctx: Ctx):
    from halo_harness.providers.capability_battery import run
    from halo_harness.providers.ollama import OllamaHost
    with BatteryRig(["bt-coder:30b"]) as rig:
        for host in (OllamaHost(name="lan", url="http://192.0.2.10:11434"),
                     OllamaHost(name="default", url="http://127.0.0.1:11434")):
            p = run(host, "bt-coder:30b", state_dir=rig.state)
            ctx.check(f"{host.url}: not probed, the reason said, got {p.get('say')!r}", p["ok"] is False and "test" in p["say"])
        ctx.check(f"the fake saw nothing, got {len(rig.mock.requests)}", not rig.mock.requests)


@test
def test_halo_models_probe_and_the_fit(ctx: Ctx):
    from halo_harness.catalog_cli import cmd_models
    from halo_harness.studio import ollama_hosts_view as V
    with BatteryRig(["bt-coder:30b", "bt-mute:24b"]) as rig:
        with V._LOCK:
            V._CACHE[("card", rig.host.url)] = (1e18, gpu_card(24.0))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = cmd_models(["probe", "ol:bt-coder:30b@fake"])
        lines = buf.getvalue().splitlines()
        ctx.check(f"exit 0, got {rc}", rc == 0)
        ctx.check(f"the cost line first, got {lines[:1]}",
                  lines[0] == "about 8 requests to bt-coder:30b on fake, 1-3 minutes, no cost; it loads the model")
        ctx.check(f"one line per probe, got {lines[1:7]}", [x.strip()[:4] for x in lines[1:7]] == [f"{i}/6 " for i in range(1, 7)])
        ctx.check(f"the profile and the blocks, got {lines[7:]}", "where it sits: full agent" in buf.getvalue()
                  and "use it for:" in buf.getvalue() and "limits:" in buf.getvalue())
        p = rig.cache()["sha256:bt-coder-30b"]["battery"]["fake"]
        ctx.check(f"the usable window from the card, got {p['window']}", isinstance(p["window"]["usable"], int)
                  and p["window"]["usable"] >= 32768)
        ctx.check(f"kv per token from /api/show (48 x 256 x 4 x 1.0625, q8_0 with its block scales), got {p['kv_per_token']}", p["kv_per_token"] == 52224)
        ctx.check(f"18.6 GB beside a 14.3 GB model on a 24 GiB card: pivot-only, got {p['resident']}",
                  p["resident"]["pivot_only"] is True and p["resident"]["co_resides_with"] == [])
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = cmd_models(["probe", "--all", "--host", "fake", "--json"])
        got = json.loads(buf.getvalue())
        ctx.check(f"--all --json: both models, got {[g.get('model') for g in got]} rc {rc}",
                  rc == 0 and sorted(g["model"] for g in got) == ["bt-coder:30b", "bt-mute:24b"])


def _wait(fn, timeout=15.0):
    import time
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        got = fn()
        if got:
            return got
        time.sleep(0.05)
    return None


@test
def test_a_member_probes_and_the_hub_takes_it(ctx: Ctx):
    import tempfile
    from halo_harness.fleet import control_models
    from halo_harness.fleet.control_probes import read_probes, take_probes
    from halo_harness.providers.ollama_capability import profile_for
    with BatteryRig(["bt-coder:30b"]) as rig:
        got = control_models.run({"cmd": "ollama_probe", "host": "fake", "model": "bt-coder:30b"})
        ctx.check(f"ollama_probe answers at once with its job, got {got}", got["ok"] and got["job"].startswith("probe-"))
        rows = _wait(lambda: read_probes(rig.state))
        ctx.check(f"the profile rides the next push, got {[r.get('model') for r in rows or []]}",
                  bool(rows) and rows[0]["model"] == "bt-coder:30b" and "evidence" not in rows[0])
        hub = Path(tempfile.mkdtemp(prefix="bt_hub-"))
        n = take_probes(hub, "mac", rows)
        kept = profile_for(hub, "bt-coder:30b")
        ctx.check(f"the hub keeps it, from the member, got {n} {kept and (kept['host'], kept['from'])}",
                  n == 1 and kept["from"] == "mac" and kept["host"] == "mac:fake")
        ctx.check("ollama_probe is a fleet model command", "ollama_probe" in control_models.CMDS)


@test
def test_the_steward_probes_a_new_model_when_idle(ctx: Ctx):
    import time
    from types import SimpleNamespace
    from halo_harness.ollama_steward import probe_new
    from halo_harness.providers.ollama_capability import profile_for
    with BatteryRig(["bt-coder:30b"]) as rig:
        said: list = []
        job = SimpleNamespace(lock=object(), host=rig.host, state_dir=rig.state, emit=lambda *a, **k: said.append(a))
        now = time.time()
        ctx.check(f"due: the model with no profile, got {probe_new.due(rig.state, rig.host)}",
                  probe_new.due(rig.state, rig.host) == ["bt-coder:30b"])
        ctx.check("it starts on it", probe_new.maybe(job, now) == "bt-coder:30b")
        ctx.check("the profile lands", bool(_wait(lambda: profile_for(rig.state, "bt-coder:30b"))))
        _wait(lambda: not probe_new._running.is_set())
        ctx.check(f"the job's finding says it, got {said}", any("probed bt-coder:30b on fake: full agent" in str(a) for a in said))
        ctx.check("not again within the check period", probe_new.maybe(job, now + 5) is None)
        ctx.check("nothing due once probed", probe_new.due(rig.state, rig.host) == [])
        rig.mock.version_response = {"version": "0.42.0"}
        ctx.check("a new Ollama version makes it due again", probe_new.due(rig.state, rig.host) == ["bt-coder:30b"])
        rig.home.calls({"at": __import__("halo_harness.ollama_steward.ledger", fromlist=["now_iso"]).now_iso(now + 999),
                        "host": {"name": "fake"}, "model": "bt-coder:30b", "kind": "turn"})
        ctx.check("never while calls flow (a ledger line just now)", probe_new.maybe(job, now + 1000) is None)
        from halo_harness.theme import set_config_value
        set_config_value("ollama.steward.probe_new", False)
        ctx.check("off: never", probe_new.maybe(job, now + 99999) is None)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
