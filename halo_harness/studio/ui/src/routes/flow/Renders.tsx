// flow-renders: the run's artboards inline (an <img>, or a <video controls>
// for a video render) with their version badges, the prompt the Art
// Director wrote, and -- while the confirm gate is open -- Confirm / Redo
// with an instruction / Stop. After the answer the band says `accepted`.
import { useState } from "react";
import type { MotionState } from "../../lib/motion";
import { Metric, NoFlow } from "./bits";
import { AnsweredBand, GateCard, useAnswered } from "./Gate";
import { NONE, useFlow } from "./store";
import type { Artboard } from "./types";

function src(a: Artboard, slug: string | undefined, ver: number): string {
  if (!a.url) return "";
  if (!ver || ver === a.version || !slug) return `${a.url}?v=${a.version}`;
  return `/design-files/${encodeURIComponent(slug)}/${encodeURIComponent(a.id)}/v${ver}/${encodeURIComponent(a.file)}`;
}

function Art({ a, big }: { a: Artboard; big?: boolean }) {
  const slug = useFlow((s) => s.data?.project?.slug);
  const [ver, setVer] = useState(0);
  const url = src(a, slug, ver);
  const shown = ver || a.version;
  return (
    <figure className="fl-art" data-big={big || undefined} data-testid="flow-artboard">
      <div className="fl-art-frame">
        {!url ? (
          <div className="fl-art-empty mono muted">no file yet</div>
        ) : a.kind === "video" ? (
          <video src={url} controls muted preload="metadata" aria-label={`${a.title || a.id} v${shown}`} />
        ) : (
          <img src={url} alt={`${a.title || a.id} v${shown}`} loading="lazy" />
        )}
      </div>
      <figcaption className="fl-art-cap mono">
        <span>{a.title || a.id}</span>
        <span className="fl-vers" role="group" aria-label="Versions">
          {(a.versions.length ? a.versions : [a.version]).map((v) => (
            <button key={v} className="fl-ver" aria-pressed={v === shown} onClick={() => setVer(v === a.version ? 0 : v)} title={`version ${v}`}>
              v{v}
            </button>
          ))}
        </span>
      </figcaption>
    </figure>
  );
}

function useConfirmGate() {
  return useFlow((s) => {
    const g = s.data?.gate;
    const kind = s.data?.flow.steps.find((x) => x.id === g?.step)?.kind;
    return g && (kind === "confirm" || !!g.artboards?.length) ? g : null;
  });
}

function useConfirmStep(): string | undefined {
  return useFlow((s) => s.data?.flow.steps.find((x) => x.kind === "confirm")?.id);
}

/** The band after the gate: what was answered here, else what the run recorded. */
function Decided() {
  const step = useConfirmStep();
  const mine = useAnswered(step);
  const rec = useFlow((s) => s.data?.steps.find((x) => x.id === step));
  const state = useFlow((s) => s.data?.flow.steps.find((x) => x.id === step)?.state);
  const accepted = (rec?.output as { accepted?: unknown[] } | null | undefined)?.accepted;
  if (mine) return <AnsweredBand action={mine} />;
  if (state === "done" && Array.isArray(accepted)) return <AnsweredBand action="accept" detail={`${accepted.length} file(s), round ${rec?.rounds ?? 1}`} />;
  return null;
}

function Prompt() {
  const out = useFlow((s) => s.data?.steps.find((x) => x.kind === "render")?.output as { prompt?: string; workflow?: string } | undefined);
  if (!out?.prompt) return null;
  return (
    <p className="fl-prompt">
      <span className="og-goal-label mono">PROMPT · {out.workflow}</span> {out.prompt}
    </p>
  );
}

export function RendersGlance() {
  const arts = useFlow((s) => s.data?.artboards || NONE);
  const has = useFlow((s) => !!s.data);
  const gate = useConfirmGate();
  if (!has) return <NoFlow what="The renders" />;
  const latest = arts[arts.length - 1];
  return (
    <div className="glance fl-renders">
      <div className="glance-numbers">
        <Metric value={arts.length} label={arts.length === 1 ? "artboard" : "artboards"} />
        <Metric value={latest ? `v${latest.version}` : "-"} label="latest version" tone="accent" />
      </div>
      {latest ? <Art a={latest} big /> : <div className="og-wait muted">Wait for the render step: its picture lands here for you to confirm.</div>}
      {gate ? <GateCard gate={gate} compact /> : <Decided />}
    </div>
  );
}

export function RendersDetail() {
  const arts = useFlow((s) => s.data?.artboards || NONE);
  const has = useFlow((s) => !!s.data);
  const gate = useConfirmGate();
  if (!has) return <NoFlow what="The renders" />;
  return (
    <div className="fl-renders">
      {gate ? <GateCard gate={gate} /> : <Decided />}
      <Prompt />
      <div className="fl-arts">
        {arts.map((a) => (
          <Art key={a.id} a={a} big={arts.length === 1} />
        ))}
      </div>
      {!arts.length && <div className="og-wait muted">Wait for the render step: its picture lands here for you to confirm.</div>}
    </div>
  );
}

export function useRendersMotion(): MotionState {
  const gate = useConfirmGate();
  const render = useFlow((s) => s.data?.flow.steps.find((x) => x.kind === "render")?.state);
  const n = useFlow((s) => s.data?.artboards.length || 0);
  if (gate) return "waiting";
  if (render === "running") return "working";
  if (render === "failed") return "error";
  return n ? "idle" : "none";
}
