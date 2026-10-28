// Local's page rail (3.3.5.0 R1), down the left of the room: the seven pages in
// their order, the open one lit, a small word each -- Resources the hosts it
// samples, Hosts how many servers Halo knows, Models how many it lists, and the
// pages still to come the round that fills them; a click opens the page
// (pages.ts). Settings' group rail turned to Local's pages.
import { goto, PAGES, usePage, type PageId } from "./pages";
import { useLocal } from "./store";

function useWords(): Record<PageId, string> {
  const hosts = useLocal((s) => (s.hosts ? s.hosts.length : -1));
  const models = useLocal((s) => (s.models ? s.models.hosts.reduce((n, h) => n + h.models.length, 0) : -1));
  const sampled = useLocal((s) => Object.keys(s.samples).length);
  const out = {} as Record<PageId, string>;
  for (const p of PAGES) out[p.id] = p.built ? "" : "soon";
  out.resources = sampled ? `${sampled} live` : "";
  out.hosts = hosts >= 0 ? String(hosts) : "";
  out.models = models >= 0 ? String(models) : "";
  return out;
}

export function LocalRail() {
  const page = usePage();
  const words = useWords();
  return (
    <nav className="lc-rail" aria-label="Local pages" data-testid="local-rail">
      <ol className="lc-rail-list">
        {PAGES.map((p) => {
          const on = p.id === page;
          return (
            <li key={p.id}>
              <button type="button" className={"lc-rail-item" + (on ? " on" : "")} onClick={() => goto(p.id)} data-testid="local-rail-page"
                      data-page={p.id} data-built={p.built || undefined} aria-current={on ? "page" : undefined}
                      title={p.built ? p.title : `${p.title}: framed here, filled in ${p.round}`}>
                <span className="lc-rail-title">{p.title}</span>
                {words[p.id] && <span className="lc-rail-word mono" data-soon={!p.built || undefined}>{words[p.id]}</span>}
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
