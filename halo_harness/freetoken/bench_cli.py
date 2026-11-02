"""halo_harness.freetoken.bench_cli -- `halo local bench --host freetoken [--quick] [--bw [--model DIR]] [--yes]
[--json]` (Halo 3.3.9.1; local_bench_cli.cmd_bench dispatches it): the cost line first, then the FreeToken server's
speed card (freetoken/bench.py), or with `--bw` the host link measured with `ft bench bw` (freetoken/link.py), the
figure the fit reads in place of the extrapolated one.

    server_named(name) -> the roster's FreeToken server named `name` (or the first one for `freetoken`) | None
    bench_ft(host, *, quick, yes, as_json, bw, model, ask) -> exit code
"""

from __future__ import annotations

import json
from typing import Callable, Optional


def server_named(name: str):
    from halo_harness.ollama_steward.servers_hf import roster
    rows = [s for s in roster() if s.runtime == "freetoken"]
    want = str(name or "").lower()
    return next((s for s in rows if s.name.lower() == want), None) or (rows[0] if rows and want == "freetoken" else None)


def _entry(s):
    """The roster row as the bench's server: its url with /v1, its key when its entry names one."""
    from types import SimpleNamespace
    from halo_harness.providers.huggingface import resolve_huggingface_local_servers
    e = next((x for x in resolve_huggingface_local_servers() if x.name.lower() == s.name.lower()), None)
    url = s.url if str(s.url).rstrip("/").endswith("/v1") else str(s.url).rstrip("/") + "/v1"
    return SimpleNamespace(name=s.name, url=url, model=s.model, api_key=getattr(e, "api_key", None))


def bench_ft(host: str, *, quick: bool = False, yes: bool = False, as_json: bool = False, bw: bool = False,
             model: Optional[str] = None, ask: Callable[[str, bool], bool]) -> int:
    from halo_harness.config.paths import bridge_home
    if bw:
        from halo_harness.freetoken import link
        print(link.estimate(model)["line"])
        if not ask("Measure the host link now?", yes):
            return 1
        got = link.run(model=model, state_dir=bridge_home())
        print(json.dumps(got, indent=2, default=str) if as_json else got["say"])
        return 0 if got.get("ok") else 1
    s = server_named(host or "freetoken")
    if s is None:
        print("no FreeToken server here: halo local serve --runtime freetoken --model <checkpoint dir> starts one")
        return 1
    from halo_harness.freetoken import bench as B
    srv = _entry(s)
    print(B.estimate(srv, quick=quick)["line"])
    if not ask("Run the bench now?", yes):
        return 1
    print(f"{srv.model} on {srv.name}:")
    got = B.bench(srv, quick=quick, state_dir=bridge_home(),
                  on_line=(lambda _s: None) if as_json else (lambda line: print(f"  {line}")))
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
