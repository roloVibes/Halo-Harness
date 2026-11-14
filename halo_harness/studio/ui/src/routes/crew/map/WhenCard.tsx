// The When card (3.6.0.0 R3, the design's "Connecting"): it opens at the line -- right after a connect, or from the
// line's label -- and says in words when the one box hands work to the other: always / when the task needs (a PDF, an
// image, audio, video, code, a review) / when the task says (words) / only when I ask / main decides per task. Save
// writes it (a receipt with Undo follows); Cancel on a line just made takes it back out (its Undo); "Take the line out"
// removes it (the box then waits under Not connected yet). The connect dot's list of targets is here too (PickList).
import { useLayoutEffect, useRef, useState } from "react";
import { Button } from "../../../lib/ui";
import { closeWhen, connect, removeLine, setPick, setWhen, undoLast, useMap, type WhenAt } from "./mapStore";
import { NEEDS, whenWords, type LineWhen, type MapLine } from "./mapTypes";
import { useMapView } from "./MapCanvas";
import { targets } from "./view";

type Mode = "always" | "needs" | "says" | "ask" | "main-decides";

function usePlace(anchor: string) {
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState({ left: 16, top: 80 });
  useLayoutEffect(() => { // the card opens at the line: the line's label is brought into view first
    document.querySelector(anchor)?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [anchor]);
  useLayoutEffect(() => {
    const a = document.querySelector(anchor)?.getBoundingClientRect();
    const me = ref.current?.getBoundingClientRect();
    if (!a || !me) return;
    const left = Math.max(8, Math.min(window.innerWidth - me.width - 8, a.left));
    const below = a.bottom + 8;
    const fits = below + me.height <= window.innerHeight - 8;
    const top = Math.max(8, Math.min(window.innerHeight - me.height - 8, fits ? below : a.top - me.height - 8));
    if (Math.abs(left - pos.left) > 1 || Math.abs(top - pos.top) > 1) setPos({ left, top });
  });
  return { ref, pos };
}

function modeOf(w?: LineWhen): Mode {
  if (!w || w === "main-decides") return "main-decides";
  if (w === "always" || w === "ask") return w;
  return "needs" in w ? "needs" : "says";
}

export function WhenCard() {
  const at = useMap((s) => s.when);
  const line = useMap((s) => s.detail?.map.lines.find((l) => at && l.from === at.from && l.to === at.to));
  if (!at || !line) return null;
  return <Card key={`${at.from}>${at.to}`} at={at} line={line} />;
}

function Card({ at, line }: { at: WhenAt; line: MapLine }) {
  const { ref, pos } = usePlace(`[data-testid=map-label][data-from="${at.from}"][data-to="${at.to}"]`);
  const w0 = line.when;
  const [mode, setMode] = useState<Mode>(modeOf(w0));
  const [needs, setNeeds] = useState<string[]>(w0 && typeof w0 === "object" && "needs" in w0 ? w0.needs : []);
  const [words, setWords] = useState(w0 && typeof w0 === "object" && "says" in w0 ? w0.says.join(", ") : "");
  const said = () => words.split(",").map((w) => w.trim().toLowerCase()).filter(Boolean);
  const when = (): LineWhen => mode === "needs" ? { needs: needs.length ? needs : ["pdf"] }
    : mode === "says" ? { says: said().length ? said() : ["review"] } : mode;
  const pick = (m: Mode) => setMode(m);
  const opt = (m: Mode, label: string) => (
    <label className="mp-opt"><input type="radio" name="mp-when" checked={mode === m} onChange={() => pick(m)} data-testid={`map-when-${m}`} /> {label}</label>
  );
  return (
    <div className="mp-pop" role="dialog" aria-label="When" ref={ref} style={{ left: pos.left, top: pos.top }} data-testid="map-when-card">
      <b>When does {at.from} hand work to {at.to}?</b>
      {opt("always", "Always")}
      {opt("needs", "When the task needs:")}
      <div className="mp-chips">
        {NEEDS.map(([k, label]) => (
          <button key={k} type="button" className="btn mp-chip" aria-pressed={needs.includes(k)} data-testid="map-when-need" data-need={k}
                  onClick={() => { setNeeds((n) => (n.includes(k) ? n.filter((x) => x !== k) : [...n, k])); setMode("needs"); }}>{label}</button>
        ))}
      </div>
      {opt("says", "When the task says:")}
      <input className="input mp-words" value={words} placeholder="review, test" aria-label="The words" data-testid="map-when-words"
             onChange={(e) => { setWords(e.target.value); setMode("says"); }} />
      {opt("ask", "Only when I ask for it")}
      {opt("main-decides", "Main decides per task (it picks among everything it can hand to)")}
      <span className="cw-line">Saves in the map; a running session takes it at its next hand-off.</span>
      <div className="mp-pop-row">
        <Button onClick={() => void removeLine(line)} data-testid="map-when-remove">Take the line out</Button>
        <span className="spacer" />
        <Button onClick={() => (at.fresh ? void undoLast().then(closeWhen) : closeWhen())} data-testid="map-when-cancel">Cancel</Button>
        <Button variant="primary" onClick={() => void setWhen(at.from, at.to, when(), whenWords(when()))} data-testid="map-when-save">Save</Button>
      </div>
    </div>
  );
}

export function PickList() {
  const from = useMap((s) => s.pick);
  const v = useMapView();
  const { ref, pos } = usePlace(from ? `[data-testid=map-dot][data-from="${from}"]` : "body");
  if (!from) return null;
  const inStrip = v.strip.some((b) => b.id === from);
  const list = inStrip ? [...v.boxes.filter((b) => !b.ghost)] : targets(v, from);
  return (
    <div className="mp-pop" role="dialog" aria-label="Connect" ref={ref} style={{ left: pos.left, top: pos.top }} data-testid="map-pick">
      <b>{inStrip ? `Who hands work to ${from}?` : `${from} hands work to ...`}</b>
      {list.map((b) => (
        <button key={b.id} type="button" className="btn mp-pick-row" data-testid="map-pick-row" data-to={b.id}
                onClick={() => { setPick(from); void (inStrip ? connect(b.id, from) : connect(from, b.id)); }}>
          <b>{b.name}</b> <span className="mp-muted">· {b.main ? "main" : b.kind}</span>
        </button>
      ))}
      {!list.length && <span className="cw-line">Nothing it can hand work to: add a box first (a line may not make a circle).</span>}
      <div className="mp-pop-row"><span className="spacer" /><Button onClick={() => setPick(from)} data-testid="map-pick-cancel">Cancel</Button></div>
    </div>
  );
}
