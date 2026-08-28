# 73 — the nesting in a nested list

## Goal

> Every acceptance criterion in GitHub issue #73 holds against the real renderer, and
> `uv run pytest` is green and hermetic — an item indented under another is shown indented
> under it, three levels read as three levels, ordered and unordered nest inside each other,
> returning to a shallower level returns to that level, and a flat list looks exactly as it
> does today.
