// One workspace panel (3.6.0.0 R0a: a place on the stage, never a tile): a title line (the title, the ? help, a close
// on a drawer or a tab, and ONE ... menu: Compact / Expand, Close, Reset width, Remove (an optional panel),
// Settings, Help), a 1 px border, and its two faces: the full one (detail, the default) and the compact one (glance).
// The focused panel alone (`.focused`, `data-focused`: the one you clicked or tabbed into, else the main thing)
// carries the ornament: the HUD brackets, the glow and the mono data line. `?` on a focused panel opens its help
// (its about line first; `?` again: how the whole section works). Panels do not move: the view bar opens and closes
// them, a drawer's inner edge (Stage.tsx) and Alt+Left / Alt+Right resize it.
import { useCallback, useEffect, useRef, useState, type CSSProperties, type KeyboardEvent, type PointerEvent } from "react";
import { Icon } from "../ui/Icon";
import { openHelp, studio, useStore, type SectionId } from "../store";
import type { MotionState } from "../motion";
import { usePanelKeys, useWorkspace } from "./controller";
import { activatePanel, hidePanel, layoutStore, patchPanel, resetPanel } from "./persist";
import { PanelHelp } from "./PanelHelp";
import { PanelMenu, type MenuItem } from "./PanelMenu";
import { mainOf, roleOf } from "./rules";
import type { Layout, PanelLayout, PanelSpec } from "./types";

const INTERACTIVE = "input, textarea, select, button, a, iframe, [contenteditable], [tabindex]";
const TYPING = "input, textarea, select, [contenteditable]";
const noMotion = (): MotionState => "none";
const titleOf = (section: string) => // a pack's section (<id>--<name>) is "this section"
  section.includes("--") ? "this section" : section.charAt(0).toUpperCase() + section.split("-")[0].slice(1);

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

/** The panel that carries the ornament while nobody clicked one: the main thing when it shows, else the first open one. */
function leadOf(specs: PanelSpec[], layout: Layout | null): string {
  const open = (s: PanelSpec) => !!layout?.[s.id] && !layout[s.id].collapsed;
  const main = mainOf(specs);
  return (main && open(main) ? main : specs.find(open))?.id ?? "";
}

/** `bar` (the full arrangement only, `?open=all`): a closed panel drawn as its title line, as the drivers knew it. */
export function Panel({ spec, p, style, width, bar }: { spec: PanelSpec; p: PanelLayout; style?: CSSProperties; width?: number; bar?: boolean }) {
  const ws = useWorkspace();
  const useMotion = spec.useMotion ?? noMotion;
  const motion = useMotion();
  const keys = usePanelKeys(spec.id);
  const ref = useRef<HTMLDivElement>(null);
  const [body, setBody] = useState<HTMLDivElement | null>(null);
  const [help, setHelp] = useState(false);
  const focus = useStore(layoutStore(ws.section), (s) => s.focus);
  const active = useStore(layoutStore(ws.section), (s) => s.active === spec.id);
  const focused = useStore(layoutStore(ws.section), (s) => (s.active && s.layout?.[s.active] && !s.layout[s.active].collapsed ? s.active : leadOf(ws.specs, s.layout)) === spec.id);
  const inspecting = useStore(studio, (s) => s.inspector?.section === ws.section && s.inspector?.panel === spec.id);
  const over = useOverflow(body);
  const closeHelp = useCallback(() => setHelp(false), []);
  const role = roleOf(spec);

  useEffect(() => {
    if (focus === spec.id && ref.current && !p.collapsed) {
      ref.current.focus({ preventScroll: true });
      ref.current.scrollIntoView({ block: "nearest", behavior: "smooth" });
      layoutStore(ws.section).update(() => ({ focus: "" }));
    }
  }, [focus, spec.id, ws.section, p.collapsed]);

  const hasDetail = !!spec.detail;
  const face = hasDetail ? p.face : "glance";
  const set = (patch: Partial<PanelLayout>) => patchPanel(ws.section, spec.id, patch);
  const toggleFace = () => hasDetail && set({ face: face === "glance" ? "detail" : "glance" });
  const settings = () =>
    studio.update(() => ({ inspector: inspecting ? null : { section: ws.section as SectionId, panel: spec.id } }));

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

  const closable = role !== "main";
  const items: MenuItem[] = [
    ...(hasDetail ? [{ id: "face", label: face === "glance" ? "Expand: the full face" : "Compact: the summary face", icon: face === "glance" ? "expand" : "shrink", run: toggleFace }] : []),
    ...(closable ? [{ id: "collapse", label: role === "tab" ? `Back to ${mainOf(ws.specs)?.title ?? "the main view"}` : "Close the drawer", icon: "close", run: () => set({ collapsed: true }) }] : []),
    ...(role === "drawer" ? [{ id: "reset", label: "Reset its width", icon: "reset", run: () => resetPanel(ws.section, spec) }] : []),
    ...(spec.optional ? [{ id: "remove", label: "Remove from this view (the palette adds it again)", icon: "close", run: () => hidePanel(ws.section, spec.id) }] : []),
    { id: "settings", label: inspecting ? "Close the settings" : "Settings", icon: "gear", run: settings },
    { id: "help", label: "Help", icon: "help", kbd: "?", run: () => setHelp(true) },
  ];
  const bodyRef = (show: boolean) => (show ? setBody : undefined);
  const where = role === "drawer" ? `drawer ${Math.round(width || 0)} px` : role;

  return (
    <section className="ws-cell" style={style} data-panel={spec.id} data-role={role} data-bar={(bar && p.collapsed) || undefined} hidden={(p.collapsed && !bar) || undefined}>
      <div
        ref={ref}
        className={"panel glass" + (focused ? " focused" : "")}
        data-motion={motion}
        data-collapsed={p.collapsed || undefined}
        data-face={face}
        data-active={active || undefined}
        data-focused={focused || undefined}
        data-inspecting={inspecting || undefined}
        tabIndex={0}
        onKeyDown={onKey}
        onFocus={activate}
        onPointerDownCapture={onPointerDown}
        aria-label={`${spec.title} panel`}
        data-testid={spec.testid}
      >
        {focused && <span className="hud-brackets" aria-hidden="true" />}
        <header className="panel-bar" data-density="bar" onDoubleClick={toggleFace} title={role === "drawer" ? "Alt+Left / Alt+Right: wider or narrower" : undefined}>
          <span className="panel-dot" data-motion={motion} aria-hidden="true" />
          <h3 className="panel-title" data-testid="panel-title" title={spec.about}>{spec.title}</h3>
          {focused && (
            <span className="panel-data mono" data-testid="panel-data" aria-hidden="true">
              {where}{hasDetail ? (face === "glance" ? " · compact" : " · full") : ""}
            </span>
          )}
          <span className="panel-tools">
            <button className="icon-btn" onClick={() => setHelp(!help)} title={`How to use ${spec.title} (?)`} aria-label="Help" aria-expanded={help} data-testid="panel-help-btn">
              <Icon name="help" />
            </button>
            {closable && (
              <button className="icon-btn" onClick={() => set({ collapsed: true })} title={role === "tab" ? "Back to the main view" : `Close ${spec.title} (its button in the bar opens it again)`}
                      aria-label={`Close ${spec.title}`} data-testid="panel-collapse">
                <Icon name="close" />
              </button>
            )}
            <PanelMenu title={spec.title} items={items} />
          </span>
        </header>
        {spec.keepAlive && hasDetail ? (
          <>
            {face === "glance" && !p.collapsed && (
              <div className="panel-body face-glance" data-density="body" ref={bodyRef(true)} data-overflow={over || undefined}>
                <spec.glance />
              </div>
            )}
            <div className="panel-body face-detail" data-density="body" hidden={p.collapsed || face !== "detail"} ref={bodyRef(face === "detail")} data-overflow={(face === "detail" && over) || undefined}>
              {spec.detail && <spec.detail />}
            </div>
          </>
        ) : (
          !p.collapsed && (
            <div className={`panel-body face-${face}`} data-density="body" ref={setBody} data-overflow={over || undefined}>
              {face === "detail" && spec.detail ? <spec.detail /> : <spec.glance />}
            </div>
          )
        )}
        {help && <PanelHelp spec={spec} anchor={ref} sectionTitle={titleOf(ws.section)} onClose={closeHelp} />}
      </div>
    </section>
  );
}
