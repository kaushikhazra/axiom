# Action

Cycle 1 left the program exiting after one exchange. That single constraint is what blocks the largest group of criteria — turns, history, empty input, and every way out of the program all require a session that persists.

Turn the one exchange into a session: loop on input, keep the message list across turns and send it whole, skip the model on an empty line, and handle both ways of leaving (an explicit exit command and EOF) with status 0.

Target AC 6, 7, 8, 9, 17, 18.

Evidence to produce: a single transcript showing three turns in one process, where the third turn asks the model about something said in the first and it answers correctly. Then a second run showing the conversation starts empty. Then `echo -n "" | ...` and an exit-command run, each with its status code.

Leave configuration, error handling, and Ctrl-C alone this cycle.
