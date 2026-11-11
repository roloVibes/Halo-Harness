"""The first-run pack's doctor row (`contributes.doctor`, Halo 3.4.0.0 B2): `halo doctor` shows it under "From packs"
while the pack is enabled and granted `doctor`. One row: the guided first run is ready to rehearse your lineup, or what
is missing first -- a provider with a key, then a lineup of your own (on Auto it would rehearse one model five times).
"""

from __future__ import annotations


def rows(ctx) -> list:
    from halo_harness.ext import core
    try:
        ok, text = core.module("checks.provider").ready()
    except Exception as e:
        ok, text = False, f"{type(e).__name__}: {e}"
    if not ok:
        return [{"ok": False, "text": f"the guided first run needs a provider first: {text}",
                 "fix": "halo init (Studio's Setup -> Providers)"}]
    from .first_run.auto_gate import AUTO_LINE, lineup_now, on_auto
    if on_auto():
        return [{"ok": False, "text": AUTO_LINE, "fix": "halo studio --mode agents (Cast), then halo teams use <name>"}]
    name, _source = lineup_now()
    return [f"the guided first run is ready to rehearse lineup {name}: halo start --explain says what it costs"]
