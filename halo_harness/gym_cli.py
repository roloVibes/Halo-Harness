"""halo_harness.gym_cli -- Halo 2.0.3 round 5d: `halo gym [--models ...]
[--roles ...] [--quick]`, `halo gym show [model]`, `halo gym propose
[--apply] [--roles ...] [--main REF] [--name NAME]`, `halo gym handout
<model> [<model> ...] [--trials N]` (3.6.0.13). Argparse + printing
only -- `gym_run.py`/`gym_propose.py`/`gym.py`/`gym_handout.py` do the actual work, same
module split as `roles_cli.py` over `roles.py`.
"""

from __future__ import annotations

import argparse
import sys

from halo_harness.gym import SUPPORTING_ROLES


def _parse_csv(raw) -> "list":
    return [v.strip() for v in raw.split(",") if v.strip()] if raw else []


def _parse_roles(raw) -> "list":
    names = _parse_csv(raw)
    unknown = [n for n in names if n not in SUPPORTING_ROLES]
    if unknown:
        raise ValueError(f"--roles: unknown role(s) {', '.join(unknown)} (expected a subset of "
                          f"{', '.join(SUPPORTING_ROLES)})")
    return names


def _cmd_run(argv: list) -> int:
    from halo_harness.config.paths import bridge_home
    from halo_harness.gym import format_card
    from halo_harness.gym_propose import composite_score
    from halo_harness.gym_run import run_gym

    parser = argparse.ArgumentParser(
        prog="halo gym", add_help=True,
        description="Run the fixed task battery against local models on THIS machine's hardware and score "
                    "each one -- tool-call accuracy, edit success, context recall, instruction adherence, "
                    "tokens/second, prefill seconds. ol:, hf:local/*, and hf:mlx/* refs are all local.")
    parser.add_argument("--models", default=None, metavar="REF,REF,...",
                         help="comma-separated ol:/hf:local/hf:mlx refs (default: every model in the default "
                             "Ollama host's own catalog); a cloud/router/endpoint ref is accepted for "
                             "comparison but never run by default")
    parser.add_argument("--roles", default=None, metavar="ROLE,ROLE,...",
                         help="also print each model's weighted composite for these roles (default: "
                             f"{', '.join(SUPPORTING_ROLES)})")
    parser.add_argument("--quick", action="store_true", help="halve the battery size N for a faster, "
                                                              "noisier read")
    parser.add_argument("--show-replies", action="store_true",
                         help="print each reply-only task's actual excerpt (first 200 chars) alongside its "
                             "score -- samples are always saved in the result JSON regardless of this flag")
    args = parser.parse_args(argv)
    try:
        models = _parse_csv(args.models) or None
        roles = _parse_roles(args.roles) or list(SUPPORTING_ROLES)
    except ValueError as e:
        print(f"halo gym: {e}", file=sys.stderr)
        return 2

    state_dir = bridge_home()
    target = ", ".join(models) if models else "every model in the default Ollama host's catalog"
    print(f"halo gym: running the battery against {target}{' (--quick)' if args.quick else ''}...")

    def _on_each(ref, result) -> None:
        print()
        print(format_card(result, show_replies=args.show_replies))
        tps_values = [result["tokens_per_second"]] if isinstance(result.get("tokens_per_second"), (int, float)) else []
        max_tps = max(tps_values) if tps_values else None
        for role in roles:
            score, _terms = composite_score(result, role, max_tps=max_tps)
            print(f"  as {role}: {score:.2f}" if score is not None else f"  as {role}: n/a")

    results = run_gym(models, quick=args.quick, state_dir=state_dir, on_each=_on_each)
    if not results:
        print("halo gym: no models to run -- pass --models, or configure an Ollama host "
              "(`ollama.hosts` in ~/.halo/config.json) with at least one model pulled", file=sys.stderr)
        return 1
    print(f"\nSaved under ~/.halo/gym/<host>/<digest>.json. `halo gym show` prints a card per model; "
          f"`halo gym propose` turns these scores into a role table.")
    return 0


def _cmd_show(argv: list) -> int:
    from halo_harness.config.paths import bridge_home
    from halo_harness.gym import find_results_for_model, format_card, iter_results

    parser = argparse.ArgumentParser(prog="halo gym show", add_help=True,
                                      description="Print the saved per-model gym card(s).")
    parser.add_argument("model", nargs="?", default=None, help="only this model's card (default: every "
                                                                "saved result, newest first)")
    parser.add_argument("--show-replies", action="store_true",
                         help="also print each reply-only task's saved reply excerpts")
    args = parser.parse_args(argv)
    from halo_harness import gym_handout
    state_dir = bridge_home()
    rows = find_results_for_model(state_dir, args.model) if args.model else iter_results(state_dir)
    cards = gym_handout.iter_cards(state_dir)  # 3.6.0.13 GM G6: `halo gym handout`'s cards, kept apart
    if args.model and cards:
        cards = find_results_for_model(state_dir, args.model, results=cards)
    if not rows and not cards:
        which = f" for {args.model!r}" if args.model else ""
        print(f"halo gym show: no saved gym results{which} -- run `halo gym` first.", file=sys.stderr)
        return 1
    for i, row in enumerate(rows):
        if i:
            print()
        print(format_card(row, show_replies=args.show_replies))
    if cards:
        if rows:
            print()
        print(gym_handout.HEAD)
        for card in cards:
            print(gym_handout.line(card))
    return 0


def _cmd_propose(argv: list) -> int:
    from halo_harness.config.paths import bridge_home
    from halo_harness.gym import iter_results
    from halo_harness.gym_propose import apply_proposal, propose_role_table

    parser = argparse.ArgumentParser(
        prog="halo gym propose", add_help=True,
        description="Turn saved `halo gym` scores into a role-table proposal (the best model per "
                    "supporting role, from the --candidates pool) -- one sentence per choice naming "
                    "the score behind it.")
    parser.add_argument("--apply", action="store_true",
                         help="write the proposal into your role table (roles.* in config.json; `halo config get "
                             "roles` shows it) and keep it as the role template --name")
    parser.add_argument("--name", default="gym-proposed", metavar="NAME",
                         help="template name for --apply (default: gym-proposed)")
    parser.add_argument("--roles", default=None, metavar="ROLE,ROLE,...",
                         help=f"propose only these roles (default: {', '.join(SUPPORTING_ROLES)})")
    parser.add_argument("--main", default=None, metavar="REF",
                         help="use REF, not the configured default model, as the VRAM-fit reference point "
                             "(main itself is never proposed either way)")
    # 2.0.6 round 11: rank cloud models too -- the gym already RUNS
    # against any reachable ref (`halo gym --model or:...`); the proposal
    # just refused to look at anything non-local until now.
    parser.add_argument("--candidates", choices=["local", "cloud", "all"], default="local",
                        help="which pool to rank: local (default, the old behavior), cloud (or:/dbx:/xp:/"
                             "endpoint refs only), or all (both together)")
    args = parser.parse_args(argv)
    try:
        roles = _parse_roles(args.roles) or None
    except ValueError as e:
        print(f"halo gym propose: {e}", file=sys.stderr)
        return 2

    state_dir = bridge_home()
    results = iter_results(state_dir)
    if not results:
        print("halo gym propose: no saved gym results yet -- run `halo gym` first.", file=sys.stderr)
        return 1
    roles_dict, sentences = propose_role_table(results, roles=roles, main_ref_raw=args.main,
                                                state_dir=state_dir, candidates=args.candidates)
    for s in sentences:
        print(s)
    if not roles_dict:
        print("halo gym propose: nothing to propose yet -- every candidate role came back with no usable "
              "score (see the sentences above).", file=sys.stderr)
        return 1
    if args.apply:
        ok, problems = apply_proposal(roles_dict, template_name=args.name)
        if not ok:
            print(f"halo gym propose --apply: {'; '.join(problems)}", file=sys.stderr)
            return 1
        # 3.6.0.0: `halo roles template load` is no command any more (only `roles point` is let through), so --apply
        # writes the table itself -- as that load did, without switching roles on (that is `halo maps use`'s choice)
        from halo_harness.roles import load_role_template, roles_mode_enabled
        from halo_harness.theme import set_config_value
        for role_name, value in ((load_role_template(args.name) or {}).get("roles") or roles_dict).items():
            set_config_value(f"roles.{role_name}", value)
        print(f"\nWritten into your role table and kept as role template {args.name!r}: `halo config get roles` "
              f"shows it; `halo roles point <role> <model>` changes one.")
        if not roles_mode_enabled():
            print("Roles are off (One model for everything): a session reads the table once a map is in use "
                  "(`halo maps use --off`).")
    return 0


def _trials(raw: str) -> int:
    try:
        n = int(raw)
    except ValueError:
        n = 0
    if n < 1:
        raise argparse.ArgumentTypeError(f"{raw!r} is not a whole number of 1 or more")
    return n


def _cmd_handout(argv: list) -> int:
    """3.6.0.13 GM G3: does main hand work out more with the helpers words ("now") than without them ("before")?
    The work is gym_handout.py's; this is argparse and printing."""
    from halo_harness import gym_handout
    from halo_harness.checks.run import is_local
    from halo_harness.config.paths import bridge_home

    parser = argparse.ArgumentParser(prog="halo gym handout", add_help=True,
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description="\n".join(gym_handout.facts()))
    parser.add_argument("model", nargs="+", help="a local model (ol:, hf:local/, hf:mlx/); any other ref is "
                                                 "refused and sends nothing")
    parser.add_argument("--trials", type=_trials, default=3, metavar="N",
                        help="trials per arm (default: 3)")
    args = parser.parse_args(argv)
    local = []
    for ref in args.model:
        if is_local(ref):
            local.append(ref)
        else:
            print(f"{ref}: the gym runs local models only.")
    if not local:
        return 1
    for fact in gym_handout.facts(args.trials):
        print(fact)
    sys.stdout.flush()
    state_dir = bridge_home()
    ran = 0
    for ref in local:
        card = gym_handout.run_model(ref, trials=args.trials, state_dir=state_dir)
        if card.get("same_words"):
            print(gym_handout.SAME_WORDS.format(model=card.get("model")))
            ran += 1
        elif not card.get("before") and not card.get("now"):  # no trial ran (the model or its host was not found):
            print(f"{ref}: not measured: {'; '.join(card.get('errors') or ['no trial ran'])}")  # the cause, no card
        else:
            gym_handout.save_card(state_dir, card)
            print(gym_handout.line(card))
            ran += 1
        sys.stdout.flush()
    return 0 if ran else 1


def cmd_gym(argv: list) -> int:
    if argv and argv[0] == "show":
        return _cmd_show(argv[1:])
    if argv and argv[0] == "propose":
        return _cmd_propose(argv[1:])
    if argv and argv[0] == "handout":
        return _cmd_handout(argv[1:])
    if argv and argv[0] in ("-h", "--help"):
        print("usage: halo gym [--models REF,REF,...] [--roles ROLE,...] [--quick]", file=sys.stderr)
        print("       halo gym show [model]", file=sys.stderr)
        print("       halo gym propose [--apply] [--name NAME] [--roles ROLE,...] [--main REF]", file=sys.stderr)
        print("       halo gym handout <model> [<model> ...] [--trials N]", file=sys.stderr)
        return 0
    return _cmd_run(argv)
