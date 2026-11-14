// The view bar (3.6.0.0 R0a, rule R3: no row of strips): one 44 px row over the stage with a named button for every
// drawer and tab of the view, its live word beside the name ("Cost $0.42", "Attention 1"), pressed while it is open.
// A press opens it (a drawer by the stage's rules: R1 / R9 close what must close) or closes it; an optional panel not
// in the view yet is added. The main thing has a button only when the view has tabs (it is the first tab then).
// Left drawers' buttons sit at the bar's start, then the tabs; right drawers' at its end.
// `data-testid="viewbar-btn"` + `data-panel`; `data-alias="panel-strip"` names the old strip for one release.
// 3.6.0.0 R4b: the words for what shows ("Map only", "Map and Live"); a drawer put aside by Only this is not pressed,
// and its button shows both again.
import type { ReactNode } from "react";
import { useStore } from "../store";
import { Icon } from "../ui/Icon";
import { useWorkspace } from "./controller";
import { focusPanel, layoutStore, patchPanel, showBoth, showPanel } from "./persist";
import { arrangementWords, roleOf, sideOf, soloOf } from "./rules";
import type { Layout, PanelSpec } from "./types";

function Count({ spec }: { spec: PanelSpec }) {
  const word = spec.useCount!();
  return word ? <span className="viewbar-count mono" data-testid="viewbar-count">{word}</span> : null;
}

function press(section: string, spec: PanelSpec, layout: Layout, hidden: boolean): void {
  const p = layout[spec.id];
  if (!p) return showPanel(section, spec);
  if (hidden) return (showBoth(section), focusPanel(section, spec.id)); // open but put aside by Only this: both again
  if (!p.collapsed && roleOf(spec) !== "main") return patchPanel(section, spec.id, { collapsed: true });
  patchPanel(section, spec.id, { collapsed: false });
  focusPanel(section, spec.id);
}

function Btn({ spec, layout }: { spec: PanelSpec; layout: Layout }) {
  const ws = useWorkspace();
  const p = layout[spec.id];
  const role = roleOf(spec);
  const solo = useStore(layoutStore(ws.section), (s) => soloOf(ws.specs, s.layout, s.solo));
  const hidden = !!p && !p.collapsed && !!solo && solo !== spec.id && role === "drawer";
  const open = !!p && !p.collapsed && !hidden;
  const verb = !p ? "Add" : open ? (role === "drawer" ? "Close" : "Showing") : role === "drawer" ? "Open" : "Show";
  return (
    <button type="button" className="viewbar-btn" data-testid="viewbar-btn" data-alias="panel-strip" data-panel={spec.id} data-role={role}
            data-side={role === "drawer" ? sideOf(spec) : undefined} aria-pressed={open} data-added={p ? undefined : "no"}
            title={`${verb} ${spec.title}${spec.about ? `: ${spec.about}` : ""}`} onClick={() => press(ws.section, spec, layout, hidden)}>
      {!p && <Icon name="plus" />}
      <span className="viewbar-name">{spec.title}</span>
      {spec.useCount && <Count spec={spec} />}
    </button>
  );
}

/** 3.6.0.0 R4b: what the stage shows, in words ("Map only", "Live only", "Map and Live"); kept per section. */
function Words({ specs, layout }: { specs: PanelSpec[]; layout: Layout }) {
  const ws = useWorkspace();
  const words = useStore(layoutStore(ws.section), (s) => arrangementWords(specs, layout, s.solo));
  return words ? <span className="viewbar-words mono" data-testid="viewbar-arrangement" title={`Shown now: ${words} (Only this / Show both in a panel's title line, Alt+Up / Alt+Down)`}>{words}</span> : null;
}

export function ViewBar({ specs, layout, lead }: { specs: PanelSpec[]; layout: Layout; lead?: ReactNode }) {
  const group = specs.filter((s) => (roleOf(s) === "main" || roleOf(s) === "tab") && (layout[s.id] || s.optional));
  const tabs = group.length > 1 ? group : [];
  const left = specs.filter((s) => roleOf(s) === "drawer" && sideOf(s) === "left");
  const right = specs.filter((s) => roleOf(s) === "drawer" && sideOf(s) === "right");
  return (
    <div className="viewbar" role="toolbar" aria-label="Panels of this view" data-density="bar" data-testid="viewbar">
      {lead}
      {left.length > 0 && <div className="viewbar-group" data-side="left">{left.map((s) => <Btn key={s.id} spec={s} layout={layout} />)}</div>}
      {tabs.length > 0 && (
        <div className="viewbar-group viewbar-tabs">
          {tabs.map((s) => <Btn key={s.id} spec={s} layout={layout} />)}
        </div>
      )}
      <span className="viewbar-gap" />
      <Words specs={specs} layout={layout} />
      {right.length > 0 && <div className="viewbar-group" data-side="right">{right.map((s) => <Btn key={s.id} spec={s} layout={layout} />)}</div>}
    </div>
  );
}
