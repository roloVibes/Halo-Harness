// "Not connected yet" (3.6.0.0 R3): under the map, the boxes on it that nothing hands work to -- what you added and did
// not connect yet, and what the builder made (tagged `new`). Drag a box's dot onto main (or any box) to connect it, or
// click the dot for a list. A drop of a row from the list here adds it, to connect later. R4: while lit, an agent of the
// session that matches no box (overlay.ts: a stranger) is shown here too, tagged with why, never dropped; in a replay,
// a box the run used that the map no longer has shows dashed, "removed since".
import { MapBox } from "./MapBox";
import { useMap } from "./mapStore";
import { useMapView } from "./MapCanvas";
import { useMapHist } from "./mapRuns";
import { STATE_WORDS } from "./LitBits";
import { useLitNow } from "./useLit";

export function Strip() {
  const v = useMapView();
  const facts = useMap((s) => s.detail?.boxes);
  const L = useLitNow();
  const removed = useMapHist((s) => (L.mode === "replay" ? s.open?.removed : undefined));
  const strangers = L.ov?.strangers || [];
  const gone = [...new Set([...(removed || []), ...(L.ov?.gone || [])])];
  const none = !v.strip.length && !strangers.length && !gone.length;
  return (
    <section className="mp-strip" data-testid="map-strip" aria-label="Not connected yet">
      <div className="mp-strip-head">
        <b>Not connected yet</b>
        <span className="cw-line">on this map, but nothing hands them work: drag a dot onto main or a box, or click it</span>
      </div>
      <div className="mp-strip-boxes">
        {v.strip.map((b) => <MapBox key={b.id} b={b} inStrip facts={facts?.[b.id]} />)}
        {strangers.map((x) => (
          <div key={x.aid} className="mp-box mp-stranger" data-testid="map-stranger" data-agent={x.aid} data-state={x.state} title={`${x.name}: ${x.why}`}>
            <span className="mp-kind mono">agent <span className="mp-tag">not on this map</span></span>
            <b className="mp-name">{x.name}</b>
            <span className="mp-meta">{x.why} · {STATE_WORDS[x.state]}</span>
          </div>
        ))}
        {gone.map((id) => (
          <div key={id} className="mp-box mp-stranger" data-testid="map-removed" data-box={id} data-ghost="1" title={`${id}: the run used it; the map no longer has it`}>
            <span className="mp-kind mono">box <span className="mp-tag">removed since</span></span>
            <b className="mp-name">{id}</b>
          </div>
        ))}
        {none && <span className="cw-line" data-testid="map-strip-none">Nothing waiting.</span>}
      </div>
    </section>
  );
}
