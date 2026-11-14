// "Not connected yet" (3.6.0.0 R3): under the map, the boxes on it that nothing hands work to -- what you added and did
// not connect yet, and what the builder made (tagged `new`). Drag a box's dot onto main (or any box) to connect it, or
// click the dot for a list. A drop of a row from the list here adds it, to connect later.
import { MapBox } from "./MapBox";
import { useMap } from "./mapStore";
import { useMapView } from "./MapCanvas";

export function Strip() {
  const v = useMapView();
  const facts = useMap((s) => s.detail?.boxes);
  return (
    <section className="mp-strip" data-testid="map-strip" aria-label="Not connected yet">
      <div className="mp-strip-head">
        <b>Not connected yet</b>
        <span className="cw-line">on this map, but nothing hands them work: drag a dot onto main or a box, or click it</span>
      </div>
      <div className="mp-strip-boxes">
        {v.strip.length ? v.strip.map((b) => <MapBox key={b.id} b={b} inStrip facts={facts?.[b.id]} />)
          : <span className="cw-line" data-testid="map-strip-none">Nothing waiting.</span>}
      </div>
    </section>
  );
}
