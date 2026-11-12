"""halo_harness.permissions_bash_io -- the files a Bash file command writes or takes away (Halo 3.4.1.2, ENGINE-4).

`permissions.py` gated redirect targets (`> .env`) by Edit deny rules and the readers' operands (`cat .env`) by Read
deny rules; `tee .env`, `cp x .env`, `mv x .env`, `rm .env`, `truncate -s0 .env`, `ln .env y`, `mv .env y` and
`dd if=.env` went through. These two lists close that set:

    write_targets(tokens) -> [word]   what cp / mv / install / ln / tee / rm / unlink / shred / truncate / dd, and
                                      curl -o / wget -O / rsync's local destination write or remove (a destination
                                      folder also names `<folder>/<source name>`)
    read_sources(tokens)  -> [word]   what mv / ln / dd take or expose (mv's and ln's sources, dd's `if=`)
`tokens` is one command's words with wrappers already stripped (permissions._deny_tokens). Interpreters stay out of
scope, as before (python -c, perl -e: the engine does not read code).
"""

from __future__ import annotations

_COPIERS = {"cp", "mv", "install", "ln"}
_REMOVERS = {"rm", "unlink", "shred", "tee", "truncate"}
#: short options that take the next word as their value (so it is not an operand)
_VALUE_OPTS = {"cp": {"-t", "-S"}, "mv": {"-t", "-S"}, "install": {"-t", "-S", "-m", "-o", "-g"}, "ln": {"-t", "-S"},
               "truncate": {"-s", "-r", "-o"}, "shred": {"-n", "-s"}}


def _head(tokens: list) -> str:
    return tokens[0].replace("\\", "/").rsplit("/", 1)[-1] if tokens else ""


def _split(head: str, args: list) -> "tuple[list, str, list]":
    """(positional operands, the -t / --target-directory folder or '', the values of value options)."""
    pos, target, values, take = [], "", [], None
    for tok in args:
        if take is not None:
            target = tok if take in ("-t", "--target-directory") else target
            values.append(tok)
            take = None
            continue
        if tok == "--":
            continue
        if tok.startswith("--"):
            name, eq, value = tok.partition("=")
            if name == "--target-directory":
                target, take = (value, None) if eq else ("", name)
            elif name in ("--reference", "--suffix", "--size", "--mode", "--owner", "--group") and not eq:
                take = name
            continue
        if tok.startswith("-") and tok != "-":
            if tok[:2] in _VALUE_OPTS.get(head, set()):
                if len(tok) == 2:
                    take = tok[:2]
                elif tok[:2] == "-t":
                    target = tok[2:]
            continue
        pos.append(tok)
    return pos, target, values


def _base(word: str) -> str:
    return word.rstrip("/\\").replace("\\", "/").rsplit("/", 1)[-1]


def _download_targets(head: str, args: list) -> list:
    """`curl -o FILE` / `--output FILE`, `wget -O FILE` / `--output-document=FILE` (glued forms too)."""
    short, long = ("-o", "--output") if head == "curl" else ("-O", "--output-document")
    out = [args[i + 1] for i, a in enumerate(args[:-1]) if a in (short, long)]
    out += [a.split("=", 1)[1] for a in args if a.startswith(long + "=")]
    return out + [a[2:] for a in args if a.startswith(short) and len(a) > 2 and not a.startswith("--")]


def write_targets(tokens: list) -> list:
    head, args = _head(tokens), tokens[1:]
    if head == "dd":
        return [a[3:] for a in args if a.startswith("of=")]
    if head in ("curl", "wget"):
        return _download_targets(head, args)
    if head == "rsync":  # its last operand, when it is a local path
        pos = [a for a in args if not a.startswith("-")]
        return [pos[-1]] if len(pos) > 1 and ":" not in pos[-1] else []
    if head not in _COPIERS | _REMOVERS:
        return []
    pos, target, _values = _split(head, args)
    if head in _REMOVERS:
        return pos
    gone = lambda sources: list(sources) if head == "mv" else []  # noqa: E731 -- a move takes its sources away too
    if target:
        return [target] + [f"{target.rstrip('/')}/{_base(s)}" for s in pos] + gone(pos)
    if head == "ln" and len(pos) == 1:
        return [_base(pos[0])]  # `ln x` links ./x
    if len(pos) < 2:
        return []
    dest, sources = pos[-1], pos[:-1]
    return [dest] + [f"{dest.rstrip('/')}/{_base(s)}" for s in sources] + gone(sources)


def read_sources(tokens: list) -> list:
    head, args = _head(tokens), tokens[1:]
    if head == "dd":
        return [a[3:] for a in args if a.startswith("if=")]
    if head == "truncate":  # `-r FILE` / `--reference=FILE` reads FILE's size
        return [args[i + 1] for i, a in enumerate(args[:-1]) if a in ("-r", "--reference")] + \
            [a.split("=", 1)[1] for a in args if a.startswith("--reference=")]
    if head not in ("mv", "ln"):
        return []
    pos, target, _values = _split(head, args)
    return pos if (target or len(pos) == 1) else pos[:-1]
