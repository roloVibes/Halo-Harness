// 3.3.16.0 R1b: a selected card opens on its own summary -- the role, the bio behind it, the model it resolves to with
// what that model takes (3.3.15.0 R2 tags), its price and context, its instances, the words that route to it -- then
// one Edit row each for its slot (role, alias, instances, routing words) and its model override, and Edit bio (the
// Bios panel on it, as before); its problems; Duplicate and Remove. The slot and the model open one page each
// (Assignment.tsx); the MODEL strip above the tabs stays as it is.
import { Button } from "../../lib/ui";
import { shortRef } from "../shared/catalog";
import { ModelTakes } from "../shared/ModelTakes";
import { edit } from "./actions";
import { openCardPage } from "./pages";
import { agentsOf, keyOf, modelRow, openDialog, priceText, readOnlySource, scopeLabel, useRoles } from "./store";
import type { Entry, GraphNode, Raw } from "./types";

type Props = { n: GraphNode; entry: Entry; onBio: () => void };

function Row({ id, title, state, muted, onEdit }: { id: string; title: string; state: string; muted?: boolean; onEdit: () => void }) {
  return (
    <li className="ri-row" data-density="row" data-block={id}>
      <button className="ri-row-main" onClick={onEdit} data-testid={`roles-block-${id}`}>
        <span className="ri-row-title">{title}</span>
        <span className="ri-row-state mono" data-muted={muted || undefined}>{state}</span>
      </button>
      <Button size="sm" variant="ghost" onClick={onEdit} data-testid={`roles-edit-${id}`} aria-label={`Edit ${title}`}>Edit</Button>
    </li>
  );
}

export function CardSummary({ n, entry, onBio }: Props) {
  const row = useRoles((s) => modelRow(s, n.model) || s.fallback.find((m) => m.ref === n.model));
  const bio = useRoles((s) => s.bios.find((b) => b.name === n.agent));
  const tier = useRoles((s) => s.graph?.tiers.find((t) => t.node_ids.includes(n.id)));
  const over = String(((entry.models && typeof entry.models === "object" ? entry.models : {}) as Raw).preference || "");
  const words = n.use_for.length ? n.use_for.join(", ") : "none: the main agent names it";
  const slot = [`role ${n.role}`, n.alias && `as ${n.alias}`, n.instances > 1 && `x${n.instances}`, n.use_for.length > 0 && `use for ${n.use_for.join(", ")}`]
    .filter(Boolean).join(" · ");
  const problems = [...n.problems, ...n.warnings];
  return (
    <div className="ri-sum" data-testid="roles-card-summary">
      <header className="re-assign-head">
        <b>{n.agent}</b>
        <span className="mono muted">{keyOf(n)}{tier ? ` · tier ${tier.index} (${tier.name})` : ""}</span>
        {n.scope && (
          <span className="rc-scope mono" data-scope={n.scope} data-testid="roles-assign-scope"
                title={n.scope === "template" ? "This bio ships with Halo: Duplicate it in the Bios panel for an editable copy"
                  : readOnlySource(n.scope) ? `This bio comes from ${scopeLabel(n.scope)}: Duplicate it in the Bios panel for an editable copy` : `This bio lives in your ${n.scope} scope`}>
            {scopeLabel(n.scope)}
          </span>
        )}
      </header>
      <dl className="ri-summary" data-testid="roles-summary">
        <div data-line="role"><dt className="mono">role</dt><dd>{n.role}{n.alias ? `, called ${n.alias}` : ""}</dd></div>
        <div data-line="bio"><dt className="mono">bio</dt><dd>{n.agent}{bio?.description ? `: ${bio.description}` : ""}</dd></div>
        <div data-line="model">
          <dt className="mono">model</dt>
          <dd className="ri-model">{n.model ? shortRef(n.model) : "none resolves"} <ModelTakes row={row || (n.model ? { ref: n.model } : null)} /></dd>
        </div>
        <div data-line="price"><dt className="mono">price</dt><dd className="mono">{priceText(row)} per 1M · ctx {row?.context || n.context || "?"}</dd></div>
        <div data-line="instances"><dt className="mono">instances</dt><dd>{n.instances > 1 ? `up to ${n.instances} at once` : "one at a time"}</dd></div>
        <div data-line="routes"><dt className="mono">routes here</dt><dd data-muted={!n.use_for.length || undefined}>{words}</dd></div>
      </dl>
      <ul className="ri-rows" aria-label="Edit this card">
        <Row id="slot" title="Slot" state={slot} onEdit={() => openCardPage("slot")} />
        <Row id="model" title="Model override" state={over ? `own: ${shortRef(over)}` : `not set = the ${n.inherit_source?.startsWith("tier:") ? "tier's" : "bio's"} own`}
             muted={!over} onEdit={() => openCardPage("model")} />
        <li className="ri-row" data-density="row" data-block="bio">
          <button className="ri-row-main" onClick={onBio} disabled={!n.agent} data-testid="roles-block-bio">
            <span className="ri-row-title">Bio</span>
            <span className="ri-row-state mono">{n.agent || "none"}{bio?.model ? ` · ${shortRef(bio.model)}` : ""}</span>
          </button>
          <Button size="sm" variant="ghost" onClick={onBio} disabled={!n.agent} data-testid="roles-edit-bio" title="The Bios panel opens on this bio">Edit bio</Button>
        </li>
      </ul>
      {problems.length > 0 && <ul className="re-card-problems">{problems.map((p) => <li key={p}>{p}</li>)}</ul>}
      <div className="re-actions" data-density="bar">
        <Button size="sm" variant="ghost" onClick={() => edit((r) => void agentsOf(r).splice(n.index + 1, 0, JSON.parse(JSON.stringify(entry))))}>Duplicate</Button>
        <Button size="sm" variant="danger" onClick={() => openDialog({ kind: "delete-card", node: n.id })} data-testid="roles-remove-card">Remove</Button>
      </div>
    </div>
  );
}
