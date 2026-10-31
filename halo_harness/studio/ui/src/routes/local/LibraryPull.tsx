// Pull on Local -> Library (3.3.5.0 R3; routes/local/jobs.ts): RowPull is a row's Pull (an Ollama model, or a GGUF
// file through Ollama as hf.co/<repo>:<quant>) onto the host picked above the list, its progress bar while it runs,
// and "installed on <host>" once the host has it; PullByName is the box for a name typed by hand. Each button's
// title is the `halo models pull` line that does the same. 3.3.5.0 R5: a Hugging Face row (GGUF or MLX) has Download
// (into a huggingface.model_dirs folder: the licence card first, routes/local/HfCards.tsx), its progress, and "on disk
// in <folder>" after; a GGUF row keeps Pull to <host> (through Ollama) beside it.
import { FitEvidenceChip } from "../shared/FitEvidence";
import { useEffect, useState } from "react";
import { Button } from "../../lib/ui";
import { askDownload, loadDirs, useHf } from "./hfstore";
import { dlJobFor, jobFor, jobKey, pullLine, startPull, useJobs } from "./jobs";
import { useLib } from "./libstore";
import { PullBar } from "./Pulls";
import type { LibRow } from "./types";

export function useLibHost(): string {
  const picked = useLib((s) => s.filters.host);
  const fallback = useLib((s) => s.data?.host?.name || s.data?.hosts?.[0]?.name || "");
  return picked || fallback;
}

function RowDownload({ row }: { row: LibRow }) {
  const dirs = useHf((s) => s.data?.dirs);
  const said = useHf((s) => s.said[`dl|${row.id}|${row.tag_or_file || ""}`]);
  const job = useJobs((s) => dlJobFor(s, row.id, row.tag_or_file || ""));
  useEffect(() => {
    if (!dirs) void loadDirs();
  }, [dirs]);
  const folders = (dirs || []).filter((d) => d.exists).map((d) => d.path);
  const disk = row.on_disk || [];
  const line = `halo local download ${row.id}${row.tag_or_file ? ` ${row.tag_or_file}` : ""}`;
  return (
    <>
      {disk.length > 0 && (
        <span className="og-chip mono lc-installed-chip" data-testid="local-library-ondisk" title="its files are in that huggingface.model_dirs folder (Local -> Hugging Face)">
          on disk in {disk.join(", ")}
        </span>
      )}
      {!disk.length && (!job || job.done) && (
        <Button size="sm" variant="primary" disabled={!folders.length} onClick={() => void askDownload(row.id, row.tag_or_file || "", folders)}
                data-testid="local-library-pull" data-act="download" title={folders.length ? line : `add a model folder on Local -> Hugging Face first (${line})`}>
          Download
        </Button>
      )}
      {job && !(disk.length && job.done && job.ok) && <PullBar j={job} />}
      {said && !said.ok && <span className="mono lc-said" data-testid="local-library-dl-said">{said.text}</span>}
    </>
  );
}

export function RowPull({ row }: { row: LibRow }) {
  const host = useLibHost();
  const target = row.pull_target || "";
  const job = useJobs((s) => (host && target ? jobFor(s, host, target) : undefined));
  const said = useJobs((s) => s.said[jobKey(host, target)] || "");
  const installed = row.installed || [];
  const hub = row.source === "hf" && (row.kind === "gguf" || row.kind === "mlx");
  if (!target) return hub ? <RowDownload row={row} /> : null;
  const here = installed.includes(host);
  return (
    <>
      {hub && <RowDownload row={row} />}
      {installed.length > 0 && (
        <span className="og-chip mono lc-installed-chip" data-testid="local-library-installed" title="the host's catalog (/api/tags) has it">
          installed on {installed.join(", ")}
        </span>
      )}
      {installed.length > 0 && <FitEvidenceChip ev={row.fit_evidence} testid="local-library-fit-evidence" />}
      {!here && (!job || job.done) && (
        <Button size="sm" variant={hub ? "default" : "primary"} disabled={!host} onClick={() => void startPull(host, target)}
                data-testid={hub ? "local-library-pull-ollama" : "local-library-pull"}
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
