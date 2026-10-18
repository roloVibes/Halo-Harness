// The top bar: brand, the seven section tabs (a tab "works" while its section
// has fresh activity), the ? menu ("How this works" for the section and,
// from 3.1.1.0 R1, the Glossary), the command palette button and the theme
// menu.
import { useEffect, useRef, useState } from "react";
import { Button, Icon, Kbd, Tabs, type TabItem } from "../lib/ui";
import { goSection, openHelp, setTheme, studio, toggleRail, useStore, type SectionId, type ThemeChoice } from "../lib/store";
import { openGlossary } from "../lib/glossary";
import { useRecent } from "../lib/motion";
import { SECTIONS, sectionDef } from "../routes";

function useSectionTabs(current: SectionId): TabItem[] {
  const activity = useStore(studio, (s) => s.activity);
  const orchestraBusy = useRecent(activity.orchestra, 3000);
  const flowBusy = useRecent(activity.flow, 3000);
  const fleetBusy = useRecent(activity.fleet, 3000);
  const teamBusy = useRecent(activity.team, 3000);
  const busy: Record<SectionId, boolean> = { orchestra: orchestraBusy, roles: false, org: false, design: false, flow: flowBusy, fleet: fleetBusy, team: teamBusy };
  return SECTIONS.map((s) => ({
    id: s.id,
    label: s.title,
    kbd: s.kbd,
    testid: "section-tab",
    title: `${s.blurb} (${s.kbd})`,
    motion: busy[s.id] && s.id !== current ? "working" : "none",
  }));
}

const THEMES: { id: ThemeChoice; label: string; icon: string }[] = [
  { id: "dark", label: "Dark (holo)", icon: "moon" },
  { id: "light", label: "Light", icon: "sun" },
  { id: "auto", label: "Follow the system", icon: "auto" },
];

/** A menu's open state: closes on Esc and on a press outside its box. */
function useMenu() {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const off = (e: Event) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !box.current?.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener("pointerdown", off);
    window.addEventListener("keydown", off);
    return () => {
      window.removeEventListener("pointerdown", off);
      window.removeEventListener("keydown", off);
    };
  }, [open]);
  return { open, setOpen, box };
}

function HelpMenu({ section }: { section: SectionId }) {
  const { open, setOpen, box } = useMenu();
  const title = sectionDef(section).title;
  return (
    <div className="menu-wrap section-help-wrap" ref={box}>
      <button
        className="icon-btn icon-btn-lg section-help-btn"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        title={`Help: how ${title} works, the glossary (?)`}
        aria-label="Help"
        data-testid="section-help-btn"
      >
        <Icon name="help" />
      </button>
      {open && (
        <div className="menu menu-left glass" role="menu" aria-label="Help" data-testid="help-menu">
          <button role="menuitem" className="menu-item" data-testid="section-help-item" onClick={() => (setOpen(false), openHelp(section))}>
            <Icon name="help" />
            <span>How {title} works</span>
            <Kbd keys="?" />
          </button>
          <button role="menuitem" className="menu-item" data-testid="glossary-item" onClick={() => (setOpen(false), openGlossary())}>
            <Icon name="file" />
            <span>Glossary</span>
          </button>
        </div>
      )}
    </div>
  );
}

function ThemeMenu() {
  const theme = useStore(studio, (s) => s.theme);
  const { open, setOpen, box } = useMenu();
  const cur = THEMES.find((t) => t.id === theme) ?? THEMES[0];
  return (
    <div className="menu-wrap" ref={box}>
      <button className="icon-btn icon-btn-lg" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen(!open)} title={`Theme: ${cur.label}`} aria-label="Theme">
        <Icon name={cur.icon} />
      </button>
      {open && (
        <div className="menu glass" role="menu" aria-label="Theme">
          {THEMES.map((t) => (
            <button
              key={t.id}
              role="menuitemradio"
              aria-checked={t.id === theme}
              className={"menu-item" + (t.id === theme ? " on" : "")}
              onClick={() => {
                setTheme(t.id);
                setOpen(false);
              }}
            >
              <Icon name={t.icon} />
              <span>{t.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function Header() {
  const section = useStore(studio, (s) => s.section);
  const tabs = useSectionTabs(section);
  return (
    <header className="topbar">
      <button className="icon-btn icon-btn-lg" onClick={toggleRail} title="Show or hide the rail" aria-label="Toggle rail">
        <Icon name="rail" />
      </button>
      <div className="brand" title="Halo Studio">
        <span className="brand-ring" aria-hidden="true" />
        <span className="brand-name">HALO</span>
        <span className="brand-sub mono">STUDIO</span>
      </div>
      <Tabs label="Sections" items={tabs} value={section} onChange={(id) => goSection(id as SectionId)} />
      <HelpMenu section={section} />
      <div className="spacer" />
      <Button variant="ghost" className="palette-btn" onClick={() => studio.update(() => ({ paletteOpen: true }))} icon={<Icon name="search" />}>
        <span className="palette-btn-text">Command</span>
        <Kbd keys="Mod+K" />
      </Button>
      <ThemeMenu />
    </header>
  );
}
