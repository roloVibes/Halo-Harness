// A panel's "..." menu: Float (or Dock), Compact / Expand (a panel with two faces), Collapse (or Open),
// Reset this panel, Settings (the Inspector) and Help (the ? popover). 3.3.2.0 R3: the header menus' own
// lib/ui/Menu.tsx (a portal, so a small panel never clips it; the arrows, Home, End, Enter, Esc), with the
// panel's small button and the list right-aligned under it.
import { Menu, type MenuRow } from "../ui/Menu";

export type MenuItem = { id: string; label: string; icon: string; kbd?: string; run: () => void };

export function PanelMenu({ title, items }: { title: string; items: MenuItem[] }) {
  const rows: MenuRow[] = items.map((it) => ({ id: it.id, label: it.label, icon: it.icon, kbd: it.kbd, run: it.run }));
  return (
    <Menu
      icon="more"
      label={`${title}: more`}
      title="More: float, compact, strip, reset, settings, help"
      testid="panel-menu-btn"
      menuTestid="panel-menu"
      groups={[{ rows }]}
      width={228}
      btnClass="icon-btn"
      menuClass="hdr-menu panel-menu"
      align="right"
    />
  );
}
