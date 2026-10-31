// The KV dial's Halo-side half (3.3.6.0 R5; providers/kv_dial.py `apply`): the profile's window set to the one this
// card holds at the KV type in force (verified by the bench when it ran), with its scope -- keep preselected, or until
// halo exits, or until the session ends -- through POST local/changes/apply (agent_proposals.land_user). The server's
// half (the KV cache type itself) stays the stated line: Halo never sets it.
import { useState } from "react";
import { Button } from "../../lib/ui";
import { applyChange, useBench, type Scope } from "../local/benchstore";
import { ScopePick } from "./ScopePick";

export type KvApplyView = { key: string; field: string; to: number; line: string };

export function KvApply({ a }: { a: KvApplyView }) {
  const [scope, setScope] = useState<Scope>("keep");
  const said = useBench((s) => s.said[`kv|${a.key}`]);
  return (
    <div className="kv-apply" data-testid="model-card-kv-apply">
      <span>{a.line}</span>
      <ScopePick value={scope} onChange={setScope} name={`kv-${a.key}`} testid="kv-scope" />
      <Button size="sm" onClick={() => void applyChange(a.key, a.field, a.to, scope, "the KV dial", `kv|${a.key}`)} data-testid="kv-apply"
              title={`ollama.profiles["${a.key}"].${a.field} = ${a.to}`}>Apply</Button>
      {said && <span className="mono lc-said" data-ok={said.ok || undefined} data-testid="kv-said">{said.text}</span>}
    </div>
  );
}
