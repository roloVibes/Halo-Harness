// An empty state that says what to do next.
import type { ReactNode } from "react";

export function Empty({ title, body, action, icon, testid }: { title: string; body?: ReactNode; action?: ReactNode; icon?: ReactNode; testid?: string }) {
  return (
    <div className="empty" data-testid={testid}>
      {icon && <div className="empty-icon">{icon}</div>}
      <div className="empty-title">{title}</div>
      {body && <div className="empty-body">{body}</div>}
      {action && <div className="empty-action">{action}</div>}
    </div>
  );
}
