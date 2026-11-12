// The owner's yes for a grant that runs a pack's code (3.4.1.2, the review's PACKS-6 and SERVERS-2). A pack Halo does not
// ship, enabled or granted with studio-script, studio-routes, doctor, services, hooks or cli:<verb>, answers 409
// `needs_yes` with one line per grant saying what it gives (packs/grants.py WHAT); this dialog shows those lines and
// sends the same request again with `yes: true` only when the owner presses Grant. Cancel gives nothing.
import { Button, Dialog } from "../../../lib/ui";
import { act, mgr, useMgr } from "./store";

export function GrantDialog() {
  const g = useMgr((s) => s.granting);
  const close = () => mgr.update(() => ({ granting: null }));
  if (!g) return null;
  const yes = async () => {
    close();
    await act(g.path, { ...g.body, yes: true }, g.what);
  };
  return (
    <Dialog open onClose={close} title={`${g.what}?`} kicker="PACKS · A GRANT THAT RUNS ITS CODE" testid="pm-grant-dialog"
            cost={{ does: "gives the pack what each line says, until you take it back or disable the pack", costs: "nothing: no model call",
                    writes: "the pack's grants in ~/.halo/packs/state.json" }}
            footer={<><Button onClick={close}>Cancel</Button><Button variant="danger" onClick={() => void yes()} data-testid="pm-grant-yes">Grant</Button></>}>
      <ul className="pm-compat" data-testid="pm-grant-lines">{g.lines.map((l) => <li key={l}>{l.trim()}</li>)}</ul>
      <p className="muted">Each line is what the pack's own code can do once you grant it; the Grant toggle takes it back.</p>
    </Dialog>
  );
}
