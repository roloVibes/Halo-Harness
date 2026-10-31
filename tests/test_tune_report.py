"""tests.test_tune_report -- Halo 3.3.6.0 R5 deliverable 5, the tuning report (ollama_steward/tune_report.py,
tune_options.py, tune_lines.py) over the bench's fake host (tests/helpers/bench_rig.py: a 24 GiB test card, f16 KV,
two slots, Ollama 0.40.6) after a bench, no model call, nothing sent but to the fake:

1. the warm set that fits together and the pivot cost from the bench's cold load; each model's window alone / beside
   the warm set / with q8_0 KV ("verified by the bench" at the type in force, else "computed"); the reserve; the
   findings rules_host raises for this host (a slow box);
2. every option {id, line, kind, writes, takes, apply | server}: Halo-side ones are profile changes; server-side ones
   (OLLAMA_KV_CACHE_TYPE, OLLAMA_FLASH_ATTENTION, OLLAMA_NUM_PARALLEL, an update) carry the exact line per OS and the
   line that reverts it, and nothing runs them (no request but the bench's);
3. Apply lands through agent_proposals.land_user with its scope (keep unless named), a server-side option is not
   applied and says so; `halo local tune [--json] [--apply ID --scope S]`.
Run: python -m tests.test_tune_report
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

from tests.helpers.bench_rig import BenchRig  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.steward_seed import line  # noqa: E402

test, TESTS = new_registry()


def _rig():
    rig = BenchRig(kv="f16", version="0.40.6")
    return rig


def _report(rig):
    from halo_harness.ollama_steward.tune_report import report_for
    return report_for(rig.state, "fake")


@test
def test_the_report_after_a_bench(ctx: Ctx):
    with _rig() as rig:
        rig.card["server"]["parallel"] = 2
        rig.bench("bn-coder:30b")
        host = {"name": "fake", "url": rig.mock.base_url}
        rig.home.calls(*[line(host=host, model="bn-small:9b", eval_tok_s=2.0, ago=3600 + i) for i in range(6)])
        r = _report(rig)
        ws = r["warm_set"]
        ctx.check(f"the warm set and the pivots, got {ws}", ws["models"] and ws["line"].endswith("GiB") and " fit together: " in ws["line"])
        coder_pivot = [p for p in ws["pivots"] if p["model"] == "bn-coder:30b"]
        ctx.check(f"a pivot to the benched model costs its cold load (the bench), got {ws['pivots']}",
                  not coder_pivot or coder_pivot[0]["line"] == "a pivot to bn-coder:30b costs ~21 s of loading (the bench)")
        m = {x["model"]: x for x in r["models"]}
        ctx.check(f"each model: alone, beside, q8_0, got {[x['line'] for x in r['models']]}",
                  all(" alone " in x["line"] and "beside the warm set" in x["line"] and "with q8_0 KV" in x["line"] for x in r["models"])
                  and m["bn-coder:30b"]["q8_0_from"] == "computed" and m["bn-coder:30b"]["reserve_floor"] == 256)
        ctx.check(f"the findings rules_host raises here, got {r['findings']}",
                  any(f["rule"] == "slow-box" and "slow box for bn-small:9b" in f["line"] for f in r["findings"]))
        kinds = {o["kind"] for o in r["options"]}
        ctx.check(f"Halo-side and server-side options, got {[(o['kind'], o['line'][:50]) for o in r['options']]}",
                  kinds == {"halo", "server"} and all(o["id"].startswith("t-") and o["writes"] and o["takes"] for o in r["options"]))
        for o in r["options"]:
            if o["kind"] == "halo":
                ctx.check(f"a Halo option is profile changes, got {o['apply']}", o["apply"] and o["server"] is None
                          and all(c["field"] in ("num_ctx", "num_predict", "keep_alive", "tools_max", "host_for", "compact_at")
                                  for c in o["apply"]) and "ollama.profiles[" in o["writes"] and o["scope_default"] == "keep")
            else:
                ctx.check(f"a server option prints its lines, applies nothing, got {o['server']}", o["apply"] is None
                          and all(s["set"] and s["revert"] and s["restart"] for s in o["server"].values())
                          and o["writes"].startswith("nothing here"))
        lines = " | ".join(o["line"] for o in r["options"])
        for want in ("OLLAMA_KV_CACHE_TYPE=q8_0 on fake", "OLLAMA_FLASH_ATTENTION=1 on fake", "OLLAMA_NUM_PARALLEL=1 on fake",
                     "update Ollama on fake from 0.40.6 to 0.40.13", "num_predict 256 for bn-coder:30b"):
            ctx.check(f"the option {want!r}", want in lines)
        sent = {r_["path"] for r_ in rig.mock.requests}
        ctx.check(f"nothing but the bench's requests reached the server, got {sorted(sent)}",
                  sent <= {"/api/version", "/api/tags", "/api/show", "/api/ps", "/api/chat", "/api/generate"})


@test
def test_the_server_lines_per_os(ctx: Ctx):
    from halo_harness.ollama_steward import tune_lines as T
    w = T.env_lines("OLLAMA_KV_CACHE_TYPE", "q8_0", "windows")
    ctx.check(f"Windows: setx-style user variable and its revert, got {w}",
              w["set"] == '[Environment]::SetEnvironmentVariable("OLLAMA_KV_CACHE_TYPE", "q8_0", "User")'
              and w["revert"] == '[Environment]::SetEnvironmentVariable("OLLAMA_KV_CACHE_TYPE", $null, "User")' and "tray" in w["restart"])
    m = T.env_lines("OLLAMA_KV_CACHE_TYPE", "q8_0", "macos")
    ctx.check(f"macOS: launchctl, got {m}", m["set"] == "launchctl setenv OLLAMA_KV_CACHE_TYPE q8_0"
              and m["revert"] == "launchctl unsetenv OLLAMA_KV_CACHE_TYPE")
    lx = T.env_lines("OLLAMA_KV_CACHE_TYPE", "q8_0", "linux")
    ctx.check(f"Linux: a systemd drop-in and its removal, got {lx}",
              "/etc/systemd/system/ollama.service.d/halo-ollama_kv_cache_type.conf" in lx["set"]
              and 'Environment="OLLAMA_KV_CACHE_TYPE=q8_0"' in lx["set"]
              and lx["revert"] == "sudo rm /etc/systemd/system/ollama.service.d/halo-ollama_kv_cache_type.conf && sudo systemctl daemon-reload"
              and lx["restart"] == "sudo systemctl restart ollama")
    ctx.check("an unknown OS: every OS's lines", sorted(T.server_block("env", "K", "v", None)) == ["linux", "macos", "windows"])
    ctx.check("the card's os wins", T.os_of(None, {"os": "darwin"}) == "macos" and T.os_of(None, {"os": "Linux"}) == "linux")


@test
def test_apply_with_a_scope_and_the_cli(ctx: Ctx):
    from halo_harness.local_bench_cli import cmd_tune
    from halo_harness.ollama_steward import changes as C
    from halo_harness.ollama_steward import tune_lines
    from halo_harness.ollama_steward.profiles import all_profiles
    with _rig() as rig:
        rig.bench("bn-coder:30b")
        r = _report(rig)
        reserve = next(o for o in r["options"] if o["line"].startswith("num_predict 256 for bn-coder:30b"))
        got = tune_lines.apply(rig.state, "fake", reserve["id"], report=r)
        ctx.check(f"Apply lands as yours, scope keep, got {got}", got["ok"] and got["lines"] == [
            "num_predict unset -> 256 on fake|bn-coder:30b (kept)"] and all_profiles()["fake|bn-coder:30b"]["num_predict"] == 256)
        row = C.in_force(rig.state)[-1]
        ctx.check(f"its change row, got {row}", row["by"] == "user" and row["scope"] == "keep" and row["field"] == "num_predict")
        server = next(o for o in r["options"] if o["kind"] == "server")
        no = tune_lines.apply(rig.state, "fake", server["id"], report=r)
        ctx.check(f"a server option is not applied, it says where it runs, got {no}", not no["ok"]
                  and "a server-side change, run on fake by you" in no["lines"][0])
        ctx.check("an unknown id says so", "no option t-nope" in tune_lines.apply(rig.state, "fake", "t-nope", report=r)["lines"][0])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cmd_tune(["--host", "fake"])
        text = out.getvalue()
        ctx.check(f"halo local tune prints the report with ids, writes and takes, got {text[:300]!r}", code == 0
                  and text.startswith("'fake': ") and "warm set: " in text and "-- writes " in text and "revert: " in text)
        keep_alive = next((o for o in _report(rig)["options"] if o["kind"] == "halo" and o["apply"][0]["field"] == "keep_alive"), None)
        if keep_alive:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = cmd_tune(["--host", "fake", "--apply", keep_alive["id"], "--scope", "until-restart"])
            ctx.check(f"--apply --scope until-restart, got {out.getvalue()!r}", code == 0
                      and out.getvalue().strip().endswith("(undone when this halo exits)"))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cmd_tune(["--host", "fake", "--json"])
        ctx.check("--json is the report", json.loads(out.getvalue())["host"] == "fake")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
