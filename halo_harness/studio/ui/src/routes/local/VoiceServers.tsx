// Local -> Voice, the speech servers and the catalog (3.3.9.0 R3; GET local/voice): one row per kind -- stt and tts --
// running (its model, device and url, Stop) or stopped (the model it would start and the cost line said before Start:
// device, memory, seconds), or on another halo (`voice.stt_server: stt@pc`, said with the line that sets it back);
// the steward's findings for that server under it. The catalog: each speech model's kind, engine, sizes on a GPU and
// on the CPU, present (its folder) or Download -- the size line first, shown as its confirmation, then the 3.3.5.0
// download job; a declared model says it has no engine in this build.
import { Button } from "../../lib/ui";
import { cancelDownload, download, server, useVoice, type CatalogRow, type VoiceServer } from "./voicestore";

function Server({ s }: { s: VoiceServer }) {
  const busy = useVoice((v) => v.busy === `server|${s.kind}`);
  const said = useVoice((v) => v.said[`server|${s.kind}`]);
  const state = s.remote ? "remote" : s.running ? "running" : "stopped";
  return (
    <li className="vc-server" data-testid="voice-server" data-kind={s.kind} data-state={state}>
      <div className="vc-server-head">
        <b className="mono">{s.kind === "stt" ? "speech-to-text" : "text-to-speech"}</b>
        <span className="mono" data-testid="voice-server-model">{s.model}</span>
        <span className="og-chip mono" data-testid="voice-server-state">{state}{s.device ? ` · ${s.device}` : ""}</span>
        {s.bundle && <span className="og-chip mono">the {s.bundle} bundle's pick</span>}
        {!s.remote && (s.running ? (
          <Button size="sm" disabled={busy} onClick={() => void server(s.kind, "stop")} data-testid="voice-server-stop"
                  title={`halo local stop ${s.kind}`}>Stop</Button>
        ) : (
          <Button size="sm" variant="primary" disabled={busy} onClick={() => void server(s.kind, "start")} data-testid="voice-server-start"
                  title={s.cost}>{busy ? "Starting..." : "Start"}</Button>
        ))}
      </div>
      <p className="mono muted vc-line" data-testid="voice-server-line">
        {s.remote || (s.running ? `on ${s.url}` : s.cost)}
      </p>
      {said && <p className="mono lc-said" data-ok={said.ok || undefined} data-testid="voice-server-said">{said.text}</p>}
      {s.findings.map((f) => (
        <p key={f.id} className="mono vc-finding" data-severity={f.severity} data-testid="voice-server-finding">{f.rule}: {f.finding}</p>
      ))}
    </li>
  );
}

function Model({ m }: { m: CatalogRow }) {
  const busy = useVoice((v) => v.busy === `dl|${m.name}`);
  const said = useVoice((v) => v.said[`dl|${m.name}`]);
  const confirm = useVoice((v) => v.confirm[m.name] || "");
  return (
    <tr data-testid="voice-catalog-row" data-name={m.name} data-present={m.present ? "yes" : undefined} data-built={m.built || undefined}>
      <td className="mono"><b>{m.name}</b></td>
      <td className="mono">{m.kind}</td>
      <td className="mono" title={m.repo + (m.verified ? "" : " (repo unverified)")}>{m.engine}</td>
      <td className="mono" title="download · on a GPU · on the CPU">{m.download_gb} GB · {m.gpu_gb} GB · {m.cpu_gb} GB</td>
      <td>
        {m.present ? <span className="mono muted" data-testid="voice-catalog-present" title={m.present}>present</span> : m.built ? (
          confirm ? (
            <span className="vc-confirm">
              <span className="mono" data-testid="voice-download-confirm">{confirm}</span>
              <Button size="sm" variant="primary" disabled={busy} onClick={() => void download(m.name, true)} data-testid="voice-download-yes">Download</Button>
              <Button size="sm" variant="ghost" onClick={() => cancelDownload(m.name)}>Cancel</Button>
            </span>
          ) : (
            <Button size="sm" disabled={busy} onClick={() => void download(m.name)} data-testid="voice-catalog-download"
                    title={`${m.size_line}: the size and the folder first, nothing downloads until you confirm`}>Download</Button>
          )
        ) : <span className="mono muted" title={m.cli}>declared</span>}
        {said && said.text && <span className="mono lc-said" data-ok={said.ok || undefined} data-testid="voice-download-said">{said.text}</span>}
      </td>
    </tr>
  );
}

export function VoiceServers() {
  const servers = useVoice((v) => v.view?.servers);
  const catalog = useVoice((v) => v.view?.catalog);
  return (
    <>
      <section className="pool-block" aria-label="Speech servers" data-testid="voice-servers">
        <div className="rail-label mono">SPEECH SERVERS</div>
        {servers ? (
          <ul className="vc-servers">{servers.map((s) => <Server key={s.kind} s={s} />)}</ul>
        ) : <p className="mono muted">reading the speech servers...</p>}
      </section>
      <section className="pool-block" aria-label="Speech models" data-testid="voice-catalog">
        <div className="rail-label mono">SPEECH MODELS · THE CATALOG</div>
        {catalog && (
          <div className="pool-scroll">
            <table className="pool-table" data-count={catalog.length}>
              <thead><tr><th>model</th><th>kind</th><th>engine</th><th>download · GPU · CPU</th><th /></tr></thead>
              <tbody>{catalog.map((m) => <Model key={m.name} m={m} />)}</tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
