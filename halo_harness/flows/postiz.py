"""halo_harness.flows.postiz -- the Postiz CLI as a small client.

    PostizCli(argv0="postiz", env=None, cwd=None, timeout_s=120.0, home=None)
      .available() -> bool            the CLI is on PATH
      .credentials() -> str           "POSTIZ_API_KEY" | "~/.postiz/credentials.json" | "" (never the key)
      .integrations() -> [{id, platform, name, disabled}]       integrations:list
      .upload(path) -> {id, url}      upload <file>; `url` is what -m takes
      .create_post(text, media, integration_id, when=None, settings=None) -> {post_id, raw}
      .post_status(post_id) -> dict   posts:status <id>
      .analytics_post(post_id, days) / .analytics_platform(integration_id, days) -> parsed JSON
      .calls                          every argv run, in order (the key is never in an argv)

The child env is `providers.config.tool_child_env` of `env` plus
POSTIZ_API_KEY / POSTIZ_API_URL passed through by name (the env-file loader's
keys are otherwise stripped from tool children). A failed call raises
`PostizError` with the argv and the CLI's stderr tail; the key value is
replaced by *** in any text it could appear in.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from halo_harness.flows.postiz_parse import find_id, parse_integrations, parse_json

# What each platform's integration wants beside the text (Postiz skill: YouTube needs a title,
# TikTok must be DIRECT_POST to publish, Instagram says feed post or story).
def _youtube(title: str, text: str) -> dict:
    first = text.strip().splitlines()[0] if text.strip() else "post"
    return {"title": (title or first)[:100], "type": "public"}


PLATFORM_SETTINGS = {
    "youtube": _youtube,
    "tiktok": lambda title, text: {"privacy_level": "PUBLIC_TO_EVERYONE", "duet": True, "stitch": True,
                                   "content_posting_method": "DIRECT_POST"},
    "instagram": lambda title, text: {"post_type": "post"},
}


def platform_settings(platform: str, title: str, text: str) -> dict:
    fn = PLATFORM_SETTINGS.get(str(platform).lower())
    return fn(title, text) if fn else {}


def iso_utc(offset_s: float = 0.0) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + offset_s))


class PostizError(RuntimeError):
    def __init__(self, message: str, argv=None):
        super().__init__(message)
        self.argv = list(argv or [])


class PostizCli:
    def __init__(self, argv0: str = "postiz", env=None, cwd=None, timeout_s: float = 120.0, home=None):
        self.argv0, self.cwd, self.timeout_s, self._home = argv0, cwd, float(timeout_s), home
        self.env = dict(os.environ if env is None else env)
        self.calls: list = []

    # ---- what is installed -----------------------------------------------------------------
    def path(self) -> str:
        return shutil.which(self.argv0, path=self.env.get("PATH")) or ""

    def available(self) -> bool:
        return bool(self.path())

    def credentials(self) -> str:
        if str(self.env.get("POSTIZ_API_KEY") or "").strip():
            return "POSTIZ_API_KEY"
        from halo_harness.config.paths import home
        base = Path(self._home) if self._home else home()
        return "~/.postiz/credentials.json" if (base / ".postiz" / "credentials.json").is_file() else ""

    def child_env(self) -> dict:
        from halo_harness.providers.config import tool_child_env
        env = tool_child_env(self.env)
        for name in ("POSTIZ_API_KEY", "POSTIZ_API_URL"):
            if self.env.get(name):
                env[name] = self.env[name]
        return env

    # ---- running ------------------------------------------------------------------------------
    def _scrub(self, text: str) -> str:
        key = str(self.env.get("POSTIZ_API_KEY") or "")
        return text.replace(key, "***") if len(key) >= 4 else text

    def _run(self, *args: str) -> str:
        argv = [self.argv0, *args]
        self.calls.append(argv)
        exe = self.path()
        if not exe:
            raise PostizError(f"the postiz CLI is not on PATH (npm i -g postiz): {self.argv0} {args[0]}", argv)
        try:
            p = subprocess.run([exe, *args], capture_output=True, cwd=self.cwd, env=self.child_env(),
                               timeout=self.timeout_s, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            raise PostizError(f"postiz {args[0]} timed out after {self.timeout_s:g}s", argv) from None
        except OSError as e:
            raise PostizError(f"postiz {args[0]} could not start: {e}", argv) from None
        out, err = (self._scrub(b.decode("utf-8", "replace")) for b in (p.stdout, p.stderr))
        if p.returncode != 0:
            tail = " | ".join((err.strip() or out.strip()).splitlines()[-4:])[-600:]
            raise PostizError(f"postiz {args[0]} failed (exit {p.returncode}): {tail or 'no output'}", argv)
        return out

    # ---- the commands ---------------------------------------------------------------------------
    def integrations(self) -> list:
        out = self._run("integrations:list")
        rows = parse_integrations(out)
        if not rows and out.strip() and parse_json(out) is None:
            raise PostizError("postiz integrations:list printed something that is neither JSON nor a table: "
                              + out.strip()[:200], self.calls[-1])
        return rows

    def upload(self, path: str) -> dict:
        data = parse_json(self._run("upload", str(path)))
        d = data if isinstance(data, dict) else {}
        url = d.get("path") or d.get("url") or ""
        if not (url or d.get("id")):
            raise PostizError(f"postiz upload {path}: the answer has no path or id", self.calls[-1])
        return {"id": str(d.get("id") or ""), "url": str(url)}

    @staticmethod
    def create_argv(text: str, media: list, integration_id: str, when: str, settings=None, argv0: str = "postiz") -> list:
        argv = [argv0, "posts:create", "-c", text]
        if media:
            argv += ["-m", ",".join(str(m) for m in media)]
        argv += ["-s", when, "-i", integration_id]
        if settings:
            argv += ["--settings", json.dumps(settings, ensure_ascii=False, separators=(",", ":"))]
        return argv

    def create_post(self, text: str, media_ids: list, integration_id: str, when=None, settings=None) -> dict:
        when = when or iso_utc(60)
        argv = self.create_argv(text, media_ids, integration_id, when, settings, self.argv0)
        raw = parse_json(self._run(*argv[1:]))
        post_id = find_id(raw)
        if not post_id:
            raise PostizError("postiz posts:create answered without a post id: " + json.dumps(raw)[:200], argv)
        return {"post_id": post_id, "scheduled_at": when, "raw": raw}

    def post_status(self, post_id: str) -> dict:
        data = parse_json(self._run("posts:status", str(post_id)))
        return data if isinstance(data, dict) else {"raw": data}

    def analytics_post(self, post_id: str, days: int = 7):
        return parse_json(self._run("analytics:post", str(post_id), "-d", str(int(days))))

    def analytics_platform(self, integration_id: str, days: int = 7):
        return parse_json(self._run("analytics:platform", str(integration_id), "-d", str(int(days))))
