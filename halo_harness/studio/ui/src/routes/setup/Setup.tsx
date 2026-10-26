// Setup (Alt+8, 3.3.0.0 R1): the terminal wizard's blocks as one page, the
// last core section. On top the status strip (the providers set up, the
// default model, the lineup, the permission mode, the terminal theme), under
// it the panel workspace: one panel per block, each its own form with its own
// Save and its own saved / changed / problem line (BlockFoot), so they are
// filled in any order; the rail lists the blocks with that line. This round
// draws Default model, Permissions, Terminal theme and Team; Providers and
// Local models come with R2, Linux fixes and Check with R3 (one line each).
import { useEffect } from "react";
import type { MotionState } from "../../lib/motion";
import { Workspace } from "../../lib/workspace/Workspace";
import { focusPanel, layoutStore, patchPanel } from "../../lib/workspace/persist";
import type { PanelSpec } from "../../lib/workspace/types";
import { HELP } from "../help";
import { DefaultModelDetail, DefaultModelGlance } from "./DefaultModel";
import { PermissionsDetail, PermissionsGlance } from "./Permissions";
import { blockWord, providersSet, startSetup, useSetup, type BlockId } from "./store";
import { TeamDetail, TeamGlance } from "./Team";
import { ThemeDetail, ThemeGlance } from "./Theme";

function useSetupMotion(): MotionState {
  useEffect(() => startSetup(), []);
  return useSetup((s) => (s.busy ? "working" : "none"));
}

/** A block another round fills in: what it will hold and what does it today, one line. */
function later(id: string, round: string, line: string) {
  const Body = () => (
    <p className="su-later muted" data-testid="setup-later" data-block={id}>
      This block comes with {round}. {line}
    </p>
  );
  return Body;
}

const ProvidersLater = later("providers", "R2", "Until then halo init sets a provider up in the terminal (its Providers tabs).");
const LocalLater = later("local", "R2", "Until then halo init's Local models step adds model folders and picks the runtime.");
const LinuxLater = later("linux", "R3", "Until then halo doctor lists the Linux fixes this box is missing.");
const CheckLater = later("check", "R3", "Until then halo doctor and halo models --refresh check this setup.");

const panel = (id: string, rest: Omit<PanelSpec, "id" | "testid">): PanelSpec => ({ id, testid: id, ...HELP[id], ...rest, useMotion: useSetupMotion });

export const setupPanels: PanelSpec[] = [
  panel("setup-providers", { title: "Providers", x: 0, y: 0, w: 6, h: 12, minW: 4, minH: 8, face: "detail", glance: ProvidersLater, detail: ProvidersLater }),
  panel("setup-local", { title: "Local models", x: 6, y: 0, w: 6, h: 12, minW: 4, minH: 8, face: "detail", glance: LocalLater, detail: LocalLater }),
  panel("setup-linux", { title: "Linux fixes", x: 12, y: 0, w: 6, h: 12, minW: 4, minH: 8, face: "detail", glance: LinuxLater, detail: LinuxLater }),
  panel("setup-check", { title: "Check", x: 18, y: 0, w: 6, h: 12, minW: 4, minH: 8, face: "detail", glance: CheckLater, detail: CheckLater }),
  panel("setup-model", { title: "Default model", x: 0, y: 12, w: 8, h: 0, minW: 6, minH: 12, face: "detail", glance: DefaultModelGlance, detail: DefaultModelDetail }),
  panel("setup-permissions", { title: "Permissions", x: 8, y: 12, w: 6, h: 42, minW: 5, minH: 12, face: "detail", glance: PermissionsGlance, detail: PermissionsDetail }),
  panel("setup-theme", { title: "Terminal theme", x: 8, y: 54, w: 6, h: 0, minW: 5, minH: 12, face: "detail", glance: ThemeGlance, detail: ThemeDetail }),
  panel("setup-team", { title: "Team", x: 14, y: 12, w: 10, h: 0, minW: 6, minH: 12, face: "detail", glance: TeamGlance, detail: TeamDetail }),
];

/** The rail's block list: each block with its line; a click brings its panel back and focuses it. */
const BLOCKS: [string, string, BlockId | string][] = [
  ["setup-providers", "Providers", "R2"], ["setup-local", "Local models", "R2"], ["setup-model", "Default model", "model"],
  ["setup-permissions", "Permissions", "permission_mode"], ["setup-theme", "Terminal theme", "theme"], ["setup-team", "Team", "team"],
  ["setup-linux", "Linux fixes", "R3"], ["setup-check", "Check", "R3"],
];

function openBlock(id: string): void {
  if (layoutStore("setup").get().layout?.[id]) patchPanel("setup", id, { collapsed: false }, false);
  focusPanel("setup", id);
}

export function SetupRail() {
  // one string per read (a new object each read would redraw forever), split back into the blocks' words
  const joined = useSetup((s) => BLOCKS.map(([, , b]) => (b.startsWith("R") ? `with ${b}` : blockWord(s, b as BlockId))).join("|"));
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
    ["provider", "Provider", set.length ? set.join(", ") : "none"],
    ["model", "Default model", d.model || "not set"],
    ["lineup", "Lineup", lineup],
    ["permissions", "Permissions", d.permission_mode || "not set"],
    ["theme", "Theme", d.theme || `${d.theme_default} (default)`],
  ];
  return (
    <div className="su-strip" role="status" aria-label="This setup" data-testid="setup-strip">
      {cells.map(([k, label, value]) => (
        <span key={k} className="su-cell" data-testid="setup-strip-cell" data-key={k} data-unset={value === "none" || value === "not set" || undefined}>
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
