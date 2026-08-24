# Goal

Restructure `C:/Projects/axiom/src/axiom/` from one procedural module into modular
object-oriented Python, so that every one of the 20 acceptance criteria on GitHub
issue #33 is demonstrably true - behaviour identical to before, each responsibility
in its own module, the model backend reachable only through a substitutable seam,
no duplicated handling, no unearned structure, `src/` grown by no more than 50%,
and the full test suite green.

Done when: all 20 criteria of #33 are met, each with evidence recorded in a cycle log.
