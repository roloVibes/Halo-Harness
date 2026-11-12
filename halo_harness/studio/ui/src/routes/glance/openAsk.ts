// A click on an alert's notification in the shell (3.4.1.0 R4, lib/alerts.ts): Session, its Attention panel open (not a
// strip) and that row selected, its answers one key away -- where a click on a waiting ask in Live leads too
// (routes/session/LiveRows.tsx). The section may still be mounting: the panel opens once its layout is up. The glance
// shows the ask on its own page instead (routes/glance/Glance.tsx).
import { goSection } from "../../lib/store";
import { patchPanel, whenLaidOut } from "../../lib/workspace/persist";
import { panels, type AttnRow } from "../fleet/pstore";

export function openAsk(row: AttnRow): void {
  panels.update(() => ({ attnSel: row.id }));
  goSection("session");
  whenLaidOut("session", () => patchPanel("session", "session-attention", { collapsed: false }, false));
}
