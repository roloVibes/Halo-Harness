// The library (3.3.16.0 R3; 3.3.16.3 three kinds): a side panel, closed on load, opened by `+ Library` on Agents' bar (on
// Cast and on Workflows) or the board's Library button (`/` opens it and focuses the search). One search box, then three
// kinds under headings: Workflows (yours / packs / shipped: whole use cases), Blocks you can start from (the shipped block
// templates: a square or a tier, every agent on auto) and Agents (the bios). A row is dragged with the pointer: a workflow
// or a template onto the canvas (or the board) raises its confirm card; a bio goes into a block (a square or a tier).
import { useEffect, useMemo, type DragEvent, type PointerEvent, type ReactNode } from "react";
import { Button, Icon } from "../../../lib/ui";
import { roles, useRoles } from "../../roles/store";
import { loadLists } from "../../roles/sync";
import { closeLibrary, libraryRows, toggleLibrary, useWf, wf, type Square } from "./store";
import { useHover } from "../../../lib/hover/useHover";
import { SquareHover } from "../hover/square";
import { startDrag } from "../blocks/drag";
import { dropTo } from "../blocks/dropTo";
import { loadTemplates, useTemplates, type Template } from "../blocks/templates";

export const DRAG_TYPE = "text/x-halo-square";
const GROUPS: ["yours" | "packs" | "shipped", string, string][] = [
  ["yours", "Yours", "none yet: halo workflows new <name> --from media copies a shipped one here"],
  ["packs", "Packs", "no running pack ships one"],
  ["shipped", "Shipped", "none"],
];

export function LibraryButton({ plus = false }: { plus?: boolean }) {
  const open = useWf((s) => s.library);
  if (plus)
    return (
      <Button size="sm" variant="ghost" icon={<Icon name="plus" size={14} />} onClick={toggleLibrary} aria-pressed={open}
              data-testid="wf-library-plus" title="The library: workflows, blocks to start from and agents, to drag onto the canvas (/ searches it)">
        Library
      </Button>
    );
  return (
    <Button size="sm" onClick={() => wf.update(() => ({ library: true }))} data-testid="wf-library-open"
            title="Open the library: drag a square from it onto the board">
      Library
    </Button>
  );
}

function Row({ sq, on }: { sq: Square; on: boolean }) {
  const hv = useHover("square", `library:${sq.ref}`, () => <SquareHover sqRef={sq.ref} row />); // 3.3.16.1: the row's hover card
  const t = hv.titles;
  const start = (e: DragEvent<HTMLLIElement>) => {
    e.dataTransfer.setData(DRAG_TYPE, sq.ref);
    e.dataTransfer.setData("text/plain", sq.ref);
    e.dataTransfer.effectAllowed = "copy";
  };
  const down = (e: PointerEvent<HTMLLIElement>) => (hv.props.onPointerDown?.(e), sq.square && startDrag(e, { kind: "workflow", ref: sq.ref }, sq.ref, dropTo({ kind: "workflow", ref: sq.ref })));
  return (
    <li className="wf-row" onDragStart={start} data-density="row" data-testid="wf-row" data-ref={sq.ref}
        data-on={on || undefined} data-square={sq.square || undefined} {...hv.props} onPointerDown={down}
        title={t ? (sq.square ? `Drag ${sq.ref} onto the canvas or the board to add it to this lineup` : `${sq.ref} is not a square: its file says no gives`) : undefined}>
      <span className="wf-row-name mono">{sq.ref}{on ? " · on" : ""}</span>
      <span className="wf-row-does" title={t ? sq.does : undefined}>{sq.square ? sq.does || "-" : "not a square (no gives): it runs as a workflow, the router never picks it"}</span>
    </li>
  );
}

function TemplateRow({ t }: { t: Template }) {
  const down = (e: PointerEvent<HTMLLIElement>) => startDrag(e, { kind: "template", name: t.name }, t.title, dropTo({ kind: "template", name: t.name }));
  return (
    <li className="wf-row lib-row" data-density="row" data-testid="lib-template" data-name={t.name} data-kind={t.kind} data-square onPointerDown={down}
        title={`Drag onto the canvas: ${t.kind === "square" ? "a new square of yours" : "a new tier in this lineup"}, every agent on auto`}>
      <span className="wf-row-name mono">{t.title}</span>
      <span className="wf-row-does">{t.kind} · {t.agents.map((a) => a.bio).join(", ")}</span>
    </li>
  );
}

function BioRow({ name, does, kind }: { name: string; does: string; kind: string }) {
  const down = (e: PointerEvent<HTMLLIElement>) => startDrag(e, { kind: "bio", bio: name }, name, dropTo({ kind: "bio", bio: name }));
  return (
    <li className="wf-row lib-row" data-density="row" data-testid="lib-bio" data-bio={name} data-square onPointerDown={down}
        title={`Drag ${name} into a block: a square's agents or a tier`}>
      <span className="wf-row-name mono">{name}<span className="muted"> · {kind || "agent"}</span></span>
      <span className="wf-row-does">{does || "-"}</span>
    </li>
  );
}

function Kind({ id, title, count, children }: { id: string; title: string; count: number; children: ReactNode }) {
  return (
    <section className="lib-kind" data-testid={`lib-kind-${id}`} data-kind={id}>
      <h2 className="lib-kind-title">{title} <span className="muted mono">{count}</span></h2>
      {children}
    </section>
  );
}

export function Library() {
  const open = useWf((s) => s.library);
  const query = useWf((s) => s.query);
  const board = useWf((s) => s.board);
  const temps = useTemplates();
  const bios = useRoles((s) => s.bios);
  useEffect(() => {
    if (!open) return;
    void loadTemplates();
    if (!roles.get().bios.length) void loadLists(); // the Agents kind: the bios (W may open before Cast ever read them)
  }, [open]);
  const rows = useMemo(() => libraryRows({ ...wf.get(), board, query }), [board, query]);
  const q = query.trim().toLowerCase();
  const hit = (...xs: string[]) => !q || xs.join(" ").toLowerCase().includes(q);
  const ts = temps.filter((t) => hit(t.name, t.title, t.does, t.agents.map((a) => a.bio).join(" ")));
  const bs = bios.filter((b) => hit(b.name, b.description, b.kind));
  const on = board?.enabled || [];
  if (!open) return null;
  const nWf = rows.yours.length + rows.packs.length + rows.shipped.length;
  return (
    <aside className="wf-library" data-testid="wf-library" aria-label="The library: workflows, blocks to start from, agents">
      <div className="wf-library-head" data-density="bar">
        <b className="wf-library-title">Library</b>
        <span className="spacer" />
        <button className="icon-btn" onClick={closeLibrary} aria-label="Close the library" data-testid="wf-library-close">×</button>
      </div>
      <input className="wf-search" type="search" value={query} placeholder="Search workflows, blocks, agents" aria-label="Search the library"
             onChange={(e) => wf.update(() => ({ query: e.target.value }))} data-testid="wf-search"
             onKeyDown={(e) => e.key === "Escape" && (e.currentTarget.blur(), closeLibrary())} />
      <div className="wf-groups">
        <Kind id="workflows" title="Workflows" count={nWf}>
          {GROUPS.map(([g, title, none]) => (
            <section key={g} className="wf-group" data-testid={`wf-group-${g}`} data-group={g}>
              <h3 className="wf-group-title mono">{title} <span className="muted">{rows[g].length}</span></h3>
              {rows[g].length ? (
                <ul className="wf-rows">{rows[g].map((sq) => <Row key={sq.ref} sq={sq} on={on.includes(sq.ref)} />)}</ul>
              ) : (
                <p className="muted wf-none">{query ? "nothing matches" : none}</p>
              )}
            </section>
          ))}
        </Kind>
        <Kind id="templates" title="Blocks you can start from" count={ts.length}>
          {ts.length ? <ul className="wf-rows">{ts.map((t) => <TemplateRow key={t.name} t={t} />)}</ul> : <p className="muted wf-none">{q ? "nothing matches" : "none shipped"}</p>}
        </Kind>
        <Kind id="agents" title="Agents" count={bs.length}>
          {bs.length ? <ul className="wf-rows">{bs.map((b) => <BioRow key={b.name} name={b.name} does={b.description} kind={b.kind} />)}</ul>
            : <p className="muted wf-none">{q ? "nothing matches" : "no bios yet (Agents -> Cast: Bios)"}</p>}
        </Kind>
      </div>
    </aside>
  );
}
