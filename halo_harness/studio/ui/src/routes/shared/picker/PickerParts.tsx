// The picker's parts (3.4.1.3): one row (one line: ref, price in / out, context with the fit meter, what it TAKES, the
// gym score and learned chips -- the 3.3.15.0 R2 look), a provider's head (its name and state in one line), the detail
// line under the list, the providers with nothing here, and the empty state (why, in one line, with its one fix).
import { FitMeter } from "../../../lib/ui";
import { refreshModels } from "../../roles/bioActions";
import { droppedFor, LearnedChips } from "../../roles/LearnedChips";
import type { GymScore, ModelRow, ModelsStatus } from "../../roles/types";
import { applyDoor } from "../../setup/door";
import { CardChips } from "../ModelCard";
import { honestLine, ModelTakes } from "../ModelTakes";
import type { Group } from "./rows";

const money = (v: number | null) => (typeof v === "number" ? "$" + (v < 1 ? v.toFixed(2) : v.toFixed(v < 10 ? 2 : 0)) : "?");

const priceOf = (m: ModelRow) => m.price_note || (m.price_in === null && m.price_out === null && m.price && m.price !== "?" ? m.price
  : `${money(m.price_in)} / ${money(m.price_out)}`);

export function Row({ m, tid, on, hot, dim, task, gym, kinds, onPick, onHot }: {
  m: ModelRow; tid: string; on: boolean; hot: boolean; dim: string; task: string; gym?: GymScore; kinds: number; onPick: () => void; onHot: () => void;
}) {
  const dropped = droppedFor(m, task);
  const l = dropped ? m.learned?.[task] : undefined;
  const title = l ? `${m.ref}: dropped for ${task} (${l.passed}/${l.n} checked tasks)` : dim ? `${m.ref}: ${dim}` : m.detail || m.ref;
  return (
    <button type="button" className={"rm-row" + (dropped ? " rm-dropped" : "")} role="option" aria-selected={on} onClick={onPick}
            onMouseEnter={onHot} onFocus={onHot} data-hot={hot || undefined} data-dim={dim ? true : undefined} tabIndex={-1}
            data-testid={`${tid}-row`} data-ref={m.ref} data-kinds={kinds} data-dropped={dropped || undefined} title={title}>
      <span className="mono rm-ref">{m.ref}</span>
      <span className="mono rm-price">{priceOf(m)}</span>
      <span className="mono rm-ctx">{m.context} <FitMeter fit={m.fit} label={false} /></span>
      <span className="rm-takes" data-testid="model-best-at"><ModelTakes row={m} /></span>
      <span className="mono rm-gym">{gym ? gym.score.toFixed(2) : ""}<LearnedChips m={m} kind={task} /></span>
    </button>
  );
}

export function GroupHead({ g, tid, folded, onFold }: { g: Group; tid: string; folded: boolean; onFold?: () => void }) {
  return (
    <div className="mpk-group mono" role="presentation" data-testid={`${tid}-group`} data-provider={g.provider} data-ok={g.ok || undefined}
         data-folded={folded || undefined}>
      {onFold ? (
        <button type="button" className="mpk-fold" onClick={onFold} aria-expanded={!folded} data-testid={`${tid}-fold`} data-provider={g.provider}
                title={folded ? "show this provider's models" : "fold this provider's models"}>{folded ? "▸" : "▾"}</button>
      ) : null}
      <b className="mpk-group-name">{g.label}</b>
      <span className="mpk-group-state" title={g.state}>{g.state}</span>
      {!g.ok && <button type="button" className="og-link" onClick={() => void refreshModels()}>Refresh</button>}
    </div>
  );
}

/** The detail line under the list (3.3.15.0 R2): the highlighted (else picked) row's honest line, the kinds it is
 *  best at, its effort word and its card's chips -- what the row itself no longer draws. */
export function Detail({ m, kinds }: { m?: ModelRow; kinds: string[] }) {
  if (!m) return <div className="rm-detail mono" data-testid="model-detail">point at a model: what it is best at shows here</div>;
  const line = honestLine(m);
  return (
    <div className="rm-detail mono" data-testid="model-detail" data-ref={m.ref} title={line || undefined}>
      <span className="rm-detail-ref">{m.ref}</span>
      <span className="rm-detail-line" data-testid="model-best-line">{line || "?"}</span>
      {kinds.length > 0 && <span className="rm-detail-kinds" data-testid="model-best-kinds" title="the kinds it is best at (the best sort)">best at {kinds.join(", ")}</span>}
      {m.effort_word ? <span className="og-chip mono" data-testid="model-effort" title="what the effort level does on this model">{m.effort_word}</span> : null}
      <CardChips card={m.card} />
    </div>
  );
}

/** Under the groups: the providers that list nothing here, one line, with the fix. */
export function NotHereLine({ unset, failing }: { unset: string[]; failing: { label: string; line: string }[] }) {
  if (!unset.length && !failing.length) return null;
  return (
    <div className="mpk-nothere mono muted" data-testid="model-picker-not-here">
      {failing.map((f) => <span key={f.label} title={f.line}>{f.label}: {f.line} · </span>)}
      {unset.length > 0 && <span title={unset.join(", ")}>not set up here: {unset.join(", ")} · </span>}
      <button type="button" className="og-link" onClick={() => applyDoor({ block: "providers" })}>Setup</button>
    </div>
  );
}

/** No model to pick: why in one line and the one action that fixes it -- never an empty list. */
export function EmptyLine({ st, error, busy, none = "" }: { st: ModelsStatus | null; error: string; busy: boolean; none?: string }) {
  if (none) { // the catalog has models, none of the kind this field takes
    return (
      <div className="mpk-empty" data-testid="models-empty">
        <span className="mpk-empty-why" data-testid="model-select-why">no {none} is listed here: Refresh asks every provider and host again</span>
        <button type="button" className="og-link mono" disabled={busy} onClick={() => void refreshModels()} data-testid="model-select-refresh">{busy ? "refreshing..." : "Refresh"}</button>
      </div>
    );
  }
  const failing = (st?.looked_at || []).filter((l) => !l.ok && !l.line.startsWith("not configured") && !l.line.startsWith("no model listed yet"));
  const why = error || (failing.length ? `${failing[0].label} did not answer: ${failing[0].line}` : (st?.providers || []).some((p) => p.enabled || p.credentials)
    ? "a provider is set up but nothing is listed yet: Refresh asks it for its list" : "no provider is set up here yet: Setup's Providers step adds one");
  const refresh = !!error || failing.length > 0 || (st?.providers || []).some((p) => p.enabled || p.credentials);
  return (
    <div className="mpk-empty" data-testid="models-empty" title={st?.reason || why}>
      <span className="mpk-empty-why" data-testid="model-select-why">{why}</span>
      {refresh ? (
        <button type="button" className="og-link mono" disabled={busy} onClick={() => void refreshModels()} data-testid="model-select-refresh">{busy ? "refreshing..." : "Refresh"}</button>
      ) : (
        <button type="button" className="og-link mono" onClick={() => applyDoor({ block: "providers" })} data-testid="model-select-setup">Setup</button>
      )}
    </div>
  );
}
