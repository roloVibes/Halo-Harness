"""halo_harness.ollama_cli -- `halo ollama [--host NAME] [--refresh]`
(Halo 2.0.3 round 3, brief item 4): the CLI twin of `/ollama`'s TUI panel
and `commands/builtins.py`'s `/ollama` print-mode fallback -- all three
render `providers.ollama_panel.analyze_host`/`format_host_analysis`, so
none of the three can quietly disagree about what a host looks like.
"""

from __future__ import annotations

import argparse
import sys


def cmd_ollama(argv: list) -> int:
    # Round 5b (brief item 2): `halo ollama calibrate <model> [--host NAME]
    # [--start N]` is its own subcommand, dispatched the same way `halo`'s
    # own top-level `cli.py` dispatches "roles"/"local" -- never confused
    # with the `--host`/`--refresh` flags the bare `halo ollama` (no
    # subcommand) form already takes.
    if argv and argv[0] == "calibrate":
        return cmd_ollama_calibrate(argv[1:])
    if argv and argv[0] == "doctor":
        return cmd_ollama_doctor(argv[1:])
    if argv and argv[0] == "discover":  # Halo 3.2.3.0 R2: the servers are found, then measured
        from halo_harness.ollama_discover_cli import cmd_ollama_discover
        return cmd_ollama_discover(argv[1:])
    if argv and argv[0] == "tune":  # Halo 3.2.3.0 R3: a tuned twin
        from halo_harness.ollama_tune_cli import cmd_ollama_tune
        return cmd_ollama_tune(argv[1:])
    if argv and argv[0] == "hardware":  # Halo 3.3.4.0 R1: the hardware card, read-only
        from halo_harness.ollama_steward.cli import cmd_ollama_hardware
        return cmd_ollama_hardware(argv[1:])
    if argv and argv[0] == "steward":  # Halo 3.3.4.0 R3: findings, the fit plan, the profiles
        from halo_harness.ollama_steward.cli_steward import cmd_ollama_steward
        return cmd_ollama_steward(argv[1:])
    if argv and argv[0] == "explain":  # Halo 3.3.4.0 R4: an alert kind or a topic, from the knowledge (no model)
        from halo_harness.ollama_steward.explain import cmd_ollama_explain
        return cmd_ollama_explain(argv[1:])
    if argv and argv[0] in ("traffic", "events"):  # Halo 3.3.4.0 R2: the ledger's rollups, the server's events
        from halo_harness.ollama_steward import cli as steward_cli
        return getattr(steward_cli, f"cmd_ollama_{argv[0]}")(argv[1:])
    from halo_harness.providers.ollama import resolve_ollama_hosts
    from halo_harness.providers.ollama_panel import analyze_host, format_host_analysis

    parser = argparse.ArgumentParser(prog="halo ollama", add_help=True,
                                      description="Per-host Ollama analysis: reachability, version, loaded "
                                                   "models (offload, context, KV cost), and tool-catalog sizing. "
                                                   "Subcommands: discover, calibrate, tune, doctor, hardware, traffic, events, steward, explain.")
    parser.add_argument("--host", default=None, help="only this configured host (by name), not every one")
    parser.add_argument("--refresh", action="store_true",
                         help="bypass the short-TTL catalog cache and re-read /api/tags+/api/show now")
    args = parser.parse_args(argv)

    hosts = resolve_ollama_hosts()
    if args.host:
        hosts = [h for h in hosts if h.name.lower() == args.host.lower()]
        if not hosts:
            print(f"halo ollama: no configured host named {args.host!r} (see `ollama.hosts` in "
                  f"~/.halo/config.json, or docs/MODELS.md's Ollama section)", file=sys.stderr)
            return 1
    if not hosts:
        print("No Ollama hosts configured.", file=sys.stderr)
        return 0
    for i, host in enumerate(hosts):
        if i:
            print()
        print(format_host_analysis(analyze_host(host, force=args.refresh)))
    if not args.host:
        from halo_harness.providers.ollama_discover_hosts import found_not_added_lines
        lines = found_not_added_lines()
        if lines:
            print()
            for line in lines:
                print(line)
    return 0


def cmd_ollama_calibrate(argv: list) -> int:
    """`halo ollama calibrate <model> [--host NAME] [--start N] [--no-up]
    [--timeout S]`: the explicit twin of the first-use calibration
    `agent/loop.py` runs -- same `providers.ollama_calibrate.run_calibration`
    loop, same `~/.halo/ollama-fit.json` record. Halo 3.2.3.0 R1: prints
    the per-step budget it uses (`load_budget_s`, or `--timeout`), one
    line per load, and the one-line outcome; an inconclusive run records
    no cap."""
    from halo_harness.config.paths import bridge_home
    from halo_harness.providers.ollama import get_catalog, probe_version, resolve_ollama_host, trained_context_for
    from halo_harness.providers.ollama_calibrate import (
        current_window, gpu_layers_for, host_gpu_total_bytes, load_budget_s, model_size_gb, outcome_line,
        record_calibration, record_inconclusive, record_prompt_speed, run_calibration,
    )
    from halo_harness.providers.ollama_hw import catalog_row, estimate_fit_for_host, is_local_host
    from halo_harness.providers.ollama_prompt import fmt_window

    parser = argparse.ArgumentParser(
        prog="halo ollama calibrate", add_help=True,
        description="Load <model> at decreasing candidate num_ctx values until it is fully resident in GPU "
                    "memory (or does not fit at all), then step UP from there to find the true ceiling, and "
                    "remember the result in ~/.halo/ollama-fit.json. A load that does not finish within its "
                    "budget is tried once more with twice the budget; still unfinished, the run is "
                    "inconclusive and records nothing.",
    )
    parser.add_argument("model", help="the Ollama model tag to calibrate, e.g. qwen3-coder:30b")
    parser.add_argument("--host", default=None, help="a configured ollama.hosts[] name (default host otherwise)")
    parser.add_argument("--start", type=int, default=None,
                         help="the first num_ctx to try (default: the GPU-based estimate when a local or ssh "
                             "read exists, else 32768)")
    parser.add_argument("--no-up", action="store_true",
                         help="stop at the first fitting candidate found while stepping DOWN -- never probe "
                             "larger contexts afterward")
    parser.add_argument("--timeout", type=float, default=None, metavar="S",
                         help="seconds each load may take (default: 20 s + 4 s per GB of the model locally, "
                             "40 s + 6 s per GB over the network, 60 s when the size is unknown)")
    args = parser.parse_args(argv)

    host = resolve_ollama_host(args.host)
    if host is None:
        print(f"halo ollama calibrate: no configured host named {args.host!r} (see `ollama.hosts` in "
              f"~/.halo/config.json)", file=sys.stderr)
        return 1
    remote = not is_local_host(host)
    print(f"Calibrating {args.model} on '{host.name}' ({host.url}) {'over the network' if remote else 'locally'}...")
    catalog = get_catalog(host, force=True)
    row = catalog_row(catalog, args.model)
    if row is None:
        print(f"halo ollama calibrate: {args.model!r} is not in this host's catalog -- "
              f"`halo ollama --host {host.name}` lists what is", file=sys.stderr)
        return 1
    digest = row.get("digest")
    version_info = probe_version(host)
    ollama_version = (version_info or {}).get("version") if isinstance(version_info, dict) else None
    start = args.start
    if start is None:
        estimate = estimate_fit_for_host(host, args.model, catalog)
        start = estimate if isinstance(estimate, int) and not isinstance(estimate, bool) and estimate > 0 else 32768
    size_gb = model_size_gb(catalog, args.model)
    if args.timeout is not None and args.timeout > 0:
        budget, why = float(args.timeout), "--timeout"
    else:
        budget = load_budget_s(size_gb, remote)
        why = (f"{size_gb:.1f} GB, {'network' if remote else 'local'}" if size_gb else "size unknown")
    print(f"  starting candidate: num_ctx={start}" + ("" if not args.no_up else " (--no-up: stepping up skipped)"))
    print(f"  budget per load: {budget:.0f} s ({why}); a load past it is tried once more with {budget * 2:.0f} s")

    def _on_step(ctx, reading):
        what = {"safe": "on the GPU, safe headroom", "tight": "on the GPU, tight (under the headroom rule)",
                "offloaded": "offloaded (part on the CPU)"}.get(
            reading.kind, "unknown (did not load within the budget, or /api/ps did not list it at that size)")
        vram = f" ({reading.size_vram / 1024 ** 3:.1f} GB on the GPU)" if reading.size_vram else ""
        print(f"    {fmt_window(ctx)}: {what}{vram}")

    result = run_calibration(host, args.model, start_ctx=start, keep_alive=host.keep_alive,
                              step_up=not args.no_up, trained_context=trained_context_for(catalog, args.model),
                              budget_s=budget, on_step=_on_step, num_gpu=gpu_layers_for(row.get("model_info")),
                              gpu_total=host_gpu_total_bytes(host))
    if result.prompt_tok_s:
        record_prompt_speed(bridge_home(), host_url=host.url, model=args.model, tok_s=result.prompt_tok_s)
    if result.outcome in ("inconclusive", "unreachable"):
        if result.outcome == "inconclusive":
            record_inconclusive(bridge_home(), host_url=host.url, model=args.model, budget_s=budget,
                                candidate=result.unknown_ctx)
        window, source = current_window(host, args.model)
        print(f"  {outcome_line(args.model, host.name, result, window=window, source=source)}")
        return 1
    record = record_calibration(bridge_home(), host_url=host.url, model=args.model, digest=digest,
                                 max_full_gpu_ctx=result.max_full_gpu_ctx, ollama_version=ollama_version,
                                 tight_ctx=result.tight_ctx, tight_vram=result.tight_vram,
                                 gpu_total=result.gpu_total)
    print(f"  {outcome_line(args.model, host.name, result)}")
    print(f"  recorded in ~/.halo/ollama-fit.json (digest {record['digest']!r}, ollama {ollama_version or '?'})")
    return 0


def cmd_ollama_doctor(argv: list) -> int:
    """`halo ollama doctor [--host NAME]` (Halo 2.0.3 round 5b part 2,
    brief item 4): the SAME `providers.ollama_panel.analyze_host`/
    `format_host_analysis` print `halo ollama` already does, PLUS
    `providers.ollama_panel.host_setup_checklist`'s own plain-sentence,
    per-OS recommendations -- see that function's own docstring for the
    local/remote OS rule."""
    from halo_harness.providers.ollama import resolve_ollama_hosts
    from halo_harness.providers.ollama_panel import analyze_host, format_host_analysis, host_setup_checklist

    parser = argparse.ArgumentParser(
        prog="halo ollama doctor", add_help=True,
        description="What each configured Ollama host exposes, plus the documented host-tuning "
                    "recommendations Halo cannot read back (flash attention, KV cache type, keep-alive, "
                    "num_parallel, context length) and where each one lives per OS.",
    )
    parser.add_argument("--host", default=None, help="only this configured host (by name), not every one")
    args = parser.parse_args(argv)

    hosts = resolve_ollama_hosts()
    if args.host:
        hosts = [h for h in hosts if h.name.lower() == args.host.lower()]
        if not hosts:
            print(f"halo ollama doctor: no configured host named {args.host!r} (see `ollama.hosts` in "
                  f"~/.halo/config.json)", file=sys.stderr)
            return 1
    if not hosts:
        print("No Ollama hosts configured.", file=sys.stderr)
        return 0
    for i, host in enumerate(hosts):
        if i:
            print()
        print(format_host_analysis(analyze_host(host)))
        for line in host_setup_checklist(host):
            print(f"  {line}")
    return 0
