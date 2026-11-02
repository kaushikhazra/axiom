"""A stand-in for Synaptra that the tests own (#95).

`CLAUDE.md` forbids a test fetching a server or a package, and the real Synaptra is a
gigabyte with an embedding model behind it. This answers in the shapes the real one was
measured to answer in on 2026-11-02 - including the refusal of a store with no `rater`,
which is the failure this feature exists to catch - and keeps its memories in a file so
a second process can find what the first stored.

Recall ranks nothing: it returns every memory, marking one as found by meaning *and* by
shared words when the question and the memory share a word, and by meaning and recency
otherwise. That is enough to exercise axiom's filter and nothing more; it says nothing
about whether the real server's ranking is any good.
"""

import json
import os
from pathlib import Path

from mcp.server import MCPServer

server = MCPServer("FakeSynaptra")
STORE_FILE = Path(os.environ["FAKE_SYNAPTRA_FILE"])


def _load() -> list[dict]:
    return (
        json.loads(STORE_FILE.read_text(encoding="utf-8"))
        if STORE_FILE.exists()
        else []
    )


@server.tool()
def memory_store(
    content: str,
    rater: str | None = None,
    memory_type: str | None = None,
    source: str | None = None,
) -> str:
    """Store a memory. `rater` is required, as it is in the real server."""
    if not rater or os.environ.get("FAKE_SYNAPTRA_REFUSE"):
        return json.dumps(
            {
                "success": False,
                "error": "rater is required when setting importance. Pass the "
                "identifier of the model producing the score.",
                "data": None,
                "meta": {},
            }
        )
    memories = _load()
    memories.append({"content": content, "rater": rater, "source": source})
    STORE_FILE.write_text(json.dumps(memories), encoding="utf-8")
    return json.dumps(
        {"success": True, "data": {"id": str(len(memories)), "content": content}}
    )


@server.tool()
def memory_recall(query: str, limit: int | None = None) -> str:
    """Return what is stored, marked by how it was found."""
    if os.environ.get("FAKE_SYNAPTRA_BREAK"):
        return json.dumps({"success": False, "error": "store unreachable"})
    # The keyword strategy matches only when *every* word of the query is in the
    # memory - measured against the real server on 2026-11-02, where "cat" and
    # "Biscuit" found a memory by keyword and "what is my cat called?" did not.
    asked = {word.strip("?.,!").lower() for word in query.split()} - {""}
    found = []
    for memory in _load():
        words = {word.strip("?.,!").lower() for word in memory["content"].split()}
        by = (
            ["semantic", "keyword"]
            if asked and asked <= words
            else ["semantic", "temporal"]
        )
        found.append({"content": memory["content"], "found_by": by, "score": 0.02})
    return json.dumps({"success": True, "data": {"memories": found[: limit or 10]}})


@server.tool()
def memory_archive(id: str) -> str:
    """A tool axiom must not offer the model."""
    return json.dumps({"success": True, "data": {}})


if __name__ == "__main__":
    server.run()
