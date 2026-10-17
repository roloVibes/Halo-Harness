// The turns of the Design thread (3.0.7.0 R3): a finished turn from the
// project's history (what you asked, the model's reply as safe markdown, its
// cost, tool calls, seconds and the versions it made) and the turn running
// now (its reply as it streams, a chip per tool call, the working dots).
import { memo } from "react";
import { Markdown } from "../../lib/markdown";
import { Icon, toolIcon } from "../../lib/ui";
import { money, versionsLine } from "./store";
import type { HistoryRow, LiveTurn, TurnEvent } from "./types";

function You({ text }: { text: string }) {
  return (
    <div className="dt-msg" data-who="you">
      <div className="dt-who mono">YOU</div>
      <Markdown text={text} className="dt-body" />
    </div>
  );
}

function meta(h: HistoryRow): string {
  const bits: string[] = [];
  if (h.tool_calls != null) bits.push(`${h.tool_calls} tool call${h.tool_calls === 1 ? "" : "s"}`);
  if (h.elapsed != null) bits.push(`${Math.round(Number(h.elapsed) || 0)} s`);
  bits.push(money(h.cost));
  bits.push(versionsLine(h.versions) || "no artboard changed");
  if (h.cancelled) bits.push("cancelled");
  else if (h.code) bits.push(`exit ${h.code}`);
  return bits.join(" · ");
}

export const HistoryTurn = memo(function HistoryTurn({ h, n }: { h: HistoryRow; n: number }) {
  const render = h.app === "comfyui";
  const reply = h.text?.trim()
    || (render ? `A ComfyUI render into ${(h.artboards || []).join(", ") || "the project"}.` : versionsLine(h.versions) ? `Changed ${versionsLine(h.versions)}.` : "No artboard changed.");
  return (
    <section className="dt-turn" data-testid="design-turn" data-n={n} data-failed={(!!h.code && !h.cancelled) || undefined}>
      <You text={h.prompt || (render ? "(a render from the Media panels)" : "(no prompt)")} />
      <div className="dt-msg" data-who="model">
        <div className="dt-who mono">{render ? "COMFYUI" : (h.model || "MODEL").toUpperCase()}</div>
        <Markdown text={reply} className="dt-body" />
        <div className="dt-meta mono muted">{h.ts ? h.ts.replace("T", " ") + " · " : ""}{meta(h)}</div>
      </div>
    </section>
  );
});

type Piece = { kind: "text"; text: string } | { kind: "tool"; name: string; line: string };

/** The streamed events as reply text and tool chips, in order (adjacent text joined). */
export function pieces(events: (TurnEvent | undefined)[]): Piece[] {
  const out: Piece[] = [];
  for (const ev of events) {
    if (!ev || ev.type !== "assistant") continue;
    for (const b of ev.message?.content || []) {
      if (b.type === "text" && b.text) {
        const last = out[out.length - 1];
        if (last && last.kind === "text") last.text += "\n\n" + b.text;
        else out.push({ kind: "text", text: b.text });
      } else if (b.type === "tool_use") {
        const line = b.input_line ?? JSON.stringify(b.input ?? {});
        out.push({ kind: "tool", name: b.name || "tool", line: String(line).slice(0, 160) });
      }
    }
  }
  return out;
}

export function LiveTurnView({ t }: { t: LiveTurn }) {
  const parts = pieces(t.events);
  const cost = [...t.events].reverse().find((e) => e && (e.total_cost_usd != null || e.cost_usd != null));
  return (
    <section className="dt-turn" data-testid="design-turn" data-live={!t.done || undefined}>
      <You text={t.prompt} />
      <div className="dt-msg" data-who="model" aria-live="polite">
        <div className="dt-who mono">{t.label ? t.label.toUpperCase() : "MODEL"}{t.done ? "" : " · WORKING"}</div>
        {parts.map((p, i) =>
          p.kind === "text" ? (
            <Markdown key={i} text={p.text} className="dt-body" />
          ) : (
            <div key={i} className="dt-tool mono" data-testid="design-tool">
              <Icon name={toolIcon(p.name)} />
              <b>{p.name}</b>
              <span className="muted">{p.line}</span>
            </div>
          ),
        )}
        {!t.done && (
          <div className="dt-working mono muted">
            <span className="dt-dots" aria-hidden="true"><i /><i /><i /></span> working{cost ? " · " + money(cost.total_cost_usd ?? cost.cost_usd) : ""}
          </div>
        )}
        {t.done && t.result && <div className="dt-meta mono muted">{t.result.cancelled ? "cancelled" : `exit ${t.result.code}`} · {money(t.result.cost)} · {versionsLine(t.result.versions) || "no artboard changed"}</div>}
      </div>
    </section>
  );
}
