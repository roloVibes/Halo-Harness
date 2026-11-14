// A section's workspace (3.6.0.0 R0a: a stage, not a grid of tiles). One main thing has most of the room; every other
// panel is a named button in the view bar and opens as a drawer beside it (or as a tab in its place). The first draw
// takes what this browser kept for the view (persist.ts v3: the drawers open, their widths, the tab shown); nothing
// else opens by itself. `?open=a,b` opens those panels (a link, a door); `?open=all` opens every drawer, stacked in
// one right drawer (the drivers' door and a capture's). `version`: the view's layout version (a saved view of an
// older one shows the one-time note). `lead`: what the view puts at the start of its bar (Agents: its views).
import { useEffect, useMemo, useRef, type ReactNode } from "react";
import { useStore } from "../store";
import { useBreakpoint } from "./breakpoint";
import { WorkspaceContext, type WorkspaceApi } from "./controller";
import { answerNote, layoutStore, registerSpecs, savedLayout, setLayout, stageWidth, takeNote } from "./persist";
import { FULL_PAGE, OPEN } from "./query";
import { fullLayout, mainOf, merge, openIn } from "./rules";
import { Stage } from "./Stage";
import { ViewBar } from "./ViewBar";
import type { PanelSpec } from "./types";

export { resetLayout, layoutStore, patchPanel, focusPanel, showPanel, hidePanel, LAYOUT_PREFIX } from "./persist";
export type { PanelSpec, Layout, PanelLayout, Face } from "./types";

export { FULL_PAGE } from "./query";

function Note({ section, note }: { section: string; note: "changed" | "dropped" }) {
  const text = note === "dropped"
    ? "The layout changed: each view opens on its main thing now, and every other panel is a button in this bar."
    : "The layout of this view changed in this version. You kept yours.";
  return (
    <div className="layout-note" role="status" data-testid="layout-note" data-note={note}>
      <span>{text}</span>
      {note === "changed" && <button type="button" className="btn btn-sm" data-testid="layout-note-new" onClick={() => answerNote(section, true)}>Use the new one</button>}
      <button type="button" className="btn btn-sm btn-ghost" data-testid="layout-note-keep" onClick={() => answerNote(section, false)}>{note === "changed" ? "Keep mine" : "OK"}</button>
    </div>
  );
}

export function Workspace({ section, specs, version = 1, lead }: { section: string; specs: PanelSpec[]; version?: number; lead?: ReactNode }) {
  const outer = useRef<HTMLDivElement>(null);
  const { layout, note } = useStore(layoutStore(section), (s) => s);
  const bp = useBreakpoint();
  registerSpecs(section, specs, version);

  useEffect(() => {
    if (!layout) {
      const n = takeNote(section);
      let next = FULL_PAGE ? fullLayout(specs) : merge(specs, savedLayout(section, specs));
      if (!FULL_PAGE) for (const id of OPEN) if (next[id]) next = openIn(next, specs, id, stageWidth(section));
      setLayout(section, next, false);
      if (n) layoutStore(section).update(() => ({ note: n }));
    } else if (specs.some((s) => !s.optional && !layout[s.id])) {
      setLayout(section, merge(specs, layout), false); // a pack's panel arrived: what is open stays open
    }
  }, [layout, section, specs]);

  const api = useMemo<WorkspaceApi>(
    () => ({
      section,
      specs,
      metrics: () => ({ width: outer.current?.clientWidth || 1, height: outer.current?.clientHeight || 1 }),
    }),
    [section, specs],
  );
  const hasMain = !!mainOf(specs);
  return (
    <WorkspaceContext.Provider value={api}>
      <div className="workspace" ref={outer} data-section={section} data-bp={bp} data-main={hasMain || undefined}>
        {layout && (
          <Stage specs={specs} layout={layout} bp={bp} full={FULL_PAGE}
                 bar={<>
                   {note && <Note section={section} note={note} />}
                   {hasMain && <ViewBar specs={specs} layout={layout} lead={lead} />}
                 </>} />
        )}
      </div>
    </WorkspaceContext.Provider>
  );
}
