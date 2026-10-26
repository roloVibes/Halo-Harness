// Setup's step rail (3.3.1.0 R1), across the top of every page, in the
// terminal wizard's order and words (tui/dialogs/step_rail.py, docs/WIZARD.md
// rule 4): the current step highlighted, a done step ticked, a step still to
// do plain; a click opens that step's page. Under it the rail's own one-line
// summary (what was 3.3.0.0's status strip): the providers set up, the default
// model, the lineup, the permission mode, the theme and the last check; a page
// `halo init` opened (`?first=1`) leads it with "set up this box". Nothing
// opens on its own here: the help is the ? in the header.
import { useFirstRun } from "./door";
import { goto, lineupWord, stateOf, stepsOf, TITLES, usePage, valueOf, type StepId } from "./pages";
import { providersSet, useSetup } from "./store";
import { lastCheckWord } from "./checkStore";

/** 3.3.0.0 R4: the page `halo init` opened (`?first=1`) leads the summary with what it is for. */
function FirstCell() {
  if (!useFirstRun()) return null;
  return (
    <span className="su-cell su-first" data-testid="setup-strip-first">
      <span className="su-cell-value mono">set up this box:</span>{" "}
      <span className="su-cell-label mono">one step a page, Next to go on; the Summary lists what is set</span>
    </span>
  );
}

function Strip() {
  const d = useSetup((s) => s.data);
  if (!d)
    return (
      <div className="su-strip mono muted" data-testid="setup-strip">
        <FirstCell />
        reading the setup...
      </div>
    );
  const set = providersSet(d);
  const cells: [string, string, string][] = [
    ["provider", "Provider", set.length ? set.join(", ") : "no provider set"],
    ["model", "Default model", d.model || "not set"],
    ["lineup", "Lineup", lineupWord(d)],
    ["permissions", "Permissions", d.permission_mode || "not set"],
    ["theme", "Theme", d.theme || `${d.theme_default} (default)`],
    ["check", "Last check", lastCheckWord(d.last_check)],
  ];
  return (
    <div className="su-strip" role="status" aria-label="This setup" data-testid="setup-strip">
      <FirstCell />
      {cells.map(([k, label, value]) => (
        <span key={k} className="su-cell" data-testid="setup-strip-cell" data-key={k}
              data-unset={value === "no provider set" || value === "not set" || value === "not run" || / failed /.test(value) || undefined}>
          <span className="su-cell-label mono">{label}:</span> <span className="su-cell-value mono">{value}</span>
        </span>
      ))}
    </div>
  );
}

export function SetupRail() {
  const page = usePage();
  // one string per read (a new array each read would redraw forever), split back into the steps
  const joined = useSetup((s) => stepsOf(s.data, page).map((st) => [st, stateOf(s.data, st, page), valueOf(s.data, st)].join("~")).join("|"));
  const steps = joined.split("|").map((x) => x.split("~") as [StepId, string, string]);
  return (
    <div className="su-top">
      <nav className="su-steps" aria-label="Setup steps" data-testid="setup-rail">
        <ol className="su-steps-list">
          {steps.map(([st, state, word], i) => (
            <li key={st} className="su-steps-item">
              {i > 0 && <span className="su-steps-sep mono" aria-hidden="true">&gt;</span>}
              <button type="button" className="su-step" onClick={() => goto(st)} data-testid="setup-rail-step" data-step={st} data-state={state}
                      data-word={word || undefined} aria-current={state === "current" ? "step" : undefined}
                      title={word ? `${TITLES[st]}: ${word}` : TITLES[st]}>
                <span className="su-step-n mono" aria-hidden="true">{state === "done" ? "✓" : i + 1}</span>
                <span className="su-step-title">{TITLES[st]}</span>
              </button>
            </li>
          ))}
        </ol>
      </nav>
      <Strip />
    </div>
  );
}
