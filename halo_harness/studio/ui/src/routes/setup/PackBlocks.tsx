// A pack's own Setup page (3.3.11.0 R3, packSetup.ts; docs/STUDIO-setup.md "A pack's blocks"): one block of an
// enabled pack's `contributes.setup`, drawn by Setup's own parts. A form is the pack's settings form (PackForm, its
// fields only: Save writes packs.settings.<id> through the pack's config route and marks the block done); a check is
// its Check row (what it does, costs, takes and writes, then Run this check: the Check job runs it, its lines show
// here and on the Check page); a note is the pack's markdown with Mark as read. Every block has Skip. The state line
// says done, skipped or waiting. The Check page lists the pack checks under "From packs" (Check.tsx), unticked.
import { useEffect } from "react";
import { Markdown } from "../../lib/markdown";
import { Button } from "../../lib/ui";
import { PackForm } from "../packs/PackForm";
import { useLoadState, Waiting } from "./BlockFoot";
import { startCheck, useCheck } from "./checkStore";
import { blockOf, blockWord, postBlock, usePackAct, type Found } from "./packSetup";
import { usePage } from "./pages";
import { loadSetup, useSetup } from "./store";

function StateLine({ f }: { f: Found }) {
  const word = blockWord(f.block);
  const last = usePackAct((s) => s.last[f.block.key]);
  return (
    <>
      <div className="su-foot-row">
        <span className="su-word mono" data-testid="setup-pack-state" data-key={f.block.key} data-word={word}>
          {f.pack.name}: {word}
          {f.block.at ? ` (${f.block.at})` : ""}
        </span>
      </div>
      {last && last.lines.length > 0 && (
        <pre className="su-lines mono" data-ok={last.ok || undefined} data-testid="setup-pack-lines" data-key={f.block.key}>
          {last.lines.join("\n")}
        </pre>
      )}
    </>
  );
}

function Skip({ f }: { f: Found }) {
  const busy = usePackAct((s) => !!s.busy);
  if (f.block.state) return null;
  return (
    <Button size="sm" variant="ghost" disabled={busy} onClick={() => void postBlock(f.block.key, { skip: true })} data-testid="setup-pack-skip"
            data-key={f.block.key} title="Leave this block for now: it stops waiting; halo setup opens it again">
      Skip
    </Button>
  );
}

function FormBlock({ f }: { f: Found }) {
  return (
    <div data-testid="setup-pack-form" data-key={f.block.key}>
      <PackForm p={{ pack: f.pack.id }} path={`setup/packs/${f.pack.id}/${f.block.id}`} onSaved={() => void loadSetup()} />
      <div className="su-foot-row">
        <Skip f={f} />
      </div>
    </div>
  );
}

function CheckBlock({ f }: { f: Found }) {
  const frame = useCheck((s) => s.frames[f.block.key]);
  const running = useCheck((s) => s.running || s.busy);
  const busy = usePackAct((s) => !!s.busy);
  useEffect(() => void startCheck(), []);
  const b = f.block;
  return (
    <div className="su-check" data-testid="setup-pack-check" data-key={b.key} data-state={frame?.state || undefined}>
      <span className="su-check-detail muted" data-testid="setup-pack-check-detail">
        {b.what}. Cost: {b.cost}. Time: {b.time}. Writes: {b.writes}.
      </span>
      <div className="su-foot-row">
        <Button variant="primary" size="sm" disabled={busy || running} onClick={() => void postBlock(b.key)} data-testid="setup-pack-run" data-key={b.key}
                title="Runs the pack's command now, as one Check job; its lines show here and on the Check page">
          Run this check
        </Button>
        <Skip f={f} />
      </div>
      {frame && frame.lines.length > 0 && (
        <pre className="su-check-log mono" data-state={frame.state} data-testid="setup-pack-check-log" data-key={b.key}>
          {frame.lines.join("\n")}
        </pre>
      )}
    </div>
  );
}

function NoteBlock({ f }: { f: Found }) {
  const busy = usePackAct((s) => !!s.busy);
  return (
    <div data-testid="setup-pack-note" data-key={f.block.key}>
      <Markdown text={f.block.text || ""} className="su-pack-note" />
      <div className="su-foot-row">
        {f.block.state !== "done" && (
          <Button variant="primary" size="sm" disabled={busy} onClick={() => void postBlock(f.block.key)} data-testid="setup-pack-dismiss"
                  data-key={f.block.key} title="You read it: the block stops waiting">
            Mark as read
          </Button>
        )}
        <Skip f={f} />
      </div>
    </div>
  );
}

/** The open page's block (the page is a `pack:<id>:<block>` step). */
export function PackBlockPage() {
  const page = usePage();
  const { ready, error } = useLoadState();
  const d = useSetup((s) => s.data); // the state itself: a {pack, block} made per read would redraw forever
  const f = blockOf(d, page);
  if (!ready) return <Waiting error={error} />;
  if (!f)
    return (
      <p className="su-note muted" data-testid="setup-pack-gone">
        This block is not here: its pack is not enabled on this box (halo pack list).
      </p>
    );
  return (
    <div className="su-block" data-testid="setup-pack-block" data-key={f.block.key} data-kind={f.block.kind}>
      {f.block.kind === "form" && <FormBlock f={f} />}
      {f.block.kind === "check" && <CheckBlock f={f} />}
      {f.block.kind === "note" && <NoteBlock f={f} />}
      <StateLine f={f} />
    </div>
  );
}
