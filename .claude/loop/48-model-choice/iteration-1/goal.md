# Goal

Let a user chat with a model their Ollama server actually has - meeting every one of the 38
acceptance criteria on GitHub issue #48.

axiom hardcodes `qwen2.5:7b` as its default model, and nothing checks that the host has it.
When it does not, the failure is silent in the worst way: `supports_tools()` and
`model_info()` both swallow the Ollama error and return `False` and `None`, so axiom prints a
confident startup line claiming Ollama-default context and no tool support, and the user only
learns the truth when their first message fails. #26 AC 14 already asked for better and did
not get it.

The fix is not a better default. It is that **axiom stops carrying a model name at all** and
settles the model from what the host reports - asking the user when there is a choice to make,
remembering what they picked, and never substituting silently.

Done when: all 38 criteria of #48 are met, each with evidence recorded in a cycle log; the
suite is green and hermetic with no Ollama running; and the startup line's regeneration of the
golden transcript is accounted for line by line.
