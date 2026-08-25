# Action

Close AC 20, AC 30 and AC 31. Take AC 20 first - it is the one carrying an unknown, and the
other two are small.

## AC 20: what compaction makes of tool history

`compacted_history` was written for a conversation of `{role, content}` pairs. Tool use
breaks both halves of that assumption:

- an assistant message carrying only `tool_calls` has `content=""`
- a `tool`-role message is not part of a user/assistant pair at all

Nothing has checked what happens. **Find out before deciding anything.** Build a history
containing a tool exchange, run `maybe_compact` over it, and record exactly what comes back -
whether the tool calls survive, whether the pair arithmetic still lines up, and whether the
summary the model is given still describes what was done.

Then decide, and say which it is:

- the existing behaviour is already correct, and a test now pins it; or
- it is wrong, and here is the fix.

**Do not assume it is broken.** A conversation whose older turns are replaced by a system
summary may lose nothing that matters - the summary says a file was read and what it said.
The criterion asks that compaction *treats them as history*, not that the calls survive
verbatim.

The sharp end is AC 20's second half: a compacted session must still be able to refer to work
done before the compaction. Test that directly - a tool result from turn one, a compaction,
then a question in turn ten whose answer depends on it.

## AC 30: Ctrl-C during a running tool

The turn loop already catches `KeyboardInterrupt` around the whole turn, so the session
survives. The question is what happens to the **process**.

`run_command` blocks in `communicate()`. An interrupt there propagates out with the child
still running - the same class of bug as cycle 4's timeout, and this one leaves a process
behind after the user thinks they cancelled. Handle it where the timeout is handled, kill the
tree, and re-raise so the turn still unwinds.

Test it the way cycle 4's timeout was tested: have the command write a marker after the
interrupt should have killed it, and assert the marker never appears. Asserting only that the
session survived would pass against a program that leaks processes.

## AC 31: telling failures apart

A tool that failed, a model that refused, and a connection that dropped must not read the
same. Two of the three already differ. Check the third and close the gap if there is one -
`report_failure` handles model and connection failures; a tool failure currently arrives as
`  | error: ...` in the tool output, which may already be distinct enough. Decide with the
transcript in front of you rather than from the code.

## Then, if the cycle has room

Nothing. Leave the live model pass to its own cycle - it needs three model loads and should
not be squeezed into the end of another.

## Record

Full suite and the hermeticity check. Status for all 35. If the transcript changes, diff it
and put the diff in the log.
