// roles-problems (3.0.7.0 R2): everything wrong with the lineup as it stands
// in the editor, saved or not -- re-read with `POST validate` 250 ms after
// every edit -- in two blocks: Blocks (Save answers 422 for these, or a run
// start stops on them: a model id its catalog does not know, a bio with no
// tool) and Warns. Each row says how to fix it; a click selects its card.
// 3.1.1.0 R2: a third block, Config, lists what `halo doctor --config` finds
// in the files behind this lineup (ConfigProblems.tsx).
import { Empty } from "../../lib/ui";
import { focusPanel } from "../../lib/workspace/persist";
import { Metric } from "../orchestra/bits";
import { ConfigGroup, useConfigFindings } from "./ConfigProblems";
import { setTab, roles, useRoles } from "./store";
import type { Finding } from "./types";

function pick(f: Finding): void {
  if (!f.node) return;
  roles.update(() => ({ sel: f.node }));
  setTab("assignment");
  focusPanel("roles", "roles-graph");
}

function Group({ title, rows, sev }: { title: string; rows: Finding[]; sev: string }) {
  if (!rows.length) return null;
  return (
    <section className="rp-group" data-sev={sev}>
      <div className="rail-label mono">{title} · {rows.length}</div>
      <ul className="rp-list">
        {rows.map((f) => (
          <li key={f.id + f.text}>
            <button className="rp-row" data-sev={f.severity} data-node={f.node || undefined} onClick={() => pick(f)} disabled={!f.node} data-testid="roles-problem"
                    title={f.node ? "Select its card" : undefined}>
              <span className="rp-dot" aria-hidden="true" />
              <span className="rp-text">{f.text}</span>
              {f.fix && <span className="rp-fix muted">fix: {f.fix}</span>}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function ProblemsDetail() {
  const findings = useRoles((s) => s.findings);
  const name = useRoles((s) => s.name);
  const config = useConfigFindings();
  if (!name) return <Empty title="No lineup open" body="Open one in Lineups: its problems show here as you edit it." />;
  const blocks = findings.filter((f) => f.severity === "blocks");
  const warns = findings.filter((f) => f.severity !== "blocks");
  if (!findings.length && !config.length) return <Empty title="No problems" body="The lineup validates, every model is in its catalog, every bio has its tools and its files pass halo doctor --config." testid="roles-problems-none" />;
  return (
    <div className="rp" data-testid="roles-problems-list">
      <Group title="BLOCKS" rows={blocks} sev="blocks" />
      <Group title="WARNS" rows={warns} sev="warns" />
      <ConfigGroup rows={config} />
    </div>
  );
}

export function ProblemsGlance() {
  const blocks = useRoles((s) => s.findings.filter((f) => f.severity === "blocks").length);
  const warns = useRoles((s) => s.findings.filter((f) => f.severity !== "blocks").length);
  const config = useConfigFindings().length;
  return (
    <div className="glance">
      <div className="glance-numbers">
        <Metric value={blocks} label="blocks" tone={blocks ? "bad" : "ok"} />
        <Metric value={warns} label="warns" tone={warns ? "warn" : undefined} />
        {config > 0 && <Metric value={config} label="config" tone="warn" />}
      </div>
      <div className="glance-hint">Expand to see each one with its fix.</div>
    </div>
  );
}

export function useProblemsMotion() {
  const blocks = useRoles((s) => s.findings.some((f) => f.severity === "blocks"));
  const any = useRoles((s) => s.findings.length > 0);
  return blocks ? ("error" as const) : any ? ("waiting" as const) : ("idle" as const);
}
