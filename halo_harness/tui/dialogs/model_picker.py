"""halo_harness.tui.dialogs.model_picker -- `/model` with no argument (D-TUI:
"ModelPicker (filter + ref/context/price)"). `models` is whatever
`Controller.list_models()` returned: `[{ref, context_tokens,
max_output_tokens, price_in_per_m, price_out_per_m, provider}, ...]`.
Dismisses with the chosen `ref` string, or `None` if cancelled.

1.0.1 hotfix addendum 7/8: the filter `Input` is a `NavInput` (Up/Down/
PageUp/PageDown/Home/End move the `OptionList` highlight, Enter selects it --
see `tui/dialogs/listnav.py`'s own docstring for why Textual's plain `Input`
needed this at all), and rows are grouped by `Controller.list_models()`'s own
`group` tag with one header per group instead of an inline `[group]` suffix,
each row rendered as a single ellipsized line (never wrapped, which used to
break the column alignment on a long ref/path).

1.0.1 hotfix 12: every row -- OpenRouter, cc:, Databricks alike -- now shows
context/output/price columns through the ONE shared `model_display.
format_model_row` (never a per-provider "show path=/dbu= INSTEAD of prices"
special case); a Databricks row's family/path still shows, as a bracketed
`detail` tag after the price columns instead of replacing them.
"""

from __future__ import annotations

import difflib

from rich.text import Text
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

from halo_harness.model_display import PICKER_COLUMN_HEADER, PICKER_FOOTER, format_picker_row
from halo_harness.tui.dialogs.listnav import NavInput

# Halo 2.0.4 round 3 (deliverable 1): "s cycles the sort key (name, price,
# ctx, speed)" (2.0.3-brief A2) -- "name" is this dialog's existing
# first-seen/alphabetical-within-group order (the default, index 0);
# cycling never changes GROUPING, only each group's own row order.
_SORT_KEYS = ("name", "price", "context", "speed")


def _sort_value(model: dict, key: str):
    """A sortable value for `key` -- ascending price/context/speed (so
    the cheapest/smallest/slowest comes first, matching how a reader
    scans a price or size list), `None`s pushed to the END regardless of
    sort direction (an unknown figure is never mistaken for the cheapest/
    smallest/fastest just because `None < anything` in Python)."""
    if key == "price":
        v = model.get("price_in_per_m")
    elif key == "context":
        v = model.get("context_tokens")
    elif key == "speed":
        v = model.get("speed_tokens_per_second")
    else:
        return (0, (model.get("ref") or "").lower())
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        return (1, 0.0)
    return (0, v)


def _gym_score_suffix(model_ref: str) -> str:
    """Best-effort, synchronous (`gym.picker_score_suffix` only ever reads
    local `~/.halo/gym/*/*.json` files, never the network) -- "" on any
    failure so a corrupt/unreadable gym result can never break the picker."""
    try:
        from halo_harness.gym import picker_score_suffix
        return picker_score_suffix(model_ref)
    except Exception:
        return ""


def _place_free_variants_beside_base(members: "list[dict]") -> "list[dict]":
    """Halo 2.0.4 round 5 ("new labs coverage" deliverable 2): "`:free`
    variants sort beside their paid row" -- REGARDLESS of the active sort
    key. Plain alphabetical "name" order already keeps `<ref>` immediately
    before `<ref>:free` in the common case (a prefix always sorts before
    any string it's a prefix of), but a `price`/`context`/`speed` re-sort
    scatters them: a free row's own $0/unknown figure usually sorts it
    BEFORE its paid sibling (price ascending puts $0 first), not after, so
    a naive "pull the free row forward to follow its base" pass (tried
    first, and wrong -- see the git history on this function) misses that
    direction entirely whenever the free row is already encountered first.

    This pass instead DEFERS a `:free` row the moment its own base ref is
    known to exist somewhere in this same group but hasn't been placed
    yet, and emits the deferred row immediately once that base IS placed
    -- so the pair always lands together at the base's own sort position,
    whichever of the two the sort happened to put first. A `:free` row
    with NO paid sibling in this group at all (a free-only model, or one
    whose base got filtered out) is never deferred -- it has nothing to
    wait for, so it keeps its original position exactly as before this
    pass. Every other row's relative order is untouched either way."""
    by_ref = {m.get("ref"): m for m in members if isinstance(m, dict)}
    placed: "set[str]" = set()
    out: "list[dict]" = []
    for m in members:
        ref = m.get("ref") or ""
        if ref in placed:
            continue
        if ref.endswith(":free"):
            base_ref = ref[: -len(":free")]
            if base_ref in by_ref and base_ref not in placed:
                continue  # the base's own turn below will emit this row right after it
            out.append(m)
            placed.add(ref)
            continue
        out.append(m)
        placed.add(ref)
        free_ref = f"{ref}:free"
        sibling = by_ref.get(free_ref)
        if sibling is not None and free_ref not in placed:
            out.append(sibling)
            placed.add(free_ref)
    return out


def _grouped(models: "list[dict]") -> "list[tuple[str, list[dict]]]":
    """Stable-groups `models` by their own `group` tag (ungrouped rows --
    OpenRouter, aliases, the synthesized current-model row -- share one
    untitled, header-less bucket) -- preserves each group's FIRST-SEEN
    order rather than assuming same-group rows already sit contiguously in
    the incoming list (`Controller.list_models()`'s own Databricks section
    is endpoint-NAME-sorted, which does not always keep one family
    together)."""
    order: "list[str]" = []
    buckets: "dict[str, list[dict]]" = {}
    for m in models:
        key = m.get("group") or ""
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(m)
    return [(key, buckets[key]) for key in order]


def autocomplete_suggestions(models: "list[dict]", query: str, *, limit: int = 6) -> "list[str]":
    """Halo 2.0.4 round 4 (deliverable 2/3): the "pick list plus
    autocomplete" every free-text ref field (the org editor's "Role or
    model" input; any future one) narrows against, as `query` is typed --
    `models` is the SAME merged, enumerated list `ModelPicker` itself
    renders (the brief's own "do not duplicate the picker's data
    source"), so a suggestion shown here is guaranteed pickable.

    Prefix matches sort first (closest to what a person typing expects),
    then every OTHER substring match, both case-insensitive; an empty
    `query` suggests nothing (there is nothing to narrow yet -- the full
    list is what the pick-list/picker screen itself is for). A query that
    matches nothing in the catalog falls back to `difflib.get_close_
    matches` (a near-miss typo, e.g. "sonet" -> "sonnet") -- still ADVISORY
    only, never a restriction: typing a ref that matches neither still
    works elsewhere in this same editor, with a one-line note instead of
    a refusal.

    This is a NEW, additive function -- `ModelPicker._refresh_list`'s own
    filter (bare substring, no prefix-first ordering, a different "no
    match" fuzzy fallback shape) is deliberately left untouched rather
    than rebuilt on top of this one, so this function's existence never
    risks changing that already-tested dialog's own behavior."""
    query_low = (query or "").strip().lower()
    refs = [m.get("ref") for m in models if isinstance(m, dict) and m.get("ref")]
    if not query_low:
        return []
    prefix = [r for r in refs if r.lower().startswith(query_low)]
    other = [r for r in refs if query_low in r.lower() and r not in prefix]
    ordered = prefix + other
    if ordered:
        return ordered[:limit]
    near = difflib.get_close_matches(query_low, [r.lower() for r in refs], n=limit, cutoff=0.4)
    low_to_orig = {r.lower(): r for r in refs}
    out = []
    for n in near:
        orig = low_to_orig.get(n)
        if orig and orig not in out:
            out.append(orig)
    return out


class ModelPicker(ModalScreen):
    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        # Halo 2.0.3 round 3 (brief item 5): set a role for the
        # HIGHLIGHTED model without editing JSON/leaving this dialog.
        # C-2 finding 12: `priority=True` -- focus starts on the filter
        # `NavInput` (`on_mount` below), which otherwise consumes a plain
        # "u" keystroke as TEXT before this binding ever sees it (unlike
        # Escape, never typeable into an Input to begin with, which is why
        # `cancel` above already worked regardless of focus with no flag
        # of its own). A priority binding only intercepts the ONE key it
        # names -- every other letter still reaches the filter and types
        # normally.
        # Round 3 follow-up (orchestrator, 2026-10-05): the action keys are
        # control combinations, never bare letters (and not Ctrl+U/Ctrl+R, which the input and
        # the app already use) -- a bare letter forwarded
        # from the filter can no longer be TYPED into it ("sonnet", "mistral",
        # "unsloth"), which is a worse cost than a chord.
        Binding("ctrl+o", "set_role", "Set role", show=True, priority=True),
        # Halo 2.0.4 round 3 (deliverable 1/G4): "s cycles the sort key" /
        # "r refreshes the current group and R all groups" -- same
        # priority-binding-plus-extra_keys-forwarding shape `u` already
        # uses (see `on_mount`'s `NavInput(extra_keys=...)` and that
        # widget's own docstring for why a plain Binding alone can never
        # reach a dialog while the filter Input holds focus, which it
        # always does under normal use here). WHAT YOU FOUND (hand-back):
        # the SAME tradeoff `u` already accepted now also applies to these
        # three letters -- "s"/"r" can no longer be TYPED into the filter
        # box at all (not even inside a longer word like "sonnet"/
        # "mistral"), a materially bigger cost than `u`'s own (rarer in
        # real model/vendor names) since both are common letters; flagged
        # for the orchestrator/owner to weigh, not silently decided here.
        Binding("ctrl+s", "cycle_sort", "Sort", show=True, priority=True),
        Binding("ctrl+g", "refresh_group", "Refresh group", show=True, priority=True),
        Binding("f5", "refresh_all", "Refresh all", show=True, priority=True),
    ]
    DEFAULT_CSS = """
    ModelPicker { align: center middle; }
    ModelPicker > Vertical { width: 90%; height: 80%; border: round $primary; background: $surface; padding: 1 2; }
    ModelPicker Input { margin-bottom: 1; }
    ModelPicker OptionList { height: 1fr; }
    """

    def __init__(self, models: "list", *, current: str = "", last_used: str = "") -> None:
        super().__init__()
        # `Controller.list_models()` returns dicts; `FakeController`'s own
        # (tests/test_fake_controller.py-pinned) shape is a bare list of ref
        # strings -- normalize both to the dict shape this dialog renders.
        # H15 item 21.2: a `{"hint": "..."}` entry (no "ref" at all -- a
        # detected-but-disabled provider's dim notice) is split out here so
        # it never reaches the filterable/selectable `self.models` list.
        self.hints = [m.get("hint", "") for m in models if isinstance(m, dict) and "hint" in m]
        self.models = [m if isinstance(m, dict) else {"ref": m, "provider": "?"}
                       for m in models if not (isinstance(m, dict) and "hint" in m)]
        self.current = current
        # 2.0.1 W3a ("launch with the last session's model and effort"):
        # the ref `launch_state.resolve_last_model` would pick on the NEXT
        # launch -- "" (the default) marks no row at all, same as today.
        self.last_used = last_used
        self._filtered = self.models
        # Halo 2.0.4 round 3 (deliverable 1): the sort cycle's current
        # position -- index into `_SORT_KEYS`, "name" (today's existing
        # first-seen/alphabetical order) first so a picker opened fresh
        # never looks different from before this round.
        self._sort_index = 0

    def compose(self):
        with Vertical():
            yield Static(f"Select a model (current: {self.current or '?'})", classes="dialog-title")
            yield Static(PICKER_FOOTER, classes="dialog-subtitle")
            yield Static(PICKER_COLUMN_HEADER, classes="dialog-subtitle")
            # C-2 finding 12: `extra_keys={"u": "set_role", ...}` -- the
            # ONLY way these screen-level letter-key shortcuts can fire
            # while the filter keeps focus by default (see NavInput's own
            # docstring on why a plain `Binding(priority=True)` alone
            # never reaches it here).
            yield NavInput(placeholder="Filter models...", id="model-filter", option_list_id="model-list",
                           extra_keys={"ctrl+o": "set_role", "ctrl+s": "cycle_sort",
                                       "ctrl+g": "refresh_group", "f5": "refresh_all"})
            yield OptionList(id="model-list")
            yield Static("", id="model-hint")

    def on_mount(self) -> None:
        self._refresh_list("")
        self.query_one("#model-filter", Input).focus()

    def _refresh_list(self, query: str) -> None:
        query_low = query.strip().lower()
        if query_low:
            self._filtered = [m for m in self.models if query_low in m["ref"].lower()]
        else:
            self._filtered = self.models
        option_list = self.query_one("#model-list", OptionList)
        option_list.clear_options()
        hint = self.query_one("#model-hint", Static)
        if self._filtered:
            sort_key = _SORT_KEYS[self._sort_index]
            for group, members in _grouped(self._filtered):
                if group:
                    option_list.add_option(Option(Text(f"── {group} ──", style="bold dim"),
                                                   disabled=True))
                # Halo 2.0.4 round 3 (deliverable 1): "s cycles the sort
                # key" -- sorts WITHIN each group only (never re-groups);
                # `sorted` is stable, so "name" (ascending ref, case-
                # insensitive) ties break the same way every other sort
                # key's own ties do -- by whatever order the members
                # already arrived in (Controller.list_models()'s own,
                # already-deterministic per-provider order).
                if sort_key != "name":
                    members = sorted(members, key=lambda m: _sort_value(m, sort_key))
                # Halo 2.0.4 round 5: re-glue a `:free` row beside its paid
                # sibling AFTER the sort above (which is what scatters them
                # under price/context/speed) -- a no-op shuffle under "name"
                # order, where they're already adjacent in the normal case.
                members = _place_free_variants_beside_base(members)
                for m in members:
                    row_text = Text(format_picker_row(m), no_wrap=True, overflow="ellipsis")
                    # Halo 2.0.3 round 5d (brief item 2): "the picker shows
                    # the gym score beside a model when one exists" -- a
                    # local-file-only lookup (gym.picker_score_suffix),
                    # never a network call, so it is safe right here in
                    # the synchronous row-building loop.
                    gym_suffix = _gym_score_suffix(m["ref"])
                    if gym_suffix:
                        row_text.append(gym_suffix, style="dim")
                    if self.last_used and m["ref"] == self.last_used:
                        row_text.append("  (last used)", style="dim italic")
                    option_list.add_option(Option(row_text, id=m["ref"]))
            # 1.0.1 hotfix addendum 7: highlights the first SELECTABLE row
            # up front (`action_first` skips a disabled group-header, unlike
            # a bare `.highlighted = 0`) -- otherwise `highlighted` starts
            # at None and "Down twice" only reaches the SECOND row, not the
            # third, contradicting the documented "Down, Down, Enter -> the
            # third entry" behavior.
            option_list.action_first()
            hint.update(self._hint_text())
        else:
            refs = [m["ref"] for m in self.models]
            near = difflib.get_close_matches(query, refs, n=5, cutoff=0.4)
            no_match = f"No exact match. Did you mean: {', '.join(near)}" if near else "No matching models."
            extra = self._hint_text()
            hint.update(f"{no_match}\n{extra}" if extra else no_match)

    def _hint_text(self) -> str:
        """H15 item 21.2: one dim line per detected-but-disabled provider,
        always shown (filter or not) -- never counted as a selectable row."""
        return "\n".join(f"  {h}" for h in self.hints) if self.hints else ""

    def on_input_changed(self, event: Input.Changed) -> None:
        self._refresh_list(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if self._filtered:
            self.dismiss(self._filtered[0]["ref"])
        else:
            self.dismiss(event.value.strip() or None)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(str(event.option_id))

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_set_role(self) -> None:
        """Halo 2.0.3 round 3 (brief item 5): `u` on the highlighted row
        opens `RoleAssignPicker` for that model's own ref -- never
        dismisses THIS dialog (the user may want to assign several roles
        in one browse); `RoleAssignPicker` itself writes `roles.<name>`
        via `roles.assign_role` (the SAME config-table mechanism `/roles`
        already reads, no second one) and reports the result in
        `#model-hint`."""
        # C-2 finding 12: `highlighted` is an index into the OptionList
        # itself, which also holds disabled group-header rows `_grouped`
        # interleaves -- indexing `self._filtered` (headers-free) with it
        # directly picked a different model than the one actually
        # highlighted the moment any group header sat above it. The
        # option's own `.id` (set to `m["ref"]` when it was added, never
        # set at all on a header) is the one reliable source.
        option_list = self.query_one("#model-list", OptionList)
        highlighted = option_list.highlighted
        if highlighted is None:
            return
        ref = option_list.get_option_at_index(highlighted).id
        if ref is None:
            return  # a disabled group-header row -- nothing to act on.
        self.app.push_screen(RoleAssignPicker(ref, main_ref=self.current),
                              lambda role_name: self._role_assigned(ref, role_name))

    def _role_assigned(self, ref: str, role_name) -> None:
        hint = self.query_one("#model-hint", Static)
        if not role_name:
            hint.update("")
            return
        hint.update(f"Set role {role_name!r} to {ref!r}.")
        if role_name == "orchestrator" and ref.startswith("ol:"):
            # brief: "choosing a non-session-capable local model as main
            # prints the plain consequence sentence and proceeds" -- the
            # assignment above ALREADY happened (proceeds immediately);
            # the catalog read behind the consequence sentence is a real
            # network call, so it runs off the UI thread and the hint is
            # amended a moment later rather than ever blocking this dialog.
            self.app.run_worker(lambda: self._consequence_worker(ref), thread=True,
                                 name="role-consequence", group="role-consequence")

    def _consequence_worker(self, ref: str) -> None:
        from halo_harness.roles import main_role_consequence_note
        note = main_role_consequence_note(ref, catalog_capabilities=_catalog_capabilities_for(ref))
        if note:
            self.app.call_from_thread(self._append_hint, note)

    def _append_hint(self, note: str) -> None:
        hint = self.query_one("#model-hint", Static)
        current = hint.renderable
        hint.update(f"{current}\n{note}" if current else note)

    def action_cycle_sort(self) -> None:
        """Halo 2.0.4 round 3 (deliverable 1): "`s` cycles the sort key
        (name, price, ctx, speed)" -- re-renders in place (the highlighted
        ref, if it's still visible after re-sorting, is not specifically
        preserved; `_refresh_list` always re-highlights the first
        selectable row, same as a filter keystroke already does)."""
        self._sort_index = (self._sort_index + 1) % len(_SORT_KEYS)
        self._refresh_list(self.query_one("#model-filter", Input).value)
        hint = self.query_one("#model-hint", Static)
        hint.update(f"Sorted by {_SORT_KEYS[self._sort_index]}.")

    def _highlighted_ref_and_provider(self):
        """`(ref, provider)` for the currently-highlighted SELECTABLE row,
        `(None, None)` on a disabled group-header row or nothing
        highlighted -- the same `.id`-not-index lookup `action_set_role`
        already uses (see its own comment for why indexing `_filtered`
        directly is wrong once a group header sits above the real row)."""
        option_list = self.query_one("#model-list", OptionList)
        highlighted = option_list.highlighted
        if highlighted is None:
            return None, None
        ref = option_list.get_option_at_index(highlighted).id
        if ref is None:
            return None, None
        provider = next((m.get("provider") for m in self._filtered if m.get("ref") == ref), None)
        return ref, provider

    def action_refresh_group(self) -> None:
        """Halo 2.0.4 round 3 (deliverable 1/G4): "`r` refreshes the
        current group" -- the ENABLED provider the highlighted row
        belongs to, off the UI thread; a group with no live catalog of
        its own (cc:/cx:/ol:/local/alias rows) gets a plain one-line
        explanation instead of silently doing nothing."""
        _ref, provider = self._highlighted_ref_and_provider()
        if provider is None:
            return
        hint = self.query_one("#model-hint", Static)
        hint.update("Refreshing this group…")
        self.app.run_worker(lambda: self._refresh_worker(providers=[provider]), thread=True,
                             name="picker-refresh-group", group="picker-refresh")

    def action_refresh_all(self) -> None:
        """"R" refreshes every group that has a live catalog of its own
        (the same set `providers.catalog_refresh` registers), off the UI
        thread."""
        hint = self.query_one("#model-hint", Static)
        hint.update("Refreshing all groups…")
        self.app.run_worker(lambda: self._refresh_worker(providers=None), thread=True,
                             name="picker-refresh-all", group="picker-refresh")

    def _refresh_worker(self, *, providers) -> None:
        """`providers`: a one-item list (the `r` case) or `None` (the `R`
        case, every registered catalog). Never touches the UI directly --
        everything after the network call runs back on the UI thread via
        `call_from_thread`, same convention `_consequence_worker`/
        `_vram_reason_worker` already use in this module."""
        try:
            state_dir = getattr(self.app.controller, "state_dir", None)
            settings = getattr(self.app.controller, "settings", None)
            env = settings.effective_env if settings is not None else None
            if state_dir is None:
                return
            if providers is None:
                from halo_harness.providers.catalog_refresh import refresh_all_enabled_catalogs
                results = refresh_all_enabled_catalogs(state_dir, env=env, force=True)
            else:
                from halo_harness.providers.catalog_refresh import refresh_one_catalog
                results = [r for r in (refresh_one_catalog(p, state_dir, env=env, force=True) for p in providers)
                           if r is not None]
            ok_names = [r["name"] for r in results if r.get("attempted") and r.get("ok")]
            failed_names = [r["name"] for r in results if r.get("attempted") and r.get("ok") is False]
            if not results:
                message = "Nothing to refresh for this group (no live catalog of its own)."
            else:
                parts = []
                if ok_names:
                    parts.append(f"refreshed: {', '.join(ok_names)}")
                if failed_names:
                    parts.append(f"failed, using the previous cache: {', '.join(failed_names)}")
                message = "; ".join(parts) or "Already up to date."
        except Exception as e:
            message = f"Refresh failed: {type(e).__name__}: {e}"
        self.app.call_from_thread(self._apply_refreshed_models, message)

    def _apply_refreshed_models(self, message: str) -> None:
        """Re-pulls `Controller.list_models()` (a pure, synchronous,
        already-cheap read -- see that method's own docstring) so a
        row that just got a real catalog for the first time appears
        immediately, without closing and reopening this dialog."""
        hint = self.query_one("#model-hint", Static)
        try:
            fresh = self.app.controller.list_models()
        except Exception:
            hint.update(message)
            return
        self.hints = [m.get("hint", "") for m in fresh if isinstance(m, dict) and "hint" in m]
        self.models = [m if isinstance(m, dict) else {"ref": m, "provider": "?"}
                       for m in fresh if not (isinstance(m, dict) and "hint" in m)]
        self._refresh_list(self.query_one("#model-filter", Input).value)
        hint.update(message)


def _catalog_capabilities_for(model_ref: str):
    """Best-effort, OFF the UI thread (see `ModelPicker._consequence_
    worker`, the only caller): a dim/offline host, or a model not yet in
    the catalog, must never turn `u` into a hang or a traceback -- see
    `roles.main_role_consequence_note`'s own "benefit of the doubt" note
    for what `None` here means to that function."""
    if not model_ref.startswith("ol:"):
        return None
    try:
        from halo_harness.model import parse_model_ref
        from halo_harness.providers.ollama import get_catalog, ollama_names_match, resolve_ollama_host
        ref = parse_model_ref(model_ref)
        host = resolve_ollama_host(ref.host)
        if host is None:
            return None
        # Review fix pass (finding 9): matched via `ollama_names_match`,
        # not a bare `==` -- an untagged ref must still find its own
        # `:latest`-qualified catalog row, same as every other Ollama
        # name comparison in this codebase.
        for row in get_catalog(host).get("models") or []:
            if isinstance(row, dict) and (ollama_names_match(row.get("model"), ref.model)
                                           or ollama_names_match(row.get("name"), ref.model)):
                return row.get("capabilities")
    except Exception:
        pass
    return None


class RoleAssignPicker(ModalScreen):
    """Halo 2.0.3 round 3 (brief item 5): `u` on `ModelPicker`'s
    highlighted row -- a short list of `roles.known_role_names()`,
    pre-selecting `roles.default_role_for_ref(model_ref)` (`small` for
    an `ol:` ref, never main by default). Enter writes `roles.<chosen>`
    to `model_ref` (`roles.assign_role` -- cheap, a local config write,
    safe to do right here on the UI thread) and dismisses with the
    chosen role name; Escape dismisses with `None` (no write). The
    brief's own "choosing a non-session-capable local model as main
    prints the plain consequence sentence and proceeds" is `ModelPicker`'s
    job, not this dialog's -- that sentence needs a real catalog read,
    which never belongs on this (or any) Textual event handler; see
    `ModelPicker._role_assigned`/`_consequence_worker`."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]
    DEFAULT_CSS = """
    RoleAssignPicker { align: center middle; }
    RoleAssignPicker > Vertical { width: 50%; height: 60%; border: round $primary; background: $surface; padding: 1 2; }
    RoleAssignPicker OptionList { height: 1fr; }
    """

    def __init__(self, model_ref: str, *, main_ref: str = "") -> None:
        super().__init__()
        self.model_ref = model_ref
        # Round 5b part 2 (brief item 3): the session's CURRENT model --
        # needed only for the "(same as main: fits beside it: no)" caption
        # below; `""` (a caller that omits it, or no session is running
        # yet) just means the caption never has anything to show.
        self.main_ref = main_ref

    def compose(self):
        with Vertical():
            yield Static(f"Set a role for {self.model_ref}", classes="dialog-title")
            yield Static("Enter: set  |  Esc: cancel", classes="dialog-subtitle")
            yield OptionList(id="role-assign-list")

    def on_mount(self) -> None:
        from halo_harness.roles import default_role_for_ref, known_role_names
        option_list = self.query_one("#role-assign-list", OptionList)
        default = default_role_for_ref(self.model_ref)
        names = known_role_names()
        for name in names:
            option_list.add_option(Option(f"{name}{'  (default)' if name == default else ''}", id=name))
        if default in names:
            option_list.highlighted = names.index(default)
        option_list.focus()
        from halo_harness.roles import VRAM_AWARE_ROLE_NAMES
        if self.main_ref and self.main_ref != self.model_ref and default in VRAM_AWARE_ROLE_NAMES:
            # Round 5b part 2: a real GPU-memory/`/api/ps` read, off the UI
            # thread (the SAME `run_worker(thread=True)` pattern every
            # other live probe in this codebase uses) and short -- the
            # dialog is already fully usable before this resolves; the
            # caption just appears a moment later, or never if the probe
            # never finishes before the screen closes (`query_one`'s own
            # `except Exception: pass` below degrades silently).
            self.run_worker(self._vram_reason_worker, thread=True, name="role-assign-vram-reason")

    def _vram_reason_worker(self) -> None:
        from halo_harness.model import parse_model_ref
        from halo_harness.roles import default_role_for_ref, vram_aware_override
        try:
            default = default_role_for_ref(self.model_ref)
            main = parse_model_ref(self.main_ref)
            _value, reason = vram_aware_override(default, self.model_ref, main_ref=main)
        except Exception:
            reason = None
        if reason:
            self.app.call_from_thread(self._apply_vram_reason, default, reason)

    def _apply_vram_reason(self, role_name: str, reason: str) -> None:
        try:
            option_list = self.query_one("#role-assign-list", OptionList)
            option_list.replace_option_prompt(role_name, f"{role_name}  (default)  {reason}")
        except Exception:
            pass

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """`roles.assign_role` is a local config write (no network) --
        safe to call right here; dismisses with the plain role-name
        string either way (a write failure is vanishingly rare -- a
        syntactically bad role name can't reach this list at all, since
        every option id comes from `known_role_names()` -- so this
        never needs its own error-reporting shape)."""
        role_name = str(event.option_id)
        from halo_harness.roles import assign_role
        assign_role(role_name, self.model_ref)
        self.dismiss(role_name)

    def action_cancel(self) -> None:
        self.dismiss(None)
