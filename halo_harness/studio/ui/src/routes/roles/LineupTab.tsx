// The Inspector's Lineup tab (3.0.7.0 R2): the lineup's description, how the
// pieces work together and what it extends, then one block per top section
// (delegation, routing, budget, escalation, context, permissions,
// pipeline, acceptance, tiers), each with its enforcement badge, its small
// form (SectionForm) and a YAML toggle that edits the raw section body
// (`POST yaml` both ways). A save that answers 422 lists the validator's
// lines above the sections. 3.1.1.0 R3: Studio is the one editor of lineups
// (`halo studio --edit lineup:<name>` opens this tab); each section's line
// and the header's field lines are field_help.py's; Save to project scope.
import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import { useFieldHelp, useHelpGroup } from "../../lib/fieldHelp";
import { Button } from "../../lib/ui";
import { edit } from "./actions";
import { TextIn } from "./controls";
import { ScopeCheck } from "./BioForm";
import { OptInFields } from "./OptInFields";
import { SectionForm } from "./SectionForm";
import { SECTIONS, type SectionDef } from "./sections";
import { useRoles } from "./store";
import { msg } from "./sync";

function YamlBox({ def }: { def: SectionDef }) {
  const body = useRoles((s) => s.raw?.[def.name]);
  const [text, setText] = useState("");
  const [err, setErr] = useState("");
  useEffect(() => {
    let live = true;
    api.post<{ yaml: string }>("yaml", { raw: body === undefined ? {} : { [def.name]: body } })
      .then((r) => live && setText(body === undefined ? `${def.name}:\n` : r.yaml))
      .catch(() => live && setText(`${def.name}:\n`));
    return () => {
      live = false;
    };
  }, [body, def.name]);
  const apply = async () => {
    try {
      const r = await api.post<{ raw: Record<string, unknown> }>("yaml", { yaml: text });
      const v = r.raw[def.name];
      if (def.list ? v !== undefined && v !== null && !Array.isArray(v) : v !== undefined && v !== null && (typeof v !== "object" || Array.isArray(v))) {
        setErr(def.list ? `${def.name} must be a YAML list` : `${def.name} must be a YAML mapping`);
        return;
      }
      setErr("");
      edit((raw) => {
        if (v === undefined || v === null) delete raw[def.name];
        else raw[def.name] = v;
      });
    } catch (e) {
      setErr(msg(e));
    }
  };
  return (
    <div className="re-yaml">
      <textarea className="input mono re-yaml-text" spellCheck={false} rows={Math.min(14, text.split("\n").length + 1)} value={text}
                onChange={(e) => setText(e.target.value)} data-testid={`roles-yaml-${def.name}`} aria-label={`${def.name} as YAML`} />
      <div className="re-yaml-row">
        <Button size="sm" variant="primary" onClick={() => void apply()} data-testid={`roles-yaml-apply-${def.name}`}>Apply this YAML</Button>
        {err && <span className="og-problems">{err}</span>}
      </div>
    </div>
  );
}

function Block({ def }: { def: SectionDef }) {
  const set = useRoles((s) => s.raw?.[def.name] !== undefined && s.raw?.[def.name] !== null);
  const enf = useRoles((s) => s.current?.enforcement?.[def.name]);
  const [open, setOpen] = useState(def.name === "tiers");
  const [yaml, setYaml] = useState(false);
  const about = useFieldHelp("lineup_sections", def.name);
  return (
    <section className="re-block" data-open={open || undefined} data-set={set || undefined}>
      <header className="re-block-head">
        <button className="re-block-title" onClick={() => setOpen(!open)} aria-expanded={open} data-testid={`roles-block-${def.name}`}>
          <span aria-hidden="true">{open ? "▾" : "▸"}</span> {def.title}
          {!set && <span className="muted mono re-unset"> not set</span>}
        </button>
        {enf?.[0] && <span className="og-chip mono" title={enf[1]}>{enf[0]}</span>}
        {open && (
          <button className="re-yaml-toggle mono" aria-pressed={yaml} onClick={() => setYaml(!yaml)} data-testid={`roles-yaml-toggle-${def.name}`}
                  title="Edit this section as YAML">YAML</button>
        )}
      </header>
      {open && about && <p className="muted re-about" data-testid={`roles-about-${def.name}`}>{about}</p>}
      {open && (yaml ? <YamlBox def={def} /> : <SectionForm def={def} />)}
    </section>
  );
}

export function LineupHeader() {
  const raw = useRoles((s) => s.raw);
  const h = useHelpGroup("assignment");
  if (!raw) return null;
  const put = (key: string) => (v: string) => edit((r) => (v ? (r[key] = v) : delete r[key]));
  return (
    <div className="re-form">
      <TextIn label="Description" hint={h.description} value={String(raw.description ?? "")} onCommit={put("description")} testid="roles-description" />
      <TextIn label="How the pieces work together" area hint={h.about} value={String(raw.about ?? "")} onCommit={put("about")} testid="roles-about" />
      <TextIn label="Extends" hint={h.extends} placeholder="another lineup to inherit sections from" value={String(raw.extends ?? "")} onCommit={put("extends")} />
      <ScopeCheck what="teams" />
    </div>
  );
}

export function SaveProblems() {
  const lines = useRoles((s) => s.saveProblems);
  if (!lines.length) return null;
  return (
    <div className="re-save-problems" data-testid="roles-save-problems" role="alert">
      <b>Not saved: the validator says</b>
      <ul>{lines.map((l) => <li key={l}>{l}</li>)}</ul>
    </div>
  );
}

export function LineupTab() {
  const name = useRoles((s) => s.name);
  if (!name) return <p className="muted">Open a lineup in Lineups first.</p>;
  return (
    <div className="re-lineup" data-testid="roles-lineup-tab" data-lineup={name}>
      <SaveProblems />
      <LineupHeader />
      <OptInFields />
      {SECTIONS.map((d) => <Block key={d.name} def={d} />)}
    </div>
  );
}
