// The model picker table (3.0.7.0 R2): every catalog row with its price in /
// out per 1M tokens, its context, what it is best at (3.1.9.0 R1: the kinds
// as chips -- visual, audio, video, image, design, pdf, code, research, bulk,
// fast, local -- and the one honest line under them, models_best_at) and its
// gym score on this machine; sort by name, price, context or best (the most
// kinds first), search by any of it; a click picks the row. A ref the catalog
// lacks can be typed below. "Test this model" sends the one-token probe
// (`POST models/test`) and shows ok and the latency, or the error, right
// under it.
import { useMemo, useState } from "react";
import { Button } from "../../lib/ui";
import { testModel } from "./bioActions";
import { useRoles } from "./store";
import type { ModelRow } from "./types";

type Sort = "name" | "price" | "context" | "best";
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

/** The "best at" cell: the kinds as chips, the line under them (the full line on hover). */
function BestAt({ m, kinds }: { m: ModelRow; kinds: string[] }) {
  const line = m.best_at?.line || "";
  return (
    <span className="rm-best" data-testid="model-best-at" title={line || undefined}>
      <span className="rm-kinds">{kinds.slice(0, 4).map((k) => <span key={k} className="og-chip mono" data-kind={k}>{k}</span>)}</span>
      {line && <span className="rm-line muted" data-testid="model-best-line">{line}</span>}
    </span>
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
  const kindsOf = (m: ModelRow) => m.best_at?.kinds || bestFor[m.ref] || [];
  const rows = useMemo(() => {
    const words = q.trim().toLowerCase().split(/\s+/).filter(Boolean);
    const text = (m: ModelRow) => [m.ref, m.group, m.detail, m.price, m.context, m.chips, m.best_at?.line, ...kindsOf(m)].join(" ").toLowerCase();
    const hit = models.filter((m) => words.every((w) => text(m).includes(w)));
    const by: Record<Sort, (a: ModelRow, b: ModelRow) => number> = {
      name: (a, b) => a.ref.localeCompare(b.ref),
      price: (a, b) => (a.price_in ?? 1e9) - (b.price_in ?? 1e9) || a.ref.localeCompare(b.ref),
      context: (a, b) => (b.context_tokens ?? 0) - (a.context_tokens ?? 0) || a.ref.localeCompare(b.ref),
      best: (a, b) => kindsOf(b).length - kindsOf(a).length || a.ref.localeCompare(b.ref),
    };
    return hit.sort(by[sort]);
  }, [models, q, sort, bestFor]);
  const inCatalog = !value || models.some((m) => m.ref === value);
  return (
    <div className="rm" data-testid="model-picker">
      <div className="rm-bar">
        <input className="input mono" placeholder="search: deepseek, flash, 200k, vision, pdf, code, cheap..." value={q} onChange={(e) => setQ(e.target.value)} data-testid="model-search" aria-label="Search the models" />
        <span className="segmented" role="group" aria-label="Sort">
          {(["name", "price", "context", "best"] as Sort[]).map((k) => (
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
          <div className="rm-row rm-head mono" aria-hidden="true"><span>model</span><span>in / out</span><span>ctx</span><span>best at</span><span>gym</span></div>
          {rows.slice(0, MAX_ROWS).map((m) => (
            <button key={m.ref} className="rm-row" role="option" aria-selected={m.ref === value} onClick={() => onPick(m.ref)} data-testid="model-row" data-ref={m.ref} title={m.detail || m.ref}>
              <span className="mono rm-ref">{m.ref}</span>
              <span className="mono">{money(m.price_in)} / {money(m.price_out)}</span>
              <span className="mono">{m.context}</span>
              <BestAt m={m} kinds={kindsOf(m)} />
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
