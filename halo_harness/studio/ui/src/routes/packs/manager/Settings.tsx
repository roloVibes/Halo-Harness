// pm-settings (3.2.0.0 R6): the selected pack's settings, R3's form (PackForm)
// over `pack/<id>/settings` -- one field per key of its config.schema, Save
// checks the values against the schema and writes packs.settings.<id> in
// ~/.halo/config.json. It works for a disabled pack too (set it up, then
// enable it); a pack not installed yet has none to set.
import { Empty } from "../../../lib/ui";
import { PackForm } from "../PackForm";
import type { PackPanel } from "../types";
import { selected, useMgr } from "./store";

function panelOf(id: string): PackPanel {
  return { id: "pm-settings", name: "settings", pack: id, section: "packs", title: "Settings", kind: "form", w: 8, h: 24, help: "", about: "", collapsed: false };
}

export function SettingsDetail() {
  const p = useMgr((s) => selected(s));
  if (!p) return <Empty title="Pick a pack" body="Its settings show here: each key of its config.schema." />;
  if (!p.installed) return <Empty title="Install it first" body={`${p.name}'s settings are kept in packs.settings.${p.id} once it is installed.`} />;
  if (!p.has_settings) return <Empty title="Nothing to set" body={`${p.name} declares no config.schema in its pack.yaml.`} testid="pm-settings-none" />;
  return (
    <div data-testid="pm-settings-body" data-id={p.id}>
      <PackForm key={p.id} p={panelOf(p.id)} path={`pack/${p.id}/settings`} />
    </div>
  );
}

export function SettingsGlance() {
  const p = useMgr((s) => selected(s));
  const n = p ? Object.keys(p.settings || {}).length : 0;
  return (
    <div className="glance">
      <div className="glance-kicker mono">SETTINGS</div>
      <div className="glance-text">{p ? `${n} setting${n === 1 ? "" : "s"}` : "no pack picked"}</div>
      <div className="glance-hint">{p ? `packs.settings.${p.id}` : "pick one in Installed"}</div>
    </div>
  );
}
