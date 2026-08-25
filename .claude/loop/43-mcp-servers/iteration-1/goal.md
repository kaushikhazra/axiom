# Goal

Let a user give axiom tools from MCP servers they already run on their machine - meeting
every one of the 30 acceptance criteria on GitHub issue #43.

#34 gave axiom seven tools of its own. Every one of them is code in this repo, and adding an
eighth means changing that code. A user who needs axiom to reach something it has no tool for
- a database, a ticket tracker, a device - has no way in.

MCP is the standard answer to that, and the servers already exist. What is missing is the
client.

This is the largest story in the queue and the only one that adds a dependency, a
configuration file, and a source of tools axiom did not write. It is last for that reason.

Done when: all 30 criteria of #43 are met, each with evidence recorded in a cycle log; the
criteria about a server's lifetime are evidenced against a real subprocess rather than an
in-process stand-in; and a run with no server configured is provably identical to today.
