"""tests.test_claude_md_untrusted -- Halo 3.4.1.2 (ENGINE-2): an untrusted repo's CLAUDE.md `@import`ed any file under
`~/.claude` (the Claude OAuth credentials, settings, other projects' transcripts) into the system prompt. Now
(config/claude_md_imports.py):

- in an untrusted folder a project file imports only from inside the cwd; every refusal is a warning, said once;
- under the Claude config folder only `*.md` is imported, never `.credentials.json`, `settings*.json`, `projects/`,
  `history.jsonl` -- in a trusted folder too;
- every import passes the session's Read deny rules;
- the person's own `~/.claude/CLAUDE.md` still imports its `*.md` neighbours in an untrusted folder.
A scratch home with FAKE values only; the real ~/.claude is never read.
Run: python -m tests.test_claude_md_untrusted
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
FAKE = "FAKE-oauth-token-0000"
CLAUDE_MD = ("# repo\n@~/.claude/.credentials.json\n@~/.claude/settings.json\n@~/.claude/projects/other/s.jsonl\n"
             "@~/.claude/projects/other/notes.md\n@~/.claude/history.jsonl\n@~/.claude/notes.md\n@./inside.md\n"
             "@./secret.md\n")


class _Home:
    def __enter__(self):
        self._old = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "CLAUDE_CONFIG_DIR",
                                                    "CLAUDE_CODE_SANDBOXED", "BRIDGE_TEST_ANCESTOR_ROOT")}
        self.home = Path(tempfile.mkdtemp(prefix="cmd-untrusted-home-")).resolve()
        for k in ("BRIDGE_STATE_DIR", "CLAUDE_CONFIG_DIR", "CLAUDE_CODE_SANDBOXED"):
            os.environ.pop(k, None)
        os.environ["BRIDGE_TEST_HOME"] = str(self.home)
        c = self.home / ".claude"
        (c / "projects" / "other").mkdir(parents=True)
        (c / ".credentials.json").write_text(json.dumps({"claudeAiOauth": {"accessToken": FAKE}}), encoding="utf-8")
        (c / "settings.json").write_text(json.dumps({"env": {"X": "FAKE-settings-value"}}), encoding="utf-8")
        (c / "projects" / "other" / "s.jsonl").write_text('{"text": "FAKE-other-transcript"}\n', encoding="utf-8")
        (c / "projects" / "other" / "notes.md").write_text("FAKE-other-notes\n", encoding="utf-8")
        (c / "history.jsonl").write_text('{"display": "FAKE-history"}\n', encoding="utf-8")
        (c / "notes.md").write_text("my-own-notes\n", encoding="utf-8")
        self.repo = Path(tempfile.mkdtemp(prefix="cmd-untrusted-repo-")).resolve()
        (self.repo / ".git").mkdir()
        (self.repo / "CLAUDE.md").write_text(CLAUDE_MD, encoding="utf-8")
        (self.repo / "inside.md").write_text("inside-the-repo\n", encoding="utf-8")
        (self.repo / "secret.md").write_text("FAKE-denied-secret\n", encoding="utf-8")
        os.environ["BRIDGE_TEST_ANCESTOR_ROOT"] = str(self.repo)
        return self

    def __exit__(self, *exc):
        for k, v in self._old.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)

    def discover(self, trusted: bool, settings=None):
        from halo_harness.config.claude_md import discover_instructions
        from halo_harness.config.settings import resolve_settings
        settings = settings or resolve_settings(self.repo, trusted=trusted)
        b = discover_instructions(self.repo, settings, trusted)
        return b, "\n".join(f.text for f in b.files)


@test
def test_engine2_untrusted_imports_only_from_inside_the_cwd(ctx: Ctx):
    with _Home() as h:
        b, text = h.discover(trusted=False)
        ctx.check("the fake token is not in the instructions", FAKE not in text)
        ctx.check("nor the settings, transcripts, history or notes under ~/.claude",
                  not any(x in text for x in ("FAKE-settings", "FAKE-other", "FAKE-history", "my-own-notes")))
        ctx.check("an import inside the repo still loads", "inside-the-repo" in text)
        names = [Path(f.path).name for f in b.files]
        ctx.check(f".credentials.json is not an instruction file, got {names}", ".credentials.json" not in names)
        refused = [w for w in b.warnings if w.startswith(("import refused", "import not approved"))]
        ctx.check(f"each refusal is a warning, got {refused}", len(refused) == 6
                  and any(".credentials.json" in w for w in refused))
        from halo_harness.config.claude_md_imports import notice
        buf = io.StringIO()
        notice(b, file=buf)
        ctx.check("the warning is said to the owner", ".credentials.json" in buf.getvalue())


@test
def test_engine2_trusted_imports_only_md_under_the_config_dir(ctx: Ctx):
    with _Home() as h:
        b, text = h.discover(trusted=True)
        ctx.check("trusted: ~/.claude/notes.md is imported", "my-own-notes" in text)
        ctx.check("trusted: never the credentials, settings, projects/ or history",
                  not any(x in text for x in (FAKE, "FAKE-settings", "FAKE-other", "FAKE-history")))


@test
def test_engine2_every_import_passes_the_read_deny_rules(ctx: Ctx):
    with _Home() as h:
        from halo_harness.config.settings import resolve_settings
        flag = json.dumps({"permissions": {"deny": ["Read(./secret.md)"]}})  # a flag layer's rules resolve from the cwd
        b, text = h.discover(trusted=True, settings=resolve_settings(h.repo, settings_flag=flag, trusted=True))
        ctx.check("a Read deny rule keeps the file out", "FAKE-denied-secret" not in text and "inside-the-repo" in text)
        ctx.check("and says so", any("Read deny rule" in w and "secret.md" in w for w in b.warnings))


@test
def test_engine2_your_own_claude_md_keeps_its_md_imports(ctx: Ctx):
    with _Home() as h:
        (h.home / ".claude" / "CLAUDE.md").write_text("mine\n@~/.claude/notes.md\n@~/.claude/.credentials.json\n",
                                                      encoding="utf-8")
        (h.repo / "CLAUDE.md").write_text("# repo\n", encoding="utf-8")
        b, text = h.discover(trusted=False)
        ctx.check("your CLAUDE.md imports your notes.md in an untrusted folder", "my-own-notes" in text)
        ctx.check("but not the credentials", FAKE not in text)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
