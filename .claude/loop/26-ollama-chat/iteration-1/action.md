# Action

Cycle 3 made the host and model addressable, which was the thing standing between the loop and the failure criteria. Take them now.

Every failure currently escapes as a traceback and kills the process. Catch what the client raises, report it in terms the user can act on — naming the host that was tried, or the model that was asked for — and return to the prompt with the session intact rather than exiting.

Target AC 13, 14, 16.

Evidence to produce: a run against `--host http://127.0.0.1:9999` showing the error names that host and no traceback appears · a run with `--model does-not-exist:1b` showing the error names that model and no other model answers · a transcript where a failed turn is followed by a working turn in the same process, proving the session survived.

The reply after a failure must be a real one, not a cached or fallback string — show it in the transcript.

Leave Ctrl-C and streaming alone this cycle.
