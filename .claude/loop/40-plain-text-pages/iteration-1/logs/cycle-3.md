# Cycle 3 — 2026-08-26, 01:43 IST

The external check. **It found a real bug in AC 7, which cycle 2 had marked
`met-with-evidence`.** Fixed, attacked again, and converged.

## The bug the cold read caught

AC 7, as written on GitHub:

> A page that announces no type at all is **judged by its content** rather than assumed
> readable.

Cycle 2 implemented "no type → treat as text", unconditionally, and marked the criterion met
on the strength of `test_a_page_announcing_no_type_is_read_as_text` — which serves a **text**
body with no type and asserts it comes back. That test passes for an implementation that
does no judging at all.

`.tmp/attack_ac7.py` serves 56 bytes of PNG over a raw socket with no `Content-Type`:

```
result       : '\udcefPNG\r\n\x1a\n\x00\x00\x00\rIHDR…SECRETBYTES…'
is an error  : False
is a source  : True
*** BYTES LEAKED: True ***
```

The bytes came back as content, and the page was counted as a source. That is AC 7 failed on
its own words, AC 6 failed in spirit, and AC 11 failed outright. **Cycle 2 tested the happy
path of the criterion and never attacked it**, then wrote `met-with-evidence` next to it.

This is exactly what `observe.md`'s external-check rule exists to catch, and it is worth
recording that it fired on its first use.

## The fix, and why it is shaped this way

A NUL byte in the decoded text means the body is not text. It is the test `file` and git
both use: binary formats carry NUL and text does not.

Two decisions inside it, both deliberate:

- **Read the decoded string, not the raw bytes.** utf-16 is half zero bytes and a raw check
  would refuse perfectly good text. Verified: a utf-16 body with a declared charset decodes
  into ordinary text and passes. `test_utf16_text_is_not_mistaken_for_binary` exists
  specifically to stop a later cycle "simplifying" the check back onto the bytes.
- **Applied to every text body, not only the typeless one.** A server announcing
  `text/plain` over a PNG is lying; the cost of not believing it is nothing, because real
  text does not contain NUL. This is one uniform rule rather than a special case, and it
  closes the AC 6 attack `action.md` asked about as a side effect.

Kaushik's decision — *"if the content type is not provided, assume it as text"* — is
preserved exactly. The default is still text. What was missing was the judgement AC 7 asks
for on top of it, and defaulting to text is not the same thing as skipping the check.

## The other attacks, all survived

`.tmp/attack_ac2_ac9.py`:

| attack | result |
|---|---|
| latin-1 body, charset declared | decodes correctly, exact match |
| utf-16 body, charset declared | decodes correctly, **not** flagged binary |
| CRLF line endings | preserved byte-for-byte |
| tabs and trailing whitespace | preserved |
| cut on plain text | applied, same `[cut here - N …]` message as HTML |
| multi-byte body | no mojibake, no mid-character cut |
| PNG announced as `text/plain` | refused, nothing leaked |

## Criteria, judged against the issue text

| AC | verdict | differs from cycle 2? |
|---|---|---|
| 1 | met | no |
| 2 | met — now also under latin-1, utf-16, CRLF, tabs | no, but broader |
| 3 | met | no |
| 4 | met — transcript byte-identical, not regenerated | no |
| 5 | met | no |
| 6 | met — including a server lying about the type | no, but broader |
| 7 | **met only after a fix** | **yes — cycle 2 was wrong** |
| 8 | met | no |
| 9 | met | no |
| 10 | met | no |
| 11 | met — a typeless binary is no longer named | **yes, as a consequence of AC 7** |
| 12 | met — four strings byte-identical to cycle 1 | no |

Suite: **229 passed**, hermetic. Transcript unchanged and never regenerated. Live sweep:
eight of eight text pages return their contents; PDF and PNG refused by name.

## An honesty note about this check

`observe.md` asks for "a reading that does not have this loop's context". This cycle ran in
the same session that wrote cycle 2, so it was not context-free, and I am not going to claim
it was. What made it work was method rather than amnesia: reading the criterion off GitHub
**before** the log or the diff, and then trying to break each one rather than confirming it.
The AC 7 bug was found by writing an attack, not by re-reading code.

A genuinely fresh reader would be stronger and should be used where one is available. Where
one is not, adversarial attempts on each criterion are the substitute that actually caught
something.

## Verdict

All twelve criteria met with evidence. Taking `loop.md` exit 1.
