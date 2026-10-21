// The Lineups and Bios panels' groups by source (3.2.0.0 R2): "yours",
// "project", one "pack <id>" per pack that runs here, "shipped", in that
// order, each a labeled group box (the owner's clarity rule), collapsed when
// empty. A disabled pack has no group (GET state lists the packs that run).
// A pack's group also lists the names of it a file of yours shadows, with
// the file that wins.
import type { ReactNode } from "react";
import { packOf } from "./store";
import type { PackFields, PackInfo } from "./types";

type Row = { name: string; scope: string; shipped_copy?: boolean } & PackFields;
export type Group<T extends Row> = { key: string; label: string; hint: string; pack: string; rows: T[]; shadowed: T[] };

/** The groups in their order; a row lands in exactly one. */
export function groupBySource<T extends Row>(rows: T[], packs: PackInfo[] | undefined): Group<T>[] {
  const ids = (packs || []).map((p) => p.id);
  for (const r of rows) if (packOf(r.scope) && !ids.includes(packOf(r.scope))) ids.push(packOf(r.scope));
  const version = (id: string) => (packs || []).find((p) => p.id === id)?.version || "";
  const g = (key: string, label: string, hint: string, pack = ""): Group<T> => ({ key, label, hint, pack, rows: [], shadowed: [] });
  const yours = g("yours", "yours", "~/.halo: yours to edit");
  const project = g("project", "project", "this repo's .halo/");
  const byPack = ids.map((id) => g(`pack:${id}`, `pack ${id}`, `${version(id) ? version(id) + " · " : ""}read-only: Clone or Customize makes your copy`, id));
  const shipped = g("shipped", "shipped", "ships with Halo: read-only");
  for (const r of rows) {
    const pack = packOf(r.scope);
    if (pack) byPack.find((x) => x.pack === pack)?.rows.push(r);
    else if (r.scope === "template" || r.shipped_copy) shipped.rows.push(r);
    else if (r.scope === "project") project.rows.push(r);
    else yours.rows.push(r);
    if (r.shadows) byPack.find((x) => x.pack === r.shadows)?.shadowed.push(r);
  }
  return [yours, project, ...byPack, shipped];
}

export function SourceBox<T extends Row>({ group, what, children }: { group: Group<T>; what: string; children: ReactNode }) {
  const n = group.rows.length;
  return (
    <details className="rsg" open={n > 0 || group.shadowed.length > 0} data-group={group.key} data-empty={n ? undefined : ""} data-testid="roles-group">
      <summary className="rsg-head" title={group.hint}>
        <span className="rail-label mono rsg-label">{group.label.toUpperCase()}</span>
        <span className="mono muted rsg-count">{n ? `${n} ${what}${n === 1 ? "" : "s"}` : "none"}</span>
        <span className="muted rsg-hint">{group.hint}</span>
      </summary>
      {children}
      {group.shadowed.map((r) => (
        <p key={"sh-" + r.name} className="rsg-shadowed mono muted" data-testid="roles-shadowed" data-name={r.name}>
          {r.name}: shadowed by {r.shadowed_by || "your file"} (yours is the one used)
        </p>
      ))}
    </details>
  );
}
