"""halo_harness.tui.lane_offer_flow -- Halo 3.3.5.0 R0b (d): what the TUI does
with the main-model line (`turn_marker` state "model-check", written by
agent/main_model_check.py after `/model` or the picker): the line in the
transcript and, when there is an offer, the one-key card under it. Accepting
writes the lineup and makes it active (the `halo teams apply` path), then
moves the session to the orchestrator; any other key goes ahead as it is.
"""

from __future__ import annotations

import logging

log = logging.getLogger("bridge")


async def show(app, data: dict) -> None:
    line = data.get("line") or data.get("text") or ""
    offer = data.get("offer")
    if not offer or getattr(app, "pending_card", None) is not None:
        await app.transcript.add_note(data.get("text") or line, kind="marker")
        return
    from halo_harness.tui.widgets.lane_offer import LaneOfferCard

    def on_decide(accepted: bool) -> None:
        app.clear_pending_card()
        if accepted:
            app.run_worker(lambda: accept_worker(app, offer), thread=True, name="lane-offer", group="lane-offer",
                           exit_on_error=False)

    card = LaneOfferCard(line=line, offer=offer, on_decide=on_decide)
    await app.transcript.mount_widget(card)
    app.set_pending_card(card)


def accept_worker(app, offer: dict) -> None:
    from halo_harness.agent.main_model_check import accept
    controller = app.controller
    try:
        ok, lines = accept(offer, session=getattr(controller, "session", None), cwd=getattr(app, "cwd", None))
    except Exception as e:  # the lineup write failed: say why, the model stays as it is
        log.debug("lane offer: accept failed", exc_info=True)
        ok, lines = False, [f"{type(e).__name__}: {e}"]
    if not ok:
        app.call_from_thread(app.transcript.add_note, "The lineup was not written: " + "; ".join(lines), kind="command")
        return
    err = controller.set_model(offer["orchestrator"])
    if not err:
        try:
            from halo_harness import launch_state
            launch_state.record_last_model(offer["orchestrator"], cwd=app.cwd)
        except Exception:
            log.debug("lane offer: the last model was not recorded", exc_info=True)
    tail = [f"main moves to {offer['orchestrator']}" if not err else f"main could not move to {offer['orchestrator']}: {err}"]
    app.call_from_thread(app.transcript.add_note, "\n".join(lines[:1] + tail + lines[1:]), kind="command")
