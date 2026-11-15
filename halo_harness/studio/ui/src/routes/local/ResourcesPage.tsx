// Local -> Resources (3.3.5.0 R1): the live view. Per host a strip
// (ResourceStrip.tsx): GPU use, VRAM used of total and who holds it, RAM, CPU,
// the temperature, sampled once a second while this page is open (it holds the
// sampler on: POST local/resources/watch {on: true}, renewed every 15 s, off
// when the page goes) or the steward job runs; the last 5 minutes come first
// from GET local/resources. Under the strips, the traffic view (TrafficView.tsx).
import { useEffect } from "react";
import { ResourceStrip } from "./ResourceStrip";
import { loadResources, RENEW_MS, useLocal, watch } from "./store";
import { TrafficView } from "./TrafficView";

function useWatch(): void {
  useEffect(() => {
    void loadResources();
    void watch(true);
    const id = window.setInterval(() => {
      if (!document.hidden) void watch(true);
    }, RENEW_MS);
    return () => {
      window.clearInterval(id);
      void watch(false);
    };
  }, []);
}

const WAIT = "Waiting for the first sample: the sampler reads this machine's GPU, memory and CPU once a second while this page is "
  + "open. A host a fleet member serves shows up here when that member pushes its samples to this hub.";

/** 3.6.0.0 R5e: before the first sample, a strip of the same rows (ResourceStrip.tsx), so the first sample moves
 *  nothing under it (a 40 px note gave way to the strip and the traffic view moved 74 px down). */
function WaitStrip() {
  const num = (label: string) => <span className="lc-num"><span className="lc-num-label mono">{label}</span> <span className="lc-num-value mono">?</span></span>;
  return (
    <section className="lc-strip lc-strip-wait" data-testid="local-resources-wait" aria-label="Resources: waiting for the first sample" title={WAIT}>
      <div className="lc-strip-head">
        <b className="mono">this machine</b>
        <span className="spacer" />
        <span className="mono muted">waiting for the first sample</span>
      </div>
      <div className="lc-vram">
        <span className="lc-vram-bar" aria-hidden="true"><span style={{ width: "0%" }} /></span>
        <span className="mono muted">VRAM ?</span>
        <span className="mono lc-holder">{WAIT}</span>
      </div>
      <div className="lc-strip-nums">
        <span className="lc-gpu">{num("GPU")}<svg className="lc-spark" aria-hidden="true" /></span>
        {num("RAM")}
        {num("CPU")}
        {num("temp")}
      </div>
    </section>
  );
}

export function ResourcesPage() {
  useWatch();
  const hosts = useLocal((s) => Object.keys(s.samples).sort().join("|"));
  const samples = useLocal((s) => s.samples);
  const names = hosts ? hosts.split("|") : [];
  return (
    <div className="lc-resources" data-testid="local-resources">
      <section className="lc-block" aria-label="Resources">
        <div className="rail-label mono">RESOURCES · ONE SAMPLE A SECOND PER HOST</div>
        {names.length ? (
          <div className="lc-strips">
            {names.map((h) => <ResourceStrip key={h} host={h} samples={samples[h] || []} />)}
          </div>
        ) : (
          <div className="lc-strips">
            <WaitStrip />
          </div>
        )}
      </section>
      <TrafficView />
    </div>
  );
}
