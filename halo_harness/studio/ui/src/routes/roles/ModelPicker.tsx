// The model picker table (3.0.7.0 R2): every catalog row with its price in /
// out per 1M tokens, its context, what it is best for (capabilities.score:
// visual, audio, video, image, design) and its gym score on this machine;
// sort by name, price or context, search by any of it; a click picks the
// row. A ref the catalog lacks can be typed below. "Test this model" sends
// the one-token probe (`POST models/test`) and shows ok and the latency, or
// the error, right under it.
import { useMemo, useState } from "react";
import { Button } from "../../lib/ui";
import { testModel } from "./bioActions";
import { useRoles } from "./store";
import type { ModelRow } from "./types";

type Sort = "name" | "price" | "context";
const MAX_ROWS = 150;
const money = (v: number | null) => (typeof v === "number" ? "$" + (v < 1 ? v.toFixed(2) : v.toFixed(v < 10 ? 2 : 0)) : "?");

export function TestButton({ value }: { value: string }) {
  const probe = useRoles((s) => (value ? s.probe[value] : undefined));
  return (
    <div className="rm-test">
      <Button size="sm" disabled={!value || probe === "running"} onClick={() => void testModel(value)} data-testid="model-test"
              title="A one-token round trip through the same path a session uses (it spends a fraction of a cent)">
        {probe === "running" ? "Testing..." : "Test this model"}
      </Button>
      {probe && probe !== "running" && (
        <span className="rm-test-result mono" data-ok={probe.ok || undefined} data-testid="model-test-result" title={probe.cost_line}>
          {probe.ok ? `ok in ${probe.latency_ms} ms` : `failed: ${probe.error || "no reply"}`}
        </span>
      )}
    </div>
  );
}

export function ModelPicker({ value, onPick }: { value: string; onPick: (ref: string) => void }) {
  const models = useRoles((s) => s.models);
  const loaded = useRoles((s) => s.modelsLoaded);
  const bestFor = useRoles((s) => s.bestFor);
  const gym = useRoles((s) => s.gym);
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<Sort>("name");
  const [typed, setTyped] = useState("");
  const rows = useMemo(() => {
    const words = q.trim().toLowerCase().split(/\s+/).filter(Boolean);
    const text = (m: ModelRow) => [m.ref, m.group, m.detail, m.price, m.context, m.chips, ...(bestFor[m.ref] || [])].join(" ").toLowerCase();
    const hit = models.filter((m) => words.every((w) => text(m).includes(w)));
    const by: Record<Sort, (a: ModelRow, b: ModelRow) => number> = {
      name: (a, b) => a.ref.localeCompare(b.ref),
      price: (a, b) => (a.price_in ?? 1e9) - (b.price_in ?? 1e9) || a.ref.localeCompare(b.ref),
      context: (a, b) => (b.context_tokens ?? 0) - (a.context_tokens ?? 0) || a.ref.localeCompare(b.ref),
    };
    return hit.sort(by[sort]);
  }, [models, q, sort, bestFor]);
  const inCatalog = !value || models.some((m) => m.ref === value);
  return (
    <div className="rm" data-testid="model-picker">
      <div className="rm-bar">
        <input className="input mono" placeholder="search: deepseek, flash, 200k, vision, design..." value={q} onChange={(e) => setQ(e.target.value)} data-testid="model-search" aria-label="Search the models" />
        <span className="segmented" role="group" aria-label="Sort">
          {(["name", "price", "context"] as Sort[]).map((k) => (
            <button key={k} className={sort === k ? "on" : ""} aria-pressed={sort === k} onClick={() => setSort(k)} data-testid={`model-sort-${k}`}>{k}</button>
          ))}
        </span>
      </div>
      {!loaded ? (
        <div className="og-wait mono muted">reading the catalog...</div>
      ) : !models.length ? (
        <p className="muted" data-testid="models-empty">No models in the catalog yet: the Models panel says why and has Refresh.</p>
      ) : (
        <div className="rm-table" role="listbox" aria-label="Models">
          <div className="rm-row rm-head mono" aria-hidden="true"><span>model</span><span>in / out</span><span>ctx</span><span>best for</span><span>gym</span></div>
          {rows.slice(0, MAX_ROWS).map((m) => (
            <button key={m.ref} className="rm-row" role="option" aria-selected={m.ref === value} onClick={() => onPick(m.ref)} data-testid="model-row" data-ref={m.ref} title={m.detail || m.ref}>
              <span className="mono rm-ref">{m.ref}</span>
              <span className="mono">{money(m.price_in)} / {money(m.price_out)}</span>
              <span className="mono">{m.context}</span>
              <span className="rm-best">{(bestFor[m.ref] || []).slice(0, 3).map((k) => <span key={k} className="og-chip mono">{k}</span>)}</span>
              <span className="mono">{gym[m.ref] ? gym[m.ref].score.toFixed(2) : ""}</span>
            </button>
          ))}
          {rows.length > MAX_ROWS && <p className="muted rm-more">{rows.length - MAX_ROWS} more: narrow the search.</p>}
          {!rows.length && <p className="muted rm-more">No model matches "{q}".</p>}
        </div>
      )}
      <div className="rm-typed">
        <input className="input mono" placeholder="or type a ref the catalog lacks (or:vendor/model)" value={typed} onChange={(e) => setTyped(e.target.value)}
               onKeyDown={(e) => e.key === "Enter" && typed.trim() && (onPick(typed.trim()), setTyped(""))} aria-label="A model ref by hand" />
        <Button size="sm" variant="ghost" disabled={!typed.trim()} onClick={() => (onPick(typed.trim()), setTyped(""))}>Use it</Button>
      </div>
      <div className="rm-current mono">
        picked: <b>{value || "(none)"}</b>
        {value && !inCatalog && <span className="rm-warn"> · not in the catalog</span>}
      </div>
      <TestButton value={value} />
    </div>
  );
}
