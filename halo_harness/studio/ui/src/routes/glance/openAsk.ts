// The one door of an ask (3.4.1.0 R4; 3.6.0.1, the owner's report from live use of 3.6.0.0: "when I get an attention
// alert and chose 'open' nothing happens"; 3.6.0.2 P4 batch 9, the owner's point 20): a click on an alert's notification
// in the shell (lib/alerts.ts) and O on an ask's row (Attention in Session or over Agents, the Feed: fleet/extras.ts
// answerRow and openTarget) land on the RUN'S DRAWING with the asking agent's box selected and its card open -- the
// ask's choices, Pause, Stop, Steer (crew/map/askBox.ts): Agents -> 4 · Live when he is in Agents, else Session with
// that session chosen, the Live column's agent pick on the asking agent, its Live drawer open and Attention open on the
// row (an optional panel not in the saved view is added). The queue's panel in Agents closes only as the card opens. An
// agent the drawing puts on no box (P4 batch 12): the Feed opens on that agent with its ask (handed to the Feed by the
// door itself, so it is there when the line says so, even before its frame came: P9 batch 2), one line says so
// (askOffMap), nothing else closes (in Session the Attention drawer the Live drawer took the place of comes back). A
// door asked before its section laid out is kept and applied at the first layout (lib/workspace/kept.ts). A session
// Studio has not read yet (its first ask came before the list's next read): the list is read once, then the door lands;
// still not there, it has ended: one line says so and nothing moves; a read that failed says so. Another machine's ask,
// or a row of no session: Session's Attention on the row (its drawing is in that machine's Studio). The glance shows the
// ask on its own page instead (routes/glance/Glance.tsx).
import { goSection, studio, toast } from "../../lib/store";
import { keepAsk } from "../../lib/workspace/kept";
import { focusPanel, layoutStore, NOT_HERE, patchPanel, showPanel, specsFor } from "../../lib/workspace/persist";
import { setAttention } from "../agents/attention";
import { askBox } from "../crew/map/askBox";
import { openFeed } from "../crew/map/feedOpen";
import { setFeedFor } from "../crew/map/litStore";
import { askEnded, askOffMap } from "../crew/map/truthBits";
import { panels, type AttnRow } from "../fleet/pstore";
import { findAgent, findSession, fleet, keyOf, localId } from "../fleet/store";
import { load } from "../fleet/sync";
import { lastRow } from "../session/pick";
import { pinTo } from "../session/steer";
import { openInLive, openSession, sess, setSessionView, showsSessionStart } from "../session/store";
import { handAsk } from "../shared/liveFeed";

/** What a door needs of an ask: an Attention row, or an `o` answer's target (fleet/extras.ts openTarget). */
export type AskRef = Pick<AttnRow, "harness" | "session_id" | "agent_id"> & Partial<Pick<AttnRow, "id" | "local">>;

export const UNREAD = "Studio could not read the sessions just now. Try Open again.";

/** Session's Attention drawer open (added first when the saved view has no such panel) and given the focus. */
function openAttention(): void {
  const id = "session-attention";
  const cur = layoutStore("session").get().layout;
  if (!cur) return keepAsk("session", id, openAttention); // applied at Session's first layout
  if (cur[id]) {
    patchPanel("session", id, { collapsed: false }, false);
    return focusPanel("session", id);
  }
  const spec = specsFor("session")?.find((s) => s.id === id);
  if (spec) showPanel("session", spec);
  else toast(NOT_HERE, "info");
}

/** The door's line "its question is in the Feed" is true when it is said (P9 batch 2): the ask itself, the attention row
 *  the door was opened with (read at the press), is handed to the Feed first (shared/liveFeed.ts handAsk). */
function offMap(row: AskRef, sid: string, aid: string): (name: string) => void {
  const r = panels.get().attention.find((x) => !!row.id && x.id === row.id) || ("keys" in row ? (row as AttnRow) : undefined);
  return (name) => {
    if (r) handAsk(keyOf(row.harness, sid, aid), r);
    toast(askOffMap(name), "info", 8000);
  };
}

function land(row: AskRef): void {
  const sid = row.session_id || "";
  const aid = row.agent_id || "main";
  const f = fleet.get();
  if (row.id) panels.update(() => ({ attnSel: row.id || "", replyFor: "" }));
  const local = row.local ?? (!f.loaded || row.harness === localId(f));
  if (sid && local && studio.get().section === "agents") {
    setFeedFor(`agent:${aid}`);
    const said = offMap(row, sid, aid);
    askBox("live", sid, aid, {
      found: () => setAttention(false), // the card carries the ask: the queue's panel would lie over it
      stranger: (name) => (openFeed(`agent:${aid}`), said(name)),
    });
    return openInLive(sid);
  }
  if (sid && local) {
    const asked = keyOf(row.harness, sid, aid);
    const main = keyOf(row.harness, sid, "main");
    const key = findAgent(f, asked) ? asked : findAgent(f, main) ? main : "";
    const said = offMap(row, sid, aid);
    askBox("session", sid, aid, { stranger: (name) => (openAttention(), said(name)) });
    openSession(key ? { key } : { session: sid });
    pinTo(key);
  } else goSection("session");
  if (showsSessionStart(fleet.get(), sess.get().view)) setSessionView("workspace");
  openAttention();
  if (sid && local) patchPanel("session", "session-map", { collapsed: false }, false);
}

/** Open `row`'s ask where it can be answered (see the head of this file). */
export function openAsk(row: AskRef): void {
  const sid = row.session_id || "";
  const here = (): boolean => !!fleet.get().loaded && !!findSession(fleet.get(), row.harness, sid);
  if (!sid || here()) return land(row);
  const ended = (): void => void toast(askEnded(lastRow(sid)?.ended || 0), "info", 6000);
  void load().then(() => (here() ? land(row) : fleet.get().error ? toast(UNREAD, "error", 5000) : ended()), () => toast(UNREAD, "error", 5000));
}
