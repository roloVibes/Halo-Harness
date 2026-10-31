"""halo_harness.models_probe_cli -- Halo 3.3.6.0 R1: `halo models probe`, the
battery (providers/capability_battery.py) from the terminal.

    halo models probe <ref> [--host H] [--force] [--json]   one model: ol:<name>@<host> or a bare name
    halo models probe --all [--host H] [--force]            every model on the host (the default host without --host)

The cost line comes first ("about 8 requests to <model> on <host>, 1-3
minutes, no cost; it loads the model"), then one line per probe, then the
profile: where it sits, use it for / don't use it for, the limits. A cached
profile (the same digest, Ollama version and probe set) answers at once;
`--force` runs it again. The host's hardware card (for the usable window and
co-reside / pivot) is the Ollama panel's, read when none is cached.
"""

from __future__ import annotations

import argparse
import json
import sys


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="halo models probe", description="Run the capability battery on a local model "
                                "(tools, system role, instruction, JSON, thinking, reference ids, speed, fit)")
    p.add_argument("ref", nargs="?", default="", help="the model: ol:<name>@<host> or a bare Ollama name")
    p.add_argument("--host", default="", help="the ollama.hosts entry (the default host without it)")
    p.add_argument("--all", action="store_true", help="every model on the host")
    p.add_argument("--force", action="store_true", help="run it again although a profile is cached")
    p.add_argument("--json", action="store_true", help="the profiles as JSON")
    return p


def _target(ref: str, host_name: str) -> "tuple[str, str]":
    from halo_harness.providers.model_card_purpose import parse_ref
    if ref.startswith("ol:"):
        r = parse_ref(ref)
        return r.model, host_name or (r.host or "")
    return ref, host_name


def profile_lines(p: dict) -> list:
    from halo_harness.providers.battery_profile import date_of, summary_line
    from halo_harness.providers.model_card_blocks import block_lines, blocks
    out = [f"{p.get('model')} on {p.get('host')}: {summary_line(p)}" + (" (cached, probed " + date_of(p) + ")"
                                                                       if p.get("cached") else "")]
    out.append(f"  agentic-ready: {'yes' if p.get('agentic_ready') else 'no'} · interactive: {p.get('interactive')}")
    for q in p.get("quirks") or []:
        out.append(f"  quirk: {q}")
    out.extend(block_lines(blocks({"window": {}}, p)))
    out.extend(f"  {line}" for line in p.get("applied") or [])
    return out


def probe_one(host, model: str, *, force: bool, as_json: bool, state_dir) -> "tuple[int, dict]":
    from halo_harness.providers.capability_battery import cost_line, run
    from halo_harness.providers.fit_meter import host_card_of
    from halo_harness.providers.capability_battery import test_guard
    if not as_json:
        print(cost_line(model, host.name))
    card = host_card_of(host, read=test_guard(host) is None)

    def on(d: dict) -> None:
        if not as_json and d.get("say"):
            print(f"  {d['say']}", flush=True)
    p = run(host, model, card=card, on_status=on, state_dir=state_dir, force=force)
    if not p.get("ok"):
        if not as_json:
            print(f"halo models probe: {p.get('say')}", file=sys.stderr)
        return 1, p
    if not as_json:
        for line in profile_lines(p):
            print(line)
    return 0, p


def cmd_models_probe(argv: list) -> int:
    from halo_harness.config.paths import bridge_home
    from halo_harness.providers.ollama import resolve_ollama_host
    args = _parser().parse_args(argv)
    if not args.ref and not args.all:
        print("halo models probe: name a model (ol:<name>@<host>) or pass --all", file=sys.stderr)
        return 2
    model, host_name = _target(args.ref, args.host)
    host = resolve_ollama_host(host_name or None)
    if host is None:
        print(f"halo models probe: no Ollama host named {host_name!r} (halo ollama lists them)", file=sys.stderr)
        return 1
    names = [model] if model else []
    if args.all:
        from halo_harness.providers.ollama import get_catalog
        names = [r.get("model") or r.get("name") for r in get_catalog(host).get("models") or [] if isinstance(r, dict)
                 and "embedding" not in (r.get("capabilities") or [])]
        if not names:
            print(f"halo models probe: no models on {host.name}", file=sys.stderr)
            return 1
    code, got = 0, []
    for name in names:
        rc, p = probe_one(host, name, force=args.force, as_json=args.json, state_dir=bridge_home())
        code = max(code, rc)
        got.append(p)
    if args.json:
        print(json.dumps(got if args.all else got[0], indent=2, default=str))
    return code
