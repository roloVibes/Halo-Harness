"""halo_harness.strata.bench -- `halo local bench --host strata [--quick] [--yes] [--json]` (Halo 3.3.9.2;
local_bench_cli.cmd_bench dispatches it): the cost line first, then FreeToken's speed card (freetoken/bench.py, the same
two calls per window over the OpenAI route, an untimed warm-up first) against the roster's Strata server, saved as a
card of runtime `strata` (digest `strata|<model>`) -- the figure the Strata fit says as "measured" in place of the
table's (local_sched/fit_st.py).

    server_named(name) -> the roster's Strata server named `name` (or the first one for `strata`) | None
    bench_st(host, *, quick, yes, as_json, ask) -> exit code
The warm-up covers Strata's first request after a start (the GPU's expert cache fills, the n-gram table's first rows
come from the SSD); a local op: it costs the seconds the cost line says, no tokens leave this machine.
"""

from __future__ import annotations

import json
from typing import Callable

WARM = "the first request after a start fills the GPU's expert cache"


def server_named(name: str):
    from halo_harness.ollama_steward.servers_hf import roster
    rows = [s for s in roster() if s.runtime == "strata"]
    want = str(name or "").lower()
    return next((s for s in rows if s.name.lower() == want), None) or (rows[0] if rows and want == "strata" else None)


def _srv(s):
    from types import SimpleNamespace
    from halo_harness.providers.huggingface import resolve_huggingface_local_servers
    e = next((x for x in resolve_huggingface_local_servers() if x.name.lower() == s.name.lower()), None)
    url = s.url if str(s.url).rstrip("/").endswith("/v1") else str(s.url).rstrip("/") + "/v1"
    return SimpleNamespace(name=s.name, url=url, model=s.model, api_key=getattr(e, "api_key", None), label="Strata")


def _set_of(s):
    """The set Halo started on this server (its registry row's flags), as the catalog names it; None for one started by
    hand (its card stays under the id the server reports)."""
    from halo_harness.config.paths import bridge_home
    from halo_harness.providers.local_runtime import load_registry
    from halo_harness.strata.catalog import get, set_name
    from halo_harness.ollama_steward.servers_hf import port_of
    e = next((r for r in load_registry(bridge_home()) if r.get("kind") == "strata" and r.get("port") == port_of(s.url)),
             None)
    f = (e or {}).get("flags") or {}
    row = get(f.get("family"), f.get("set")) if f.get("family") else None
    return set_name(row) if row else None


def bench_st(host: str, *, quick: bool = False, yes: bool = False, as_json: bool = False,
             ask: Callable[[str, bool], bool]) -> int:
    from halo_harness.config.paths import bridge_home
    from halo_harness.freetoken import bench as B
    s = server_named(host or "strata")
    if s is None:
        print("no Strata server here: halo local serve --runtime strata --model <family>/<set> starts one, or start it "
              "with strata launch and the auto-detect names it")
        return 1
    srv = _srv(s)
    print(B.estimate(srv, quick=quick)["line"].replace("the host link", "the SSD"))
    if not ask("Run the bench now?", yes):
        return 1
    print(f"{srv.model} on {srv.name}:")
    got = B.bench(srv, quick=quick, state_dir=bridge_home(), runtime="strata", warm_words=WARM,
                  on_line=(lambda _s: None) if as_json else (lambda line: print(f"  {line}")))
    named = _set_of(s)
    if got.get("ok") and named:  # the card under the set's name too: the fit reads it for that set (local_sched/fit_st)
        from halo_harness.providers.local_bench_runs import save
        save(bridge_home(), {**{k: v for k, v in got.items() if k != "ok"}, "model": named, "digest": f"strata|{named}"})
    if as_json:
        print(json.dumps(got, indent=2, default=str))
    elif got.get("ok"):
        from halo_harness.providers.local_bench_runs import _row_line
        print(f"  speed card: {len(got['windows'])} windows, reply reserve "
              + (f"at least {got['reserve_floor']:,}" if got.get("reserve_floor") else "not found") + f", {got['took_s']:g} s")
        for r in got["windows"]:
            print("    " + _row_line(r))
    else:
        print(f"  {got.get('say')}")
    return 0 if got.get("ok") else 1
