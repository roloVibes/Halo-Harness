// The Fleet tree, the Fleet section's Tree panel (`fleet-tree`, optional: the
// header's "+" menu adds it; 3.3.2.0 R2 moved it out of the expanded rail of
// every section, where 3.0.5.0 had put it): the fleet as a tree, harness >
// session > agent, each with its status dot; the live and the need-you counts
// at the top. Click a node: this harness's opens the Session section on it
// (3.1.4.0 R2: the session chosen, the agent selected), a member's selects it
// on the map. A session that waits on you keeps its inline answer
// (shell/Sessions.tsx), for this harness and for a member. R4: the need-you
// count is the attention queue's (a click opens Attention), and the "While you
// were away" card shows at the top after ten minutes away (the Fleet icon in
// the rail carries a dot meanwhile, and a click on it opens this panel).
// 3.0.6.0 R8: a mission part's session (`mission-worker`) carries a `mission`
// chip; its `mission` link opens the Mission panel on that mission and part.
import { useEffect, useState } from "react";
import { Empty } from "../../lib/ui";
import { goSection, type SessionInfo } from "../../lib/store";
import { layoutStore, showPanel } from "../../lib/workspace/persist";
import type { PanelSpec } from "../../lib/workspace/types";
import { HELP } from "../help";
import { Answer } from "../../shell/Sessions";
import { openSession } from "../session/store";
import { select } from "./actions";
import { DigestCard } from "./Digest";
import { showFleetPanel } from "./extras";
import { openMission } from "./mload";
import { useAttnCount } from "./pstore";
import { agentMotion, enterWorkspace, fleet, keyOf, sessionMotion, sessionTitle, showsStart, treeOf, useCounts, useFleet } from "./store";
import { load, startFleet } from "./sync";
import type { Harness, SessionRow } from "./types";

const MAX_AGENTS = 12;

/** A click on a node: this harness's opens Session on it (a session row: that session), a member's selects it in Fleet. */
function open(key?: string, local = false, session = ""): void {
  if (local) return openSession(session ? { session } : key ? { key } : {});
  goSection("fleet");
  enterWorkspace();
  if (key) select(key);
}

function Session({ h, s }: { h: Harness; s: SessionRow }) {
  const [answer, setAnswer] = useState(false);
  const selected = useFleet((st) => st.selected);
  const doneAt = useFleet((st) => st.doneAt);
  const tree = treeOf(s.agents || []);
  const mainKey = keyOf(h.id, s.session_id, tree[0]?.a.agent_id || "main");
  const waiting = s.status === "waiting";
  const path = h.local ? undefined : `fleet/${encodeURIComponent(h.id)}/${encodeURIComponent(s.session_id)}/command`;
  return (
    <div className="fr-session">
      <div className="fr-srow">
        <button className="rail-item fr-row" data-kind="session" data-id={s.session_id} data-testid="fleet-tree-node" onClick={() => open(mainKey, !!h.local, s.session_id)}
                title={`${sessionTitle(s)} · ${s.cwd || ""}${h.local ? " · opens it in Session" : ""}`}>
          <span className="fr-dot" data-status={s.status || "unknown"} data-motion={sessionMotion(s)} aria-hidden="true" />
          <span className="rail-item-text">{sessionTitle(s)}</span>
          {s.mission && <span className="badge fr-mission" data-testid="fleet-tree-mission" title={`mission ${s.mission} part ${s.part}`}>mission</span>}
          <span className="badge" data-status={s.status || "unknown"}>{s.status || "?"}</span>
        </button>
        {s.mission && (
          <button className="og-link mono fr-answer" onClick={() => openMission(String(s.mission), String(s.part || ""))} title={`open mission ${s.mission} in the Mission panel`} data-testid="fleet-tree-mission-open">
            part {String(s.part || "?")}
          </button>
        )}
        {waiting && (
          <button className="og-link mono fr-answer" onClick={() => setAnswer(!answer)} aria-expanded={answer}>
            answer
          </button>
        )}
      </div>
      {waiting && answer && <Answer s={s as unknown as SessionInfo} path={path} after={() => void load()} />}
      {tree.slice(0, MAX_AGENTS).map(({ a, depth }) => {
        const key = keyOf(h.id, s.session_id, a.agent_id);
        return (
          <button key={key} className="rail-item fr-row fr-agent" style={{ paddingLeft: 20 + depth * 12 }} data-kind="agent" data-id={a.agent_id} data-testid="fleet-tree-node"
                  aria-current={selected === key || undefined} onClick={() => open(key, !!h.local)} title={`${a.name || a.agent_id}: ${a.state}${a.current ? " · " + a.current : ""}`}>
            <span className="fr-adot" data-state={a.state || "none"} data-motion={agentMotion(a, doneAt[key] || 0)} aria-hidden="true" />
            <span className="rail-item-text">{a.name || a.role || a.agent_id}</span>
            <span className="mono fr-state" data-state={a.state || "none"}>{a.state}</span>
          </button>
        );
      })}
      {tree.length > MAX_AGENTS && <div className="rail-note fr-more">+{tree.length - MAX_AGENTS} more on the map</div>}
    </div>
  );
}

function Counts() {
  const c = useCounts();
  const attn = useAttnCount(c.attention);
  return (
    <div className="rail-label mono">
      FLEET · {c.live} LIVE
      {attn > 0 && (
        <button className="fr-attn fr-attn-btn" onClick={() => showFleetPanel("fleet-attention")} title="Open Attention: every decision that waits on you" data-testid="fleet-tree-attention">
          {" "}· {attn} NEED{attn === 1 ? "S" : ""} YOU
        </button>
      )}
    </div>
  );
}

/** The Tree panel's full face: the away card, the counts, then every harness. */
export function TreeDetail() {
  useEffect(() => startFleet(), []);
  const harnesses = useFleet((s) => s.harnesses);
  const loaded = useFleet((s) => s.loaded);
  const c = useCounts();
  return (
    <section className="fr fr-panel" aria-label="Fleet tree" data-testid="fleet-tree-list">
      <DigestCard where="tree" />
      <Counts />
      {harnesses.map((h) => (
        <div key={h.id} className="fr-harness">
          <button className="rail-item fr-row fr-h" data-kind="harness" data-id={h.id} data-testid="fleet-tree-node" onClick={() => open(undefined, !!h.local)} title={[h.name, h.host, h.version, h.local ? "this harness" : h.online ? "online" : "offline"].filter(Boolean).join(" · ")}>
            <span className="fr-dot" data-status={h.local || h.online ? "online" : "offline"} aria-hidden="true" />
            <span className="rail-item-text">{h.name || h.id.slice(0, 8)}</span>
            {h.version_mismatch && <span className="badge fr-version" title="another Halo version: `halo update` on the older one">{h.version}</span>}
            <span className="badge mono">{(h.sessions || []).reduce((n, s) => n + (s.agents || []).length, 0)}</span>
          </button>
          {(h.sessions || []).map((s) => (
            <Session key={s.session_id} h={h} s={s} />
          ))}
        </div>
      ))}
      {loaded && !c.sessions && <Empty title="No session yet" body="Run halo in a terminal: it shows up here." />}
    </section>
  );
}

/** The compact face: the counts and the away card. */
export function TreeGlance() {
  useEffect(() => startFleet(), []);
  const c = useCounts();
  return (
    <div className="glance fr-panel">
      <DigestCard where="tree" />
      <Counts />
      <div className="glance-hint">{c.sessions} session{c.sessions === 1 ? "" : "s"} across the fleet; expand for the tree.</div>
    </div>
  );
}

/** The Tree panel (Fleet.tsx lists it last): optional, the header's "+" adds it, in the right-hand column under the strips. */
export const treePanel: PanelSpec = {
  id: "fleet-tree", testid: "fleet-tree", ...HELP["fleet-tree"], title: "Tree", x: 18, y: 0, w: 6, h: 40, minW: 5, minH: 14, face: "detail", optional: true,
  glance: TreeGlance, detail: TreeDetail,
};

/** Fleet on its Tree panel, added when it is not on the page (the Fleet icon's away dot, the palette's while you were away);
 *  the Start view shows the away card itself. */
export function openTree(): void {
  goSection("fleet");
  if (showsStart(fleet.get())) return;
  enterWorkspace();
  const go = () => showPanel("fleet", treePanel);
  if (layoutStore("fleet").get().layout) go();
  else window.setTimeout(go, 150);
}
