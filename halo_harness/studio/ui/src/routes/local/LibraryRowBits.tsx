// The search's parts of a Library row (3.3.6.0 R2; models_library/search.py): each capability chip with its truth
// as a glyph and a title (✓ verified: probed on this host · ◇ declared: the metadata says it · ≈ expected: the
// family, size or name · ? needs a probe), the two verdicts side by side ("fits: yes · role-ready: no (no tool
// calls)"), the cost preview line (download and eta, VRAM at the window, cold load, tok/s, what it evicts -- each
// number's source as the title), the crash line of a model that died here, and Download and verify with its stages
// and the role offer.
import { useEffect } from "react";
import { Button } from "../../lib/ui";
import { useLibHost } from "./LibraryPull";
import { useLib } from "./libstore";
import type { LibRow } from "./types";
import { assignRole, startVerifies, startVerify, useVerify, verifyFor } from "./verify";

const TRUTH_WORDS: Record<string, string> = {
  verified: "verified: the battery probed it on this host", declared: "declared: the metadata says it (not probed)",
  expected: "expected: inferred from the family, size or name (not probed)",
};

export function CapMarks({ row }: { row: LibRow }) {
  const chips = row.chips || [];
  if (!chips.length) return null;
  return (
    <span className="ls-caps" data-testid="local-library-caps">
      {chips.map((c) => (
        <span key={c.cap} className="og-chip mono ls-cap" data-testid="local-library-cap-chip" data-cap={c.cap}
              data-truth={c.truth || "probe"} title={`${c.title}: ${c.truth ? TRUTH_WORDS[c.truth] : "needs a probe"} -- ${c.why}`}>
          {c.title} <span className="ls-glyph" aria-label={c.truth || "needs a probe"}>{c.glyph}</span>
        </span>
      ))}
    </span>
  );
}

function word(ok: boolean | null | undefined): string {
  return ok ? "yes" : ok === false ? "no" : "not yet";
}

export function Verdicts({ row }: { row: LibRow }) {
  const v = row.verdicts;
  if (!v) return null;
  return (
    <p className="mono ls-verdicts" data-testid="local-library-verdicts" data-fits={word(v.fits.ok)} data-ready={word(v.role_ready.ok)}>
      <span title={v.fits.why}>fits: {v.fits.word}</span> · <span title="only a probe on this host makes a model role-ready">
        role-ready: {word(v.role_ready.ok)} ({v.role_ready.why})</span>
    </p>
  );
}

export function CostLine({ row }: { row: LibRow }) {
  const c = row.cost;
  if (!c) return null;
  const title = [`download: ${c.line_from}`, `cold load: ${c.cold_from}`, `speed: ${c.tok_from}`,
                 c.evicts.length ? `it would push out ${c.evicts.join(", ")}` : "it fits beside what is resident"].join("\n");
  return <p className="mono muted ls-cost" data-testid="local-library-cost" data-evicts={c.evicts.join(",")} title={title}>cost: {c.text}</p>;
}

export function CrashLine({ row }: { row: LibRow }) {
  if (!row.crashed) return null;
  return (
    <p className="mono ls-crash" data-testid="local-library-crashed" data-signature={row.crashed.signature}
       title="from the server's own events (halo ollama crashes): the search greys it with Exclude crashed">{row.crashed.line}</p>
  );
}

export function VerifyBits({ row }: { row: LibRow }) {
  const host = useLibHost();
  const search = useLib((s) => s.data?.search);
  const job = useVerify((s) => verifyFor(s, host, row.pull_target || ""));
  const said = useVerify((s) => s.said[`v|${host}|${row.pull_target || ""}`]);
  const assigned = useVerify((s) => (job ? s.said[`a|${job.job}`] : undefined));
  useEffect(() => {
    startVerifies();
  }, []);
  const target = row.pull_target || "";
  if (!target || row.kind === "mlx") return null;
  const role = search?.for_role || search?.bundle?.lineup_role || "";
  const here = (row.installed || []).includes(host);
  return (
    <>
      {(!job || job.done) && !(job && job.ok) && (
        <Button size="sm" variant={here ? "default" : "primary"} disabled={!host} onClick={() => void startVerify(host, target, role)}
                data-testid="local-library-verify" title={`pull ${target} onto ${host || "the host"}, run the battery on it (about 8 requests, 1-3 minutes), `
                  + `write its profile${role ? `, then offer it the ${role} role` : ""}; nothing downloads until you press it`}>
          {here ? "Verify" : "Download and verify"}
        </Button>
      )}
      {job && (
        <span className="mono ls-verify" data-testid="local-library-verify-job" data-stage={job.stage} data-done={job.done || undefined}
              data-ok={job.ok || undefined}>
          {job.done ? job.say : job.stage === "pull" ? "1/2 pulling..." : "2/2 probing..."}
        </span>
      )}
      {job?.offer && (
        <span className="ls-offer" data-testid="local-library-offer" data-ok={job.offer.ok || undefined}>
          <span className="mono">{job.offer.line}</span>
          {job.offer.ok && !assigned?.ok && (
            <Button size="sm" variant="primary" onClick={() => void assignRole(job)} data-testid="local-library-assign"
                    title={`the lineup's ${job.offer.role} role gets ${job.offer.ref} (the halo teams path)`}>Assign</Button>
          )}
          {assigned && <span className="mono lc-said" data-ok={assigned.ok || undefined} data-testid="local-library-assigned">{assigned.text}</span>}
        </span>
      )}
      {said && !said.ok && <span className="mono lc-said" data-testid="local-library-verify-said">{said.text}</span>}
    </>
  );
}
