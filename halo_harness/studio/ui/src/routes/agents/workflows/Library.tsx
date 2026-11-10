// The library (3.3.16.0 R3): a side panel, closed on load, opened by `+` on Agents' bar or the board's Library button
// (`/` opens it and focuses the search). A search box, then three groups -- yours (yours and the project's), packs,
// shipped -- one row per square with its DOES line. Dragging a row onto the board raises the confirm card (Board.tsx);
// dropping is the only way a square gets on the board.
import { useMemo, type DragEvent } from "react";
import { Button, Icon } from "../../../lib/ui";
import { closeLibrary, libraryRows, toggleLibrary, useWf, wf, type Square } from "./store";

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
              data-testid="wf-library-plus" title="The library: every square, to drag onto the board (/ searches it)">
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
  const start = (e: DragEvent<HTMLLIElement>) => {
    e.dataTransfer.setData(DRAG_TYPE, sq.ref);
    e.dataTransfer.setData("text/plain", sq.ref);
    e.dataTransfer.effectAllowed = "copy";
  };
  return (
    <li className="wf-row" draggable={sq.square} onDragStart={start} data-density="row" data-testid="wf-row" data-ref={sq.ref}
        data-on={on || undefined} data-square={sq.square || undefined}
        title={sq.square ? `Drag ${sq.ref} onto the board to enable it for this lineup` : `${sq.ref} is not a square: its file says no gives`}>
      <span className="wf-row-name mono">{sq.ref}{on ? " · on" : ""}</span>
      <span className="wf-row-does" title={sq.does}>{sq.square ? sq.does || "-" : "not a square (no gives): it runs as a workflow, the router never picks it"}</span>
    </li>
  );
}

export function Library() {
  const open = useWf((s) => s.library);
  const query = useWf((s) => s.query);
  const board = useWf((s) => s.board);
  const rows = useMemo(() => libraryRows({ ...wf.get(), board, query }), [board, query]);
  const on = board?.enabled || [];
  if (!open) return null;
  return (
    <aside className="wf-library" data-testid="wf-library" aria-label="The library of squares">
      <div className="wf-library-head" data-density="bar">
        <b className="wf-library-title">Library</b>
        <span className="spacer" />
        <button className="icon-btn" onClick={closeLibrary} aria-label="Close the library" data-testid="wf-library-close">×</button>
      </div>
      <input className="wf-search" type="search" value={query} placeholder="Search squares" aria-label="Search the library"
             onChange={(e) => wf.update(() => ({ query: e.target.value }))} data-testid="wf-search"
             onKeyDown={(e) => e.key === "Escape" && (e.currentTarget.blur(), closeLibrary())} />
      <div className="wf-groups">
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
      </div>
    </aside>
  );
}
