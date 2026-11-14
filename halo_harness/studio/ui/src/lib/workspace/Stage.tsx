// The stage (3.6.0.0 R0a "room for everything in Studio"): a view's main thing with most of the room, a drawer slot
// on each side (full height, beside the main thing, pushing it: R2), the main thing's tabs shown in its place.
// Under 1100 px the drawer floats over the main thing with its close (R9); a view with no main thing (Local's Media
// over its page) floats its drawer too. `full` (`?open=all`, the drivers' door): every drawer and tab open, each side's
// stacked in one drawer that shares its height among them (tabs on the right). A drawer's inner edge is a splitter (controller.ts). Emits nothing of its own: the
// view bar and the doors open and close panels through persist.ts (open = patchPanel collapsed false, close = true,
// resize = setDrawerWidth).
import { useEffect, useRef, useState, type ReactNode } from "react";
import { floats, type Breakpoint } from "./breakpoint";
import { useSplitter } from "./controller";
import { Panel } from "./Panel";
import { contentWOf, drawerW, mainOf, openDrawers, roleOf, shownMain, sideOf } from "./rules";
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

function Drawer({ spec, layout, stageW, floating }: { spec: PanelSpec; layout: Layout; stageW: number; floating: boolean }) {
  const w = drawerW(spec, layout[spec.id], floating ? 0 : stageW);
  const split = useSplitter(spec, w);
  return (
    <div className="stage-drawer" data-side={sideOf(spec)} data-floating={floating || undefined} style={{ width: w }} data-testid="stage-drawer" data-panel-in={spec.id} data-content-w={contentWOf(spec)}>
      <span className="stage-splitter" onPointerDown={split} role="separator" aria-orientation="vertical" aria-label={`Resize ${spec.title}`} title="Drag to resize (Alt+Left / Alt+Right on the drawer)" />
      <Panel spec={spec} p={layout[spec.id]} width={w} />
    </div>
  );
}

export function Stage({ specs, layout, bp, full, bar }: { specs: PanelSpec[]; layout: Layout; bp: Breakpoint; full: boolean; bar?: ReactNode }) {
  const [row, stageW] = useWidth();
  const main = mainOf(specs);
  const shown = full ? main : shownMain(specs, layout);
  const float = floats(bp) || !main;
  const open = openDrawers(specs, layout);
  const docks = specs.filter((s) => roleOf(s) === "dock" && layout[s.id]); // a bar at the main thing's foot (a prompt box)
  // closed panels that keep their body mounted (an iframe), and the main group's others while a tab shows
  const kept = specs.filter((s) => s.keepAlive && layout[s.id]?.collapsed);
  const side = (which: "left" | "right") => open.filter((s) => sideOf(s) === which);
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
      <div className="stage-row" ref={row} data-testid="stage" data-float={float || undefined} data-full={full || undefined}>
        {full && fullDrawer("left")}
        {!float && !full && side("left").map((s) => <Drawer key={s.id} spec={s} layout={layout} stageW={stageW} floating={false} />)}
        {main && (
          <div className="stage-main" data-testid="stage-main" data-panel-in={shown?.id} data-docked={docks.length ? true : undefined}>
            {shown && layout[shown.id] && <Panel key={shown.id} spec={shown} p={{ ...layout[shown.id], collapsed: false }} />}
            {docks.map((s) => <Panel key={s.id} spec={s} p={{ ...layout[s.id], collapsed: false }} />)}
          </div>
        )}
        {full && fullDrawer("right")}
        {!full && (float ? open.slice(-1) : side("right")).map((s) => <Drawer key={s.id} spec={s} layout={layout} stageW={stageW} floating={float} />)}
        {kept.length > 0 && (
          <div hidden>
            {kept.filter((s) => roleOf(s) !== "main").map((s) => <Panel key={s.id} spec={s} p={layout[s.id]} />)}
          </div>
        )}
      </div>
    </>
  );
}
