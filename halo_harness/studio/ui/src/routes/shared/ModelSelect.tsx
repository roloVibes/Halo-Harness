// ModelSelect (3.1.4.0 R4, "the model is where you look"): the one compact model FIELD wherever Studio takes a model --
// the Roles Inspector's MODEL strip and Assignment tab, the bio form (preferred, fallback, a schedule's model), a tier's
// model, a lineup's escalation, Orchestra's goal and workflow forms, the Models panel's Test, Settings' model rows,
// Session's new session, a pack's model setting, the design pack's New project and Projects. 3.4.1.3 ("Pick, don't
// type"): the field is a button showing the model (or what it inherits, or "not in your catalog"); a click, or a key
// in it (Enter, Space, Down, or a letter, which starts the search), opens THE picker (shared/picker/ModelPicker.tsx) --
// folded in place with `inline`, else a dialog -- and a pick closes it. Test runs the one-token probe beside it; what
// the model takes shows under it; with no live list the field says why in one line with Refresh. Every label's line is
// field_help.py's (the `model_select` group).
import { useCallback, useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { createPortal } from "react-dom";
import { useHelpGroup } from "../../lib/fieldHelp";
import { Button, Dialog } from "../../lib/ui";
import { testModel } from "../roles/bioActions";
import { useRoles } from "../roles/store";
import type { ModelRow } from "../roles/types";
import { CatalogLines, modelLine, shortRef, useCatalog } from "./catalog";
import { ModelTakes } from "./ModelTakes"; // 3.3.15.0 R2: what the picked model takes, under the field
import { ModelPicker } from "./picker/ModelPicker";
import { EmptyLine } from "./picker/PickerParts";
import { useStatusOnce } from "./picker/state";

export type Inherit = { label: string; model: string };

type Props = {
  value: string;
  onPick: (ref: string) => void;
  label: string;
  /** The label's one line (field_help.py). */
  hint?: string;
  /** The picker's first row keeps what the field inherits: "the bio's own" and the model that is. */
  inherit?: Inherit;
  testid: string;
  /** The picker folds in place under the field instead of a dialog. */
  inline?: boolean;
  /** Move the keyboard focus to the field once it shows; `onFocused` clears the request. */
  focus?: boolean;
  onFocused?: () => void;
  busy?: boolean;
  /** A form that must keep its height: no hint line (the label's title carries it). */
  compact?: boolean;
  /** The label for screen readers only and no hint line (a strip whose own line names the field). */
  bare?: boolean;
  /** 3.3.5.0 R0b: the main agent's model -- the picker's card panel offers the coder lane when it cannot orchestrate. */
  forMain?: boolean;
  /** What the model must take (vision, tools ...): the picker lists the fitting ones first. */
  needs?: string[];
  only?: (m: ModelRow) => boolean;
  onlyWhat?: string;
  /** No Test button (a field whose model is not a chat model, such as the embeddings model). */
  noTest?: boolean;
  /** The picker's test-id prefix (model-* by default). */
  tid?: string;
};

export function ModelSelect({ value, onPick, label, hint, inherit, testid, inline, focus, onFocused, busy, compact, bare, forMain, needs, only, onlyWhat, noTest, tid }: Props) {
  const id = useId();
  const h = useHelpGroup("model_select");
  const { models, loaded } = useCatalog();
  const st = useStatusOnce();
  const error = useRoles((s) => s.modelsError);
  const refreshing = useRoles((s) => s.busy === "refresh");
  const justRefreshed = useRoles((s) => s.justRefreshed);
  const effective = value || inherit?.model || "";
  const probe = useRoles((s) => (effective ? s.probe[effective] : undefined));
  const [open, setOpen] = useState(false);
  const [seed, setSeed] = useState("");
  const btn = useRef<HTMLButtonElement>(null);
  const close = useCallback(() => {
    setOpen(false);
    window.setTimeout(() => btn.current?.focus({ preventScroll: true }), 0);
  }, []);
  useEffect(() => {
    if (!focus || !btn.current) return;
    btn.current.focus({ preventScroll: true });
    btn.current.scrollIntoView({ block: "nearest" });
    onFocused?.();
  }, [focus, onFocused]);
  const row = models.find((m) => m.ref === effective);
  const known = !value || models.some((m) => m.ref === value);
  const empty = loaded && !models.length;
  const pick = (ref: string) => {
    close();
    if (ref !== value) onPick(ref);
  };
  const show = (s = "") => (setSeed(s), setOpen(true));
  const onKey = (e: KeyboardEvent<HTMLButtonElement>) => {
    if (open) return;
    if (e.key === "Enter" || e.key === " " || e.key === "ArrowDown") (e.preventDefault(), show());
    else if (e.key.length === 1 && /\S/.test(e.key) && !e.ctrlKey && !e.metaKey && !e.altKey) (e.preventDefault(), show(e.key));
  };
  const shownText = value ? shortRef(value) : inherit ? `${inherit.label} (${inherit.model ? shortRef(inherit.model) : "none resolves"})` : "(none)";
  const table = <ModelPicker value={value} onPick={pick} forMain={forMain} inherit={inherit} needs={needs} only={only} onlyWhat={onlyWhat} autoFocus seed={seed} onClose={close} tid={tid} bare />;
  return (
    <div className="field re-field msel" data-testid={testid} data-value={value} data-empty={empty || undefined}>
      <label className={"field-label mono" + (bare ? " msel-bare" : "")} htmlFor={id} title={hint}>{label}</label>
      <div className="msel-row">
        <button type="button" id={id} ref={btn} className="input mono msel-trigger" disabled={busy} title={modelLine(row, effective) || hint}
                aria-haspopup="listbox" aria-expanded={open} onClick={() => (open ? close() : show())} onKeyDown={onKey} data-testid="model-select" data-value={value}>
          <span className="msel-trigger-text" data-inherit={!value || undefined}>{shownText}</span>
          {value && !known && <span className="msel-off" data-testid="model-select-off">not in your catalog</span>}
          <span className="msel-caret" aria-hidden="true">▾</span>
        </button>
        {!noTest && (
          <Button size="sm" disabled={!effective || probe === "running"} onClick={() => void testModel(effective)} title={h.test} data-testid="model-select-test">
            {probe === "running" ? "Testing..." : "Test"}
          </Button>
        )}
      </div>
      {row && <div className="msel-takes"><ModelTakes row={row} /></div>}
      {probe && probe !== "running" && !noTest && (
        <div className="msel-result mono" data-ok={probe.ok || undefined} data-testid="model-select-result" title={probe.cost_line}>
          {shortRef(probe.ref || effective)}: {probe.ok ? `ok in ${probe.latency_ms} ms` : `failed: ${probe.error || "no reply"}`}
        </div>
      )}
      {!loaded && <div className="msel-why mono muted">reading the catalog...</div>}
      {empty && !open && <EmptyLine st={st} error={error} busy={refreshing} />}
      {justRefreshed && !open ? <CatalogLines empty={false} /> : null}
      {hint && !compact && !bare && <div className="field-hint">{hint}</div>}
      {open && inline && <div className="msel-fold" data-testid="model-select-fold">{table}</div>}
      {open && !inline && createPortal(
        <Dialog open onClose={close} title={label} kicker="PICK A MODEL · THE MODELS YOU HAVE" testid="model-select-dialog">{table}</Dialog>,
        document.body,
      )}
    </div>
  );
}
