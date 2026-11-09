// The three mono lines every confirmation shows before its buttons (3.3.15.0 L1, the Instrument look's Dialog: the
// pack kit's offered-action rule -- say what it does, what it costs and what it writes before it runs -- made
// visible on every Dialog that asks). styles/instrument.css draws it; `Dialog` takes it as `cost`.
export type DialogCostLines = { does: string; costs: string; writes: string };

export function DialogCost({ cost }: { cost: DialogCostLines }) {
  const rows: [string, string][] = [["DOES", cost.does], ["COSTS", cost.costs], ["WRITES", cost.writes]];
  return (
    <dl className="dialog-cost" data-testid="dialog-cost">
      {rows.map(([k, v]) => [
        <dt key={k}>{k}</dt>,
        <dd key={k + "-v"} data-line={k.toLowerCase()} data-none={/^nothing\b/.test(v) || undefined}>{v}</dd>,
      ])}
    </dl>
  );
}
