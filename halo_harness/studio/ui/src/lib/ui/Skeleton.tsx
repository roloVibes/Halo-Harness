// Loading placeholders: `lines` bars, the last one shorter.
export function Skeleton({ lines = 3, height = 12 }: { lines?: number; height?: number }) {
  return (
    <div className="skeleton" aria-busy="true" aria-label="loading">
      {Array.from({ length: lines }, (_, i) => (
        <span key={i} className="skeleton-bar" style={{ height, width: i === lines - 1 && lines > 1 ? "62%" : "100%" }} />
      ))}
    </div>
  );
}
