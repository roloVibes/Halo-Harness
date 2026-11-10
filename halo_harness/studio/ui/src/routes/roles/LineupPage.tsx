// 3.3.16.0 R1b, "one block per page": Edit on a summary row opens that block alone in the inspector -- a header with
// Back (Esc too), the block's title, its enforcement chip, the YAML toggle and the page's `?` (that block's field lines
// only); one sentence of what this does (field_help.py's LINEUP_SECTIONS line); when the block is not set, "not set =
// Halo does ..." (LINEUP_DEFAULTS, the code's real default); then the block's form: SectionForm as it was, or the
// header's three fields, the opt-ins, the swap preview. A change is an edit of the draft (Save / Revert as before).
import { useEffect, useState, type KeyboardEvent, type ReactNode } from "react";
import { api } from "../../lib/api";
import { useHelpGroup } from "../../lib/fieldHelp";
import { Button, TextBox } from "../../lib/ui";
import { edit } from "./actions";
import { blockSet, lineupBlock } from "./defaults";
import { LineupHeader } from "./LineupHeader";
import { LineupSched } from "./LineupSched";
import { OptInFields } from "./OptInFields";
import { closePage } from "./pages";
import { SectionForm } from "./SectionForm";
import { InHelp, TabHelp, useBlockLines, type HelpLine } from "./TabHelp";
import { sectionDef, type SectionDef } from "./sections";
import { useRoles } from "./store";
import { msg } from "./sync";

function YamlBox({ def }: { def: SectionDef }) {
  const body = useRoles((s) => s.raw?.[def.name]);
  const [text, setText] = useState("");
  const [err, setErr] = useState("");
  useEffect(() => {
    let live = true;
    api.post<{ yaml: string }>("yaml", { raw: body === undefined ? {} : { [def.name]: body } })
      .then((r) => live && setText(body === undefined ? `${def.name}:\n` : r.yaml))
      .catch(() => live && setText(`${def.name}:\n`));
    return () => {
      live = false;
    };
  }, [body, def.name]);
  const apply = async () => {
    try {
      const r = await api.post<{ raw: Record<string, unknown> }>("yaml", { yaml: text });
      const v = r.raw[def.name];
      if (def.list ? v !== undefined && v !== null && !Array.isArray(v) : v !== undefined && v !== null && (typeof v !== "object" || Array.isArray(v))) {
        setErr(def.list ? `${def.name} must be a YAML list` : `${def.name} must be a YAML mapping`);
        return;
      }
      setErr("");
      edit((raw) => {
        if (v === undefined || v === null) delete raw[def.name];
        else raw[def.name] = v;
      });
    } catch (e) {
      setErr(msg(e));
    }
  };
  return (
    <div className="re-yaml">
      <TextBox mono className="re-yaml-text" spellCheck={false} value={text}
               onChange={(e) => setText(e.target.value)} data-testid={`roles-yaml-${def.name}`} aria-label={`${def.name} as YAML`} />
      <div className="re-yaml-row" data-density="bar">
        <Button size="sm" variant="primary" onClick={() => void apply()} data-testid={`roles-yaml-apply-${def.name}`}>Apply this YAML</Button>
        {err && <span className="og-problems">{err}</span>}
      </div>
    </div>
  );
}

type FrameProps = { id: string; title: string; what?: string; dflt?: string; set: boolean; help: HelpLine[]; helpId?: string; tools?: ReactNode; children: ReactNode };

/** One page: Back, the title, the tools (enforcement chip, YAML), the `?`; what this does; the default when unset. */
export function PageFrame({ id, title, what, dflt, set, help, helpId = "roles-lineup-help", tools, children }: FrameProps) {
  const esc = (ev: KeyboardEvent<HTMLElement>) => {
    if (ev.key !== "Escape" || ev.defaultPrevented) return;
    ev.preventDefault();
    ev.stopPropagation();
    closePage();
  };
  return (
    <InHelp>
      <section className="ri-page" data-testid={`roles-page-${id}`} data-block={id} data-set={set || undefined} onKeyDown={esc}>
        <header className="ri-page-head" data-density="bar">
          <Button size="sm" variant="ghost" onClick={closePage} data-testid="roles-page-back" title="Back to the summary (Esc); the draft keeps your edits">
            ‹ Back
          </Button>
          <b className="ri-page-title">{title}</b>
          {tools}
          <TabHelp lines={help} testid={helpId} />
        </header>
        {what && <p className="ri-page-what" data-testid={`roles-about-${id}`}>{what}</p>}
        {!set && dflt && <p className="ri-page-default mono" data-testid="roles-page-default">not set = Halo does: {dflt}</p>}
        {children}
      </section>
    </InHelp>
  );
}

/** The open lineup's block `id` on its own page. */
export function LineupPage({ id }: { id: string }) {
  const name = useRoles((s) => s.name);
  const set = useRoles((s) => blockSet(id, s.raw));
  const enf = useRoles((s) => s.current?.enforcement?.[id]);
  const sections = useHelpGroup("lineup_sections");
  const defaults = useHelpGroup("lineup_defaults");
  const help = useBlockLines(id);
  const [yaml, setYaml] = useState(false);
  const block = lineupBlock(id);
  const def = sectionDef(id);
  if (!block) return null;
  const what = def ? sections[id] : id === "description" ? "what this lineup is for and how its cards work together; members read the about as 'How this team works'"
    : id === "workers" ? "where an Orchestra run's workers run, where their secrets come from, and the tools every member may have"
    : "which models each card keeps loaded, and what one pass of the lineup costs in swaps";
  const tools = def ? (
    <>
      {enf?.[0] && <span className="og-chip mono" title={enf[1]}>{enf[0]}</span>}
      <button className="re-yaml-toggle mono" aria-pressed={yaml} onClick={() => setYaml(!yaml)} data-testid={`roles-yaml-toggle-${id}`}
              title="Edit this section as YAML">YAML</button>
    </>
  ) : null;
  return (
    <PageFrame id={id} title={block.title} what={what} dflt={block.defaultKey ? defaults[block.defaultKey] : undefined} set={set} help={help} tools={tools}>
      {def ? (yaml ? <YamlBox def={def} /> : <SectionForm def={def} />)
        : id === "description" ? <LineupHeader />
        : id === "workers" ? <OptInFields />
        : <LineupSched name={name} empty />}
    </PageFrame>
  );
}
