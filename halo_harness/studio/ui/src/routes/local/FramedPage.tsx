// Local's framed page (3.3.5.0 R1): a page a later round fills says in one paragraph what it will hold and lists the
// commands that do that work today, each one copyable. Every page is built now (3.3.7.0 R5 built the last, Steward:
// StewardPage.tsx), so FRAMES is empty; the frame stays for the next page a round adds before it is built.
import type { PageId } from "./pages";

type Frame = { round: string; holds: string; cli: [string, string][] };

export const FRAMES: Partial<Record<PageId, Frame>> = {};

export function FramedPage({ page }: { page: PageId }) {
  const f = FRAMES[page];
  if (!f) return null;
  return (
    <div className="lc-framed" data-testid="local-framed" data-page={page}>
      <section className="lc-block" aria-label="What this page will hold">
        <div className="rail-label mono">WHAT THIS PAGE WILL HOLD · {f.round}</div>
        <p className="lc-holds" data-testid="local-framed-holds">{f.holds}</p>
      </section>
      <section className="lc-block" aria-label="The commands today">
        <div className="rail-label mono">TODAY, FROM A TERMINAL</div>
        <ul className="lc-cli">
          {f.cli.map(([cmd, what]) => (
            <li key={cmd} data-testid="local-framed-cli">
              <code className="mono lc-cli-line">{cmd}</code> <span className="muted">{what}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
