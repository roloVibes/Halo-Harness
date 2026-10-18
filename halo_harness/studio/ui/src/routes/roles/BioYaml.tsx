// The bio form's YAML toggle (3.1.1.0 R3): the whole draft as the YAML the
// file would hold (`POST yaml {raw}`), editable; "Apply this YAML" turns it
// back into the draft (`POST yaml {yaml}`), so a key the form has no field
// for (hooks, a per-tool limit, models.temperature ...) is edited here.
// Nothing is saved until Save bio.
import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import { Button } from "../../lib/ui";
import { editBio } from "./bioActions";
import { useRoles } from "./store";
import { msg } from "./sync";
import type { Raw } from "./types";

export function BioYaml() {
  const draft = useRoles((s) => s.bioDraft);
  const [text, setText] = useState("");
  const [err, setErr] = useState("");
  useEffect(() => {
    let live = true;
    api.post<{ yaml: string }>("yaml", { raw: draft || {} })
      .then((r) => live && setText(r.yaml))
      .catch(() => live && setText(""));
    return () => {
      live = false;
    };
  }, [draft]);
  const apply = async () => {
    try {
      const r = await api.post<{ raw: Raw }>("yaml", { yaml: text });
      if (!r.raw || typeof r.raw !== "object" || Array.isArray(r.raw)) {
        setErr("a bio is a YAML mapping (key: value lines)");
        return;
      }
      setErr("");
      editBio((d) => {
        for (const k of Object.keys(d)) delete d[k];
        Object.assign(d, r.raw);
      });
    } catch (e) {
      setErr(msg(e));
    }
  };
  return (
    <div className="re-yaml" data-testid="bio-yaml">
      <textarea className="input mono re-yaml-text" spellCheck={false} rows={Math.min(24, text.split("\n").length + 1)} value={text}
                onChange={(e) => setText(e.target.value)} data-testid="bio-yaml-text" aria-label="The bio as YAML" />
      <div className="re-yaml-row">
        <Button size="sm" variant="primary" onClick={() => void apply()} data-testid="bio-yaml-apply">Apply this YAML</Button>
        {err && <span className="og-problems">{err}</span>}
      </div>
    </div>
  );
}
