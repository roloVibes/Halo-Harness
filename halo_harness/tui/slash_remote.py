"""halo_harness.tui.slash_remote -- the TUI side of `/remote` (Halo 2.0.9 round 4; 3.3.13.0 R3: the Signal dialog
left with the Signal bridge, now the signal pack).

`/remote` prints the control socket's status in the transcript (remote/status.text: this session's socket, the
registry, `remote.enabled`, the transports listening, the packs' services). A slow poll keeps the remote chip on the
transports: with no phone attached to this session it names the transport that listens ("signal"), or the pack
service that should run and does not ("signal/bridge off"). All file work runs on worker threads.
"""

from __future__ import annotations

CHIP_POLL_S = 15.0


async def handle_remote(app, args: str) -> None:
    from halo_harness.tui.slash import _run_slash_worker
    app.run_worker(lambda: _run_slash_worker(app, "remote", args or ""), thread=True, name="remote-text",
                   group="remote-text", exit_on_error=False)


def poll_chip_once(app) -> str:
    from halo_harness.remote.status import chip
    text = chip()
    app.call_from_thread(app.status_bar.set_transport, text)
    return text


def start_notice_poll(app) -> None:
    """Called from the app's mount: the chip's poll (only while some pack declares a service or a transport listens)."""
    def tick() -> None:
        app.run_worker(lambda: _safe_poll(app), thread=True, name="remote-chip", group="remote-chip",
                       exit_on_error=False)
    app.set_interval(CHIP_POLL_S, tick)
    tick()


def _safe_poll(app) -> None:
    try:
        poll_chip_once(app)
    except Exception:
        pass
