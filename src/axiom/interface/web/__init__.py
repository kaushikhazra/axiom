"""M10 — axiom-web: the FastAPI + AG-UI backend for axiom's interactive UI.

Interface-layer package (per CLAUDE.md's package-per-component rule): the
core (axiom.agent, axiom.router, axiom.loop, axiom.interfaces) never imports
from here. This package imports FROM core, not the other way around
(dryrun-design-3 C1)."""
