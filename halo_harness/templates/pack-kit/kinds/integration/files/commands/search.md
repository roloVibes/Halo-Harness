---
description: Search the project for a word or a pattern with ripgrep (rg), through the pack's rg MCP server
argument-hint: "<pattern> [folder]"
---
Search the project for $ARGUMENTS with the `search` tool of the pack's `rg` MCP server (it runs ripgrep; the pack's
README says how to install it). List each match as `file:line: text`, at most 30, then say how many there were. When
the tool says rg is not installed, say so with the install line it gives and stop.
