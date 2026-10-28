// Pull on Local -> Library (3.3.5.0 R3; routes/local/jobs.ts): RowPull is a row's Pull (an Ollama model, or a GGUF
// file through Ollama as hf.co/<repo>:<quant>) onto the host picked above the list, its progress bar while it runs,
// and "installed on <host>" once the host has it; PullByName is the box for a name typed by hand. Each button's
// title is the `halo models pull` line that does the same.
import { useState } from "react";
import { Button } from "../../lib/ui";
import { jobFor, jobKey, pullLine, startPull, useJobs } from "./jobs";
import { useLib } from "./libstore";
import { PullBar } from "./Pulls";
import type { LibRow } from "./types";

export function useLibHost(): string {
  const picked = useLib((s) => s.filters.host);
  const fallback = useLib((s) => s.data?.host?.name || s.data?.hosts?.[0]?.name || "");
  return picked || fallback;
}

export function RowPull({ row }: { row: LibRow }) {
  const host = useLibHost();
  const target = row.pull_target || "";
  const job = useJobs((s) => (host && target ? jobFor(s, host, target) : undefined));
  const said = useJobs((s) => s.said[jobKey(host, target)] || "");
  const installed = row.installed || [];
  if (!target) {
    return (
      <Button size="sm" variant="primary" disabled data-testid="local-library-pull"
              title={`an MLX repo runs outside Ollama: ${row.pull_line} (Local -> Hugging Face)`}>Pull</Button>
    );
  }
  const here = installed.includes(host);
  return (
    <>
      {installed.length > 0 && (
        <span className="og-chip mono lc-installed-chip" data-testid="local-library-installed" title="the host's catalog (/api/tags) has it">
          installed on {installed.join(", ")}
        </span>
      )}
      {!here && (!job || job.done) && (
        <Button size="sm" variant="primary" disabled={!host} onClick={() => void startPull(host, target)} data-testid="local-library-pull"
                title={host ? pullLine(target, host) : "pick a host above the list first"}>
          Pull{host ? ` to ${host}` : ""}
        </Button>
      )}
      {job && !(here && job.done && job.ok) && <PullBar j={job} />}
      {said && <span className="mono lc-said" data-testid="local-library-pull-said">{said}</span>}
    </>
  );
}

export function PullByName() {
  const host = useLibHost();
  const [name, setName] = useState("");
  const [asked, setAsked] = useState("");
  const job = useJobs((s) => (asked && host ? jobFor(s, host, asked) : undefined));
  const said = useJobs((s) => (asked ? s.said[jobKey(host, asked)] || "" : ""));
  const go = () => {
    const n = name.trim();
    if (!n || !host) return;
    setAsked(n);
    void startPull(host, n);
  };
  return (
    <div className="lc-pull-name" data-testid="local-pull-box">
      <input className="input mono" value={name} onChange={(e) => setName(e.target.value)} onKeyDown={(e) => e.key === "Enter" && go()}
             placeholder="pull by name: qwen3.5:9b or hf.co/<repo>:<quant>" aria-label="pull by name" data-testid="local-pull-name" />
      <Button size="sm" variant="primary" disabled={!name.trim() || !host} onClick={go} data-testid="local-pull-go"
              title={name.trim() && host ? pullLine(name.trim(), host) : "type a model's name; the host is the one picked above"}>
        Pull{host ? ` to ${host}` : ""}
      </Button>
      {job && <PullBar j={job} />}
      {said && <span className="mono lc-said" data-testid="local-pull-name-said">{said}</span>}
    </div>
  );
}
