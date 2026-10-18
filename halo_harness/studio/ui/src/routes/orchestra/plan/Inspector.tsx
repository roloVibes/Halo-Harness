// The plan card's inspector (3.0.9.0 R2): the selected lane's title, its
// claims as chips (add one from the goal's units), what it runs after, what
// it takes (needs: from a lane, all / summary / one of its gives) and what it
// hands on (gives), its bio (the Roles bios) and its model (the Roles model
// picker with "Test this model"), Drop lane, and the problems on this card.
// Every change is one edit: the draft is PUT and the problems come back.
import { useEffect, useState } from "react";
import { Button, Field } from "../../../lib/ui";
import { ModelPicker } from "../../roles/ModelPicker";
import { useRoles } from "../../roles/store";
import type { Give, Need } from "../types";
import { dropLane, patchJob } from "./actions";
import { NO_JOBS, problemsOf, usePlan } from "./store";
import type { PlanJob } from "./types";

const KINDS: Give["kind"][] = ["files", "summary", "artifact"];

function Chips({ list, onDrop, testid }: { list: string[]; onDrop: (v: string) => void; testid: string }) {
  return (
    <span className="og-chips">
      {list.map((v) => (
        <button key={v} type="button" className="og-chip mono" data-testid={testid} onClick={() => onDrop(v)} title={`Remove ${v}`}>
          {v} ×
        </button>
      ))}
      {!list.length && <span className="muted mono">none</span>}
    </span>
  );
}

function AddSelect({ label, options, onAdd, testid }: { label: string; options: [string, string][]; onAdd: (v: string) => void; testid: string }) {
  return (
    <select className="input mono pc-add" value="" onChange={(e) => e.target.value && onAdd(e.target.value)} aria-label={label} data-testid={testid}>
      <option value="">{label}</option>
      {options.map(([v, text]) => <option key={v} value={v}>{text}</option>)}
    </select>
  );
}

function TitleField({ job }: { job: PlanJob }) {
  const [text, setText] = useState(job.title);
  useEffect(() => setText(job.title), [job.id, job.title]);
  const commit = () => text !== job.title && patchJob(job.id, { title: text });
  return (
    <Field label="TITLE">
      {(id) => <input id={id} className="input" value={text} placeholder="what its worker does, in one line" data-testid="plan-title"
                      onChange={(e) => setText(e.target.value)} onBlur={commit} onKeyDown={(e) => e.key === "Enter" && commit()} />}
    </Field>
  );
}

function Needs({ job, jobs }: { job: PlanJob; jobs: PlanJob[] }) {
  const needs = job.handoff?.needs || [];
  const put = (next: Need[]) => patchJob(job.id, { handoff: { ...(job.handoff || {}), needs: next } });
  const others = jobs.filter((j) => j.id !== job.id);
  const takes = (from: string) => ["summary", "all", ...((jobs.find((j) => j.id === from)?.handoff?.gives || []).map((g) => g.name))];
  return (
    <div className="pc-rows">
      {needs.map((n, i) => (
        <div key={i} className="pc-row">
          <select className="input mono" value={n.from} onChange={(e) => put(needs.map((x, j) => (j === i ? { ...x, from: e.target.value } : x)))} aria-label="From lane">
            {others.map((o) => <option key={o.id} value={o.id}>{o.id}</option>)}
            {!others.some((o) => o.id === n.from) && <option value={n.from}>{n.from}</option>}
          </select>
          <select className="input mono" value={n.take} onChange={(e) => put(needs.map((x, j) => (j === i ? { ...x, take: e.target.value } : x)))} aria-label="Takes">
            {[...new Set([...takes(n.from), n.take])].map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          <button type="button" className="og-link mono" onClick={() => put(needs.filter((_x, j) => j !== i))}>remove</button>
        </div>
      ))}
      {others.length > 0 && <Button size="sm" variant="ghost" onClick={() => put([...needs, { from: others[0].id, take: "summary" }])}>+ take from a lane</Button>}
    </div>
  );
}

function Gives({ job }: { job: PlanJob }) {
  const gives = job.handoff?.gives || [];
  const put = (next: Give[]) => patchJob(job.id, { handoff: { ...(job.handoff || {}), gives: next } });
  const set = (i: number, patch: Partial<Give>) => put(gives.map((g, j) => (j === i ? { ...g, ...patch } : g)));
  return (
    <div className="pc-rows">
      {gives.map((g, i) => (
        <div key={i} className="pc-row">
          <input className="input mono" value={g.name} placeholder="name" aria-label="Name" onChange={(e) => set(i, { name: e.target.value })} />
          <select className="input mono" value={g.kind} aria-label="Kind" onChange={(e) => set(i, { kind: e.target.value as Give["kind"] })}>
            {KINDS.map((k) => <option key={k} value={k}>{k}</option>)}
          </select>
          <input className="input mono" value={(g.paths || []).join(", ")} placeholder="paths, comma separated" aria-label="Paths"
                 onChange={(e) => set(i, { paths: e.target.value.split(",").map((x) => x.trim()).filter(Boolean) })} />
          <button type="button" className="og-link mono" onClick={() => put(gives.filter((_x, j) => j !== i))}>remove</button>
        </div>
      ))}
      <Button size="sm" variant="ghost" onClick={() => put([...gives, { name: `notes-${gives.length + 1}`, kind: "artifact" }])}>+ hand something on</Button>
    </div>
  );
}

export function PlanInspector() {
  const jobs = usePlan((s) => s.jobs || NO_JOBS);
  const sel = usePlan((s) => s.sel);
  const units = usePlan((s) => s.units);
  const problems = usePlan((s) => s.problems);
  const bios = useRoles((s) => s.bios);
  const [picking, setPicking] = useState(false);
  const job = jobs.find((j) => j.id === sel);
  if (!job) return <p className="muted pc-none">Click a lane card to edit it, or Add lane.</p>;
  const owner = (u: string) => jobs.find((j) => j.id !== job.id && j.claims.includes(u))?.id;
  const mine = problemsOf(problems, job.id);
  return (
    <div className="pc-inspector" data-testid="plan-inspector" data-id={job.id}>
      <header className="pc-insp-head">
        <b className="mono">{job.id}</b>
        <span className="spacer" />
        <Button size="sm" variant="danger" onClick={() => dropLane(job.id)} data-testid="plan-drop" title="Drop this lane (Ctrl+Z brings it back)">Drop lane</Button>
      </header>
      <TitleField job={job} />
      <Field label="CLAIMS">
        {() => (
          <div className="pc-rows">
            <Chips list={job.claims} testid="plan-claim" onDrop={(c) => patchJob(job.id, { claims: job.claims.filter((x) => x !== c) })} />
            <AddSelect label="+ claim a unit" testid="plan-claim-add" onAdd={(u) => patchJob(job.id, { claims: [...job.claims, u] })}
                       options={units.filter((u) => !job.claims.includes(u)).map((u) => [u, owner(u) ? `${u} · ${owner(u)}` : u])} />
          </div>
        )}
      </Field>
      <Field label="RUNS AFTER">
        {() => (
          <div className="pc-rows">
            <Chips list={job.after || []} testid="plan-after" onDrop={(a) => patchJob(job.id, { after: (job.after || []).filter((x) => x !== a) })} />
            <AddSelect label="+ run after a lane" testid="plan-after-add" onAdd={(a) => patchJob(job.id, { after: [...(job.after || []), a] })}
                       options={jobs.filter((j) => j.id !== job.id && !(job.after || []).includes(j.id)).map((j) => [j.id, `${j.id} · ${j.title}`])} />
          </div>
        )}
      </Field>
      <Field label="TAKES (NEEDS)">{() => <Needs job={job} jobs={jobs} />}</Field>
      <Field label="HANDS ON (GIVES)">{() => <Gives job={job} />}</Field>
      <Field label="BIO">
        {(id) => (
          <select id={id} className="input mono" value={job.bio || ""} onChange={(e) => patchJob(job.id, { bio: e.target.value })} data-testid="plan-bio">
            <option value="">the goal's worker role</option>
            {bios.map((b) => <option key={b.name} value={b.name}>{b.name}{b.model ? ` · ${b.model}` : ""}</option>)}
            {job.bio && !bios.some((b) => b.name === job.bio) && <option value={job.bio}>{job.bio} (not found)</option>}
          </select>
        )}
      </Field>
      <Field label="MODEL">
        {() => (
          <div className="pc-rows">
            <span className="pc-row mono">
              {job.model || <span className="muted">the bio's or the role's</span>}
              <button type="button" className="og-link mono" onClick={() => setPicking(!picking)} data-testid="plan-model-pick">{picking ? "close the picker" : "pick"}</button>
              {job.model && <button type="button" className="og-link mono" onClick={() => patchJob(job.id, { model: "" })}>clear</button>}
            </span>
            {picking && <ModelPicker value={job.model || ""} onPick={(ref) => patchJob(job.id, { model: ref })} />}
          </div>
        )}
      </Field>
      {mine.length > 0 && (
        <ul className="og-problems" role="alert">
          {mine.map((p) => <li key={p.text}>{p.text}</li>)}
        </ul>
      )}
    </div>
  );
}
