"""halo_harness.tui.slash_fleet -- the TUI side of `/fleet` (Halo 3.0.5.0
"Fleet" round R2): bare `/fleet` opens the FleetTable dialog (the fleet view
read on a worker thread, never the UI thread); `/fleet text` prints the same
table in the transcript (commands/builtins.py, also what `halo -p "/fleet"`
prints)."""

from __future__ import annotations


async def handle_fleet(app, args: str) -> None:
    if (args or "").strip():
        from halo_harness.tui.slash import _run_slash_worker
        app.run_worker(lambda: _run_slash_worker(app, "fleet", args), thread=True, name="fleet-text",
                       group="fleet-text", exit_on_error=False)
        return
    app.run_worker(lambda: _open_dialog(app), thread=True, name="fleet", group="fleet", exit_on_error=False)


def _open_dialog(app) -> None:
    from halo_harness.fleet.table import snapshot
    from halo_harness.tui.dialogs.fleet_table import FleetTable
    view, source = snapshot()
    app.call_from_thread(app.push_screen, FleetTable(view, source))
