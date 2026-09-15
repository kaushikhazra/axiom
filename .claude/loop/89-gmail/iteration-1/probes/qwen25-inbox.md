# Does the folder operator survive without a thinking phase?

Run 2026-09-15, twice, from a pipe. One question — *"what's in my inbox?"* — asked of
`qwen2.5:7b`, which is dense and **non-thinking**. That is the whole reason it was worth a
run: `ornith:9b` reached `in:inbox` and thinks, `gemma4:e2b` reached a bare `inbox` and
does not, so neither of them separates *the description works* from *reasoning rescued
it*.

Steps in `qwen25-inbox.steps`. Driven by `../../74-scheduled-prompts/iteration-1/drive.py`,
which needs `AXIOM_GOOGLE_CLIENT_ID` and `AXIOM_GOOGLE_CLIENT_SECRET` in the environment it
is started with:

```
uv run --env-file <the env file> --project C:/Projects/axiom python \
  .claude/loop/74-scheduled-prompts/iteration-1/drive.py \
  .claude/loop/89-gmail/iteration-1/probes/qwen25-inbox.steps qwen2.5:7b
```

## What it wrote

Both runs, identically:

```
axiom: search_mail(query=is:inbox)
```

**Not `in:`, which is the operator `e3f435b` added, and not the bare `inbox` that was the
defect.** A third answer, and the one thing that decides whether it is a defect is what
Gmail does with it.

## What Gmail does with it

`ground_truth.py` asks the API the same four ways with the grant axiom already holds, and
prints each message's real `labelIds`. Twelve newest, checked against the INBOX label:

| query | against ground truth |
|---|---|
| `labelIds=[INBOX]` | the ground truth itself |
| `in:inbox` | identical, twelve for twelve, in order |
| `is:inbox` | **identical, twelve for twelve, in order** |
| `inbox` | **differs — none of the twelve**, and three of what it returns carry no INBOX label |

So `is:inbox` is honoured, `qwen2.5:7b`'s answer was right, and **the contingency in the
handoff is not needed** — moving `in:inbox` into the description's single `Example:` line
would fix something that is not broken.

Worth keeping straight: this does **not** show the model read `in:` and generalised. `is:`
was already in the description, on `is:unread`, and `is:inbox` is what you get by
extending that pattern. One run cannot tell which line it drew from. What it does show is
that a non-thinking 7B composes a working folder filter from this description, which is
the question that was open.

**The floor sits between ~2B and 7B**, not at thinking. `gemma4:e2b` failed this with
`e3f435b` already loaded.

## Two things fell out of it

**The transcript died at the first emoji.** Run 1 lost every line after second 28 of a
five minute run — the entire reply. `drive.py` decodes the child as utf-8 correctly and
then *echoes* it, and its own stdout is a pipe, which on Windows is cp1252: a 🙏 in a
subject line raised `UnicodeEncodeError` **inside the reader thread**, which killed the
thread silently while the run carried on for another four minutes. Fixed in both scripts
by reconfiguring stdout with `errors="replace"`. Any mail row driven from a pipe would
have hit this — real mail is full of characters cp1252 has no byte for.

**One more data point for [#78](https://github.com/kaushikhazra/axiom/issues/78).** In the
relayed list, the Uber receipt is stamped `11:14:01 IST`. The tool line above it says that
message arrived `06:08:28 +0000`; `11:14:01 +0530` belongs to the Pepperfry message two
rows up. Axiom supplied both correctly. Same shape as the three from 15 Sep — not
invention from nothing, a field crossing between adjacent rows.

## Where the transcripts are

**Not in this repo**, which is public. They list ten real messages with senders and
subjects, including one naming a school. They are at
`C:/Projects/.tmp/axiom-manual/probe-logs/`, next to the rest of the manual pass. Nothing
in the finding above needs them — the query line is the evidence, and `ground_truth.py`
reproduces the comparison against the live mailbox in about twenty seconds.
