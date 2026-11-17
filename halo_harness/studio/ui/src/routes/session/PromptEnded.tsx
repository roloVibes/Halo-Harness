// 3.6.0.2 P32 ("one prompt"): the picked session left the list, nothing follows it (P31) and the box holds text. The
// box is read-only and this line stands over it with `Copy`, which reads `Copied.` for 2 s once the text is on the
// clipboard. Picking another session makes the box editable again with the same text (the page keeps one text).
import { useEffect, useState } from "react";
import { Button } from "../../lib/ui";
import { COPIED, COPIED_MS, COPY, ENDED } from "./promptWords";

/** The text on the clipboard: the Clipboard API, else the page's own copy command (a page without the permission). */
async function toClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const el = document.createElement("textarea");
    el.value = text;
    el.setAttribute("readonly", "");
    el.style.cssText = "position:fixed;left:-9999px;top:0;opacity:0";
    document.body.appendChild(el);
    el.select();
    try {
      return document.execCommand("copy");
    } catch {
      return false;
    } finally {
      el.remove();
    }
  }
}

export function PromptEnded({ text }: { text: string }) {
  const [copied, setCopied] = useState(0);
  useEffect(() => {
    if (!copied) return;
    const t = window.setTimeout(() => setCopied(0), COPIED_MS);
    return () => window.clearTimeout(t);
  }, [copied]);
  const copy = async () => void ((await toClipboard(text)) && setCopied((n) => n + 1));
  return (
    <div className="spp-ended" data-testid="prompt-ended" role="status">
      <span className="spp-ended-line">{ENDED}</span>
      <Button size="sm" onClick={() => void copy()} data-testid="prompt-copy" data-copied={copied ? true : undefined}>
        {copied ? COPIED : COPY}
      </Button>
    </div>
  );
}
