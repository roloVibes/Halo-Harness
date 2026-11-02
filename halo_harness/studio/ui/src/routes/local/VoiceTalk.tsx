// Local -> Voice, Talk and the loop (3.3.9.0 R3): the session it talks to (this machine's running sessions; Session's
// chosen one first), that session's voice loop (`/voice on | off | ptt` through its control socket: the terminal's
// microphone, not this browser's), and Talk -- this browser's microphone into the same turn: the first press says what
// it does and what it costs (the permission, the servers it starts, the seconds) and starts on "Start talking"; a press
// records, the next one sends (press-then-press, like the TUI's push-to-talk); the transcript, the reply's audio played
// as it streams and kept in the <audio> sink, the reply's text and its latency card follow.
import { useEffect, useRef, useState } from "react";
import { Button } from "../../lib/ui";
import { micReady, Player, recording, startMic, stopMic } from "./voicemic";
import { loop, onAudio, pickSession, resetTalk, sendTalk, setTalk, target, useVoice, voice } from "./voicestore";

function Sessions() {
  const rows = useVoice((v) => v.view?.sessions);
  const sid = useVoice((v) => target(v));
  const st = useVoice((v) => v.view?.loop);
  const busy = useVoice((v) => v.busy === "loop");
  const said = useVoice((v) => v.said.loop);
  if (!rows) return null;
  if (!rows.length) {
    return <p className="mono muted" data-testid="voice-no-session">no running halo session here: start `halo` (Talk and the loop talk to one)</p>;
  }
  return (
    <div className="vc-sessions">
      <label className="mono">session{" "}
        <select value={sid} onChange={(e) => pickSession(e.target.value)} data-testid="voice-session-select">
          {rows.map((r) => <option key={r.session_id} value={r.session_id}>{r.session_id.slice(0, 8)} · {r.title || r.cwd}</option>)}
        </select>
      </label>
      <span className="og-chip mono" data-testid="voice-loop-state" data-on={st?.on || undefined}
            title="the session's own voice loop: the microphone of the machine it runs on">{st?.on ? `voice on: ${st.mode}` : "voice off"}</span>
      <Button size="sm" disabled={busy} onClick={() => void loop(st?.on ? "off" : "on")} data-testid="voice-loop-toggle"
              title={st?.on ? "/voice off in that session" : "/voice on in that session: its terminal's microphone, the servers started with their cost line"}>
        {st?.on ? "Voice off" : "Voice on"}</Button>
      <Button size="sm" variant="ghost" disabled={busy} onClick={() => void loop("ptt")} data-testid="voice-loop-ptt"
              title="/voice ptt: push-to-talk in that session (Ctrl+Space, again to send)">Push-to-talk</Button>
      {said && said.text && <span className="mono lc-said" data-ok={said.ok || undefined} data-testid="voice-loop-said">{said.text}</span>}
    </div>
  );
}

function Sink() {
  const ref = useRef<HTMLAudioElement>(null);
  const player = useRef(new Player());
  const [sunk, setSunk] = useState(0);
  const fresh = useVoice((v) => v.talk.state === "recording"); // a new utterance: the last reply's bytes go
  const done = useVoice((v) => v.talk.state === "done");
  useEffect(() => {
    return onAudio((b64, rate) => {
      setSunk(player.current.play(b64, rate));
    });
  }, []);
  useEffect(() => {
    if (!fresh) return;
    player.current.reset();
    setSunk(0);
  }, [fresh]);
  useEffect(() => {
    if (!done || !ref.current || !player.current.parts.length) return;
    const url = URL.createObjectURL(player.current.wav());
    ref.current.src = url;
    return () => {
      URL.revokeObjectURL(url);
    };
  }, [done]);
  return <audio ref={ref} controls className="vc-sink" data-testid="voice-talk-sink" data-bytes={sunk} />;
}

async function press(): Promise<void> {
  const s = voice.get();
  if (recording()) {
    const got = await stopMic();
    if (got.seconds < 0.1) return resetTalk();
    return sendTalk(got.b64, got.rate, got.seconds);
  }
  if (!s.asked) return setTalk({ state: "confirm" });
  try {
    resetTalk("recording");
    await startMic();
  } catch (e) {
    setTalk({ state: "error", error: `the microphone did not open: ${String(e)}` });
  }
}

export function VoiceTalk() {
  const talk = useVoice((v) => v.talk);
  const says = useVoice((v) => v.view?.talk?.confirm || "");
  const sid = useVoice((v) => target(v));
  const busy = talk.state === "sending" || talk.state === "working";
  const label = talk.state === "recording" ? "Send" : busy ? "Working..." : "Talk";
  return (
    <section className="pool-block" aria-label="Talk" data-testid="voice-talk-block">
      <div className="rail-label mono">TALK · THIS BROWSER'S MICROPHONE</div>
      <Sessions />
      <div className="vc-talk-row">
        <Button variant="primary" disabled={busy || !sid || !micReady()} onClick={() => void press()} data-testid="voice-talk"
                data-state={talk.state} data-seconds={talk.seconds || undefined} title={says}>{label}</Button>
        <span className="mono muted" data-testid="voice-talk-hint">
          {talk.state === "recording" ? "recording: press Send when you have said it (up to 30 s)" :
            !micReady() ? "this browser gives no microphone here (a page on 127.0.0.1 or localhost does)" : "press, speak, press again"}
        </span>
      </div>
      {talk.state === "confirm" && (
        <div className="vc-confirm-box" data-testid="voice-talk-confirm-box">
          <p className="mono" data-testid="voice-talk-confirm">{says}</p>
          <Button size="sm" variant="primary" onClick={() => { voice.update(() => ({ asked: true })); void press(); }}
                  data-testid="voice-talk-go">Start talking</Button>
          <Button size="sm" variant="ghost" onClick={() => resetTalk()}>Cancel</Button>
        </div>
      )}
      {talk.transcript && <p className="mono" data-testid="voice-talk-transcript">you said: {talk.transcript}</p>}
      {talk.notes.map((n, i) => <p key={`${i}|${n}`} className="mono muted" data-testid="voice-talk-note">{n}</p>)}
      {talk.reply && <p className="vc-reply" data-testid="voice-talk-reply">{talk.reply}</p>}
      {talk.line && <p className="mono muted" data-testid="voice-talk-line">{talk.line}</p>}
      {talk.state === "error" && <p className="mono lc-said" data-testid="voice-talk-error">{talk.error}</p>}
      <Sink />
    </section>
  );
}
