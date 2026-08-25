# Action

Configuration, the startup line, and the plumbing that #34 should already give. End the cycle
with a deliberate transcript regeneration.

## Configuration

`config.Settings` gains the three from `Limits` - result count, fetch time limit, page
characters kept - each with a default, an environment variable and a flag, resolved in the
same precedence as everything else (AC 28). Then hand them into the `Limits` that `main()`
already builds.

Then a **web switch separate from `--no-tools`** (AC 29). Switching off the web must leave
`read_file` and `run_command` working; switching off tools must switch off the web too.
Decide how that composes and say so in the log - the two flags interact, and a user who
passes both should get something obvious rather than something clever.

## The startup line

AC 1 wants web availability shown; AC 29 wants the off state shown. The line already carries
a tool count, and `7 tools` says nothing about whether the web is reachable.

Three web states - available, switched off, and unavailable because tools are off entirely -
against the three tool states already there. **Do not let this become a matrix of nine
sentences.** Find the reading that stays one short line and says the true thing.

## Then the plumbing, by verification rather than construction

These should already work. Confirm each against these tools, and if one does not, that is the
finding:

- **AC 13, 14** - `note_tool` shows the query before a search and the address before a fetch.
- **AC 15** - `show_tool_result` marks fetched content.
- **AC 24** - Ctrl-C during a fetch. `run_command` needed explicit killing because it held a
  subprocess; httpx holds a socket. Check whether an interrupt leaves anything behind, and
  test the world rather than the message.
- **AC 25, 26** - results and pages enter history, and survive compaction with their
  addresses. #34 cycle 6 made compaction render call arguments, so the address should
  survive - **test that specifically**, since AC 26 names it.
- **AC 30** - exits, re-verified with the web tools registered.

## AC 23: no network at all

Not the same as an unreachable host. Force it - point the process at a network that cannot
resolve, or patch at the transport layer - and confirm both tools fail with a plain
explanation **and that chat still works for anything not needing the web**. That second half
is the criterion's real content.

## Then regenerate the transcript

All eighteen scenarios change, plus new ones: a search running, a page read, a throttled
search, an unreachable address, web switched off.

Copy aside, regenerate, diff, and put the diff in the log. Confirm every changed line is the
startup line and the additions are additions.

## Record

Full suite and the hermeticity check. `wc -l` and test count against 1116 and 150. Status for
all 30. What is left after this should be only the criteria a live model has to demonstrate.
