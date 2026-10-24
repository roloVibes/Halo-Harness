// A pack's settings form (3.2.0.0 R3, kind `form`, and the Settings panel
// `config_form: true` adds): one field per key of pack.yaml's config.schema,
// labelled like every Studio form (lib/ui Field: the key, its control, the
// schema's description or the default as the help line). Save posts the
// values to `pack/<id>/config`, which checks them against the schema and
// writes packs.settings.<id> in ~/.halo/config.json; a problem shows under
// its field and nothing is written.
import { useEffect, useState } from "react";
import { api, ApiError } from "../../lib/api";
import { toast } from "../../lib/store";
import { Button, Empty, Field } from "../../lib/ui";
import { usePacks } from "./store";
import type { PackPanel } from "./types";

type FieldDef = { key: string; type: string; enum: unknown[] | null; help: string; default: unknown; value: unknown };
type Config = { pack: string; name: string; key: string; fields: FieldDef[]; values: Record<string, unknown>; problems: string[] };

const text = (v: unknown) => (v === null || v === undefined ? "" : String(v));

function coerce(f: FieldDef, raw: string | boolean): unknown {
  if (f.type === "boolean") return !!raw;
  if (f.enum) return f.enum.find((e) => String(e) === raw) ?? raw;
  if (f.type === "integer" || f.type === "number") {
    const n = f.type === "integer" ? parseInt(String(raw), 10) : parseFloat(String(raw));
    return Number.isNaN(n) ? raw : n;
  }
  return raw;
}

function Control({ f, id, value, onChange }: { f: FieldDef; id: string; value: unknown; onChange: (v: unknown) => void }) {
  if (f.type === "boolean")
    return <input id={id} type="checkbox" checked={!!value} onChange={(e) => onChange(e.target.checked)} data-testid="pack-form-input" data-key={f.key} />;
  if (f.enum)
    return (
      <select id={id} className="input" value={text(value)} onChange={(e) => onChange(coerce(f, e.target.value))} data-testid="pack-form-input" data-key={f.key}>
        {f.enum.map((e) => (
          <option key={String(e)} value={String(e)}>
            {String(e)}
          </option>
        ))}
      </select>
    );
  const num = f.type === "integer" || f.type === "number";
  return (
    <input id={id} className={"input" + (num ? " mono" : "")} type={num ? "number" : "text"} value={text(value)}
           onChange={(e) => onChange(coerce(f, e.target.value))} data-testid="pack-form-input" data-key={f.key} />
  );
}

export function PackForm({ p }: { p: PackPanel }) {
  const reg = usePacks((s) => s.reg);
  const [cfg, setCfg] = useState<Config | null>(null);
  const [draft, setDraft] = useState<Record<string, unknown>>({});
  const [error, setError] = useState("");
  const [problems, setProblems] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let live = true;
    api.get<Config>(`pack/${p.pack}/config`).then(
      (c) => live && (setCfg(c), setDraft({ ...c.values }), setError("")),
      (e) => live && setError(e instanceof Error ? e.message : String(e)),
    );
    return () => {
      live = false;
    };
  }, [p.pack, reg]);
  if (error && !cfg) return <Empty title="Studio could not read the settings" body={error} testid="pack-error" />;
  if (!cfg) return <div className="og-wait mono muted">reading the settings...</div>;
  if (!cfg.fields.length) return <Empty title="Nothing to set" body="pack.yaml's config.schema names no keys." />;
  const changed = cfg.fields.filter((f) => JSON.stringify(draft[f.key]) !== JSON.stringify(cfg.values[f.key]));
  const save = async () => {
    setBusy(true);
    try {
      const c = await api.post<Config>(`pack/${p.pack}/config`, { values: Object.fromEntries(changed.map((f) => [f.key, draft[f.key]])) });
      setCfg(c);
      setDraft({ ...c.values });
      setProblems([]);
      toast(`Saved: ${c.key}`, "done");
    } catch (e) {
      setProblems(e instanceof ApiError && e.problems.length ? e.problems : [e instanceof Error ? e.message : String(e)]);
    } finally {
      setBusy(false);
    }
  };
  const problemOf = (key: string) => problems.find((x) => x.includes(`.${key}:`) || x.includes(` ${key} `)) || "";
  return (
    <form className="pk-form" data-testid="pack-form" onSubmit={(e) => (e.preventDefault(), void save())}>
      <p className="muted pk-form-key mono">{cfg.key}</p>
      {cfg.fields.map((f) => (
        <Field key={f.key} label={f.key} error={problemOf(f.key)} hint={f.help || (f.default !== undefined && f.default !== null ? `default ${text(f.default)}` : undefined)}>
          {(id) => <Control f={f} id={id} value={draft[f.key]} onChange={(v) => setDraft((d) => ({ ...d, [f.key]: v }))} />}
        </Field>
      ))}
      {problems.length > 0 && !cfg.fields.some((f) => problemOf(f.key)) && <div className="field-error">{problems[0]}</div>}
      <div className="pk-form-foot">
        <Button type="submit" variant="primary" size="sm" disabled={busy || !changed.length} data-testid="pack-form-save">
          Save
        </Button>
        <Button size="sm" variant="ghost" disabled={busy || !changed.length} onClick={() => (setDraft({ ...cfg.values }), setProblems([]))}>
          Revert
        </Button>
        <span className="muted">{changed.length ? `${changed.length} changed` : "saved"}</span>
      </div>
    </form>
  );
}
