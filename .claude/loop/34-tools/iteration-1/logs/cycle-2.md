# Cycle 2 - 2026-08-25 06:22 IST

The seam, one tool, and a live round trip through the real program. **66 tests green,
transcript unchanged.**

## Tool support is free

`show()` exposes `capabilities` on the same call `model_info()` already makes:

| model | capabilities |
|---|---|
| `qwen2.5:7b` | `completion`, `tools` |
| `gemma4:e2b` | `completion`, `vision`, `audio`, `tools`, `thinking` |
| `ornith:9b` | `completion`, `tools`, `thinking` |
| `gemma2:2b` | `completion` |

So AC 2's startup check costs nothing and needs no probe request. `supports_tools()` joins the
protocol and asks `show()` directly. It does not share `model_info()`'s call - a second local
HTTP round trip at startup is a few milliseconds, and caching it would add state to earn back
nothing measurable.

## The dict form holds, so the abstraction holds

Cycle 1's round trip fed Ollama's own `Message` object back into history. If `Call` is our own
type, the assistant turn has to be rebuilt from primitives instead - and if Ollama rejected
that, the vendor object would have had to leak all the way up to the chat loop.

Probed before designing on it. Ollama accepts:

```python
{"role": "assistant", "content": "",
 "tool_calls": [{"function": {"name": ..., "arguments": {...}}}]}
```

and the model answered from the file contents exactly as with its own object. **`backend.py`
stays the only module that knows what a vendor looks like.**

## What was built

`backend.py` - `Call(name, arguments)` alongside `Piece`, with `as_message_part()` for the
history rebuild. `stream()` takes `tools` and yields either type. `supports_tools()`.

A deliberate detail: **a `Piece` is still yielded for every chunk, empty text included.** The
final chunk usually carries no text and all of the usage counts, so filtering empty pieces
would silently break compaction's trigger. That is why the non-tool transcript is untouched.

`tools.py` (new, 86 lines) - a `Tool` dataclass, a registry, `declarations()` and `run()`.
`run()` returns failures rather than raising: the model is what has to act on a failed tool,
and a tool that cannot do its job is not a reason to end the turn.

`terminal.py` - `note_tool()` before, `show_tool_result()` after, the latter prefixing every
line with `  | ` and truncating at 2000 characters.

`__init__.py` - the turn is now a bounded loop, at most `MAX_TOOL_ROUNDS = 5` passes. On
failure it deletes everything appended since the user's line rather than popping one message,
because a failed turn may have accumulated tool results.

## Live, through the real program

```
$ printf '...notes.txt say?\n/exit\n' | python -c "from axiom import main; main([...])"
axiom: qwen2.5:7b at http://localhost:11434 (context: 500 tokens, debug override)
> axiom: read_file(path='C:/Projects/.tmp/axiom-tool-sandbox/notes.txt')
  | Biscuit the cat is ginger.
The file `...notes.txt` contains the following content: "Biscuit the cat is ginger."
>
```

Real model, real tool, real file, real program. AC 10, 18, 19, 21 and 22 in one run.

(The `debug override` in that line is the leaked `AXIOM_DEBUG_MAX_CONTEXT=500` from #29,
still in this session's environment. It affects the live program, not the suite, and did not
change the outcome.)

## A pre-existing crash, found by accident

Verifying the tool-less path, `gemma2:2b` chatted normally without tools - and then killed
the program mid-answer:

```
UnicodeEncodeError: 'charmap' codec can't encode character '\U0001f60a'
```

The model emitted an emoji. Windows consoles default to cp1252, which cannot spell it, and
`print()` raised on a reply that was otherwise finished and correct.

**This is not #34's bug.** `show_piece` is #33's code and #26's before that; it would crash on
`master` today for any model that emits an emoji, which small chatty models do constantly. It
was invisible until now only because every previous live run happened to stay inside cp1252.

Fixed in `terminal.py`, which is where writing to a terminal belongs: stdout and stderr are
reconfigured to UTF-8 with `errors="replace"`, guarded so a stream that cannot be retuned -
pytest's capture, for instance - is left alone. An unreadable glyph beats a traceback over a
finished answer.

Verified: `gemma2:2b` asked for an emoji now prints `Hello! 👋` and exits cleanly.

Fixing it here rather than filing it: it crashes the program, it blocks this loop's own live
verification, and the fix is four lines in the module that owns the problem. Recorded as
out-of-scope so the #34 story stays legible.

## Structure kept

```
$ grep -rn "ollama\|httpx" src/ --include=*.py | grep -v backend.py   -> nothing
$ grep -rln "print(\|input("  src/ --include=*.py                     -> terminal.py only
```

`src/` is **651 lines**, up from 442. No ceiling applies here; recorded so growth stays
visible.

## Criteria status

**Startup**
1. `not-started` - deliberately. The startup line is where the transcript legitimately
   changes, and holding it back kept the safety net intact while the mechanism landed.
2. `attempted` - detection works and a tool-less model chats normally with nothing sent; the
   user is not yet *told*

**Works across models**
3. `not-started` - only `qwen2.5:7b` verified live this cycle
4. `met-with-evidence` - `declarations()` takes no model argument, and grep finds no
   model-conditional anywhere in `src/`
5. `attempted` - structurally true, not demonstrated by actually adding a model
6. `not-started` - and still no live example to design against
7. `not-started` - only the streaming path is exercised
8. `attempted` - `gemma2:2b` ran live and behaved; AC 2 itself is incomplete

**Files**
9. `not-started`
10. `met-with-evidence` - live, answered from the file's real contents
11. `not-started`
12. `not-started`

**Commands** 13-16 `not-started`

**Multi-step work**
17. `attempted` - the loop exists and is bounded; only a single call demonstrated
18. `met-with-evidence` - live, the model answered from the tool result
19. `met-with-evidence` - assistant and tool messages enter history and the model matched them
20. `not-started`

**Visibility**
21. `met-with-evidence` - `axiom: read_file(path='...')` printed before it ran
22. `met-with-evidence` - `  | ` prefix, live
23. `attempted` - implemented at 2000 characters, not yet tested

**Boundaries** 24-27 `not-started` - 24's path exists in `run()` but is untested

**Failure and recovery**
28. `attempted` - `run()` returns failures rather than raising; untested
29. `attempted` - an unknown tool name returns a message; untested
30. `not-started`
31. `not-started`

**Configuration** 32-34 `not-started`

**Exit**
35. `met-with-evidence` - transcript unchanged, and `/exit` after a tool ran exited cleanly

## Goal check

**Not met.** 8 criteria carry evidence, from 0. The mechanism is proven end to end; what
remains is more tools, the startup line, and the boundaries.

## What is still missing

Nothing looks blocked. The next constraint is that **every criterion still standing needs
tests, and there are no tool tests at all yet** - this cycle proved the mechanism live but
added not one test for it. That is the gap to close before adding a second tool, or the tool
count grows faster than the evidence for it.
