# 29-context-compaction, iteration 2

## Goal

> Fix repeated compaction losing facts: found live during manual verification of #29 (kaushikhazra/axiom) — after a second "compacting older history (everything)" pass in the same session, the model could no longer recall a fact ("teal") that a *single* compaction pass had preserved correctly. Finished when a real, live conversation survives two or more compaction passes in the same session and still correctly answers a question about a fact from the very first message.
