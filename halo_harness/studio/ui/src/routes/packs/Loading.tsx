// A pack's own section before the packs registry answers (3.2.1.0 R1): the
// served page names the running packs' sections (`data-pack-sections`,
// studio/session_open.py boot_html), so a reload on a pack section paints
// that section first, its frame holding this one line; the panels come with
// `GET pack/registry` (routes/packs/store.ts), or, when the pack is gone,
// the first tab does.
import type { PanelSpec } from "../../lib/workspace/types";

export function PackSectionLoading({ section }: { section: string; specs: PanelSpec[] }) {
  return (
    <div className="pack-loading mono muted" data-testid="pack-section-loading" data-section={section} role="status">
      loading the pack's section
    </div>
  );
}
