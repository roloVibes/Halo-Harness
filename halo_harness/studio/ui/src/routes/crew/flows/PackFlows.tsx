// A pack's crew workflows, each with Run it (3.6.0.6 P): drawn by Studio itself -- in a pack's own section, above
// the section's page (App.tsx), and under the pack in the Pack Manager (Details.tsx) -- never by the pack's script,
// whose scoped client is not given the route. The rows come with the pack registry (packs/studio_registry.py
// `crew_workflows`), so the row is there from the section's first draw. A pack with none: no row.
import { usePacks } from "../../packs/store";
import { RunFlow } from "./RunFlow";

const NONE: { name: string; problems: string[] }[] = [];

export function PackFlows({ pack, where }: { pack: string; where: string }) {
  const rows = usePacks((s) => s.reg.crew_workflows?.[pack]) || NONE;
  if (!rows.length) return null;
  return (
    <div className="rf-list rf-pack" data-testid="pack-flows" data-pack={pack} data-where={where}>
      {rows.map((r) => (
        <div key={r.name} className="rf-item rf-inline" data-testid="pack-flow" data-name={r.name}>
          <b className="cw-item-name mono">{r.name}</b>
          <RunFlow name={r.name} scope="pack" problems={r.problems} where={where} />
        </div>
      ))}
    </div>
  );
}
