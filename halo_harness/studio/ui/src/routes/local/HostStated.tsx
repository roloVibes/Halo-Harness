// 3.3.7.0 R2: a host-served card's server settings (POST local/host/<name>/server-line, studio/local_host_api.py):
// the KV cache type, flash attention or a restart, asked of the halo host that serves it. The host answers with the
// exact line for its OS and `applied: false` -- a stated action: Halo never changes a server setting and never
// restarts a server; you run the line there.
import { useState } from "react";
import { Button } from "../../lib/ui";
import { act, useLocal } from "./store";

const CHOICES: { id: string; label: string; op: string; value?: unknown }[] = [
  { id: "kv-q8_0", label: "KV cache q8_0", op: "set_kv_cache_type", value: "q8_0" },
  { id: "kv-f16", label: "KV cache f16", op: "set_kv_cache_type", value: "f16" },
  { id: "fa-on", label: "flash attention on", op: "set_flash_attn", value: true },
  { id: "fa-off", label: "flash attention off", op: "set_flash_attn", value: false },
  { id: "restart", label: "restart Ollama", op: "restart_ollama" },
];

export function HostStated({ name }: { name: string }) {
  const [pick, setPick] = useState(CHOICES[0].id);
  const busy = useLocal((s) => !!s.busy);
  const said = useLocal((s) => s.said[`line|${name}`]);
  const ask = () => {
    const c = CHOICES.find((x) => x.id === pick) || CHOICES[0];
    void act(`line|${name}`, `local/host/${encodeURIComponent(name)}/server-line`, { op: c.op, value: c.value });
  };
  return (
    <div className="lc-add" data-testid="local-host-stated">
      <label className="mono muted">server setting{" "}
        <select value={pick} onChange={(e) => setPick(e.target.value)} data-testid="local-host-stated-pick">
          {CHOICES.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
        </select>
      </label>
      <Button size="sm" variant="ghost" disabled={busy} onClick={ask} data-testid="local-host-stated-ask"
              title="the halo host answers with the exact line for its OS; nothing is applied (you run it there)">The line</Button>
      {said && <div className="mono lc-said" data-ok={said.ok || undefined} data-testid="local-host-stated-said">{said.text}</div>}
    </div>
  );
}
