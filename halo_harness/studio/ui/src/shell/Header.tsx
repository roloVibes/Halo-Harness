// The top bar: brand, the current section's title and blurb (3.3.2.0 R1: the
// section tabs became the icon rail, shell/RailSections.tsx), the ? menu
// ("How this works" for the section and, from 3.1.1.0 R1, the Glossary),
// its "..." menu (Reset layout, How panels open; 3.6.0.0 R0a: the "+" menu, Arrange and the "custom layout" badge
// went -- every panel is a button in the view's bar, lib/workspace/ViewBar.tsx; shell/SectionMore.tsx), the Focus button (3.3.2.0 R1: hides
// the rail, the inspector and the status bar; F), the command palette button,
// 3.3.2.0 R3's density toggle (comfortable / compact, lib/density.ts) and the
// theme menu (3.3.12.0 R1: shell/ThemeMenu.tsx, the palettes of the registry). 3.3.15.0 L1: restyled to the
// Instrument look (styles/shell.css): the title in mono caps, a / and the blurb, the palette door a 300 px field.
import { Button, Icon, Kbd } from "../lib/ui";
import { openHelp, studio, toggleFocus, toggleRail, useStore, type SectionId } from "../lib/store";
import { openGlossary } from "../lib/glossary";
import { toggleDensity, useDensity } from "../lib/density";
import { sectionDef } from "../routes";
import { SectionMore } from "./SectionMore";
import { ThemeMenu } from "./ThemeMenu"; // 3.3.12.0 R1: the ten palettes, one `theme` key
import { useMenu } from "./useMenu";

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

/** 3.3.2.0 R3: comfortable / compact, beside the theme choice; remembered per browser (halo.studio.density). */
function DensityToggle() {
  const d = useDensity();
  const next = d === "compact" ? "comfortable" : "compact";
  return (
    <button className="icon-btn icon-btn-lg" onClick={toggleDensity} aria-pressed={d === "compact"} aria-label={`Density: ${d}`}
            title={`Density: ${d} (press for ${next})`} data-testid="density-toggle" data-density={d}>
      <Icon name={d === "compact" ? "density-compact" : "density"} />
    </button>
  );
}

export function Header() {
  const section = useStore(studio, (s) => s.section);
  const focus = useStore(studio, (s) => s.focus);
  const def = sectionDef(section);
  return (
    <header className="topbar" data-density="bar">
      <button className="icon-btn icon-btn-lg rail-menu-btn" onClick={toggleRail} aria-label="Sections" title="The sections (a menu on a narrow window)" data-testid="rail-menu-btn">
        <Icon name="rail" />
      </button>
      <div className="brand" title="Halo Studio">
        <span className="brand-ring" aria-hidden="true" />
        <span className="brand-name">HALO</span>
        <span className="brand-sub mono">STUDIO</span>
      </div>
      <div className="topbar-section" data-testid="section-title">
        <span className="topbar-title">{def.title}</span>
        <span className="topbar-blurb">{def.blurb}</span>
      </div>
      <HelpMenu section={section} />
      <div className="topbar-tools" data-testid="section-tools">
        <SectionMore />
      </div>
      <div className="spacer" />
      <button
        className="icon-btn icon-btn-lg"
        onClick={toggleFocus}
        aria-pressed={focus}
        aria-label="Focus"
        title="Focus: hide the rail, the inspector and the status bar (F)"
        data-testid="focus-toggle"
      >
        <Icon name="focus" />
      </button>
      <Button variant="ghost" className="palette-btn" onClick={() => studio.update(() => ({ paletteOpen: true }))} icon={<Icon name="search" />}>
        <span className="palette-btn-text">search or run a command</span>
        <Kbd keys="Mod+K" />
      </Button>
      <DensityToggle />
      <ThemeMenu />
    </header>
  );
}
