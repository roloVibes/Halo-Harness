// The Fleet dialogs, in the shell so a key or a menu in any section can open
// them: Stop / Shut down ask first ("Stop it" has the focus, so K then
// Enter stops). 3.3.16.0 R2: the pair card is Setup -> Machines' (the palette's
// "Setup: pair a machine" opens it there), no dialog of its own.
import { useEffect } from "react";
import { Button, Dialog } from "../../lib/ui";
import { confirmed } from "./actions";
import { fleet, useFleet } from "./store";

const close = () => fleet.update(() => ({ confirm: null }));

export function FleetDialogs() {
  const c = useFleet((s) => s.confirm);
  useEffect(() => {
    if (!c) return;
    const id = window.setTimeout(() => document.querySelector<HTMLElement>('[data-testid="fleet-confirm-yes"]')?.focus(), 0);
    return () => window.clearTimeout(id);
  }, [c]);
  return (
    <>
      {c && (
        <Dialog
          open
          onClose={close}
          title={c.what === "stop" ? `Stop ${c.label}?` : `Shut ${c.label} down?`}
          kicker="FLEET"
          testid="fleet-confirm"
          footer={
            <>
              <Button onClick={close}>Cancel</Button>
              <Button variant="danger" onClick={() => void confirmed()} data-testid="fleet-confirm-yes">
                {c.what === "stop" ? "Stop it" : "Shut it down"}
              </Button>
            </>
          }
        >
          <p className="fs-confirm">
            {c.what === "stop"
              ? "It stops at its next tool or model call, its own sub-agents with it; the agent that spawned it gets the stopped hand-back and carries on."
              : "The session ends after its current tool call; its agents stop with it."}
          </p>
        </Dialog>
      )}
    </>
  );
}
