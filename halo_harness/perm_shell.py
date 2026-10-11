"""halo_harness.perm_shell -- shell-form normalisation tables for the DENY and
ASK side of the permission engine (2.0.10 review, findings 12, 13).

A deny or ask rule the user wrote (`Bash(rm:*)`, `Bash(git push:*)`) must
still fire when the same command is reached through a compound keyword
(`if ...; then rm x; fi`, `for f in a; do rm $f; done`, `! rm x`), a wrapper
(`watch`, `flock`, `strace`, `unshare`, ...), or a tool's global options
(`git -C x push`, `docker --context x run`, `kubectl -n x delete`).

Everything here only ever ADDS candidate strings for deny/ask matching. It
is a leaf module (no import of permissions.py) and never touches the allow
side, and it adds no judgement about which commands are dangerous.
"""
from __future__ import annotations

import os
import re
import shlex

# Words that precede the real command inside a compound statement.
CONTROL_WORDS = frozenset({"if", "then", "else", "elif", "do", "while", "until", "!", "time", "coproc"})

# Extra transparent wrappers for deny/ask (permissions._DENY_STRIP_WRAPPERS
# is the union of its own set and this one).
EXTRA_WRAPPERS = frozenset({
    "exec", "watch", "flock", "unshare", "chroot", "strace", "ltrace", "fakeroot",
    "fakeroot-sysv", "nsenter", "taskset", "chrt", "setarch", "runuser", "pkexec",
    "unbuffer", "eatmydata", "proxychains", "proxychains4", "torsocks", "caffeinate",
    "busybox", "setpriv", "firejail",
})

# Options that consume a separate value token, per wrapper.
EXTRA_WRAPPER_VALUE_OPTS = {
    "exec": {"-a"},
    "watch": {"-n", "--interval"},
    "flock": {"-w", "--timeout", "-E", "--conflict-exit-code"},
    "unshare": {"-R", "-w", "--root", "--wd", "--propagation", "--map-user", "--map-group", "--setgroups"},
    "strace": {"-o", "-e", "-p", "-s", "-u", "-E", "-a", "-I", "-P", "-O", "-b", "-X", "-S", "-U"},
    "ltrace": {"-o", "-e", "-p", "-s", "-u", "-n", "-a", "-l"},
    "fakeroot": {"-l", "-i", "-s", "-b", "--lib", "--faked"},
    "fakeroot-sysv": {"-l", "-i", "-s", "-b", "--lib", "--faked"},
    "nsenter": {"-t", "--target", "-S", "-G", "--setuid", "--setgid", "-w", "--wd"},
    "taskset": {"-c", "--cpu-list"},
    "chrt": {"-T", "-P", "-D"},
    "runuser": {"-u", "-g", "-G", "-l", "-s", "-c"},
    "pkexec": {"--user"},
    "chroot": {"--userspec", "--groups"},
    "setpriv": {"--reuid", "--regid", "--groups", "--inh-caps", "--bounding-set", "--ruid", "--euid"},
}

# Positional operands a wrapper takes BEFORE the command (name -> count).
EXTRA_WRAPPER_POSITIONAL = {"flock": 1, "chroot": 1, "setarch": 1, "taskset": 1}
# `taskset -c LIST cmd` / `taskset -p ...` carry no mask positional.
POSITIONAL_SKIPPED_BY = {"taskset": {"-c", "--cpu-list", "-p", "--pid"}}
# Wrappers whose positional chrt priority is a bare number.
NUMERIC_AFTER_OPTS = frozenset({"timeout", "nice", "chrt"})

# Wrappers that take their command as a `-c STRING` payload.
_C_PAYLOAD_WRAPPERS = frozenset({"flock", "runuser", "su"})


def tokenize(segment: str) -> list:
    try:
        return shlex.split(segment, posix=True)
    except ValueError:
        return segment.split()


def strip_case_prefix(tokens: list) -> bool:
    """Drop a `case WORD in` head and a leading `pattern)` token in place
    (so `case a in a) rm x` and the later arm `b) rm y` surface `rm ...`).
    Returns True when something was dropped."""
    changed = False
    if tokens and tokens[0] == "case" and "in" in tokens:
        del tokens[:tokens.index("in") + 1]
        changed = True
    if tokens and tokens[0].endswith(")") and "(" not in tokens[0].lstrip("("):
        tokens.pop(0)
        changed = True
    return changed


# ---- finding 13: tool-global options between the binary and the verb -------

_NPM_VALUE = {"--prefix", "--workspace", "-w", "--registry", "--userconfig", "--globalconfig",
              "--cache", "--loglevel", "--tag", "--otp", "--scope", "--location", "--include",
              "--omit", "--install-strategy", "--fetch-retries"}
_DOCKER_VALUE = {"--context", "-c", "-H", "--host", "--config", "-l", "--log-level",
                 "--tlscacert", "--tlscert", "--tlskey"}
_COMPOSE_VALUE = {"-f", "--file", "-p", "--project-name", "--profile", "--env-file",
                  "--project-directory", "--ansi", "--parallel", "--progress"}
_KUBECTL_VALUE = {"-n", "--namespace", "--context", "--kubeconfig", "-s", "--server", "--cluster",
                  "--user", "--token", "--as", "--as-group", "-v", "--v", "--cache-dir",
                  "--certificate-authority", "--client-certificate", "--client-key", "--request-timeout"}
_GIT_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--super-prefix", "--config-env",
              "--exec-path", "--attr-source"}

TOOL_GLOBAL_VALUE_OPTS = {
    "git": _GIT_VALUE,
    "docker": _DOCKER_VALUE, "podman": _DOCKER_VALUE,
    "kubectl": _KUBECTL_VALUE, "oc": _KUBECTL_VALUE,
    "helm": {"-n", "--namespace", "--kube-context", "--kubeconfig", "--kube-apiserver",
             "--kube-token", "--registry-config", "--repository-config", "--repository-cache"},
    "npm": _NPM_VALUE, "npx": _NPM_VALUE,
    "pnpm": {"-C", "--dir", "--filter", "-F", "--workspace-root", "--reporter", "--loglevel"},
    "yarn": {"--cwd", "--registry", "--cache-folder", "--modules-folder", "--network-timeout"},
    "cargo": {"-C", "--config", "--color", "--manifest-path", "-Z"},
    "uv": {"--directory", "--project", "--config-file", "--cache-dir", "--color", "-p", "--python"},
    "pip": {"--python", "--log", "--proxy", "--retries", "--timeout", "--cache-dir", "--cert"},
    "pip3": {"--python", "--log", "--proxy", "--retries", "--timeout", "--cache-dir", "--cert"},
    "gh": {"-R", "--repo", "--hostname"},
    "terraform": set(),
    "aws": {"--profile", "--region", "--output", "--endpoint-url", "--query", "--ca-bundle",
            "--cli-read-timeout", "--cli-connect-timeout"},
    "systemctl": {"-H", "--host", "-M", "--machine", "-t", "--type", "-p", "--property", "-n", "--lines", "-o", "--output"},
    "make": {"-C", "--directory", "-f", "--file", "-j", "--jobs", "-I", "--include-dir"},
}


def _drop_leading_options(tokens: list, value_opts) -> bool:
    """Remove leading `-x` / `--opt[=v]` words (and the value token of a
    value-taking option written without `=`) from `tokens` in place. A `+toolchain`
    word (cargo, rustup) is dropped too."""
    changed = False
    while tokens and (tokens[0].startswith("+") and len(tokens[0]) > 1 or
                      (tokens[0].startswith("-") and tokens[0] != "-")):
        if tokens[0] == "--":
            break
        opt = tokens.pop(0)
        changed = True
        if opt.startswith("-") and "=" not in opt and opt in value_opts and tokens:
            tokens.pop(0)
    return changed


def strip_tool_global_options(candidate: str) -> str:
    """`git -C x push` -> `git push`; `docker --context x compose -f f up` ->
    `docker compose up`. Returns "" when the candidate is not one of the
    tools above or has no global options to drop."""
    tokens = tokenize(candidate.strip())
    if len(tokens) < 2:
        return ""
    head = tokens[0].replace("\\", "/").rsplit("/", 1)[-1].lower()
    head = re.sub(r"\.(exe|cmd|bat)$", "", head)
    if head not in TOOL_GLOBAL_VALUE_OPTS:
        return ""
    rest = tokens[1:]
    changed = _drop_leading_options(rest, TOOL_GLOBAL_VALUE_OPTS[head])
    if head in ("docker", "podman") and rest[:1] == ["compose"]:
        tail = rest[1:]
        if _drop_leading_options(tail, _COMPOSE_VALUE):
            rest = ["compose"] + tail
            changed = True
    if not changed or not rest:
        return ""
    return " ".join([tokens[0]] + rest)


# ---- payloads carried as a string or as exec arguments ----------------------

def payload_strings(segment: str) -> list:
    """Command text a wrapper hands to a shell or to exec: `flock f -c
    'rm x'`, `runuser u -c 'rm x'`, `find . -exec rm {} ;`. Each is a mini
    command line the deny/ask matcher scans like a segment. The wrapper may
    sit behind other words (`do find ...`, `sudo find ...`)."""
    tokens = tokenize(segment.strip())
    out: list = []
    heads = [i for i, t in enumerate(tokens) if t.replace("\\", "/").rsplit("/", 1)[-1] in _C_PAYLOAD_WRAPPERS]
    if heads:
        for i in range(heads[0] + 1, len(tokens) - 1):
            if tokens[i] in ("-c", "--command"):
                out.append(tokens[i + 1])
    flags = ("-exec", "-execdir", "-ok", "-okdir", "--exec", "--exec-batch")
    i = 0
    while i < len(tokens):
        if tokens[i] in flags:
            j = i + 1
            body = []
            while j < len(tokens) and tokens[j] not in (";", "+", chr(92) + ";"):
                body.append(tokens[j])
                j += 1
            if body:
                out.append(" ".join(body))
            i = j
        i += 1
    return out


def expand_home_token(token: str) -> str:
    """`~` / `~/x` / `$HOME/x` / `${HOME}/x` -> the user's home path, the way
    the shell would expand them; any other token is returned unchanged."""
    if token == "~" or token.startswith("~/"):
        return os.path.expanduser(token)
    for prefix in ("${HOME}", "$HOME"):
        if token == prefix or token.startswith(prefix + "/"):
            return os.path.expanduser("~") + token[len(prefix):]
    return token
