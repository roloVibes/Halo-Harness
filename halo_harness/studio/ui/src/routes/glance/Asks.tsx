// What waits on you, on the glance (3.4.1.0 R4): each row of the attention queue (the same rows Attention lists, GET
// fleet/attention), oldest first, with its answers as large buttons -- the row's own a / r / s keys and their words,
// each with one line of what it does. An answer that needs words (a question's answer, a plan sent back) opens a text
// box first; a permission's deny takes an optional reason. Every answer goes through fleet/extras.ts answerRow, the
// path Attention's keys take (POST fleet/attention/answer with the token and the owner proof). `lit`: the ask a click
// on its notification opened.
import { useEffect, useRef, useState } from "react";
import { TextBox } from "../../lib/ui";
import { answerRow } from "../fleet/extras";
import { usePanels, type AttnRow } from "../fleet/pstore";
import { useNow } from "../fleet/store";
import { agoWords, useGlance } from "./data";

const KEYS = ["a", "r", "s"];
/** The owner proof needs WebCrypto (lib/owner.ts), which a browser gives only a secure page (127.0.0.1 and localhost are). */
const SIGNS = typeof crypto !== "undefined" && !!crypto.subtle;
const DOES: Record<string, string> = {
  "permission:a": "runs this one call", "permission:r": "refuses it; the agent goes on", "permission:s": "refuses it and stops the agent",
  "question:r": "sends your answer", "question:s": "stops the agent",
  "plan:a": "approves the plan: the work starts", "plan:r": "sends it back with your note", "plan:s": "sends it back and stops the agent",
  "approval:a": "accepts this step", "approval:r": "sends your edit", "approval:s": "stops at this step",
  "paused:a": "lets it go on", "paused:s": "stops it", "waiting:s": "stops the agent",
  "cap:a": "lifts the cap for today: the paused sessions go on",
};

function Reply({ row, k, done }: { row: AttnRow; k: string; done: () => void }) {
  const [text, setText] = useState("");
  const box = useRef<HTMLTextAreaElement>(null);
  useEffect(() => box.current?.focus(), []);
  const optional = row.kind === "permission";
  const send = () => (optional || text.trim() ? void answerRow(row, k, text.trim()).then(done) : undefined);
  return (
    <div className="gz-reply">
      <TextBox ref={box} className="gz-reply-box" maxRows={6} value={text} onChange={(e) => setText(e.target.value)} data-testid="glance-reply"
                placeholder={optional ? "why not (optional)" : `${row.keys[k]}: type it, then Send`} aria-label={row.keys[k]} />
      <div className="gz-reply-acts">
        <button type="button" className="gz-key" data-key={k} disabled={!optional && !text.trim()} onClick={send} data-testid="glance-send">
          <span className="gz-key-word">Send</span>
          <span className="gz-key-does">{DOES[`${row.kind}:${k}`] || row.keys[k]}</span>
        </button>
        <button type="button" className="gz-key gz-key-quiet" onClick={done}>
          <span className="gz-key-word">Cancel</span>
          <span className="gz-key-does">sends nothing</span>
        </button>
      </div>
    </div>
  );
}

function Ask({ row, now }: { row: AttnRow; now: number }) {
  const [replying, setReplying] = useState("");
  const [busy, setBusy] = useState(false);
  const lit = useGlance((s) => s.lit === row.id);
  const ref = useRef<HTMLLIElement>(null);
  useEffect(() => {
    if (lit) ref.current?.scrollIntoView({ block: "center" });
  }, [lit]);
  const press = (k: string) => {
    if (k === "r" && row.text_for === "r") return setReplying(k);
    setBusy(true);
    void answerRow(row, k).finally(() => setBusy(false));
  };
  return (
    <li ref={ref} className="gz-ask" data-testid="glance-ask" data-kind={row.kind} data-id={row.id} data-lit={lit || undefined}>
      <div className="gz-ask-what">{row.what}</div>
      <div className="gz-ask-who mono muted">
        {[row.session || row.harness_name, row.agent, `waiting ${agoWords(row.since, now).replace(" ago", "")}`].filter(Boolean).join(" · ")}
      </div>
      {row.detail && <div className="gz-ask-detail mono">{row.detail}</div>}
      {replying ? (
        <Reply row={row} k={replying} done={() => setReplying("")} />
      ) : (
        <div className="gz-keys">
          {KEYS.filter((k) => row.keys[k]).map((k) => (
            <button key={k} type="button" className="gz-key" data-key={k} data-testid="glance-key" disabled={busy} onClick={() => press(k)}>
              <span className="gz-key-word">{row.keys[k]}</span>
              <span className="gz-key-does">{DOES[`${row.kind}:${k}`] || (k === "r" && row.text_for === "r" ? "opens a box for your words" : row.keys[k])}</span>
            </button>
          ))}
        </div>
      )}
    </li>
  );
}

export function Asks() {
  const rows = usePanels((s) => s.attention);
  const loaded = usePanels((s) => s.attnLoaded);
  const error = usePanels((s) => s.attnError);
  const now = useNow(rows.length > 0, 5000);
  return (
    <section className="gz-block" data-testid="glance-asks" data-count={rows.length} aria-label="What waits on you">
      <h2 className="gz-h mono">WAITS ON YOU{rows.length ? ` · ${rows.length}` : ""}</h2>
      {rows.length > 0 && !SIGNS && (
        <p className="gz-bad" data-testid="glance-no-proof">This browser cannot sign an answer on this address (no WebCrypto off a secure page): Studio refuses it. Open the page at 127.0.0.1 or localhost.</p>
      )}
      {!loaded ? (
        <p className="muted">reading what waits on you...</p>
      ) : error && !rows.length ? (
        <p className="gz-bad" data-testid="glance-asks-error">Studio could not read the queue: {error}</p>
      ) : !rows.length ? (
        <p className="muted" data-testid="glance-asks-none">Nothing waits on you.</p>
      ) : (
        <ul className="gz-asks">
          {rows.map((r) => <Ask key={r.id} row={r} now={now} />)}
        </ul>
      )}
    </section>
  );
}
