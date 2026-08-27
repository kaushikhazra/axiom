# Goal

Let a user switch to a different installed model in the middle of a conversation, without
losing what has already been said - meeting every one of the 34 acceptance criteria on GitHub
issue #49.

#48 settled which model a run starts with. It is settled **once**, and #48 AC 38 says so
explicitly: the question is not asked again and restarting is the only way to change it. That
is the right shape for one story and the wrong shape for a session where the model turns out
to be the problem - a 2B model that cannot follow the question, or a 9B one being used for
something trivial.

Restarting is not a neutral cost. It throws away the conversation, which is usually the thing
worth keeping: "this model is not getting it, let me try a bigger one" only works if the
bigger one can see what was asked.

So the switch has to carry the conversation across, and the criteria are mostly about what
survives and what does not. The context window and tool availability belong to the new model;
everything the user set, every running server, and every word already said belong to the
session.

Done when: all 34 criteria of #49 are met, each with evidence recorded in a cycle log; the
suite is green and hermetic with no Ollama running; and the golden transcript's change is
accounted for line by line.
