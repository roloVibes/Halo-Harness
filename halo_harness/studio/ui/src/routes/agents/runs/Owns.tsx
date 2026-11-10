// Who owns what (3.3.16.0 R1: what Team's board gave, now a run-plan detail): each lane's owns line -- the claim
// ledger's keys for that lane ("owns src/api.py#login, tests/test_api.py") -- on its plan card and its row in Lanes,
// and the ledger's rows for a lane (holder, state) where the lane is inspected: the plan inspector and the lane
// focused in Lanes. The rows are the run's ClaimLog as GET orchestra/<run> carries it (`claims`); a lane's keys are
// the ones its holder has claimed, else the units the plan gave it (`claims` on the lane or the plan job).
import { useOrch } from "../../orchestra/store";
import type { Claim, Lane } from "../../orchestra/types";

const NO_CLAIMS: Claim[] = [];

/** The ledger rows of a lane: held by it (`lane:<n>` or its holder's name), or for one of the units it owns. */
export function ledgerOf(claims: Claim[], keys: string[], lane?: Pick<Lane, "lane" | "holder"> | null): Claim[] {
  const mine = new Set([...(lane ? [`lane:${lane.lane}`] : []), ...(lane?.holder ? [lane.holder] : [])]);
  return claims.filter((c) => mine.has(c.holder) || keys.includes(c.key));
}

/** The keys a lane owns: the ones its holder claimed in the ledger, else the units the plan gave it. */
export function ownsOf(lane: Pick<Lane, "lane" | "holder" | "claims">, claims: Claim[]): string[] {
  const held = ledgerOf(claims, [], lane).map((c) => c.key);
  return held.length ? [...new Set(held)] : lane.claims || [];
}

/** One line: OWNS and the keys, shortened to the panel's width (the whole list in its tooltip). */
export function OwnsLine({ keys, testid }: { keys: string[]; testid: string }) {
  const text = keys.length ? keys.join(", ") : "nothing yet";
  return (
    <span className="ag-owns mono" data-testid={testid} data-count={keys.length} title={`owns ${text}`}>
      <b>OWNS</b>
      {text}
    </span>
  );
}

/** The ledger's rows for a lane: key, holder, state; one line when it holds none yet. */
export function LaneClaims({ keys, lane }: { keys: string[]; lane?: Pick<Lane, "lane" | "holder"> | null }) {
  const claims = useOrch((s) => s.data?.claims || NO_CLAIMS);
  const rows = ledgerOf(claims, keys, lane);
  if (!rows.length)
    return <p className="muted mono ag-claims-none" data-testid="lane-claims" data-count={0}>No claim held: a worker claims its units when it joins, and a finished run holds none.</p>;
  return (
    <ul className="ag-claims mono" data-testid="lane-claims" data-count={rows.length}>
      {rows.map((c) => (
        <li key={c.key} data-testid="lane-claim" data-state={c.state} data-holder={c.holder}>
          <span title={c.key}>{c.key}</span>
          <span className="muted">{c.holder}</span>
          <span>{c.state}</span>
        </li>
      ))}
    </ul>
  );
}
