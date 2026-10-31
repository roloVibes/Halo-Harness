// One Local page (3.3.5.0 R1): the open page under a head that says which page
// it is and what it holds (routes/help-local.ts), its help lines one click away
// (closed by default), and a line naming which of Local's five ideas the page
// carries (the fit meter, "why" on every number, intents, "make it fit", the hub
// as the one picture). Resources, Hosts, Models and Library (3.3.5.0 R2) are
// built, and Hugging Face (3.3.5.0 R5); Benchmarks and Steward are framed (FramedPage.tsx).
import { useEffect, useRef, type ComponentType } from "react";
import { HELP } from "../help";
import { FramedPage } from "./FramedPage";
import { HfPage } from "./HfPage";
import { HostsPage } from "./HostsPage";
import { LibraryPage } from "./LibraryPage";
import { ModelsPage } from "./ModelsPage";
import { PAGES, titleOf, usePage, type PageId } from "./pages";
import { ResourcesPage } from "./ResourcesPage";

const BODY: Partial<Record<PageId, ComponentType>> = { resources: ResourcesPage, hosts: HostsPage, models: ModelsPage, library: LibraryPage,
  huggingface: HfPage };

/** Which of the five ideas each page shows (the help names all five). */
export const IDEAS: Record<PageId, string[]> = {
  resources: ["why on every number", "the hub as the one picture"],
  hosts: ["fit meter", "make it fit", "why on every number", "the hub as the one picture"],
  models: ["fit meter", "intents, not model names", "why on every number"],
  library: ["fit meter", "why on every number", "intents, not model names", "presets and the three truths"],
  huggingface: ["fit meter", "why on every number"],
  benchmarks: ["fit meter", "why on every number"],
  steward: ["make it fit", "the hub as the one picture"],
};

function Head({ page }: { page: PageId }) {
  const h = HELP[`local-${page}`] || { about: "", help: "" };
  const lines = (h.help || "").split("\n").filter(Boolean);
  const n = PAGES.findIndex((p) => p.id === page) + 1;
  return (
    <header className="lc-page-head">
      <div className="lc-page-kicker mono">LOCAL · PAGE {n} OF {PAGES.length}</div>
      <h2 className="lc-page-title" data-testid="local-page-title">{titleOf(page)}</h2>
      {h.about && <p className="lc-lead muted">{h.about}</p>}
      <p className="lc-ideas mono muted" data-testid="local-ideas">ideas here: {IDEAS[page].join(" · ")}</p>
      {lines.length > 0 && (
        <details className="lc-page-help" data-testid="local-page-help">
          <summary className="mono">How this page works</summary>
          <ul>
            {lines.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        </details>
      )}
    </header>
  );
}

export function LocalPage() {
  const page = usePage();
  const ref = useRef<HTMLElement>(null);
  useEffect(() => {
    void ref.current?.closest(".lc-scroll")?.scrollTo({ top: 0 }); // braces: a scrollTo that answers a promise is no cleanup
  }, [page]);
  const Body = BODY[page];
  return (
    <section className="lc-page-card" ref={ref} data-testid="local-page" data-page={page} aria-label={`Local: ${titleOf(page)}`}>
      <Head page={page} />
      {Body ? <Body /> : <FramedPage page={page} />}
    </section>
  );
}
