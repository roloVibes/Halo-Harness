// ModelSelect (3.1.4.0 R4, "the model is where you look"): the one compact
// model control wherever an agent is configured in Studio -- the Roles
// Inspector's MODEL strip and Assignment tab, the bio form, Orchestra's goal
// form, Design's New project dialog and Projects panel. A <select> of the
// catalog grouped by provider (GET models, the rows the picker table reads),
// each option its short ref with the price in / out and the context on its
// title, then the refs already in use and Halo's shipped list (GET
// models/fallback, "not verified"); a first option that keeps what the field
// inherits when it is an override ("the bio's own (<model>)", "the lineup's
// (...)", "the default (...)"). "more..." opens the full picker table (a
// dialog, or folded in place with `inline`); its pick lands in the select.
// Test runs the one-token probe (POST models/test) and shows ok and the
// latency, or the error, under it. With no live list it says why (the
// Models panel's lines: every provider looked at) and offers Refresh. Every
// label's line is field_help.py's (the `model_select` group).
import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useHelpGroup } from "../../lib/fieldHelp";
import { Button, Dialog } from "../../lib/ui";
import { refreshModels, testModel } from "../roles/bioActions";
import { ModelPicker } from "../roles/ModelPicker";
import { useRoles } from "../roles/store";
import type { ModelRow } from "../roles/types";
import { CatalogLines, modelLine, shortRef, useCatalog } from "./catalog";

export type Inherit = { label: string; model: string };

type Props = {
  value: string;
  onPick: (ref: string) => void;
  label: string;
  /** The label's one line (field_help.py). */
  hint?: string;
  /** The first option keeps what the field inherits: "the bio's own" and the model that is. */
  inherit?: Inherit;
  testid: string;
  /** "more..." folds the picker table in place instead of a dialog. */
  inline?: boolean;
  /** Move the keyboard focus to the select once it shows; `onFocused` clears the request. */
  focus?: boolean;
  onFocused?: () => void;
  busy?: boolean;
  /** A form that must keep its height: no hint line (the label's title carries it), the empty state in one line. */
  compact?: boolean;
  /** The label for screen readers only and no hint line (a strip whose own line names the field). */
  bare?: boolean;
};

function groupsOf(models: ModelRow[]): [string, ModelRow[]][] {
  const by = new Map<string, ModelRow[]>();
  for (const m of models) by.set(m.provider || "other", [...(by.get(m.provider || "other") || []), m]);
  return [...by.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([p, list]) => [p, [...list].sort((x, y) => x.ref.localeCompare(y.ref))]);
}

export function ModelSelect({ value, onPick, label, hint, inherit, testid, inline, focus, onFocused, busy, compact, bare }: Props) {
  const id = useId();
  const h = useHelpGroup("model_select");
  const { models, fallback, loaded } = useCatalog();
  const status = useRoles((s) => s.modelsStatus);
  const refreshing = useRoles((s) => s.busy === "refresh");
  const justRefreshed = useRoles((s) => s.justRefreshed);
  const effective = value || inherit?.model || "";
  const probe = useRoles((s) => (effective ? s.probe[effective] : undefined));
  const [more, setMore] = useState(false);
  const sel = useRef<HTMLSelectElement>(null);
  const close = useCallback(() => setMore(false), []);
  useEffect(() => {
    if (!focus || !sel.current) return;
    sel.current.focus({ preventScroll: true });
    sel.current.scrollIntoView({ block: "nearest" });
    onFocused?.();
  }, [focus, onFocused]);
  const live = useMemo(() => groupsOf(models), [models]);
  const used = useMemo(() => fallback.filter((m) => m.source === "in use"), [fallback]);
  const shipped = useMemo(() => fallback.filter((m) => m.source === "shipped"), [fallback]);
  const labels = useMemo(() => Object.fromEntries((status?.providers || []).map((p) => [p.name, p.label])), [status]);
  const row = models.find((m) => m.ref === effective) || fallback.find((m) => m.ref === effective);
  const known = !value || models.some((m) => m.ref === value) || fallback.some((m) => m.ref === value);
  const empty = loaded && !models.length;
  const pick = (ref: string) => {
    setMore(false);
    if (ref !== value) onPick(ref);
  };
  const opt = (m: ModelRow) => (
    <option key={m.ref} value={m.ref} title={modelLine(m)}>{shortRef(m.ref)}{m.verified === false ? " · not verified" : ""}</option>
  );
  const table = <ModelPicker value={value} onPick={pick} />;
  return (
    <div className="field re-field msel" data-testid={testid} data-value={value} data-empty={empty || undefined}>
      <label className={"field-label mono" + (bare ? " msel-bare" : "")} htmlFor={id} title={hint}>{label}</label>
      <div className="msel-row">
        <select id={id} ref={sel} className="input mono msel-select" value={value} disabled={busy} title={modelLine(row, effective) || hint}
                onChange={(e) => pick(e.target.value)} data-testid="model-select">
          <option value="">{inherit ? `${inherit.label} (${inherit.model ? shortRef(inherit.model) : "none resolves"})` : "(none)"}</option>
          {value && !known && <option value={value}>{shortRef(value)} · not in the catalog</option>}
          {live.map(([p, list]) => <optgroup key={p} label={labels[p] || p}>{list.map(opt)}</optgroup>)}
          {used.length > 0 && <optgroup label="named in your config, bios and lineups · not verified">{used.map(opt)}</optgroup>}
          {shipped.length > 0 && <optgroup label="OpenRouter · Halo's shipped list, not verified">{shipped.map(opt)}</optgroup>}
        </select>
        <button type="button" className="og-link mono msel-more" aria-expanded={more} onClick={() => setMore(!more)} title={h.more} data-testid="model-select-more">
          {more && inline ? "fold" : "more..."}
        </button>
        <Button size="sm" disabled={!effective || probe === "running"} onClick={() => void testModel(effective)} title={h.test} data-testid="model-select-test">
          {probe === "running" ? "Testing..." : "Test"}
        </Button>
      </div>
      {probe && probe !== "running" && (
        <div className="msel-result mono" data-ok={probe.ok || undefined} data-testid="model-select-result" title={probe.cost_line}>
          {shortRef(probe.ref || effective)}: {probe.ok ? `ok in ${probe.latency_ms} ms` : `failed: ${probe.error || "no reply"}`}
        </div>
      )}
      {!loaded && <div className="msel-why mono muted">reading the catalog...</div>}
      {empty && compact && (
        <div className="msel-why-line mono">
          <button type="button" className="og-link" disabled={refreshing} onClick={() => void refreshModels()} title={h.refresh} data-testid="model-select-refresh">
            {refreshing ? "refreshing..." : "Refresh"}
          </button>
          <span className="msel-why-text" data-testid="model-select-why" title={status?.reason || ""}>
            {status?.reason || "No live model list yet: Refresh asks every provider for its list."}
          </span>
        </div>
      )}
      {empty && !compact && (
        <div className="msel-empty" data-testid="model-select-empty">
          <span className="msel-why" data-testid="model-select-why">{status?.looked_at ? "No live model list yet; what each provider said:" : "No live model list yet: Refresh asks every provider for its list."}</span>
          <Button size="sm" variant="primary" disabled={refreshing} onClick={() => void refreshModels()} title={h.refresh} data-testid="model-select-refresh">
            {refreshing ? "Refreshing..." : "Refresh"}
          </Button>
        </div>
      )}
      {(empty && !compact) || justRefreshed ? <CatalogLines empty={empty && !compact} /> : null}
      {hint && !compact && !bare && <div className="field-hint">{hint}</div>}
      {more && inline && <div className="msel-fold" data-testid="model-select-fold">{table}</div>}
      {more && !inline && createPortal(
        <Dialog open onClose={close} title={label} kicker="MODELS · THE WHOLE CATALOG" testid="model-select-dialog">{table}</Dialog>,
        document.body,
      )}
    </div>
  );
}
