# Action

Wire configuration and the startup line. This is the cycle where the transcript changes
deliberately, so make that the headline rather than a side effect.

## Configuration first

`config.Settings` gains the two things tools need, each with a default and an override
(AC 32, AC 33), plus a switch (AC 34):

- the directory commands run in - default: wherever axiom was started
- the command time limit - default: the current 30 seconds
- tools on or off for the session

Resolve them in `config.resolve()` alongside host and model, same precedence: command line,
then environment, then default. Then hand them to `tools` rather than leaving
`WORKING_DIRECTORY` and `COMMAND_TIMEOUT_SECONDS` as module constants nothing sets.

**How they are handed over is the design decision.** Module-level globals that `main()`
mutates would work and would be the wrong shape - `tools.run()` would depend on assignment
order, and two tests running in either order would interfere. Prefer passing what a tool
needs into `run()`, and keep it out of the model-visible schema so the argument filter added
in cycle 4 still refuses it from a model.

## Then the startup line

AC 1: tools are available, shown alongside model, host and context.
AC 2: a model that cannot call tools is said so in plain terms, and chat still works.
AC 34: when tools are off, the line says so.

Three states, one line. `terminal.announce()` already formats the startup line and should
keep doing it - do not assemble the text in `main()` and pass a finished string.

## Then regenerate the transcript, deliberately

Every one of the sixteen scenarios starts with that line, so all sixteen change. This is the
legitimate regeneration `observe.md` describes.

**Follow the cycle-3 procedure, which earned itself:** copy the baseline aside first,
regenerate, then `diff` old against new and put the diff in the log. Confirm every changed
line is the startup line and nothing else moved. A regeneration reviewed without a diff is
how a real regression gets committed as an intended change.

Add scenarios for the states that do not exist yet: tools switched off, and a model that
cannot use them (the latter exists but its startup line is about to gain meaning).

## Then AC 30 and AC 31 if there is room

Ctrl-C during a running tool, and a tool failure being distinguishable from a model or
connection failure. If the cycle is full, leave them - they are small and independent.

## Do not

Touch the live models. That is its own cycle, and it needs the startup line settled first so
what it verifies is the finished behaviour.

## Record

Full suite and the hermeticity check. `wc -l` and test count against 828 and 106. Status for
all 35. The diff, in full.
