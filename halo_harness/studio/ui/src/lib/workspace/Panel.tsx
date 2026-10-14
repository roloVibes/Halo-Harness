// One workspace panel: glass surface, HUD corner brackets, a title bar that
// drags it, eight resize handles, and three depths -- the Glance face, the
// Expand face (detail) and Settings (the gear opens the Inspector).
import { useEffect, useRef, type CSSProperties } from "react";
import { Icon } from "../ui/Icon";
import { studio, useStore, type SectionId } from "../store";
import type { MotionState } from "../motion";
import { useGesture, usePanelKeys, useWorkspace } from "./controller";
import { effH } from "./grid";
import { layoutStore, patchPanel } from "./persist";
import type { Gesture, PanelLayout, PanelSpec } from "./types";

const HANDLES: Gesture[] = ["n", "s", "e", "w", "ne", "nw", "se", "sw"];
const noMotion = (): MotionState => "none";

function Handle({ id, g }: { id: string; g: Gesture }) {
  const down = useGesture(id, g);
  return <span className={`rz rz-${g}`} onPointerDown={down} aria-hidden="true" />;
}

export function Panel({ spec, p }: { spec: PanelSpec; p: PanelLayout }) {
  const ws = useWorkspace();
  const useMotion = spec.useMotion ?? noMotion;
  const motion = useMotion();
  const move = useGesture(spec.id, "move");
  const keys = usePanelKeys(spec.id);
  const ref = useRef<HTMLDivElement>(null);
  const focus = useStore(layoutStore(ws.section), (s) => s.focus);
  const inspecting = useStore(studio, (s) => s.inspector?.section === ws.section && s.inspector?.panel === spec.id);

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
  const openSettings = () =>
    studio.update((s) => ({
      inspector: inspecting ? null : { section: s.section as SectionId, panel: spec.id },
    }));

  return (
    <section className="ws-cell" style={style} data-panel={spec.id} data-floating={p.floating || undefined}>
      <div
        ref={ref}
        className="panel glass"
        data-motion={motion}
        data-collapsed={p.collapsed || undefined}
        data-face={face}
        data-inspecting={inspecting || undefined}
        tabIndex={0}
        onKeyDown={keys}
        aria-label={`${spec.title} panel`}
        data-testid={spec.testid}
      >
        <span className="hud-brackets" aria-hidden="true" />
        <header
          className="panel-bar"
          onPointerDown={move}
          onDoubleClick={() => hasDetail && set({ face: face === "glance" ? "detail" : "glance" })}
          title="Drag to move. Alt+arrows move, Alt+Shift+arrows resize."
        >
          <span className="panel-dot" data-motion={motion} aria-hidden="true" />
          <h3 className="panel-title">{spec.title}</h3>
          {hasDetail && (
            <span className="panel-face mono" aria-label={`face: ${face}`}>
              {face === "glance" ? "GLANCE" : "DETAIL"}
            </span>
          )}
          <span className="panel-tools">
            {hasDetail && (
              <button
                className="icon-btn"
                onClick={() => set({ face: face === "glance" ? "detail" : "glance", collapsed: false })}
                title={face === "glance" ? "Expand: show the details" : "Glance: the summary"}
                aria-label={face === "glance" ? "Expand" : "Glance"}
              >
                <Icon name={face === "glance" ? "expand" : "shrink"} />
              </button>
            )}
            <button
              className="icon-btn"
              onClick={() => set({ collapsed: !p.collapsed })}
              title={p.collapsed ? "Open the panel" : "Collapse to a strip"}
              aria-label={p.collapsed ? "Open" : "Collapse"}
              aria-expanded={!p.collapsed}
            >
              <Icon name={p.collapsed ? "chevron-right" : "chevron-down"} />
            </button>
            <button
              className="icon-btn"
              onClick={() => set({ floating: !p.floating, z: (p.z || 0) + 1 })}
              title={p.floating ? "Dock back into the grid" : "Pop out: float over the grid"}
              aria-label={p.floating ? "Dock" : "Pop out"}
              aria-pressed={p.floating}
            >
              <Icon name={p.floating ? "dock" : "popout"} />
            </button>
            <button className="icon-btn" onClick={openSettings} title="Settings (opens the Inspector)" aria-label="Settings" aria-pressed={inspecting}>
              <Icon name="gear" />
            </button>
          </span>
        </header>
        {spec.keepAlive && hasDetail ? (
          <>
            {face === "glance" && !p.collapsed && <div className="panel-body face-glance"><spec.glance /></div>}
            <div className="panel-body face-detail" hidden={p.collapsed || face !== "detail"}>
              {spec.detail && <spec.detail />}
            </div>
          </>
        ) : (
          !p.collapsed && <div className={`panel-body face-${face}`}>{face === "detail" && spec.detail ? <spec.detail /> : <spec.glance />}</div>
        )}
        {!p.collapsed && HANDLES.map((g) => <Handle key={g} id={spec.id} g={g} />)}
      </div>
    </section>
  );
}
