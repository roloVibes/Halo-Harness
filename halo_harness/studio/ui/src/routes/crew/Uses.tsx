// What it may use and how careful (3.6.0.0 R1; the approved mock): one switch row per kind of tool, its plain line
// (what it can do on, what it cannot off), a skill or connected tool the agent has (a builder change, a copied
// starter) as a row of its own; then the three careful modes as radios, each with its line.
import { setForm } from "./store";
import { CAREFUL, USES, type Agent, type Careful } from "./types";

export function Switch({ on, label, onFlip, testid }: { on: boolean; label: string; onFlip: () => void; testid: string }) {
  return <button type="button" role="switch" className="cw-switch" aria-checked={on} aria-label={label} onClick={onFlip} data-testid={testid} />;
}

function extraWords(u: string): [string, string, string] {
  const [kind, name] = u.split(":");
  return kind === "skill"
    ? [`Skill: ${name}`, "a skill of yours it may load", "not loaded"]
    : [`Connected tool: ${name}`, `the ${name} server's tools`, `it cannot reach ${name}`];
}

export function Uses({ a }: { a: Agent }) {
  const flip = (u: string) => setForm({ uses: a.uses.includes(u) ? a.uses.filter((x) => x !== u) : [...a.uses, u] });
  const extras = a.uses.filter((u) => u.includes(":"));
  const rows: [string, string, string, string][] = [...USES, ...extras.map((u) => [u, ...extraWords(u)] as [string, string, string, string])];
  return (
    <div className="cw-field" data-testid="crew-uses">
      <span className="cw-label mono">What it may use</span>
      {rows.map(([k, title, onLine, offLine]) => {
        const on = a.uses.includes(k);
        return (
          <div className="cw-sw" key={k}>
            <Switch on={on} label={title} onFlip={() => flip(k)} testid={`crew-use-${k.replace(":", "-")}`} />
            <div className="cw-sw-text">
              <b>{title}</b>
              <span className="cw-line">{on ? onLine : `off: ${offLine}`}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function Careful({ a }: { a: Agent }) {
  return (
    <fieldset className="cw-field cw-careful" data-testid="crew-careful">
      <legend className="cw-label mono">How careful</legend>
      {CAREFUL.map(([k, title, line]) => (
        <label key={k} className="cw-radio" data-testid={`crew-careful-${k}`}>
          <input type="radio" name="crew-careful" value={k} checked={a.careful === k} onChange={() => setForm({ careful: k as Careful })} />
          <span>
            <b>{title}</b>
            <span className="cw-line">{line}</span>
          </span>
        </label>
      ))}
    </fieldset>
  );
}
