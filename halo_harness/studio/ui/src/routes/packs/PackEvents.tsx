// A pack's `events` panel and its `bundle` panel (3.2.0.0 R3).
// PackEvents: the pack's own `pack_event` frames as they arrive, newest last,
// each with the pack's label and its line template (events.ts).
// PackBundle: the pack's own ES module, loaded only once you grant
// studio-script (the registry says `script: granted`); until then the panel
// is one line naming the command that grants it. The module exports
// `mount(el, api)`; `api` is { pack, panel, get(path), config() }: get reads a
// file of the pack (as text), config its settings; what mount returns, when a
// function, runs when the panel goes away.
import { useEffect, useMemo, useRef, useState } from "react";
import { api, token } from "../../lib/api";
import { Empty } from "../../lib/ui";
import { clock } from "../orchestra/format";
import { lineOf } from "./events";
import { fetchText } from "./nav";
import { usePacks } from "./store";
import type { PackPanel } from "./types";

export function PackEvents({ p }: { p: PackPanel }) {
  const frames = usePacks((s) => s.frames);
  const reg = usePacks((s) => s.reg);
  const mine = useMemo(() => frames.filter((f) => f.pack === p.pack), [frames, p.pack]);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (box.current) box.current.scrollTop = box.current.scrollHeight;
  }, [mine]);
  if (!mine.length)
    return <Empty title="Nothing yet" body={`The lines ${p.pack} publishes show here the moment they arrive.`} testid="pack-events-empty" />;
  return (
    <div className="pk-events fac-log" ref={box} data-testid="pack-events" data-reg={reg.packs.length}>
      {mine.map((f) => {
        const l = lineOf(f.pack, f.kind, f.data);
        return (
          <div key={f.n} className="fac-line" data-kind="pack" data-testid="pack-event-line" data-known={l.known || undefined}>
            <span className="mono fac-ts">{clock(f.ts)}</span>
            <span className="mono fac-kind">{l.label}</span>
            <span className="fac-text">{l.text}</span>
          </div>
        );
      })}
    </div>
  );
}

type Mounted = { off?: () => void };

export function PackBundle({ p }: { p: PackPanel }) {
  const el = useRef<HTMLDivElement>(null);
  const [error, setError] = useState("");
  const granted = p.script === "granted" && !!p.file;
  useEffect(() => {
    if (!granted || !el.current) return;
    const host = el.current;
    const m: Mounted = {};
    let live = true;
    const url = new URL(`${p.file}?t=${encodeURIComponent(token())}`, location.origin + "/").href;
    const bridge = { pack: p.pack, panel: p.name, get: (path: string) => fetchText(`api/pack/${p.pack}/file/${path}`), config: () => api.get(`pack/${p.pack}/config`) };
    import(/* @vite-ignore */ url).then(
      (mod: { mount?: (el: HTMLElement, a: typeof bridge) => unknown }) => {
        if (!live) return;
        if (typeof mod.mount !== "function") return setError(`${p.source} exports no mount(el, api)`);
        try {
          const off = mod.mount(host, bridge);
          if (typeof off === "function") m.off = off as () => void;
        } catch (e) {
          setError(`${p.source}: ${e instanceof Error ? e.message : String(e)}`);
        }
      },
      (e) => live && setError(`${p.source} did not load: ${e instanceof Error ? e.message : String(e)}`),
    );
    return () => {
      live = false;
      m.off?.();
      host.replaceChildren();
    };
  }, [granted, p.file, p.pack, p.name, p.source]);
  if (!granted)
    return (
      <div className="pk-grant" data-testid="pack-bundle-grant">
        <p>This panel is {p.pack}'s own script ({p.source}). It runs once you grant it:</p>
        <code className="pk-grant-cmd">{p.grant}</code>
      </div>
    );
  return (
    <div className="pk-bundle" data-testid="pack-bundle">
      {error && <div className="field-error" data-testid="pack-bundle-error">{error}</div>}
      <div className="pk-bundle-host" ref={el} />
    </div>
  );
}
