# Halo 2.0.7 fix pass, round 6: the nine red CI tests after review rounds 1-5

Repo: `<repo>` (branch master; start from HEAD = 1d3a46b, clean). Read
`plans/WORKER-RULES.md` FIRST and follow every rule in it (test environment:
`BRIDGE_TEST_HOME=<fresh scratch dir>`, `BRIDGE_TEST_NO_BACKGROUND_NET=1`,
`OLLAMA_HOST=http://127.0.0.1:1`). `plans/CYCLE.md` "Budget discipline"
applies. Read `plans/HANDOFF.md` section "WHERE THINGS STAND -- 2026-10-09
~01:30" for the standing contract of the review fix pass: deny rules hold
in every mode, auto mode with no rules stays allow, and the review's
classifier-shaped suggestions are rejected, never re-added.

The CI run on f2aaad4 (both platforms) fails 9 of 4169 tests. For each,
decide product bug versus stale pin by reading the review round that
touched the area (`tests/test_review2_round1..5.py` and their commits
c858334, 2a05160, 25a615a, f2aaad4), then fix at the source:

1. `test_h5c_f03_ineffective_compaction_backs_off_instead_of_retrying_every_other_step`:
   "step 1: backoff armed because the retained tail alone is still >= trigger".
2. `test_invariant_e_the_privacy_scan_passes` and
   `test_no_key_shaped_fragments_outside_the_allowlist` (the handoff calls
   the key-shaped-fragment check a known failure on clean HEAD: find the
   fragment the review rounds introduced, or fix the allowlist, never
   loosen the scan).
3. `test_invariant_c_path_home_outside_paths_py_is_a_reasoned_exception`:
   a new `Path.home()` outside `config/paths.py`; route it through paths.py
   or give it the reasoned-exception comment the invariant accepts.
4. `test_the_read_only_whitelist_table`: `find . -name x -maxdepth 2` no
   longer classified read-only (review finding 5 changed the whitelist;
   restore the read-only classification for find without -exec/-delete).
5. `test_github_release_falls_back_to_curl_with_a_credential_token_when_gh_is_absent`:
   "the token rides in the Authorization header, got None" (review
   finding 17 moved the token off the command line; the test must assert
   the new, safe transport, and the transport must still carry the token).
6. `test_cli_exit_codes_and_json`: "a clean lineup exits 0, got 1" with
   "RESULT: 2 problem(s); the roles lineup needs attention" (doctor --roles
   on the fixture lineup now reports problems: find which review change
   made the fixture invalid, fix the checker or the fixture, whichever is
   wrong).
7. `test_resolve_role_ref_session_model_when_nothing_set`: source label
   "session model" vs "session model (inherit)" (decide the one label,
   update the other side).
8. `test_v2a_anthropic_gateway_404_error_surfaces`: "status 404, got 400"
   (review finding 40 non-JSON 200 handling or the 404 path; the real
   status must surface).

Verification: the eight test modules involved, `python tests/run_all.py`
once, `python test_bridge.py`, `python test_tui.py` once, `python
tests/test_invariants.py`, `python tests/test_privacy_scan.py`, `python -m
halo_harness audit privacy`, all green. Hard constraints as in every brief:
no safety or refusal language, no real paths or names, no network in
tests, no loosened invariant. Hand back RESULT LINES (one per failure:
product bug or stale pin, the fix), FILES TOUCHED, WHAT YOU FOUND. No
commit, no push.
