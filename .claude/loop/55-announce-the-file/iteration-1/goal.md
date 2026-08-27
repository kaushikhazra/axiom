# Goal

Let a user know the first time axiom writes a file of its own into a directory of theirs -
meeting every one of the 11 acceptance criteria on GitHub issue #55.

#48 AC 30 says: *"The first time axiom creates a `.axiom/` folder in a directory that had none,
it says where it put the file. No folder appears in the user's project unannounced."*

That is what was built, exactly: `fresh = not Path(".axiom").exists()`. Correct against the
criterion, and it leaves the hole the criterion was written to close.

**Any project that configures MCP already has `.axiom/mcp.json`.** In one of those, axiom
creates no folder, so it says nothing - and writes `model.json` in there silently, on that run
and on every run after. The user gets a new file in a folder they made for a different purpose,
never announced. That is "a folder appears in the user's project unannounced", one level down.

Kaushik confirmed during the manual pass that usage is directory-based, which makes this worse
rather than academic: every project gets its own `.axiom/model.json`, so every project gets a
file written into it, and how many of those a user is told about is the whole question.

Found 2026-08-27 by a clean-directory run that turned out not to be clean. The confusion over
whether the announcement had fired is the only reason anyone read the wording. No test could
have produced it - **the criterion and the implementation agree perfectly. They are both wrong
about the same thing.**

Done when: all 11 criteria of #55 are met, each with evidence recorded in a cycle log; the suite
is green and hermetic; and the golden transcript's change is accounted for line by line.
