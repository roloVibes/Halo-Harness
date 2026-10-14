// A failed load: the message, the server's `problems` lines, and Retry.
import { ApiError } from "../api";
import { Button } from "./Button";

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message = error instanceof Error ? error.message : String(error);
  const problems = error instanceof ApiError ? error.problems : [];
  return (
    <div className="error-state" role="alert" data-motion="error">
      <div className="error-title">{message}</div>
      {problems.length > 0 && (
        <ul className="error-problems mono">
          {problems.map((p, i) => (
            <li key={i}>{p}</li>
          ))}
        </ul>
      )}
      {onRetry && (
        <Button variant="default" size="sm" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  );
}
