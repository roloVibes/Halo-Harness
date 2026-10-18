"""halo_harness.studio.edit_open -- open Studio on an edit target, or focus the
Studio that already runs for this home (Halo 3.1.1.0 R3).

`open_edit(target, ...)` is what `halo studio --edit`, `halo agents edit`,
`halo teams edit`, the TUI's `/edit` and the read-only views' `e` all call:

* a Studio runs for this home (`~/.halo/studio.json`, its port answers; or
  the one this process serves, the TUI's `/studio`):
  `POST /api/focus {edit}` asks it to open the target in every page that is
  open on it (studio/focus_api.py: a `focus` frame on the live feed). When at
  least one page took it, that is all ("focused"); with no page open, the
  browser opens the URL ("opened"), or, when no browser can be opened, the
  URL is the answer ("printed").
* none runs: `launch.launch_detached` starts one in the background with
  `--edit` and it opens the browser itself ("started"; '' url: it did not start).

`open_browser=False` (`--no-open`) never touches a page or a browser: it only
finds (or starts) the Studio and answers the URL ("printed").
"""

from __future__ import annotations

from pathlib import Path


def _focus_in_process(target, publish: bool) -> "tuple[str, int] | None":
    """The Studio this very process serves (the TUI's `/studio`, `server.ensure_background`, writes no
    studio.json): its URL and (`publish`) the pages that took the `focus` frame; None when there is none."""
    from halo_harness.studio import server as S
    srv = S._BACKGROUND.get("server")
    if srv is None:
        return None
    if not publish:
        return S.url_for(srv, target.mode, target.text), 0
    import time
    from halo_harness.studio.events import bridge_for
    bridge = bridge_for(srv)
    pages = bridge.listeners()
    bridge.publish_local({"session_id": "studio", "event": "focus", "ts": time.time(),
                          "data": {"edit": target.text, "mode": target.mode}})
    return S.url_for(srv, target.mode, target.text), pages


def open_edit(target, *, cwd, state_dir, open_browser: bool = True, timeout: float = 15.0) -> dict:
    """`{"url", "how": focused|opened|printed|started|failed, "pages": n, "target"}`."""
    from halo_harness.studio import launch
    state_dir, cwd = Path(state_dir), Path(cwd)
    out = {"url": "", "how": "failed", "pages": 0, "target": target.text}
    here = _focus_in_process(target, publish=open_browser)
    url = here[0] if here else launch.existing_url(state_dir, target.mode, target.text)
    if url:
        out["url"] = url
        if not open_browser:
            out["how"] = "printed"
            return out
        if here:
            pages = here[1]
        else:
            answer = launch.api_call(state_dir, "POST", "focus", {"edit": target.text})
            pages = int((answer[1] or {}).get("pages") or 0) if answer and answer[0] == 200 and isinstance(answer[1], dict) else 0
        out["pages"] = pages
        if pages:
            out["how"] = "focused"
        else:
            out["how"] = "opened" if launch._open(url) else "printed"
        return out
    url = launch.launch_detached(target.mode, cwd=cwd, state_dir=state_dir, open_browser=open_browser,
                                 timeout=timeout, edit=target.text)
    out["url"] = url
    out["how"] = ("started" if open_browser else "printed") if url else "failed"
    return out


def describe(result: dict) -> str:
    """One line for the terminal: what happened and the URL."""
    url, how, target = result.get("url") or "", result.get("how"), result.get("target") or "?"
    if how == "focused":
        n = result.get("pages") or 1
        return f"Opened {target} in the Studio page{'s' if n > 1 else ''} already open ({url})."
    if how == "opened":
        return f"Opened {target} in Studio in your browser: {url}"
    if how == "started":
        return f"Started Studio and opened {target} in your browser: {url}  (halo studio --stop ends it)"
    if how == "printed":
        return f"Studio is at {url}  (open it to edit {target})"
    return f"Studio did not start: run `halo studio --edit {target}` in a shell."
