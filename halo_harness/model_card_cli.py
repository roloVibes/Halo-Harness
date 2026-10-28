"""halo_harness.model_card_cli -- Halo 3.3.5.0 R0b: `halo models show <ref>`
(the model card: what the model is, its fit here, how Halo will call it, the
roles it can hold) and `halo models --cards` (one line per model).

`show` reads the model's host the way `halo local` does (an Ollama host's
`/api/tags` + `/api/show`, the tool-call probe's cache file) and the host's
hardware card for the fit meter; it never loads a model. `--cards` reads the
configured local servers once (the `/local` view), then every catalog row.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional


def _catalog_for(ref, state_dir, *, cached: bool = False) -> "tuple[Optional[dict], object]":
    """(the catalog or row the card reads, the Ollama host or None); `cached`: what this process already read."""
    from halo_harness.providers.model_card import parse_ref
    r = parse_ref(ref) if isinstance(ref, str) else ref
    if r.provider == "ollama":
        from halo_harness.providers.ollama import get_catalog, resolve_ollama_host
        host = resolve_ollama_host(r.host)
        if host is None:
            return None, None
        if cached:
            from halo_harness.providers.local_models_cached import cached_catalog
            return cached_catalog(host), host
        try:
            return get_catalog(host), host
        except Exception:
            return None, host
    try:
        from halo_harness.studio.model import catalog_rows
        row = next((x for x in catalog_rows(state_dir, cached=True) if x.get("ref") == r.raw), None)
    except Exception:
        row = None
    return row, None


def card_and_meter(ref: str, state_dir, *, read_hardware: bool = True, cached: bool = False) -> "tuple[dict, dict]":
    from halo_harness.providers.fit_meter import fit_meter, host_card_of
    from halo_harness.providers.model_card import card_of
    catalog, host = _catalog_for(ref, state_dir, cached=cached)
    host_card = host_card_of(host, read=read_hardware) if host is not None else None
    card = card_of(ref, state_dir=state_dir, catalog=catalog, host=host, host_card=host_card)
    return card, fit_meter(card, host_card)


def _public(card: dict, meter: dict) -> dict:
    return {**{k: v for k, v in card.items() if not k.startswith("_")}, "fit": meter}


def cmd_models_show(argv: list) -> int:
    from halo_harness.config.paths import bridge_home
    from halo_harness.providers.model_card_words import card_lines
    parser = argparse.ArgumentParser(prog="halo models show", add_help=True,
                                     description="The model card: what the model is, how Halo calls it, its fit here.")
    parser.add_argument("ref", help="a model ref, e.g. ol:qwen3-coder:30b@lan")
    parser.add_argument("--json", action="store_true", help="the card as JSON")
    args = parser.parse_args(argv)
    from halo_harness.providers.config import load_provider_env_files
    load_provider_env_files()
    card, meter = card_and_meter(args.ref, bridge_home())
    if args.json:
        print(json.dumps(_public(card, meter), indent=2, default=str))
        return 0
    for line in card_lines(card, meter):
        print(line)
    return 0


def cmd_models_cards(*, as_json: bool = False) -> int:
    """`halo models --cards`: one line per model, local ones first."""
    from halo_harness.config.paths import bridge_home
    from halo_harness.providers.fit_meter import fit_meter, host_card_of
    from halo_harness.providers.model_card import card_of, parse_ref
    from halo_harness.providers.model_card_words import card_line
    from halo_harness.studio.model import catalog_rows
    state_dir = bridge_home()
    try:
        rows = catalog_rows(state_dir)
    except Exception as e:
        print(f"halo models --cards: could not read the catalog: {e}", file=sys.stderr)
        return 1
    rows = sorted(rows, key=lambda r: (not r.get("local"), str(r.get("ref"))))
    out = []
    for row in rows:
        ref = parse_ref(str(row["ref"]))
        catalog, host = (None, None)
        if ref.provider == "ollama":
            catalog, host = _catalog_for(ref, state_dir)
        card = card_of(ref, state_dir=state_dir, catalog=catalog if ref.provider == "ollama" else row, host=host,
                       host_card=host_card_of(host) if host is not None else None)
        meter = fit_meter(card, host_card_of(host) if host is not None else None)
        out.append((card, meter))
    if as_json:
        print(json.dumps([_public(c, m) for c, m in out], indent=2, default=str))
        return 0
    for card, meter in out:
        print(card_line(card, meter))
    local = sum(1 for c, _m in out if c.get("kind") != "cloud")
    print(f"{len(out)} models ({local} local); halo models show <ref> prints one card in full")
    return 0
