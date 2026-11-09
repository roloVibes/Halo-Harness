// PackView (3.3.13.0 R2, extension API 1.2): a pack section drawn whole by one module of the pack (its pack.yaml's
// `sections[].view: {bundle}`). Studio imports the module once the owner grants studio-script (the registry then names
// its file) and calls `mount(el, api)` with the section's page as `el`; `api` is a bundle panel's (bundleApi.ts) with
// `lib` -- the shell's React, ReactDOM, lib/ui and helpers -- `routes` (the pack's own routes under /api/) and
// `section`. What mount returns, when a function, runs when the section goes away (the pack turned off, a reload).
// Until the grant, the page is one line naming the command that gives it.
import { useEffect, useRef, useState } from "react";
import { bundleApi, type BundleApi } from "./bundleApi";
import { importPack } from "./importPack";
import { usePacks } from "./store";
import type { PackPanel, PackSection } from "./types";

type Mounted = { off?: () => void };

function asPanel(s: PackSection): PackPanel {
  return { id: s.id, name: s.name, pack: s.pack, section: s.id, title: s.title, kind: "bundle", w: 24, h: 0, help: s.help,
           about: `from pack ${s.pack}`, collapsed: false, source: s.view?.source, file: s.view?.file,
           script: s.view?.script, grant: s.view?.grant };
}

export function PackView({ section }: { section: string }) {
  const s = usePacks((st) => st.reg.packs.flatMap((p) => p.sections).find((x) => x.id === section));
  const el = useRef<HTMLDivElement>(null);
  const [error, setError] = useState("");
  const file = s?.view?.script === "granted" ? s.view.file || "" : "";
  useEffect(() => {
    if (!s || !file || !el.current) return;
    const host = el.current;
    const m: Mounted = {};
    let live = true;
    const made = bundleApi(asPanel(s));
    setError("");
    importPack<{ mount?: (el: HTMLElement, a: BundleApi) => unknown }>(s.pack, file).then( // 3.3.14.0 R1: ?k=, its lib
      (mod) => {
        if (!live) return;
        if (typeof mod.mount !== "function") return setError(`${s.view?.source} exports no mount(el, api)`);
        try {
          const off = mod.mount(host, made.api);
          if (typeof off === "function") m.off = off as () => void;
        } catch (e) {
          setError(`${s.view?.source}: ${e instanceof Error ? e.message : String(e)}`);
        }
      },
      (e) => live && setError(`${s.view?.source} did not load: ${e instanceof Error ? e.message : String(e)}`),
    );
    return () => {
      live = false;
      m.off?.();
      made.close();
      host.replaceChildren();
    };
  }, [file, s?.id]); // eslint-disable-line react-hooks/exhaustive-deps -- s is a new object on every registry read
  if (!s) return <div className="pack-loading mono muted" role="status">loading the pack's section</div>;
  if (!file)
    return (
      <div className="pk-grant pk-view-grant" data-testid="pack-view-grant" data-section={s.id}>
        <p>{s.title} is drawn by {s.pack}'s own script ({s.view?.source}). It runs once you grant it:</p>
        <code className="pk-grant-cmd">{s.view?.grant}</code>
      </div>
    );
  return (
    <div className="pk-view" data-testid="pack-view" data-section={s.id}>
      {error && <div className="field-error" data-testid="pack-view-error">{error}</div>}
      <div className="pk-view-host" ref={el} />
    </div>
  );
}
