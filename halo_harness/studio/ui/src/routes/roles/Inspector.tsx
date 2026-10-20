// roles-inspector (3.0.7.0 R2): three tabs. Assignment edits the selected
// card's slot (with no card: the lineup's description and about); Lineup is
// every top section as a small form with its YAML toggle; Live shows what the
// agents on the selected card do right now (it opens by itself when a card
// with a live agent is clicked). 3.1.4.0 R4: above the tabs, the MODEL strip
// (ModelStrip.tsx): what the selected card runs on and the select to change it.
import { Tabs } from "../../lib/ui";
import { Metric } from "../orchestra/bits";
import { Assignment } from "./Assignment";
import { LineupTab } from "./LineupTab";
import { useByNode } from "./live";
import { LiveTab } from "./LiveTab";
import { ModelStrip } from "./ModelStrip";
import { nodeById, setTab, useRoles, type InspectorTab } from "./store";

export function InspectorDetail() {
  const tab = useRoles((s) => s.tab);
  const sel = useRoles((s) => s.sel);
  const byNode = useByNode();
  const liveHere = sel ? (byNode[sel] || []).length : 0;
  const anyLive = Object.keys(byNode).length;
  return (
    <div className="ri" data-testid="roles-inspector-body">
      <ModelStrip />
      <Tabs
        label="Inspector"
        value={tab}
        onChange={(t) => setTab(t as InspectorTab)}
        items={[
          { id: "assignment", label: "Assignment", testid: "roles-tab-assignment" },
          { id: "lineup", label: "Lineup", testid: "roles-tab-lineup" },
          { id: "live", label: liveHere ? `Live · ${liveHere}` : "Live", testid: "roles-live-tab", motion: anyLive ? "working" : "none", title: "What the agents on this card do right now: their streams, Steer, Pause, Stop" },
        ]}
      />
      <div className="ri-body">{tab === "assignment" ? <Assignment /> : tab === "lineup" ? <LineupTab /> : <LiveTab />}</div>
    </div>
  );
}

export function InspectorGlance() {
  const n = useRoles((s) => nodeById(s, s.sel));
  const byNode = useByNode();
  return (
    <div className="glance">
      <div className="glance-kicker mono">{n ? n.role.toUpperCase() : "NO CARD"}</div>
      <div className="glance-text">{n ? n.agent : "Click a card"}</div>
      <div className="glance-numbers">
        <Metric value={Object.keys(byNode).length} label="live cards" tone={Object.keys(byNode).length ? "accent" : undefined} />
      </div>
    </div>
  );
}
