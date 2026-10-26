// One Setup page (3.3.1.0 R1): the open step's block, alone, under a head
// that says which step it is and what it decides (docs/WIZARD.md rule 6), its
// help lines one click away (closed by default), then Back / Next at the
// foot (Next on the page before the Summary says Summary). The blocks are
// the 3.3.0.0 ones, unchanged inside, each with its own Save. Keys: Enter in
// a block's field is that block's Save (a card's form submits itself);
// Ctrl+Left / Ctrl+Right are Back / Next outside a text field, as in the
// terminal wizard. Focus lands on the content when a page opens (rule 7).
import { useEffect, useRef, type ComponentType, type KeyboardEvent } from "react";
import { Button } from "../../lib/ui";
import { HELP } from "../help";
import { useLoadState } from "./BlockFoot";
import { CheckDetail } from "./Check";
import { DefaultModelDetail } from "./DefaultModel";
import { LinuxFixesDetail } from "./LinuxFixes";
import { LocalModelsDetail } from "./LocalModels";
import { HELP_KEY, step, stepsOf, TITLES, usePage, type StepId } from "./pages";
import { PermissionsDetail } from "./Permissions";
import { ProvidersDetail } from "./Providers";
import { useSetup } from "./store";
import { SummaryDetail } from "./Summary";
import { TeamDetail } from "./Team";
import { ThemeDetail } from "./Theme";

const BODY: Record<StepId, ComponentType> = {
  providers: ProvidersDetail,
  local: LocalModelsDetail,
  model: DefaultModelDetail,
  permissions: PermissionsDetail,
  theme: ThemeDetail,
  team: TeamDetail,
  linux: LinuxFixesDetail,
  check: CheckDetail,
  summary: SummaryDetail,
};

const TEXT_TYPES = new Set(["text", "password", "search", "url", "email", "number"]);

function inTextField(t: EventTarget | null): boolean {
  const el = t as HTMLElement | null;
  if (!el) return false;
  if (el.tagName === "TEXTAREA" || el.isContentEditable) return true;
  return el.tagName === "INPUT" && TEXT_TYPES.has((el as HTMLInputElement).type);
}

/** Enter in a field outside a card's form: press this page's block Save when it can save. */
function enterSaves(e: KeyboardEvent<HTMLElement>, root: HTMLElement): boolean {
  const el = e.target as HTMLElement;
  if (el.tagName !== "INPUT" || el.closest("form")) return false;
  const type = (el as HTMLInputElement).type;
  if (type === "checkbox") return false;
  const btn = root.querySelector<HTMLButtonElement>("[data-testid=setup-save]");
  if (!btn || btn.disabled) return false;
  btn.click();
  return true;
}

/** Rule 7: the first field of the block, else its first choice, else the page itself. */
function focusContent(root: HTMLElement): void {
  const first = root.querySelector<HTMLElement>(".su-step-body input:not([disabled]), .su-step-body select, .su-step-body button:not([disabled])");
  (first || root).focus({ preventScroll: true });
  root.closest(".su-scroll")?.scrollTo({ top: 0 });
}

function Head({ page, n, of }: { page: StepId; n: number; of: number }) {
  const h = HELP[HELP_KEY[page]];
  const lines = (h?.help || "").split("\n").filter(Boolean);
  return (
    <header className="su-page-head">
      <div className="su-page-kicker mono">
        STEP {n} OF {of}
      </div>
      <h2 className="su-page-title" data-testid="setup-page-title">
        {TITLES[page]}
      </h2>
      {h?.about && <p className="su-lead muted">{h.about}</p>}
      {lines.length > 0 && (
        <details className="su-page-help" data-testid="setup-page-help">
          <summary className="mono">How this page works</summary>
          <ul>
            {lines.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        </details>
      )}
    </header>
  );
}

export function SetupPage() {
  const page = usePage();
  const steps = useSetup((s) => stepsOf(s.data, page).join("|")).split("|") as StepId[];
  const { ready } = useLoadState();
  const ref = useRef<HTMLElement>(null);
  const shown = useRef(false);
  const i = Math.max(0, steps.indexOf(page));
  const nextTo = steps[i + 1];
  useEffect(() => {
    if (!ref.current || !ready) return;
    if (shown.current) focusContent(ref.current);
    else ref.current.focus({ preventScroll: true }); // the page as it loads: the page itself, so a typed key lands in no field
    shown.current = true;
  }, [page, ready]);
  const Body = BODY[page];
  const onKey = (e: KeyboardEvent<HTMLElement>) => {
    if (e.key === "Enter" && !e.ctrlKey && !e.altKey && ref.current && enterSaves(e, ref.current)) {
      e.preventDefault();
      return;
    }
    if (e.ctrlKey && !e.altKey && !e.shiftKey && (e.key === "ArrowLeft" || e.key === "ArrowRight") && !inTextField(e.target)) {
      e.preventDefault();
      step(e.key === "ArrowLeft" ? -1 : 1);
    }
  };
  return (
    <section className="su-page-card" ref={ref} tabIndex={-1} onKeyDown={onKey} data-testid="setup-step-page" data-step={page}
             aria-label={`Setup: ${TITLES[page]}`}>
      <Head page={page} n={i + 1} of={steps.length} />
      <div className="su-step-body">
        <Body />
      </div>
      <footer className="su-page-foot">
        <Button variant="ghost" disabled={i === 0} onClick={() => step(-1)} data-testid="setup-back" title="the step before (Ctrl+Left)">
          Back
        </Button>
        <span className="su-page-where muted mono">
          {i + 1} / {steps.length}
        </span>
        {nextTo && (
          <Button variant="primary" onClick={() => step(1)} data-testid="setup-next" title={`${TITLES[nextTo]} (Ctrl+Right)`}>
            {nextTo === "summary" ? "Summary" : "Next"}
          </Button>
        )}
      </footer>
    </section>
  );
}
