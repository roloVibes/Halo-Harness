// The stage (3.6.0.0 R0a "room for everything in Studio"): a view's main thing with most of the room, a drawer slot
// on each side (full height, beside the main thing, pushing it: R2), the main thing's tabs shown in its place.
// Under 1100 px the drawer floats over the main thing with its close (R9); a view with no main thing (Local's Media
// over its page) floats its drawer too. `full` (`?open=all`, the drivers' door): every drawer and tab open, each side's
// stacked in one drawer that shares its height among them (tabs on the right). A drawer's inner edge is a splitter
// (controller.ts). Emits nothing of its own: the view bar and the doors open and close panels through persist.ts
// (open = patchPanel collapsed false, close = true, resize = setDrawerWidth).
// 3.6.0.0 R4b: a drawing's drawer drags until the main thing is MAIN_MIN wide (`data-max` says how far), a floating
// drawer drags too; Only this (`solo`): a drawer alone takes the whole stage while the main thing stays mounted, hidden
// (it keeps following); the main thing alone puts its drawers aside (they come back with Show both).
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useStore } from "../store";
import { floats, type Breakpoint } from "./breakpoint";
import { useSplitter, useWorkspace } from "./controller";
import { layoutStore } from "./persist";
import { Panel } from "./Panel";
import { contentWOf, drawerMax, drawerW, mainOf, openDrawers, roleOf, shownMain, sideOf, soloOf } from "./rules";
import { DRAWER_MIN, type Layout, type PanelSpec } from "./types";

function useWidth(): [React.RefObject<HTMLDivElement | null>, number] {
  const ref = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const measure = () => setW(el.clientWidth);
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, w];
}

function Drawer({ spec, layout, stageW, floating, others, alone }: { spec: PanelSpec; layout: Layout; stageW: number; floating: boolean; others: number; alone?: boolean }) {
  const w = drawerW(spec, layout[spec.id], stageW, others, floating);
  const max = drawerMax(spec, stageW, others, floating);
  const split = useSplitter(spec, w, max);
  return (
    <div className={"stage-drawer" + (alone ? " stage-alone" : "")} data-side={sideOf(spec)} data-floating={(floating && !alone) || undefined}
         style={alone ? undefined : { width: w }} data-testid="stage-drawer" data-alone={alone || undefined}
         data-panel-in={spec.id} data-content-w={contentWOf(spec)} data-max={max} data-drawing={spec.drawing || undefined}>
      {!alone && (
        <span className="stage-splitter" onPointerDown={split} role="separator" aria-orientation="vertical" aria-label={`Resize ${spec.title}`}
              aria-valuenow={w} aria-valuemin={DRAWER_MIN} aria-valuemax={max} data-testid="stage-splitter"
              title="Drag to resize (Alt+Left / Alt+Right on the drawer)" />
      )}
      <Panel spec={spec} p={layout[spec.id]} width={alone ? stageW : w} />
    </div>
  );
}

export function Stage({ specs, layout, bp, full, bar }: { specs: PanelSpec[]; layout: Layout; bp: Breakpoint; full: boolean; bar?: ReactNode }) {
  const ws = useWorkspace();
  const [row, stageW] = useWidth();
  const solo = soloOf(specs, layout, useStore(layoutStore(ws.section), (s) => s.solo));
  const main = mainOf(specs);
  const shown = full ? main : shownMain(specs, layout);
  const float = floats(bp) || !main;
  const open = openDrawers(specs, layout);
  const alone = !full && solo ? specs.find((s) => s.id === solo) : undefined;
  const drawerAlone = alone && roleOf(alone) === "drawer" ? alone : undefined;
  const mainAlone = !!alone && !drawerAlone;
  const docks = specs.filter((s) => roleOf(s) === "dock" && layout[s.id]); // a bar at the main thing's foot (a prompt box)
  // closed panels that keep their body mounted (an iframe), and the main group's others while a tab shows
  const kept = specs.filter((s) => s.keepAlive && layout[s.id]?.collapsed);
  const side = (which: "left" | "right") => (mainAlone ? [] : open.filter((s) => sideOf(s) === which));
  // a drawer alone stands in its own slot (its side's; a floating one the right), so it is the same element as before
  const aloneSlot = drawerAlone ? (float ? "right" : sideOf(drawerAlone)) : "";
  const leftList = drawerAlone ? (aloneSlot === "left" ? [drawerAlone] : []) : !float && !full ? side("left") : [];
  const rightList = drawerAlone ? (aloneSlot === "right" ? [drawerAlone] : []) : full ? [] : float ? (mainAlone ? [] : open.slice(-1)) : side("right");
  const widthOf = (s: PanelSpec) => drawerW(s, layout[s.id], stageW, 0, false);
  const othersOf = (s: PanelSpec) => open.filter((o) => o.id !== s.id).reduce((t, o) => t + widthOf(o), 0);
  // the full arrangement: every open panel but the main thing in one drawer per side (tabs on the right), top to bottom
  // (a panel closed there shows as its title line, as the drivers knew the old arrangement's strips)
  const stack = (which: "left" | "right") => full ? specs.filter((s) => s.id !== main?.id && roleOf(s) !== "dock" && layout[s.id] && (roleOf(s) === "drawer" ? sideOf(s) : "right") === which) : [];
  const fullDrawer = (which: "left" | "right") => {
    const list = stack(which);
    if (!list.length) return null;
    const w = DRAWER_MIN; // the drivers' door: the narrowest drawer, so the main thing keeps the room it had in the old full grid
    return (
      <div className="stage-drawer stage-full" data-side={which} style={{ width: w }} data-testid="stage-drawer">
        {list.map((s) => <Panel key={s.id} spec={s} p={layout[s.id]} width={w} bar style={s.fullGrow && !layout[s.id].collapsed ? { flexGrow: s.fullGrow } : undefined} />)}
      </div>
    );
  };
  return (
    <>
      {bar}
      <div className="stage-row" ref={row} data-testid="stage" data-float={float || undefined} data-full={full || undefined} data-solo={solo || undefined}>
        {full && fullDrawer("left")}
        {leftList.map((s) => <Drawer key={s.id} spec={s} layout={layout} stageW={stageW} floating={false} others={othersOf(s)} alone={s === drawerAlone} />)}
        {main && (
          <div className="stage-main" data-testid="stage-main" data-panel-in={shown?.id} data-docked={docks.length ? true : undefined}
               data-away={drawerAlone ? true : undefined} aria-hidden={drawerAlone ? true : undefined}>
            {shown && layout[shown.id] && <Panel key={shown.id} spec={shown} p={{ ...layout[shown.id], collapsed: false }} />}
            {docks.map((s) => <Panel key={s.id} spec={s} p={{ ...layout[s.id], collapsed: false }} />)}
          </div>
        )}
        {full && fullDrawer("right")}
        {rightList.map((s) => <Drawer key={s.id} spec={s} layout={layout} stageW={stageW} floating={float} others={float ? 0 : othersOf(s)} alone={s === drawerAlone} />)}
        {kept.length > 0 && (
          <div hidden>
            {kept.filter((s) => roleOf(s) !== "main").map((s) => <Panel key={s.id} spec={s} p={layout[s.id]} />)}
          </div>
        )}
      </div>
    </>
  );
}
