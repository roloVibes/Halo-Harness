// "Test this model" (3.0.7.0 R2): the one-token probe (`POST models/test`) through the same path a session uses; ok
// and the latency, or the error, right beside it. Under the picker and in the Models panel.
import { Button } from "../../lib/ui";
import { testModel } from "./bioActions";
import { useRoles } from "./store";

export function TestButton({ value, label = "Test this model" }: { value: string; label?: string }) {
  const probe = useRoles((s) => (value ? s.probe[value] : undefined));
  return (
    <div className="rm-test">
      <Button size="sm" disabled={!value || probe === "running"} onClick={() => void testModel(value)} data-testid="model-test"
              title="A one-token round trip through the same path a session uses (it spends a fraction of a cent)">
        {probe === "running" ? "Testing..." : label}
      </Button>
      {probe && probe !== "running" && (
        <span className="rm-test-result mono" data-ok={probe.ok || undefined} data-testid="model-test-result" title={probe.cost_line}>
          {probe.ok ? `ok in ${probe.latency_ms} ms` : `failed: ${probe.error || "no reply"}`}
        </span>
      )}
    </div>
  );
}
