# Assumptions

Standing inputs that survive a rewrite of `action.md`. Each was measured on 2026-11-02
unless marked.

1. **Synaptra and axiom cannot share a venv.** synaptra 2.1.1 requires `mcp<2.0`; axiom
   requires `mcp>=2.1.1` and does `from mcp import Client`, absent in mcp 1.30. A dry-run
   install into axiom's venv replaces mcp 2.1.1 with 1.30.0. Hence Synaptra lives in its
   own venv, in the user's project.
2. **Axiom's MCP client works with Synaptra as configured.** Connected, 18 tools, no code
   change. Start takes 19-25 s against axiom's 30 s limit.
3. **Synaptra's `memory_store` refuses a call with no `rater`** and the model then said it
   had remembered. Axiom must supply the rater and must not let a refusal read as success.
4. **Synaptra's recall returns up to `limit` ranked results with `found_by`, `score`,
   `retrievability` and no similarity.** "Relevant" is axiom's judgement. (Read from
   `synaptra/retrieval.py`; not calibrated on real data.)
5. **Cost of installing:** ~940 MB packages (torch 2.14 CPU build, 510 MB), plus the
   `all-MiniLM-L6-v2` embedding model fetched from HuggingFace on first start. CPU only.
   Needs network once. Synaptra requires Python >=3.11.
6. **Entry point:** `synaptra = synaptra.server:main`. Synaptra defaults its data to
   `~/.synaptra/data`; the project-local layout sets `SYNAPTRA_DB` to override.
7. **Decisions from the owner (via Velasari, 2026-11-02):** memory comes with axiom, no
   opt-in; Synaptra in its own venv inside the user's project, data alongside, axiom
   outside it; first run must show what it downloads; axiom does not store exchanges
   itself; live tests wait for the go.
8. **uv is on the user's PATH.** Axiom installs with `uv tool install`, so uv is there; a
   fallback to `python -m venv` and pip is kept for the run that has none.
9. **Per the owner's no-hardcoding rule,** nothing frozen at setup may hold an absolute
   path: the server is launched as `<venv python> -c "from synaptra.server import main; main()"`,
   not through the console shim that pip writes with the venv's path inside it.
