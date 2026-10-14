// One workspace panel: glass surface, HUD corner brackets, a title bar that
// drags it (the title, the panel's one-line `about`, ONE Compact / Expand
// toggle and ONE ... menu), eight resize handles, and its two faces: the full
// one (detail, the default) and the compact one (glance). Clicking anywhere
// on a panel focuses it (the ring; an open Inspector follows), and `?` on a
// focused panel opens its help (`?` again: how the whole section works).
import { useCallback, useEffect, useRef, useState, type CSSProperties, type KeyboardEvent, type PointerEvent } from "react";
import { Icon } from "../ui/Icon";
import { openHelp, studio, useStore, type SectionId } from "../store";
import type { MotionState } from "../motion";
import { useGesture, usePanelKeys, useWorkspace } from "./controller";
import { effH } from "./grid";
import { activatePanel, layoutStore, patchPanel, resetPanel } from "./persist";
import { PanelHelp } from "./PanelHelp";
import { PanelMenu, type MenuItem } from "./PanelMenu";
import type { Gesture, PanelLayout, PanelSpec } from "./types";

const HANDLES: Gesture[] = ["n", "s", "e", "w", "ne", "nw", "se", "sw"];
const INTERACTIVE = "input, textarea, select, button, a, iframe, [contenteditable], [tabindex]";
const TYPING = "input, textarea, select, [contenteditable]";
const noMotion = (): MotionState => "none";
const titleOf = (section: string) => section.charAt(0).toUpperCase() + section.slice(1);

function Handle({ id, g }: { id: string; g: Gesture }) {
  const down = useGesture(id, g);
  return <span className={`rz rz-${g}`} onPointerDown={down} aria-hidden="true" />;
}

/** True while the element's content is taller than its box (the body shows a "more below" edge). */
function useOverflow(el: HTMLElement | null): boolean {
  const [over, setOver] = useState(false);
  useEffect(() => {
    if (!el) return;
    const check = () => setOver(el.scrollHeight > el.clientHeight + 2);
    const ro = new ResizeObserver(check);
    const watch = () => {
      ro.disconnect();
      ro.observe(el);
      for (const c of Array.from(el.children)) ro.observe(c);
      check();
    };
    const mo = new MutationObserver(watch);
    mo.observe(el, { childList: true });
    watch();
    return () => {
      ro.disconnect();
      mo.disconnect();
    };
  }, [el]);
  return over;
}

export function Panel({ spec, p }: { spec: PanelSpec; p: PanelLayout }) {
  const ws = useWorkspace();
  const useMotion = spec.useMotion ?? noMotion;
  const motion = useMotion();
  const move = useGesture(spec.id, "move");
  const keys = usePanelKeys(spec.id);
  const ref = useRef<HTMLDivElement>(null);
  const [body, setBody] = useState<HTMLDivElement | null>(null);
  const [help, setHelp] = useState(false);
  const focus = useStore(layoutStore(ws.section), (s) => s.focus);
  const active = useStore(layoutStore(ws.section), (s) => s.active === spec.id);
  const inspecting = useStore(studio, (s) => s.inspector?.section === ws.section && s.inspector?.panel === spec.id);
  const over = useOverflow(body);
  const closeHelp = useCallback(() => setHelp(false), []);

  useEffect(() => {
    if (focus === spec.id && ref.current) {
      ref.current.focus({ preventScroll: true });
      ref.current.scrollIntoView({ block: "nearest", behavior: "smooth" });
      layoutStore(ws.section).update(() => ({ focus: "" }));
    }
  }, [focus, spec.id, ws.section]);

  const style: CSSProperties = p.floating
    ? { position: "absolute", left: p.fx, top: p.fy, width: p.fw, height: p.fh, zIndex: 20 + (p.z || 0) }
    : { gridColumn: `${p.x + 1} / span ${p.w}`, gridRow: `${p.y + 1} / span ${effH(p)}` };
  const hasDetail = !!spec.detail;
  const face = hasDetail ? p.face : "glance";
  const set = (patch: Partial<PanelLayout>) => patchPanel(ws.section, spec.id, patch);
  const toggleFace = () => hasDetail && set({ face: face === "glance" ? "detail" : "glance", collapsed: false });
  const settings = () =>
    studio.update((s) => ({ inspector: inspecting ? null : { section: s.section as SectionId, panel: spec.id } }));

  /** This panel is the one the user is on: the ring, and an open Inspector shows it. */
  const activate = () => {
    activatePanel(ws.section, spec.id);
    const insp = studio.get().inspector;
    if (insp && insp.section === ws.section && insp.panel !== spec.id)
      studio.update(() => ({ inspector: { section: ws.section as SectionId, panel: spec.id } }));
  };
  const onPointerDown = (ev: PointerEvent<HTMLDivElement>) => {
    activate();
    const hit = (ev.target as HTMLElement).closest(INTERACTIVE);
    if (!hit || hit === ref.current) ref.current?.focus({ preventScroll: true });
  };
  const onKey = (ev: KeyboardEvent<HTMLDivElement>) => {
    const typing = (ev.target as HTMLElement).closest(TYPING);
    if (ev.key === "?" && !typing && !ev.ctrlKey && !ev.metaKey && !ev.altKey) {
      ev.preventDefault();
      if (help) {
        setHelp(false);
        openHelp(ws.section as SectionId);
      } else setHelp(true);
      return;
    }
    if (ev.key === "Escape" && help) {
      ev.preventDefault();
      setHelp(false);
      return;
    }
    keys(ev);
  };

  const items: MenuItem[] = [
    { id: "float", label: p.floating ? "Dock into the grid" : "Float over the grid", icon: p.floating ? "dock" : "popout", run: () => set({ floating: !p.floating, z: (p.z || 0) + 1 }) },
    { id: "collapse", label: p.collapsed ? "Open the panel" : "Collapse to a strip", icon: p.collapsed ? "chevron-right" : "chevron-down", run: () => set({ collapsed: !p.collapsed }) },
    { id: "reset", label: "Reset this panel", icon: "reset", run: () => resetPanel(ws.section, spec) },
    { id: "settings", label: inspecting ? "Close the settings" : "Settings", icon: "gear", run: settings },
    { id: "help", label: "Help", icon: "help", kbd: "?", run: () => setHelp(true) },
  ];
  const bodyRef = (show: boolean) => (show ? setBody : undefined);

  return (
    <section className="ws-cell" style={style} data-panel={spec.id} data-floating={p.floating || undefined}>
      <div
        ref={ref}
        className="panel glass"
        data-motion={motion}
        data-collapsed={p.collapsed || undefined}
        data-face={face}
        data-active={active || undefined}
        data-inspecting={inspecting || undefined}
        tabIndex={0}
        onKeyDown={onKey}
        onFocus={activate}
        onPointerDownCapture={onPointerDown}
        aria-label={`${spec.title} panel`}
        data-testid={spec.testid}
      >
        <span className="hud-brackets" aria-hidden="true" />
        <header className="panel-bar" onPointerDown={move} onDoubleClick={toggleFace} title="Drag to move. Alt+arrows move, Alt+Shift+arrows resize.">
          <span className="panel-dot" data-motion={motion} aria-hidden="true" />
          <h3 className="panel-title">{spec.title}</h3>
          <span className="panel-about" data-testid={spec.about ? "panel-about" : undefined} title={spec.about}>
            {spec.about}
          </span>
          <span className="panel-tools">
            {p.collapsed ? (
              <button className="icon-btn" onClick={() => set({ collapsed: false })} title="Open the panel" aria-label="Open" aria-expanded={false}>
                <Icon name="chevron-right" />
              </button>
            ) : (
              hasDetail && (
                <button className="icon-btn" onClick={toggleFace} title="Compact / Expand" aria-label={face === "glance" ? "Expand" : "Compact"} data-testid="panel-compact">
                  <Icon name={face === "glance" ? "expand" : "shrink"} />
                </button>
              )
            )}
            <PanelMenu title={spec.title} items={items} />
          </span>
        </header>
        {spec.keepAlive && hasDetail ? (
          <>
            {face === "glance" && !p.collapsed && (
              <div className="panel-body face-glance" ref={bodyRef(true)} data-overflow={over || undefined}>
                <spec.glance />
              </div>
            )}
            <div className="panel-body face-detail" hidden={p.collapsed || face !== "detail"} ref={bodyRef(face === "detail")} data-overflow={(face === "detail" && over) || undefined}>
              {spec.detail && <spec.detail />}
            </div>
          </>
        ) : (
          !p.collapsed && (
            <div className={`panel-body face-${face}`} ref={setBody} data-overflow={over || undefined}>
              {face === "detail" && spec.detail ? <spec.detail /> : <spec.glance />}
            </div>
          )
        )}
        {!p.collapsed && HANDLES.map((g) => <Handle key={g} id={spec.id} g={g} />)}
        {help && <PanelHelp spec={spec} anchor={ref} sectionTitle={titleOf(ws.section)} onClose={closeHelp} />}
      </div>
    </section>
  );
}
