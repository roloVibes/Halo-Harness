// The Artboards panel's settings face (3.0.7.0 R3b, shown in the Inspector:
// the title bar's ... menu, Settings, or a card's Knobs button): the preview
// device (also in the panel's toolbar, remembered as the panel's setting),
// then the knobs of one artboard (its controls.json) as sliders, colour
// pickers and selects. A change is posted 150 ms after the last move: a
// css: knob is applied at once and saved as a new version (the chip shows
// it), any other is kept for the next turn.
import { useEffect, useRef, useState } from "react";
import { DEVICE_IDS, DEVICES, isDevice } from "./layout";
import { setKnob } from "./more";
import { artboard, design, setDevice, useDesign } from "./store";
import type { Knob } from "./types";

export function DeviceSelect({ compact = false }: { compact?: boolean }) {
  const dev = useDesign((s) => s.device);
  return (
    <select className={compact ? "input da-device" : "input"} value={dev} onChange={(e) => isDevice(e.target.value) && setDevice(e.target.value)}
            aria-label="Preview prototypes at" title="The size a prototype is drawn at" data-testid="design-device">
      {DEVICE_IDS.map((d) => <option key={d} value={d}>{DEVICES[d].label}</option>)}
    </select>
  );
}

const hex = (v: unknown) => (/^#[0-9a-fA-F]{6}$/.test(String(v)) ? String(v) : "#000000");

function KnobRow({ aid, k }: { aid: string; k: Knob }) {
  const [value, setValue] = useState<unknown>(k.value);
  const moved = useRef(0);
  useEffect(() => {
    // the saved value comes back after each post: it does not pull the control back while it is still moving
    if (Date.now() - moved.current > 1000) setValue(k.value);
  }, [k.value]);
  const change = (v: unknown) => ((moved.current = Date.now()), setValue(v), setKnob(aid, k.name, v));
  const target = String(k.target || "");
  let control;
  if (k.kind === "color")
    control = <input type="color" value={hex(value)} onChange={(e) => change(e.target.value)} aria-label={k.name} />;
  else if (k.kind === "select")
    control = (
      <select className="input" value={String(value ?? "")} onChange={(e) => change(e.target.value)} aria-label={k.name}>
        {(k.options || []).map((o) => <option key={String(o)} value={String(o)}>{String(o)}</option>)}
      </select>
    );
  else
    control = (
      <input type="range" min={k.min ?? 0} max={k.max ?? 100} step={k.step || 1} value={Number(value ?? 0)} onChange={(e) => change(Number(e.target.value))} aria-label={k.name} />
    );
  return (
    <div className="dk-row" data-testid="design-knob" data-name={k.name}>
      <div className="dk-head">
        <label>{k.name}</label>
        <span className="mono dk-value">{String(value ?? "")}{k.kind !== "color" && k.kind !== "select" && k.unit ? k.unit : ""}</span>
      </div>
      {control}
      <div className="mono muted dk-target">{target || "no target"}{target.startsWith("css:") ? " · applies at once" : " · applies on the next turn"}</div>
    </div>
  );
}

export function ArtboardsSettings() {
  const boards = useDesign((s) => s.data?.artboards || null);
  const sel = useDesign((s) => s.sel);
  const a = useDesign((s) => artboard(s, s.sel) || s.data?.artboards[0]);
  const note = useDesign((s) => (a ? s.knobNote[a.id] || "" : ""));
  return (
    <div className="og-settings dk">
      <label className="fd-field">
        <span className="rail-label mono">PREVIEW PROTOTYPES AT</span>
        <DeviceSelect />
      </label>
      {!boards || !a ? (
        <p className="muted">Knobs belong to an artboard: open a project and run a turn first.</p>
      ) : (
        <>
          <label className="fd-field">
            <span className="rail-label mono">KNOBS OF</span>
            <select className="input" value={a.id || sel} onChange={(e) => design.update(() => ({ sel: e.target.value }))} aria-label="Artboard">
              {boards.map((b) => <option key={b.id} value={b.id}>{b.title || b.id} ({b.controls.length})</option>)}
            </select>
          </label>
          <div className="dk-ver mono muted">
            {a.title || a.id} · now v{a.latest || "-"}
            {note && <span className="og-chip mono" data-testid="design-knob-version">{note === "next turn" ? "saved for the next turn" : `made ${note}`}</span>}
          </div>
          {a.controls.length ? (
            a.controls.map((k) => <KnobRow key={a.id + "/" + k.name} aid={a.id} k={k} />)
          ) : (
            <p className="muted">{a.title || a.id} has no knobs yet. Ask for them in a turn: "add knobs for spacing and the accent colour".</p>
          )}
        </>
      )}
    </div>
  );
}
