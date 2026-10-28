// Local's framed pages (3.3.5.0 R1): Hugging Face, Benchmarks and Steward,
// the rounds after R2 fill them (Library is built: LibraryPage.tsx) (plans/ROADMAP.md, the 3.3.5.0 entry).
// Each says in one paragraph what it will hold and lists the commands that do
// that work today, each one copyable; Steward also shows the steward job's
// status line and its last note (the Ollama panel's steward block, read the
// same way: GET ollama/steward).
import { useEffect } from "react";
import { NoteLines } from "../fleet/OllamaSteward";
import { loadSteward, startOllamaFeed, useOllama } from "../fleet/ostore";
import type { PageId } from "./pages";

type Frame = { round: string; holds: string; cli: [string, string][] };

export const FRAMES: Partial<Record<PageId, Frame>> = {
  huggingface: {
    round: "R4",
    holds: "Hugging Face local models, controlled: download a GGUF or MLX repo into a huggingface.model_dirs folder through " +
      "the hub cache (progress, resume, the token for a gated repo, the licence first), what is on disk per folder with sizes " +
      "and the fit badge, delete a download, start a local server for a model (llama-server or mlx_lm.server with the fit " +
      "planner's window and layers), stop it, its health and the tail of its log.",
    cli: [["halo local --terminal", "the merged local view: hosts, local servers, the hub cache, the model folders"],
          ["halo local import <file.gguf>", "a GGUF file as an Ollama model"], ["halo local serve <model>", "start a local server"],
          ["halo local stop", "stop it"]],
  },
  benchmarks: {
    round: "R5",
    holds: "A short measured battery per model on this card -- load time, prompt and reply tokens per second at three " +
      "windows, the largest window that stays on the GPU, the reply reserve that avoids cuts, the tool-call and vision " +
      "probes -- kept as the model's speed card and shown on its card and fit badge; tuning scans for the whole host with " +
      "Apply for Halo's side and the exact line for the server's; every change tagged session, until-restart or keep, so " +
      "a session's trial settings revert when it ends.",
    cli: [["halo ollama calibrate <model>", "the largest window that stays on the GPU"],
          ["halo ollama discover --calibrate", "find the servers here, then measure their models"],
          ["halo ollama tune <model>", "a tuned twin with every layer on the GPU"]],
  },
  steward: {
    round: "R6",
    holds: "The steward's page: the job's status, its notes, and a chat box to the steward's own small model (it reads the " +
      "card, the ledger, the events, the profiles and the knowledge, proposes and applies Halo-side changes through the " +
      "same guarded path, runs a benchmark, explains a kind); and the scheduling of several local models on one card, one " +
      "at a time unless the planner says both fit, the steward pivoting between them as a workflow's stages change.",
    cli: [["halo ollama steward status", "whether the job runs, where, its last run and note"],
          ["halo ollama steward findings", "what the rules find"], ["halo ollama steward plan", "the fit plan per host"],
          ["halo ollama steward --watch", "run the job here in the foreground"]],
  },
};

function StewardNow() {
  const lines = useOllama((s) => s.steward?.status_lines || null);
  const note = useOllama((s) => s.steward?.last_note || null);
  useEffect(() => {
    startOllamaFeed();
    void loadSteward();
  }, []);
  return (
    <section className="lc-block" aria-label="The steward now" data-testid="local-steward-now">
      <div className="rail-label mono">THE STEWARD NOW</div>
      <div className="mono muted lc-status" data-testid="local-steward-status">
        {(lines || ["reading the steward..."]).map((l) => (
          <div key={l}>{l.trim()}</div>
        ))}
      </div>
      <NoteLines note={note} testid="local-steward-note" />
    </section>
  );
}

export function FramedPage({ page }: { page: PageId }) {
  const f = FRAMES[page];
  if (!f) return null;
  return (
    <div className="lc-framed" data-testid="local-framed" data-page={page}>
      <section className="lc-block" aria-label="What this page will hold">
        <div className="rail-label mono">WHAT THIS PAGE WILL HOLD · 3.3.5.0 {f.round}</div>
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
      {page === "steward" && <StewardNow />}
    </div>
  );
}
