"""halo_harness.tui.slash_remote -- the TUI side of `/remote` (Halo 2.0.9
round 4): bare `/remote` opens the dialog, `/remote status|pair [N]|off` print
their text in the transcript, and a slow poll turns the bridge's notices
(changed safety number, rate limit, captcha) into notifications.

All file work runs on worker threads; the bridge is never started here.
"""

from __future__ import annotations

NOTICE_POLL_S = 5.0


async def handle_remote(app, args: str) -> None:
    if (args or "").strip():
        from halo_harness.tui.slash import _run_slash_worker
        app.run_worker(lambda: _run_slash_worker(app, "remote", args), thread=True, name="remote-text",
                       group="remote-text", exit_on_error=False)
        return
    app.run_worker(lambda: _open_dialog(app), thread=True, name="remote", group="remote", exit_on_error=False)


def _open_dialog(app) -> None:
    from halo_harness.remote import dialog_model
    from halo_harness.tui.dialogs.remote_status import RemoteStatus
    app.call_from_thread(app.push_screen, RemoteStatus(dialog_model.snapshot()))


def poll_notices_once(app) -> int:
    """Read and clear the bridge's notices; show each as a notification. Returns how many."""
    from halo_harness.remote import dialog_model
    notices = dialog_model.pop_notices()
    for n in notices:
        text = str(n.get("text") or n.get("kind") or "remote control notice")
        app.call_from_thread(app.notify, text, title="Remote control", severity="warning")
    return len(notices)


def start_notice_poll(app) -> None:
    """Called from the app's mount: only when `remote.enabled` (the Signal
    bridge's switch; its notices are the bridge's) is on."""
    from halo_harness.remote import runtime
    if not runtime.remote_enabled():
        return

    def tick() -> None:
        app.run_worker(lambda: _safe_poll(app), thread=True, name="remote-notices", group="remote-notices",
                       exit_on_error=False)
    app.set_interval(NOTICE_POLL_S, tick)


def _safe_poll(app) -> None:
    try:
        poll_notices_once(app)
    except Exception:
        pass
