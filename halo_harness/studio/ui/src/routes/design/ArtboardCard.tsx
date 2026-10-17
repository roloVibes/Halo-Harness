// One artboard card on the Design canvas (3.0.7.0 R3): the title bar drags
// it; the frame shows the artboard (a prototype in a sandboxed iframe with
// scripts only, a render as an image, a video, else a link), its open
// comment pins; under it the version slider with Restore, then Critique,
// Contrast, Rename, Delete and Download. Memoised: a poll that changed one
// artboard redraws that card only. 3.0.7.0 R3b: a prototype draws at the
// panel's device size (phone / tablet / desktop); its current version is
// framed with the double-click text picker (`?edit=pick`); CardLayers.tsx
// draws the comment layer, the pins, the comment box and the text editor;
// Knobs opens the panel's settings on this artboard's knobs.
import { memo, type PointerEvent } from "react";
import { studio } from "../../lib/store";
import { Button } from "../../lib/ui";
import { contrast, critique, restore } from "./actions";
import { CardLayers } from "./CardLayers";
import { CARD_W, DEVICES, frameOf, type Device } from "./layout";
import { design, fileUrl, openDialog } from "./store";
import type { Artboard, Comment } from "./types";

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
  dev: Device;
  onDown: (ev: PointerEvent<HTMLElement>, id: string) => void;
};

function Frame({ a, slug, n, bust, dev }: { a: Artboard; slug: string; n: number; bust: number; dev: Device }) {
  if (!a.render) return <div className="da-nofile muted">no preview yet</div>;
  const current = n === a.latest;
  const src = fileUrl(slug, a.id, a.render, current ? 0 : n, bust);
  if (a.render === "index.html") {
    const d = DEVICES[dev];
    const f = frameOf(dev);
    const live = current ? src + (src.includes("?") ? "&" : "?") + "edit=pick" : src; // the current version: double-click a text to edit it
    return (
      <div className="da-scaler" style={{ width: f.w, height: f.h }}>
        <iframe sandbox="allow-scripts" title={`${a.title || a.id} prototype`} src={live} style={{ width: d.w, height: d.h, transform: `scale(${f.s})` }} />
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

function knobs(aid: string): void {
  design.update(() => ({ sel: aid }));
  studio.update(() => ({ inspector: { section: "design", panel: "design-artboards" } }));
}

export const ArtboardCard = memo(function ArtboardCard({ a, slug, x, y, shown, bust, pins, selected, dragging, running, dev, onDown }: Props) {
  const vs = [...a.versions].sort((p, q) => p - q);
  const n = shown || a.latest;
  const idx = Math.max(0, vs.indexOf(n));
  const old = n !== a.latest && a.latest > 0;
  const file = a.render ? fileUrl(slug, a.id, a.render, old ? n : 0) : "";
  const proto = a.render === "index.html";
  const f = frameOf(dev);
  return (
    <article className="da-card" style={{ left: x, top: y, width: CARD_W }} data-testid="design-artboard" data-id={a.id} data-device={proto ? dev : undefined}
             data-selected={selected || undefined} data-dragging={dragging || undefined} onPointerDown={() => design.update((s) => (s.sel === a.id ? {} : { sel: a.id }))}>
      <header className="da-title" onPointerDown={(ev) => onDown(ev, a.id)} title="Drag to move">
        <b>{a.title || a.id}</b>
        <span className="og-chip mono">{a.kind}</span>
        {a.app && <span className="og-chip mono" data-app>{a.app}</span>}
        <span className="spacer" />
        <span className="mono muted" data-testid="design-version">v{n || "-"}</span>
      </header>
      <div className="da-frame" style={proto ? { width: f.w, height: f.h } : undefined}>
        <Frame a={a} slug={slug} n={n} bust={bust} dev={dev} />
        <CardLayers aid={a.id} pins={pins} scale={f.s} />
      </div>
      <footer className="da-foot">
        {vs.length > 1 ? (
          <div className="da-versions">
            <input type="range" min={0} max={vs.length - 1} value={idx} aria-label={`Version of ${a.id}`}
                   onChange={(e) => design.update((s) => ({ view: { ...s.view, [a.id]: vs[Number(e.target.value)] }, editing: null }))} />
            <span className="mono muted">{old ? `v${n} of ${a.latest}` : `v${n} (current)`}</span>
            {old && <Button size="sm" variant="ghost" disabled={running} onClick={() => void restore(a.id, n)}>Restore</Button>}
          </div>
        ) : (
          <span className="mono muted">{vs.length ? `v${vs[0]} (current)` : "no versions yet"}</span>
        )}
        <div className="da-actions">
          {a.controls.length > 0 && <Button size="sm" variant="ghost" onClick={() => knobs(a.id)} title="Its knobs, in this panel's settings" data-testid="design-knobs">Knobs ({a.controls.length})</Button>}
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
