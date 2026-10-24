// The packs registry's shapes (3.2.0.0 R3): `GET pack/registry`, built by the
// server from the packs that run here (halo_harness/packs/studio_registry.py).
// Every id is qualified `<pack id>--<id>`; titles are the pack's own words.
import type { CoreSectionId, PackSectionId } from "../../lib/store";

export type PanelKind = "markdown" | "table" | "form" | "links" | "events" | "bundle" | "artifact"; // artifact: 3.2.0.0 R5
export type Route = { section: string; panel?: string };
export type PackLink = { label: string; route?: Route; url?: string };

export type PackPanel = {
  id: string;
  name: string;
  pack: string;
  /** The section it sits in: a core one, or the pack's own. */
  section: string;
  title: string;
  kind: PanelKind;
  w: number;
  h: number;
  help: string;
  /** The source line in the title bar: "from pack <id>". */
  about: string;
  /** In a core section it starts as a strip. */
  collapsed: boolean;
  source?: string;
  /** The api path of its source (markdown, table, a granted bundle). */
  file?: string;
  columns?: string[];
  links?: PackLink[];
  /** An artifact panel (3.2.0.0 R5): its schema and that schema's view hint. */
  schema?: string;
  view?: string;
  /** A bundle: whether you granted studio-script, and the command that does. */
  script?: "granted" | "not granted";
  grant?: string;
};

export type PackSection = { id: PackSectionId; name: string; pack: string; title: string; blurb: string; help: string; panels: PackPanel[] };
export type PaletteEntry = { id: string; label: string; group: string; action: { kind: "route" | "url" | "none"; section?: string; panel?: string; url?: string } };
export type EventLine = { label: string; line: string; view?: string }; // view: the kind schema's hint (3.2.0.0 R5)
export type AttnKind = { label: string; keys: Record<string, string> };

export type PackEntry = {
  id: string;
  name: string;
  version: string;
  scope: string;
  script: "granted" | "not granted" | "none";
  grant: string;
  sections: PackSection[];
  panels: (PackPanel & { section: CoreSectionId })[];
  palette: PaletteEntry[];
  config_form: boolean;
  events: Record<string, EventLine>;
  attention: Record<string, AttnKind>;
};

/** boot (3.2.1.0 R1): the served page's sections only (`data-pack-sections`), before `GET pack/registry` answers. */
export type Registry = { version: number; core: string[]; packs: PackEntry[]; boot?: boolean };

/** A `pack_event` frame's data (halo_harness/ext/events.py publish_event). */
/** 3.2.0.0 R5: `problems` when the data does not match the kind's schema (published all the same). */
export type PackFrame = { pack: string; kind: string; data: unknown; ts: number; n: number; problems?: string[] };
