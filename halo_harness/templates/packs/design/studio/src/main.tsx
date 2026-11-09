// The design pack's page (Halo 3.3.13.0 R2): Studio loads studio/design.js -- this module, built by the Studio UI's
// `npm run build` (vite.pack.config.ts) -- once the owner grants studio-script, and calls mount(el, api) with the
// Design section's whole page. React, the lib/ui parts and the workspace are the shell's own (api.lib), so nothing
// of the shell is copied in here. The page: the Start view or the panels (Start.tsx), the dialogs, the palette's
// Design lines while it is on screen, and its stylesheet; what mount returns takes all of it away again.
import { createRoot } from "react-dom/client";
import type { BundleApi } from "@halo/bundle";
import { setApi } from "./base";
import { designCommands } from "./commands";
import { designPanels } from "./Design";
import { DesignDialogs } from "./Dialogs";
import { DesignPage } from "./Start";
import thread from "./design-thread.css?inline";
import css from "./design.css?inline";

export function mount(el: HTMLElement, api: BundleApi): () => void {
  setApi(api);
  const offCss = api.lib.css(css + "\n" + thread);
  const offCommands = api.lib.commands(() => designCommands().map(({ id, label, hint, run }) => ({ id, label, hint, run })));
  el.classList.add("ds-page");
  const root = createRoot(el);
  root.render(
    <>
      <DesignPage specs={designPanels} />
      <DesignDialogs />
    </>,
  );
  return () => {
    root.unmount();
    offCommands();
    offCss();
    setApi(null);
  };
}
