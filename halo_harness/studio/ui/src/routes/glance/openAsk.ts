// ONE door for "open this ask" (3.6.0.1; the owner's report from live use of 3.6.0.0: "when I get an attention alert and
// chose 'open' nothing happens"). The alert's click (3.4.1.0 R4, lib/alerts.ts), an Attention row's O and the Live ask
// card's O (routes/fleet/extras.ts `openTarget`) all come here: Session, the row's session selected, the Feed pointed at
// the asking agent (the Live column's agent pick), the Attention drawer open with that row selected, its answers one key
// away. The section may still be mounting: the drawer opens once its layout is up (an optional panel not in the saved
// view is added). A row of no session (a cap, a conflict) opens Attention on it as before. Never silent: a session that
// has ended says so in one toast line. A row of another harness (Session shows this one's) goes to `elsewhere`, else
// Agents' Attention on it. The glance shows the ask on its own page instead (routes/glance/Glance.tsx).
import { goSection, toast } from "../../lib/store";
import { focusPanel, layoutStore, patchPanel, showPanel, specsFor, whenLaidOut } from "../../lib/workspace/persist";
import { setAttention } from "../agents/attention";
import { findAgent, findSession, fleet, keyOf, localId } from "../fleet/store";
import { panels, type AttnRow } from "../fleet/pstore";
import { load } from "../fleet/sync";
import { pinTo } from "../session/steer";
import { openSession, sess, setSessionView, showsSessionStart } from "../session/store";

export type AskRef = Pick<AttnRow, "harness" | "session_id" | "agent_id"> & { id?: string };

export const GONE = "That session has ended; its ask is gone.";

/** Session's Attention drawer open (added first when the saved view has no such panel) and given the focus. */
function openAttention(): void {
  const id = "session-attention";
  if (layoutStore("session").get().layout?.[id]) {
    patchPanel("session", id, { collapsed: false }, false);
    focusPanel("session", id);
    return;
  }
  const spec = specsFor("session")?.find((s) => s.id === id);
  if (spec) showPanel("session", spec);
  else toast("Session has no Attention panel here: open it from the view bar", "info", 5000);
}

function land(row: AskRef): void {
  const s = fleet.get();
  const sid = row.session_id || "";
  if (sid) {
    const asked = keyOf(row.harness, sid, row.agent_id || "main");
    const main = keyOf(row.harness, sid, "main");
    const key = findAgent(s, asked) ? asked : findAgent(s, main) ? main : "";
    openSession(key ? { key } : { session: sid });
    pinTo(key);
  } else goSection("session");
  if (showsSessionStart(fleet.get(), sess.get().view)) setSessionView("workspace");
  whenLaidOut("session", openAttention);
}

/** Open `row`'s ask where it can be answered (see the head of this file). */
export function openAsk(row: AskRef, elsewhere?: () => void): void {
  if (row.id) panels.update(() => ({ attnSel: row.id || "", replyFor: "" }));
  const sid = row.session_id || "";
  const here = (): boolean => !!fleet.get().loaded && !!sid && !!findSession(fleet.get(), row.harness, sid);
  const local = (): boolean => !fleet.get().loaded || row.harness === localId(fleet.get());
  const go = (): void => {
    if (!local()) return elsewhere ? elsewhere() : (goSection("agents"), setAttention(true));
    land(row);
  };
  if (!sid || here()) return go();
  // a session Studio has not read yet (its first ask came before the fleet's next read), or one that has ended
  void load().then(() => (here() ? go() : toast(GONE, "info", 5000)), () => toast(GONE, "info", 5000));
}
