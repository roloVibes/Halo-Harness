"""tests.test_agents_teams -- Halo 2.0.4 round 4 (deliverables 6-8): agent
bios (`agents_yaml.py`), the `.claude/agents/*.md` frontmatter bridge
(`agents_md_bridge.py`), team templates/lineups (`teams_yaml.py`), the
legacy-role-table migration, the CLI (`agents_cli.py`/`teams_cli.py`),
`/agents`/`/teams`, and `halo doctor --agents` (`agents_doctor.py`).
"""
import io
import os
import sys
import tempfile
import time
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()


class _Env:
    """Scratch `BRIDGE_TEST_HOME`/`BRIDGE_STATE_DIR` + a scratch project
    cwd (for the `.halo/agents`/`.halo/teams` PROJECT tier) -- the real
    `~/.halo` is never touched."""

    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
        d = Path(tempfile.mkdtemp(prefix="agents-teams-"))
        os.environ["BRIDGE_TEST_HOME"] = str(d)
        os.environ["BRIDGE_STATE_DIR"] = str(d / ".halo")
        self.home = d
        self.state_dir = d / ".halo"
        self.cwd = d / "project"
        self.cwd.mkdir(parents=True, exist_ok=True)
        return self

    def __exit__(self, *exc):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# ---------------------------------------------------------------------------
# agents_yaml.py: bios -- round trip, extends precedence, validation.
# ---------------------------------------------------------------------------

@test
def test_save_load_bio_round_trips_every_section(ctx: Ctx):
    from halo_harness.agents_yaml import resolve_agent_bio, save_agent_bio
    with _Env() as e:
        bio = {"description": "A test bio.", "version": "1.0", "tags": ["x"], "kind": "subagent",
               "models": {"preference": "or:vendor/model", "effort": "high"},
               "tools": {"allow": ["Read", "Bash"]}, "limits": {"max_iterations": 10},
               "acceptance": {"prompt": "say hi", "expect": "non-empty"}}
        ok, problems = save_agent_bio("mine", bio, state_dir=e.state_dir)
        ctx.check(f"save ok, got {problems}", ok)
        back = resolve_agent_bio("mine", state_dir=e.state_dir)
        ctx.check(f"round-tripped models, got {back['models']}", back["models"] == bio["models"])
        ctx.check(f"round-tripped tools, got {back['tools']}", back["tools"] == bio["tools"])
        ctx.check(f"round-tripped acceptance, got {back['acceptance']}", back["acceptance"] == bio["acceptance"])


@test
def test_bio_extends_merges_section_by_section_child_wins(ctx: Ctx):
    from halo_harness.agents_yaml import resolve_agent_bio, save_agent_bio
    with _Env() as e:
        save_agent_bio("parent", {"description": "parent",
                                   "models": {"preference": "or:vendor/parent-model", "effort": "low"},
                                   "limits": {"max_iterations": 5}}, state_dir=e.state_dir)
        save_agent_bio("child", {"description": "child", "extends": "parent",
                                  "models": {"effort": "high"}}, state_dir=e.state_dir)
        resolved = resolve_agent_bio("child", state_dir=e.state_dir)
        ctx.check(f"child's own effort wins, got {resolved['models']}", resolved["models"]["effort"] == "high")
        ctx.check(f"parent's preference is INHERITED (child never mentioned it), got {resolved['models']}",
                  resolved["models"]["preference"] == "or:vendor/parent-model")
        ctx.check(f"parent's limits section is inherited WHOLE (child never mentioned it), got {resolved['limits']}",
                  resolved["limits"] == {"max_iterations": 5})
        ctx.check(f"child's OWN description, never the parent's, got {resolved['description']!r}",
                  resolved["description"] == "child")


@test
def test_bio_extends_cycle_is_a_validation_problem_not_a_hang(ctx: Ctx):
    from halo_harness.agents_yaml import save_agent_bio, validate_agent_bio, load_agent_bio_raw
    with _Env() as e:
        save_agent_bio("a", {"description": "a"}, state_dir=e.state_dir)
        save_agent_bio("b", {"description": "b", "extends": "a"}, state_dir=e.state_dir)
        # Hand-edit "a" to extend "b" -- a genuine cycle -- bypassing
        # save_agent_bio's own validation (which would refuse to create
        # one in the first place) to prove the LOADER survives one that
        # already exists on disk (hand-edited, or from an older version).
        import yaml
        path = e.state_dir / "agents" / "a.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        data["extends"] = "b"
        path.write_text(yaml.safe_dump(data), encoding="utf-8")
        raw = load_agent_bio_raw("a", state_dir=e.state_dir)
        problems = validate_agent_bio(raw, name="a", state_dir=e.state_dir)
        ctx.check(f"the cycle is reported, got {problems}", any("cycle" in p for p in problems))


@test
def test_validate_agent_bio_rejects_bad_kind_and_bad_section_type(ctx: Ctx):
    from halo_harness.agents_yaml import validate_agent_bio
    problems = validate_agent_bio({"description": "x", "kind": "not-a-kind", "models": "not-a-mapping"})
    ctx.check(f"bad kind reported, got {problems}", any("kind" in p for p in problems))
    ctx.check(f"bad section type reported, got {problems}", any("models" in p for p in problems))


@test
def test_shipped_bio_templates_all_validate_clean(ctx: Ctx):
    """The orchestrator's own richer example set (orchestrator/
    implementer/verifier/reviewer/researcher/release-manager/watchdog)
    plus this round's own starters (coder/general/judge/local-small/
    tester) -- every one must parse and validate with zero problems."""
    from halo_harness.agents_yaml import list_bundled_agent_templates, load_agent_bio_raw, validate_agent_bio
    names = list_bundled_agent_templates()
    ctx.check(f"at least a dozen shipped bios, got {names}", len(names) >= 12)
    for name in names:
        raw = load_agent_bio_raw(name)
        problems = validate_agent_bio(raw, name=name)
        ctx.check(f"{name}: zero problems, got {problems}", problems == [])


@test
def test_thinking_off_normalizes_from_yaml_bool_to_the_string(ctx: Ctx):
    """YAML 1.1's bare-word resolver reads unquoted `off` as the Python
    bool False -- `_normalize_thinking_field` fixes this up right after
    the raw read so `models.thinking` is always the literal string."""
    from halo_harness.agents_yaml import resolve_agent_bio
    resolved = resolve_agent_bio("implementer")  # shipped file writes `thinking: off` unquoted
    ctx.check(f"normalized to the string 'off', got {resolved['models']['thinking']!r}",
              resolved["models"]["thinking"] == "off")


# ---------------------------------------------------------------------------
# agents_md_bridge.py: import/export to/from `.claude/agents/*.md`.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# teams_yaml.py: team templates ("lineups") -- shorthand expansion, round
# trip, validation, resolution to a role table.
# ---------------------------------------------------------------------------

def _save_two_bios(state_dir) -> None:
    from halo_harness.agents_yaml import save_agent_bio
    save_agent_bio("bio-a", {"description": "a", "models": {"preference": "or:vendor/model-a"}},
                    state_dir=state_dir)
    save_agent_bio("bio-b", {"description": "b", "models": {"preference": "or:vendor/model-b", "effort": "low"}},
                    state_dir=state_dir)


@test
def test_roles_shorthand_expands_to_the_same_agents_list_shape(ctx: Ctx):
    from halo_harness.teams_yaml import load_team_template_raw, save_team_template
    with _Env() as e:
        _save_two_bios(e.state_dir)
        ok, problems = save_team_template("shorthand-demo", {"description": "x",
                                                                "roles": {"main": "bio-a", "small": "bio-b"}},
                                           state_dir=e.state_dir)
        ctx.check(f"saved ok, got {problems}", ok)
        raw = load_team_template_raw("shorthand-demo", state_dir=e.state_dir)
        ctx.check(f"\"roles:\" shorthand expanded into \"agents:\" on disk, got {raw.get('agents')}",
                  {"agent": "bio-a", "role": "main"} in raw["agents"]
                  and {"agent": "bio-b", "role": "small"} in raw["agents"])
        on_disk_text = (e.state_dir / "teams" / "shorthand-demo.yaml").read_text(encoding="utf-8")
        ctx.check(f'the file on disk carries "agents:" in canonical form, never a literal "roles:" key, '
                  f"got:\n{on_disk_text}", "agents:" in on_disk_text and "roles:" not in on_disk_text)


@test
def test_validate_team_template_catches_no_main_duplicate_alias_and_unknown_agent(ctx: Ctx):
    from halo_harness.teams_yaml import validate_team_template
    with _Env() as e:
        _save_two_bios(e.state_dir)
        no_main = validate_team_template({"agents": [{"agent": "bio-a", "role": "subagent"}]},
                                          state_dir=e.state_dir)
        ctx.check(f"no main reported, got {no_main}", any("main" in p for p in no_main))
        dup_alias = validate_team_template(
            {"agents": [{"agent": "bio-a", "role": "main", "as": "x"},
                        {"agent": "bio-b", "role": "subagent", "as": "x"}]}, state_dir=e.state_dir)
        ctx.check(f"duplicate alias reported, got {dup_alias}", any("duplicate" in p.lower() for p in dup_alias))
        unknown_agent = validate_team_template(
            {"agents": [{"agent": "no-such-bio", "role": "main"}]}, state_dir=e.state_dir)
        ctx.check(f"unknown agent reported, got {unknown_agent}", any("no-such-bio" in p for p in unknown_agent))
        unknown_routing = validate_team_template(
            {"agents": [{"agent": "bio-a", "role": "main", "as": "boss"}], "routing": {"default": "nope"}},
            state_dir=e.state_dir)
        ctx.check(f"unknown routing target reported, got {unknown_routing}",
                  any("routing" in p and "nope" in p for p in unknown_routing))


@test
def test_resolve_role_table_applies_per_assignment_override_over_bio(ctx: Ctx):
    from halo_harness.teams_yaml import resolve_role_table
    with _Env() as e:
        _save_two_bios(e.state_dir)
        template = {"agents": [
            {"agent": "bio-a", "role": "main"},
            {"agent": "bio-b", "role": "subagent", "as": "worker-override",
             "models": {"preference": "or:vendor/overridden"}},
        ]}
        role_table, notes = resolve_role_table(template, state_dir=e.state_dir)
        ctx.check(f"main resolves to the bio's own model, got {role_table}", role_table["main"] == "or:vendor/model-a")
        ctx.check(f"the per-assignment override wins over the bio's own preference, got {role_table}",
                  role_table["worker-override"] == {"model": "or:vendor/overridden", "effort": "low"})
        ctx.check(f"no notes (both resolved), got {notes}", notes == [])


@test
def test_resolve_role_table_notes_an_agent_with_no_model_anywhere(ctx: Ctx):
    from halo_harness.teams_yaml import resolve_role_table
    with _Env() as e:
        from halo_harness.agents_yaml import save_agent_bio
        save_agent_bio("bare", {"description": "no model pinned"}, state_dir=e.state_dir)
        role_table, notes = resolve_role_table({"agents": [{"agent": "bare", "role": "main"}]}, state_dir=e.state_dir)
        ctx.check(f"left out of the role table, got {role_table}", role_table == {})
        ctx.check(f"a plain-English note explains why, got {notes}", len(notes) == 1 and "bare" in notes[0])


@test
def test_shipped_halo_dev_cycle_team_template_validates_and_resolves(ctx: Ctx):
    """The orchestrator's own flagship multi-agent example (seven
    assignments, delegation/routing/budget/escalation/pipeline/
    acceptance) -- the docs/AGENTS.md example this round documents."""
    from halo_harness.teams_yaml import resolve_role_table, resolve_team_template, validate_team_template
    with _Env() as e:
        resolved = resolve_team_template("halo-dev-cycle", state_dir=e.state_dir)
        ctx.check("the shipped template resolves", resolved is not None)
        problems = validate_team_template(resolved, name="halo-dev-cycle", state_dir=e.state_dir)
        ctx.check(f"zero validation problems, got {problems}", problems == [])
        role_table, notes = resolve_role_table(resolved, state_dir=e.state_dir)
        ctx.check(f"all seven assignments resolved to a real model, got {role_table}", len(role_table) == 7
                  and notes == [])
        ctx.check(f"delegation/routing/budget/escalation/pipeline all carried through, got keys={list(resolved)}",
                  all(s in resolved for s in ("delegation", "routing", "budget", "escalation", "pipeline")))


# ---------------------------------------------------------------------------
# Migration: legacy role table -> "migrated" team template + one bio per
# distinct model.
# ---------------------------------------------------------------------------

@test
def test_migrate_legacy_role_table_builds_bios_and_a_team_template(ctx: Ctx):
    from halo_harness.teams_yaml import migrate_legacy_role_table, resolve_role_table, resolve_team_template
    from halo_harness.theme import set_config_value
    with _Env() as e:
        set_config_value("model", "or:vendor/session-default")
        legacy = {"researcher": "or:deepseek/deepseek-chat", "judge": {"model": "ant:opus", "effort": "high"},
                  "small": "or:deepseek/deepseek-chat"}
        name, notes = migrate_legacy_role_table(legacy, state_dir=e.state_dir)
        ctx.check(f"migrated to a team template named 'migrated', got {name}", name == "migrated")
        ctx.check(f"one bio per DISTINCT model (2: deepseek-chat shared, opus, session-default = 3 total "
                  f"bios created), got notes={notes}", sum(1 for n in notes if n.startswith("created agent bio")) == 3)
        resolved = resolve_team_template("migrated", state_dir=e.state_dir)
        role_table, rt_notes = resolve_role_table(resolved, state_dir=e.state_dir)
        ctx.check(f"every legacy role resolved to its ORIGINAL model, got {role_table}",
                  role_table.get("researcher") == "or:deepseek/deepseek-chat"
                  and role_table.get("judge") == {"model": "ant:opus", "effort": "high"}
                  and role_table.get("small") == "or:deepseek/deepseek-chat")
        ctx.check(f"a 'main' assignment was synthesized from the session default, got {role_table}",
                  role_table.get("main") == "or:vendor/session-default")
        ctx.check(f"clean resolution, got {rt_notes}", rt_notes == [])


@test
def test_migrate_legacy_role_table_is_idempotent_never_overwrites(ctx: Ctx):
    from halo_harness.teams_yaml import migrate_legacy_role_table
    from halo_harness.theme import set_config_value
    with _Env() as e:
        set_config_value("model", "or:vendor/session-default")
        first_name, _ = migrate_legacy_role_table({"researcher": "or:deepseek/deepseek-chat"}, state_dir=e.state_dir)
        ctx.check("first call migrates", first_name == "migrated")
        second_name, second_notes = migrate_legacy_role_table({"researcher": "or:something-completely-different"},
                                                                 state_dir=e.state_dir)
        ctx.check(f"second call is a no-op (never overwrites), got {second_name, second_notes}",
                  second_name is None and second_notes == [])


@test
def test_migrate_legacy_role_table_empty_table_is_a_noop(ctx: Ctx):
    from halo_harness.teams_yaml import migrate_legacy_role_table
    with _Env() as e:
        name, notes = migrate_legacy_role_table({}, state_dir=e.state_dir)
        ctx.check(f"nothing to migrate, got {name, notes}", name is None and notes == [])


# ---------------------------------------------------------------------------
# agents_cli.py / teams_cli.py.
# ---------------------------------------------------------------------------

def _run_cli(fn, argv) -> "tuple[int, str]":
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = fn(argv)
    return rc, buf.getvalue()


@test
def test_check_expectation_handles_non_empty_sentinel_and_substring(ctx: Ctx):
    from halo_harness.agents_doctor import check_expectation
    ctx.check("non-empty sentinel: any real text passes", check_expectation("anything at all", "non-empty"))
    ctx.check("non-empty sentinel: blank fails", not check_expectation("   ", "non-empty"))
    ctx.check("substring match, case-insensitive", check_expectation("The Answer is OK.", "ok"))
    ctx.check("substring match failure", not check_expectation("nope", "ok"))
    ctx.check("no expectation at all always passes", check_expectation("", None))


@test
def test_run_acceptance_uses_the_injected_mock_never_a_real_subprocess(ctx: Ctx):
    """"a mock in tests" -- `call_fn` is the seam; this test proves it's
    actually USED (the real `_default_call` would try to spawn `halo -p`,
    which this test never lets happen)."""
    from halo_harness.agents_doctor import run_acceptance
    calls = []

    def fake_call(model_ref, prompt):
        calls.append((model_ref, prompt))
        return "ok, all good"

    bio = {"models": {"preference": "or:vendor/model"}, "acceptance": {"prompt": "say ok", "expect": "ok"}}
    ok, message = run_acceptance(bio, call_fn=fake_call)
    ctx.check(f"passed, using the injected call, got {message!r}", ok and calls == [("or:vendor/model", "say ok")])


@test
def test_run_acceptance_with_no_acceptance_block_is_reported_distinctly(ctx: Ctx):
    from halo_harness.agents_doctor import run_acceptance
    ok, message = run_acceptance({"models": {"preference": "or:x"}})
    ctx.check(f"not ok, distinct message, got {ok, message}", not ok and message == "no acceptance block")


@test
def test_run_all_acceptance_against_every_shipped_bio_with_a_mock(ctx: Ctx):
    from halo_harness.agents_doctor import run_all_acceptance
    with _Env() as e:
        results = run_all_acceptance(state_dir=e.state_dir, call_fn=lambda _r, _p: "ok")
        ctx.check(f"one result per shipped bio, got {len(results)}", len(results) >= 12)
        with_model = [r for r in results if r[0] in ("orchestrator", "reviewer", "implementer")]
        ctx.check(f"the ones WITH a pinned model pass against the mock's 'ok', got {with_model}",
                  all(ok for _n, ok, _m in with_model))


@test
def test_check_active_team_validates_the_configured_team_key(ctx: Ctx):
    from halo_harness.agents_doctor import check_active_team
    from halo_harness.theme import set_config_value
    with _Env() as e:
        ctx.check("no active team -- nothing to check", check_active_team(state_dir=e.state_dir) == [])
        set_config_value("team", "halo-dev-cycle")
        ctx.check("the shipped, valid template -- still nothing to report",
                  check_active_team(state_dir=e.state_dir) == [])
        set_config_value("team", "no-such-team-at-all")
        problems = check_active_team(state_dir=e.state_dir)
        ctx.check(f"an unresolvable active team is reported, got {problems}", len(problems) == 1)


@test
def test_bio_hooks_schedule_triggers_validate_round_trip_and_extend(ctx: Ctx):
    from halo_harness.agents_yaml import resolve_agent_bio, save_agent_bio, validate_agent_bio
    with _Env() as e:
        problems = validate_agent_bio({"description": "x", "hooks": {"pre_tool": [{"command": "echo"}],
                                                                     "bad_key": []}})
        ctx.check(f"an unknown hooks key is a plain line, got {problems}",
                  any("hooks.bad_key" in p for p in problems))
        problems = validate_agent_bio({"description": "x", "hooks": {"pre_tool": [{"match": "Bash"}]}})
        ctx.check(f"a hook entry without command is a plain line, got {problems}",
                  any("command" in p for p in problems))
        problems = validate_agent_bio({"description": "x", "schedule": {"cron": "* * * *", "prompt": "p"}})
        ctx.check(f"a 4-field cron is rejected, got {problems}", any("cron" in p for p in problems))
        problems = validate_agent_bio({"description": "x", "schedule": {"every": "1s"}})
        ctx.check(f"a schedule without a prompt is rejected, got {problems}",
                  any("prompt" in p for p in problems))
        problems = validate_agent_bio({"description": "x", "triggers": [{"on": "cron"}]})
        ctx.check(f"an unknown trigger kind is rejected, got {problems}",
                  any('triggers[0]' in p for p in problems))
        # the good shapes round trip and inherit through extends
        save_agent_bio("hooks-parent", {"description": "p",
                                        "hooks": {"on_start": ["echo hi"]},
                                        "schedule": {"every": "30m", "prompt": "check"}},
                       state_dir=e.state_dir)
        ok, problems = save_agent_bio("hooks-child", {"description": "c", "extends": "hooks-parent"},
                                      state_dir=e.state_dir)
        ctx.check(f"the child saves clean, got {problems}", ok)
        resolved = resolve_agent_bio("hooks-child", state_dir=e.state_dir)
        ctx.check(f"hooks inherit whole through extends, got {resolved.get('hooks')}",
                  resolved.get("hooks") == {"on_start": ["echo hi"]})
        ctx.check(f"schedule inherits whole through extends, got {resolved.get('schedule')}",
                  resolved.get("schedule") == {"every": "30m", "prompt": "check"})


@test
def test_team_new_section_validation_lines(ctx: Ctx):
    from halo_harness.teams_yaml import validate_team_template
    problems = validate_team_template({
        "description": "x",
        "agents": [{"agent": "general", "role": "main", "hooks": {"pre_tool": [{"match": "Bash"}]}}],
        "delegation": {"max_parallel": 0, "forward_text": "yes"},
        "budget": {"max_budget_usd": -1, "agents_may_exceed": "no"},
        "escalation": {"triggers": ["ran-out-of-patience"], "to": 5, "ask": "maybe"},
        "pipeline": {"stages": [{"name": "s", "gate": "required", "acceptance": {"prompt": ""}}]},
    })
    joined = " | ".join(problems)
    for needle in ("max_parallel", "forward_text", "max_budget_usd", "agents_may_exceed",
                   "ran-out-of-patience", '"escalation.to"', '"escalation.ask"', "hooks",
                   "acceptance"):
        ctx.check(f"the validator names {needle!r}, got {joined}", needle in joined)


@test
def test_shipped_templates_still_validate_and_dev_cycle_gains_enforcement_lines(ctx: Ctx):
    from halo_harness.teams_yaml import enforcement_lines, load_team_template_raw, resolve_team_template, \
        validate_team_template
    with _Env():
        raw = load_team_template_raw("halo-dev-cycle")
        problems = validate_team_template(raw, name="halo-dev-cycle")
        ctx.check(f"the shipped dev-cycle lineup validates clean, got {problems}", problems == [])
        template = resolve_team_template("halo-dev-cycle")
        lines = enforcement_lines(template)
        text = "\n".join(lines)
        ctx.check(f"every enforced section names its behaviour, got {text}",
                  all(f"{s}: enforced" in text for s in
                      ("delegation", "routing", "budget", "escalation", "context", "permissions",
                       "pipeline")) and "org:" not in text)
        ctx.check("acceptance carries the doctor marker", "acceptance: checked by doctor" in text)


@test
def test_cli_flags_and_headless_accept_the_team_flag(ctx: Ctx):
    from halo_harness.cli_flags import cli_flags_from_args
    flags = cli_flags_from_args(type("A", (), {"team": "my-lineup"})())
    ctx.check(f"--team lands in cli_flags, got {flags}", flags.get("team") == "my-lineup")
    flags = cli_flags_from_args(type("A", (), {})())
    ctx.check("no flag means no team override", flags.get("team") is None)


# ---------------------------------------------------------------------------
# Halo 2.1.0 round B2: one obvious path to pick and inspect a lineup.
# ---------------------------------------------------------------------------

@test
def test_a_yaml_file_is_parsed_once_per_change(ctx: Ctx):
    """3.5.0.1: a pack's check read every bio again for every stage of every workflow (thousands of parses, seconds
    on every command). A file is parsed once per change; each caller gets its own copy; a file changed in the last
    three seconds is always read from the disk (a same-size rewrite inside one clock tick is never served old)."""
    from halo_harness import agents_yaml as A
    with tempfile.TemporaryDirectory(prefix="yaml-once-") as d:
        f = Path(d) / "coder.yaml"
        f.write_text("name: coder\nkind: coder\ntools: {allow: [Read]}\n", encoding="utf-8")
        old = time.time() - 60
        os.utime(f, (old, old))  # a file that has not changed for a minute
        calls: list = []
        real = A.yaml.safe_load
        A.yaml.safe_load = lambda text: (calls.append(1), real(text))[1]
        try:
            first = A._read_yaml_file(f)
            for _ in range(50):
                A._read_yaml_file(f)
            ctx.check(f"51 reads of a settled, unchanged file parse it once, got {len(calls)}", len(calls) == 1)
            first["tools"]["allow"].append("Bash")
            again = A._read_yaml_file(f)
            ctx.check(f"a caller's change to its copy is not seen by the next reader, got {again['tools']['allow']}",
                      again["tools"]["allow"] == ["Read"])
            # the judge's case: rewrites of the SAME size, back to back, by a writer that is not Halo's own
            stale = 0
            for i in range(200):
                f.write_text(f"count: {i % 10}\n", encoding="utf-8")
                if A._read_yaml_file(f).get("count") != i % 10:
                    stale += 1
            ctx.check(f"200 same-size rewrites, each read back at once: none stale, got {stale}", stale == 0)
            problems = A._write_yaml_file(f, {"name": "coder", "kind": "planner"})
            ctx.check(f"Halo's own write is read back, got {problems} {A._read_yaml_file(f).get('kind')!r}",
                      problems == [] and A._read_yaml_file(f).get("kind") == "planner")
            before = len(calls)
            A._read_yaml_file(f)
            A._read_yaml_file(f)
            ctx.check(f"a file written a moment ago is read from the disk each time, got {len(calls) - before} parses",
                      len(calls) - before == 2)
            ctx.check("a file that is not there is None", A._read_yaml_file(Path(d) / "none.yaml") is None)
        finally:
            A.yaml.safe_load = real


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
