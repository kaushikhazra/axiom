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
