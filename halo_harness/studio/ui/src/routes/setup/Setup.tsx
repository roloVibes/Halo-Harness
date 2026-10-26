// Setup (Alt+8, 3.3.0.0 R1): the terminal wizard's blocks as one page, the
// last core section. On top the status strip (the providers set up, the
// default model, the lineup, the permission mode, the terminal theme), under
// it the panel workspace: one panel per block, each its own form with its own
// Save and its own saved / changed / problem line (BlockFoot), so they are
// filled in any order; the rail lists the blocks with that line. R1 drew
// Default model, Permissions, Terminal theme and Team; R2 Providers (one card
// per provider) and Local models; R3 Linux fixes (only when this box needs
// them) and Check (the five checks as one job), and the strip's Last check.
import { useEffect } from "react";
import type { MotionState } from "../../lib/motion";
import { Workspace } from "../../lib/workspace/Workspace";
import { focusPanel, layoutStore, patchPanel } from "../../lib/workspace/persist";
import type { PanelSpec } from "../../lib/workspace/types";
import { HELP } from "../help";
import { CheckDetail, CheckGlance } from "./Check";
import { lastCheckWord } from "./checkStore";
import { LinuxFixesDetail, LinuxFixesGlance } from "./LinuxFixes";
import { LocalModelsDetail, LocalModelsGlance } from "./LocalModels";
import { DefaultModelDetail, DefaultModelGlance } from "./DefaultModel";
import { PermissionsDetail, PermissionsGlance } from "./Permissions";
import { ProvidersDetail, ProvidersGlance } from "./Providers";
import { blockWord, providersSet, startSetup, useSetup, type BlockId, type SetupState } from "./store";
import { TeamDetail, TeamGlance } from "./Team";
import { ThemeDetail, ThemeGlance } from "./Theme";

function useSetupMotion(): MotionState {
  useEffect(() => startSetup(), []);
  return useSetup((s) => (s.busy ? "working" : "none"));
}

const panel = (id: string, rest: Omit<PanelSpec, "id" | "testid">): PanelSpec => ({ id, testid: id, ...HELP[id], ...rest, useMotion: useSetupMotion });

export const setupPanels: PanelSpec[] = [
  panel("setup-providers", { title: "Providers", x: 0, y: 0, w: 14, h: 76, minW: 6, minH: 16, face: "detail", glance: ProvidersGlance, detail: ProvidersDetail }),
  panel("setup-local", { title: "Local models", x: 14, y: 0, w: 10, h: 76, minW: 5, minH: 16, face: "detail", glance: LocalModelsGlance, detail: LocalModelsDetail }),
  panel("setup-linux", { title: "Linux fixes", x: 0, y: 76, w: 8, h: 16, minW: 4, minH: 8, face: "detail", glance: LinuxFixesGlance, detail: LinuxFixesDetail }),
  panel("setup-check", { title: "Check", x: 8, y: 76, w: 16, h: 64, minW: 6, minH: 16, face: "detail", glance: CheckGlance, detail: CheckDetail }),
  panel("setup-model", { title: "Default model", x: 0, y: 92, w: 8, h: 72, minW: 6, minH: 12, face: "detail", glance: DefaultModelGlance, detail: DefaultModelDetail }),
  panel("setup-permissions", { title: "Permissions", x: 8, y: 140, w: 6, h: 42, minW: 5, minH: 12, face: "detail", glance: PermissionsGlance, detail: PermissionsDetail }),
  panel("setup-theme", { title: "Terminal theme", x: 8, y: 182, w: 6, h: 40, minW: 5, minH: 12, face: "detail", glance: ThemeGlance, detail: ThemeDetail }),
  panel("setup-team", { title: "Team", x: 14, y: 140, w: 10, h: 72, minW: 6, minH: 12, face: "detail", glance: TeamGlance, detail: TeamDetail }),
];

/** The rail's block list: each block with its line; a click brings its panel back and focuses it. */
const BLOCKS: [string, string, BlockId | string][] = [
  ["setup-providers", "Providers", "providers"], ["setup-local", "Local models", "local"], ["setup-model", "Default model", "model"],
  ["setup-permissions", "Permissions", "permission_mode"], ["setup-theme", "Terminal theme", "theme"], ["setup-team", "Team", "team"],
  ["setup-linux", "Linux fixes", "linux"], ["setup-check", "Check", "check"],
];

/** The rail's word for a block: how many providers are set, how many model folders, the fixes to apply, the last
 *  check, or the block's line. */
function railWord(s: SetupState, b: string): string {
  if (b === "providers") return `${providersSet(s.data).length} set`;
  if (b === "local") {
    const n = s.data?.local_models.model_dirs.length || 0;
    return `${n} folder${n === 1 ? "" : "s"}`;
  }
  if (b === "linux") return s.data?.linux_fixes.needed ? `${s.data.linux_fixes.items.length} to apply` : "none needed";
  if (b === "check") return lastCheckWord(s.data?.last_check);
  return blockWord(s, b as BlockId);
}

function openBlock(id: string): void {
  if (layoutStore("setup").get().layout?.[id]) patchPanel("setup", id, { collapsed: false }, false);
  focusPanel("setup", id);
}

export function SetupRail() {
  // one string per read (a new object each read would redraw forever), split back into the blocks' words
  const joined = useSetup((s) => BLOCKS.map(([, , b]) => railWord(s, b)).join("|"));
  const words = Object.fromEntries(joined.split("|").map((w, i) => [BLOCKS[i][0], w]));
  return (
    <nav className="rail-group su-rail" aria-label="Setup blocks" data-testid="setup-rail">
      <div className="rail-label mono">BLOCKS</div>
      {BLOCKS.map(([id, title]) => (
        <button key={id} className="rail-item" onClick={() => openBlock(id)} data-testid="setup-rail-block" data-block={id}>
          <span className="rail-item-text">{title}</span>
          <span className="su-word mono" data-word={words[id]}>
            {words[id]}
          </span>
        </button>
      ))}
    </nav>
  );
}

function Strip() {
  const d = useSetup((s) => s.data);
  if (!d) return <div className="su-strip mono muted" data-testid="setup-strip">reading the setup...</div>;
  const set = providersSet(d);
  const lineup = d.team.active === "one-model" ? "one model for everything" : d.team.active + (d.team.source === "default" ? " (default)" : "");
  const cells: [string, string, string][] = [
    ["provider", "Provider", set.length ? set.join(", ") : "no provider set"],
    ["model", "Default model", d.model || "not set"],
    ["lineup", "Lineup", lineup],
    ["permissions", "Permissions", d.permission_mode || "not set"],
    ["theme", "Theme", d.theme || `${d.theme_default} (default)`],
    ["check", "Last check", lastCheckWord(d.last_check)],
  ];
  return (
    <div className="su-strip" role="status" aria-label="This setup" data-testid="setup-strip">
      {cells.map(([k, label, value]) => (
        <span key={k} className="su-cell" data-testid="setup-strip-cell" data-key={k} data-unset={value === "no provider set" || value === "not set" || value === "not run" || / failed /.test(value) || undefined}>
          <span className="su-cell-label mono">{label}:</span> <span className="su-cell-value mono">{value}</span>
        </span>
      ))}
    </div>
  );
}

/** The section's page: the strip over the bare workspace (the workspace rules apply: move, make room, Arrange). */
export function SetupView({ section, specs }: { section: string; specs: PanelSpec[] }) {
  useEffect(() => startSetup(), []);
  return (
    <div className="su-page" data-testid="setup-page">
      <Strip />
      <div className="su-work">
        <Workspace section={section} specs={specs} />
      </div>
    </div>
  );
}

/** The section's entry (the rail or the palette may open a panel before the view draws). */
export function enterSetup(): void {
  startSetup();
}
