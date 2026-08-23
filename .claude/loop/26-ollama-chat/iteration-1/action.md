# Action

One criterion left. AC 19: Ctrl-C while the model is generating cancels that reply and returns to the prompt; Ctrl-C at an idle prompt exits.

Streaming, added last cycle, is what makes this reachable — there is now a real generation loop to interrupt, and the interrupt lands inside it rather than inside a single blocking call.

Two behaviours, and they must not be confused with each other: an interrupt during generation is *not* an exit, and an interrupt at the prompt *is*. The cancelled reply must be treated the way a cut-off stream already is — the partial does not enter history, and the user is told it was cancelled rather than left thinking the model stopped there on its own.

Evidence to produce: a transcript where a long generation is interrupted part-way, the program says the reply was cancelled, and a following message in the same process gets a real reply · a run where Ctrl-C at an idle prompt exits, with its status code · confirmation that the cancelled reply is absent from history, by asking the model afterwards about what it was saying.

Sending a real Ctrl-C to a child process on Windows is not the same as on POSIX — a `CTRL_C_EVENT` goes to the whole process group. Work out how to deliver it before writing the handler, or the evidence will not be trustworthy.

When this is met, all 19 criteria are met: stop the loop, delete the cron, and report.
