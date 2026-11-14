// Setup's step rail (3.3.1.0 R1), across the top of every page, in the
// terminal wizard's order and words (tui/dialogs/step_rail.py, docs/WIZARD.md
// rule 4): the current step highlighted, a done step ticked, a step still to
// do plain; a click opens that step's page. Under it the rail's own one-line
// summary (what was 3.3.0.0's status strip): the providers set up, the default
// model, the lineup, the permission mode, the theme and the last check; a page
// `halo init` opened (`?first=1`) leads it with "set up this box". Nothing
// opens on its own here: the help is the ? in the header. 3.3.11.0 R3: a pack's own blocks follow the core steps
// under the pack's name (one placed by `after` sits behind its core step, the pack's name on its button).
import { useFirstRun } from "./door";
import { blockOf, isPackStep } from "./packSetup";
import { goto, lineupWord, stateOf, stepsOf, titleOf, usePage, valueOf, type StepId } from "./pages";
import { providersSet, useSetup } from "./store";
import { lastCheckWord } from "./checkStore";

/** 3.3.0.0 R4: the page `halo init` opened (`?first=1`) leads the summary with what it is for; 3.3.3.0 R1: not once
 *  Setup's Done was pressed for this home (the state's `done_at`). */
function FirstCell() {
  const first = useFirstRun();
  const doneAt = useSetup((s) => s.data?.done_at || "");
  if (!first || doneAt) return null;
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
        {/* 3.3.2.0 R3: no "reading the setup..." here, the page under it says it once */}
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
  // one string per read (a new array each read would redraw forever), parsed back into the steps (3.3.11.0 R3: JSON,
  // a pack's title may hold any character)
  const joined = useSetup((s) =>
    JSON.stringify(
      stepsOf(s.data, page).map((st) => {
        const f = blockOf(s.data, st);
        return [st, stateOf(s.data, st, page), valueOf(s.data, st), titleOf(s.data, st), f?.pack.name || "", f?.block.after ? "1" : ""];
      }),
    ),
  );
  const steps = JSON.parse(joined) as [StepId, string, string, string, string, string][];
  return (
    <div className="su-top">
      <nav className="su-steps" aria-label="Setup steps" data-testid="setup-rail" data-density="bar">
        <ol className="su-steps-list">
          {steps.map(([st, state, word, title, pack, placed], i) => {
            const prev = steps[i - 1];
            const after = !!placed; // behind its core step: the pack's name on the button
            const group = !!pack && !after && !(prev && prev[4] === pack && isPackStep(prev[0]) && !prev[5]);
            return (
              <li key={st} className="su-steps-item" data-pack={pack || undefined}>
                {i > 0 && <span className="su-steps-sep mono" aria-hidden="true">&gt;</span>}
                {group && <span className="su-steps-pack mono" data-testid="setup-rail-pack">{pack}:</span>}
                <button type="button" className="su-step" onClick={() => goto(st)} data-testid="setup-rail-step" data-step={st} data-state={state}
                        data-word={word || undefined} aria-current={state === "current" ? "step" : undefined}
                        title={word ? `${title}: ${word}` : title}>
                  <span className="su-step-n mono" aria-hidden="true">{state === "done" ? "✓" : i + 1}</span>
                  <span className="su-step-title">{after ? `${pack}: ${title}` : title}</span>
                </button>
              </li>
            );
          })}
        </ol>
      </nav>
      <Strip />
    </div>
  );
}
