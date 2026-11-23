// A row's `current` in a few words: the ONE rule (3.6.0.15 F12; 3.6.0.16 U1 moved it here so the lit map's overlay.ts,
// which may import only pure siblings, follows it too). Used by a box's NOW words (overlay.ts doingOf), Session's status
// line (session/statusOf.ts) and the wait link (crew/live/waits.ts); truth.ts re-exports it. Pure: it imports nothing.
//
// A tool followed by its raw JSON arguments (agent_transcript.py tool_label's form when no argument says what it does:
// an MCP tool's `{"seconds": 30}`) is named alone, as a box's NOW names it (nowLine.ts: the raw name). A JSON object or
// array opens with `{"`, `{}`, `["`, `[{` or `[]`, so a built-in's short form ("Bash: [ -f x ]") reads as before.
const RAW_ARGS = /^([^\s:{[]+):?\s+(?:\{["}]|\[["{\]])/;

/** On what (R23): "Bash: ls -la" reads "Bash ls -la"; a tool with raw JSON arguments reads as its name alone. The raw
 *  arguments are asked first: the short form would otherwise keep them ("mcp__x {...}" has no colon to drop). */
export function toolWords(current: string): string {
  const raw = RAW_ARGS.exec(current);
  return raw ? raw[1] : current.replace(/^([A-Za-z_]+):\s*/, "$1 ").trim();
}
