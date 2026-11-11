# Commands: what changed

Read this when you want to know what a Halo version changed on a box with no repo (`halo whatsnew`).

Part of [Commands](COMMANDS.md), which lists every part.

## `halo whatsnew`

Halo 3.3.16.2. What a version changed, on a box with no repo: the package
ships the newest twelve dated entries of CHANGELOG.md
(`halo_harness/data/changelog.md`, written by `scripts/release.py` when it
dates a release). The TUI's `/whatsnew` prints the same text.

```sh
halo whatsnew                    # the installed version: its two-sentence summary, each ### heading and its first line
halo whatsnew 3.3.15.0           # another version's entry, the same way
halo whatsnew --full             # the whole entry
halo whatsnew --since 3.3.15.0   # every entry after that one, newest first (with --full: whole)
halo whatsnew --summary          # the summary alone (what halo update prints after it installs)
```

A version the shipped copy does not hold exits 1 and names the ones it does;
an install whose version has no dated entry yet (a build between releases)
shows the newest shipped one and says so. Exit 0 shown, 1 not there, 2 usage.
