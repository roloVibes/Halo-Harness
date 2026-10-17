// A safe markdown subset as React elements (3.0.7.0 R3, the Design thread):
// headings, paragraphs, lists (- * + and 1.), block quotes, fenced code,
// inline code, bold, italic and links. Nothing is ever parsed as HTML (React
// escapes every string), a link opens only for an http(s) or mailto address
// (with rel="noopener noreferrer"), and an image is never fetched: it shows
// as its alt text.
import type { ReactNode } from "react";

const SAFE_URL = /^(https?:\/\/|mailto:)/i;
const INLINE = /(`[^`\n]+`)|(!\[[^\]\n]*\]\([^)\s]*\))|(\[[^\]\n]+\]\([^)\s]+\))|(\*\*[^*\n]+\*\*|__[^_\n]+__)|(\*[^*\s][^*\n]*\*|_[^_\s][^_\n]*_)/;

/** Inline markdown of one line or paragraph. */
export function inline(text: string, key = "i"): ReactNode[] {
  const out: ReactNode[] = [];
  let rest = text;
  let n = 0;
  while (rest) {
    const m = INLINE.exec(rest);
    if (!m) {
      out.push(rest);
      break;
    }
    if (m.index) out.push(rest.slice(0, m.index));
    const tok = m[0];
    const k = `${key}-${n++}`;
    if (m[1]) out.push(<code key={k} className="md-code">{tok.slice(1, -1)}</code>);
    else if (m[2]) out.push(<span key={k} className="md-img muted">[image: {tok.slice(2, tok.indexOf("]")) || "no description"}]</span>);
    else if (m[3]) {
      const label = tok.slice(1, tok.indexOf("]("));
      const url = tok.slice(tok.indexOf("](") + 2, -1);
      out.push(
        SAFE_URL.test(url) ? (
          <a key={k} href={url} target="_blank" rel="noopener noreferrer" className="md-link">
            {inline(label, k)}
          </a>
        ) : (
          <span key={k}>{inline(label, k)}</span>
        ),
      );
    } else if (m[4]) out.push(<strong key={k}>{inline(tok.slice(2, -2), k)}</strong>);
    else out.push(<em key={k}>{inline(tok.slice(1, -1), k)}</em>);
    rest = rest.slice(m.index + tok.length);
  }
  return out;
}

type Block =
  | { t: "h"; level: number; text: string }
  | { t: "p"; text: string }
  | { t: "ul"; items: string[] }
  | { t: "ol"; items: string[] }
  | { t: "quote"; text: string }
  | { t: "code"; lang: string; text: string };

const HEAD = /^(#{1,6})\s+(.*)$/;
const UL = /^\s*[-*+]\s+(.*)$/;
const OL = /^\s*\d+[.)]\s+(.*)$/;
const FENCE = /^\s*(```|~~~)\s*([\w+-]*)\s*$/;

export function blocks(src: string): Block[] {
  const lines = String(src || "").replace(/\r\n?/g, "\n").split("\n");
  const out: Block[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    const fence = FENCE.exec(line);
    if (fence) {
      const body: string[] = [];
      i += 1;
      while (i < lines.length && !lines[i].trim().startsWith(fence[1])) body.push(lines[i++]);
      i += 1;
      out.push({ t: "code", lang: fence[2], text: body.join("\n") });
      continue;
    }
    if (!line.trim()) {
      i += 1;
      continue;
    }
    const h = HEAD.exec(line);
    if (h) {
      out.push({ t: "h", level: h[1].length, text: h[2] });
      i += 1;
      continue;
    }
    const list = UL.test(line) ? ({ t: "ul", re: UL } as const) : OL.test(line) ? ({ t: "ol", re: OL } as const) : null;
    if (list) {
      const items: string[] = [];
      while (i < lines.length && list.re.test(lines[i])) items.push(list.re.exec(lines[i++])![1]);
      out.push({ t: list.t, items });
      continue;
    }
    if (/^\s*>/.test(line)) {
      const q: string[] = [];
      while (i < lines.length && /^\s*>/.test(lines[i])) q.push(lines[i++].replace(/^\s*>\s?/, ""));
      out.push({ t: "quote", text: q.join(" ") });
      continue;
    }
    const para: string[] = [];
    while (i < lines.length && lines[i].trim() && !HEAD.test(lines[i]) && !FENCE.test(lines[i]) && !UL.test(lines[i]) && !OL.test(lines[i]) && !/^\s*>/.test(lines[i]))
      para.push(lines[i++].trim());
    out.push({ t: "p", text: para.join(" ") });
  }
  return out;
}

/** The markdown as React elements: never HTML, never a remote image. */
export function Markdown({ text, className }: { text: string; className?: string }) {
  return (
    <div className={"md" + (className ? " " + className : "")}>
      {blocks(text).map((b, i) => {
        const k = "b" + i;
        if (b.t === "h") return <div key={k} className={`md-h md-h${Math.min(b.level, 4)}`} role="heading" aria-level={Math.min(b.level + 2, 6)}>{inline(b.text, k)}</div>;
        if (b.t === "code") return <pre key={k} className="md-pre" data-lang={b.lang || undefined}><code>{b.text}</code></pre>;
        if (b.t === "quote") return <blockquote key={k} className="md-quote">{inline(b.text, k)}</blockquote>;
        if (b.t === "ul" || b.t === "ol") {
          const items = b.items.map((it, j) => <li key={j}>{inline(it, `${k}-${j}`)}</li>);
          return b.t === "ul" ? <ul key={k} className="md-list">{items}</ul> : <ol key={k} className="md-list">{items}</ol>;
        }
        return <p key={k} className="md-p">{inline(b.text, k)}</p>;
      })}
    </div>
  );
}
