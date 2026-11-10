// Setup -> Machines (3.3.16.0 R2 "the Fleet fold": machines are Setup -- pairing, sharing, people; the step rail's last
// step before the Summary). While only this harness is here, Fleet's Start view's five lines lead the page (what
// pairing gives you); then the pair card (the one-time six-word code, the `halo fleet join` line to type on the other
// machine and its QR; Start the hub when none runs here), the share / control settings as radio rows (`fleet.share`,
// `fleet.allow_control`) and the hubs this harness joined, and the People table: one row per harness with its Halo
// version chip (amber when it differs: `halo update`), what it shares and what it is on, Message and Forget (this
// machine's hub only, asks first). Their agents show on Agents -> Live, their models in Local.
import { useEffect } from "react";
import { Empty } from "../../lib/ui";
import { FleetSettings, PairCard } from "../fleet/Pair";
import { Person } from "../fleet/People";
import { useFleet, useNow } from "../fleet/store";
import { startFleet } from "../fleet/sync";
import { Explain, MACHINES_WHAT } from "../shared/StartBits";

function People() {
  const harnesses = useFleet((s) => s.harnesses);
  const hubHere = useFleet((s) => !!s.hub?.serving);
  const loaded = useFleet((s) => s.loaded);
  const now = useNow(true, 5000);
  if (!loaded) return <div className="og-wait mono muted">reading the machines...</div>;
  if (!harnesses.length) return <Empty title="Nobody here yet" body="This harness shows as soon as Studio reads it; another one joins with a pair code." />;
  return (
    <section className="su-machines-people" aria-label="People">
      <div className="rail-label mono">PEOPLE · {harnesses.length} MACHINE{harnesses.length === 1 ? "" : "S"}</div>
      <ul className="fpe" data-testid="fleet-people-list">
        {harnesses.map((h) => <Person key={h.id} h={h} now={now} hubHere={hubHere} />)}
      </ul>
    </section>
  );
}

export function MachinesDetail() {
  useEffect(() => startFleet(), []);
  const alone = useFleet((s) => s.loaded && s.harnesses.length <= 1);
  return (
    <div className="su-machines" data-testid="setup-machines">
      {alone && (
        <div className="su-machines-lead" data-testid="setup-machines-lead">
          <Explain lines={MACHINES_WHAT} />
        </div>
      )}
      <PairCard />
      <FleetSettings />
      <People />
    </div>
  );
}
