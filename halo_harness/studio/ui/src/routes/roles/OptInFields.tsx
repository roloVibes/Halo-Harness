// The Lineup tab's three opt-in fields (3.1.8.0 R5, docs/ISOLATION.md): plain
// Field rows under the header, no panel of their own. Isolation is the mode
// (`isolation: container | user`; a mapping keeps its other keys, the YAML of
// the file edits them), Secrets broker is `secrets.broker`, Tool
// capabilities is the lineup-wide `tools.capabilities` (a tier or a card may
// name its own in the YAML). Each line is field_help.py's.
import { useHelpGroup } from "../../lib/fieldHelp";
import { edit } from "./actions";
import { ListIn, Pick } from "./controls";
import { useRoles } from "./store";
import type { Raw } from "./types";

type Rec = Record<string, unknown>;
const asRec = (v: unknown): Rec => (v && typeof v === "object" && !Array.isArray(v) ? (v as Rec) : {});

function isolationMode(v: unknown): string {
  if (typeof v === "string") return v;
  if (v && typeof v === "object") return String((v as Rec).mode ?? "container");
  return "";
}

function setIsolation(raw: Raw, mode: string): void {
  const cur = raw.isolation;
  if (!mode) delete raw.isolation;
  else if (cur && typeof cur === "object" && !Array.isArray(cur)) raw.isolation = { ...asRec(cur), mode };
  else raw.isolation = mode;
}

function setBroker(raw: Raw, broker: string): void {
  if (!broker) delete raw.secrets;
  else raw.secrets = { ...asRec(raw.secrets), broker };
}

function setCaps(raw: Raw, caps: string[]): void {
  const tools = { ...asRec(raw.tools) };
  if (caps.length) tools.capabilities = caps;
  else delete tools.capabilities;
  if (Object.keys(tools).length) raw.tools = tools;
  else delete raw.tools;
}

export function OptInFields() {
  const raw = useRoles((s) => s.raw);
  const h = useHelpGroup("assignment");
  if (!raw) return null;
  const caps = asRec(raw.tools).capabilities;
  return (
    <div className="re-form" data-testid="roles-optins">
      <Pick label="Isolation" hint={h.isolation} options={["", "container", "user"]} value={isolationMode(raw.isolation)}
            labels={{ "": "(none: workers run as you, here)" }} onChange={(v) => edit((r) => setIsolation(r, v))} testid="roles-isolation" />
      <Pick label="Secrets broker" hint={h.secrets} options={["", "1password", "env"]} value={String(asRec(raw.secrets).broker ?? "")}
            labels={{ "": "(none: the host's environment)" }} onChange={(v) => edit((r) => setBroker(r, v))} testid="roles-secrets" />
      <ListIn label="Tool capabilities" hint={h.capabilities} placeholder="read, edit, bash, web, agent, mcp:<server>, media, recall"
              value={Array.isArray(caps) ? (caps as string[]) : []} onCommit={(v) => edit((r) => setCaps(r, v))} testid="roles-capabilities" />
    </div>
  );
}
