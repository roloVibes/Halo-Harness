// The Team stage's model (3.1.4.0 R4): a stage has no model field of its own
// (team/spec.py) -- an agent stage runs its lead member under that member's
// lineup as its card's bio, an Orchestra stage runs on the role table -- so
// the stage face says what it runs on ("runs on: <model>", where that comes
// from) with a link that opens that lineup's card in Roles, the Inspector's
// MODEL strip focused, where the model is changed.
import { useHelpGroup } from "../../lib/fieldHelp";
import { openCardModel } from "../roles/modelActions";
import { shortRef } from "../shared/catalog";
import { useResolved } from "../shared/resolve";
import { memberOf, rowOf, specOf, useTeam } from "./store";

export function StageModel({ id }: { id: string }) {
  const spec = useTeam((s) => specOf(s, id));
  const row = useTeam((s) => rowOf(s, id));
  const leadName = row?.lead || spec?.lead || row?.members?.[0] || spec?.members?.[0] || "";
  const member = useTeam((s) => (leadName ? memberOf(s, leadName) : undefined));
  const orchestra = spec?.kind === "orchestra";
  const role = orchestra ? String((spec?.goal as { lead?: string } | null)?.lead || "main") : member?.role || "main";
  const got = useResolved(role, orchestra ? "" : member?.lineup || "");
  const help = useHelpGroup("model_select");
  if (!spec || (spec.kind !== "agent" && !orchestra)) return null;
  const from = !got ? "" : got.source === "lineup" ? `${leadName}'s card (${role}) in ${got.lineup}`
    : got.source === "roles" ? `the role table's ${role}` : got.source === "default" ? "the default model" : "";
  return (
    <div className="tm-model mono" data-testid="team-stage-model" data-ref={got?.ref || ""} data-source={got?.source || ""} title={help.team}>
      <span className="glance-kicker">MODEL</span>
      <span>runs on: <b>{got ? (got.ref ? shortRef(got.ref) : "no model resolves") : "..."}</b></span>
      {from && <span className="muted">{from}</span>}
      {got?.lineup && got.card && (
        <button type="button" className="og-link" onClick={() => void openCardModel(got.lineup, got.card)} data-testid="team-stage-model-link"
                title="Open that lineup's card in Roles: its MODEL strip changes the model">
          change it in Roles
        </button>
      )}
    </div>
  );
}
