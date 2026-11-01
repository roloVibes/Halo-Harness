// Local -> Pool, the members (3.3.8.0 R1; GET local/pool/members): one row per member of pool.json -- its host and
// RPC port (a paired host's name, `local`, or a worker's address), the GPU and its total, the FREE VRAM the split
// follows (usable with the helper out, minus what is resident, minus what bundles claim: the title says each), the
// link the host card reads ("2.5 GbE", "Wi-Fi (adapter)"), the RTT of the last Scan ("12 ms -- Wi-Fi?"), its share of
// the tensor split, and Remove (pool.json only: nothing on that machine changes). A member whose VRAM no card reads
// says so, with the --vram line that states it.
import { Button } from "../../lib/ui";
import { gb, removeMember, usePool, type Member } from "./poolstore";

function Row({ m }: { m: Member }) {
  const busy = usePool((s) => s.busy === `rm|${m.name}`);
  const said = usePool((s) => s.said[`rm|${m.name}`]);
  const vram = m.free_gb == null ? "not read" : `${gb(m.free_gb)} of ${gb(m.total_gb)}`;
  const parts = [`usable ${gb(m.usable_gb)}`, m.helper_gb ? `helper ${gb(m.helper_gb)} out` : "",
    m.resident.length ? `resident ${gb(m.resident_gb)} (${m.resident.join(", ")})` : "", m.claims_gb ? `claimed ${gb(m.claims_gb)}` : ""];
  return (
    <tr data-testid="pool-member" data-name={m.name} data-kind={m.kind} data-vram={m.vram_source} data-link={m.link?.type || "unknown"}>
      <td className="mono"><b>{m.name}</b></td>
      <td className="mono" title={m.kind === "paired" ? `the paired host ${m.host} at ${m.addr}` : m.kind === "local" ? "this machine" : "an address: no halo host there"}>
        {m.host}:{m.rpc_port}
      </td>
      <td className="mono" data-testid="pool-member-gpu">{m.gpu || "—"}</td>
      <td className="mono" data-testid="pool-member-vram" title={`${m.source}${m.vram_source === "card" ? `\n${parts.filter(Boolean).join(" · ")}` : ""}`}>
        {vram}{m.vram_source === "stated" ? " (as you stated it)" : ""}
      </td>
      <td className="mono" data-testid="pool-member-link" title="the adapter that carries the host's own address, read by halo host there">{m.link_word}</td>
      <td className="mono" data-testid="pool-member-rtt" data-wifi={m.rtt_word.includes("Wi-Fi") || undefined}
          title="a TCP connect to its rpc-server port during the last Scan; the adapter type, when the card has it, wins">{m.rtt_word}</td>
      <td className="mono" data-testid="pool-member-share" title="its share of --tensor-split (from the free VRAM)">{m.share_word || "—"}</td>
      <td>
        <Button size="sm" variant="ghost" disabled={busy} onClick={() => void removeMember(m.name)} data-testid="pool-member-remove"
                title={`halo pool remove ${m.name}: pool.json only, nothing on that machine changes`}>Remove</Button>
        {said && !said.ok && <span className="mono lc-said" data-testid="pool-member-said">{said.text}</span>}
      </td>
    </tr>
  );
}

export function PoolMembers() {
  const v = usePool((s) => s.members);
  if (!v) return <p className="mono muted">reading the members...</p>;
  return (
    <section className="pool-block" data-testid="pool-members" data-count={v.members.length} aria-label="Members">
      <div className="rail-label mono">MEMBERS · {v.file.replace(/\\/g, "/").split("/").slice(-2).join("/")}</div>
      <p className="mono" data-testid="pool-members-head">{v.head}</p>
      {v.problems.length > 0 && (
        <ul className="pool-problems mono" data-testid="pool-problems">{v.problems.map((p) => <li key={p}>{p}</li>)}</ul>
      )}
      {v.members.length > 0 && (
        <div className="pool-scroll">
          <table className="pool-table">
            <thead><tr><th>member</th><th>host:port</th><th>GPU</th><th>free of total</th><th>link</th><th>RTT</th><th>share</th><th /></tr></thead>
            <tbody>{v.members.map((m) => <Row key={m.name} m={m} />)}</tbody>
          </table>
        </div>
      )}
      {!v.members.length && (
        <p className="mono muted" data-testid="pool-members-none">
          Add a member from the Scan below, or from a terminal: <code>halo pool add worker1 worker1.local:{v.rpc_port}</code>
          {" "}(a paired host by its name; <code>--vram GB</code> for a worker no card reads).
        </p>
      )}
    </section>
  );
}
