# Action

Cycle 2 left the host and model frozen as module constants. That is the binding constraint, and not only for the configuration criteria: **the failure criteria cannot be evidenced without it.** Proving that an unreachable host produces a named error (AC 13) means pointing the program at an unreachable host, and proving a missing model is named (AC 14) means naming a model that isn't installed. Neither is testable while the values are literals in the source.

So configuration comes before error handling — it is what makes error handling checkable.

Add a host and a model setting, each resolving in the order flag → environment variable → default, with `--help` documenting the defaults, and show the effective host and model to the user at startup.

Target AC 2, 10, 11, 12.

Evidence to produce: `--help` output showing both defaults · a run with the environment variable set, showing the effective value change · a run with both the environment variable and the flag set, showing the flag wins · the startup line naming host and model in a normal run.

Leave error handling and Ctrl-C alone this cycle. Do not add streaming.
