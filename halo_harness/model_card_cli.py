"""halo_harness.model_card_cli -- Halo 3.3.5.0 R0b: `halo models show <ref>`
(the model card: what the model is, its fit here, how Halo will call it, the
roles it can hold), `halo models --cards` (one line per model) and, 3.3.6.0 R6, `halo models --vision` (the
models that can see, with the truth).

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
    parser.add_argument("ref", help="a model ref, e.g. ol:qwen3-coder:30b@lan (with --host: the model's name)")
    parser.add_argument("--host", default="", help="3.3.5.0 R3: the ollama.hosts entry; the ref is then the model's name")
    parser.add_argument("--json", action="store_true", help="the card as JSON")
    args = parser.parse_args(argv)
    from halo_harness.providers.config import load_provider_env_files
    load_provider_env_files()
    ref = args.ref
    if args.host and not ref.startswith(("ol:", "or:", "hf:", "ant:", "db:", "local:")):
        ref = f"ol:{ref}@{args.host}"  # `halo models show qwen3.5:9b --host box`
    card, meter = card_and_meter(ref, bridge_home())
    facts = _show_facts(ref)
    if args.json:
        print(json.dumps({**_public(card, meter), **({"api_show": facts} if facts else {})}, indent=2, default=str))
        return 0
    for line in card_lines(card, meter) + show_lines(facts):
        print(line)
    return 0


def _show_facts(ref: str) -> Optional[dict]:
    """3.3.5.0 R3: `/api/show` of an Ollama ref (providers/ollama_control.show), None for any other ref."""
    from halo_harness.providers.model_card import parse_ref
    from halo_harness.providers.ollama import resolve_ollama_host
    from halo_harness.providers.ollama_control import show
    r = parse_ref(ref)
    if r.provider != "ollama":
        return None
    host = resolve_ollama_host(r.host)
    got = show(host, r.model) if host is not None else {"ok": False, "say": f"no Ollama host named {r.host!r}"}
    return {"ok": got["ok"], "say": got["say"], "facts": got.get("facts"), "show": got.get("show")}


def show_lines(got: Optional[dict]) -> list:
    if not got:
        return []
    if not got["ok"]:
        return [f"/api/show: {got['say']}"]
    f, s = got["facts"] or {}, got["show"] or {}
    lines = ["/api/show: " + ", ".join(f"{k} {v}" for k, v in f.items() if v not in (None, ""))]
    if s.get("capabilities"):
        lines.append("  capabilities: " + ", ".join(map(str, s["capabilities"])))
    if s.get("params"):
        lines.append("  parameters: " + ", ".join(f"{k} {v}" for k, v in s["params"].items()))
    if s.get("license"):
        lines.append("  licence: " + str(s["license"]).strip().splitlines()[0][:100])
    if s.get("template"):
        lines.append(f"  template: {len(str(s['template'])):,} characters (--json prints it)")
    return lines


def all_cards(state_dir) -> list:
    """[(card, meter)] for every catalog row, local ones first (`--cards`, `--vision`); raises when the catalog fails."""
    from halo_harness.providers.fit_meter import fit_meter, host_card_of
    from halo_harness.providers.model_card import card_of, parse_ref
    from halo_harness.studio.model import catalog_rows
    rows = sorted(catalog_rows(state_dir), key=lambda r: (not r.get("local"), str(r.get("ref"))))
    out = []
    for row in rows:
        ref = parse_ref(str(row["ref"]))
        catalog, host = (None, None)
        if ref.provider == "ollama":
            catalog, host = _catalog_for(ref, state_dir)
        card = card_of(ref, state_dir=state_dir, catalog=catalog if ref.provider == "ollama" else row, host=host,
                       host_card=host_card_of(host) if host is not None else None)
        out.append((card, fit_meter(card, host_card_of(host) if host is not None else None)))
    return out


def cmd_models_cards(*, as_json: bool = False) -> int:
    """`halo models --cards`: one line per model, local ones first."""
    from halo_harness.config.paths import bridge_home
    from halo_harness.providers.model_card_words import card_line
    try:
        out = all_cards(bridge_home())
    except Exception as e:
        print(f"halo models --cards: could not read the catalog: {e}", file=sys.stderr)
        return 1
    if as_json:
        print(json.dumps([_public(c, m) for c, m in out], indent=2, default=str))
        return 0
    for card, meter in out:
        print(card_line(card, meter))
    local = sum(1 for c, _m in out if c.get("kind") != "cloud")
    print(f"{len(out)} models ({local} local); halo models show <ref> prints one card in full")
    return 0


def cmd_models_vision(*, as_json: bool = False) -> int:
    """3.3.6.0 R6: `halo models --vision`: the models that can see, each with its truth and source
    (providers/vision_fact.py), then how many say nothing (the probe settles a local one)."""
    from halo_harness.config.paths import bridge_home
    try:
        out = all_cards(bridge_home())
    except Exception as e:
        print(f"halo models --vision: could not read the catalog: {e}", file=sys.stderr)
        return 1
    rows = [{"ref": c.get("ref"), "vision": c.get("vision"), "truth": c.get("vision_truth"),
             "source": (c.get("sources") or {}).get("vision"), "kind": c.get("kind")} for c, _m in out]
    sees = [r for r in rows if r["vision"] is True]
    unknown = [r for r in rows if r["vision"] is None]
    if as_json:
        print(json.dumps({"sees": sees, "unknown": unknown}, indent=2, default=str))
        return 0
    for r in sees:
        print(f"{r['ref']}: sees ({r['truth']}: {r['source']})")
    local = [r for r in unknown if r["kind"] != "cloud"]
    print(f"{len(sees)} of {len(rows)} models can see images" + (
        f"; {len(unknown)} say nothing ({len(local)} local: halo models probe <ref> settles it)" if unknown else ""))
    return 0
