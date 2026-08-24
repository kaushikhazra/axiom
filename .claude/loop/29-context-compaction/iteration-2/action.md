# Action

Treat C and D as one investigation, not two — this cycle's evidence showed D's growth directly feeds C's overflow risk (a ballooned, verbatim-carried-forward summary is exactly the kind of thing that could itself exceed `num_ctx` on a later turn).

Start by reproducing C for real, on the now-stable GPU: drive the same kind of scenario (small `AXIOM_DEBUG_MAX_CONTEXT`, many natural turns, compaction firing repeatedly) far enough that the *compacted* history itself — not a raw oversized message this time, the summary produced by repeated compaction — grows large enough to risk exceeding `num_ctx` on its own. Confirm whether it actually overflows and gets silently truncated by Ollama (matching the mechanism already found live earlier tonight with a raw oversized message), or whether something else happens.

Once reproduced, the fix likely needs to address both at once: something that stops the carried-forward summary from growing unboundedly (re-compact the summary itself once it exceeds some size, rather than only ever appending to it — this reintroduces a bounded version of "re-summarize a summary," but deliberately this time, with the same anti-narrative-drift instruction B already fixed, and only when actually needed rather than on every pass) — and a check before sending that the final assembled request (summary + kept pairs + new message) doesn't itself risk exceeding `num_ctx`, using something more reliable than `estimated_tokens()`'s character guess if one exists.

Investigate what's actually available before committing to a mechanism for the second half — don't assume a real tokenizer call exists without checking.

Evidence to produce: a live run where D's growth is deliberately pushed far enough to test C's boundary, showing either a genuine failure caught and handled (named, not silently truncated) or the growth successfully bounded before it becomes a problem. Full suite green throughout.

If this cycle also runs out of time: same discipline as last time — stop clean, write down exactly what's proven and what isn't, don't claim more than the evidence supports.
