// A tier box on the Roles canvas (3.0.7.0 R2; 3.1.6.0 R1 its own head): the
// caret collapses it to its label strip (so does a click on the strip's empty
// part), a double-click on its name renames it in place (Enter keeps it,
// Escape drops it), a second row shows the tier's model pill and its trigger
// chip (`⚡ every 30m`) when it names either (a click opens that form of the
// box menu), and `...` opens the box's own menu (TierMenu.tsx). An empty
// declared tier says "Drag cards here" inside its holo brackets.
import { memo, useEffect, useRef, type KeyboardEvent, type MouseEvent } from "react";
import { useHelpGroup } from "../../lib/fieldHelp";
import { shortRef } from "../shared/catalog";
import type { GlowState } from "./glow";
import type { Box } from "./layout";
import { roles, useRoles, type TierMenuAt } from "./store";
import { renameTier } from "./tierActions";
import { triggerText } from "./tierText";
import type { Tier } from "./types";

type Props = {
  t: Tier;
  b: Box;
  count: number;
  collapsed: boolean;
  hot: boolean;
  /** The strongest glow of its cards (working, waiting, done, failed), "" for none. */
  state: GlowState | "";
  onToggle: (name: string) => void;
};

const stop = (e: { stopPropagation: () => void }) => e.stopPropagation();

function RenameField({ name }: { name: string }) {
  const ref = useRef<HTMLInputElement>(null);
  const done = useRef(false);
  useEffect(() => {
    ref.current?.focus({ preventScroll: true });
    ref.current?.select();
  }, []);
  const finish = (keep: boolean) => {
    if (done.current) return;
    done.current = true;
    if (keep) void renameTier(name, ref.current?.value || "");
    else roles.update(() => ({ tierRename: "" }));
  };
  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    e.stopPropagation(); // the canvas's own keys (A, F, Delete) stay out of the field
    if (e.key === "Enter") (e.preventDefault(), finish(true));
    else if (e.key === "Escape") (e.preventDefault(), finish(false));
  };
  return (
    <input ref={ref} className="input mono rc-tier-rename" defaultValue={name} aria-label={`Rename tier ${name}`} data-testid="roles-tier-rename"
           onKeyDown={onKey} onBlur={() => finish(true)} onPointerDown={stop} onClick={stop} onDoubleClick={stop} />
  );
}

export const TierBox = memo(function TierBox({ t, b, count, collapsed, hot, state, onToggle }: Props) {
  const renaming = useRoles((s) => s.tierRename === t.name);
  const h = useHelpGroup("lineup_fields");
  const trig = triggerText(t.trigger);
  const open = (e: MouseEvent<HTMLElement>, face: TierMenuAt["face"]) => {
    e.stopPropagation();
    const r = e.currentTarget.getBoundingClientRect();
    roles.update(() => ({ tierMenu: { tier: t.name, x: r.left, y: r.bottom, face } }));
  };
  return (
    <div className="rc-tier holo-frame" data-testid="roles-tier" data-tier={t.name} data-index={t.index} data-implicit={t.implicit || undefined}
         data-collapsed={collapsed || undefined} data-hot={hot || undefined} data-holo-state={state || undefined} data-chips={t.model || t.trigger ? "" : undefined}
         style={{ left: b.x, top: b.y, width: b.w, height: b.h }}>
      <span className="holo-corners" aria-hidden="true" />
      <div className="rc-tier-head" onClick={() => !renaming && onToggle(t.name)} title={collapsed ? "Expand this tier" : "Collapse this tier to its label"}>
        <button type="button" className="rc-tier-caret" onClick={(e) => (stop(e), onToggle(t.name))} aria-expanded={!collapsed} data-testid="roles-tier-toggle"
                aria-label={collapsed ? `Expand tier ${t.name}` : `Collapse tier ${t.name}`}>
          {collapsed ? "▸" : "▾"}
        </button>
        {renaming ? (
          <RenameField name={t.name} />
        ) : (
          <span className="rc-tier-label" data-testid="roles-tier-name" onClick={stop} onDoubleClick={() => !t.implicit && roles.update(() => ({ tierRename: t.name }))}
                title={t.implicit ? "An implicit tier: Add tier makes one of your own" : h["tiers.rename"] || "Double-click to rename"}>
            Tier {t.index} · {t.name}
          </span>
        )}
        <span className="rc-tier-count mono">
          {count}
          {t.max_parallel ? ` · max ${t.max_parallel}` : ""}
          {t.implicit ? " · implicit" : ""}
        </span>
        {!t.implicit && (
          <button type="button" className="rc-tier-more mono" onClick={(e) => open(e, "menu")} aria-haspopup="menu" aria-label={`tier ${t.name}: more`}
                  title={h["tiers.menu"]} data-testid="roles-tier-more">
            ...
          </button>
        )}
      </div>
      {(t.model || trig) && (
        <div className="rc-tier-chips" onClick={stop}>
          {t.model && (
            <button type="button" className="rc-tier-model mono" data-testid="roles-tier-model" data-ref={t.model} onClick={(e) => open(e, "model")}
                    title={`${t.model}: ${h["tiers.model"] || "what this tier's members run on"} (click to change)`}>
              {shortRef(t.model)}
            </button>
          )}
          {trig && (
            <button type="button" className="rc-tier-trigger mono" data-testid="roles-tier-trigger" data-on={t.trigger?.on} onClick={(e) => open(e, "trigger")}
                    title={`${trig}${t.trigger?.prompt ? `: "${t.trigger.prompt}"` : ""} -- ${h["tiers.trigger"] || "starts this tier's lead"} (click to change)`}>
              ⚡ {trig}
            </button>
          )}
        </div>
      )}
      {!count && !collapsed && !t.implicit && <div className="rc-tier-drop mono" data-testid="roles-tier-drop">Drag cards here</div>}
    </div>
  );
});
