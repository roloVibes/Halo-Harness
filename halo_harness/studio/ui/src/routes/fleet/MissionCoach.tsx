// The Mission panel's Coach face (3.0.9.0 R3): once a mission ended, the
// post-run coach's cards for it (GET fleet/missions/<id>/coach, lib/coach):
// a part that waited long for a harness owner, an edit refused outside a
// part's claims, two parts whose merge conflicted, outputs nobody wrote.
// A mission's changes go into its next plan, so its cards carry no Apply.
import { CoachCards } from "../../lib/coach/CoachCards";
import { applySuggestion } from "../orchestra/coachApply";
import { useMissions } from "./mstore";

export function MissionCoach() {
  const id = useMissions((s) => s.view?.mission.id || "");
  return id ? (
    <div className="fmi-coach" data-testid="fleet-mission-coach">
      <CoachCards kind="mission" run={id} onApply={applySuggestion} />
    </div>
  ) : null;
}
