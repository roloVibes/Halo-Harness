// LiveFile: the one-file view. The base file's lines in mono; each lane's
// claimed unit is a band in the lane's colour with its state on it
// (claimed / writing / written / merged) and the lane's current text inside;
// a band being written shimmers (working). A picker when the goal has
// several files. Refetched on every claim and merge frame (sync.ts).
import { useEffect, useRef, type ReactNode } from "react";
import type { MotionState } from "../../lib/motion";
import { Metric, NoRun } from "./bits";
import { focusLane, laneColor, NONE, orch, regionMotion, setOpt, useOrch } from "./store";
import { loadFile, selectFile } from "./sync";
import type { FileView, Region } from "./types";

function Lines({ lines, from }: { lines: string[]; from: number }) {
  return (
    <>
      {lines.map((text, i) => (
        <div key={from + i} className="og-line">
          <span className="og-ln">{from + i}</span>
          <span className="og-code">{text || " "}</span>
        </div>
      ))}
    </>
  );
}

function Band({ r, focused }: { r: Region; focused: boolean }) {
  return (
    <div
      className="og-band"
      data-testid="claim-region"
      data-state={r.state}
      data-lc={laneColor(r.lane)}
      data-motion={regionMotion(r.state)}
      data-focus={focused || undefined}
      data-lane={r.lane}
      onClick={() => focusLane(r.lane)}
    >
      <div className="og-band-tag mono">
        <span className="og-band-lane">lane {r.lane}</span>
        <span className="og-band-state">{r.state}</span>
        <span className="og-band-key">{r.key.split("#")[1] || r.key}</span>
        <span className="og-band-holder" title={r.holder}>
          {r.holder}
        </span>
      </div>
      <Lines lines={r.text} from={r.start_line} />
    </div>
  );
}

function compose(view: FileView, focus: number | null, onlyClaimed: boolean): ReactNode[] {
  const out: ReactNode[] = [];
  let line = 1;
  for (const r of view.regions) {
    if (r.start_line < line) continue; // overlapping claims: the first band wins
    if (r.start_line > line) {
      const gap = view.base.slice(line - 1, r.start_line - 1);
      out.push(onlyClaimed ? <div key={"gap" + line} className="og-gap mono">{gap.length} line{gap.length === 1 ? "" : "s"}</div> : <Lines key={"l" + line} lines={gap} from={line} />);
    }
    out.push(<Band key={r.key} r={r} focused={focus === r.lane} />);
    line = r.end_line + 1;
  }
  if (line <= view.base.length && !onlyClaimed) out.push(<Lines key={"l" + line} lines={view.base.slice(line - 1)} from={line} />);
  return out;
}

export function FilePicker() {
  const files = useOrch((s) => s.data?.goal.files || NONE);
  const file = useOrch((s) => s.file);
  if (files.length < 2) return <span className="mono og-file-name">{file}</span>;
  return (
    <select className="input mono og-file-pick" value={file} onChange={(e) => selectFile(e.target.value)} aria-label="File">
      {files.map((f) => (
        <option key={f}>{f}</option>
      ))}
    </select>
  );
}

export function LiveFileDetail() {
  const has = useOrch((s) => !!s.data);
  const file = useOrch((s) => s.file);
  const view = useOrch((s) => s.files[s.file]);
  const focus = useOrch((s) => s.focusLane);
  const only = useOrch((s) => s.opts.fileOnlyClaimed);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (file && !orch.get().files[file]) void loadFile(file);
  }, [file]);
  useEffect(() => {
    box.current?.querySelector(`.og-band[data-lane="${focus}"]`)?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [focus, view]);
  if (!has) return <NoRun what="The live file" />;
  return (
    <div className="og-file">
      <div className="og-file-bar">
        <FilePicker />
        <span className="mono muted">{view ? `base: ${view.base_ref} · ${view.regions.length} claimed unit${view.regions.length === 1 ? "" : "s"}` : "loading..."}</span>
      </div>
      <div className="og-file-body mono" ref={box}>
        {view && compose(view, focus, only)}
      </div>
    </div>
  );
}

export function LiveFileGlance() {
  const view = useOrch((s) => s.files[s.file]);
  const has = useOrch((s) => !!s.data);
  if (!has) return <NoRun what="The live file" />;
  const regions = view?.regions || [];
  const total = Math.max(1, view?.base.length || 1);
  const n = (st: string) => regions.filter((r) => r.state === st).length;
  return (
    <div className="glance">
      <div className="glance-row">
        <span className="glance-kicker mono">FILE</span>
        <FilePicker />
      </div>
      <div className="glance-numbers">
        <Metric value={n("writing")} label="being written" tone="accent" />
        <Metric value={`${n("merged")}/${regions.length}`} label="units merged" tone="ok" />
      </div>
      <div className="og-minimap" aria-hidden="true">
        {regions.map((r) => (
          <span
            key={r.key}
            className="og-mini"
            data-lc={laneColor(r.lane)}
            data-state={r.state}
            data-motion={regionMotion(r.state)}
            style={{ left: `${((r.start_line - 1) / total) * 100}%`, width: `${Math.max(1.5, ((r.end_line - r.start_line + 1) / total) * 100)}%` }}
          />
        ))}
      </div>
    </div>
  );
}

export function LiveFileSettings() {
  const only = useOrch((s) => s.opts.fileOnlyClaimed);
  return (
    <div className="og-settings">
      <label className="field">
        <span className="field-label mono">FILE</span>
        <FilePicker />
      </label>
      <label className="check">
        <input type="checkbox" checked={only} onChange={(e) => setOpt("fileOnlyClaimed", e.target.checked)} /> Only the claimed units (fold the rest)
      </label>
    </div>
  );
}

export function useLiveFileMotion(): MotionState {
  const regions = useOrch((s) => s.files[s.file]?.regions);
  if (!regions || !regions.length) return "none";
  return regions.some((r) => r.state === "writing") ? "working" : "idle";
}
