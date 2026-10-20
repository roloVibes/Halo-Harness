// The tier box's own menu (3.1.6.0 R1), in the Fleet map node menu's
// vocabulary (a `...` on the head, a glass menu of items, a "..." on each one
// that opens a form): Rename, Model... (the ModelSelect bound to
// `tiers[i].model`, its first option the session's model), Trigger... (the
// kind, its one field, the prompt; "none" clears it), Max parallel... and
// Delete (its cards fall to the implicit last tier; tier 0 stays). Escape or
// a click outside closes it; every item's title is field_help.py's line.
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { useHelpGroup } from "../../lib/fieldHelp";
import { Button, Icon } from "../../lib/ui";
import { ModelSelect } from "../shared/ModelSelect";
import { roles, useRoles, type TierMenuAt } from "./store";
import { deleteTier, setTierMax, setTierModel, setTierTrigger } from "./tierActions";
import { makeTrigger, TRIGGER_KINDS, triggerField } from "./tierText";
import type { Tier } from "./types";

const close = () => roles.update(() => ({ tierMenu: null }));
const face = (f: TierMenuAt["face"]) => roles.update((s) => (s.tierMenu ? { tierMenu: { ...s.tierMenu, face: f } } : {}));

const FIELD: Record<string, [string, string]> = {
  schedule: ["every or cron", "30m, 1h30m, or a cron line like 0 9 * * 1"],
  file_change: ["paths", "comma separated, e.g. src/, assets/clips"],
  event: ["event", "a halo event kind, e.g. turn_done"],
  message: ["from", "the role or alias whose message starts it"],
};

function Form({ title, testid, onSubmit, ok, children }: { title: string; testid: string; onSubmit: () => void; ok: boolean; children: ReactNode }) {
  const busy = useRoles((s) => s.busy === "save");
  const submit = (e: FormEvent) => (e.preventDefault(), ok && !busy && onSubmit());
  return (
    <form className="rc-tier-form" data-testid={testid} onSubmit={submit}>
      <div className="rc-tier-form-head">
        <button type="button" className="og-link mono" onClick={() => face("menu")}>‹ menu</button>
        <b>{title}</b>
      </div>
      {children}
      <div className="rc-tier-form-foot">
        <Button size="sm" variant="ghost" onClick={close}>Cancel</Button>
        <Button size="sm" variant="primary" type="submit" disabled={!ok || busy} data-testid={`${testid}-save`}>Save</Button>
      </div>
    </form>
  );
}

function TriggerForm({ t }: { t: Tier }) {
  const h = useHelpGroup("lineup_fields");
  const [kind, setKind] = useState<string>(t.trigger?.on || "none");
  const [field, setField] = useState(triggerField(t.trigger));
  const [prompt, setPrompt] = useState(t.trigger?.prompt || "");
  const ok = kind === "none" || (!!field.trim() && !!prompt.trim());
  const save = () => void setTierTrigger(t.name, kind === "none" ? null : makeTrigger(kind, field, prompt, t.trigger?.model || "")).then((done) => done && close());
  return (
    <Form title={`Tier ${t.name}: trigger`} testid="roles-tier-trigger-form" onSubmit={save} ok={ok}>
      <p className="rc-tier-form-line muted">{h["tiers.trigger"]}</p>
      <label className="field-label mono" htmlFor="rc-tier-kind">starts on</label>
      <select id="rc-tier-kind" className="input mono" value={kind} onChange={(e) => setKind(e.target.value)} data-testid="roles-tier-trigger-kind">
        <option value="none">none</option>
        {TRIGGER_KINDS.map((k) => <option key={k} value={k}>{k}</option>)}
      </select>
      {kind !== "none" && (
        <>
          <label className="field-label mono" htmlFor="rc-tier-field" title={FIELD[kind][1]}>{FIELD[kind][0]}</label>
          <input id="rc-tier-field" className="input mono" value={field} placeholder={FIELD[kind][1]} onChange={(e) => setField(e.target.value)} data-testid="roles-tier-trigger-field" />
          <label className="field-label mono" htmlFor="rc-tier-prompt">prompt (what the lead starts on)</label>
          <input id="rc-tier-prompt" className="input" value={prompt} onChange={(e) => setPrompt(e.target.value)} data-testid="roles-tier-trigger-prompt" />
        </>
      )}
    </Form>
  );
}

function MaxForm({ t }: { t: Tier }) {
  const h = useHelpGroup("lineup_fields");
  const [v, setV] = useState(t.max_parallel ? String(t.max_parallel) : "");
  const n = v.trim() ? Number(v) : null;
  const ok = n === null || (Number.isInteger(n) && n >= 1);
  return (
    <Form title={`Tier ${t.name}: max parallel`} testid="roles-tier-max-form" onSubmit={() => void setTierMax(t.name, n).then((done) => done && close())} ok={ok}>
      <p className="rc-tier-form-line muted">{h["tiers.max_parallel"]}</p>
      <input className="input mono" type="number" min={1} step={1} value={v} placeholder="no cap" onChange={(e) => setV(e.target.value)} data-testid="roles-tier-max-input" autoFocus />
    </Form>
  );
}

function ModelForm({ t }: { t: Tier }) {
  const h = useHelpGroup("lineup_fields");
  const session = useRoles((s) => s.info?.default_model || "");
  const busy = useRoles((s) => s.busy === "save");
  return (
    <div className="rc-tier-form" data-testid="roles-tier-model-form">
      <div className="rc-tier-form-head">
        <button type="button" className="og-link mono" onClick={() => face("menu")}>‹ menu</button>
        <b>Tier {t.name}: model</b>
      </div>
      <ModelSelect label={`tier ${t.name}'s model`} hint={h["tiers.model"]} value={t.model || ""} inherit={{ label: "the session's", model: session }}
                   onPick={(ref) => void setTierModel(t.name, ref).then((done) => done && close())} testid="roles-tier-model-select" busy={busy} compact />
    </div>
  );
}

export function TierMenu() {
  const at = useRoles((s) => s.tierMenu);
  const t = useRoles((s) => s.graph?.tiers.find((x) => x.name === s.tierMenu?.tier && !x.implicit));
  const h = useHelpGroup("lineup_fields");
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!at) return;
    const off = (e: PointerEvent) => {
      const el = e.target as HTMLElement | null;
      if (!box.current?.contains(el) && !el?.closest?.("[role=dialog]")) close();
    };
    const esc = (e: KeyboardEvent) => e.key === "Escape" && !document.querySelector("[role=dialog]") && (e.preventDefault(), close());
    window.addEventListener("pointerdown", off, true);
    window.addEventListener("keydown", esc, true);
    if (at.face === "menu") box.current?.querySelector<HTMLElement>("[role=menuitem]")?.focus({ preventScroll: true });
    return () => {
      window.removeEventListener("pointerdown", off, true);
      window.removeEventListener("keydown", esc, true);
    };
  }, [at]);
  if (!at || !t) return null;
  const items: [string, string, string, () => void, boolean][] = [
    ["rename", "Rename", "edit", () => (close(), roles.update(() => ({ tierRename: t.name }))), false],
    ["model", "Model...", "agent", () => face("model"), false],
    ["trigger", "Trigger...", "pulse", () => face("trigger"), false],
    ["max", "Max parallel...", "grid", () => face("max"), false],
    ["delete", t.index === 0 ? "Delete (tier 0 stays)" : "Delete", "close", () => (close(), void deleteTier(t.name)), t.index === 0],
  ];
  const W = at.face === "menu" ? 228 : 320;
  return createPortal(
    <div ref={box} className="menu glass panel-menu rc-tier-menu" role={at.face === "menu" ? "menu" : "group"} aria-label={`tier ${t.name}`} data-face={at.face}
         style={{ left: Math.max(8, Math.min(at.x, window.innerWidth - W - 8)), top: Math.max(8, Math.min(at.y + 6, window.innerHeight - (at.face === "menu" ? 220 : 330))), width: W }}
         data-testid="roles-tier-menu" data-tier={t.name}>
      {at.face === "menu" && items.map(([id, label, icon, run, off]) => (
        <button key={id} role="menuitem" className="menu-item" data-item={id} disabled={off} onClick={run} title={h[`tiers.${id === "max" ? "max_parallel" : id}`] || label}>
          <Icon name={icon} />
          <span className="menu-label">{label}</span>
        </button>
      ))}
      {at.face === "model" && <ModelForm t={t} />}
      {at.face === "trigger" && <TriggerForm key={t.name} t={t} />}
      {at.face === "max" && <MaxForm key={t.name} t={t} />}
    </div>,
    document.body,
  );
}
