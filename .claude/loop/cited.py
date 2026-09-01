"""Which acceptance criteria a test file actually claims.

Two greps have now been wrong about this in opposite directions, one cycle apart.

    grep -rhoE "#80 AC [0-9]+"     under-reports: it sees only the first criterion
                                   of a phrase, so "#80 AC 23, and AC 4 and AC 24
                                   with it" reads as AC 23 alone. Two false claims
                                   hid behind that for two cycles.

    grep -rhoE "AC [0-9]+"         over-reports: it cannot tell a claim from a
                                   disclaimer, so a docstring saying "this used to
                                   claim AC 4 and never proved it" reads as a claim.

Neither reads meaning, and a check that is trusted and wrong is worse than none.

**The convention this reads is the one the tests already follow**: a test claims its
criteria on the *first line* of its docstring, and discusses everything else below.
So the claims are the `AC N` on line one, and nothing further down counts.

One rule the convention needs and did not state: **a first line cites the file's own
issue and nothing else.** This cannot tell #42's AC 4 from #80's, and a test that
mentioned both on line one reported a criterion it was not testing. Another issue's
number goes on the second line.

    uv run --no-sync python .claude/loop/cited.py tests/test_multiline.py
    uv run --no-sync python .claude/loop/cited.py tests/test_multiline.py --by-test

Compare the list against `gh issue view <n>`. A criterion in the issue and not here
has no test; a number here and not in the issue is a citation left behind by a
renumbering.
"""

import ast
import re
import sys
from pathlib import Path

CITATION = re.compile(r"AC (\d+)")


def claims(path: Path) -> dict[str, list[int]]:
    """Every test in `path`, with the criteria its docstring's first line claims."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: dict[str, list[int]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or not node.name.startswith("test_"):
            continue
        doc = ast.get_docstring(node) or ""
        first = doc.split("\n", 1)[0]
        found[node.name] = [int(n) for n in CITATION.findall(first)]
    return found


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__.strip().splitlines()[-4])
        return 2
    path = Path(argv[0])
    by_test = "--by-test" in argv
    found = claims(path)

    if by_test:
        for name, numbers in sorted(found.items()):
            shown = ", ".join(str(n) for n in numbers) if numbers else "-"
            print(f"  {shown:<16} {name}")
        print()

    every = sorted({n for numbers in found.values() for n in numbers})
    silent = [name for name, numbers in found.items() if not numbers]

    print(f"  claimed: {' '.join(str(n) for n in every)}")
    print(f"  {len(found)} tests, {len(every)} criteria claimed")
    if silent:
        print(f"  {len(silent)} claiming nothing: {', '.join(sorted(silent))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
