// Settings' group rail (3.3.3.0 R2), down the left of the page: one button per
// catalog group in its order (General ... Local), how many of its keys are set
// out of how many, the open group lit; a click opens its page (pages.ts). It
// is Setup's step rail turned on its side: there is no order to walk here,
// every group is a page of its own.
import { goto, usePages } from "./pages";
import { useSettings } from "./store";

export function SettingsRail() {
  const page = usePages((s) => s.page);
  const searching = usePages((s) => !!s.query.trim());
  const groups = useSettings((s) => s.groups);
  // one string per read (a new object each read would redraw forever): the set count per group
  const counts = useSettings((s) => s.rows.map((r) => (s.values[r.key]?.set ? r.group : "")).filter(Boolean).join("|"));
  const setIn = (id: string) => counts.split("|").filter((g) => g === id).length;
  return (
    <nav className="st-rail" aria-label="Settings groups" data-testid="settings-rail">
      <ol className="st-rail-list">
        {groups.map((g) => {
          const on = g.id === page && !searching;
          const n = setIn(g.id);
          return (
            <li key={g.id}>
              <button type="button" className={"st-rail-item" + (on ? " on" : "")} onClick={() => goto(g.id)} data-testid="settings-rail-group"
                      data-group={g.id} aria-current={on ? "page" : undefined} title={`${g.title}: ${n} of ${g.count} keys set`}>
                <span className="st-rail-title">{g.title}</span>
                <span className="st-rail-count mono" data-set={n > 0 || undefined}>
                  {n ? `${n}/${g.count}` : g.count}
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
