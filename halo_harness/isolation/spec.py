"""halo_harness.isolation.spec -- reading the three opt-ins (Halo 3.1.8.0 R5).

    isolation: container                      # the defaults below
    isolation: {mode: container, image: <name>, mounts: ["<host>:<container>[:ro]"],
                network: host | none, env: [KEYS the worker may see]}   # host the default
    isolation: {mode: user, user: <name>, group: <optional>, env: [...]}
    secrets: {broker: 1password | env, account: <optional>}
    environment:                              # a bio's
      secrets: [{env: OPENROUTER_API_KEY, ref: "op://<vault>/<item>/<field>"}]
      pass_to_tools: [KEY]                    # a broker key its tool children may see too

`isolation` and `secrets` sit on a lineup (every worker) or a bio (its
workers; the bio wins). `for_lane` answers what one Orchestra lane runs
with: the goal's lineup (or the probe's `team`), the lane's bio (the plan's
`bio`, else the lineup's member for the goal's worker role), and the
`tools.capabilities` list (isolation/capabilities.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

MODES = ("container", "user")
NETWORKS = ("host", "none")  # host the default: a worker reaches its model provider; none: a model inside the image
BROKERS = ("1password", "env")
_ISO_KEYS = ("mode", "image", "mounts", "network", "env", "user", "group")


def isolation_of(value) -> Optional[dict]:
    """The declaration as a mapping with its defaults (`isolation: container` alone = the defaults); None unset."""
    if value is None or value == "" or value is False:
        return None
    raw = {"mode": value} if isinstance(value, str) else dict(value) if isinstance(value, dict) else {}
    out = {"mode": str(raw.get("mode") or "container"), "env": [str(k) for k in raw.get("env") or []]}
    if out["mode"] == "container":
        from halo_harness.isolation.container import default_image
        out.update(image=str(raw.get("image") or default_image()), mounts=[str(m) for m in raw.get("mounts") or []],
                   network=str(raw.get("network") or "host"))
    else:
        out.update(user=str(raw.get("user") or ""), group=str(raw.get("group") or ""))
    return out


def isolation_problems(value, where: str = "isolation") -> "list[str]":
    if value is None:
        return []
    if isinstance(value, str):
        return [] if value in MODES else [f'"{where}" {value!r} is not one of {", ".join(MODES)}']
    if not isinstance(value, dict):
        return [f'"{where}" must be container, user or a mapping with "mode"']
    out = [f'"{where}.{k}" is not a key of isolation ({", ".join(_ISO_KEYS)})' for k in value if k not in _ISO_KEYS]
    mode = value.get("mode", "container")
    if mode not in MODES:
        out.append(f'"{where}.mode" {mode!r} is not one of {", ".join(MODES)}')
    if value.get("network") is not None and value.get("network") not in NETWORKS:
        out.append(f'"{where}.network" {value.get("network")!r} is not one of {", ".join(NETWORKS)}')
    for key in ("mounts", "env"):
        v = value.get(key)
        if v is not None and not (isinstance(v, list) and all(isinstance(x, str) and x.strip() for x in v)):
            out.append(f'"{where}.{key}" must be a list of strings')
    for m in value.get("mounts") or [] if isinstance(value.get("mounts"), list) else []:
        if isinstance(m, str) and ":" not in m.strip().strip(":"):
            out.append(f'"{where}.mounts" {m!r} is not <host path>:<container path>[:ro]')
    if mode == "user" and not (isinstance(value.get("user"), str) and value.get("user").strip()):
        out.append(f'"{where}.user" is required with mode user')
    if value.get("image") is not None and not (isinstance(value.get("image"), str) and value.get("image").strip()):
        out.append(f'"{where}.image" must be an image name')
    return out


def secrets_problems(value, where: str = "secrets") -> "list[str]":
    if value is None:
        return []
    if not isinstance(value, dict):
        return [f'"{where}" must be a mapping {{broker: {" | ".join(BROKERS)}, account: <optional>}}']
    out = [f'"{where}.{k}" is not a key of secrets (broker, account)' for k in value if k not in ("broker", "account")]
    if value.get("broker") not in BROKERS:
        out.append(f'"{where}.broker" {value.get("broker")!r} is not one of {", ".join(BROKERS)}')
    if value.get("account") is not None and not isinstance(value.get("account"), str):
        out.append(f'"{where}.account" must be a string')
    return out


def env_secrets_problems(environment, where: str = "environment") -> "list[str]":
    """A bio's `environment.secrets` and `environment.pass_to_tools`."""
    env = environment if isinstance(environment, dict) else {}
    out = []
    refs = env.get("secrets")
    if refs is not None:
        ok = isinstance(refs, list) and all(isinstance(r, dict) and isinstance(r.get("env"), str) and r.get("env").strip()
                                            and isinstance(r.get("ref"), str) and r.get("ref").strip() for r in refs)
        if not ok:
            out.append(f'"{where}.secrets" must be a list of {{env: <KEY>, ref: <broker ref>}}')
    passes = env.get("pass_to_tools")
    if passes is not None and not (isinstance(passes, list) and all(isinstance(k, str) and k.strip() for k in passes)):
        out.append(f'"{where}.pass_to_tools" must be a list of env names')
    return out


def _tools_problems(tools, where: str) -> "list[str]":
    from halo_harness.isolation.capabilities import problems
    if tools is None:
        return []
    if not isinstance(tools, dict):
        return [f'"{where}" must be a mapping']
    return problems(tools.get("capabilities"), f"{where}.capabilities")


def lineup_problems(data: dict) -> "list[str]":
    """teams_yaml.validate_team_template's one call: isolation, secrets, every tools.capabilities."""
    out = isolation_problems(data.get("isolation")) + secrets_problems(data.get("secrets"))
    out += _tools_problems(data.get("tools"), "tools")
    for i, tier in enumerate(data.get("tiers") if isinstance(data.get("tiers"), list) else []):
        out += _tools_problems(tier.get("tools") if isinstance(tier, dict) else None, f"tiers[{i}].tools")
    for i, entry in enumerate(data.get("agents") if isinstance(data.get("agents"), list) else []):
        if isinstance(entry, dict) and isinstance(entry.get("tools"), dict):
            out += _tools_problems(entry["tools"], f"agents[{i}].tools")
    return out


def bio_problems(data: dict) -> "list[str]":
    """agents_yaml.validate_agent_bio's one call: isolation, secrets, tools.capabilities, environment.secrets."""
    out = isolation_problems(data.get("isolation")) + secrets_problems(data.get("secrets"))
    if isinstance(data.get("tools"), dict):
        out += _tools_problems(data["tools"], "tools")
    return out + env_secrets_problems(data.get("environment"))


def refs_of(bio: Optional[dict]) -> "list[tuple[str, str]]":
    env = (bio or {}).get("environment") if isinstance((bio or {}).get("environment"), dict) else {}
    return [(str(r["env"]).strip(), str(r["ref"]).strip()) for r in env.get("secrets") or []
            if isinstance(r, dict) and r.get("env") and r.get("ref")]


def pass_of(bio: Optional[dict]) -> "list[str]":
    env = (bio or {}).get("environment") if isinstance((bio or {}).get("environment"), dict) else {}
    return [str(k).strip() for k in env.get("pass_to_tools") or [] if str(k).strip()]


@dataclass
class OptIns:
    """What one lane runs with; every field empty when nothing is declared."""
    lineup: str = ""
    bio: str = ""
    isolation: Optional[dict] = None
    isolation_by: str = ""
    secrets: Optional[dict] = None          # {broker, account, refs: [(env, ref)], pass: [keys], by}
    caps: Optional[list] = None
    caps_by: str = ""
    problems: list = field(default_factory=list)

    @property
    def declared(self) -> bool:
        return bool(self.isolation or self.secrets or self.caps is not None)


def _member(template: dict, worker: str, bio_name: str) -> "tuple[Optional[str], Optional[dict]]":
    for e in template.get("agents") or []:
        if not isinstance(e, dict):
            continue
        key = e.get("as") or e.get("role")
        if (bio_name and e.get("agent") == bio_name) or (not bio_name and worker in (e.get("as"), e.get("role"))):
            return key, e
    return None, None


def resolve(lineup: Optional[dict], lineup_name: str, bio: Optional[dict], bio_name: str,
            alias: Optional[str] = None) -> OptIns:
    from halo_harness.isolation import capabilities as C
    out = OptIns(lineup=lineup_name, bio=bio_name)
    lineup, bio = lineup or {}, bio or {}
    for value, by in ((bio.get("isolation"), f"bio {bio_name}"), (lineup.get("isolation"), f"lineup {lineup_name}")):
        if value:
            out.isolation, out.isolation_by = isolation_of(value), by
            break
    broker = next(((v, by) for v, by in ((bio.get("secrets"), f"bio {bio_name}"),
                                         (lineup.get("secrets"), f"lineup {lineup_name}")) if v), None)
    refs = refs_of(bio)
    if broker or refs:
        conf = broker[0] if broker and isinstance(broker[0], dict) else {}
        out.secrets = {"broker": str(conf.get("broker") or ""), "account": conf.get("account") or "",
                       "refs": refs, "pass": pass_of(bio), "by": broker[1] if broker else f"bio {bio_name}"}
    out.caps, out.caps_by = C.resolve(lineup, lineup_name, alias, bio or None, bio_name)
    return out


def for_lane(run_dir, job, *, team: Optional[str] = None) -> OptIns:
    """The lane's opt-ins from the goal's lineup (or `team`) and the lane's bio. Never raises:
    an unreadable lineup or bio declares nothing."""
    try:
        from halo_harness.agents_yaml import resolve_agent_bio
        from halo_harness.orchestra.goal import load_goal, repo_root_of
        from halo_harness.teams_yaml import resolve_team_template
        run_dir = Path(run_dir)
        repo = repo_root_of(run_dir)
        goal = load_goal(run_dir / "goal.json")
        name = team or goal.lineup or ""
        template = resolve_team_template(name, cwd=repo) if name else None
        bio_name = str(getattr(job, "bio", "") or "")
        alias, entry = _member(template or {}, goal.worker, bio_name)
        bio_name = bio_name or str((entry or {}).get("agent") or "")
        bio = resolve_agent_bio(bio_name, cwd=repo) if bio_name else None
        return resolve(template, name, bio, bio_name, alias)
    except Exception:
        return OptIns()
