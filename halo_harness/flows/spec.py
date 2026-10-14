"""halo_harness.flows.spec -- the flow file: where it lives, loading it,
`validate_flow` and the step lookups.

A flow is `~/.halo/flows/<name>.flow.yaml` (user) or `<cwd>/.halo/flow.yaml`
(project, wins when its `name:` matches); the shipped templates are
`halo_harness/templates/flows/<name>.flow.yaml`. `validate_flow(data)`
returns plain-English lines; a line that starts with "warning: " does not
stop a run, every other line does (`errors(lines)`).
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

from halo_harness.flows.refs import is_ref, parse_ref, refs_in, resolve_ref, resolve_value  # noqa: F401

KINDS = ("intake", "roles", "org", "render", "confirm", "post", "metrics", "done")
FORM_TYPES = ("text", "number", "files")
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "flows"
SUFFIX = ".flow.yaml"
_VAR = re.compile(r"\{\{\s*intake\.([A-Za-z0-9_]+)\s*\}\}")


def flows_dir(state_dir=None) -> Path:
    if state_dir is None:
        from halo_harness.config.paths import bridge_home
        state_dir = bridge_home()
    return Path(state_dir) / "flows"


def template_names() -> list:
    return sorted(p.name[:-len(SUFFIX)] for p in TEMPLATES_DIR.glob("*" + SUFFIX))


def template_path(name: str) -> Optional[Path]:
    p = TEMPLATES_DIR / f"{name}{SUFFIX}"
    return p if p.is_file() else None


def load_flow(path) -> dict:
    """The parsed flow file; ValueError with a plain message when it is not YAML or not a mapping."""
    import yaml
    path = Path(path)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as e:
        raise ValueError(f"cannot read {path}: {e}") from None
    except yaml.YAMLError as e:
        raise ValueError(f"{path} is not valid YAML: {e}") from None
    if not isinstance(data, dict):
        raise ValueError(f"{path}: a flow file is a mapping with name, steps, ...")
    return data


def find_flow(name: str, *, cwd=None, state_dir=None) -> Optional[Path]:
    """Project `.halo/flow.yaml` with that name, then the user's flow, then a
    shipped template, then `name` as a path."""
    project = Path(cwd or os.getcwd()) / ".halo" / "flow.yaml"
    if project.is_file():
        try:
            if load_flow(project).get("name") == name:
                return project
        except ValueError:
            pass
    user = flows_dir(state_dir) / f"{name}{SUFFIX}"
    if user.is_file():
        return user
    shipped = template_path(name)
    if shipped is not None:
        return shipped
    direct = Path(name).expanduser()
    return direct if direct.is_file() and direct.suffix in (".yaml", ".yml") else None


def list_flows(*, cwd=None, state_dir=None) -> list:
    d = flows_dir(state_dir)
    names = sorted(p.name[:-len(SUFFIX)] for p in d.glob("*" + SUFFIX)) if d.is_dir() else []
    return names


def render_vars(value, intake: dict):
    """`{{intake.<key>}}` in a string, filled from the intake values ('' when absent)."""
    if isinstance(value, str):
        return _VAR.sub(lambda m: str(intake.get(m.group(1)) or ""), value)
    return value


def step_by_id(spec: dict, step_id: str) -> Optional[dict]:
    return next((s for s in spec.get("steps") or [] if isinstance(s, dict) and s.get("id") == step_id), None)


def step_index(spec: dict, step_id: str) -> int:
    for i, s in enumerate(spec.get("steps") or []):
        if isinstance(s, dict) and s.get("id") == step_id:
            return i
    return -1


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0


def errors(lines: list) -> list:
    return [line for line in lines if not str(line).startswith("warning: ")]


def postiz_configured(env: Optional[dict] = None) -> bool:
    src = os.environ if env is None else env
    if str(src.get("POSTIZ_API_KEY") or "").strip():
        return True
    from halo_harness.config.paths import home
    return (Path(home()) / ".postiz" / "credentials.json").is_file()


def _comfy_known(workflow: str, state_dir, cwd) -> bool:
    from halo_harness.media.comfy_ops import load_starter
    if load_starter(workflow) is not None:
        return True
    p = Path(workflow).expanduser()
    if (p if p.is_absolute() else Path(cwd or os.getcwd()) / p).is_file():
        return True
    try:
        from halo_harness.providers.media_models import load_cached
        saved = load_cached(state_dir if state_dir is not None else flows_dir().parent).get("workflows") or []
    except Exception:
        saved = []
    stem = workflow[:-5] if workflow.lower().endswith(".json") else workflow
    return any(str(n) in (stem, stem + ".json") for n in saved)


def _check_uses(step: dict, kind: str, sid: str, *, cwd, state_dir, env) -> list:
    uses = str(step.get("uses") or "")
    out = []
    if kind == "roles":
        if not uses.startswith("lineup:"):
            return [f"step {sid}: a roles step uses \"lineup:<name>\", got {uses or 'nothing'!r}"]
        from halo_harness.teams_yaml import list_team_templates, resolve_team_template
        name = uses[len("lineup:"):]
        if resolve_team_template(name, cwd=cwd, state_dir=state_dir) is None:
            out.append(f"step {sid}: lineup {name!r} does not resolve (known: {', '.join(list_team_templates(cwd=cwd, state_dir=state_dir))})")
        roles = step.get("roles")
        if not isinstance(roles, list) or not roles or not all(isinstance(r, str) and r for r in roles):
            out.append(f"step {sid}: roles is a non-empty list of role names")
    elif kind == "org":
        if not uses.startswith("org:"):
            return [f"step {sid}: an org step uses \"org:<name>\", got {uses or 'nothing'!r}"]
        from halo_harness.orgs import list_orgs, load_org
        name = uses[len("org:"):]
        if load_org(name, state_dir=state_dir) is None:
            out.append(f"step {sid}: org {name!r} is not found or does not validate (known: {', '.join(list_orgs(state_dir=state_dir))})")
    elif kind == "render":
        if not uses.startswith("comfy:"):
            return [f"step {sid}: a render step uses \"comfy:<workflow>\", got {uses or 'nothing'!r}"]
        wf = uses[len("comfy:"):]
        if not _comfy_known(wf, state_dir, cwd):
            out.append(f"warning: step {sid}: workflow {wf!r} is not a starter, a file or a saved workflow in the "
                       "inventory cache (`halo media models` refreshes it); it is checked again on the server at run time")
    elif kind == "metrics":
        from halo_harness.flows.postiz_parse import parse_every
        if step.get("every") is not None and parse_every(step.get("every")) is None:
            out.append(f"step {sid}: every is a duration like 30m, 6h or 1d, got {step.get('every')!r}")
    elif kind == "post":
        if step.get("live") is True and not postiz_configured(env):
            out.append(f"warning: step {sid}: live: true, and neither POSTIZ_API_KEY nor ~/.postiz/credentials.json is set")
    return out


def validate_flow(data, *, cwd=None, state_dir=None, env: Optional[dict] = None) -> list:
    if not isinstance(data, dict):
        return ["a flow file is a mapping with name, steps, ..."]
    lines = []
    if not isinstance(data.get("name"), str) or not data.get("name").strip():
        lines.append("name: give the flow a name")
    if "budget_usd" in data and not _num(data.get("budget_usd")):
        lines.append(f"budget_usd: a non-negative number, got {data.get('budget_usd')!r}")
    steps = data.get("steps")
    if not isinstance(steps, list) or not steps:
        return lines + ["steps: a non-empty list of steps"]
    seen, step_budgets, rendered = [], 0.0, []
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            lines.append(f"step #{i + 1}: a mapping with id and kind")
            continue
        sid, kind = str(step.get("id") or ""), step.get("kind")
        if not sid:
            lines.append(f"step #{i + 1}: needs an id")
            sid = f"#{i + 1}"
        elif sid in seen:
            lines.append(f"step {sid}: duplicate id")
        if kind not in KINDS:
            lines.append(f"step {sid}: unknown kind {kind!r} (expected one of {', '.join(KINDS)})")
        for ref in refs_in([step.get("inputs"), step.get("set")]):
            try:
                target = parse_ref(ref)[0]
            except ValueError as e:
                lines.append(f"step {sid}: {e}")
                continue
            if target not in seen:
                later = any(isinstance(s, dict) and s.get("id") == target for s in steps[i:])
                lines.append(f"step {sid}: {ref} refers to {'a later' if later else 'an unknown'} step {target!r}")
        if "budget_usd" in step:
            if _num(step.get("budget_usd")):
                step_budgets += float(step["budget_usd"])
            else:
                lines.append(f"step {sid}: budget_usd is a non-negative number, got {step.get('budget_usd')!r}")
        if kind == "intake":
            form = step.get("form")
            if not isinstance(form, dict) or not form:
                lines.append(f"step {sid}: an intake step has a form {{field: text|number|files|[choices]}}")
            else:
                for f, t in form.items():
                    if not (t in FORM_TYPES or isinstance(t, list)):
                        lines.append(f"step {sid}: form field {f}: {t!r} is not text, number, files or a list of choices")
        if kind == "confirm":
            if not rendered:
                lines.append(f"step {sid}: a confirm step needs a render step before it")
            on_fail = str(step.get("on_fail") or "")
            if on_fail and not (on_fail.startswith("redo:") and on_fail[5:] in rendered):
                lines.append(f"step {sid}: on_fail is \"redo:<an earlier render step>\", got {on_fail!r}")
        if kind in KINDS:
            lines += _check_uses(step, kind, sid, cwd=cwd, state_dir=state_dir, env=env)
        if kind == "render":
            rendered.append(sid)
        seen.append(sid)
    if _num(data.get("budget_usd")) and step_budgets > float(data["budget_usd"]) + 1e-9:
        lines.append(f"warning: the step budgets add up to ${step_budgets:.2f}, above the run budget "
                     f"${float(data['budget_usd']):.2f}; the run stops at its own budget")
    return lines
