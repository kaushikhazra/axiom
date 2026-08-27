# Goal

Let a user's config file be read however their editor or shell saved it - meeting every one of
the 9 acceptance criteria on GitHub issue #57.

`.axiom/mcp.json` is the one file axiom asks a user to write by hand. `.claude/handoff.md` says
so explicitly. And on Windows the default way to write it produces a file axiom rejects:
`Set-Content -Encoding utf8` in PowerShell 5.1, `Out-File`, and Notepad's "UTF-8" all emit a
byte order mark, `config.read_servers` reads with `encoding="utf-8"`, and `json.loads` refuses
it outright:

```
axiom: .axiom\mcp.json could not be read (Unexpected UTF-8 BOM (decode using utf-8-sig): line 1 column 1 (char 0))
```

Found in the first five minutes of the first manual pass, 2026-08-27, by Kaushik writing that
file the ordinary way for his platform.

Nothing in the suite could have caught it. Every test writes config with `Path.write_text(...,
encoding="utf-8")` - Python's own encoding, which never emits a mark - so the stubs and the
world disagreed about what a file looks like. That is the same fault as `given_page` announcing
`text/plain` over HTML in #40, and the constant `prompt_eval_count` in #41.

**axiom behaved correctly around the failure** and that part is not in scope to change: it
named the file, gave the cause verbatim, started without the server, and left the session
usable. The message was good enough to diagnose from one line. Only the reading is wrong.

Done when: all 9 criteria of #57 are met, each with evidence recorded in a cycle log; the suite
is green and hermetic; and a file written by PowerShell's own default is read by axiom without
complaint.
