// A machine in Agents -> Live's inspector (3.3.16.0 R2 "the Fleet fold"; R1b's summary first, one block per page): its
// People row (name, host, version chip, what it shares and lets you do, what it is on, Message / Kick), its Health
// row (the doctor line: providers, versions, disk, sockets, with Refresh), what it spent today per session, then one
// Edit row per block -- Specs (Capabilities' spec card under the "Who can..." box, and the recall box), Spend caps
// (`POST fleet/caps`; the same keys are Settings -> Fleet's `fleet.caps.*`), and on this halo Sharing and control (Setup
// -> Machines, where the radio rows are). Back or Esc returns to the summary. Fleet's People, Health, Capabilities and
// Costs panels drew these before.
import { useEffect, useMemo, type KeyboardEvent, type ReactNode } from "react";
import { goSection } from "../../../lib/store";
import { Button } from "../../../lib/ui";
import { cost, short } from "../../orchestra/format";
import { CapsCard } from "../../fleet/Capabilities";
import { startCaps, useCaps } from "../../fleet/caps";
import { Caps, useCosts } from "../../fleet/Costs";
import { HealthRowView, useHealth } from "../../fleet/Health";
import { Person } from "../../fleet/People";
import { usePanels } from "../../fleet/pstore";
import { RecallBox } from "../../fleet/Recall";
import { useFleet, useNow } from "../../fleet/store";
import { WhoBox } from "../../fleet/Who";
import { goto as gotoSettings } from "../../settings/pages";
import { goto as gotoSetup } from "../../setup/pages";
import { setMachinePage, useMachinePage } from "./scope";

type Row = { id: string; title: string; state: string; open: () => void };

function EditRows({ rows }: { rows: Row[] }) {
  return (
    <ul className="ri-rows" aria-label="Edit one block">
      {rows.map((r) => (
        <li key={r.id} className="ri-row" data-density="row" data-block={r.id}>
          <button className="ri-row-main" onClick={r.open} data-testid={`machine-block-${r.id}`}>
            <span className="ri-row-title">{r.title}</span>
            <span className="ri-row-state mono">{r.state}</span>
          </button>
          <Button size="sm" variant="ghost" onClick={r.open} data-testid={`machine-edit-${r.id}`} aria-label={`Edit ${r.title}`}>Edit</Button>
        </li>
      ))}
    </ul>
  );
}

function Page({ title, children }: { title: string; children: ReactNode }) {
  const back = () => setMachinePage("");
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => e.key === "Escape" && (e.preventDefault(), e.stopPropagation(), back());
  return (
    <div className="ri-page" data-testid="machine-page" data-block={title} onKeyDown={onKey}>
      <header className="ri-page-head" data-density="bar">
        <Button size="sm" variant="ghost" onClick={back} data-testid="machine-page-back" title="Back to the summary (Esc)">Back</Button>
        <b>{title}</b>
      </header>
      {children}
    </div>
  );
}

function Spend({ hid }: { hid: string }) {
  const costs = usePanels((s) => s.costs); // the list itself: a filtered copy is a new value on every read (React re-renders forever)
  const rows = useMemo(() => (costs?.sessions || []).filter((x) => x.harness === hid), [costs, hid]);
  const total = costs?.harnesses.find((h) => h.id === hid);
  return (
    <section className="lv-spend" data-testid="machine-spend">
      <div className="rail-label mono">SPENT TODAY · {cost(total?.usd ?? 0)}</div>
      {total && <div className="fco-row" data-testid="fleet-cost-harness"><span>{total.name}{total.local ? " (here)" : ""}</span><span className="mono muted">{total.sessions} s</span><b className="mono">{cost(total.usd)}</b></div>}
      {rows.map((s) => (
        <div key={s.session_id} className="fco-row"><span>{short(s.title, 36)}</span><span className="mono muted">{s.today ? "today" : "earlier"}</span><b className="mono">{cost(s.usd)}</b></div>
      ))}
    </section>
  );
}

export function MachineSummary({ hid }: { hid: string }) {
  useEffect(() => startCaps(), []);
  useHealth();
  useCosts();
  const h = useFleet((s) => s.harnesses.find((x) => x.id === hid));
  const hubHere = useFleet((s) => !!s.hub?.serving);
  const now = useNow(true, 5000);
  const page = useMachinePage();
  const health = usePanels((s) => s.health?.harnesses.find((x) => x.id === hid));
  const capsRow = useCaps((s) => s.rows?.find((r) => r.harness === hid));
  const costs = usePanels((s) => s.costs);
  if (!h) return <p className="muted" data-testid="machine-gone">That machine is not in the fleet any more.</p>;
  if (page === "specs")
    return (
      <Page title="Specs and who can...">
        <div className="fcap" data-testid="fleet-caps-detail">
          <WhoBox />
          {capsRow ? <ul className="fcap-list"><CapsCard r={capsRow} now={now} /></ul> : <p className="muted">reading what it can do...</p>}
          <RecallBox />
        </div>
      </Page>
    );
  if (page === "caps")
    return (
      <Page title="Spend caps">
        <p className="muted">A cap reached pauses the sessions in its scope and raises an Attention row; the same keys are Settings -&gt; Remote (<code>fleet.caps.*</code>).</p>
        {costs ? <Caps c={costs} /> : <p className="muted">reading today's spend...</p>}
        <Button size="sm" variant="ghost" onClick={() => (gotoSettings("remote"), goSection("settings"))} data-testid="machine-caps-settings">Open Settings -&gt; Remote</Button>
      </Page>
    );
  const capsSet = costs ? Object.values(costs.caps || {}).filter((v) => v != null).length : 0;
  const rows: Row[] = [
    { id: "specs", title: "Specs and who can...", state: capsRow?.chips.join(" · ") || capsRow?.summary || "its catalog", open: () => setMachinePage("specs") },
    { id: "caps", title: "Spend caps", state: capsSet ? `${capsSet} cap${capsSet === 1 ? "" : "s"} set` : "not set = no cap", open: () => setMachinePage("caps") },
  ];
  if (h.local) rows.push({ id: "sharing", title: "Sharing and control", state: "Setup -> Machines", open: () => (gotoSetup("machines"), goSection("setup")) });
  return (
    <div className="ri-sum lv-machine" data-testid="machine-summary" data-harness={hid}>
      <ul className="fpe"><Person h={h} now={now} hubHere={hubHere} /></ul>
      {health ? <ul className="fhe-list"><HealthRowView h={health} now={now} /></ul> : <p className="muted mono">asking it how it is...</p>}
      <Spend hid={hid} />
      <EditRows rows={rows} />
    </div>
  );
}
