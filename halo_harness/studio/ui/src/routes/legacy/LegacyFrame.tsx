// Roles, Org and Design are the plain-JS pages from before the shell, served
// at /legacy/ and framed here so nothing regresses. `embedded=1` makes the
// page drop its own header (logo, Roles / Org / Design) for a slim toolbar
// and send its status line to the shell's status bar (shell/legacy.ts);
// `tour=off` because the shell's first-visit welcome stands in for the
// page's tour (`?` inside the page still replays it). The token goes in the
// fragment, exactly as `halo studio` hands it to the page.
import { token } from "../../lib/api";
import type { PanelSpec } from "../../lib/workspace/types";
import { HELP } from "../help";

export type LegacyMode = "roles" | "org" | "design";

export function legacySrc(mode: LegacyMode, embedded = true): string {
  return `legacy/index.html?mode=${mode}${embedded ? "&embedded=1&tour=off" : ""}#t=${token()}`;
}

export function LegacyFrame({ mode }: { mode: LegacyMode }) {
  return <iframe className="legacy-frame" src={legacySrc(mode)} title={`Halo Studio ${mode}`} data-testid="legacy-frame" />;
}

const BLURB: Record<LegacyMode, string> = {
  roles: "Lineups and agent bios as an editable graph.",
  org: "Your company in Paperclip: agents, reporting lines, issues.",
  design: "Prototypes, pages and decks on your own apps.",
};

/** One full-size panel holding the legacy page in `mode`. */
export function legacyPanels(mode: LegacyMode, title: string): PanelSpec[] {
  return [
    {
      id: "canvas",
      title,
      ...HELP[`${mode}-canvas`],
      x: 0,
      y: 0,
      w: 24,
      h: 0,
      minW: 8,
      minH: 24,
      face: "detail",
      keepAlive: true,
      glance: () => (
        <div className="glance">
          <div className="glance-kicker mono">{mode.toUpperCase()}</div>
          <div className="glance-text">{BLURB[mode]}</div>
          <div className="glance-hint">Expand (or double-click the title bar) to open it.</div>
        </div>
      ),
      detail: () => <LegacyFrame mode={mode} />,
      settings: () => (
        <p className="muted">
          This page is the classic Studio {mode} view, framed. Open it on its own (with its full header) at{" "}
          <a href={legacySrc(mode, false)} target="_blank" rel="noreferrer">
            /legacy/
          </a>
          .
        </p>
      ),
    },
  ];
}
