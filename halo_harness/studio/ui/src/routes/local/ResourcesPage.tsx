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
          <p className="muted" data-testid="local-resources-wait">
            Waiting for the first sample: the sampler reads this machine's GPU, memory and CPU once a second while this page is
            open. A host a fleet member serves shows up here when that member pushes its samples to this hub.
          </p>
        )}
      </section>
      <TrafficView />
    </div>
  );
}
