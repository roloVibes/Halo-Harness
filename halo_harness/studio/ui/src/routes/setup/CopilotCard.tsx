// The Copilot card in Setup's Providers block (3.3.17.0 R2; studio/setup_copilot_api.py, docs/PROVIDERS-copilot.md):
// your work's Microsoft 365 Copilot. One fact per row (the status lines `halo copilot status` prints, each cut with an
// ellipsis and whole in its tooltip), the tenant and app id form, the door (workiq | graph-beta), Sign in / Sign out,
// the scopes an admin consents to as a copyable list and "Register the app" (docs/PROVIDERS-copilot.md's steps, in a
// closed disclosure: the bundle carries no remote URL, so the card holds the steps and names the doc). Sign in runs on the machine
// Studio runs on: a browser there gets Microsoft's page in a new tab and the card says "finish in the browser tab that
// opened"; a remote Studio (no browser there) shows the device code to type on any device. The card reads its state
// once when it mounts and polls only while a sign-in waits; nothing opens on load. Never a token on the page.
import { useEffect, useState } from "react";
import { api, ApiError } from "../../lib/api";
import { Button } from "../../lib/ui";
import { MiniForm } from "./cards";

type Signin = { state: string; flow: string; line: string; user_code: string; verification_uri: string };
export type CopilotState = {
  configured: boolean; signed_in: boolean; tenant: string; client_id: string; api: string; apis: string[]; web: boolean;
  timezone: string; status: string[]; consent_scopes: string[]; signin: Signin;
};
type Said = { ok: boolean; lines: string[] };

const STEPS = [
  "Entra admin center -> App registrations -> New registration (this organization only, no redirect yet).",
  "Authentication -> Add a platform -> Mobile and desktop: the redirect URI is localhost over http (any port); Allow public client flows: Yes.",
  "API permissions -> add the delegated scopes below, then Grant admin consent.",
  "Copy the Application (client) id and the Directory (tenant) id into the form above.",
];
const DOORS: Record<string, string> = {
  workiq: "the Work IQ API: production, billed as Copilot Credits (consumptive billing on the tenant)",
  "graph-beta": "Graph's preview Copilot Chat API: a Microsoft 365 Copilot licence per user",
};

function Row({ text, testid }: { text: string; testid: string }) {
  return <div className="su-cp-row mono" title={text} data-testid={testid}>{text}</div>;
}

export function CopilotCard() {
  const [s, setS] = useState<CopilotState | null>(null);
  const [said, setSaid] = useState<Said | null>(null);
  const [busy, setBusy] = useState(false);
  const load = () => api.get<CopilotState>("setup/copilot").then(setS, () => undefined);
  useEffect(() => void load(), []);
  const waiting = s?.signin.state === "waiting";
  useEffect(() => {
    if (!waiting) return;
    const t = window.setInterval(() => void load(), 1000);
    return () => window.clearInterval(t);
  }, [waiting]);
  const post = async (path: string, body: Record<string, unknown> = {}): Promise<boolean> => {
    setBusy(true);
    try {
      const { lines, ...rest } = await api.post<CopilotState & { lines?: string[] }>(path, body);
      setS(rest as CopilotState);
      setSaid(lines?.length ? { ok: true, lines } : null);
      return true;
    } catch (e) {
      setSaid({ ok: false, lines: e instanceof ApiError && e.problems.length ? e.problems : [e instanceof Error ? e.message : String(e)] });
      return false;
    } finally {
      setBusy(false);
    }
  };
  const copy = () =>
    navigator.clipboard.writeText((s?.consent_scopes || []).join(" ")).then(
      () => setSaid({ ok: true, lines: ["Copied the scopes."] }),
      () => setSaid({ ok: false, lines: ["The clipboard is closed to this page: select the list instead."] }),
    );
  if (!s) return null;
  const sign = s.signin;
  return (
    <section className="su-card su-cp" data-testid="setup-copilot" data-set={s.signed_in || undefined} data-signed-in={s.signed_in || undefined}>
      <div className="su-card-head">
        <span className="su-card-title">Copilot at work</span>
        <span className="su-mark mono" data-on={s.signed_in || undefined} data-testid="setup-copilot-mark">
          {s.signed_in ? "signed in" : s.configured ? "set up" : "-"}
        </span>
      </div>
      {s.status.map((line, i) => <Row key={i} text={line} testid="setup-copilot-status" />)}
      <div className="su-sub mono">Your app registration</div>
      <MiniForm card="copilot" button="Save" title="writes copilot.tenant and copilot.client_id to config.json"
                inputs={[{ id: "tenant", label: "Tenant (id or domain)", placeholder: s.tenant ? `now ${s.tenant}` : "pretend-tenant" },
                         { id: "client_id", label: "Application (client) id", placeholder: s.client_id ? `now ${s.client_id}` : "00000000-0000-0000-0000-000000000000" }]}
                onSave={(v) => post("setup/copilot/config", Object.fromEntries(Object.entries(v).filter(([, x]) => x.trim())))} />
      <div className="su-sub mono">Door</div>
      <div className="su-card-row">
        {s.apis.map((a) => (
          <Button key={a} size="sm" variant={a === s.api ? "primary" : "ghost"} aria-pressed={a === s.api} title={DOORS[a] || a}
                  disabled={busy || a === s.api} onClick={() => void post("setup/copilot/config", { api: a })}
                  data-testid="setup-copilot-api" data-id={a} data-on={a === s.api || undefined}>
            {a}
          </Button>
        ))}
      </div>
      <div className="su-sub mono">Sign in</div>
      <div className="su-card-row">
        <Button size="sm" variant="primary" disabled={busy || waiting || !s.configured} onClick={() => void post("setup/copilot/signin")}
                title={s.configured ? "opens Microsoft's sign-in page on the machine Studio runs on (a device code when it has no browser)" : "save the tenant and the app id first"}
                data-testid="setup-copilot-signin">
          {s.signed_in ? "Sign in again" : "Sign in"}
        </Button>
        <Button size="sm" variant="ghost" disabled={busy || !s.signed_in} onClick={() => void post("setup/copilot/signout")}
                title="removes the refresh token from the env file and forgets the access token" data-testid="setup-copilot-signout">
          Sign out
        </Button>
      </div>
      {sign.line && <Row text={sign.line} testid="setup-copilot-signin-line" />}
      {waiting && sign.flow === "device" && (
        <div className="su-cp-code mono" data-testid="setup-copilot-code" title={`enter it at ${sign.verification_uri}`}>{sign.user_code}</div>
      )}
      <div className="su-sub mono">Scopes an admin consents to</div>
      <pre className="su-detect mono" data-testid="setup-copilot-scopes">{s.consent_scopes.join("\n")}</pre>
      <div className="su-card-row">
        <Button size="sm" variant="ghost" onClick={() => void copy()} data-testid="setup-copilot-copy">Copy the scopes</Button>
      </div>
      <details className="su-more-box" data-testid="setup-copilot-register">
        <summary className="mono">Register the app (docs/PROVIDERS-copilot.md)</summary>
        <ol className="su-cp-steps">
          {STEPS.map((t) => <li key={t} title={t}>{t}</li>)}
        </ol>
      </details>
      {said && (
        <pre className="su-lines mono" data-ok={said.ok || undefined} data-testid="setup-copilot-lines">{said.lines.join("\n")}</pre>
      )}
    </section>
  );
}
