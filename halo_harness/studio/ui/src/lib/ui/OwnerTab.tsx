// "Make this tab yours" (3.6.0.6 P, lib/ownerTab.ts): the one sentence and the one button, drawn in the notice row at
// the top of a tab that can only look (from the first draw: lib/owner.ts knows at boot, so nothing moves) and in the one
// toast of a refused write (lib/ui/Toast.tsx). The button reloads the tab for the person's own press only
// (`isTrusted`): a script's click does nothing, and a script's reload would get no proof anyway.
import type { MouseEvent } from "react";
import { ownerPage } from "../owner";
import { MAKE_YOURS, MAKE_YOURS_HOVER, TAB_LINE } from "../ownerTab";
import { Button } from "./Button";

function yours(e: MouseEvent<HTMLButtonElement>): void {
  if (e.nativeEvent.isTrusted) location.reload();
}

export function OwnerTabSays() {
  return (
    <>
      <span className="owner-tab-line" data-testid="owner-tab-line">{TAB_LINE}</span>
      <Button size="sm" onClick={yours} title={MAKE_YOURS_HOVER} data-testid="owner-tab-yours">{MAKE_YOURS}</Button>
    </>
  );
}

export function OwnerTabRow() {
  if (ownerPage()) return null;
  return (
    <div className="owner-tab-row" role="note" data-testid="owner-tab-row">
      <OwnerTabSays />
    </div>
  );
}
