"""Searching the web and reading a page.

No test here touches the network. ddgs and httpx are replaced at the point
tools.py uses them, so the suite stays green offline and cannot be made to
depend on someone else's uptime.
"""

import httpx
import pytest

from axiom import tools
from axiom.tools import Limits

PAGE = "https://example.invalid/page"


def search(query: str = "anything", limits: Limits = None) -> str:
    return tools.run("search_web", {"query": query}, limits or tools.DEFAULT_LIMITS)


def fetch(url: str = PAGE, limits: Limits = None) -> str:
    return tools.run("fetch_page", {"url": url}, limits or tools.DEFAULT_LIMITS)


def given_results(monkeypatch, results, asked=None):
    class Stub:
        def text(self, query, max_results=None):  # noqa: ANN001
            if asked is not None:
                asked.update({"query": query, "max_results": max_results})
            return results

    monkeypatch.setattr(tools.ddgs, "DDGS", Stub)


def given_search_raises(monkeypatch, failure):
    class Stub:
        def text(self, query, max_results=None):  # noqa: ANN001, ARG002
            raise failure

    monkeypatch.setattr(tools.ddgs, "DDGS", Stub)


def given_page(monkeypatch, html="", status=200, raises=None, seen=None):
    def fake_get(url, timeout=None, follow_redirects=None):  # noqa: ANN001
        if seen is not None:
            seen.update({"url": url, "timeout": timeout})
        if raises is not None:
            raise raises
        return httpx.Response(status, text=html, request=httpx.Request("GET", url))

    monkeypatch.setattr(tools.httpx, "get", fake_get)


# --- searching --------------------------------------------------------------


def test_a_result_carries_title_address_and_snippet(monkeypatch):
    """AC 3: axiom has to be able to choose between results."""
    given_results(
        monkeypatch,
        [{"title": "Pathlib docs", "href": "https://x/y", "body": "a snippet"}],
    )

    result = search()

    assert "Pathlib docs" in result
    assert "https://x/y" in result
    assert "a snippet" in result


def test_the_result_count_has_a_default_and_is_honoured(monkeypatch):
    """AC 4: one search must not crowd out the conversation."""
    asked = {}
    given_results(monkeypatch, [], asked)

    search()
    assert asked["max_results"] == tools.DEFAULT_LIMITS.search_results

    search(limits=Limits(search_results=2))
    assert asked["max_results"] == 2


def test_no_results_is_reported_as_no_results(monkeypatch):
    """AC 16: not an error, and not something to answer around."""
    given_results(monkeypatch, [])

    result = search("nothing at all")

    assert "no results" in result
    assert "error" not in result


def test_throttling_is_reported_distinctly(monkeypatch):
    """AC 19: the advice is to wait. Telling the user to check their network
    would send them after a problem they do not have."""
    given_search_raises(
        monkeypatch, tools.ddgs.exceptions.RatelimitException("202 Ratelimit")
    )

    result = search()

    assert "throttl" in result
    assert "wait" in result


def test_a_search_timeout_is_not_reported_as_throttling(monkeypatch):
    given_search_raises(monkeypatch, tools.ddgs.exceptions.TimeoutException("too slow"))

    result = search()

    assert "error:" in result
    assert "throttl" not in result


def test_an_unreachable_provider_is_not_reported_as_throttling(monkeypatch):
    given_search_raises(monkeypatch, OSError("no route to host"))

    result = search()

    assert "error:" in result
    assert "throttl" not in result


# --- reading a page ---------------------------------------------------------


def test_a_page_comes_back_as_readable_text(monkeypatch):
    """AC 5 and AC 6: prose, not markup."""
    given_page(
        monkeypatch,
        "<html><body><nav>Home About</nav><article><p>"
        + "Biscuit the cat is ginger. " * 20
        + "</p></article></body></html>",
    )

    result = fetch()

    assert "Biscuit the cat is ginger." in result
    assert "<p>" not in result
    assert "<html" not in result


def test_an_error_status_is_reported_as_that_error(monkeypatch):
    """AC 21, and the reason it is not enough to return the body.

    httpx does not raise on 4xx, and a real 404 page carries several kilobytes
    of prose that extracts cleanly. Returned as content, the model would answer
    from an error page believing it was the page asked for.
    """
    given_page(
        monkeypatch,
        "<html><body><article><p>"
        + "Sorry, that page could not be found on this server. " * 20
        + "</p></article></body></html>",
        status=404,
    )

    result = fetch()

    assert "404" in result
    assert result.startswith("error:")
    assert "could not be found on this server" not in result


def test_a_page_with_no_readable_text_says_so(monkeypatch):
    """AC 17: reported as having none, rather than returned as noise."""
    given_page(monkeypatch, "<html><body><script>var x = 1;</script></body></html>")

    result = fetch()

    assert "no readable text" in result


def test_a_large_page_is_cut_and_says_by_how_much(monkeypatch):
    """AC 18: the bound is on what the model is given.

    #34 made display truncation a screen concern with the model receiving
    results whole. Right for a file; a 54,000-character page would crowd out
    the conversation and then trigger compaction.
    """
    given_page(
        monkeypatch,
        "<html><body><article><p>" + ("word " * 5000) + "</p></article></body></html>",
    )

    result = fetch(limits=Limits(page_characters=500))

    assert len(result) < 700, "the page was not cut"
    assert "cut here" in result
    assert "more characters not included" in result


def test_an_unreachable_address_reports_the_reason(monkeypatch):
    """AC 20."""
    given_page(monkeypatch, raises=httpx.ConnectError("connection refused"))

    result = fetch()

    assert result.startswith("error:")
    assert PAGE in result
    assert "connection refused" in result


def test_a_fetch_that_does_not_finish_is_stopped(monkeypatch):
    """AC 22: stopped at the limit, and said to have been stopped."""
    given_page(monkeypatch, raises=httpx.ReadTimeout("too slow"))

    result = fetch(limits=Limits(fetch_timeout=3))

    assert "did not answer within 3 seconds" in result


def test_the_fetch_timeout_reaches_the_request(monkeypatch):
    seen = {}
    given_page(monkeypatch, "<html><body><p>hi</p></body></html>", seen=seen)

    fetch(limits=Limits(fetch_timeout=7))

    assert seen["timeout"] == 7


# --- independence -----------------------------------------------------------


def test_a_throttled_search_does_not_prevent_reading_a_page(monkeypatch):
    """AC 10, forced rather than assumed.

    DuckDuckGo throttling is routine, and if it took away the ability to read
    an address the user handed over, one 202 would disable half the feature.
    """
    given_search_raises(
        monkeypatch, tools.ddgs.exceptions.RatelimitException("202 Ratelimit")
    )
    given_page(
        monkeypatch,
        "<html><body><article><p>"
        + "Still readable. " * 20
        + "</p></article></body></html>",
    )

    throttled = search()
    read = fetch()

    assert "throttl" in throttled
    assert "Still readable." in read


def test_an_unreachable_page_does_not_prevent_searching(monkeypatch):
    """AC 10, the other direction."""
    given_page(monkeypatch, raises=httpx.ConnectError("refused"))
    given_results(
        monkeypatch, [{"title": "T", "href": "https://x/y", "body": "snippet"}]
    )

    failed = fetch()
    found = search()

    assert failed.startswith("error:")
    assert "https://x/y" in found


# --- the tools are declared like any other ----------------------------------


@pytest.mark.parametrize("name", ["search_web", "fetch_page"])
def test_the_web_tools_are_ordinary_registry_entries(name):
    """They ride #34's mechanism rather than a second one."""
    assert name in tools.REGISTRY
    declaration = next(d for d in tools.declarations() if d["function"]["name"] == name)
    assert declaration["function"]["description"]
    assert declaration["function"]["parameters"]["type"] == "object"


@pytest.mark.parametrize("name", ["search_web", "fetch_page"])
def test_operational_settings_are_not_offered_to_the_model(name):
    """The result count and timeouts belong to the user. run() refuses any
    argument a tool did not declare, so they cannot be set by asking."""
    declared = set(tools.REGISTRY[name].parameters["properties"])

    assert not declared & {"limits", "max_results", "timeout", "page_characters"}


# --- what #34's machinery should already give -------------------------------


def a_search_call(query: str = "what is a pathlib"):
    from axiom.backend import Call

    return Call("search_web", {"query": query})


def a_fetch_call(url: str = PAGE):
    from axiom.backend import Call

    return Call("fetch_page", {"url": url})


def test_the_query_is_shown_before_a_search_runs(monkeypatch, capsys):
    """AC 13."""
    import axiom
    from conftest import StubBackend, feed

    given_results(monkeypatch, [{"title": "T", "href": "https://x/y", "body": "b"}])
    feed(monkeypatch, ["find out", "/exit"])

    axiom.main([], using=StubBackend(turns=[[a_search_call("teal cats")], ["done"]]))

    assert "search_web(query=teal cats)" in capsys.readouterr().out


def test_the_address_is_shown_before_a_page_is_fetched(monkeypatch, capsys):
    """AC 14."""
    import axiom
    from conftest import StubBackend, feed

    given_page(monkeypatch, "<html><body><article><p>" + "text " * 30 + "</p></article></body></html>")
    feed(monkeypatch, ["read it", "/exit"])

    axiom.main([], using=StubBackend(turns=[[a_fetch_call()], ["done"]]))

    assert f"fetch_page(url={PAGE})" in capsys.readouterr().out


def test_fetched_content_is_marked_apart_from_axioms_words(monkeypatch, capsys):
    """AC 15."""
    import axiom
    from conftest import StubBackend, feed

    given_page(
        monkeypatch,
        "<html><body><article><p>" + "Distinctive sentence. " * 20 + "</p></article></body></html>",
    )
    feed(monkeypatch, ["read it", "/exit"])

    axiom.main([], using=StubBackend(turns=[[a_fetch_call()], ["My own words."]]))
    out = capsys.readouterr().out

    assert "  | Distinctive sentence." in out
    assert "My own words." in out
    assert "  | My own words." not in out


def test_a_page_becomes_part_of_the_conversation(monkeypatch, capsys):
    """AC 25: a later turn can refer to what was read."""
    import axiom
    from conftest import StubBackend, feed

    given_page(
        monkeypatch,
        "<html><body><article><p>" + "Biscuit is ginger. " * 20 + "</p></article></body></html>",
    )
    backend = StubBackend(turns=[[a_fetch_call()], ["noted"]])
    feed(monkeypatch, ["read it", "/exit"])

    axiom.main([], using=backend)
    capsys.readouterr()

    tool_message = [m for m in backend.streamed[1] if m.get("role") == "tool"][0]
    assert "Biscuit is ginger." in tool_message["content"]
    assert tool_message["tool_name"] == "fetch_page"


def test_a_cited_address_survives_compaction():
    """AC 26 names the addresses specifically.

    #34 cycle 6 made compaction render a call's arguments, which is what
    carries the address into the summary. Without it a summary would record
    what a page said and not which page.
    """
    import axiom

    history = [
        {"role": "user", "content": "what does it say?"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"function": {"name": "fetch_page", "arguments": {"url": PAGE}}}
            ],
        },
        {"role": "tool", "content": "Biscuit is ginger.", "tool_name": "fetch_page"},
        {"role": "assistant", "content": "It says Biscuit is ginger."},
    ] * 3

    class Recorder:
        def __init__(self):
            self.saw = ""

        def complete(self, model, messages):  # noqa: ANN001, ARG002
            self.saw = messages[0]["content"]
            return "S"

    recorder = Recorder()
    axiom.compaction.compacted_history(recorder, "m", history, kept_pairs=0)

    assert PAGE in recorder.saw, "the address did not reach the summary"
    assert "fetch_page" in recorder.saw


def test_with_no_network_the_web_fails_plainly_and_chat_still_works(
    monkeypatch, capsys
):
    """AC 23, and the second half is the point.

    Ollama is local. Losing the network must cost the web and nothing else -
    a session that stopped answering because DuckDuckGo was unreachable would
    be broken in a way the user cannot fix.
    """
    import axiom
    from conftest import StubBackend, feed

    given_search_raises(monkeypatch, OSError("getaddrinfo failed"))
    given_page(monkeypatch, raises=httpx.ConnectError("getaddrinfo failed"))

    assert search().startswith("error:")
    assert fetch().startswith("error:")

    feed(monkeypatch, ["what is two plus two?", "/exit"])
    axiom.main([], using=StubBackend(turns=[["Four."]]))

    assert "Four." in capsys.readouterr().out


def test_the_web_tools_are_absent_when_the_web_is_switched_off(monkeypatch, capsys):
    """AC 29: and the other tools survive it."""
    import axiom
    from conftest import StubBackend, feed

    backend = StubBackend(turns=[["hello"]])
    feed(monkeypatch, ["hi", "/exit"])

    axiom.main(["--no-web"], using=backend)
    capsys.readouterr()

    offered = {t["function"]["name"] for t in backend.tools_sent[0]}
    assert not offered & tools.WEB_TOOLS, "web tools were offered with --no-web"
    assert "read_file" in offered, "switching off the web took away the file tools"


# --- interrupting a search or a fetch ---------------------------------------


def test_an_interrupt_during_a_search_is_not_swallowed(monkeypatch):
    """AC 24. search_web catches Exception broadly to report provider trouble;
    KeyboardInterrupt is a BaseException and must pass straight through, or the
    turn never unwinds and the prompt never comes back."""
    given_search_raises(monkeypatch, KeyboardInterrupt())

    with pytest.raises(KeyboardInterrupt):
        search()


def test_an_interrupt_during_a_fetch_is_not_swallowed(monkeypatch):
    given_page(monkeypatch, raises=KeyboardInterrupt())

    with pytest.raises(KeyboardInterrupt):
        fetch()


def test_a_cancelled_fetch_leaves_the_session_usable(monkeypatch, capsys):
    """AC 24: stops it and returns to the prompt."""
    import axiom
    from conftest import StubBackend, feed

    given_page(monkeypatch, raises=KeyboardInterrupt())
    backend = StubBackend(turns=[[a_fetch_call()], ["second answer"]])
    feed(monkeypatch, ["read it", "ask something else"])

    axiom.main([], using=backend)
    out = capsys.readouterr()

    assert "cancelled" in out.err
    assert "second answer" in out.out, "the session did not survive the interrupt"


def test_a_cancelled_fetch_leaves_nothing_of_the_turn_in_history(
    monkeypatch, capsys
):
    """The same all-or-nothing rule #34 established for tools generally."""
    import axiom
    from conftest import StubBackend, feed

    given_page(monkeypatch, raises=KeyboardInterrupt())
    backend = StubBackend(turns=[[a_fetch_call()], ["second answer"]])
    feed(monkeypatch, ["read it", "ask something else"])

    axiom.main([], using=backend)
    capsys.readouterr()

    assert [m["content"] for m in backend.streamed[1]] == ["ask something else"]


def test_read_file_sends_a_web_address_to_the_right_tool():
    """Found live: a model handed a URL reached for the tool that says "read".

    On Windows the address was mangled into a path first, so the failure was an
    unhelpable OS error, and the model gave up and answered from memory - which
    is what AC 5 exists to prevent. A pointed message lets it correct itself on
    the next round instead.
    """
    result = tools.run("read_file", {"path": "https://example.invalid/page"})

    assert "web address" in result
    assert "fetch_page" in result


def test_a_local_path_is_still_read_normally(tmp_path):
    target = tmp_path / "notes.txt"
    target.write_text("local", encoding="utf-8")

    assert tools.run("read_file", {"path": str(target)}) == "local"


# --- sources: what axiom actually retrieved ---------------------------------


def run_turn(monkeypatch, capsys, turns, lines=None):
    import axiom
    from conftest import StubBackend, feed

    feed(monkeypatch, lines or ["go", "/exit"])
    axiom.main([], using=StubBackend(turns=turns))
    return capsys.readouterr().out


def test_pages_that_were_read_are_named(monkeypatch, capsys):
    """AC 11, from data rather than from the model's word for it."""
    from axiom.backend import Call

    given_page(
        monkeypatch,
        "<html><body><article><p>" + "Content here. " * 20 + "</p></article></body></html>",
    )
    out = run_turn(
        monkeypatch,
        capsys,
        [
            [
                Call("fetch_page", {"url": "https://a.invalid/one"}),
                Call("fetch_page", {"url": "https://b.invalid/two"}),
            ],
            ["answered"],
        ],
    )

    assert "read: https://a.invalid/one, https://b.invalid/two" in out


def test_a_page_that_failed_is_never_named_as_a_source(monkeypatch, capsys):
    """AC 12 at its sharpest: presenting an address as read when it was not."""
    from axiom.backend import Call

    given_page(monkeypatch, raises=httpx.ConnectError("refused"))
    out = run_turn(
        monkeypatch,
        capsys,
        [[Call("fetch_page", {"url": "https://gone.invalid/x"})], ["could not"]],
    )

    assert "read:" not in out
    assert "found, not read:" not in out


def test_search_results_are_not_claimed_as_pages_read(monkeypatch, capsys):
    """AC 12: a snippet is not a page. Listing results as sources would be the
    same lie the model was making, told by axiom instead."""
    from axiom.backend import Call

    given_results(
        monkeypatch,
        [
            {"title": "One", "href": "https://a.invalid/one", "body": "snippet one"},
            {"title": "Two", "href": "https://b.invalid/two", "body": "snippet two"},
        ],
    )
    out = run_turn(
        monkeypatch,
        capsys,
        [[Call("search_web", {"query": "anything"})], ["answered from snippets"]],
    )

    assert "found, not read: https://a.invalid/one, https://b.invalid/two" in out
    assert "axiom: read:" not in out, "a snippet was claimed as a page read"


def test_a_page_found_then_read_is_listed_only_as_read(monkeypatch, capsys):
    from axiom.backend import Call

    given_results(
        monkeypatch, [{"title": "One", "href": "https://a.invalid/one", "body": "s"}]
    )
    given_page(
        monkeypatch,
        "<html><body><article><p>" + "Real content. " * 20 + "</p></article></body></html>",
    )
    out = run_turn(
        monkeypatch,
        capsys,
        [
            [Call("search_web", {"query": "anything"})],
            [Call("fetch_page", {"url": "https://a.invalid/one"})],
            ["answered"],
        ],
    )

    assert "read: https://a.invalid/one" in out
    assert "found, not read:" not in out


def test_a_turn_with_no_web_use_says_nothing_about_sources(monkeypatch, capsys):
    out = run_turn(monkeypatch, capsys, [["just an answer"]])

    assert "axiom: read:" not in out
    assert "found, not read:" not in out


def test_sources_do_not_carry_over_to_the_next_answer(monkeypatch, capsys):
    """A later answer inheriting an earlier question's sources would be the
    same false claim, one turn removed."""
    import axiom
    from axiom.backend import Call
    from conftest import StubBackend, feed

    given_page(
        monkeypatch,
        "<html><body><article><p>" + "Content. " * 20 + "</p></article></body></html>",
    )
    feed(monkeypatch, ["read it", "now something else", "/exit"])
    axiom.main(
        [],
        using=StubBackend(
            turns=[
                [Call("fetch_page", {"url": "https://a.invalid/one"})],
                ["answered"],
                ["a second answer with no web at all"],
            ]
        ),
    )

    second_answer = capsys.readouterr().out.split("a second answer")[-1]
    assert "axiom: read:" not in second_answer


def test_an_address_inside_a_snippet_is_not_taken_for_a_result():
    """The parser reads our own format - one bare address on its own line."""
    from axiom import tools as t

    block = (
        "A title\n"
        "https://real.invalid/page\n"
        "A snippet that mentions https://mentioned.invalid/x in passing.\n"
    )

    assert t.addresses_in(block) == ["https://real.invalid/page"]
