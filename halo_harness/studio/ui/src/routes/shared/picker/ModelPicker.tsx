// THE model picker (3.4.1.3 "Pick, don't type"; the owner, 2026-11-12: "These model selections in studio need to allow
// the user to select which model to use that is available to them, not somehow type out a huge string correctly").
// Every place in Studio that takes a model draws this one list: the models of the providers set up here (GET models,
// local servers included), grouped by provider with the provider's state in one line, searchable by ref, name,
// provider, best-at, takes, "cheap", "local", a window ("200k"); sorted by name, price, context or best; the 3.3.15.0 R2
// row (one line, TAKES tags) and the detail line under it. Keys: type to filter, Up / Down, Enter picks, Esc closes.
// A field that needs a capability (`needs`) lists the fitting models first and dims the others, saying why. A saved
// value the catalog lacks shows as it is, marked "not in your catalog", and stays selectable. No model: why, in one
// line, with Refresh or Setup -- never an empty list or a bare text box. The last row, always: "use a reference that is
// not listed" (NotListed.tsx). `tid` prefixes the test ids (model-*, setup-model-*, settings-model-*).
import { Fragment, useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { WindowedRows } from "../../../lib/ui";
import { TestButton } from "../../roles/TestButton";
import { learnedKinds } from "../../roles/LearnedChips";
import { useRoles } from "../../roles/store";
import type { ModelRow } from "../../roles/types";
import { useCatalog } from "../catalog";
import { CardDetail, ModelCardPanel } from "../ModelCard";
import { NotListed } from "./NotListed";
import { Detail, EmptyLine, GroupHead, NotHereLine, Row } from "./PickerParts";
import { fits, groupRows, notHere, type Sort } from "./rows";
import { readFolds, saveFolds, useStatusOnce } from "./state";

export type PickerProps = {
  value: string;
  onPick: (ref: string) => void;
  /** 3.3.5.0 R0b: the main agent's model -- the picked model's card panel offers the coder lane when it cannot orchestrate. */
  forMain?: boolean;
  /** What the field needs the model to take (vision, tools, think ...): the fitting models first, the others dimmed. */
  needs?: string[];
  /** Only these rows (an Ollama-only field); the catalog otherwise. `onlyWhat` names them for the empty line. */
  only?: (m: ModelRow) => boolean;
  onlyWhat?: string;
  /** The rows to list instead of GET models (Setup's page lists its cached rows: reading it probes no host). */
  rows?: ModelRow[];
  /** The first row keeps what the field inherits (picks ""): "the bio's own (<model>)", "the default (<model>)". */
  inherit?: { label: string; model: string; text?: string };
  tid?: string;
  autoFocus?: boolean;
  seed?: string;
  onClose?: () => void;
  /** Setup's page: a taller list, no "picked" line or Test (its own foot saves). */
  embedded?: boolean;
  /** No "picked:" line and Test under the list (the field around it has its own). */
  bare?: boolean;
  foldKey?: string;
};

export function ModelPicker({ value, onPick, forMain, needs = [], only, onlyWhat = "model this field takes", rows, inherit, tid = "model", autoFocus, seed = "", onClose, embedded, bare, foldKey }: PickerProps) {
  const catalog = useCatalog();
  const all = rows ?? catalog.models;
  const loaded = rows ? true : catalog.loaded;
  const st = useStatusOnce();
  const bestFor = useRoles((s) => s.bestFor);
  const gym = useRoles((s) => s.gym);
  const error = useRoles((s) => s.modelsError);
  const busy = useRoles((s) => s.busy === "refresh");
  const models = useMemo(() => (only ? all.filter(only) : all), [all, only]);
  const [q, setQ] = useState(seed);
  const [sort, setSort] = useState<Sort>("name");
  const [task, setTask] = useState("");
  const [hot, setHot] = useState(-1);
  const [typing, setTyping] = useState(false);
  const [folds, setFolds] = useState<Record<string, boolean>>(() => readFolds(foldKey));
  const box = useRef<HTMLInputElement>(null);
  const list = useRef<HTMLDivElement>(null);
  const tasks = useMemo(() => learnedKinds(models), [models]);
  const kindsOf = (m: ModelRow) => m.best_at?.kinds || bestFor[m.ref] || [];
  const groups = useMemo(() => groupRows(models, q, sort, needs, st, kindsOf, value), [models, q, sort, needs.join(","), st, bestFor, value]); // eslint-disable-line react-hooks/exhaustive-deps
  const known = !value || models.some((m) => m.ref === value);
  const count = groups.reduce((n, g) => n + g.rows.length, 0);
  const open = (p: string) => !!q.trim() || !folds[p];
  const flat: string[] = [...(inherit ? [""] : []), ...(known ? [] : [value]), ...groups.flatMap((g) => (open(g.provider) ? g.rows.map((m) => m.ref) : []))];
  useEffect(() => { // after a dialog's own first focus, so the search box holds it
    if (!autoFocus) return undefined;
    const t = window.setTimeout(() => box.current?.focus({ preventScroll: true }), 0);
    return () => window.clearTimeout(t);
  }, [autoFocus]);
  const specials = (inherit ? 1 : 0) + (known ? 0 : 1); // a search lands on its first match, not on the field's own rows
  useEffect(() => {
    setHot(q.trim() ? (count ? specials : -1) : -1);
  }, [q, count]); // eslint-disable-line react-hooks/exhaustive-deps -- a new search, or the list arriving under one
  useEffect(() => {
    list.current?.querySelector("[data-hot]")?.scrollIntoView({ block: "nearest" });
  }, [hot]);
  const hotRef = hot >= 0 ? flat[hot] : undefined;
  const shown = models.find((m) => m.ref === hotRef) || models.find((m) => m.ref === value);
  const onKey = (e: KeyboardEvent) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (flat.length) setHot((h) => (e.key === "ArrowDown" ? Math.min(flat.length - 1, h + 1) : Math.max(0, h - 1)));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (hot >= 0 && hot < flat.length) onPick(flat[hot]);
      else if (!flat.length && q.trim()) setTyping(true);
    } else if (e.key === "Escape" && onClose) {
      e.preventDefault();
      onClose();
    }
  };
  const fold = (p: string) => {
    const next = { ...folds, [p]: !folds[p] };
    setFolds(next);
    saveFolds(foldKey, next);
  };
  const dimOf = (m: ModelRow) => (needs.length && !fits(m, needs) ? `does not state ${needs.join(" + ")}` : "");
  const gone = notHere(groups, st);
  return (
    <div className="rm mpk" data-testid={tid === "model" ? "model-picker" : `${tid}-picker`} data-embedded={embedded || undefined} onKeyDown={onKey}>
      <div className="rm-bar">
        <input ref={box} className="input mono" type="search" placeholder="search: name, provider, vision, tools, cheap, local, 200k..." value={q}
               onChange={(e) => setQ(e.target.value)} data-testid={`${tid}-search`} aria-label="Search the models" spellCheck={false} autoComplete="off" />
        <span className="segmented" role="group" aria-label="Sort">
          {(["name", "price", "context", "best"] as Sort[]).map((k) => (
            <button key={k} type="button" className={sort === k ? "on" : ""} aria-pressed={sort === k} onClick={() => setSort(k)} data-testid={`model-sort-${k}`}>{k}</button>
          ))}
        </span>
        {tasks.length > 0 && (
          <select className="input mono rm-task" value={task} onChange={(e) => setTask(e.target.value)} data-testid="model-learned-kind"
                  aria-label="Learned for a task kind" title="What Auto learned here for one task kind: its chips only, and the models dropped for it struck through">
            <option value="">learned: any kind</option>
            {tasks.map((k) => <option key={k} value={k}>learned for {k}</option>)}
          </select>
        )}
      </div>
      {needs.length > 0 && <div className="mpk-needs mono muted" data-testid="model-picker-needs">needs {needs.join(" + ")}: the models that state it first; the dimmed ones do not</div>}
      {!loaded ? (
        <div className="og-wait mono muted">reading the catalog...</div>
      ) : (
        <>
          <div className="muted mono rm-count" data-testid={`${tid}-count`}>{q.trim() ? `${count} of ${models.length} models` : `${models.length} models`}</div>
          <div ref={list} className="rm-table" role="listbox" aria-label="Models">
            <div className="rm-row rm-head mono" aria-hidden="true"><span>model</span><span className="rm-price">in / out</span><span className="rm-ctx">ctx</span><span>takes</span><span className="rm-gym">gym</span></div>
            {inherit && (
              <button type="button" className="rm-row mpk-special" role="option" aria-selected={!value} data-hot={hotRef === "" || undefined} tabIndex={-1}
                      onClick={() => onPick("")} onMouseEnter={() => setHot(0)} data-testid={`${tid}-inherit`}>
                <span className="mono rm-ref">{inherit.text ?? `${inherit.label} (${inherit.model || "none resolves"})`}</span>
              </button>
            )}
            {!known && (
              <button type="button" className="rm-row mpk-special" role="option" aria-selected data-hot={hotRef === value || undefined} tabIndex={-1}
                      onClick={() => onPick(value)} data-testid={`${tid}-saved`} data-ref={value} title="saved before; the providers set up here do not list it">
                <span className="mono rm-ref">{value}</span><span className="rm-warn mono">not in your catalog</span>
              </button>
            )}
            {!models.length ? <EmptyLine st={st} error={error} busy={busy} none={all.length ? onlyWhat : ""} /> : groups.map((g) => (
              <Fragment key={g.provider}>
                <GroupHead g={g} tid={tid} folded={!open(g.provider)} onFold={q.trim() ? undefined : () => fold(g.provider)} />
                {open(g.provider) && <WindowedRows items={g.rows} render={(m) => (
                  <Fragment key={m.ref}>
                    <Row m={m} tid={tid} on={m.ref === value} hot={m.ref === hotRef} dim={dimOf(m)} task={task} gym={gym[m.ref]} kinds={kindsOf(m).length}
                         onPick={() => onPick(m.ref)} onHot={() => setHot(flat.indexOf(m.ref))} />
                    {m.ref === value && m.card && !embedded ? <div className="rm-card"><CardDetail card={m.card} refName={m.ref} /></div> : null}
                  </Fragment>
                )} />}
              </Fragment>
            ))}
            {models.length > 0 && !count && <p className="muted rm-more" data-testid="model-picker-nomatch">No model matches "{q}": the last row takes a reference that is not listed.</p>}
            <NotHereLine {...gone} />
            <NotListed tid={tid} onPick={onPick} seed={q.trim()} open={typing} setOpen={setTyping} />
          </div>
          {models.length > 0 && <Detail m={shown} kinds={shown ? kindsOf(shown) : []} />}
        </>
      )}
      {!bare && !embedded && (
        <>
          <div className="rm-current mono">picked: <b>{value || "(none)"}</b>{value && !known && <span className="rm-warn"> · not in your catalog</span>}</div>
          <TestButton value={value} />
          {forMain && value ? <ModelCardPanel refName={value} /> : null}
        </>
      )}
    </div>
  );
}
