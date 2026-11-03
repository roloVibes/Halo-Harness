// A pack's `events` panel and its `bundle` panel (3.2.0.0 R3).
// PackEvents: the pack's own `pack_event` frames as they arrive, newest last,
// each with the pack's label and its line template (events.ts); 3.2.0.0 R5:
// when the kind's schema has a view hint its data shows under the line
// (ArtifactView), and a frame whose data did not match the schema carries its
// problems, shown under it (the event is published all the same).
// PackBundle: the pack's own ES module, loaded only once you grant
// studio-script (the registry says `script: granted`); until then the panel
// is one line naming the command that grants it. The module exports
// `mount(el, api)`; `api` is bundleApi.ts's: { pack, panel, get(path), config() }
// (get reads a file of the pack as text, config its settings) and, 3.3.10.0 R3,
// publish, on, getData, mode, attention and route; what mount returns, when a
// function, runs when the panel goes away, and every on() it made stops.
import { useEffect, useMemo, useRef, useState } from "react";
import { token } from "../../lib/api";
import { Empty } from "../../lib/ui";
import { clock } from "../orchestra/format";
import { ArtifactProblems, ArtifactView } from "./ArtifactView";
import { bundleApi, type BundleApi } from "./bundleApi";
import { lineOf } from "./events";
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
        const view = reg.packs.find((x) => x.id === f.pack)?.events[f.kind]?.view;
        return (
          <div key={f.n} className="pk-event" data-testid="pack-event" data-problems={f.problems ? f.problems.length : undefined}>
            <div className="fac-line" data-kind="pack" data-testid="pack-event-line" data-known={l.known || undefined}>
              <span className="mono fac-ts">{clock(f.ts)}</span>
              <span className="mono fac-kind">{l.label}</span>
              <span className="fac-text">{l.text}</span>
            </div>
            {view && f.data !== null && <div className="pk-event-data" data-testid="pack-event-data"><ArtifactView doc={f.data} view={view} /></div>}
            {f.problems && <ArtifactProblems list={f.problems} />}
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
    const made = bundleApi(p);
    import(/* @vite-ignore */ url).then(
      (mod: { mount?: (el: HTMLElement, a: BundleApi) => unknown }) => {
        if (!live) return;
        if (typeof mod.mount !== "function") return setError(`${p.source} exports no mount(el, api)`);
        try {
          const off = mod.mount(host, made.api);
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
      made.close();
      host.replaceChildren();
    };
  }, [granted, p.file, p.pack, p.name, p.source]); // p itself is a new object on every registry read
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
