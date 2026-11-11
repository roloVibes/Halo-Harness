// A failed agent stays on Live until it is acknowledged (3.3.18.0 "The living canvas", now.ts): its node carries one
// small button that says so. A click takes it off the canvas (its group goes too when it was the last one there) and
// stops its red glow on Cast; the session it ran in keeps it in History.
import type { MouseEvent } from "react";
import { ackFailed } from "../../roles/glow";
import type { LiveAgent } from "../../roles/types";
import { dismiss } from "./now";

export function DismissFailed({ k, name }: { k: string; name: string }) {
  const go = (e: MouseEvent) => {
    e.stopPropagation();
    dismiss(k);
    ackFailed([{ key: k, state: "failed" } as LiveAgent]);
  };
  return (
    <button className="rlm-dismiss mono" onClick={go} onDoubleClick={(e) => e.stopPropagation()} data-testid="roles-live-dismiss" data-hover-skip
            title={`Seen: take ${name}, which failed, off the canvas (Cast stops glowing for it; its session keeps it in History)`}>
      dismiss
    </button>
  );
}
