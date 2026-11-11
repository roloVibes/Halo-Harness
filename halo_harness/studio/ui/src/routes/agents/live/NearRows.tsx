// The near level's rows on a live agent's box (3.3.18.0 "The living canvas" part 4, levels.ts): its current thought (the
// newest THINK row's text, three lines, CSS-clamped) and its running tool with its last output line (the newest TOOL
// row's result, one line). Fixed rows the box grew for (NEAR_H): nothing above them moves.
import { short } from "../../orchestra/format";
import { useLive, type OpenTool } from "../../shared/liveFeed";
import type { LiveLine } from "../../shared/liveTypes";

const SCAN = 400; // the newest lines looked at

function newest(lines: LiveLine[], key: string, kind: string): LiveLine | null {
  for (let i = lines.length - 1; i >= Math.max(0, lines.length - SCAN); i--) if (lines[i].key === key && lines[i].kind === kind) return lines[i];
  return null;
}

export function NearRows({ k }: { k: string }) {
  const think = useLive((s) => newest(s.lines, k, "thinking"));
  const tool = useLive((s) => newest(s.lines, k, "tool"));
  const open = useLive((s): OpenTool | null => s.open[k] || null);
  const out = tool?.result ? String(tool.result).split(/\r?\n/).map((x) => x.trim()).filter(Boolean).pop() || "" : "";
  return (
    <div className="rlm-near" data-testid="roles-live-near">
      <div className="rlm-near-think" data-testid="roles-live-thought" title={think?.text || undefined}>
        <span className="rlm-near-k mono">THINKS</span> {think?.text ? short(think.text, 400) : "no thought shown yet"}
      </div>
      <div className="rlm-near-tool mono" data-testid="roles-live-near-tool" title={out || undefined}>
        <span className="rlm-near-k">TOOL</span> {open ? open.tool : tool?.tool || "none yet"}{out ? ` · ${short(out, 140)}` : ""}
      </div>
    </div>
  );
}
