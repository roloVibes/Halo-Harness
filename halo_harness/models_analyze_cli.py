"""halo_harness.models_analyze_cli -- `halo models analyze [--json]` (Halo
3.1.9.0 R1): rebuild the "best at" cache (`models_best_at`) from the catalog
the way `halo models` lists it, then print one line per model (its kinds and
its best-at line) and, per kind, the cheapest and the strongest model.
`--json` prints the cache itself (`built`, `sources` by file name, `rows`,
`best`; 3.1.8.0 R3: and `measured`, the `halo models --measured` rows).
3.1.9.0 R3: a model dropped for a task kind (outcomes/learn.py) is marked
on its line and in the table ("dropped for code (1/4 in the last 30 days)").
Reads cached catalogs only: `halo models --refresh` re-pulls them.
"""

from __future__ import annotations

import argparse
import json


def _price(facts: dict) -> str:
    from halo_harness.model_display import format_price_per_m
    pin = format_price_per_m(facts.get("price_in_per_m")) or "?"
    pout = format_price_per_m(facts.get("price_out_per_m")) or "?"
    return f"{pin} / {pout}"


def summary_lines(cache: dict, state_dir=None) -> list:
    """The text `halo models analyze` prints (also handy for a test); 3.1.8.0 R3: with `state_dir`, the
    measured success per model and kind last (outcomes/measured.py)."""
    rows = cache.get("rows") or {}
    from halo_harness.outcomes.learn import marks as learned_marks  # 3.1.9.0 R3: dropped for a task kind
    marks = learned_marks(state_dir) if state_dir is not None else {}
    lines = [f"{len(rows)} model(s) analyzed -- kinds a model is good at, then what the catalog states and this host measured:"]
    for ref in sorted(rows):
        e = rows[ref]
        kinds = ",".join(e.get("kinds") or []) or "-"
        dropped = "; ".join(text for (model, _kind), text in sorted(marks.items()) if model == ref)
        lines.append(f"  {ref:<44} {kinds:<30} {e.get('line', '')}" + (f" -- {dropped}" if dropped else ""))
    best = cache.get("best") or {}
    if best:
        lines.append("Cheapest and strongest per kind (prices per 1M tokens in / out):")
        for kind, pick in best.items():
            strong = pick.get("strongest")
            cheap = pick.get("cheapest")
            text = f"  {kind:<9} strongest {strong} ({_price((rows.get(strong) or {}).get('facts') or {})})"
            if cheap and cheap != strong:
                text += f" · cheapest {cheap} ({_price((rows.get(cheap) or {}).get('facts') or {})})"
            lines.append(text)
    from halo_harness.outcomes.measured import success_by_model_kind, table_lines  # 3.1.8.0 R3
    stats = success_by_model_kind(state_dir) if state_dir is not None else {}
    if stats:
        lines.append("Measured success per model and kind here (`halo models --measured`):")
        lines += [f"  {line}" for line in table_lines(stats, marks)]
    return lines


def cmd_models_analyze(argv) -> int:
    parser = argparse.ArgumentParser(prog="halo models analyze",
                                     description="Rebuild what each model is good at (the best-at cache) and print it")
    parser.add_argument("--json", action="store_true", help="Print the cache as JSON")
    args = parser.parse_args(argv)
    from halo_harness.config.paths import bridge_home
    from halo_harness.models_best_at import catalog_rows, rebuild
    from halo_harness.providers.config import load_provider_env_files
    load_provider_env_files()
    state_dir = bridge_home()
    cache = rebuild(state_dir, catalog_rows(state_dir))
    if args.json:
        from halo_harness.outcomes.cli import measured_rows  # 3.1.8.0 R3: the measured rows beside the cache
        from halo_harness.outcomes.learn import marks
        from halo_harness.outcomes.measured import success_by_model_kind
        dropped = marks(state_dir)  # 3.1.9.0 R3: each row's mark ("" when the model is not dropped for the kind)
        measured = [dict(r, dropped=dropped.get((r["model"], r["kind"]), ""))
                    for r in measured_rows(success_by_model_kind(state_dir))]
        print(json.dumps(dict(cache, measured=measured), indent=1, ensure_ascii=False))
        return 0
    if not cache.get("rows"):
        print("No models in the catalog yet: `halo models --refresh` pulls every enabled provider's list.")
        return 1
    print("\n".join(summary_lines(cache, state_dir)))
    return 0
