// One lineup section as a small form (3.0.7.0 R2), from its definition in
// sections.ts: every change is one `edit` of the open lineup (undoable; the
// Problems panel re-validates). Rows edit org positions, pipeline stages and
// tiers; a mapping edits routing; members are toggles of the lineup's
// aliases. The YAML toggle (YamlBox) edits the raw section instead.
// 3.1.1.0 R3: each field's help line is field_help.py's (lib/fieldHelp.ts).
import { useMemo, useState } from "react";
import { useHelpGroup } from "../../lib/fieldHelp";
import { Button } from "../../lib/ui";
import { edit } from "./actions";
import { Check, ListIn, NumberIn, Pick, Row, TextIn } from "./controls";
import { getPath, setPath, type Col, type FieldDef, type SectionDef } from "./sections";
import { agentsOf, useRoles } from "./store";
import type { Raw } from "./types";

type Rec = Record<string, unknown>;

/** Every role and alias the lineup's cards define (what routing, stages and positions may name). */
export function useTargets(): string[] {
  const raw = useRoles((s) => s.raw);
  return useMemo(() => {
    const out = new Set<string>();
    for (const e of agentsOf(raw)) {
      if (e.as) out.add(String(e.as));
      if (e.role) out.add(String(e.role));
    }
    return [...out];
  }, [raw]);
}

function change(def: SectionDef, path: string, v: unknown): void {
  edit((raw) => {
    if (!path) {
      if (v === undefined || (Array.isArray(v) && !v.length) || (v && typeof v === "object" && !Object.keys(v as Rec).length)) delete raw[def.name];
      else raw[def.name] = v;
      return;
    }
    const body = (raw[def.name] && typeof raw[def.name] === "object" && !Array.isArray(raw[def.name]) ? raw[def.name] : {}) as Rec;
    setPath(body, path, v);
    if (Object.keys(body).length) raw[def.name] = body;
    else delete raw[def.name];
  });
}

function Cell({ col, value, onChange, targets }: { col: Col; value: unknown; onChange: (v: unknown) => void; targets: string[] }) {
  if (col.kind === "members") {
    const on = Array.isArray(value) ? (value as string[]) : [];
    return (
      <span className="re-members">
        {targets.map((t) => (
          <button key={t} className="re-member mono" aria-pressed={on.includes(t)} onClick={() => onChange(on.includes(t) ? on.filter((x) => x !== t) : [...on, t])}>{t}</button>
        ))}
      </span>
    );
  }
  if (col.kind === "select" || col.kind === "target") {
    const opts = col.kind === "target" ? ["", ...targets] : col.options || [];
    return <Pick value={String(value ?? "")} options={opts} onChange={onChange} />;
  }
  if (col.kind === "number") return <NumberIn value={typeof value === "number" ? value : undefined} onCommit={onChange} />;
  if (col.kind === "list") return <ListIn value={Array.isArray(value) ? (value as string[]) : []} onCommit={onChange} hint="" />;
  return <TextIn value={String(value ?? "")} onCommit={onChange} />;
}

function Rows({ def, f, value, targets, hint }: { def: SectionDef; f: Extract<FieldDef, { kind: "rows" }>; value: unknown; targets: string[]; hint?: string }) {
  const rows = (Array.isArray(value) ? value : []) as Rec[];
  const put = (next: Rec[]) => change(def, f.path, next);
  return (
    <Row label={f.label} hint={hint}>
      <div className="re-rows" data-testid={`roles-rows-${def.name}`}>
        <div className="re-row re-row-head mono" style={{ gridTemplateColumns: `${f.cols.map((c) => (c.width ? c.width + "px" : "minmax(0,1fr)")).join(" ")} 28px` }}>
          {f.cols.map((c) => <span key={c.key}>{c.label}</span>)}
          <span />
        </div>
        {rows.map((r, i) => (
          <div key={i} className="re-row" style={{ gridTemplateColumns: `${f.cols.map((c) => (c.width ? c.width + "px" : "minmax(0,1fr)")).join(" ")} 28px` }}>
            {f.cols.map((c) => (
              <Cell key={c.key} col={c} value={r?.[c.key]} targets={targets} onChange={(v) => {
                const next = rows.map((x) => ({ ...x }));
                if (v === undefined || v === "" || (Array.isArray(v) && !v.length && c.kind !== "members")) delete next[i][c.key];
                else next[i][c.key] = v;
                put(next);
              }} />
            ))}
            <button className="icon-btn" title="Remove this row" aria-label="Remove this row" onClick={() => put(rows.filter((_x, j) => j !== i))}>×</button>
          </div>
        ))}
        <Button size="sm" variant="ghost" onClick={() => put([...rows, { ...f.add }])}>Add a row</Button>
      </div>
    </Row>
  );
}

function MapRows({ def, f, value, targets, hint }: { def: SectionDef; f: Extract<FieldDef, { kind: "map" }>; value: unknown; targets: string[]; hint?: string }) {
  const map = (value && typeof value === "object" && !Array.isArray(value) ? value : {}) as Record<string, string>;
  const [key, setKey] = useState("");
  const put = (next: Record<string, string>) => change(def, f.path, next);
  return (
    <Row label={f.label} hint={hint}>
      <div className="re-rows">
        {Object.entries(map).map(([k, v]) => (
          <div key={k} className="re-row" style={{ gridTemplateColumns: "minmax(0,1fr) minmax(0,1fr) 28px" }}>
            <span className="mono re-key">{k}</span>
            <Pick value={String(v)} options={targets} onChange={(t) => put({ ...map, [k]: t })} />
            <button className="icon-btn" aria-label={`Remove ${k}`} onClick={() => put(Object.fromEntries(Object.entries(map).filter(([x]) => x !== k)))}>×</button>
          </div>
        ))}
        <div className="re-row" style={{ gridTemplateColumns: "minmax(0,1fr) auto" }}>
          <input className="input" value={key} placeholder={`a ${f.keyLabel}`} onChange={(e) => setKey(e.target.value)} />
          <Button size="sm" variant="ghost" disabled={!key.trim() || key.trim() in map} onClick={() => (put({ ...map, [key.trim()]: targets[0] || "main" }), setKey(""))}>Add</Button>
        </div>
      </div>
    </Row>
  );
}

export function SectionForm({ def }: { def: SectionDef }) {
  const body = useRoles((s) => (s.raw as Raw | null)?.[def.name]);
  const models = useRoles((s) => s.models);
  const targets = useTargets();
  const help = useHelpGroup("lineup_fields");
  return (
    <div className="re-form" data-testid={`roles-section-${def.name}`}>
      {def.fields.map((f) => {
        const v = getPath(body, f.path);
        const hint = help[f.path ? `${def.name}.${f.path}` : def.name] || undefined;
        const set = (x: unknown) => change(def, f.path, x);
        switch (f.kind) {
          case "rows": return <Rows key={f.path} def={def} f={f} value={v} targets={targets} hint={hint} />;
          case "map": return <MapRows key={f.path} def={def} f={f} value={v} targets={targets} hint={hint} />;
          case "bool": return <Row key={f.path} hint={hint}><Check label={f.label} value={!!v} onChange={(x) => set(x || undefined)} /></Row>;
          case "number": return <NumberIn key={f.path} label={f.label} hint={hint} value={typeof v === "number" ? v : undefined} onCommit={set} />;
          case "list": return <ListIn key={f.path} label={f.label} hint={hint} placeholder={f.placeholder} value={Array.isArray(v) ? (v as string[]) : []} onCommit={set} />;
          case "select": return <Pick key={f.path} label={f.label} hint={hint} value={String(v ?? "")} options={f.options} onChange={(x) => set(x || undefined)} />;
          case "model": return <Pick key={f.path} label={f.label} hint={hint || "a model ref from the catalog"} value={String(v ?? "")} options={["", ...models.map((m) => m.ref)]} onChange={(x) => set(x || undefined)} />;
          case "checks": {
            const on = Array.isArray(v) ? (v as string[]) : [];
            return (
              <Row key={f.path} label={f.label} hint={hint}>
                <span className="re-members">{f.options.map((o) => <Check key={o} label={o} value={on.includes(o)} onChange={(x) => set(x ? [...on, o] : on.filter((y) => y !== o))} />)}</span>
              </Row>
            );
          }
          default: return <TextIn key={f.path} label={f.label} hint={hint} placeholder={f.placeholder} value={String(v ?? "")} onCommit={set} />;
        }
      })}
    </div>
  );
}
