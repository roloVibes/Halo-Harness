// roles-problems, Config group (3.1.1.0 R2): what `halo doctor --config` finds
// in the files behind the open lineup -- its own file and the ones it extends,
// config.json's `team:` naming it, a flow or team file naming it, the same
// lineup in two folders with different contents. Read with
// `GET doctor/config?lineup=<name>` when the lineup opens and after each save.
import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import { useRoles } from "./store";

export type ConfigFinding = { id: string; severity: "blocks" | "warns"; text: string; fix: string; file: string; check: string };

export function useConfigFindings(): ConfigFinding[] {
  const name = useRoles((s) => s.name);
  const saved = useRoles((s) => s.current);
  const [rows, setRows] = useState<ConfigFinding[]>([]);
  useEffect(() => {
    let live = true;
    if (!name) {
      setRows([]);
      return;
    }
    api
      .get<{ findings: ConfigFinding[] }>("doctor/config", { lineup: name })
      .then((r) => live && setRows(Array.isArray(r.findings) ? r.findings : []))
      .catch(() => live && setRows([]));
    return () => {
      live = false;
    };
  }, [name, saved]);
  return rows;
}

export function ConfigGroup({ rows }: { rows: ConfigFinding[] }) {
  if (!rows.length) return null;
  return (
    <section className="rp-group" data-sev="config" data-testid="roles-problems-config">
      <div className="rail-label mono">CONFIG · {rows.length}</div>
      <ul className="rp-list">
        {rows.map((f) => (
          <li key={f.id}>
            <div className="rp-row" data-sev={f.severity} data-check={f.check} data-testid="roles-problem-config" title={f.file}>
              <span className="rp-dot" aria-hidden="true" />
              <span className="rp-text">
                <span className="mono muted">{f.file}</span> {f.text}
              </span>
              {f.fix && <span className="rp-fix muted">fix: {f.fix}</span>}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
