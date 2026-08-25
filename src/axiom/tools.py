"""What axiom can do, as the model sees it and as we run it.

One declaration per tool, sent unchanged to every model. Nothing here varies by
model: the probe in this loop's cycle-1 log found qwen2, gemma4 and qwen35 all
return the same structured call for the same declaration, so a per-model branch
would be inventing a difference that is not there.
"""

import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import ddgs
import ddgs.exceptions
import httpx
import psutil
import trafilatura


@dataclass(frozen=True)
class Tool:
    """One thing axiom can do.

    `parameters` is JSON Schema, because that is what the model is given.
    `run` takes the arguments as keywords and returns what the model sees.
    """

    name: str
    description: str
    parameters: dict
    run: Callable[..., str]
    needs_limits: bool = False


@dataclass(frozen=True)
class Limits:
    """Operational settings a tool may need.

    Never model-visible: these belong to the user, and run() refuses any
    argument a tool did not declare in its schema, so a model cannot set them
    by asking.
    """

    working_directory: str | None = None  # None means where axiom was started
    command_timeout: float = 30.0
    search_results: int = 5
    fetch_timeout: float = 20.0
    page_characters: int = 20_000


DEFAULT_LIMITS = Limits()

# The tools that reach the network. Named here so a caller can leave them out
# without knowing how they are implemented.
WEB_TOOLS = frozenset({"search_web", "fetch_page"})


def working_directory(limits: "Limits") -> Path:
    """Where this run's work lands. `None` means where axiom was started."""
    return Path(limits.working_directory or Path.cwd())


def _resolve(path: str, limits: "Limits") -> Path:
    """A path argument, resolved the way the working directory promises.

    A relative name lands in the working directory rather than wherever the
    process happens to be. Before this, `--working-directory` reached
    `run_command` as its `cwd` and reached the file tools not at all, so the
    same relative name meant two different places depending on which tool
    used it - and the setting could not mean what it says.

    An absolute path is untouched. That is #41 AC 5: a path the user named is
    used exactly as they wrote it, wherever it points.
    """
    asked = Path(path)
    return asked if asked.is_absolute() else working_directory(limits) / asked


# Arguments that name a place on disk. Listed rather than guessed, so a tool
# gaining a string argument does not silently start being path-resolved.
PATH_ARGUMENTS = frozenset({"path"})


def outside(arguments: dict, limits: "Limits") -> list[str]:
    """Resolved paths in this call that land outside the working directory.

    Shown to the user before the tool runs (#41 AC 6). **Visibility only** -
    nothing is blocked and nothing is asked. Enforcement belongs to the
    security stories, and AC 5 exists to stop a guard being built here.

    Resolved rather than echoed, because `notes.txt` on screen says nothing
    about where it actually lands, and that is the whole surprise this exists
    to prevent.
    """
    base = working_directory(limits).resolve()
    found = []
    for name in PATH_ARGUMENTS:
        value = arguments.get(name)
        if not isinstance(value, str) or value.startswith(("http://", "https://")):
            continue
        try:
            resolved = _resolve(value, limits).resolve()
        except OSError:  # a name the filesystem will not even resolve
            continue
        if resolved != base and base not in resolved.parents:
            found.append(str(resolved))
    return found


def system_prompt(limits: "Limits") -> str:
    """What the model is told before it does anything.

    Built from the same `Limits` the tools are handed, so what the model is
    told and what actually applies cannot drift - there is one value, not a
    description of one.

    Describes the limits, not the inventory. No tool count and no tool names:
    the list already varies with `--no-web` and #43 will make it vary per run,
    and a prompt naming a number would go wrong without anything failing.

    The working directory is stated as the place work lands rather than as a
    value in a list. Measured reason: asked how long a command may run,
    qwen2.5:7b answered from the prompt; asked what directory it was working
    in, from the same list, it called `read_file` instead. A duration reads as
    a fact and a path reads as something to go and look up.
    """
    return (
        "You are axiom, a terminal assistant.\n"
        "\n"
        f"You are working in {working_directory(limits)}. Files you create or "
        "change go there. Use a path somewhere else only when the user names "
        "one, and when they do, use it exactly as they wrote it.\n"
        "\n"
        "The limits you are working within:\n"
        f"- a command is stopped if it runs longer than "
        f"{limits.command_timeout:g} seconds\n"
        f"- a page you fetch is stopped after {limits.fetch_timeout:g} seconds "
        f"and kept to {limits.page_characters} characters\n"
        f"- a search returns {limits.search_results} results\n"
        "\n"
        "These are facts about how you are running, not settings. Neither you "
        "nor the user can change them during this run. If a request needs more "
        "than one of them allows, say so rather than trying anyway."
    )


def read_file(path: str, limits: "Limits" = DEFAULT_LIMITS) -> str:
    # A model handed a web address will reach for the tool that says "read".
    # Without this it becomes an unhelpable OS error - on Windows the address
    # is mangled into a path first - and the model answers from memory instead
    # of saying it could not read the page.
    if path.startswith(("http://", "https://")):
        return f"error: {path} is a web address - use fetch_page to read it"
    return _resolve(path, limits).read_text(encoding="utf-8")


def write_file(path: str, content: str, limits: "Limits" = DEFAULT_LIMITS) -> str:
    target = _resolve(path, limits)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"wrote {len(content)} characters to {target}"


def edit_file(path: str, old: str, new: str, limits: "Limits" = DEFAULT_LIMITS) -> str:
    """Replace one stretch of a file and leave every other byte alone.

    Refuses when the text appears more than once: the model asked to change
    one thing, and silently changing three would be a different edit than the
    one it described to the user.
    """
    target = _resolve(path, limits)
    original = target.read_text(encoding="utf-8")
    found = original.count(old)
    if found == 0:
        return f"error: that text does not appear in {target}"
    if found > 1:
        return f"error: that text appears {found} times in {target} - narrow it down"
    target.write_text(original.replace(old, new, 1), encoding="utf-8")
    return f"replaced one occurrence in {target}"


def delete_file(path: str, limits: "Limits" = DEFAULT_LIMITS) -> str:
    target = _resolve(path, limits)
    target.unlink()
    return f"deleted {target}"


def search_web(query: str, limits: "Limits" = None) -> str:
    """Search the web and return what was found, one result per block."""
    limits = limits or DEFAULT_LIMITS
    try:
        found = ddgs.DDGS().text(query, max_results=limits.search_results)
    except ddgs.exceptions.RatelimitException as throttled:
        # Its own message, distinct from every other failure: the advice is to
        # wait, and telling the user to check their network would be wrong.
        return f"error: the search provider is throttling us - wait and retry ({throttled})"
    except ddgs.exceptions.TimeoutException as slow:
        return f"error: the search provider did not answer in time ({slow})"
    except ddgs.exceptions.DDGSException as refused:
        return f"error: the search provider refused the request ({refused})"
    except Exception as unreachable:  # noqa: BLE001
        return f"error: could not reach the search provider ({unreachable})"

    if not found:
        return f"no results for {query!r}"

    return "\n\n".join(
        "{}\n{}\n{}".format(
            item.get("title", ""), item.get("href", ""), item.get("body", "")
        )
        for item in found
    )


# Types whose body is markup to be reduced, not content to be kept.
HTML_TYPES = frozenset({"text/html", "application/xhtml+xml"})

# Text that does not arrive under `text/`. Raw hosts serve markdown, rst, csv
# and javascript all as `text/plain`, but other hosts announce them properly,
# and a body is no less readable for being labelled precisely.
TEXT_TYPES = frozenset(
    {
        "application/ecmascript",
        "application/graphql",
        "application/javascript",
        "application/json",
        "application/sql",
        "application/toml",
        "application/x-yaml",
        "application/xml",
        "application/yaml",
    }
)


def _media_type(page: httpx.Response) -> str:
    """The bare media type: lowercased, with any parameters removed.

    Real headers arrive in three shapes and all three were measured:
    `text/plain; charset=utf-8`, a bare `text/plain` with no parameter at all,
    and `application/pdf; qs=0.001` - a parameter on a *binary* type, which is
    why the split has to happen before anything compares.
    """
    return (page.headers.get("content-type") or "").split(";")[0].strip().lower()


def _treat_as(media_type: str) -> str | None:
    """How a body of this type is read: 'html', 'text', or None for neither.

    None means not readable at all, and its bytes are never returned.

    A body announcing no type is treated as text. Text is the only treatment
    that can hand back exactly what was served: guessing HTML would run a
    reducer over something that may not be markup, and guessing unreadable
    would refuse a page that is most likely fine.
    """
    if not media_type:
        return "text"
    if media_type in HTML_TYPES:
        return "html"
    if media_type.startswith("text/"):
        return "text"
    if media_type in TEXT_TYPES or media_type.endswith(("+json", "+xml")):
        return "text"
    return None


def fetch_page(url: str, limits: "Limits" = None) -> str:
    """Fetch one page and return what it says.

    Three outcomes, and the type decides which: markup is reduced to its prose,
    text is returned as it was served, and anything else is refused without its
    bytes ever being read.
    """
    limits = limits or DEFAULT_LIMITS
    try:
        page = httpx.get(url, timeout=limits.fetch_timeout, follow_redirects=True)
    except httpx.TimeoutException:
        return f"error: {url} did not answer within {limits.fetch_timeout:g} seconds"
    except httpx.HTTPError as unreachable:
        return f"error: could not reach {url} ({unreachable})"

    # httpx does not raise on 4xx or 5xx, and an error page has a body that
    # extracts into convincing prose. Returning it would hand the model an
    # error page as though it were the page asked for.
    if page.status_code >= 400:
        return f"error: {url} answered {page.status_code}"

    media_type = _media_type(page)
    treatment = _treat_as(media_type)

    # Decided before anything touches `page.text`, deliberately: decoding a PNG
    # returns control characters rather than raising, and a PDF decodes into
    # something that looks enough like text to pass a careless eye. Neither is
    # ever allowed to become content, at any length.
    if treatment is None:
        return f"error: {url} is {media_type} - not readable as text"

    # Reached, and there was nothing in it. Not a failure: nothing went wrong,
    # and "nothing" is a true answer about a page that really was served.
    if not page.content:
        return f"warning: {url} is empty"

    if treatment == "html":
        text = trafilatura.extract(page.text)
        # Distinct from empty above, and deliberately a different message: this
        # page had a body, it just carried no prose - navigation, script, or
        # markup with nothing to say.
        if not text:
            return f"error: {url} has no readable text"
    else:
        # Verbatim. `trafilatura.extract` joins paragraphs and drops chrome,
        # which is right for markup and wrong here - in a source file the line
        # breaks and the indentation *are* the content.
        text = page.text

        # A page announcing no type is *judged by its content*, not assumed
        # readable - so a body that is not text is refused even though the
        # missing header sent it down this branch. A NUL is the same test
        # `file` and git use: binary formats carry them and text does not.
        #
        # Read from the decoded text rather than the raw bytes deliberately.
        # utf-16 is half zero bytes and would fail a raw check, but decodes
        # through its declared charset into ordinary text with no NUL in it.
        #
        # Applied to every text body, not only the typeless one. A server that
        # announces `text/plain` over a PNG is lying, and the cost of not
        # believing it is nothing: real text does not contain NUL.
        if "\x00" in text:
            return f"error: {url} is binary - not readable as text"

        if not text.strip():
            return f"warning: {url} is empty"

    if len(text) > limits.page_characters:
        withheld = len(text) - limits.page_characters
        return (
            text[: limits.page_characters]
            + f"\n\n[cut here - {withheld} more characters not included]"
        )
    return text


# Prefixes are this module's format, so the test for them lives here beside the
# code that writes them - the same reason `addresses_in` sits next to the
# search format it parses.
NOT_A_SOURCE = ("error:", "warning:")


def was_read(result: str) -> bool:
    """Whether a `fetch_page` result means the page was actually read.

    Two of the three outcomes are not a source: a failure, and a page that was
    reached and found empty. An empty page is not an error - nothing went
    wrong - but there is nothing in it to cite either.
    """
    return not result.startswith(NOT_A_SOURCE)


def addresses_in(result: str) -> list[str]:
    """The addresses a search result names.

    The format is ours - one bare address on a line of its own - so an address
    mentioned inside a snippet is not mistaken for a result. Parser and format
    live together deliberately; splitting them is how one drifts from the other.
    """
    return [
        line
        for line in result.splitlines()
        if line.startswith(("http://", "https://")) and " " not in line
    ]


def _report(stdout: str, stderr: str, status: int) -> str:
    """What the model is told about a finished command.

    Both streams, and the exit status whenever it is not success - a command
    that failed must never read as one that worked.
    """
    parts = []
    if stdout:
        parts.append(stdout.rstrip("\n"))
    if stderr:
        parts.append("stderr:\n" + stderr.rstrip("\n"))
    if status != 0:
        parts.append(f"error: exited with status {status}")
    elif not parts:
        parts.append("(finished with no output)")
    return "\n".join(parts)


def failure_kind(result: str) -> str:
    """What kind of failure a result is, with the command's own output removed.

    #41 AC 9 asks whether a command failed "the same way" twice. Comparing
    whole results answers a different question: a command whose output carries
    a pid, a timestamp, a duration or a temp path never produces the same
    string twice, so the check never fires and the criterion is decorative.

    Found by attacking it in cycle 4 - the same command exiting 9 twice gave
    'stderr:\\n24136\\nerror: exited with status 9' and
    'stderr:\\n20664\\nerror: exited with status 9'. Same command, same
    failure, different pid.

    The failure is the `error:` line `_report` adds. Everything else is what
    the command printed. Parser and format live together, as with
    `addresses_in` and `was_read`.
    """
    return "\n".join(line for line in result.splitlines() if line.startswith("error:"))


def _kill_tree(pid: int) -> None:
    """Kill a process and everything it started.

    Killing only the process is not enough: with shell=True the child is a
    shell, and the program the user actually asked about is its grandchild.
    Killing the shell alone leaves that program running - and holding the
    output pipe open, so waiting on it blocks for as long as it wants to live.
    """
    try:
        parent = psutil.Process(pid)
        doomed = [*parent.children(recursive=True), parent]
    except psutil.Error:
        return
    for process in doomed:
        try:
            process.kill()
        except psutil.Error:
            pass  # already gone, which is the outcome we wanted


def run_command(command: str, limits: "Limits" = DEFAULT_LIMITS) -> str:
    process = subprocess.Popen(  # noqa: S602
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=limits.working_directory,
    )
    try:
        stdout, stderr = process.communicate(timeout=limits.command_timeout)
    except subprocess.TimeoutExpired:
        _kill_tree(process.pid)
        process.communicate()  # returns now that nothing holds the pipes open
        # Named as a rule rather than an incident (#41 AC 7). The old wording -
        # "still running after N seconds - stopped it" - was the same shape as
        # "exited with status 3", so a retry looked worth trying. It never is:
        # the bound applies to every command and cannot be raised from here.
        return (
            f"error: stopped at the {limits.command_timeout:g} second limit that "
            f"applies to every command. Running it again will stop at the same "
            f"point - the limit is not something this session can raise."
        )
    except KeyboardInterrupt:
        # The user cancelled while this was running. Kill it before unwinding:
        # letting the turn end with the process still going would leave work
        # happening that nobody is waiting for and nobody can see.
        _kill_tree(process.pid)
        process.communicate()
        raise
    return _report(stdout, stderr, process.returncode)


REGISTRY: dict[str, Tool] = {
    tool.name: tool
    for tool in (
        Tool(
            name="read_file",
            description=(
                "Read a local file from disk. For a web address, use fetch_page "
                "instead."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path of the file to read.",
                    }
                },
                "required": ["path"],
            },
            run=read_file,
            needs_limits=True,
        ),
        Tool(
            name="write_file",
            description="Create a file, or replace one entirely, with given content.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to write to."},
                    "content": {"type": "string", "description": "What to write."},
                },
                "required": ["path", "content"],
            },
            run=write_file,
            needs_limits=True,
        ),
        Tool(
            name="edit_file",
            description=(
                "Replace one exact stretch of text in a file, leaving the rest "
                "unchanged. The text to replace must appear exactly once."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path of the file."},
                    "old": {
                        "type": "string",
                        "description": "Exact text to replace. Must be unique in the file.",
                    },
                    "new": {
                        "type": "string",
                        "description": "What to put in its place.",
                    },
                },
                "required": ["path", "old", "new"],
            },
            run=edit_file,
            needs_limits=True,
        ),
        Tool(
            name="delete_file",
            description="Delete a file.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path of the file."}
                },
                "required": ["path"],
            },
            run=delete_file,
            needs_limits=True,
        ),
        Tool(
            name="run_command",
            description=(
                "Run a shell command and return its output. Any program on the "
                "machine can be run this way."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The command line to run.",
                    }
                },
                "required": ["command"],
            },
            run=run_command,
            needs_limits=True,
        ),
        Tool(
            name="search_web",
            description=(
                "Search the web and return the title, address and a snippet for "
                "each result. Use this to find pages; use fetch_page to read one. "
                "When you use anything from a result, quote its address exactly as "
                "listed above. Never write an address that is not in the results."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What to search for."}
                },
                "required": ["query"],
            },
            run=search_web,
            needs_limits=True,
        ),
        Tool(
            name="fetch_page",
            description=(
                "Fetch one web page over http or https and return its readable "
                "text. Use this for any address, whether or not it came from a "
                "search. This is the only tool that can read a web page. When you "
                "use what it returns, quote the address in your answer."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The address to read."}
                },
                "required": ["url"],
            },
            run=fetch_page,
            needs_limits=True,
        ),
    )
}


def declarations() -> list[dict]:
    """The tools as they are sent to a model."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }
        for tool in REGISTRY.values()
    ]


def run(name: str, arguments: dict, limits: Limits = DEFAULT_LIMITS) -> str:
    """Run a call and return what the model should be told.

    A failure is returned rather than raised: the model is the one that has to
    act on it, and a tool that cannot do its job is not a reason to end the
    turn. The session sees a result either way.
    """
    tool = REGISTRY.get(name)
    if tool is None:
        return f"error: there is no tool named {name!r}"

    if not isinstance(arguments, dict):
        return f"error: {name} was given arguments that are not a mapping"

    # Only what the tool declared. A model inventing an argument gets told so,
    # and cannot reach a keyword the schema does not offer it - the time limit,
    # for instance, which belongs to the user rather than to the model.
    declared = set(tool.parameters.get("properties", {}))
    unexpected = sorted(set(arguments) - declared)
    if unexpected:
        return f"error: {name} does not take {', '.join(unexpected)}"

    try:
        if tool.needs_limits:
            return tool.run(**arguments, limits=limits)
        return tool.run(**arguments)
    except TypeError as wrong_arguments:
        return f"error: {name} was called wrongly - {wrong_arguments}"
    except OSError as failed:
        return f"error: {failed.strerror or failed}: {failed.filename or ''}".strip()
    except Exception as failed:  # noqa: BLE001
        return f"error: {failed}"
