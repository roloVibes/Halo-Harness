// Talk's browser side (3.3.9.0 R3): the microphone through getUserMedia (the permission asked once, by the browser),
// recorded as 16-bit mono PCM at the audio context's rate until the second press (a terminal-style press-then-press,
// the same as the TUI's push-to-talk), and the reply's PCM played as it streams in (one AudioBuffer per piece, queued
// back to back) and kept, so the page's <audio> sink can replay the whole reply as a WAV. No PortAudio, nothing to
// install: the browser is the audio device.
export const MAX_S = 30;

type Rec = { ctx: AudioContext; stream: MediaStream; node: ScriptProcessorNode; parts: Float32Array[]; started: number };
let rec: Rec | null = null;

export function micReady(): boolean {
  return !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
}

export async function startMic(): Promise<void> {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true } });
  const ctx = new AudioContext();
  if (ctx.state === "suspended") await ctx.resume(); // the press is the gesture that lets it run
  const src = ctx.createMediaStreamSource(stream);
  const node = ctx.createScriptProcessor(4096, 1, 1);
  const parts: Float32Array[] = [];
  node.onaudioprocess = (ev) => {
    parts.push(new Float32Array(ev.inputBuffer.getChannelData(0)));
  };
  src.connect(node);
  node.connect(ctx.destination);
  rec = { ctx, stream, node, parts, started: performance.now() };
}

export function recording(): boolean {
  return rec !== null;
}

/** The second press: the utterance as base64 PCM16, its rate and its seconds (cut at MAX_S). */
export async function stopMic(): Promise<{ b64: string; rate: number; seconds: number }> {
  const r = rec;
  rec = null;
  if (!r) return { b64: "", rate: 16000, seconds: 0 };
  r.node.disconnect();
  r.stream.getTracks().forEach((t) => t.stop());
  const rate = r.ctx.sampleRate;
  await r.ctx.close();
  const n = Math.min(r.parts.reduce((a, p) => a + p.length, 0), Math.floor(MAX_S * rate));
  const pcm = new Int16Array(n);
  let i = 0;
  for (const p of r.parts) {
    for (let j = 0; j < p.length && i < n; j += 1, i += 1) pcm[i] = Math.max(-32768, Math.min(32767, Math.round(p[j] * 32767)));
  }
  return { b64: toB64(new Uint8Array(pcm.buffer)), rate, seconds: n / rate };
}

function toB64(bytes: Uint8Array): string {
  let s = "";
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(s);
}

export function fromB64(b64: string): Uint8Array {
  const s = atob(b64);
  const out = new Uint8Array(s.length);
  for (let i = 0; i < s.length; i += 1) out[i] = s.charCodeAt(i);
  return out;
}

/** The reply's player: each piece scheduled after the last, and every byte kept for the sink's WAV. */
export class Player {
  private ctx: AudioContext | null = null;
  private at = 0;
  parts: Uint8Array[] = [];
  rate = 24000;

  play(b64: string, rate: number): number {
    const bytes = fromB64(b64);
    this.parts.push(bytes);
    this.rate = rate;
    try {
      if (!this.ctx) this.ctx = new AudioContext();
      if (this.ctx.state === "suspended") void this.ctx.resume();
      const pcm = new Int16Array(bytes.buffer, bytes.byteOffset, Math.floor(bytes.length / 2));
      const buf = this.ctx.createBuffer(1, Math.max(1, pcm.length), rate);
      const ch = buf.getChannelData(0);
      for (let i = 0; i < pcm.length; i += 1) ch[i] = pcm[i] / 32768;
      const node = this.ctx.createBufferSource();
      node.buffer = buf;
      node.connect(this.ctx.destination);
      this.at = Math.max(this.at, this.ctx.currentTime);
      node.start(this.at);
      this.at += buf.duration;
    } catch {
      // no audio output here: the sink keeps the bytes for the <audio> element
    }
    return this.parts.reduce((a, p) => a + p.length, 0);
  }

  /** The whole reply as a WAV (the <audio> sink's source). */
  wav(): Blob {
    const n = this.parts.reduce((a, p) => a + p.length, 0);
    const head = new DataView(new ArrayBuffer(44));
    const w = (o: number, t: string) => [...t].forEach((c, i) => head.setUint8(o + i, c.charCodeAt(0)));
    w(0, "RIFF");
    head.setUint32(4, 36 + n, true);
    w(8, "WAVEfmt ");
    head.setUint32(16, 16, true);
    head.setUint16(20, 1, true);
    head.setUint16(22, 1, true);
    head.setUint32(24, this.rate, true);
    head.setUint32(28, this.rate * 2, true);
    head.setUint16(32, 2, true);
    head.setUint16(34, 16, true);
    w(36, "data");
    head.setUint32(40, n, true);
    return new Blob([head.buffer, ...this.parts.map((p) => p.slice().buffer)], { type: "audio/wav" });
  }

  reset(): void {
    this.parts = [];
    this.at = 0;
  }
}
