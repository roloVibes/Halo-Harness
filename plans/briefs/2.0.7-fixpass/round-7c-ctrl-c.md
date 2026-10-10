# Halo 2.0.7 fix pass, round 7c: Ctrl+C copies; a second press asks before quitting; PowerShell never kills the session

Owner's report (rolo, 2026-10-09 ~23:45): "When I press Ctrl+C once in a
Halo session in PowerShell, it closes. I need Ctrl+C for copying. The first
Ctrl+C should copy; if a user does that twice they probably want to quit,
and a popup should show confirming they want to quit Halo."

Repo: `<repo>` (branch master; start from HEAD after round 7b, clean). Read
`plans/WORKER-RULES.md` FIRST (test environment as always). `plans/CYCLE.md`
"Budget discipline" applies.

## What exists

`halo_harness/tui/app.py` binds `ctrl+c` to `interrupt_or_quit` with a
`DOUBLE_CTRL_C_WINDOW_S` window (`tui/keys.py`) and the config switch
`quit_on_double_ctrl_c` (default true): first press interrupts a running
turn or notifies, second press within the window quits. The 2.0.7 copy-out
work (`clipboard.osc52_trusted()`, `copy_to_clipboard`, the selected-range
copy, the mechanism confirmation) is the copy path to reuse. On a Windows
console (PowerShell 5.1 under conhost, and Windows Terminal), Ctrl+C can be
delivered as a console control event that terminates the process before
Textual sees a key, which is the single-press close the owner hit.

## Deliverables

1. **The console never kills the session.** On Windows, for the TUI's
   lifetime, Ctrl+C reaches Halo only as a key: clear
   `ENABLE_PROCESSED_INPUT` on the console input handle (restore the mode
   on exit, including on crash via the existing exit path) and install a
   control handler that ignores `CTRL_C_EVENT` while the TUI runs; on POSIX
   keep the SIGINT behaviour Textual already gives the app. Verify by hand
   on PowerShell 5.1 in conhost and in Windows Terminal (describe the
   check); pin the mode helper with a unit test against a fake kernel32.
   Print mode (`-p`) keeps SIGINT = exit 130 unchanged (there is a pinned
   test for it).
2. **First Ctrl+C copies.** If a selection exists (transcript selected
   range, a TextArea or Input selection) copy it; otherwise copy the last
   assistant reply; toast "Copied <n> characters" or "Nothing to copy".
   Ctrl+C never interrupts a running turn (Esc keeps that job; the toast
   says so when a turn is running and nothing was selected). The copy uses
   the existing mechanism (OSC 52 when trusted, else the platform command:
   `clip.exe` on Windows, `pbcopy` / `xclip` / `wl-copy` elsewhere), with
   the existing mechanism confirmation.
3. **Second Ctrl+C asks.** A second press within `DOUBLE_CTRL_C_WINDOW_S`
   (raise it to 3 s) opens a confirmation card "Quit Halo? Enter quits,
   Esc stays" and never quits by itself; Enter runs the existing quit
   path; Esc dismisses and the window resets. With
   `quit_on_double_ctrl_c: false` the second press just copies again.
   Ctrl+D on an empty input, Ctrl+Q and `/exit` are unchanged.
4. **Docs**: HANDBOOK keys section and the `/help` key table, CONFIG.md for
   the switch, CHANGELOG `[unreleased]` "### Ctrl+C copies; quitting asks".

## Tests (hermetic, Textual pilots)

Ctrl+C with a transcript selection copies it (the fake clipboard sink
receives it, toast shown); without a selection copies the last reply;
with an empty transcript shows "Nothing to copy"; two presses within the
window open the card, Enter quits, Esc stays and a later press copies
again; a press outside the window copies; a running turn is not
interrupted; the switch off disables the card; the Windows console-mode
helper sets and restores the flags on a fake kernel32 and is a no-op on
POSIX; the print-mode SIGINT pin still passes.

## Hard constraints

No safety or refusal language; no real paths or names; no new dependency;
chords or function keys only in screens with text input; never block the
UI thread.

## Verification before hand-back

Touched and new modules, `python test_bridge.py`, `python test_tui.py`
once, `python tests/test_invariants.py`, `python tests/test_privacy_scan.py`,
`python tests/test_docs_slash_commands.py`, `python -m halo_harness audit
privacy`, all green. Hand back RESULT LINES (1-4), FILES TOUCHED, WHAT YOU
FOUND (the exact Windows mechanism that killed the session, and the manual
check for the owner). No commit, no push.
