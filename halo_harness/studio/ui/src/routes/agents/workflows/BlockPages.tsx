// A block's own edit pages (3.3.16.3, the inspector's "one block per page"): Purpose -- the square's DOES line, one
// sentence, saved into the square's file of yours (a shipped or a pack's square says how to copy it first) -- and
// Agents -- who is inside, the lead first, each with its model (an `auto` one: picked per task) and what that model
// takes. Adding, removing and reordering agents is the canvas's drag (docs/STUDIO-agents.md "Blocks").
import { useState } from "react";
import { shortModel } from "../../../lib/modelName";
import { Button } from "../../../lib/ui";
import { TextBox } from "../../../lib/ui/TextBox";
import { ModelTakes } from "../../shared/ModelTakes";
import { modelRow, useRoles } from "../../roles/store";
import { agentsOf, type BlockAgent } from "../blocks/blockLayout";
import { saveContract, type Square } from "./store";
import { Head, ReadOnly } from "./WorkflowSummary";

export function PurposePage({ q }: { q: Square }) {
  const [text, setText] = useState(q.does);
  const [err, setErr] = useState("");
  return (
    <div className="wf-page" data-testid="wf-page-purpose">
      <Head q={q} title="Purpose" />
      <ReadOnly q={q} />
      <p className="muted">One sentence: what this block does for main. The block's title bar and the router's receipts say it.</p>
      <TextBox value={text} disabled={!q.writable} maxRows={5} onChange={(e) => setText(e.target.value)} data-testid="wf-field-does"
               aria-label={`${q.ref}: its purpose`} placeholder="Reads the PDFs and images main cannot, and hands back what it found." />
      {err && <p className="wf-err" data-testid="wf-page-error">{err}</p>}
      <div className="wf-page-actions" data-density="bar">
        <Button variant="primary" size="sm" disabled={!q.writable || !text.trim() || text.trim() === q.does}
                onClick={async () => setErr(await saveContract(q.ref, { does: text.trim() }))} data-testid="wf-page-save">Save</Button>
        <span className="muted mono">writes {q.path.split(/[\\/]/).slice(-2).join("/")}</span>
      </div>
    </div>
  );
}

function AgentLine({ a }: { a: BlockAgent }) {
  const row = useRoles((s) => modelRow(s, a.model));
  const auto = !a.model || a.model === "auto" || a.model === "measured";
  return (
    <li className="ri-row blk-page-agent" data-density="row" data-testid="wf-agent" data-bio={a.bio}>
      <span className="ri-row-title">{a.bio}{a.lead ? <span className="muted mono"> · lead</span> : null}</span>
      <span className="ri-row-state mono">{auto ? "auto: picked per task" : shortModel(a.model)}</span>
      {row && <ModelTakes row={row} />}
    </li>
  );
}

export function AgentsPage({ q }: { q: Square }) {
  const list = agentsOf(q);
  return (
    <div className="wf-page" data-testid="wf-page-agents">
      <Head q={q} title="Agents" />
      <ul className="ri-rows" aria-label={`Who is inside ${q.ref}`}>
        {list.map((a) => <AgentLine key={a.bio} a={a} />)}
      </ul>
      <p className="muted">{list.length === 1 ? "One agent runs this block: its lead." : `${list.length} agents: the lead hands the others their part.`}</p>
    </div>
  );
}
