// 3.3.7.0 R3: the Hosts card's warm-set line -- which of the active lineup's local models co-reside on this card and
// how much of it they use ("warm on pc: qwen3-coder:30b (main, coder), qwen2.5:1.5b (small) -- 20.8 of 21.5 GB;
// qwen3.8:27b (reviewer) pivots; 2 swaps a pass, ~50 s of loading"), GET local/warm-set?host=<name>
// (studio/local_sched_api.py, local_sched/warm_set.py). Read when the card shows and again when what is loaded on
// it changes; nothing shows for a host the lineup has no local lane on.
import { useEffect, useState } from "react";
import { api } from "../../lib/api";

type WarmSet = { line: string; swaps: number; lineup: string };

export function HostWarm({ name, loadedKey }: { name: string; loadedKey: string }) {
  const [got, setGot] = useState<WarmSet | null>(null);
  useEffect(() => {
    let live = true;
    api.get<WarmSet>("local/warm-set", { host: name })
      .then((r) => {
        if (live) setGot(r);
      })
      .catch(() => {
        if (live) setGot(null);
      });
    return () => {
      live = false;
    };
  }, [name, loadedKey]);
  if (!got || !got.line) return null;
  return (
    <div className="mono muted lc-host-line" data-testid="local-host-warm" data-swaps={got.swaps}
         title={`the warm set of lineup ${got.lineup}: halo local warm ${got.lineup} loads it`}>
      {got.line}
    </div>
  );
}
