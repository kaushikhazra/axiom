# Goal

Let the model be told what it is working within and where, rather than discovering both by
hitting them - meeting every one of the 12 acceptance criteria on GitHub issue #41.

#34 gave axiom file CRUD and command execution, #35 gave it the web, and #40 taught it to
read what a page actually is. All three bounded what a tool does. **None of them told the
model those bounds exist.** It learns the command timeout by having a command killed, the
page bound by getting a cut page, and its working directory not at all.

Two costs, and the second is the expensive one. A request that cannot succeed is attempted
anyway, repeatedly, until the round limit ends the turn with an empty answer. And work lands
wherever a relative path happens to resolve, which is not necessarily where the user is
looking.

Done when: all 12 criteria of #41 are met, each with evidence recorded in a cycle log; the
criteria about what the model is *told* are evidenced against what a real model actually
received and did, not only against the string axiom assembled; and a run that reaches no
limit is provably unchanged.
