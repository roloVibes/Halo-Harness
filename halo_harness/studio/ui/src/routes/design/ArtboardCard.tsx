// One artboard card on the Design canvas (3.0.7.0 R3): the title bar drags
// it; the frame shows the artboard (a prototype in a sandboxed iframe with
// scripts only, a render as an image, a video, else a link), its open
// comment pins; under it the version slider with Restore, then Critique,
// Contrast, Rename, Delete and Download. Memoised: a poll that changed one
// artboard redraws that card only.
import { memo, type PointerEvent } from "react";
import { Button } from "../../lib/ui";
import { contrast, critique, restore } from "./actions";
import { design, fileUrl, openDialog } from "./store";
import type { Artboard, Comment } from "./types";

export const CARD_W = 380;
const FRAME_W = 356;
const DEVICE = { w: 1280, h: 800 };

type Props = {
  a: Artboard;
  slug: string;
  x: number;
  y: number;
  shown: number;
  bust: number;
  pins: Comment[];
  selected: boolean;
  dragging: boolean;
  running: boolean;
  onDown: (ev: PointerEvent<HTMLElement>, id: string) => void;
};

function Frame({ a, slug, n, bust }: { a: Artboard; slug: string; n: number; bust: number }) {
  if (!a.render) return <div className="da-nofile muted">no preview yet</div>;
  const src = fileUrl(slug, a.id, a.render, n === a.latest ? 0 : n, bust);
  if (a.render === "index.html") {
    const s = FRAME_W / DEVICE.w;
    return (
      <div className="da-scaler" style={{ width: FRAME_W, height: DEVICE.h * s }}>
        <iframe sandbox="allow-scripts" title={`${a.title || a.id} prototype`} src={src} style={{ width: DEVICE.w, height: DEVICE.h, transform: `scale(${s})` }} />
      </div>
    );
  }
  if (/\.(png|svg)$/.test(a.render)) return <img className="da-img" src={src} alt={`${a.title || a.id} render`} draggable={false} />;
  if (a.render.endsWith(".mp4")) return <video className="da-img" src={src} controls muted />;
  return (
    <a className="da-link" href={src} target="_blank" rel="noopener noreferrer">
      <b>{a.render}</b> <span className="muted">open it in a new tab</span>
    </a>
  );
}

export const ArtboardCard = memo(function ArtboardCard({ a, slug, x, y, shown, bust, pins, selected, dragging, running, onDown }: Props) {
  const vs = [...a.versions].sort((p, q) => p - q);
  const n = shown || a.latest;
  const idx = Math.max(0, vs.indexOf(n));
  const old = n !== a.latest && a.latest > 0;
  const file = a.render ? fileUrl(slug, a.id, a.render, old ? n : 0) : "";
  return (
    <article className="da-card" style={{ left: x, top: y, width: CARD_W }} data-testid="design-artboard" data-id={a.id}
             data-selected={selected || undefined} data-dragging={dragging || undefined} onPointerDown={() => design.update((s) => (s.sel === a.id ? {} : { sel: a.id }))}>
      <header className="da-title" onPointerDown={(ev) => onDown(ev, a.id)} title="Drag to move">
        <b>{a.title || a.id}</b>
        <span className="og-chip mono">{a.kind}</span>
        {a.app && <span className="og-chip mono" data-app>{a.app}</span>}
        <span className="spacer" />
        <span className="mono muted">v{n || "-"}</span>
      </header>
      <div className="da-frame">
        <Frame a={a} slug={slug} n={n} bust={bust} />
        {pins.map((c, i) => (
          <span key={c.id} className="da-pin" data-crit={c.source === "critique" || undefined} style={{ left: `${c.x}%`, top: `${c.y}%` }} title={c.text} data-testid="design-pin">{i + 1}</span>
        ))}
      </div>
      <footer className="da-foot">
        {vs.length > 1 ? (
          <div className="da-versions">
            <input type="range" min={0} max={vs.length - 1} value={idx} aria-label={`Version of ${a.id}`}
                   onChange={(e) => design.update((s) => ({ view: { ...s.view, [a.id]: vs[Number(e.target.value)] } }))} />
            <span className="mono muted">{old ? `v${n} of ${a.latest}` : `v${n} (current)`}</span>
            {old && <Button size="sm" variant="ghost" disabled={running} onClick={() => void restore(a.id, n)}>Restore</Button>}
          </div>
        ) : (
          <span className="mono muted">{vs.length ? `v${vs[0]} (current)` : "no versions yet"}</span>
        )}
        <div className="da-actions">
          <Button size="sm" variant="ghost" disabled={running} onClick={() => void critique(a.id)} title="A second model reads it and pins its notes">Critique</Button>
          <Button size="sm" variant="ghost" onClick={() => void contrast(a.id)} title="WCAG contrast of its text">Contrast</Button>
          <Button size="sm" variant="ghost" onClick={() => openDialog({ kind: "rename", aid: a.id })} data-testid="design-rename">Rename</Button>
          <Button size="sm" variant="ghost" disabled={running} onClick={() => openDialog({ kind: "delete", aid: a.id })} data-testid="design-delete">Delete</Button>
          {file && <a className="btn btn-ghost btn-sm" href={file} download={`${a.id}-v${n}-${a.render}`}><span className="btn-label">Download</span></a>}
        </div>
      </footer>
    </article>
  );
});
