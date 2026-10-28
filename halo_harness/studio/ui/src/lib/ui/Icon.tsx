// A handful of 16 px stroke icons drawn inline (no icon font, no fetch).
const PATHS: Record<string, string> = {
  gear: "M8 6a2 2 0 1 0 0 4 2 2 0 0 0 0-4ZM6.8 1.8h2.4l.4 1.6 1.4.8 1.6-.5 1.2 2.1-1.2 1.1v1.6l1.2 1.1-1.2 2.1-1.6-.5-1.4.8-.4 1.6H6.8l-.4-1.6-1.4-.8-1.6.5-1.2-2.1 1.2-1.1V7.2L2.2 6.1l1.2-2.1 1.6.5 1.4-.8Z",
  "chevron-down": "M4 6l4 4 4-4",
  "chevron-right": "M6 4l4 4-4 4",
  popout: "M9 3h4v4M13 3 8 8M7 4H4v8h8V9",
  dock: "M3 3h10v10H3zM3 9h10",
  expand: "M3 7V3h4M13 9v4H9M3 3l4 4M13 13 9 9",
  shrink: "M7 3v4H3M9 13V9h4M3 3l4 4M13 13 9 9",
  close: "M4 4l8 8M12 4l-8 8",
  search: "M7 3a4 4 0 1 1 0 8 4 4 0 0 1 0-8Zm3 7 3 3",
  sun: "M8 5a3 3 0 1 1 0 6 3 3 0 0 1 0-6ZM8 1v2M8 13v2M1 8h2M13 8h2M3 3l1.4 1.4M11.6 11.6 13 13M3 13l1.4-1.4M11.6 4.4 13 3",
  moon: "M12.5 9.5A5 5 0 0 1 6.5 3.5a5 5 0 1 0 6 6Z",
  auto: "M8 2a6 6 0 1 1 0 12A6 6 0 0 1 8 2Zm0 0v12",
  rail: "M3 3h10v10H3zM6.5 3v10",
  plus: "M8 3v10M3 8h10",
  reset: "M3 8a5 5 0 1 0 1.5-3.5M3 3v2.5h2.5",
  pulse: "M1 8h3l2-4 3 8 2-4h4",
  grid: "M3 3h4v4H3zM9 3h4v4H9zM3 9h4v4H3zM9 9h4v4H9z",
  density: "M2 4h12M2 8h12M2 12h12", // 3.3.2.0 R3: the density toggle (three rows)
  "density-compact": "M2 3.5h12M2 6.5h12M2 9.5h12M2 12.5h12",
  more: "M3 7.2a.8.8 0 1 0 0 1.6.8.8 0 1 0 0-1.6ZM8 7.2a.8.8 0 1 0 0 1.6.8.8 0 1 0 0-1.6ZM13 7.2a.8.8 0 1 0 0 1.6.8.8 0 1 0 0-1.6Z",
  help: "M8 2a6 6 0 1 1 0 12A6 6 0 0 1 8 2ZM6.2 6.3a1.9 1.9 0 1 1 2.6 1.8c-.5.2-.8.6-.8 1.1v.5M8 11.3v.3",
  // 3.0.5.0 Fleet: the tool an agent runs, and the agent controls
  edit: "M3 13l1-3 7-7 2 2-7 7-3 1ZM10 4l2 2",
  terminal: "M2 3h12v10H2zM4.5 6.5 6.5 8l-2 1.5M8 10h3",
  file: "M4 2h5l3 3v9H4zM9 2v3h3",
  agent: "M8 2.5a2 2 0 1 1 0 4 2 2 0 0 1 0-4ZM3.5 13.5a4.5 4.5 0 0 1 9 0",
  globe: "M8 2a6 6 0 1 1 0 12A6 6 0 0 1 8 2ZM2 8h12M8 2c2 2 2 10 0 12M8 2c-2 2-2 10 0 12",
  pause: "M5.5 3.5v9M10.5 3.5v9",
  play: "M5 3.5v9l7-4.5z",
  stop: "M4 4h8v8H4z",
  pin: "M6 2h4l-.5 4 2.5 2.5H4L6.5 6 6 2ZM8 8.5V14",
  follow: "M8 2v8M4.5 6.5 8 10l3.5-3.5M3 13h10",
  send: "M2 8l12-5-5 12-2-5-5-2Z",
  diamond: "M8 2l6 6-6 6-6-6Z",
  link: "M6.5 9.5l3-3M5 8 3.5 9.5a2.1 2.1 0 0 0 3 3L8 11M11 8l1.5-1.5a2.1 2.1 0 0 0-3-3L8 5",
  // 3.3.2.0 R1: one per core section for the icon rail (shell/RailSections.tsx), the chevron and Focus
  session: "M2.5 3h11v7.5h-6L4.5 13v-2.5h-2Z",
  team: "M5.5 3a1.8 1.8 0 1 1 0 3.6 1.8 1.8 0 0 1 0-3.6ZM1.8 12.5a3.7 3.7 0 0 1 7.4 0M11 4a1.6 1.6 0 1 1 0 3.2A1.6 1.6 0 0 1 11 4ZM10.2 8.7a3.2 3.2 0 0 1 4 3.3",
  roles: "M6 2h4v3H6zM2 11h4v3H2zM10 11h4v3h-4zM8 5v3M4 11V8h8v3",
  fleet: "M8 2a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3ZM3 10.5a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3ZM13 10.5a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3ZM7.2 4.8 3.8 10.7M8.8 4.8l3.4 5.9M4.5 12h7",
  design: "M2 14l1.2-3.8L10.6 2.8l2.6 2.6-7.4 7.4L2 14ZM9.2 4.2l2.6 2.6",
  orchestra: "M2 4h12M2 8h12M2 12h12M5 2.5v3M10.5 6.5v3M7 10.5v3",
  packs: "M2.5 5 8 2l5.5 3v6L8 14l-5.5-3ZM2.5 5 8 8l5.5-3M8 8v6",
  setup: "M4 2v12M8 2v12M12 2v12M2.5 5h3M6.5 10h3M10.5 6.5h3",
  settings: "M2.5 4h6M11.5 4h2M2.5 8h2M7.5 8h6M2.5 12h7M12.5 12h1M10 2.5v3M6 6.5v3M11 10.5v3", // 3.3.3.0 R2: rows with their knobs
  "chevron-left": "M10 4 6 8l4 4",
  focus: "M2 6V2h4M10 2h4v4M14 10v4h-4M6 14H2v-4",
  eye: "M1.5 8S4 3.5 8 3.5 14.5 8 14.5 8 12 12.5 8 12.5 1.5 8 1.5 8ZM8 6.2a1.8 1.8 0 1 1 0 3.6 1.8 1.8 0 0 1 0-3.6Z", // 3.3.4.0 R5: a vision model
  copy: "M5.5 5.5h7v7h-7zM3.5 10.5v-7h7", // 3.3.4.0 R5: the Ollama panel's Copy line
};

/** The icon for a tool an agent runs (Edit, Bash, Read, Agent, WebFetch ...). */
export function toolIcon(tool: string): string {
  if (/^(Edit|Write|MultiEdit|NotebookEdit|ApplyPatch)/.test(tool)) return "edit";
  if (/^(Bash|PowerShell|Shell|Monitor)/.test(tool)) return "terminal";
  if (/^(Read|Glob|LS|NotebookRead)/.test(tool)) return "file";
  if (/^(Grep|Search|ToolSearch)/.test(tool)) return "search";
  if (/^(Agent|Task|SendMessage)/.test(tool)) return "agent";
  if (/^Web/.test(tool)) return "globe";
  return tool ? "pulse" : "";
}

export type IconName = keyof typeof PATHS;

export function Icon({ name, size = 16, label }: { name: string; size?: number; label?: string }) {
  return (
    <svg
      className="icon"
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
    >
      <path d={PATHS[name] || PATHS.grid} />
    </svg>
  );
}
